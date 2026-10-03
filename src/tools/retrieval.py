"""Embedding similarity (EMBED model) for re-ranking mapping candidates and finding the nearest BFO/CCO classes.

Vectors are kept in memory for the run; the upper-ontology label vectors are built once per run.
"""
import numpy as np

from src.config import EMBED
from src.tools import llm, upper

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


def nearest_upper(texts: list[str], k: int, ledger=None) -> list[list[tuple[str, float]]]:
    """For each text, the k most similar BFO/CCO classes as (IRI, cosine)."""
    classes = upper.terms()["classes"]
    iris = list(classes)
    keys = [f"{classes[i]['label']}: {classes[i]['definition'][:200]}" for i in iris]
    U = embed(keys, ledger)
    Q = embed(texts, ledger)
    sims = Q @ U.T
    return [[(iris[j], float(row[j])) for j in np.argsort(-row)[:k]] for row in sims]
