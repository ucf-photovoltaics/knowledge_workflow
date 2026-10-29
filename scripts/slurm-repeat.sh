#!/usr/bin/env bash
# Author: Brent Thompson <brent.thompson@ucf.edu>
# Run-to-run drift: the same model, use case and corpus size run several times, every repeat asking the model again for
# everything (KW_FRESH=all, extraction included), then compared. Run on the login node from the repo folder:
#
#   scripts/slurm-repeat.sh --iterations 3                                     # newest sweep's model and use case, n5
#   scripts/slurm-repeat.sh --iterations 5 n10                                 # at n10
#   scripts/slurm-repeat.sh --iterations 3 n15 pv-cost-chain-gemma4-26b-n10    # another sweep's model and use case
#
# Repeats are the sweeps <use case>-<tag>-n<size>-r1 ... -r<iterations>; rerunning with more iterations submits only
# the new ones. A small job runs after the repeats end and writes scripts/compare_runs.py repeats to
# outputs/repeats/<use case>-<tag>-n<size>-x<iterations>.txt. PARTITION and ACCOUNT as in scripts/slurm-models.sh.
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}" || exit 1   # in the job, $0 is Slurm's copy of this script
ENV_FILE=${ENV_FILE:-$HOME/kw-hpc/env.sh}
[ -f "$ENV_FILE" ] && source "$ENV_FILE"
for d in "$HOME/.local/bin" "$HOME/.cargo/bin" "$HOME/kw-hpc/bin"; do
    [ -d "$d" ] && case ":$PATH:" in *":$d:"*) ;; *) PATH="$d:$PATH" ;; esac
done
export PATH

iterations=3 size=5 sweep="" compare=""
while [ $# -gt 0 ]; do
    case $1 in
        --iterations) iterations=${2:-}; shift ;;
        --compare) compare=1 ;;   # the comparison job
        n[0-9]*|[0-9]*) size=${1#n} ;;
        -*) echo "unknown option $1 (--iterations N, optional size such as n10, optional sweep id)"; exit 1 ;;
        *) sweep=${1#sweep-}; sweep=${sweep%/} ;;
    esac
    shift
done
[[ $iterations =~ ^[0-9]+$ && $iterations -ge 2 ]] || { echo "--iterations needs a number of at least 2"; exit 1; }
[[ $size =~ ^[0-9]+$ ]] || { echo "size must be a number such as n5 or 10"; exit 1; }

tags=$(sed -n '/^MODELS=/,/^EOF/p' scripts/slurm-models.sh | awk '$1 ~ /^(small|mid|large)$/ {print $2}')
parse() {  # sweep id -> "use_case tag", for sweeps named by scripts/slurm-models.sh
    local name=${1%-r[0-9]*} t
    for t in $tags; do
        [[ $name =~ ^(.+)-$t-n[0-9-]+$ ]] && { echo "${BASH_REMATCH[1]} $t"; return 0; }
    done
    return 1
}
if [ -z "$sweep" ]; then   # newest sweep folder with a model in its name
    for d in $(ls -dt outputs/sweep-*/ 2>/dev/null); do
        d=$(basename "$d"); parse "${d#sweep-}" >/dev/null && { sweep=${d#sweep-}; break; }
    done
    [ -n "$sweep" ] || { echo "no sweep named <use case>-<model tag>-n<size> in outputs/; give one"; exit 1; }
fi
read -r use_case tag <<<"$(parse "$sweep")" || true
[ -n "${tag:-}" ] || { echo "$sweep: not a <use case>-<model tag>-n<size> sweep from scripts/slurm-models.sh"; exit 1; }
base=$use_case-$tag-n$size
repeats=$(for r in $(seq 1 "$iterations"); do echo "$base-r$r"; done)

if [ -n "$compare" ]; then
    export UV_CACHE_DIR=${UV_CACHE_DIR:-$HOME/.cache/uv-kw}   # not the repo's Windows .uv-cache
    out=outputs/repeats/$base-x$iterations.txt
    uv run --with-requirements requirements.txt python scripts/compare_runs.py repeats $repeats | tee "$out"
    rc=${PIPESTATUS[0]}; echo "written: $out"; exit "$rc"
fi

command -v sbatch >/dev/null || { echo "run this on the cluster login node"; exit 1; }
ME=${USER:-$(id -un)}
echo "repeating $tag on $use_case at n$size, $iterations times (from sweep $sweep)"
for r in $(seq 1 "$iterations"); do
    s=outputs/sweep-$base-r$r
    grep -q '"integration".*"completed"' "$s/summary.csv" 2>/dev/null || rm -rf "$s/report"   # else a failed repeat counts as done
    KW_FRESH=all REPEAT=$r ONLY=$tag USE_CASE=$use_case LIMITS=$size JOB_SUFFIX=-n$size scripts/slurm-models.sh all
done
ids=$(for r in $(seq 1 "$iterations"); do squeue -h -u "$ME" -n "kw-$tag-n$size-r$r" -o %i; done | paste -sd:)
mkdir -p outputs/repeats
job=$(sbatch --parsable -J "kw-$tag-n$size-repeats" -p "${PARTITION:-normal}" -A "${ACCOUNT:-kdavis}" -c 1 --mem=4G \
      -t 00:30:00 ${ids:+--dependency=afterany:$ids} -o "outputs/repeats/$base-x$iterations-%j.out" \
      scripts/slurm-repeat.sh --compare --iterations "$iterations" "n$size" "$base") || exit 1
echo "comparison: job $job, after ${ids:-nothing (all repeats already ended)} -> outputs/repeats/$base-x$iterations.txt"
