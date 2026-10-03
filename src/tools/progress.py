"""Console progress: every line is 'HH:MM:SS [stage] message'."""
import time

_stage = ["setup"]


def set_stage(name: str):
    _stage[0] = name


def log(message: str, end: str = "\n"):
    print(f"{time.strftime('%H:%M:%S')} [{_stage[0]}] {message}", end=end, flush=True)


def finish(message: str):
    """Complete a line started with log(..., end='')."""
    print(f" {message}", flush=True)
