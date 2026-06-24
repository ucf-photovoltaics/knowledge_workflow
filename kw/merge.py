# -*- coding: utf-8 -*-
"""
Entity resolution / merge (T3.1).

REBEL triples and the LLM concept list are produced independently. This step
links each triple endpoint (subject/object) to a concept node when they refer to
the same thing, so the relational layer connects to the concept graph instead of
floating beside it.

Matching is dependency-free by default: exact/substring then fuzzy ratio
(difflib). If `sentence-transformers` is installed, a semantic pass is used for
the borderline cases. Resolved IRIs are written to Triple.subject_id/object_id;
nothing is overwritten that was already set.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from kw.models import Triple
from kw.config import MDS_NS, MERGE_SIM_THRESHOLD

_st_model = None
_st_tried = False


def _slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')[:80]


def concept_iri(concept: str, ns: str = MDS_NS) -> str:
    return f'{ns}concept/{_slug(concept)}'


def _fuzzy(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _try_load_st():
    """Best-effort load of a sentence-transformer; returns None if unavailable."""
    global _st_model, _st_tried
    if _st_tried:
        return _st_model
    _st_tried = True
    try:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception:
        _st_model = None
    return _st_model


def _best_match(text: str, concepts: list[str], threshold: float) -> tuple[str | None, float]:
    """Return (best concept, score) if score >= threshold, else (None, score)."""
    t = (text or '').strip().lower()
    if not t or not concepts:
        return None, 0.0

    # 1) exact / substring
    for c in concepts:
        cl = c.lower()
        if t == cl or cl in t or t in cl:
            return c, 1.0

    # 2) fuzzy ratio
    best, best_score = None, 0.0
    for c in concepts:
        s = _fuzzy(t, c.lower())
        if s > best_score:
            best, best_score = c, s
    if best_score >= threshold:
        return best, round(best_score, 3)

    # 3) optional semantic pass for borderline cases
    model = _try_load_st()
    if model is not None:
        try:
            import numpy as np
            embs = model.encode([t] + [c.lower() for c in concepts], normalize_embeddings=True)
            sims = embs[0] @ embs[1:].T
            j = int(np.argmax(sims))
            if float(sims[j]) >= threshold:
                return concepts[j], round(float(sims[j]), 3)
        except Exception:
            pass

    return None, round(best_score, 3)


def resolve(triples: list[Triple], concepts: list[str],
            ns: str = MDS_NS, threshold: float | None = None) -> list[Triple]:
    """Set subject_id/object_id on each triple where an endpoint matches a concept."""
    th = MERGE_SIM_THRESHOLD if threshold is None else threshold
    for t in triples:
        if not t.subject_id:
            m, _ = _best_match(t.subject, concepts, th)
            if m:
                t.subject_id = concept_iri(m, ns)
        if not t.object_id:
            m, _ = _best_match(t.object, concepts, th)
            if m:
                t.object_id = concept_iri(m, ns)
    return triples


def stats(triples: list[Triple]) -> dict:
    """Resolution coverage: fraction of endpoints linked to a concept node."""
    if not triples:
        return {'triples': 0, 'endpoints_resolved': 0, 'resolution_rate': 0.0}
    endpoints = 2 * len(triples)
    resolved  = sum(bool(t.subject_id) + bool(t.object_id) for t in triples)
    return {
        'triples': len(triples),
        'endpoints_resolved': resolved,
        'resolution_rate': round(resolved / endpoints, 3),
    }
