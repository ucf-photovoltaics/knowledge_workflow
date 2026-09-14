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
import re
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic_ai import Agent

from kw import llm
from kw.config import (pydantic_model, output_spec,
                       RATE_LIMIT_DELAY, TOP_N_PER_PAPER, FULL_TEXT_MAX_CHARS,
                       CHUNK_FULL_TEXT, CHUNK_SIZE, CHUNK_OVERLAP,
                       CONCEPT_SOURCE, INTRO_MAX_CHARS, MINE_WORKERS)
from kw.models import (
    ConceptList, ConceptRow, ConceptTable, NormalizedConceptList,
    SchemaValue, SchemaValueList, SchemaRow, DomainContext,
)

# Unsupervised per-collection domain inference (de-biases Step 1). Off => no hint.
INFER_DOMAIN = os.getenv('INFER_DOMAIN', 'true').lower() != 'false'


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
        'You are a scientific literature analyst and ontologist. Given the abstract and '
        'introduction of a research paper, extract domain-specific concepts in TWO forms: '
        '1. canonical - a general ontology-ready label (lowercase, 1-4 words) reusable as a '
        'column header across papers in the SAME field (a material, a method, a measured '
        'property, a device/structure, a process); avoid numeric values ("22.1%") and vague '
        'terms ("cell"). 2. paper_term - the specific term/value/phrase THIS paper uses. '
        "Score each 0.0-1.0 by centrality to the paper's contribution. Stay faithful to the "
        'paper\'s actual subject area, whatever field it is in - do not assume any particular domain.'
    ),
)

normalizer_agent = Agent(
    pydantic_model, output_type=output_spec(NormalizedConceptList), retries=2,
    system_prompt=(
        'You are a knowledge-graph ontologist. You receive candidate concept labels '
        'extracted from many papers in ONE research collection. Return a clean, deduplicated, '
        'normalized set of ontology-ready labels (lowercase, 1-4 words). Merge near-synonyms '
        'and abbreviations with their expansions; drop vague labels and overly specific '
        'instance names. Aim for 50-80 distinct concepts, ordered by domain importance. Stay '
        "faithful to the collection's actual domain - do not impose concepts from other fields."
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


domain_agent = Agent(
    pydantic_model, output_type=output_spec(DomainContext), retries=2,
    system_prompt=(
        'You are a research librarian. Given a sample of paper titles (and short '
        'abstracts) from ONE collection, identify the specific research domain in a short '
        'phrase and list 5-8 general, reusable concept categories an ontology of this '
        'corpus should capture. Be faithful to the actual topic; do not assume any field.'
    ),
)


# --------------------------------------------------------------------------- #
# Step 1 - concepts
# --------------------------------------------------------------------------- #
# Section headings that typically follow the Introduction (mark where it ends).
_INTRO_HEAD = re.compile(r'\bintroduction\b', re.I)
_NEXT_SECTION = re.compile(
    r'\b(?:materials?\s+and\s+methods?|methodology|methods?|experimental|'
    r'results?\s+and\s+discussion|results?|discussion|background|'
    r'theoretical\s+background|theory|related\s+work|literature\s+review|'
    r'conclusions?)\b', re.I)


def intro_section(full_text: str, max_chars: int = INTRO_MAX_CHARS) -> str:
    """Best-effort slice of a paper's Introduction from its full text.

    Anchors on the 'Introduction' heading and stops at the next common section
    heading; if no heading is found, falls back to the head of the body. Always
    length-capped. Returns '' when there is no usable text.
    """
    text = (full_text or '').strip()
    if not text:
        return ''
    m = _INTRO_HEAD.search(text)
    if not m:
        return text[:max_chars].strip()          # no heading: proxy with the body head
    window = text[m.end(): m.end() + max_chars * 3]
    end = _NEXT_SECTION.search(window, 200)       # skip a little so it doesn't end immediately
    intro = (window[:end.start()] if end else window).strip()
    if len(intro) < 200:                          # heading matched junk -> fall back
        return text[:max_chars].strip()
    return intro[:max_chars]


def concept_source_text(paper: dict) -> str:
    """Text fed to Step 1, per config.CONCEPT_SOURCE ('abstract' | 'abstract+intro')."""
    abstract = (paper.get('abstract') or '').strip()
    if CONCEPT_SOURCE != 'abstract+intro':
        return abstract
    intro = intro_section(paper.get('full_text') or '')
    if abstract and intro:
        return f'Abstract:\n{abstract}\n\nIntroduction:\n{intro}'
    return abstract or intro


def extract_concepts(text: str, top_n: int = TOP_N_PER_PAPER, domain_hint: str = '') -> list:
    preamble = f'Corpus domain: {domain_hint}\n\n' if domain_hint else ''
    result = llm.run_sync(
        extractor_agent,
        f'{preamble}Extract the top {top_n} concepts from the following text (the abstract and '
        f'introduction of a paper). For each, give a canonical ontology label AND the '
        f'paper-specific term.\n\n{text}'
    )
    return sorted(result.output.concepts, key=lambda c: c.relevance, reverse=True)[:top_n]


def extract_concepts_from_abstract(abstract: str, top_n: int = TOP_N_PER_PAPER,
                                  domain_hint: str = '') -> list:
    """Back-compat alias; prefer extract_concepts(text)."""
    return extract_concepts(abstract, top_n=top_n, domain_hint=domain_hint)


def infer_domain_context(papers: dict, sample: int = 20) -> str:
    """Unsupervised, one LLM pass over sampled titles+abstracts -> a short domain hint
    used to focus Step 1 (de-biases extraction). Returns '' if disabled or on failure."""
    if not INFER_DOMAIN:
        return ''
    items = [p for p in papers.values() if p.get('title')]
    if not items:
        return ''
    lines = []
    for p in items[:sample]:
        ab = (p.get('abstract') or '').strip().replace('\n', ' ')
        lines.append(f"- {p['title']}" + (f" :: {ab[:200]}" if ab else ''))
    try:
        result = llm.run_sync(
            domain_agent,
            'Identify the research domain and concept categories for this collection.\n\n'
            + '\n'.join(lines))
        dc = result.output
        cats = ', '.join(dc.categories[:8]) if dc.categories else ''
        hint = dc.domain.strip() + (f' (key categories: {cats})' if cats else '')
        print(f'  [domain] inferred: {hint}')
        return hint
    except Exception as exc:                              # noqa: BLE001
        print(f'  [domain] inference skipped ({exc})')
        return ''


def _merge_concepts(concept_lists: list[list]) -> list:
    """Merge per-chunk concept lists: dedup by canonical, keep the max-relevance hit."""
    best: dict[str, object] = {}
    for cs in concept_lists:
        for c in cs:
            key = c.canonical.strip().lower()
            if not key:
                continue
            if key not in best or c.relevance > best[key].relevance:
                best[key] = c
    return sorted(best.values(), key=lambda c: c.relevance, reverse=True)


def extract_concepts_for_paper(paper: dict, top_n: int = TOP_N_PER_PAPER,
                               domain_hint: str = '') -> list:
    """Step-1 concept extraction for one paper, honoring config.CONCEPT_SOURCE.

      abstract       - concepts from the abstract only
      abstract+intro - concepts from abstract + sliced introduction
      full-text      - chunk the WHOLE paper, extract per chunk, merge (dedup by
                       canonical, keep max relevance). Falls back to the abstract
                       when a paper has no extractable full text.
    """
    if CONCEPT_SOURCE == 'full-text':
        full = (paper.get('full_text') or '').strip()
        if full:
            chunks = _chunks(full, CHUNK_SIZE, CHUNK_OVERLAP)
            print(f'      [concepts] full-text: {len(full)} chars in {len(chunks)} chunk(s)')
            return _merge_concepts([extract_concepts(ck, top_n=top_n, domain_hint=domain_hint) for ck in chunks])
        abstract = (paper.get('abstract') or '').strip()   # no full text -> abstract only
        return extract_concepts(abstract, top_n=top_n, domain_hint=domain_hint) if abstract else []
    text = concept_source_text(paper)
    return extract_concepts(text, top_n=top_n, domain_hint=domain_hint) if text else []


def build_concept_table(papers: dict, top_n: int = TOP_N_PER_PAPER,
                        min_relevance: float = 0.0, domain_hint: str = '') -> ConceptTable:
    rows: list[ConceptRow] = []
    items = [p for p in papers.values() if p.get('abstract') or p.get('full_text')]
    total = len(items)
    kept = dropped = 0
    print(f'  [concepts] source={CONCEPT_SOURCE}, top_n={top_n}')
    for i, paper in enumerate(items, 1):
        print(f'  [{i}/{total}] Concepts: {paper["title"][:70]}')
        concepts = extract_concepts_for_paper(paper, top_n=top_n, domain_hint=domain_hint)
        if not concepts:
            continue
        for c in concepts:
            if min_relevance and c.relevance < min_relevance:
                dropped += 1
                continue
            kept += 1
            rows.append(ConceptRow(
                paper=paper['title'], doi=paper.get('doi', ''),
                canonical=c.canonical.strip().lower(),
                paper_term=c.paper_term, relevance=round(c.relevance, 4),
            ))
        if i < total:
            time.sleep(RATE_LIMIT_DELAY)
    if min_relevance:
        print(f'  [concepts] relevance>={min_relevance}: kept {kept}, dropped {dropped}')
    return ConceptTable(rows=rows)


def normalize_concept_list(all_canonicals: list[str], max_concepts: int = 0,
                           domain_hint: str = '') -> list[str]:
    unique = sorted(set(c for c in all_canonicals if c))
    if not unique:
        return []
    target = str(max_concepts) if max_concepts and max_concepts > 0 else '30-80'
    preamble = f'Corpus domain: {domain_hint}\n\n' if domain_hint else ''
    result = llm.run_sync(
        normalizer_agent,
        f'{preamble}Here are {len(unique)} candidate concept labels from this collection. '
        f'Normalize and deduplicate into a clean ontology-ready list ({target}).\n\n'
        + '\n'.join(f'- {c}' for c in unique)
    )
    concepts = [c.strip().lower() for c in result.output.concepts if c.strip()] or unique[:80]
    if max_concepts and max_concepts > 0:
        concepts = concepts[:max_concepts]
    return concepts


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

    # Chunked mining with chunk-skip: each window only queries concepts that are
    # not yet filled, and we stop as soon as every concept has a value. This drops
    # the redundant re-asking of already-found concepts in later chunks.
    merged = {c: SchemaValue(canonical=c) for c in concepts}
    remaining = list(concepts)
    for chunk in _chunks(text, CHUNK_SIZE, CHUNK_OVERLAP):
        if not remaining:
            break
        part = _mine_excerpt(chunk, remaining)
        for c in list(remaining):
            sv = part.get(c)
            if sv and sv.value:
                merged[c] = sv
                remaining.remove(c)
    return merged


def _mine_one(idx: int, total: int, paper: dict, concepts: list[str], domain: str,
              chash: str, checkpoint_dir: str | None) -> SchemaRow:
    """Mine a single paper (checkpoint-aware). Used by both the sequential and
    parallel paths of build_schema_rows."""
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
                print(f'  [{idx}/{total}] cached: {paper["title"][:60]}')
        except Exception:
            cells = None

    if cells is None:
        print(f'  [{idx}/{total}] Mining: {paper["title"][:70]}')
        text = paper.get('full_text') or paper.get('abstract', '')
        data = populate_schema_row(text, concepts)
        cells = {c: data.get(c, SchemaValue(canonical=c)).formatted() for c in concepts}
        if cpath:
            with open(cpath, 'w', encoding='utf-8') as fh:
                json.dump({'concepts_hash': chash, 'cells': cells}, fh, ensure_ascii=False)
    return SchemaRow(domain=domain, doi=paper.get('doi', ''), cells=cells)


def build_schema_rows(papers: dict, concepts: list[str], domain: str,
                      checkpoint_dir: str | None = None) -> list[SchemaRow]:
    """Mine every paper. If checkpoint_dir is set, each paper's result is cached
    to disk and reused on a later run (so a crash resumes instead of restarting).
    The cache is invalidated automatically if the concept set changes.

    Set MINE_WORKERS>1 to mine papers concurrently with a thread pool. This only
    speeds things up if the LLM backend serves parallel requests (e.g. Ollama with
    OLLAMA_NUM_PARALLEL>=2); otherwise leave it at 1. Output order is preserved and
    a single paper failing does not abort the batch."""
    items = [p for p in papers.values() if p.get('abstract') or p.get('full_text')]
    total = len(items)
    chash = hashlib.md5('|'.join(concepts).encode('utf-8')).hexdigest()[:8]
    if checkpoint_dir:
        os.makedirs(checkpoint_dir, exist_ok=True)

    workers = max(1, MINE_WORKERS)
    if workers > 1 and total > 1:
        print(f'  [mine] parallel: {workers} workers over {total} papers '
              f'(needs OLLAMA_NUM_PARALLEL>=2 to actually overlap)')
        rows: list[SchemaRow | None] = [None] * total
        with ThreadPoolExecutor(max_workers=workers) as ex:
            fut_to_idx = {
                ex.submit(_mine_one, i, total, paper, concepts, domain, chash, checkpoint_dir): i - 1
                for i, paper in enumerate(items, 1)
            }
            for fut in as_completed(fut_to_idx):
                idx = fut_to_idx[fut]
                try:
                    rows[idx] = fut.result()
                except Exception as exc:                  # one paper must not kill the batch
                    p = items[idx]
                    print(f'  [mine] paper {idx + 1}/{total} failed ({exc}); leaving blank.')
                    rows[idx] = SchemaRow(domain=domain, doi=p.get('doi', ''),
                                          cells={c: '' for c in concepts})
        return [r for r in rows if r is not None]

    rows: list[SchemaRow] = []
    for i, paper in enumerate(items, 1):
        rows.append(_mine_one(i, total, paper, concepts, domain, chash, checkpoint_dir))
        if i < total and RATE_LIMIT_DELAY:               # 0 => no inter-paper delay (local LLM)
            time.sleep(RATE_LIMIT_DELAY)
    return rows
