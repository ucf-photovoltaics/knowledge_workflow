# -*- coding: utf-8 -*-
"""
Pydantic models for Phase 1 concept extraction.
"""

from pydantic import BaseModel, Field


class ExtractedConcept(BaseModel):
    """One concept extracted from a single paper abstract."""
    canonical:  str
    paper_term: str
    relevance:  float = Field(ge=0.0, le=1.0)


class ConceptRow(BaseModel):
    """A single row in the flat concept-extraction table."""
    paper:      str
    doi:        str = ''
    canonical:  str
    paper_term: str
    relevance:  float


class ConceptTable(BaseModel):
    """The full flat table produced by Phase 1 across all papers."""
    rows: list[ConceptRow]

    @property
    def all_canonicals(self) -> list[str]:
        """All canonical labels (with duplicates) — input for normalization."""
        return [r.canonical for r in self.rows]


# ---------------------------------------------------------------------------
# PydanticAI result-type wrappers
# These are the structured-output contracts that each agent returns.
# PydanticAI auto-generates the tool/function schema from these models,
# replacing all hand-written JSON tool dicts.
# ---------------------------------------------------------------------------

class ConceptList(BaseModel):
    """result_type for the extractor agent."""
    concepts: list[ExtractedConcept] = Field(
        description='Concepts extracted from the abstract, sorted by relevance descending.'
    )


class NormalizedConceptList(BaseModel):
    """result_type for the normalizer agent."""
    concepts: list[str] = Field(
        description=(
            'Clean, deduplicated ontology-ready labels (lowercase, 1-4 words). '
            'Aim for 30–80 items covering the corpus.'
        )
    )
