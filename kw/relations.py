# -*- coding: utf-8 -*-
"""
Relation-vocabulary normalization (T3.2).

REBEL emits free-text predicates ("is made of", "located in", ...). To make the
relational layer queryable we map them onto a small controlled set of mds: object
properties. Unmapped predicates are left as-is (predicate_norm stays '') and the
raw predicate is always preserved for provenance.

Pure-Python, dependency-free: an exact-phrase lookup plus a keyword fallback.
"""
from __future__ import annotations

from kw.models import Triple

# Controlled mds: object-property vocabulary. Extend as your domains require.
RELATION_VOCAB: dict[str, str] = {
    'mds:partOf':           ['part of', 'located in', 'within', 'belongs to', 'component of'],
    'mds:hasPart':          ['contains', 'has part', 'includes', 'comprises'],
    'mds:madeOf':           ['made of', 'composed of', 'consists of', 'made from', 'fabricated from'],
    'mds:hasConstituent':   ['contains element', 'doped with', 'alloyed with'],
    'mds:depositedOn':      ['deposited on', 'coated on', 'grown on', 'applied to', 'printed on'],
    'mds:usedIn':           ['used in', 'used for', 'applied in', 'employed in', 'utilized in'],
    'mds:causes':           ['causes', 'leads to', 'results in', 'induces', 'produces'],
    'mds:characterizedBy':  ['measured by', 'characterized by', 'analyzed by', 'imaged by',
                             'observed by', 'evaluated by'],
    'mds:hasProperty':      ['has property', 'exhibits', 'shows', 'has value'],
    'mds:subClassOf':       ['is a', 'type of', 'kind of', 'subclass of', 'instance of'],
    'mds:manufacturedBy':   ['manufactured by', 'produced by', 'synthesized by', 'prepared by'],
}

# Flatten to a phrase -> curie index (longest phrases first for greedy matching).
_PHRASE_INDEX: list[tuple[str, str]] = sorted(
    ((phrase, curie) for curie, phrases in RELATION_VOCAB.items() for phrase in phrases),
    key=lambda kv: len(kv[0]), reverse=True,
)


def normalize_predicate(predicate: str) -> str:
    """Return the mds: curie for a free-text predicate, or '' if unmapped."""
    p = (predicate or '').strip().lower()
    if not p:
        return ''
    for phrase, curie in _PHRASE_INDEX:          # exact, then substring
        if p == phrase:
            return curie
    for phrase, curie in _PHRASE_INDEX:
        if phrase in p:
            return curie
    return ''


def normalize_triples(triples: list[Triple]) -> list[Triple]:
    """Set predicate_norm on each triple in place; returns the same list."""
    for t in triples:
        if not t.predicate_norm:
            t.predicate_norm = normalize_predicate(t.predicate)
    return triples


def coverage(triples: list[Triple]) -> float:
    """Fraction of triples whose predicate mapped to the controlled vocabulary."""
    if not triples:
        return 0.0
    mapped = sum(1 for t in triples if t.predicate_norm)
    return round(mapped / len(triples), 3)
