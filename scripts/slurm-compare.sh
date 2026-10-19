#!/usr/bin/env bash
# Author: Brent Thompson <brent.thompson@ucf.edu>
# A model comparison at one corpus size, in one step. Run on the login node from the repo folder:
#
#   scripts/slurm-compare.sh                     # SIZE=25 for the default MODELS: submit each model's sweep that is not
#                                                # finished or queued, then a CPU job that waits for all of them,
#                                                # builds the comparison and emails it
#   SIZE=10 MODELS="gemma4-e4b gemma4-26b" scripts/slurm-compare.sh
#   scripts/slurm-compare.sh --test-mail         # send a one-line test email now, to check mail leaves the cluster
#
# Sweeps are <use case>-<tag>-n<SIZE>; the papers of a smaller size come from the extraction cache, so an n25 sweep
# after n10 extracts only the 15 new papers per domain. Jobs are named kw-<tag>-n<SIZE>.
# Overrides: SIZE (25), MODELS (best of each size at n10: gptoss-20b, gemma4-31b, gptoss-120b), TIME_LIMIT (each
# model's own from scripts/slurm-models.sh), MAIL_TO (br895930@ucf.edu), GCS_BUCKET.
# Mail goes through sendmail when the node has it, else the SMTP server named in .env (SMTP_HOST, SMTP_PORT 587 or 465,
# SMTP_USER, SMTP_PASSWORD, optional SMTP_FROM), else localhost:25. The report is also uploaded to the bucket, and
# Slurm sends its own end-of-job notice.
# Each sweep resumes where it stopped (completed stages are skipped) and ends with its own cross-domain integration;
# the comparison runs after every sweep has ended, whether it succeeded or not, and lists any it could not compare.
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}" || exit 1   # in the job, $0 is Slurm's copy of this script
ENV_FILE=${ENV_FILE:-$HOME/kw-hpc/env.sh}
[ -f "$ENV_FILE" ] && source "$ENV_FILE"
# Batch jobs get the submitting shell's PATH, which may lack tools added by hand in another login session.
for d in "$HOME/.local/bin" "$HOME/.cargo/bin" "$HOME/kw-hpc/bin" "$HOME/kw-hpc/google-cloud-sdk/bin"; do
    [ -d "$d" ] && case ":$PATH:" in *":$d:"*) ;; *) PATH="$d:$PATH" ;; esac
done
export PATH
MAIL_TO=${MAIL_TO:-br895930@ucf.edu}
ME=${USER:-$(id -un)}
USE_CASE=${USE_CASE:-pv-cost-chain}
SIZE=${SIZE:-25}
MODELS=${MODELS:-"gptoss-20b gemma4-31b gptoss-120b"}
export SIZE MODELS USE_CASE MAIL_TO   # the comparison job reads the same values
OUT=outputs/model-comparison/$USE_CASE-n$SIZE
BUCKET=${GCS_BUCKET:-gs://research-dpv-kw-outputs}   # the comparison is also uploaded here (dashboard, PC sync)
BUCKET_OUT=${BUCKET:+$BUCKET/$("${VLLM_ENV:-$HOME/.venvs/vllm}/bin/python" scripts/bucket_layout.py dest "$(basename "$OUT")" model-comparison)}  # experiments/<use case>-n<size>/_comparison

send_mail() {  # subject, body (file or text), attachments...: sendmail, else SMTP_* from .env, else SMTP on localhost
    python3 - "$MAIL_TO" "$@" <<'EOF'
import getpass, mimetypes, os, shutil, smtplib, socket, subprocess, sys
from email.message import EmailMessage
from pathlib import Path
to, subject, body, *files = sys.argv[1:]
env = dict(os.environ)
if Path(".env").exists():  # SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM (optional)
    for line in Path(".env").read_text(encoding="utf-8", errors="replace").splitlines():
        k, _, v = line.partition("=")
        if k.strip().startswith("SMTP_"):
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
msg = EmailMessage()
msg["To"], msg["Subject"] = to, subject
msg["From"] = env.get("SMTP_FROM") or env.get("SMTP_USER") or "{}@{}".format(getpass.getuser(), socket.getfqdn())
msg.set_content(Path(body).read_text(encoding="utf-8", errors="replace") if Path(body).is_file() else body)
for f in map(Path, files):
    if f.is_file():
        kind, _ = mimetypes.guess_type(f.name)
        main, sub = (kind or "application/octet-stream").split("/")
        msg.add_attachment(f.read_bytes(), maintype=main, subtype=sub, filename=f.name)
sendmail = shutil.which("sendmail") or next((p for p in ("/usr/sbin/sendmail", "/usr/lib/sendmail") if Path(p).exists()), None)
if sendmail:
    subprocess.run([sendmail, "-t", "-oi"], input=msg.as_bytes(), check=True)
elif env.get("SMTP_HOST"):
    port = int(env.get("SMTP_PORT", "587"))
    with (smtplib.SMTP_SSL if port == 465 else smtplib.SMTP)(env["SMTP_HOST"], port, timeout=60) as s:
        if port == 587:
            s.starttls()
        if env.get("SMTP_USER"):
            s.login(env["SMTP_USER"], env["SMTP_PASSWORD"])
        s.send_message(msg)
else:
    with smtplib.SMTP("localhost", timeout=60) as s:
        s.send_message(msg)
print("emailed {}: {}".format(to, subject))
EOF
}

if [ "${1:-}" = "--test-mail" ]; then
    send_mail "kw test from $(hostname -s)" "If this arrived, the model comparison will reach you the same way." 2>&1 | tail -1
    rc=${PIPESTATUS[0]}
    [ "$rc" -eq 0 ] || echo "could not send from $(hostname -s): no sendmail here, and the SMTP server (SMTP_HOST in .env, else localhost:25) refused"
    exit "$rc"
fi

if [ "${1:-}" = "--compare" ]; then   # inside the Slurm job
    export UV_CACHE_DIR=${UV_CACHE_DIR:-$HOME/.cache/uv-kw} UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/kw}
    sweeps=(); for t in $MODELS; do sweeps+=("$USE_CASE-$t-n$SIZE"); done
    log=$OUT.log; mkdir -p "$(dirname "$OUT")"
    {
        echo "n$SIZE sweeps, integration rows:"
        for s in "${sweeps[@]}"; do
            r=$(grep -h '"integration"' "outputs/sweep-$s/summary.csv" 2>/dev/null | cut -d, -f4 | tr -d '"')
            printf "  %-45s %s\n" "$s" "${r:-no summary}"
        done
        uv run --with-requirements requirements.txt python scripts/compare_models.py --sweeps "${sweeps[@]}" --size "$SIZE" --out "$OUT"
    } >"$log" 2>&1
    rc=$?
    if [ "$rc" -eq 0 ] && [ -f "$OUT/report.md" ]; then
        (cd "$(dirname "$OUT")" && rm -f "$(basename "$OUT").zip" && python3 -m zipfile -c "$(basename "$OUT").zip" "$(basename "$OUT")")
        { cat "$log"; echo; echo "Full report with figures: unzip the attachment and open report.html."; echo
          cat "$OUT/report.md"; } >"$OUT.mail.txt"
        [ -z "$BUCKET" ] || gcloud storage rsync -r "$OUT" "$BUCKET_OUT" >>"$log" 2>&1 \
            || echo "upload to $BUCKET failed" >>"$log"
        send_mail "n$SIZE model comparison ($USE_CASE)" "$OUT.mail.txt" "$OUT.zip" "$OUT/report.html" "$OUT/model_metrics.csv" \
            || echo "email failed; the report is in $OUT${BUCKET:+ and $BUCKET_OUT}"
    else
        send_mail "n$SIZE model comparison FAILED ($USE_CASE)" "$log" "$log" || cat "$log"
    fi
    exit "$rc"
fi

# ---- login node: submit the sweeps, then the comparison ----
command -v sbatch >/dev/null || { echo "run this on the cluster login node"; exit 1; }
command -v uv >/dev/null || { echo "uv not found on PATH or in ~/.local/bin, ~/.cargo/bin, ~/kw-hpc/bin: every job would fail at start"; exit 1; }
jobname() { echo "kw-$1-n$SIZE"; }
for t in $MODELS; do
    sweep=outputs/sweep-$USE_CASE-$t-n$SIZE
    if [ -n "$(squeue -h -u "$ME" -n "$(jobname "$t")")" ]; then echo "$t: already queued or running"; continue; fi
    if grep -q '"integration".*"completed"' "$sweep/summary.csv" 2>/dev/null; then
        echo "$t: n$SIZE integration already completed"; continue
    fi
    rm -rf "$sweep/report"   # else slurm-models.sh counts a failed sweep as done
    ONLY=$t LIMITS=$SIZE JOB_SUFFIX=-n$SIZE scripts/slurm-models.sh all
done
old=$(squeue -h -u "$ME" -n "kw-n$SIZE-compare" -o %i)
[ -z "$old" ] || { scancel $old; echo "replaced the queued comparison job $old"; }
ids=$(for t in $MODELS; do squeue -h -u "$ME" -n "$(jobname "$t")" -o %i; done | paste -sd:)
dep=${ids:+--dependency=afterany:$ids}
job=$(sbatch --parsable -J "kw-n$SIZE-compare" -p "${PARTITION:-normal}" -A "${ACCOUNT:-kdavis}" -c 4 --mem=16G -t 01:00:00 \
      $dep --mail-type=END,FAIL --mail-user="$MAIL_TO" -o "kw-n$SIZE-compare-%j.out" scripts/slurm-compare.sh --compare) || exit 1
echo "comparison: job $job, after ${ids:-nothing (all sweeps already ended)}; emails $MAIL_TO when done"
echo "check progress: scripts/slurm-status.sh"
