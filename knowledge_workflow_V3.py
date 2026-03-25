# -*- coding: utf-8 -*-
"""
V3: Claude AI agent — structured device & material parameter extraction.

Reads one paper at a time, returns a single structured row per paper using
a Pydantic model built dynamically from a V4 schema CSV (or default concepts).

Fixed universal columns (always first):
  Title | Author | Institution | Country | DOI | Device Type

Domain-specific columns (from V4 schema CSV, or _DEFAULT_CONCEPTS):
  absorber composition | absorber crystallinity | ... (any concepts from V4)

Reads ANTHROPIC_API_KEY from the .env file in the project root.
"""

from pyzotero import Zotero
import anthropic
import instructor
import pandas as pd
from pydantic import BaseModel, Field, create_model
from pypdf import PdfReader
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
from typing import Literal, Any
import re, glob, os, time

load_dotenv()

# --- CONFIG ---
LIBRARY_ID        = '2189702'
LIBRARY_TYPE      = 'group'
API_KEY           = 'W3COg3WIiWEvORVM3CiTLwc2'    # Zotero API key (revoke & move to .env)
MODEL             = 'claude-sonnet-4-6'
RATE_LIMIT_DELAY  = 0.5                             # seconds between Claude API calls

# Optional: load concept columns from a V4 schema or rankings CSV.
# Leave blank to use _DEFAULT_CONCEPTS below.
CONCEPTS_CSV_PATH = ''
CONCEPTS_COLUMN   = 'concept'                       # column to read (for rankings CSVs)

zot    = Zotero(LIBRARY_ID, LIBRARY_TYPE, API_KEY)
client = instructor.from_anthropic(anthropic.Anthropic())


# ── Fixed universal fields (always present, always first) ─────────────────────
# These apply to any research domain and never change.

_FIXED_FIELDS: dict[str, tuple] = {
    'author': (
        str,
        Field(description='Last name of the first author. Output "Not Specified" if not explicitly stated.')
    ),
    'institution': (
        str,
        Field(description='Name of the institution of the first author. Output "Not Specified" if not explicitly stated.')
    ),
    'country': (
        str,
        Field(description='Country of that institution. Output "Not Specified" if not explicitly stated.')
    ),
    'doi': (
        str,
        Field(description='Full DOI URL (https://doi.org/10.xxxx/...). Output "Not Specified" if not explicitly stated.')
    ),
    'device_type': (
        Literal['photovoltaic cell', 'light emitting diode', 'photodetector', 'Not Specified'],
        Field(description='Type of device studied. Must be exactly one of the allowed values.')
    ),
}

# ── Default domain-specific concepts (used when no CSV is supplied) ───────────
# Replace or extend by pointing CONCEPTS_CSV_PATH at a V4 schema_*.csv or
# rankings_*.csv — those column/concept names become the extraction targets.

_DEFAULT_CONCEPTS = [
    'absorber composition',
    'absorber crystallinity',
    'absorber bandgap type',
    'absorber bandgap eV',
]

# Columns that appear in V4 schema CSVs but are NOT concept labels
_SCHEMA_SKIP_COLS = {'domain', 'doi', 'title', 'paper'}


# ── Dynamic model builder ─────────────────────────────────────────────────────

def _slug(concept: str) -> str:
    """Convert a concept label into a valid Python/Pydantic field name."""
    s = re.sub(r'[^a-z0-9]+', '_', concept.lower().strip()).strip('_')
    return s or 'concept'


def build_extraction_model(concepts: list[str]) -> type[BaseModel]:
    """
    Dynamically build a Pydantic model using pydantic.create_model().

    Fixed universal fields come first (author, institution, country, doi,
    device_type), followed by one str field per concept from the supplied list.
    instructor uses this model to auto-generate the tool schema sent to Claude
    and to validate the response.
    """
    fields: dict[str, Any] = dict(_FIXED_FIELDS)
    for concept in concepts:
        slug = _slug(concept)
        # Avoid colliding with the fixed field names
        if slug in fields:
            slug = f'{slug}_val'
        fields[slug] = (
            str,
            Field(
                description=(
                    f'For "{concept}": the exact term, value, or measurement this paper '
                    f'reports. Output "Not Specified" if not explicitly stated.'
                )
            ),
        )
    return create_model('PaperExtraction', **fields)


def build_system_prompt(concepts: list[str]) -> str:
    """
    Build the system prompt dynamically, ending with the domain-specific
    concept list so it can be swapped per collection without touching the rest.
    """
    concept_lines = '\n'.join(
        f'  - {concept}: the exact term, value, or measurement this paper reports. '
        f'"Not Specified" if absent.'
        for concept in concepts
    )
    return (
        'Act as an expert materials scientist and researcher. Your task is to analyze '
        'the provided research article and extract specific parameters into a structured format.\n\n'
        'Crucial: Do not infer, guess, or calculate missing information. '
        'If a value is not explicitly stated in the text, output exactly "Not Specified".\n\n'
        'Always extract these universal fields:\n'
        '  - author: Last name of the first author.\n'
        '  - institution: Name of the institution where the first author is affiliated.\n'
        '  - country: Country where that institution is located.\n'
        '  - doi: Full DOI URL formatted as https://doi.org/10.xxxx/...\n'
        '  - device_type: Classify strictly as "photovoltaic cell", '
        '"light emitting diode", "photodetector", or "Not Specified".\n\n'
        'Also extract these domain-specific concepts (output "Not Specified" if absent):\n'
        f'{concept_lines}'
    )


def model_to_row(instance: BaseModel, title: str, concepts: list[str]) -> dict:
    """Convert a dynamic PaperExtraction instance to a flat dict for a DataFrame row."""
    data = instance.model_dump()

    doi_val = data.get('doi', 'Not Specified') or 'Not Specified'
    if doi_val != 'Not Specified' and not doi_val.startswith('http'):
        doi_val = f'https://doi.org/{doi_val}'

    row: dict = {
        'Title':       title,
        'Author':      data.get('author',      'Not Specified'),
        'Institution': data.get('institution', 'Not Specified'),
        'Country':     data.get('country',     'Not Specified'),
        'DOI':         doi_val,
        'Device Type': data.get('device_type', 'Not Specified'),
    }
    for concept in concepts:
        row[concept] = data.get(_slug(concept), 'Not Specified')
    return row


def col_headers(concepts: list[str]) -> list[str]:
    """Return the ordered column list for a given concept set."""
    return ['Title', 'Author', 'Institution', 'Country', 'DOI', 'Device Type'] + concepts


# ── Concept loader ────────────────────────────────────────────────────────────

def load_concepts_from_csv(path: str, column: str = 'concept') -> list[str]:
    """
    Load concept labels from a V4 schema CSV or rankings CSV.

    V4 schema CSVs: columns after 'domain'/'doi' are concept labels.
    Rankings CSVs:  use the specified column name (default 'concept').
    """
    df = pd.read_csv(path)
    # V4 schema CSV: concept labels are all columns except the skip set
    if column not in df.columns:
        return [c for c in df.columns if c.lower() not in _SCHEMA_SKIP_COLS]
    # Rankings CSV: read the named column
    return df[column].dropna().str.strip().str.lower().tolist()


# ── Utilities ─────────────────────────────────────────────────────────────────

def make_filename(collection_name, username='Brent_Thompson', version=3):
    date = datetime.now().strftime('%Y%m%d')
    name = collection_name.replace(' ', '_').lower()
    return f"{name}-{username}-v{version}-{date}.csv"


def find_latest_file(pattern):
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=lambda f: os.path.getmtime(f))


# ── Zotero ────────────────────────────────────────────────────────────────────

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
    """Return {title_lower: {metadata + full_text}} for all papers in a collection."""
    items = zot.everything(zot.collection_items(collection_id))
    collection = {}
    for item in items:
        data = item['data']
        if data.get('itemType') in ('attachment', 'note') or not data.get('title'):
            continue
        collection[data['title'].lower()] = {
            'key':       item['key'],
            'title':     data['title'],
            'doi':       data.get('DOI'),
            'abstract':  data.get('abstractNote'),
            'date':      data.get('date'),
            'authors':   data.get('creators', []),
            'full_text': get_pdf_text(item['key'])
        }
    return collection


# ── AI Agent ──────────────────────────────────────────────────────────────────

def _build_context(paper: dict) -> str:
    """Assemble the text block sent to Claude for one paper."""
    parts = [f"Title: {paper['title']}"]

    if paper.get('doi'):
        doi = paper['doi']
        if not doi.startswith('http'):
            doi = f'https://doi.org/{doi}'
        parts.append(f'DOI (from metadata): {doi}')

    names = '; '.join(
        a.get('lastName', '') for a in paper.get('authors', []) if a.get('lastName')
    )
    if names:
        parts.append(f'Authors (from metadata): {names}')

    opening = (paper.get('full_text') or '')[:2000]
    if opening:
        parts.append(f'\n[Article opening — may contain affiliations]:\n{opening}')

    if paper.get('abstract'):
        parts.append(f"\n[Abstract]:\n{paper['abstract']}")

    return '\n'.join(parts)


def extract_paper_data(
    paper: dict,
    model_class: type[BaseModel],
    system_prompt: str,
    concepts: list[str],
) -> dict:
    """
    Use instructor + Claude to extract structured parameters for one paper.

    model_class is built by build_extraction_model(concepts) — instructor
    derives the tool schema from it automatically and returns a validated
    instance, which model_to_row() converts to a flat dict.
    """
    result = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{'role': 'user', 'content': _build_context(paper)}],
        response_model=model_class,
    )
    return model_to_row(result, paper['title'], concepts)


# ── Pipeline ──────────────────────────────────────────────────────────────────

def build_extraction_table(collection_dict, concepts: list[str]) -> pd.DataFrame:
    """Extract one structured row per paper using the given concept list."""
    model_class   = build_extraction_model(concepts)
    system_prompt = build_system_prompt(concepts)
    rows          = []
    papers        = list(collection_dict.values())
    total         = len(papers)

    for i, paper in enumerate(papers, 1):
        print(f'  [{i}/{total}] {paper["title"][:70]}')
        rows.append(extract_paper_data(paper, model_class, system_prompt, concepts))
        if i < total:
            time.sleep(RATE_LIMIT_DELAY)

    return pd.DataFrame(rows, columns=col_headers(concepts)) if rows else pd.DataFrame(
        columns=col_headers(concepts)
    )


# ── Workflow ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # 1. List available Zotero collections
    my_collections = get_collection_map()
    print('Available collections:')
    for name in my_collections:
        print(f'  {name}')

    # 2. Select collection
    collection_name = 'TEM-Semiconductors'   # <-- change this
    papers = get_collection_with_text(my_collections[collection_name])
    print(f'\nLoaded {len(papers)} papers from "{collection_name}"')

    # 3. Report missing PDFs
    missing = [p['title'] for p in papers.values() if not p['full_text']]
    if missing:
        print(f'\n{len(missing)} papers without PDF text:')
        for t in missing:
            print(f'  - {t}')

    # 4. Resolve concept list
    if CONCEPTS_CSV_PATH:
        print(f'\nLoading concepts from: {CONCEPTS_CSV_PATH}')
        concepts = load_concepts_from_csv(CONCEPTS_CSV_PATH, column=CONCEPTS_COLUMN)
        print(f'  {len(concepts)} concepts loaded.')
    else:
        concepts = _DEFAULT_CONCEPTS
        print(f'\nUsing default concepts: {concepts}')

    # 5. Extract structured parameters via Claude
    print(f'\nExtracting parameters with {MODEL}...')
    df = build_extraction_table(papers, concepts)
    print(f'\nExtracted {len(df)} rows  ×  {len(df.columns)} columns')

    # 6. Save CSV
    collection_slug = collection_name.replace(' ', '_').lower()
    out_dir  = os.path.join('outputs', collection_slug)
    os.makedirs(out_dir, exist_ok=True)
    prefix   = make_filename(collection_name)
    out_file = os.path.join(out_dir, f'extraction_{prefix}')
    df.to_csv(out_file, index=False)
    print(f'Saved: {out_file}')

    # 7. Preview as markdown table
    print('\n--- Extraction Results ---')
    print(df.to_markdown(index=False))
