#!/usr/bin/env bash
# Author: Brent Thompson <brent.thompson@ucf.edu>
# Status of this user's sweep jobs: the queue, expected starts, today's finished jobs, and for each running sweep
# the stage each domain is on (logs written by the current job only) with an error count. Run from the repo folder:
#   scripts/slurm-status.sh
cd "$(dirname "$0")/.." || exit 1
echo "== queue"; squeue -u "$USER" -o "%.8i %.26j %.8T %.10M %.10l %.6D %R"
echo "== expected starts"; squeue -u "$USER" -t PD -h --start -o "%.8i %.26j %S" 2>/dev/null
echo "== finished today"
sacct -u "$USER" -S "$(date +%F)T00:00" -X -n -o JobID,JobName%26,State,Elapsed,End | grep -vE "RUNNING|PENDING" | tail -15
echo "== running sweeps"
for j in $(squeue -u "$USER" -h -t R -o %i); do
    s=$(grep -m1 -oE "^sweep [^:]+" "kw-sweep-$j.out" 2>/dev/null | cut -d' ' -f2)
    [ -n "$s" ] || { echo "$j: starting (model loading)"; continue; }
    t=$(squeue -h -j "$j" -o %S)
    logs=$(find "outputs/sweep-$s" -name "*-attempt*.log" -newermt "$t" 2>/dev/null | sort)
    [ -n "$logs" ] || { echo "$j $s: model server up, runs not started"; continue; }
    for log in $logs; do
        printf "%s  %-58s %-22s %s errors\n" "$j" "$(basename "$log" .log)" \
            "$(grep -oE "stage [0-9]/[0-9]: [a-z]+" "$log" | tail -1)" "$(grep -ciE "malformed|Traceback" "$log")"
    done
    grep -hE "finished \(exit|merged|damaged" "kw-sweep-$j.out" | tail -4 | sed "s/^/$j  /"
done
