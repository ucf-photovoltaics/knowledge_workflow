"""Normalized retrieval vectors in memory; llm.embed also persists them across runs by endpoint and model.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import numpy as np

from src.config import EMBED
from src.tools import llm

_vectors: dict[str, np.ndarray] = {}
_identity = None


def enabled() -> bool:
    return bool(EMBED["model"])


def embed(texts: list[str], ledger=None, agent: str = "enrichment") -> np.ndarray:
    global _identity
    identity = (EMBED["base_url"], EMBED["model"], EMBED.get("cache_version", 1))
    if identity != _identity:
        _vectors.clear()
        _identity = identity
    todo = [t for t in dict.fromkeys(texts) if t not in _vectors]
    if todo:
        vecs, usage = llm.embed(todo)
        if ledger:
            ledger.log(agent, "embeddings", EMBED["model"], usage)
        for t, v in zip(todo, vecs):
            v = np.asarray(v, dtype=float)
            _vectors[t] = v / (np.linalg.norm(v) + 1e-12)
    return np.stack([_vectors[t] for t in texts]) if texts else np.zeros((0, 1))


def query(texts: list[str], ledger=None, agent: str = "enrichment") -> np.ndarray:
    """Vectors for texts searched against the ontology store (EMBED query prefix)."""
    return embed([EMBED.get("query_prefix", "") + t for t in texts], ledger, agent)


def document(texts: list[str], ledger=None, agent: str = "enrichment") -> np.ndarray:
    """Vectors for texts scored as store terms (EMBED document prefix, as the store's own vectors)."""
    return embed([EMBED.get("document_prefix", "") + t for t in texts], ledger, agent)


def similarity(a: str, b: str) -> float:
    return float(_vectors[a] @ _vectors[b])
