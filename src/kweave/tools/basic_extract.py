"""Dependency-free extraction tools used as a reliable baseline."""

from __future__ import annotations

import re

from kweave.contracts import Entity, Relation


_TERM = re.compile(r"\b[A-Z][A-Za-z0-9+-]*(?:\s+[A-Z][A-Za-z0-9+-]*){0,2}\b")
_RELATION = re.compile(
    r"\b(?P<subject>[A-Z][A-Za-z0-9+-]*)\s+"
    r"(?P<predicate>improves|reduces|increases|degrades|contains|uses)\s+"
    r"(?P<object>[A-Za-z][A-Za-z0-9+-]*)\b",
    re.IGNORECASE,
)


def extract_entities(text: str) -> list[Entity]:
    if not text.strip():
        return []
    return [
        Entity(match.group(), "candidate", start=match.start(), end=match.end(), source_tool="baseline")
        for match in _TERM.finditer(text)
    ]


def extract_relations(text: str, entities: tuple[Entity, ...]) -> list[Relation]:
    del entities
    return [
        Relation(
            match.group("subject"),
            match.group("predicate"),
            match.group("object"),
            evidence=match.group(),
            source_tool="baseline",
        )
        for match in _RELATION.finditer(text)
    ]
