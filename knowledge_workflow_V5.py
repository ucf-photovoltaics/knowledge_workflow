# -*- coding: utf-8 -*-
"""
V5: Provider-agnostic two-stage knowledge extraction using any OpenAI-compatible API.

Identical pipeline to V4 (concept extraction → normalization → schema population)
but uses the openai Python client, which works with any service that follows the
OpenAI API standard:

  Provider         BASE_URL                              MODEL example
  --------         --------                              ------------
  OpenAI           https://api.openai.com/v1             gpt-4o
  Anthropic        https://api.anthropic.com/v1          claude-sonnet-4-6
  Groq             https://api.groq.com/openai/v1        llama-3.3-70b-versatile
  Together AI      https://api.together.xyz/v1            meta-llama/Llama-3-70b-chat-hf
  Mistral          https://api.mistral.ai/v1              mistral-large-latest
  Ollama (local)   http://localhost:11434/v1              llama3.2
  LM Studio        http://localhost:1234/v1               <loaded-model-name>
  vLLM             http://localhost:8000/v1               <model-path>

Configuration (in order of precedence):
  1. Edit the CONFIG block below
  2. Set environment variables: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
  3. .env file in project root

Notes:
  - Tool/function calling must be supported by the chosen model & provider.
    Most hosted providers support it; local models vary.
  - If tool_choice forced-name syntax fails for your provider, set
    FORCE_TOOL_CHOICE = False — responses will be parsed more leniently.
  - Anthropic's own API follows the Anthropic SDK format (not OpenAI); use V3/V4
    for Anthropic. Anthropic does expose a beta OpenAI-compat layer, but V5 is
    not required for it — use the env vars to point at it if desired.

Output files (saved to outputs/<collection>/):
  concepts_<name>-<user>-v5-<date>.csv   (flat extraction table)
  schema_<name>-<user>-v5-<date>.csv     (wide-format schema)
  schemas/<collection>/schema_<name>-<user>-v5-<date>.csv  (copy for reuse)
"""

from pyzotero import Zotero
from openai import OpenAI
import pandas as pd
from pypdf import PdfReader
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
import json, re, glob, os, time

load_dotenv()

# ---------------------------------------------------------------------------
# CONFIG — edit these, or set the equivalent environment variables
# ---------------------------------------------------------------------------

# Zotero
ZOTERO_LIBRARY_ID   = '2189702'
ZOTERO_LIBRARY_TYPE = 'group'
ZOTERO_API_KEY      = os.getenv('ZOTERO_API_KEY', '')

# LLM provider — any OpenAI-compatible endpoint
# Examples:
#   OpenAI:     LLM_BASE_URL=https://api.openai.com/v1    LLM_MODEL=gpt-4o
#   Anthropic:  LLM_BASE_URL=https://api.anthropic.com/v1 LLM_MODEL=claude-sonnet-4-6
#   Groq:       LLM_BASE_URL=https://api.groq.com/openai/v1
#   Ollama:     LLM_BASE_URL=http://localhost:11434/v1    LLM_MODEL=llama3.2
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
LLM_API_KEY  = os.getenv('LLM_API_KEY',  os.getenv('OPENAI_API_KEY', os.getenv('ANTHROPIC_API_KEY', '')))
MODEL        = os.getenv('LLM_MODEL',    'gpt-4o')

# If your provider/model doesn't support forced tool_choice by name, set False.
# Responses will still be parsed from the first tool call returned.
FORCE_TOOL_CHOICE = True

RATE_LIMIT_DELAY    = 0.5   # seconds between LLM calls
TOP_N_PER_PAPER     = 25    # concepts to extract per paper (Phase 1)
FULL_TEXT_MAX_CHARS = 80_000  # ~20k tokens; safe for most 128k+ context models

# Optional: skip Phase 1 and use an existing concept list from a CSV
USE_CSV_CONCEPTS  = False
CONCEPTS_CSV_PATH = ''       # path to rankings_*.csv or schema_*.csv
CONCEPTS_COLUMN   = 'concept'

# ---------------------------------------------------------------------------

zot    = Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)
client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

# ---------------------------------------------------------------------------
# TOOL SCHEMAS  (OpenAI function-calling format)
# ---------------------------------------------------------------------------

_EXTRACT_TOOL = {
    'type': 'function',
    'function': {
        'name': 'return_concepts',
        'description': (
            'Return key concepts extracted from the abstract. '
            'Each concept has a canonical ontology label AND the paper-specific term.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'concepts': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'canonical': {
                                'type': 'string',
                                'description': (
                                    'Ontology-ready label, lowercase, 1-4 words, suitable as a '
                                    'reusable column header across multiple papers. '
                                    'E.g. "absorber material", "device efficiency", '
                                    '"dopant species", "carrier lifetime".'
                                )
                            },
                            'paper_term': {
                                'type': 'string',
                                'description': (
                                    'The specific term, compound, or value this paper uses '
                                    'for that concept. E.g. "CdSexTe1-x", "22%", "arsenic".'
                                )
                            },
                            'relevance': {
                                'type': 'number',
                                'description': 'Relevance score 0.0–1.0'
                            }
                        },
                        'required': ['canonical', 'paper_term', 'relevance']
                    }
                }
            },
            'required': ['concepts']
        }
    }
}

_NORMALIZE_TOOL = {
    'type': 'function',
    'function': {
        'name': 'return_normalized_concepts',
        'description': (
            'Return a deduplicated, normalized list of ontology-ready concept labels '
            'distilled from candidate labels across the full corpus.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'concepts': {
                    'type': 'array',
                    'items': {
                        'type': 'string',
                        'description': (
                            'Canonical concept label: lowercase, 1-4 words, '
                            'general enough to apply across multiple papers.'
                        )
                    }
                }
            },
            'required': ['concepts']
        }
    }
}

_SCHEMA_TOOL = {
    'type': 'function',
    'function': {
        'name': 'return_schema_values',
        'description': (
            'For each canonical concept, return the paper-specific value and '
            'the most informative source sentence from the paper text.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'values': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'canonical': {
                                'type': 'string',
                                'description': 'The canonical concept label being answered.'
                            },
                            'value': {
                                'type': 'string',
                                'description': (
                                    'The specific term, measurement, or short description '
                                    'this paper reports for the concept. '
                                    'Empty string if not found.'
                                )
                            },
                            'quote': {
                                'type': 'string',
                                'description': (
                                    'The single most informative sentence or phrase from '
                                    'the paper that establishes this concept. '
                                    'Empty string if not found.'
                                )
                            }
                        },
                        'required': ['canonical', 'value', 'quote']
                    }
                }
            },
            'required': ['values']
        }
    }
}

# ---------------------------------------------------------------------------
# SYSTEM PROMPTS
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM = (
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
    'Score each 0.0–1.0 by centrality to the paper\'s contribution.'
)

_NORMALIZE_SYSTEM = (
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
)

_SCHEMA_SYSTEM = (
    'You are a precise scientific data extractor. '
    'You will be given the full text of a scientific paper and a list of '
    'ontology concept labels. '
    'For EACH concept, find and return:\n'
    '  value  — the exact term, number, or very short phrase this paper uses '
    'for that concept (use the paper\'s own wording). '
    'If the concept is not addressed in this paper, use an empty string.\n'
    '  quote  — the single most informative sentence from the text that '
    'establishes or describes this concept. '
    'Prefer results sections, abstracts, or conclusion sentences. '
    'If not found, use an empty string.\n\n'
    'Be precise. Do not paraphrase. Do not invent values not in the text.'
)

# ---------------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------------

def make_filename(collection_name, username='Brent_Thompson', version=5):
    date = datetime.now().strftime('%Y%m%d')
    name = collection_name.replace(' ', '_').lower()
    return f"{name}-{username}-v{version}-{date}.csv"


def find_latest_file(pattern):
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _tool_choice(name):
    """Build tool_choice param; returns None if FORCE_TOOL_CHOICE is disabled."""
    if not FORCE_TOOL_CHOICE:
        return 'auto'
    return {'type': 'function', 'function': {'name': name}}


def _parse_tool_call(response, expected_name):
    """
    Extract and JSON-parse the first matching tool call from an OpenAI response.
    Returns the parsed dict, or None if not found.
    """
    msg = response.choices[0].message
    if not msg.tool_calls:
        return None
    for tc in msg.tool_calls:
        if tc.function.name == expected_name:
            try:
                return json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                return None
    # Fallback: return first tool call regardless of name
    try:
        return json.loads(msg.tool_calls[0].function.arguments)
    except json.JSONDecodeError:
        return None

# ---------------------------------------------------------------------------
# ZOTERO
# ---------------------------------------------------------------------------

def get_collection_map():
    """Return {collection_name: collection_id} for all collections."""
    return {c['data']['name']: c['key'] for c in zot.collections()}


def get_pdf_text(item_key):
    """Extract full text from a Zotero item's PDF attachment."""
    for child in zot.children(item_key):
        if child['data'].get('contentType') == 'application/pdf':
            try:
                reader = PdfReader(BytesIO(zot.file(child['key'])))
                return ''.join(p.extract_text() or '' for p in reader.pages)
            except Exception:
                pass
    return ''


def get_collection_with_text(collection_id):
    """Return {title_lower: {metadata + full_text}} for all papers."""
    items = zot.everything(zot.collection_items(collection_id))
    collection = {}
    for item in items:
        data = item['data']
        if data.get('itemType') in ('attachment', 'note') or not data.get('title'):
            continue
        collection[data['title'].lower()] = {
            'key':       item['key'],
            'title':     data['title'],
            'doi':       data.get('DOI', ''),
            'abstract':  data.get('abstractNote', ''),
            'date':      data.get('date', ''),
            'authors':   data.get('creators', []),
            'full_text': get_pdf_text(item['key'])
        }
    return collection

# ---------------------------------------------------------------------------
# AI AGENT — PHASE 1: CONCEPT EXTRACTION
# ---------------------------------------------------------------------------

def extract_concepts_from_abstract(abstract, top_n=25):
    """
    Extract concepts from a single abstract.
    Returns a list of dicts: [{canonical, paper_term, relevance}, ...]
    sorted by relevance descending.
    """
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=2048,
        messages=[
            {'role': 'system', 'content': _EXTRACT_SYSTEM},
            {'role': 'user',   'content': (
                f'Extract the top {top_n} concepts from this abstract. '
                f'For each, provide a canonical ontology label AND the paper-specific term.\n\n'
                f'Abstract:\n{abstract}'
            )}
        ],
        tools=[_EXTRACT_TOOL],
        tool_choice=_tool_choice('return_concepts'),
    )
    result = _parse_tool_call(response, 'return_concepts')
    if result:
        concepts = result.get('concepts', [])
        return sorted(concepts, key=lambda c: c.get('relevance', 0), reverse=True)[:top_n]
    return []


def build_concept_table(collection_dict, top_n=25):
    """
    Phase 1: Run per-paper concept extraction across the collection.

    Returns:
      df_concepts    — flat DataFrame (paper, doi, canonical, paper_term, relevance)
      all_canonicals — list of all raw canonical labels (with duplicates, for normalization)
    """
    rows = []
    all_canonicals = []
    papers = [p for p in collection_dict.values() if p.get('abstract')]
    total = len(papers)

    for i, paper in enumerate(papers, 1):
        print(f'  [{i}/{total}] Extracting: {paper["title"][:70]}')
        concepts = extract_concepts_from_abstract(paper['abstract'], top_n=top_n)
        for c in concepts:
            canon = c.get('canonical', '').strip().lower()
            rows.append({
                'paper':      paper['title'],
                'doi':        paper.get('doi', ''),
                'canonical':  canon,
                'paper_term': c.get('paper_term', ''),
                'relevance':  round(c.get('relevance', 0), 4)
            })
            all_canonicals.append(canon)
        if i < total:
            time.sleep(RATE_LIMIT_DELAY)

    return pd.DataFrame(rows), all_canonicals


def normalize_concept_list(all_canonicals):
    """
    Deduplication/normalization pass: merges near-synonyms and
    returns a clean list of 30–80 ontology-ready concept labels.
    """
    unique = sorted(set(c for c in all_canonicals if c))
    if not unique:
        return []

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=2048,
        messages=[
            {'role': 'system', 'content': _NORMALIZE_SYSTEM},
            {'role': 'user',   'content': (
                f'Here are {len(unique)} candidate concept labels from a corpus of '
                f'solar cell materials papers. '
                f'Normalize and deduplicate into a clean ontology-ready list (30–80 concepts).\n\n'
                + '\n'.join(f'- {c}' for c in unique)
            )}
        ],
        tools=[_NORMALIZE_TOOL],
        tool_choice=_tool_choice('return_normalized_concepts'),
    )
    result = _parse_tool_call(response, 'return_normalized_concepts')
    if result:
        return [c.strip().lower() for c in result.get('concepts', []) if c.strip()]
    return unique[:80]

# ---------------------------------------------------------------------------
# AI AGENT — PHASE 2: SCHEMA POPULATION
# ---------------------------------------------------------------------------

def populate_schema_row(full_text, canonical_concepts):
    """
    For one paper's full text and the normalized concept list,
    extract the paper-specific value and source sentence for each concept.

    Returns: {canonical: {'value': str, 'quote': str}}
    """
    empty = {c: {'value': '', 'quote': ''} for c in canonical_concepts}
    text_excerpt = (full_text or '')[:FULL_TEXT_MAX_CHARS]
    if not text_excerpt:
        return empty

    concept_list = '\n'.join(f'- {c}' for c in canonical_concepts)

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {'role': 'system', 'content': _SCHEMA_SYSTEM},
            {'role': 'user',   'content': (
                f'Paper text (may be truncated to {FULL_TEXT_MAX_CHARS:,} characters):\n\n'
                f'{text_excerpt}\n\n'
                f'---\n'
                f'For each concept below, return the paper-specific value and source quote:\n\n'
                f'{concept_list}'
            )}
        ],
        tools=[_SCHEMA_TOOL],
        tool_choice=_tool_choice('return_schema_values'),
    )

    result = _parse_tool_call(response, 'return_schema_values')
    if not result:
        return empty

    out = empty.copy()
    for item in result.get('values', []):
        canon = item.get('canonical', '').strip().lower()
        if canon in out:
            out[canon] = {
                'value': item.get('value', '').strip(),
                'quote': item.get('quote', '').strip()
            }
    return out


def build_schema_csv(collection_dict, canonical_concepts, domain):
    """
    Phase 2: Build the wide-format schema DataFrame.

    One row per paper:
      domain  — the collection/domain name
      doi     — paper DOI
      <concept_1> ... <concept_N>
                — "paper-specific value | source sentence"
    """
    rows = []
    papers = [
        p for p in collection_dict.values()
        if p.get('abstract') or p.get('full_text')
    ]
    total = len(papers)

    for i, paper in enumerate(papers, 1):
        print(f'  [{i}/{total}] Schema row: {paper["title"][:70]}')
        text = paper.get('full_text') or paper.get('abstract', '')
        schema_data = populate_schema_row(text, canonical_concepts)

        row = {'domain': domain, 'doi': paper.get('doi', '')}
        for concept in canonical_concepts:
            cv    = schema_data.get(concept, {'value': '', 'quote': ''})
            value = cv.get('value', '')
            quote = cv.get('quote', '')
            if value and quote:
                row[concept] = f'{value} | {quote}'
            elif value:
                row[concept] = value
            elif quote:
                row[concept] = quote
            else:
                row[concept] = ''
        rows.append(row)
        if i < total:
            time.sleep(RATE_LIMIT_DELAY)

    columns = ['domain', 'doi'] + canonical_concepts
    return pd.DataFrame(rows, columns=columns)

# ---------------------------------------------------------------------------
# WORKFLOW
# ---------------------------------------------------------------------------

if __name__ == '__main__':

    print(f'Provider: {LLM_BASE_URL}')
    print(f'Model:    {MODEL}\n')

    # 1. List available Zotero collections
    my_collections = get_collection_map()
    print('Available collections:')
    for name in my_collections:
        print(f'  {name}')

    # 2. Select collection
    collection_name = 'CdTe'            # <-- change this
    domain          = collection_name.lower().replace(' ', '_')

    papers = get_collection_with_text(my_collections[collection_name])
    print(f'\nLoaded {len(papers)} papers from "{collection_name}"')

    # 3. Report missing PDFs
    missing_pdf = [p['title'] for p in papers.values() if not p['full_text']]
    if missing_pdf:
        print(f'\n{len(missing_pdf)} papers without PDF (will use abstract for Phase 2):')
        for t in missing_pdf:
            print(f'  - {t}')

    # -----------------------------------------------------------------------
    # Concept list: extract fresh or load from CSV
    # -----------------------------------------------------------------------
    if USE_CSV_CONCEPTS and CONCEPTS_CSV_PATH:
        print(f'\n[Concepts] Loading from CSV: {CONCEPTS_CSV_PATH}')
        normalized_concepts = (
            pd.read_csv(CONCEPTS_CSV_PATH)[CONCEPTS_COLUMN]
            .dropna().str.strip().str.lower().tolist()
        )
        print(f'  Loaded {len(normalized_concepts)} concepts.')
        df_concepts = pd.DataFrame()

    else:
        # Phase 1 — extract per-paper concepts from abstracts
        print(f'\n[Phase 1] Extracting concepts ({TOP_N_PER_PAPER}/paper) with {MODEL}...')
        df_concepts, all_canonicals = build_concept_table(papers, top_n=TOP_N_PER_PAPER)
        print(f'  {len(df_concepts)} concept-paper pairs extracted.')
        print(f'  {len(set(all_canonicals))} unique raw canonical labels.')

        # Normalization pass
        print(f'\n[Normalization] Normalizing concept list with {MODEL}...')
        time.sleep(RATE_LIMIT_DELAY)
        normalized_concepts = normalize_concept_list(all_canonicals)
        print(f'  Normalized to {len(normalized_concepts)} canonical concepts:')
        for c in normalized_concepts[:10]:
            print(f'    - {c}')
        if len(normalized_concepts) > 10:
            print(f'    ... and {len(normalized_concepts) - 10} more')

        latest_rankings = find_latest_file(
            f"outputs/*/{collection_name.replace(' ', '_').lower()}*/rankings_*.csv"
        )
        if latest_rankings:
            print(f'\n  Note: found existing rankings file: {latest_rankings}')
            print('  Set USE_CSV_CONCEPTS = True and CONCEPTS_CSV_PATH to use it instead.')

    # -----------------------------------------------------------------------
    # Phase 2 — populate schema rows from full text
    # -----------------------------------------------------------------------
    print(f'\n[Phase 2] Building schema CSV ({len(normalized_concepts)} columns) with {MODEL}...')
    print('  (Mining full PDF text per paper — this may take a few minutes)')
    df_schema = build_schema_csv(papers, normalized_concepts, domain)

    # -----------------------------------------------------------------------
    # Save outputs to outputs/<collection>/
    # -----------------------------------------------------------------------
    collection_slug = collection_name.replace(' ', '_').lower()
    out_dir = os.path.join('outputs', collection_slug)
    os.makedirs(out_dir, exist_ok=True)
    prefix = make_filename(collection_name)

    if not df_concepts.empty:
        concepts_file = os.path.join(out_dir, f'concepts_{prefix}')
        df_concepts.to_csv(concepts_file, index=False)
        print(f'\nSaved: {concepts_file}')

    schema_file = os.path.join(out_dir, f'schema_{prefix}')
    df_schema.to_csv(schema_file, index=False)
    print(f'Saved: {schema_file}')

    # Copy to schemas/<collection>/ for reuse in later runs
    schema_dir = os.path.join('schemas', collection_slug)
    os.makedirs(schema_dir, exist_ok=True)
    schema_copy = os.path.join(schema_dir, f'schema_{prefix}')
    df_schema.to_csv(schema_copy, index=False)
    print(f'Saved: {schema_copy}')

    # -----------------------------------------------------------------------
    # Preview
    # -----------------------------------------------------------------------
    if not df_concepts.empty:
        print('\n--- Concept extraction (top 20 rows) ---')
        print(df_concepts.head(20).to_string(index=False))

    print(f'\n--- Schema CSV preview ---')
    print(f'Shape: {df_schema.shape[0]} rows × {df_schema.shape[1]} columns')
    preview_cols = ['domain', 'doi'] + normalized_concepts[:4]
    available    = [c for c in preview_cols if c in df_schema.columns]
    print(df_schema[available].head(3).to_string())
    print(f'\nAll concept columns ({len(normalized_concepts)}):')
    for c in normalized_concepts:
        print(f'  {c}')
