"""Serializable contracts shared by Kweave agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Paper:
    key: str
    title: str
    doi: str = ""
    abstract: str = ""
    full_text: str = ""
    date: str = ""
    authors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Entity:
    text: str
    label: str
    canonical_id: str | None = None
    score: float | None = None
    start: int | None = None
    end: int | None = None
    source_tool: str = ""


@dataclass(frozen=True, slots=True)
class Relation:
    subject: str
    predicate: str
    object: str
    evidence: str = ""
    score: float | None = None
    source_tool: str = ""


@dataclass(frozen=True, slots=True)
class ExtractionArtifact:
    paper_key: str
    title: str
    entities: tuple[Entity, ...] = ()
    relations: tuple[Relation, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NormalizedGraph:
    entities: tuple[Entity, ...]
    relations: tuple[Relation, ...]
    source_papers: tuple[str, ...]
    validation_errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
