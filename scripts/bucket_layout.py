"""Where each outputs/ folder belongs in the results bucket: one folder per experiment (a use case at one corpus size).

    gs://<bucket>/experiments/<use case>-n<size>/   every sweep, domain run and integration of that experiment, side by
                                                   side (scripts/compare_models.py --outputs reads such a folder);
                                                   _comparison/ holds the comparison report
    gs://<bucket>/experiments/local-<sweep id>/    sweeps with a timestamp id (laptop runs)
    gs://<bucket>/experiments/<use case>-tests/    sweeps named <use case>-<timestamp>
    gs://<bucket>/review/, embeddings/             reviewer workbooks, embedding benchmarks
    gs://<bucket>/misc/                            anything else

    python scripts/bucket_layout.py dest NAME [PARENT]         # the bucket folder for one outputs/ folder ("" = skip)
    python scripts/bucket_layout.py map DIR                    # NAME<TAB>DEST for every folder in DIR (sync-outputs.ps1)
    python scripts/bucket_layout.py migrate gs://BUCKET        # plan: what would move out of the bucket's top level
    python scripts/bucket_layout.py migrate gs://BUCKET --apply   # move it (copy, then delete the old copy)

Standard library and Python 3.6 syntax only, so it runs on the cluster's system python and on Windows. Migration needs gcloud signed in.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEEP = {"experiments", "review", "embeddings", "misc", "private"}      # private holds runtime access config; never migrate it
LOCAL_ONLY = {"cache", "dashboard", "hpc-sync", "bucket", "development", "tmp", "private"}
STAMP = r"\d{8}-\d{6}"


def use_cases():
    path = ROOT / "scripts" / "use-cases.txt"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    names = [m.group(1) for m in (re.match(r"\s*([\w-]+)\s*:", line) for line in lines if not line.lstrip().startswith("#")) if m]
    return sorted(names, key=len, reverse=True)  # longest first, so pv-cost-chain-x never matches pv-cost


def sweep_of(name):
    """The sweep id in a sweep folder (sweep-<id>) or a run folder (<collection>-n<size>-<id>, integration-n<size>-<id>)."""
    if name.startswith("sweep-"):
        return name[6:]
    m = re.match(r"^.+?-n\d+-(.+)$", name)
    return m.group(1) if m else None


def experiment(sweep):
    if re.fullmatch(STAMP, sweep):
        return f"local-{sweep}"
    for uc in use_cases():
        if sweep.startswith(uc + "-"):
            m = re.search(r"-n(\d+(?:-\d+)*)$", sweep)
            if m:
                return f"{uc}-n{m.group(1)}"
            return f"{uc}-tests"
    return "misc"


def dest(name, parent=""):
    """The bucket path (relative to the bucket) of a top-level outputs/ folder NAME; "" = not uploaded."""
    if parent == "model-comparison":
        return f"experiments/{name}/_comparison" if not name.startswith("_") else ""
    if name in LOCAL_ONLY or name in ("model-comparison", "experiments", "misc"):
        return ""
    if name == "review":
        return "review"
    if name == "eval_embeddings":
        return "embeddings"
    sweep = sweep_of(name)
    return f"experiments/{experiment(sweep)}/{name}" if sweep else f"misc/{name}"


def gcloud(*args, check=True):
    exe = shutil.which("gcloud") or shutil.which("gcloud.cmd") or "gcloud"
    r = subprocess.run([exe, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if check and r.returncode:
        sys.exit(f"gcloud {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout


def migrate(bucket, apply):
    bucket = bucket.rstrip("/")
    moves = []
    for line in gcloud("storage", "ls", bucket + "/").splitlines():
        name = line.rstrip("/").rsplit("/", 1)[-1]
        if not line.endswith("/") or not name or name in KEEP:
            continue
        if name == "model-comparison":
            for sub in gcloud("storage", "ls", f"{bucket}/model-comparison/").splitlines():
                child = sub.rstrip("/").rsplit("/", 1)[-1]
                d = dest(child, "model-comparison")
                if sub.endswith("/") and d:
                    moves.append((f"model-comparison/{child}", d))
            continue
        d = dest(name)
        if d:
            moves.append((name, d))
    groups = {}
    for src, d in moves:
        groups.setdefault(d.split("/")[1] if d.startswith("experiments/") else d.split("/")[0], []).append(src)
    for g, srcs in sorted(groups.items()):
        print(f"{g}: {len(srcs)} folder(s)  e.g. {srcs[0]}")
    print(f"{len(moves)} folder(s) to move{'' if apply else ' (plan only; add --apply to move them)'}")
    if not apply:
        return
    for i, (src, d) in enumerate(moves, 1):
        print(f"[{i}/{len(moves)}] {src} -> {d}", flush=True)
        gcloud("storage", "rsync", "-r", f"{bucket}/{src}", f"{bucket}/{d}")   # copy (safe to repeat)
        gcloud("storage", "rm", "-r", f"{bucket}/{src}")                     # then remove the old copy
    print("done; the bucket's top level now holds only experiments/, review/, embeddings/ and misc/")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dest")
    d.add_argument("name")
    d.add_argument("parent", nargs="?", default="", help='"model-comparison" for a folder inside it')
    sub.add_parser("map").add_argument("dir")
    m = sub.add_parser("migrate")
    m.add_argument("bucket")
    m.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.cmd == "dest":
        print(dest(a.name, a.parent))
    elif a.cmd == "map":
        root = Path(a.dir)
        for p in sorted(root.iterdir()):
            if not p.is_dir():
                continue
            if p.name == "model-comparison":
                for c in sorted(p.iterdir()):
                    d = dest(c.name, "model-comparison")
                    if c.is_dir() and d:
                        print(f"model-comparison/{c.name}\t{d}")
            elif dest(p.name):
                print(f"{p.name}\t{dest(p.name)}")
    else:
        migrate(a.bucket, a.apply)


if __name__ == "__main__":
    main()
