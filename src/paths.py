"""Central filesystem path resolution for Kweave."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """Return the project-local input data directory."""
    return PROJECT_ROOT / "data"


def runs_dir() -> Path:
    """Return the project-local generated-runs directory."""
    return PROJECT_ROOT / "runs"


def cache_file() -> Path:
    """Return the project-local metadata cache path."""
    return PROJECT_ROOT / ".mdsonto_cache.json"

