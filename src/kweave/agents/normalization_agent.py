"""Deterministic normalization baseline with optional grounding hooks."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import re

from kweave.contracts import Entity, ExtractionArtifact, NormalizedGraph, Relation


Grounder = Callable[[str], tuple[str | None, str | None]]
Validator = Callable[[tuple[Entity, ...], tuple[Relation, ...]], Iterable[str]]
PredicateCanonicalizer = Callable[[str], str]
Persister = Callable[[NormalizedGraph], None]


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


class NormalizationAgent:
    def __init__(
        self,
        grounder: Grounder | None = None,
        validator: Validator | None = None,
        predicate_canonicalizer: PredicateCanonicalizer | None = None,
        persister: Persister | None = None,
    ) -> None:
        self.grounder = grounder
        self.validator = validator
        self.predicate_canonicalizer = predicate_canonicalizer
        self.persister = persister

    def normalize(self, artifacts: Iterable[ExtractionArtifact]) -> NormalizedGraph:
        artifact_list = tuple(artifacts)
        entities_by_name: dict[str, Entity] = {}
        for artifact in artifact_list:
            for entity in artifact.entities:
                key = _clean(entity.text)
                if not key:
                    continue
                canonical_id = entity.canonical_id
                label = _clean(entity.label) or "entity"
                if self.grounder is not None and canonical_id is None:
                    grounded_id, grounded_label = self.grounder(entity.text)
                    canonical_id = grounded_id
                    label = grounded_label or label
                candidate = Entity(
                    text=key,
                    label=label,
                    canonical_id=canonical_id,
                    score=entity.score,
                    source_tool=entity.source_tool,
                )
                current = entities_by_name.get(key)
                if current is None or (candidate.score or 0) > (current.score or 0):
                    entities_by_name[key] = candidate

        relations_by_key: dict[tuple[str, str, str], Relation] = {}
        for artifact in artifact_list:
            for relation in artifact.relations:
                predicate = _clean(relation.predicate)
                if self.predicate_canonicalizer is not None:
                    predicate = _clean(self.predicate_canonicalizer(predicate))
                key = (_clean(relation.subject), predicate, _clean(relation.object))
                if all(key):
                    relations_by_key.setdefault(
                        key,
                        Relation(*key, evidence=relation.evidence, score=relation.score, source_tool=relation.source_tool),
                    )
        entities = tuple(entities_by_name.values())
        relations = tuple(relations_by_key.values())
        errors = tuple(self.validator(entities, relations)) if self.validator else ()
        graph = NormalizedGraph(
            entities=entities,
            relations=relations,
            source_papers=tuple(artifact.paper_key for artifact in artifact_list),
            validation_errors=errors,
        )
        if self.persister is not None:
            self.persister(graph)
        return graph
