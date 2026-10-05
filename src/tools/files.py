"""Writes that stay safe when several runs share outputs/ and the cache (e.g. three domains in parallel)."""
import os
import time
from contextlib import contextmanager
from pathlib import Path


def atomic_write(path: Path, text: str):
    """Write to a temporary file beside path, then rename: a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8", errors="replace")
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows: the target is open in another process for a moment
            time.sleep(0.25 * (attempt + 1))
    tmp.unlink(missing_ok=True)
    raise PermissionError(f"could not replace {path}")


@contextmanager
def locked(path: Path, wait_s: float = 120, stale_s: float = 300):
    """Cross-process lock for a read-modify-write of path (a <name>.lock file beside it). A lock older than stale_s
    is left over from a killed process and is taken over."""
    lock = path.with_name(path.name + ".lock")
    t0 = time.monotonic()
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale_s:
                    lock.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() - t0 > wait_s:
                raise TimeoutError(f"{lock} held for over {wait_s:.0f}s")
            time.sleep(0.2)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)
