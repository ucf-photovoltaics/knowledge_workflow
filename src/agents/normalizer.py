# -*- coding: utf-8 -*-
"""
Normalizer agent.

Receives the raw list of all canonical labels from the extractor
(with duplicates) and returns a clean, deduplicated list of
30–80 ontology-ready concept labels.

PydanticAI infers the tool schema from NormalizedConceptList — no
manual JSON tool dict required.
"""

from pydantic_ai import Agent

from src.config import pydantic_model
from src.models.concept import NormalizedConceptList

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

normalizer_agent = Agent(
    pydantic_model,
    result_type=NormalizedConceptList,
    system_prompt=(
        'You are a knowledge-graph ontologist. '
        'You will receive a list of candidate concept labels extracted by AI from '
        'multiple scientific papers in the solar cell materials domain. '
        'Your task: return a clean, deduplicated, normalized set of ontology-ready '
        'labels suitable as column headers in a knowledge-graph schema.\n\n'
        'Rules:\n'
        '- Merge near-synonyms into one canonical form '
        '(e.g. "open circuit voltage", "open-circuit voltage voc", "voc" → '
        '"open circuit voltage").\n'
        '- Keep labels lowercase, 1-4 words, general and reusable.\n'
        '- Remove labels that are too vague ("cell", "material"), too specific '
        '("CdSeTe", "22%"), or duplicates.\n'
        '- Aim for 30–80 high-quality, distinct concepts covering the corpus.\n'
        '- Order them roughly by domain importance (most central properties first).'
    ),
    retries=2,
)

# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def normalize_concept_list(all_canonicals: list[str]) -> list[str]:
    """
    Deduplicate and normalize a raw list of canonical labels.

    Input:  all_canonicals — list with duplicates from the extractor agent.
    Output: clean list of 30–80 ontology-ready labels.
    """
    unique = sorted(set(c for c in all_canonicals if c))
    if not unique:
        return []

    result = normalizer_agent.run_sync(
        f'Here are {len(unique)} candidate concept labels from a corpus of '
        f'domain-specific peer-reviewed research papers. '
        f'Normalize and deduplicate into a clean ontology-ready list (30–80 concepts).\n\n'
        + '\n'.join(f'- {c}' for c in unique)
    )
    concepts = [c.strip().lower() for c in result.data.concepts if c.strip()]
    return concepts or unique[:80]
