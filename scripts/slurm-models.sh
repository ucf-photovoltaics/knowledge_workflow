#!/usr/bin/env bash
# Author: Brent Thompson <brent.thompson@ucf.edu>
# Model comparison: one scripts/slurm-sweep.sh job per model, all on the same use case, corpus size, embedding model
# and temperature, so the runs differ only by LLM. Run on the login node from the repo folder:
#
#   scripts/slurm-models.sh small                 # every small model (one copy per GPU)
#   scripts/slurm-models.sh mid large             # mid and large models (split across both GPUs)
#   scripts/slurm-models.sh all --after 939999    # hold every job until job 939999 succeeds
#   scripts/slurm-models.sh small --dry-run       # print the sbatch commands only
#
# Each model's sweep is <use case>-<model tag>-n<size>, so rerunning this resumes unfinished sweeps and skips models
# that are finished or already queued. Weights must be downloaded first (hf download <repo>; Llama and Gemma need
# their license accepted on Hugging Face); a model that isn't downloaded is skipped with a message.
# Overrides: USE_CASE (pv-cost-chain), LIMITS (25), PARTITION (normal), ACCOUNT (kdavis), GRES, MAIL_USER,
# ENV_FILE (~/kw-hpc/env.sh, sourced if present), GCS_BUCKET, LLM_TEMPERATURE, TIME_LIMIT (instead of each model's),
# EXCLUDE (nodes to avoid), ONLY (model tags to submit, e.g. ONLY="gemma4-26b gptoss-120b"), CPUS (32), MEM (240G), JOB_SUFFIX (added to job names, so a test can run beside a
# queued sweep of the same model).
# Quick test of every small model: LIMITS=2 TIME_LIMIT=01:30:00 scripts/slurm-models.sh small
# Start-up check of every model: model server + smoke test only (slurm-sweep.sh SMOKE_ONLY), on 1 GPU where it
# fits; tiny, short jobs that backfill ahead of the queue:
#   SMOKE_ONLY=1 LIMITS=1 TIME_LIMIT=00:30:00 GRES=gpu:nvidia_h100_pcie:1 CPUS=4 MEM=64G JOB_SUFFIX=-check \
#   MAX_MODEL_LEN=24576 GPU_MEMORY_UTILIZATION=0.95 scripts/slurm-models.sh all
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
ENV_FILE=${ENV_FILE:-$HOME/kw-hpc/env.sh}
[ -f "$ENV_FILE" ] && source "$ENV_FILE"
USE_CASE=${USE_CASE:-pv-cost-chain}
LIMITS=${LIMITS:-25}
PARTITION=${PARTITION:-normal}
ACCOUNT=${ACCOUNT:-kdavis}
GRES=${GRES:-gpu:nvidia_h100_pcie:2}
EXCLUDE=${EXCLUDE:-}   # nodes to avoid, e.g. EXCLUDE=evc26 (GPUs not visible to jobs)
MAIL_USER=${MAIL_USER:-}
CPUS=${CPUS:-32} MEM=${MEM:-240G} JOB_SUFFIX=${JOB_SUFFIX:-} ONLY=${ONLY:-}
HF_HUB=${HF_HOME:-$HOME/.cache/huggingface}/hub
MISTRAL="--tokenizer-mode mistral --config-format mistral --load-format mistral"

# tier  tag  Hugging Face repo  reasoning  time  placement (- = PARTITION/GRES, or GRES@partition)  extra vLLM flags
# Dropped after the n2 test (2026-10-17): phi4-mini, llama32-3b, llama31-8b lost 4-65% of extraction calls
# to runaway JSON even with whitespace-free decoding; their n2 sweeps stay as the low baseline. llama33-70b dropped
# too (only 31% of its relation/causal evidence found in the papers); mistral-small4 takes the large slot.
# gemma4-31b-think: Gemma 4 31B with thinking on (reasoning high; src/config.py doubles max_tokens for it).
# mistral-small4: FP8 MoE, ~120 GB of weights on 2 x H100 PCIe (kdavis cannot use highgpu or short): submit it with
#   MAX_MODEL_LEN=24576 GPU_MEMORY_UTILIZATION=0.95 so the KV cache fits. Its placement pins 2 GPUs, so a
#   GRES=...:1 override for the others never shrinks it; move it to bigger GPUs by editing the placement.
MODELS=$(cat <<EOF
small gemma4-e4b    google/gemma-4-E4B-it                         none 06:00:00 -
small ministral3-8b mistralai/Ministral-3-8B-Instruct-2512        none 06:00:00 - $MISTRAL
small gptoss-20b    openai/gpt-oss-20b                            low  08:00:00 -
mid   ministral3-14b mistralai/Ministral-3-14B-Instruct-2512      none 10:00:00 - $MISTRAL
mid   gemma4-26b    google/gemma-4-26B-A4B-it                     none 10:00:00 -
mid   gemma4-31b    google/gemma-4-31B-it                         none 12:00:00 -
mid   gemma4-31b-think google/gemma-4-31B-it                      high 16:00:00 - --reasoning-parser gemma4
large gptoss-120b   openai/gpt-oss-120b                           low  16:00:00 -
large mistral-small4 mistralai/Mistral-Small-4-119B-2603          none 16:00:00 gpu:nvidia_h100_pcie:2@normal --tokenizer-mode mistral --reasoning-parser mistral
EOF
)

tiers=() after="" dry=""
while [ $# -gt 0 ]; do
    case $1 in
        small|mid|large) tiers+=("$1") ;;
        all) tiers+=(small mid large) ;;
        --after) after=$2; shift ;;
        --dry-run) dry=1 ;;
        *) echo "unknown argument: $1 (small, mid, large, all, --after JOBID, --dry-run)"; exit 1 ;;
    esac
    shift
done
[ ${#tiers[@]} -gt 0 ] || { echo "give a tier: small, mid, large or all"; exit 1; }
unset TP DP WORKERS   # let slurm-sweep.sh size each model to the GPUs

while read -r tier tag repo reasoning time place extra; do
    [[ " ${tiers[*]} " == *" $tier "* ]] || continue
    [ -z "$ONLY" ] || [[ " $ONLY " == *" $tag "* ]] || continue
    sweep=$USE_CASE-$tag-n${LIMITS// /-}
    if [ -f "outputs/sweep-$sweep/report/report.html" ]; then echo "$tag: done (outputs/sweep-$sweep)"; continue; fi
    if [ -n "$(squeue -h -u "${USER:-$(id -un)}" -n "kw-$tag$JOB_SUFFIX" 2>/dev/null)" ]; then echo "$tag: already queued"; continue; fi
    if [ ! -d "$HF_HUB/models--${repo//\//--}" ]; then echo "$tag: skipped, not downloaded (hf download $repo)"; continue; fi
    gres=$GRES part=$PARTITION
    [ "$place" = - ] || { gres=${place%@*}; part=${place#*@}; }   # models too large for the default nodes
    cmd=(sbatch --parsable -J "kw-$tag$JOB_SUFFIX" -p "$part" -A "$ACCOUNT" --gres="$gres" --cpus-per-task="$CPUS" --mem="$MEM"
         --time="${TIME_LIMIT:-$time}" ${EXCLUDE:+--exclude=$EXCLUDE} ${after:+--dependency=afterok:$after}
         ${MAIL_USER:+--mail-type=END,FAIL --mail-user=$MAIL_USER} scripts/slurm-sweep.sh)
    if [ -n "$dry" ]; then
        echo "$tag: VLLM_MODEL=$repo VLLM_REASONING_EFFORT=$reasoning VLLM_EXTRA_ARGS='$extra' SWEEP_ID=$sweep ${cmd[*]}"
        continue
    fi
    job=$(USE_CASE=$USE_CASE LIMITS=$LIMITS SWEEP_ID=$sweep VLLM_MODEL=$repo VLLM_REASONING_EFFORT=$reasoning \
          VLLM_EXTRA_ARGS=$extra "${cmd[@]}") && echo "$tag: job $job, sweep $sweep" || echo "$tag: sbatch failed"
done <<<"$MODELS"
