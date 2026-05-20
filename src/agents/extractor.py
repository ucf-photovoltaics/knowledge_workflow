# -*- coding: utf-8 -*-
"""
Extractor agent — Phase 1.

Calls the LLM to pull domain concepts out of each paper abstract.
PydanticAI auto-generates the tool schema from ConceptList and handles
response parsing — no manual JSON tool dicts or parse_tool_call needed.
"""

import time

from pydantic_ai import Agent

from src.config import pydantic_model, RATE_LIMIT_DELAY, TOP_N_PER_PAPER
from src.models.concept import ConceptList, ConceptRow, ConceptTable

# ---------------------------------------------------------------------------
# Agent — defined once at module level (mirrors the noir engine pattern)
# ---------------------------------------------------------------------------

extractor_agent = Agent(
    pydantic_model,
    result_type=ConceptList,
    system_prompt=(
        'You are a scientific literature analyst and ontologist specialising in '
        'materials science and solar cell research. '
        'Given a paper abstract, extract domain-specific concepts in TWO forms:\n'
        '1. canonical — a general ontology-ready label (lowercase, 1-4 words) that '
        'could serve as a reusable column header across many papers in the field. '
        'Good examples: "absorber material", "device efficiency", "dopant species", '
        '"carrier lifetime", "passivation method", "open circuit voltage". '
        'Bad examples: "CdSeTe" (too specific), "22.1%" (a value, not a concept), '
        '"cell" (too vague).\n'
        '2. paper_term — the specific term, compound, percentage, or phrase this '
        'particular paper uses for that concept.\n'
        'Focus on technical properties, materials, methods, and performance metrics. '
        "Score each 0.0–1.0 by centrality to the paper's contribution."
    ),
    retries=2,
)

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def extract_concepts_from_abstract(abstract: str, top_n: int = TOP_N_PER_PAPER) -> list:
    """
    Extract up to *top_n* concepts from a single abstract.
    Returns a list of ExtractedConcept sorted by relevance descending.
    """
    result = extractor_agent.run_sync(
        f'Extract the top {top_n} concepts from this abstract. '
        f'For each, provide a canonical ontology label AND the paper-specific term.\n\n'
        f'Abstract:\n{abstract}'
    )
    concepts = result.data.concepts
    return sorted(concepts, key=lambda c: c.relevance, reverse=True)[:top_n]


def build_concept_table(collection_dict: dict, top_n: int = TOP_N_PER_PAPER) -> ConceptTable:
    """
    Phase 1: run per-paper concept extraction across the whole collection.

    Returns a ConceptTable whose .all_canonicals property provides the raw
    canonical list (with duplicates) needed by the normalizer agent.
    """
    rows: list[ConceptRow] = []
    papers = [p for p in collection_dict.values() if p.get('abstract')]
    total  = len(papers)

    for i, paper in enumerate(papers, 1):
        print(f'  [{i}/{total}] Extracting: {paper["title"][:70]}')
        concepts = extract_concepts_from_abstract(paper['abstract'], top_n=top_n)
        for c in concepts:
            rows.append(ConceptRow(
                paper=paper['title'],
                doi=paper.get('doi', ''),
                canonical=c.canonical.strip().lower(),
                paper_term=c.paper_term,
                relevance=round(c.relevance, 4),
            ))
        if i < total:
            time.sleep(RATE_LIMIT_DELAY)

    return ConceptTable(rows=rows)
