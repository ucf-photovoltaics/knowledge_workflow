"""Embedding vectors (EMBED model) for the texts a stage searches the ontology store with, kept in memory for the run."""
import numpy as np

from src.config import EMBED
from src.tools import llm

_vectors: dict[str, np.ndarray] = {}


def enabled() -> bool:
    return bool(EMBED["model"])


def embed(texts: list[str], ledger=None, agent: str = "enrichment") -> np.ndarray:
    todo = [t for t in dict.fromkeys(texts) if t not in _vectors]
    if todo:
        vecs, usage = llm.embed(todo)
        if ledger:
            ledger.log(agent, "embeddings", EMBED["model"], usage)
        for t, v in zip(todo, vecs):
            v = np.asarray(v, dtype=float)
            _vectors[t] = v / (np.linalg.norm(v) + 1e-12)
    return np.stack([_vectors[t] for t in texts]) if texts else np.zeros((0, 1))


def similarity(a: str, b: str) -> float:
    return float(_vectors[a] @ _vectors[b])
