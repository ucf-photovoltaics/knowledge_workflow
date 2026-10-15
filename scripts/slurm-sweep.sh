#!/usr/bin/env bash
# Paper sweep on one GPU node. vLLM serves the LLM (profile "vllm" in src/config.py); Ollama on CPU serves
# nomic-embed-text at localhost:11434 so the embedding cache from local runs is reused unchanged.
# Bash port of scripts/run-sweep.ps1, plus: the sweep stops when either model server is down instead of failing
# every remaining run. Resubmit with the same SWEEP_ID to resume; completed stages are skipped.
#
#   sbatch scripts/slurm-sweep.sh
#   SWEEP_ID=20261014-150000 sbatch scripts/slurm-sweep.sh                                  # resume
#   VLLM_MODEL=RedHatAI/Mistral-Small-4-119B-2603 sbatch --gres=gpu:2 scripts/slurm-sweep.sh   # FP8 on 2 GPUs
#
#SBATCH --job-name=kw-sweep
#SBATCH --nodes=1
#SBATCH --gres=gpu:4
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=48:00:00
#SBATCH --output=kw-sweep-%j.out
##SBATCH --partition=CHANGE_ME
##SBATCH --account=CHANGE_ME
set -uo pipefail

cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}" || exit 1
ROOT=$PWD
export LLM_PROFILE=vllm
export VLLM_MODEL=${VLLM_MODEL:-mistralai/Mistral-Small-4-119B-2603}
VLLM_PORT=${VLLM_PORT:-8000}
export VLLM_BASE_URL=http://localhost:$VLLM_PORT/v1
TP=${TP:-${SLURM_GPUS_ON_NODE:-$(nvidia-smi -L | wc -l)}}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-32768}   # same window as the local kw-qwen3.5-9b-32k runs
WORKERS=${WORKERS:-4}
LIMITS=${LIMITS:-"5 10 15 20 25 30 35 40 45 50"}
COLLECTIONS=${COLLECTIONS:-"tea reliability si-topcon"}
RETRIES=${RETRIES:-1}
SWEEP_ID=${SWEEP_ID:-$(date +%Y%m%d-%H%M%S)}
VLLM_ENV=${VLLM_ENV:-$HOME/.venvs/vllm}
OLLAMA=${OLLAMA:-$(command -v ollama || echo "$HOME/.local/ollama/bin/ollama")}
export HF_HOME=${HF_HOME:-$HOME/.cache/huggingface}
export UV_CACHE_DIR=${UV_CACHE_DIR:-$HOME/.cache/uv-kw}                  # not the repo's Windows .uv-cache
export UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/kw}   # nor its Windows .venv
export OLLAMA_HOST=127.0.0.1:11434
LOG=$ROOT/outputs/sweep-$SWEEP_ID
mkdir -p "$LOG"
echo "sweep $SWEEP_ID: $VLLM_MODEL, tensor parallel $TP, workers $WORKERS, sizes $LIMITS"

# ---- model servers ----
command -v uv >/dev/null || { echo "uv not found (curl -LsSf https://astral.sh/uv/install.sh | sh)"; exit 1; }
[ -x "$OLLAMA" ] || { echo "Ollama not found; set OLLAMA=/path/to/ollama"; exit 1; }
if [ ! -x "$VLLM_ENV/bin/vllm" ]; then
    uv venv --python 3.12 "$VLLM_ENV" && VIRTUAL_ENV=$VLLM_ENV uv pip install "vllm${VLLM_VERSION:+==$VLLM_VERSION}" || exit 1
fi
CUDA_VISIBLE_DEVICES='' "$OLLAMA" serve >"$LOG/ollama.log" 2>&1 &
OLLAMA_PID=$!
# shellcheck disable=SC2086  # VLLM_EXTRA_ARGS is a list of flags
"$VLLM_ENV/bin/vllm" serve "$VLLM_MODEL" --port "$VLLM_PORT" --tensor-parallel-size "$TP" \
    --max-model-len "$MAX_MODEL_LEN" --gpu-memory-utilization 0.90 --enable-prefix-caching \
    ${VLLM_EXTRA_ARGS:-} >"$LOG/vllm.log" 2>&1 &
VLLM_PID=$!
trap 'kill $VLLM_PID $OLLAMA_PID 2>/dev/null' EXIT

wait_for() {  # url name pid: up to 60 min (the first run downloads the model)
    for _ in $(seq 360); do
        curl -sf "$1" >/dev/null && return 0
        kill -0 "$3" 2>/dev/null || { echo "$2 exited; see $LOG/$2.log"; return 1; }
        sleep 10
    done
    echo "$2 not ready after 60 min"; return 1
}
wait_for http://127.0.0.1:11434/api/tags ollama $OLLAMA_PID || exit 2
"$OLLAMA" pull nomic-embed-text >/dev/null || exit 2
wait_for "http://localhost:$VLLM_PORT/health" vllm $VLLM_PID || exit 2
healthy() { curl -sf "http://localhost:$VLLM_PORT/health" >/dev/null && curl -sf http://127.0.0.1:11434/api/tags >/dev/null; }

PY=(uv run --with-requirements requirements.txt python)
# Smoke test through the pipeline's own client: JSON mode, reasoning off, embeddings.
"${PY[@]}" - <<'EOF' || { echo "smoke test failed"; exit 2; }
import json, time
from src.config import LLM
from src.tools import llm
t = time.time()
text, u = llm.chat("Return ONLY JSON.", 'Return {"ok": true, "bfo_category": "<BFO category of: solar cell>"}', LLM["model"], profile=LLM)
json.loads(text)
print(f"chat ok in {time.time() - t:.1f}s, {u.output_tokens} output tokens: {text[:200]}")
vec, _ = llm.embed(["solar cell"])
print(f"embedding ok: {len(vec[0])} dimensions")
EOF

# ---- sweep ----
SUMMARY=$LOG/summary.csv
echo '"kind","limit","run_id","status","detail"' >"$SUMMARY"
save() { printf '"%s","%s","%s","%s","%s"\n' "$1" "$2" "$3" "$4" "$5" >>"$SUMMARY"; }

run_kw() {  # id, then src.run arguments; --workers drops to 1 after a transient error, like run-sweep.ps1
    local id=$1; shift
    local args=("$@") attempt log
    for attempt in $(seq 0 "$RETRIES"); do
        healthy || { echo "model server down; stopping the sweep (resubmit with SWEEP_ID=$SWEEP_ID)"; exit 3; }
        log=$LOG/$id-attempt$attempt.log
        "${PY[@]}" -m src.run "${args[@]}" 2>&1 | tee "$log"
        [ "${PIPESTATUS[0]}" -eq 0 ] && return 0
        grep -qE 'APIConnectionError|APITimeoutError|InternalServerError|RateLimitError|HTTP (429|502|503|504)|ConnectionError|ConnectTimeout|ReadTimeout|database is locked|out of memory|overloaded' "$log" || return 1
        for i in "${!args[@]}"; do [ "${args[$i]}" = --workers ] && args[i+1]=1; done
        sleep 10
    done
    return 1
}

status() {  # prints: valid processed failed_count
    python3 - "$1" <<'EOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
d = json.loads(p.read_text(encoding="utf-8-sig")) if p.is_file() else {}
c = d.get("corpus", {})
v = d.get("valid", d.get("stages", {}).get("interop", {}).get("valid", False))
print(v is True, c.get("processed", 0), len(c.get("failed", [])))
EOF
}

for n in $LIMITS; do
    completed=()
    for col in $COLLECTIONS; do
        id=$col-n$n-$SWEEP_ID
        if ! run_kw "$id" all --collection "$col" --limit "$n" --run-id "$id" --workers "$WORKERS"; then
            save domain "$n" "$id" failed "Command failed; see attempt log."; continue
        fi
        read -r valid processed failed <<<"$(status "outputs/$id/run.json")"
        if [ "$valid" != True ] || [ "$processed" -lt 1 ]; then
            save domain "$n" "$id" invalid "Incomplete or structurally invalid; excluded from integration."
        elif [ "$failed" -gt 0 ]; then
            save domain "$n" "$id" partial "Failed papers; excluded from integration. Other runs continue."
        else
            completed+=("$id"); save domain "$n" "$id" completed "$processed papers processed; requested $n."
        fi
    done
    iid=integration-n$n-$SWEEP_ID
    if [ ${#completed[@]} -lt 2 ]; then
        save integration "$n" "$iid" skipped "Fewer than two successful domains at this size."; continue
    fi
    if ! run_kw "$iid" integrate --run-id "$iid" --workers "$WORKERS" --runs "${completed[@]}"; then
        save integration "$n" "$iid" failed "Command failed; see attempt log."; continue
    fi
    read -r valid _ _ <<<"$(status "outputs/$iid/validation.json")"
    joined=$(printf '%s, ' "${completed[@]}")
    if [ "$valid" = True ]; then save integration "$n" "$iid" completed "${joined%, }"
    else save integration "$n" "$iid" invalid "Structural validation failed."; fi
done

"${PY[@]}" -m src.figures --sweep-summary "$SUMMARY" --out "$LOG/report" --title "Paper sweep $SWEEP_ID" \
    >"$LOG/report.log" 2>&1 || save report "" "sweep-$SWEEP_ID-report" failed "see report.log"
echo "summary: $SUMMARY"; echo "report:  $LOG/report/report.html"
grep -q '"completed"' "$SUMMARY" && ! grep -qE '"(failed|invalid|partial|skipped)"' "$SUMMARY"
