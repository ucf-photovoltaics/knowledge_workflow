# -*- coding: utf-8 -*-
"""
Schema builder agent — Phase 2.

For each paper's full text and the normalized concept list, calls the LLM
to extract the paper-specific value and source sentence for every concept.

PydanticAI infers the tool schema from SchemaValueList — no manual JSON
tool dict or parse_tool_call required.
"""

import time

from pydantic_ai import Agent

from src.config import pydantic_model, RATE_LIMIT_DELAY, FULL_TEXT_MAX_CHARS
from src.models.schema import SchemaValue, SchemaValueList, SchemaRow

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

schema_agent = Agent(
    pydantic_model,
    result_type=SchemaValueList,
    system_prompt=(
        'You are a precise scientific data extractor. '
        'You will be given the full text of a scientific paper and a list of '
        'ontology concept labels. '
        'For EACH concept, find and return:\n'
        "  value  — the exact term, number, or very short phrase this paper uses "
        "for that concept (use the paper's own wording). "
        'If the concept is not addressed in this paper, use an empty string.\n'
        '  quote  — the single most informative sentence from the text that '
        'establishes or describes this concept. '
        'Prefer results sections, abstracts, or conclusion sentences. '
        'If not found, use an empty string.\n\n'
        'Be precise. Do not paraphrase. Do not invent values not in the text.'
    ),
    retries=2,
)

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def populate_schema_row(full_text: str, canonical_concepts: list[str]) -> dict[str, SchemaValue]:
    """
    For one paper, extract {value, quote} for every concept.
    Returns a mapping {canonical: SchemaValue}.
    """
    empty        = {c: SchemaValue(canonical=c) for c in canonical_concepts}
    text_excerpt = (full_text or '')[:FULL_TEXT_MAX_CHARS]
    if not text_excerpt:
        return empty

    concept_list = '\n'.join(f'- {c}' for c in canonical_concepts)

    result = schema_agent.run_sync(
        f'Paper text (may be truncated to {FULL_TEXT_MAX_CHARS:,} characters):\n\n'
        f'{text_excerpt}\n\n'
        f'---\n'
        f'For each concept below, return the paper-specific value and source quote:\n\n'
        f'{concept_list}'
    )

    out = empty.copy()
    for sv in result.data.values:
        canon = sv.canonical.strip().lower()
        if canon in out:
            out[canon] = SchemaValue(
                canonical=canon,
                value=sv.value.strip(),
                quote=sv.quote.strip(),
            )
    return out


def build_schema_rows(
    collection_dict:    dict,
    canonical_concepts: list[str],
    domain:             str,
) -> list[SchemaRow]:
    """
    Phase 2: build one SchemaRow per paper across the full collection.
    Each row contains a 'cells' dict mapping concept → "value | quote" string.
    """
    rows:  list[SchemaRow] = []
    papers = [p for p in collection_dict.values() if p.get('abstract') or p.get('full_text')]
    total  = len(papers)

    for i, paper in enumerate(papers, 1):
        print(f'  [{i}/{total}] Schema row: {paper["title"][:70]}')
        text        = paper.get('full_text') or paper.get('abstract', '')
        schema_data = populate_schema_row(text, canonical_concepts)

        cells = {
            concept: schema_data.get(concept, SchemaValue(canonical=concept)).formatted()
            for concept in canonical_concepts
        }
        rows.append(SchemaRow(domain=domain, doi=paper.get('doi', ''), cells=cells))

        if i < total:
            time.sleep(RATE_LIMIT_DELAY)

    return rows
