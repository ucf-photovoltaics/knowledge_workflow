"""Composable scientific extraction agent."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from kweave.contracts import Entity, ExtractionArtifact, Paper, Relation


EntityTool = Callable[[str], Iterable[Entity]]
RelationTool = Callable[[str, tuple[Entity, ...]], Iterable[Relation]]


class ExtractAgent:
    """Run configured extraction tools while isolating optional-tool failures."""

    def __init__(
        self,
        entity_tools: Mapping[str, EntityTool] | None = None,
        relation_tools: Mapping[str, RelationTool] | None = None,
    ) -> None:
        self.entity_tools = dict(entity_tools or {})
        self.relation_tools = dict(relation_tools or {})

    def extract(self, paper: Paper) -> ExtractionArtifact:
        text = (paper.full_text or paper.abstract).strip()
        if not text:
            return ExtractionArtifact(paper.key, paper.title, errors=("paper has no extractable text",))

        entities: list[Entity] = []
        relations: list[Relation] = []
        errors: list[str] = []
        for name, tool in self.entity_tools.items():
            try:
                entities.extend(tool(text))
            except Exception as exc:  # optional engines must not abort the collection
                errors.append(f"{name}: {exc}")
        frozen_entities = tuple(entities)
        for name, tool in self.relation_tools.items():
            try:
                relations.extend(tool(text, frozen_entities))
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        return ExtractionArtifact(
            paper_key=paper.key,
            title=paper.title,
            entities=tuple(entities),
            relations=tuple(relations),
            errors=tuple(errors),
        )
