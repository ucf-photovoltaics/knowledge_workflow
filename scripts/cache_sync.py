"""Give a Slurm job private copies of the shared SQLite caches, and merge what it added back afterwards.

SQLite's file locks and WAL shared memory do not work between the nodes of a network filesystem such as Lustre, so
jobs on several nodes writing outputs/cache/rows.sqlite3 or embeddings.sqlite3 at once corrupt them ("database disk
image is malformed"). Each job works on node-local copies instead; at the end it merges its new entries into the
shared files one job at a time (an atomic mkdir lock) and swaps the result in with a rename.

  python scripts/cache_sync.py pull SHARED_DIR LOCAL_DIR    # at job start
  python scripts/cache_sync.py push SHARED_DIR LOCAL_DIR    # at job end

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

TABLES = {"rows.sqlite3": "rows", "embeddings.sqlite3": "embeddings"}


def _open_ro(path: Path) -> sqlite3.Connection:
    # immutable: no locks and no WAL lookup, which a network filesystem cannot provide anyway
    return sqlite3.connect(f"file:{path}?immutable=1", uri=True)


def healthy(path: Path) -> bool:
    try:
        with _open_ro(path) as con:
            return con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except sqlite3.DatabaseError:
        return False


def _copy(src: Path, dst: Path) -> bool:
    """Copy src to local dst and check it there: one sequential read of the network filesystem instead of the
    random reads of an integrity check on it, which take minutes for a large file. False (and no dst) if damaged."""
    shutil.copyfile(src, dst)
    if healthy(dst):
        with sqlite3.connect(dst) as d:
            d.execute("PRAGMA journal_mode=DELETE")
        return True
    dst.unlink()
    return False


def _count(path: Path, table: str) -> int:
    with _open_ro(path) as con:
        return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def pull(shared: Path, local: Path):
    local.mkdir(parents=True, exist_ok=True)
    for name, table in TABLES.items():
        src = shared / name
        if not src.exists():
            print(f"{name}: none yet; this job starts an empty cache", flush=True)
        elif _copy(src, local / name):
            print(f"{name}: {_count(local / name, table):,} entries copied to {local}", flush=True)
        else:
            print(f"{name}: shared copy is damaged; this job starts an empty cache (the merge at the end replaces it)",
                  flush=True)


def _lock(path: Path, wait_s: int = 1800) -> bool:
    deadline = time.time() + wait_s
    while True:
        try:
            path.mkdir()
            return True
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > 3600:  # left by a job killed mid-merge
                    path.rmdir()
                    continue
            except FileNotFoundError:
                continue
            if time.time() > deadline:
                return False
            time.sleep(10)


def push(shared: Path, local: Path):
    lock = shared / ".cache-merge.lock"
    if not _lock(lock):
        print(f"cache merge skipped: {lock} held for 30 min")
        return
    try:
        for name, table in TABLES.items():
            mine, target = local / name, shared / name
            if not mine.exists():
                continue
            merged = local / f"{name}.merged"
            if not (target.exists() and _copy(target, merged)):
                if target.exists():
                    damaged = target.with_name(f"{name}.damaged-{time.strftime('%Y%m%d-%H%M%S')}")
                    target.rename(damaged)
                    print(f"{name}: shared copy was damaged; kept as {damaged.name}", flush=True)
                shutil.copyfile(mine, merged)
            with sqlite3.connect(merged) as con:
                con.execute("ATTACH DATABASE ? AS job", (str(mine),))
                added = con.execute(f"INSERT OR IGNORE INTO main.{table} SELECT * FROM job.{table}").rowcount
                con.commit()
                con.execute("DETACH DATABASE job")
            if not healthy(merged):
                print(f"{name}: merged copy failed its check; shared copy left as it was", flush=True)
                continue
            tmp = shared / f"{name}.incoming-{os.getpid()}"
            shutil.copyfile(merged, tmp)
            for side in ("-wal", "-shm", "-journal"):  # left by older jobs that wrote the shared file directly
                Path(f"{target}{side}").unlink(missing_ok=True)
            os.replace(tmp, target)
            merged.unlink()
            print(f"{name}: {added:,} new entries merged; {_count(target, table):,} in {target}", flush=True)
    finally:
        lock.rmdir()


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("pull", "push"):
        sys.exit(__doc__)
    {"pull": pull, "push": push}[sys.argv[1]](Path(sys.argv[2]), Path(sys.argv[3]))
