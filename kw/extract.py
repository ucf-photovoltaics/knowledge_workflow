# -*- coding: utf-8 -*-
"""
Extraction stages (consolidates the old extractor + normalizer + schema_builder).

  build_concept_table(papers)            Step 1 - per-abstract concept extraction
  normalize_concept_list(canonicals)     Step 1 - dedupe -> shared concept list
  build_schema_rows(papers, concepts)    Step 2 - full-text mining (value + quote)

REBEL (the other half of Step 2) lives in kw/rebel.py and runs alongside this.
"""
import time
import os
import json
import hashlib

from pydantic_ai import Agent

from kw import llm
from kw.config import (pydantic_model, output_spec,
                       RATE_LIMIT_DELAY, TOP_N_PER_PAPER, FULL_TEXT_MAX_CHARS,
                       CHUNK_FULL_TEXT, CHUNK_SIZE, CHUNK_OVERLAP)
from kw.models import (
    ConceptList, ConceptRow, ConceptTable, NormalizedConceptList,
    SchemaValue, SchemaValueList, SchemaRow,
)


def _chunks(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping windows (used only when CHUNK_FULL_TEXT)."""
    if len(text) <= size:
        return [text]
    step = max(1, size - overlap)
    return [text[i:i + size] for i in range(0, len(text), step)]

# --------------------------------------------------------------------------- #
# Agents (defined once at module level)
# --------------------------------------------------------------------------- #
extractor_agent = Agent(
    pydantic_model, output_type=output_spec(ConceptList), retries=2,
    system_prompt=(
        'You are a scientific literature analyst and ontologist specialising in '
        'materials science and solar cell research. Given a paper abstract, extract '
        'domain-specific concepts in TWO forms: '
        '1. canonical - a general ontology-ready label (lowercase, 1-4 words) reusable '
        'as a column header across many papers (e.g. "absorber material", "device '
        'efficiency", "carrier lifetime"); avoid values ("22.1%") and vague terms ("cell"). '
        '2. paper_term - the specific term/value/phrase THIS paper uses for that concept. '
        "Score each 0.0-1.0 by centrality to the paper's contribution."
    ),
)

normalizer_agent = Agent(
    pydantic_model, output_type=output_spec(NormalizedConceptList), retries=2,
    system_prompt=(
        'You are a knowledge-graph ontologist. You receive candidate concept labels '
        'extracted from many papers. Return a clean, deduplicated, normalized set of '
        'ontology-ready labels (lowercase, 1-4 words). Merge near-synonyms (e.g. "voc", '
        '"open-circuit voltage" -> "open circuit voltage"); drop vague ("cell") and '
        'over-specific ("CdSeTe") labels. Aim for 30-80 distinct concepts, ordered by '
        'domain importance.'
    ),
)

schema_agent = Agent(
    pydantic_model, output_type=output_spec(SchemaValueList), retries=2,
    system_prompt=(
        'You are a precise scientific data extractor. Given the full text of a paper and '
        'a list of ontology concept labels, return for EACH concept: value - the exact '
        "term/number/short phrase this paper uses (the paper's own wording; empty string "
        'if absent); quote - the single most informative sentence establishing it (empty '
        'if none). Do not paraphrase. Do not invent values not in the text.'
    ),
)


# --------------------------------------------------------------------------- #
# Step 1 - concepts
# --------------------------------------------------------------------------- #
def extract_concepts_from_abstract(abstract: str, top_n: int = TOP_N_PER_PAPER) -> list:
    result = llm.run_sync(
        extractor_agent,
        f'Extract the top {top_n} concepts from this abstract. For each, give a '
        f'canonical ontology label AND the paper-specific term.\n\nAbstract:\n{abstract}'
    )
    return sorted(result.output.concepts, key=lambda c: c.relevance, reverse=True)[:top_n]


def build_concept_table(papers: dict, top_n: int = TOP_N_PER_PAPER) -> ConceptTable:
    rows: list[ConceptRow] = []
    items = [p for p in papers.values() if p.get('abstract')]
    total = len(items)
    for i, paper in enumerate(items, 1):
        print(f'  [{i}/{total}] Concepts: {paper["title"][:70]}')
        for c in extract_concepts_from_abstract(paper['abstract'], top_n=top_n):
            rows.append(ConceptRow(
                paper=paper['title'], doi=paper.get('doi', ''),
                canonical=c.canonical.strip().lower(),
                paper_term=c.paper_term, relevance=round(c.relevance, 4),
            ))
        if i < total:
            time.sleep(RATE_LIMIT_DELAY)
    return ConceptTable(rows=rows)


def normalize_concept_list(all_canonicals: list[str]) -> list[str]:
    unique = sorted(set(c for c in all_canonicals if c))
    if not unique:
        return []
    result = llm.run_sync(
        normalizer_agent,
        f'Here are {len(unique)} candidate concept labels from a domain corpus. '
        f'Normalize and deduplicate into a clean ontology-ready list (30-80).\n\n'
        + '\n'.join(f'- {c}' for c in unique)
    )
    concepts = [c.strip().lower() for c in result.output.concepts if c.strip()]
    return concepts or unique[:80]


# --------------------------------------------------------------------------- #
# Step 2 - mining (LLM half)
# --------------------------------------------------------------------------- #
def _mine_excerpt(excerpt: str, concepts: list[str]) -> dict[str, SchemaValue]:
    """One LLM mining pass over a single text excerpt."""
    out = {c: SchemaValue(canonical=c) for c in concepts}
    result = llm.run_sync(
        schema_agent,
        f'Paper text:\n\n{excerpt}\n\n---\n'
        f'For each concept below, return the paper-specific value and source quote:\n\n'
        + '\n'.join(f'- {c}' for c in concepts)
    )
    for sv in result.output.values:
        canon = sv.canonical.strip().lower()
        if canon in out:
            out[canon] = SchemaValue(canonical=canon, value=sv.value.strip(), quote=sv.quote.strip())
    return out


def populate_schema_row(full_text: str, concepts: list[str]) -> dict[str, SchemaValue]:
    text = full_text or ''
    if not text:
        return {c: SchemaValue(canonical=c) for c in concepts}

    if not CHUNK_FULL_TEXT:
        # Legacy behaviour: single truncated excerpt.
        return _mine_excerpt(text[:FULL_TEXT_MAX_CHARS], concepts)

    # Chunked mining: scan overlapping windows and keep the first non-empty
    # value found per concept (preferring the one with a supporting quote).
    merged = {c: SchemaValue(canonical=c) for c in concepts}
    for chunk in _chunks(text, CHUNK_SIZE, CHUNK_OVERLAP):
        part = _mine_excerpt(chunk, concepts)
        for c, sv in part.items():
            cur = merged[c]
            if sv.value and (not cur.value or (sv.quote and not cur.quote)):
                merged[c] = sv
    return merged


def build_schema_rows(papers: dict, concepts: list[str], domain: str,
                      checkpoint_dir: str | None = None) -> list[SchemaRow]:
    """Mine every paper. If checkpoint_dir is set, each paper's result is cached
    to disk and reused on a later run (so a crash resumes instead of restarting).
    The cache is invalidated automatically if the concept set changes."""
    rows: list[SchemaRow] = []
    items = [p for p in papers.values() if p.get('abstract') or p.get('full_text')]
    total = len(items)
    chash = hashlib.md5('|'.join(concepts).encode('utf-8')).hexdigest()[:8]
    if checkpoint_dir:
        os.makedirs(checkpoint_dir, exist_ok=True)

    for i, paper in enumerate(items, 1):
        key   = paper.get('key') or paper.get('doi') or paper['title']
        cpath = (os.path.join(checkpoint_dir,
                              hashlib.md5(key.encode('utf-8')).hexdigest() + '.json')
                 if checkpoint_dir else None)
        cells = None
        if cpath and os.path.isfile(cpath):
            try:
                cached = json.load(open(cpath, encoding='utf-8'))
                if cached.get('concepts_hash') == chash:
                    cells = cached['cells']
                    print(f'  [{i}/{total}] cached: {paper["title"][:60]}')
            except Exception:
                cells = None

        if cells is None:
            print(f'  [{i}/{total}] Mining: {paper["title"][:70]}')
            text = paper.get('full_text') or paper.get('abstract', '')
            data = populate_schema_row(text, concepts)
            cells = {c: data.get(c, SchemaValue(canonical=c)).formatted() for c in concepts}
            if cpath:
                with open(cpath, 'w', encoding='utf-8') as fh:
                    json.dump({'concepts_hash': chash, 'cells': cells}, fh, ensure_ascii=False)
            if i < total:
                time.sleep(RATE_LIMIT_DELAY)

        rows.append(SchemaRow(domain=domain, doi=paper.get('doi', ''), cells=cells))
    return rows
