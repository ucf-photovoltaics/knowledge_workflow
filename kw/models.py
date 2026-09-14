# -*- coding: utf-8 -*-
"""
All Pydantic data contracts in one place (consolidates the old src/models/*).

These are the typed objects every pipeline stage passes around. CSV / TTL /
JSON-LD are serialization at the edges only.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# JSON-leak repair
# --------------------------------------------------------------------------- #
# Structured-output parsing over an OpenAI-compatible endpoint can sweep raw
# tool-call JSON into a string field when the source text contains unescaped
# quotes, e.g.  paper_term == '50 MW", "power grid ...", "relevance": 0.7}, {'.
# Detect that JSON-structure signature and truncate at the first stray closing
# quote, recovering the leading legitimate text. Conservative: only fires when a
# JSON signal is present, so clean values pass through untouched.
_JSON_LEAK_SIGNAL = re.compile(
    r'\}\s*,\s*\{|"(?:relevance|canonical|paper_term|value|quote)"\s*:|"\s*\]\s*\)')
_JSON_LEAK_CUT = re.compile(r'["\u201c\u201d]\s*[,:}\]]')


def strip_json_leak(value: str) -> str:
    s = value or ""
    if not _JSON_LEAK_SIGNAL.search(s):
        return value
    m = _JSON_LEAK_CUT.search(s)
    if m:
        s = s[:m.start()]
    return s.strip().strip('"\u201c\u201d').strip().rstrip(",").strip().strip('"\u201c\u201d').strip()


# --------------------------------------------------------------------------- #
# Phase 1 — concepts
# --------------------------------------------------------------------------- #
class ExtractedConcept(BaseModel):
    canonical:  str
    paper_term: str
    relevance:  float = Field(ge=0.0, le=1.0)

    @field_validator('canonical', 'paper_term')
    @classmethod
    def _clean(cls, v: str) -> str:
        return strip_json_leak(v)


class ConceptRow(BaseModel):
    paper:      str
    doi:        str = ''
    canonical:  str
    paper_term: str
    relevance:  float


class ConceptTable(BaseModel):
    rows: list[ConceptRow]

    @property
    def all_canonicals(self) -> list[str]:
        return [r.canonical for r in self.rows]


class ConceptList(BaseModel):
    """result_type for the extractor agent."""
    concepts: list[ExtractedConcept] = Field(
        description='Concepts extracted from the abstract, sorted by relevance descending.'
    )


class NormalizedConceptList(BaseModel):
    """result_type for the normalizer agent."""
    concepts: list[str] = Field(
        description=('Clean, deduplicated ontology-ready labels (lowercase, 1-4 words). '
                     'Aim for 30-80 items covering the corpus.')
    )


class DomainContext(BaseModel):
    """result_type for the domain-inference agent (unsupervised corpus framing)."""
    domain: str = Field(
        description='The specific research domain of this collection, in a short phrase.')
    categories: list[str] = Field(
        default_factory=list,
        description=('5-8 general, reusable concept categories appropriate to this domain '
                     '(e.g. a material type, a method, a measured property) - not specific values.'))


class UpperClassAssignment(BaseModel):
    """One data-derived term fitted to an MDS-Onto upper class."""
    term: str = Field(description='The candidate term, copied verbatim from the input.')
    mds_class: str = Field(
        description='The chosen MDS upper-class id (one of the provided class ids), verbatim.')


class UpperClassAssignmentList(BaseModel):
    """result_type for the upper-class classifier agent."""
    assignments: list[UpperClassAssignment] = Field(
        description='One assignment per input term.')


# --------------------------------------------------------------------------- #
# Phase 2 — schema population
# --------------------------------------------------------------------------- #
class SchemaValue(BaseModel):
    canonical: str
    value:     str = ''
    quote:     str = ''

    @field_validator('value', 'quote')
    @classmethod
    def _clean(cls, v: str) -> str:
        return strip_json_leak(v)

    def formatted(self) -> str:
        if self.value and self.quote:
            return f'{self.value} | {self.quote}'
        return self.value or self.quote


class SchemaRow(BaseModel):
    domain: str
    doi:    str = ''
    cells:  dict[str, str] = {}


class SchemaValueList(BaseModel):
    """result_type for the schema_builder agent."""
    values: list[SchemaValue] = Field(
        description='Paper-specific value and source quote for each canonical concept.'
    )


# --------------------------------------------------------------------------- #
# Grounding — MDS tags
# --------------------------------------------------------------------------- #
class TaggedConceptOutput(BaseModel):
    concept:                str       = Field(description='Concept label, exactly as provided.')
    mds_study_stage:        list[str] = Field(description='One or more MDS-Onto study stages.')
    mds_supply_chain_level: list[str] = Field(description='One or more supply chain levels.')


class TaggedConceptBatch(BaseModel):
    """result_type for the tagger agent."""
    tagged_concepts: list[TaggedConceptOutput] = Field(
        description='Each concept with its MDS-Onto study stage and supply chain level tags.'
    )


# --------------------------------------------------------------------------- #
# Mining — REBEL triples + provenance
# --------------------------------------------------------------------------- #
class Provenance(BaseModel):
    """Attached to every extracted assertion — supports explainability/reproducibility."""
    source_paper: str = ''
    text_span:    str = ''
    tool:         str = ''
    model:        str = ''
    seed:         int | None = None
    confidence:   float = 1.0


class Triple(BaseModel):
    """A flat S-P-O fact extracted from text (e.g. by REBEL)."""
    subject:   str
    predicate: str
    object:    str
    predicate_norm: str = ''   # normalized mds: relation (T3.2), '' if unmapped
    subject_id:     str = ''   # resolved concept/entity id (T3.1 entity resolution)
    object_id:      str = ''
    provenance: Provenance = Provenance()
