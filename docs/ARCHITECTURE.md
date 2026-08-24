# Architecture

This document describes the overall system design, pipeline evolution, Zotero integration, and data flow.

## System Overview

```
┌─────────────────┐
│  Zotero Group   │
│    Library      │
└────────┬────────┘
         │ API (pyzotero)
         │
         v
┌─────────────────────────────────────────────────────┐
│  Python Pipeline (uv managed, Python 3.13)          │
│                                                     │
│  1. Fetch papers (metadata + PDFs)                 │
│  2. Extract text (pypdf)                           │
│  3. Concept extraction (NLP or Claude AI)          │
│  4. Build structured output (pandas)               │
│  5. Save CSV files                                 │
└─────────────────┬───────────────────────────────────┘
                  │
                  v
         ┌────────────────┐
         │   CSV Outputs  │
         │                │
         │  - concepts    │
         │  - schema      │
         │  - rankings    │
         │  - ontology    │
         └────────────────┘
```

## Pipeline Evolution

The project has four main pipeline versions, each improving on the last:

### V1 & `zotero_bulk_read.py` (Legacy: spaCy + TF-IDF)

**Approach**: Traditional NLP stack

- **Concept extraction**: spaCy noun phrase chunking
- **Ranking**: TF-IDF across all abstracts
- **Mapping**: Match concepts back to source sentences via regex

**Outputs**:
- `ontology_<name>.csv` — paper × concept matrix with source sentences
- `frequencies_<name>.csv` — concept frequency counts

**Pros**:
- Fast (no API calls)
- Deterministic
- Works offline

**Cons**:
- Misses domain-specific multi-word terms
- TF-IDF isn't semantic (ranks frequent words, not important concepts)
- Noun chunking isn't domain-aware

**When to use**: Never (deprecated in favor of V2+). Kept for reference.

### V2 (Legacy: KeyBERT)

**Approach**: Transformer-based keyword extraction

- **Concept extraction**: KeyBERT with sentence-transformers
- **Diversity**: MMR (Maximal Marginal Relevance) to avoid redundant keyphrases
- **Ranking**: KeyBERT relevance scores + frequency counts

**Outputs**:
- `concepts_<name>.csv` — flat concept-paper pairs with scores
- `rankings_<name>.csv` — aggregated concept frequencies
- `ontology_<name>.csv` — paper × concept matrix (built from top-N ranked concepts)
- `ontology_custom_<name>.csv` — optional, built from user-supplied concept CSV

**Pros**:
- Semantic understanding (BERT embeddings)
- Better at multi-word technical terms
- Still deterministic and offline

**Cons**:
- Still not domain-aware (general-purpose BERT model)
- No structured extraction (just concept labels, not values)
- Requires downloading large models (sentence-transformers)

**When to use**: When you need offline concept discovery and don't have Claude API access.

### V3 (Current: Claude + Structured Extraction)

**Approach**: LLM-based structured data extraction with dynamic Pydantic models

- **Concept source**: Predefined schema (default concepts or loaded from CSV)
- **Extraction**: Claude with instructor library (function calling + validation)
- **Output**: One row per paper with fixed columns (universal fields + domain concepts)

**Key features**:
- **Dynamic Pydantic models**: Schema is built at runtime from concept list
- **Universal fields**: Always extracts author, institution, country, DOI, device type
- **Explicit prompting**: "Do not guess or infer" — only extract what's stated
- **Fast**: ~2-4 minutes for 50 papers

**Outputs**:
- `extraction_<name>.csv` — structured table with fixed columns

**Pros**:
- Precise extraction of specific values (not just concept labels)
- Domain-aware (Claude understands materials science)
- Consistent output structure
- Validates against Pydantic schema

**Cons**:
- Requires known schema upfront
- API costs (~$1-2 per 50 papers)
- No full-text mining (uses first 2000 chars + abstract)
- No source provenance (just extracted values)

**When to use**: When you have a stable schema and want fast, structured extraction.

### V4 (Current: Two-Stage Discovery + Full-Text Mining)

**Approach**: Multi-phase LLM pipeline with concept discovery, normalization, and full-text population

**Phase 1: Concept Discovery**
- Extract top-N concepts from each paper's abstract
- Each concept has canonical label + paper-specific term
- Collect all canonical labels across corpus

**Normalization**
- Send all canonical labels to Claude for deduplication
- Merge near-synonyms ("Voc", "open circuit voltage" → "open circuit voltage")
- Remove overly specific/vague terms
- Return 30-80 clean ontology-ready concepts

**Phase 2: Schema Population**
- Mine full PDF text (up to 80k chars per paper)
- For each normalized concept, extract:
  - Paper-specific value (exact term/number from text)
  - Source sentence (most informative quote)
- Build wide-format schema: `domain | doi | concept1 | concept2 | ...`
- Cell format: `"value | quote"`

**Outputs**:
- `concepts_<name>.csv` — Phase 1 flat table
- `schema_<name>.csv` — Phase 2 wide-format schema with source quotes
- Copy to `schemas/<collection>/` for reuse

**Pros**:
- Discovers what's actually reported in papers (not just what you expect)
- Full-text mining (not just abstracts)
- Source provenance for validation
- Reusable schemas across collections
- Can skip Phase 1 and use existing schema

**Cons**:
- Slower (~7-13 min for 50 papers)
- More expensive (~$3-8 per 50 papers)
- Normalization is opaque (Claude controls synonym merging)
- Can produce 60-80 columns (comprehensive but unwieldy)

**When to use**: When exploring new domains, building knowledge graphs, or when you need source quotes for validation.

## Pipeline Comparison Table

| Feature | V1 (spaCy) | V2 (KeyBERT) | V3 (Claude) | V4 (Claude 2-stage) |
|---------|-----------|-------------|------------|---------------------|
| Concept extraction | Noun phrases | BERT keywords | Predefined schema | Claude discovery |
| Semantic understanding | No | Yes (BERT) | Yes (Claude) | Yes (Claude) |
| Domain awareness | No | Partial | Yes | Yes |
| Structured values | No | No | Yes | Yes |
| Source provenance | Regex match | No | No | Yes (quotes) |
| Full-text mining | No | No | Partial (2k chars) | Yes (80k chars) |
| Schema discovery | No | Partial | No | Yes |
| Output format | Matrix | Flat + Matrix | Structured table | Wide schema |
| Speed (50 papers) | <1 min | ~1 min | 2-4 min | 7-13 min |
| Cost (50 papers) | Free | Free | $1-2 | $3-8 |
| API required | No | No | Yes | Yes |
| Best for | Reference only | Offline exploration | Known schema, speed | Discovery, knowledge graphs |

## Recommended Workflow

For most users:

1. **Start with V4** on a representative sample (20-50 papers) to discover the schema
2. **Review and prune** the normalized concept list
3. **Save the schema** to `schemas/<domain>/`
4. **Use V3** with that schema for all future extractions (faster, cheaper)

V4 for discovery, V3 for production.

## Zotero Integration

### Authentication

Both V3 and V4 use the Zotero API via `pyzotero`:

```python
from pyzotero import Zotero

LIBRARY_ID   = '2189702'           # Group library ID (or user ID)
LIBRARY_TYPE = 'group'             # 'group' or 'user'
API_KEY      = 'W3COg3WIiWEvORVM3CiTLwc2'  # API key (move to .env)

zot = Zotero(LIBRARY_ID, LIBRARY_TYPE, API_KEY)
```

**Security note**: The API key is currently hardcoded in V3/V4 scripts. Move it to `.env`:

```env
ZOTERO_API_KEY=W3COg3WIiWEvORVM3CiTLwc2
```

Then load with:

```python
import os
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv('ZOTERO_API_KEY')
```

### Collection Discovery

`get_collection_map()` fetches all collections in the library:

```python
def get_collection_map():
    """Return {collection_name: collection_id} for all collections."""
    return {c['data']['name']: c['key'] for c in zot.collections()}
```

This lets you list available collections and select one by name:

```python
my_collections = get_collection_map()
print('Available collections:', list(my_collections.keys()))

collection_name = 'CdTe'
collection_id   = my_collections[collection_name]
```

### PDF Text Extraction

`get_pdf_text(item_key)` downloads the PDF attachment and extracts full text:

```python
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
```

**Flow**:
1. `zot.children(item_key)` → list of attachments (PDFs, notes, etc.)
2. Filter by `contentType == 'application/pdf'`
3. `zot.file(child['key'])` → download PDF as bytes
4. `PdfReader(BytesIO(...))` → parse PDF in-memory (no temp files)
5. Extract text from all pages, concatenate

**Error handling**: If PDF is corrupt, passwordprotected, or scanned (no text layer), returns `''`. Scripts detect this and report "papers without PDF text".

### Metadata + Full-Text Bundle

`get_collection_with_text(collection_id)` fetches everything needed:

```python
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
```

**Key design decisions**:

1. **Key by `title.lower()`** — enables case-insensitive lookups
2. **Filter out attachments/notes** — only process actual papers
3. **Lazy PDF fetch** — `get_pdf_text()` is called per item (not bulk)
4. **Graceful degradation** — if PDF missing, `full_text` is `''`

**Return structure**:

```python
{
    'high-efficiency cdte solar cells': {
        'key': 'ABC123',
        'title': 'High-Efficiency CdTe Solar Cells',
        'doi': '10.1234/example',
        'abstract': 'We report...',
        'date': '2024',
        'authors': [
            {'firstName': 'John', 'lastName': 'Smith', 'creatorType': 'author'},
            ...
        ],
        'full_text': 'High-Efficiency CdTe Solar Cells\nJohn Smith et al.\n...'
    },
    ...
}
```

## Data Flow

### V3 Data Flow

```
Zotero API
   |
   v
get_collection_with_text()
   |
   v
{paper_title: {metadata, full_text}}
   |
   v
build_extraction_model(concepts) → Pydantic model
build_system_prompt(concepts)    → system prompt
   |
   v
For each paper:
   _build_context(paper) → Title, DOI, authors, first 2k chars, abstract
   |
   v
   Claude API (instructor)
   - Tool: PaperExtraction (dynamic Pydantic model)
   - Response: validated model instance
   |
   v
   model_to_row() → flat dict
   |
   v
   Append to rows list
   |
   v
pd.DataFrame(rows) → extraction_*.csv
```

### V4 Data Flow

```
Zotero API
   |
   v
get_collection_with_text()
   |
   v
{paper_title: {metadata, full_text}}
   |
   |
   |─── PHASE 1: CONCEPT EXTRACTION ───
   |
   v
For each paper:
   extract_concepts_from_abstract(abstract, top_n=25)
   |
   v
   Claude API
   - Tool: return_concepts
   - Response: [{canonical, paper_term, relevance}, ...]
   |
   v
   Collect all canonical labels across corpus
   |
   v
build_concept_table() → concepts_*.csv + raw canonical list
   |
   |
   |─── NORMALIZATION ───
   |
   v
normalize_concept_list(all_canonicals)
   |
   v
   Claude API
   - Tool: return_normalized_concepts
   - Response: [clean_concept_1, clean_concept_2, ...]
   |
   v
   30-80 normalized concepts
   |
   |
   |─── PHASE 2: SCHEMA POPULATION ───
   |
   v
For each paper:
   populate_schema_row(full_text, canonical_concepts)
   |
   v
   Claude API
   - Tool: return_schema_values
   - Response: [{canonical, value, quote}, ...]
   |
   v
   {concept: {value, quote}}
   |
   v
   Build row: domain | doi | concept1 | concept2 | ...
   Cell: "value | quote"
   |
   v
pd.DataFrame(rows) → schema_*.csv
```

## File Naming Convention

All outputs use:

```
{type}_{collection_name}-{username}-v{version}-{YYYYMMDD}.csv
```

Generated by:

```python
def make_filename(collection_name, username='Brent_Thompson', version=3):
    date = datetime.now().strftime('%Y%m%d')
    name = collection_name.replace(' ', '_').lower()
    return f"{name}-{username}-v{version}-{date}.csv"
```

Examples:
- `extraction_cdte-Brent_Thompson-v3-20260325.csv`
- `schema_perovskites-Brent_Thompson-v4-20260311.csv`
- `concepts_tem-semiconductors-Brent_Thompson-v4-20260311.csv`

This convention:
- **Groups by collection** (file system sorts by name)
- **Tracks version** (v3 vs v4)
- **Timestamps** (YYYYMMDD for sortable dates)
- **Attributes to user** (multi-user library support)

## Output Directory Structure

```
knowledge_workflow/
├── outputs/                           # All generated CSVs
│   ├── extraction_cdte-...-v3-20260325.csv
│   ├── concepts_cdte-...-v4-20260311.csv
│   ├── schema_cdte-...-v4-20260311.csv
│   └── ...
├── schemas/                           # Curated schemas for reuse
│   ├── cdte/
│   │   └── schema_cdte-...-v4-20260311.csv
│   ├── tem-semiconductors/
│   │   └── schema_tem-semiconductors-...-v4-20260311.csv
│   └── knowledge_management/
│       └── knowledge_management-...-v1-20260304.csv
└── scripts/
    ├── knowledge_workflow_V3.py
    └── knowledge_workflow_V4.py
```

**Design rationale**:

- `outputs/` — all raw outputs (chronological, not curated)
- `schemas/` — organized by domain/collection, only final schemas
  - V4 automatically copies `schema_*.csv` here after Phase 2
  - Enables reuse: `CONCEPTS_CSV_PATH = 'schemas/cdte/schema_cdte-...-v4-20260311.csv'`

## Claude AI Integration

### API Client Setup

V3 and V4 use different Anthropic client wrappers:

**V3**: `instructor` library (Pydantic-first)

```python
import anthropic
import instructor

client = instructor.from_anthropic(anthropic.Anthropic())
```

instructor patches the Anthropic client to accept `response_model=<Pydantic class>` and auto-validates responses.

**V4**: Raw `anthropic.Anthropic()` with manual tool schemas

```python
import anthropic

client = anthropic.Anthropic()  # Reads ANTHROPIC_API_KEY from env
```

V4 defines tool schemas manually (see V4_GUIDE.md for details) and parses `tool_use` blocks from responses.

### Why Different Approaches?

- **V3** needs dynamic Pydantic models → instructor is perfect for this
- **V4** uses fixed tool schemas across all papers → manual tool definitions are clearer

Both work. V3's approach is more elegant for structured extraction. V4's approach gives more control over tool schemas.

### Rate Limiting

Both scripts use `time.sleep(RATE_LIMIT_DELAY)` between API calls:

```python
RATE_LIMIT_DELAY = 0.5  # seconds

for i, paper in enumerate(papers, 1):
    # ... extract data ...
    if i < total:
        time.sleep(RATE_LIMIT_DELAY)
```

This prevents hitting Anthropic's rate limits. Default 0.5s = ~100 papers/hour, well under most tier limits.

Adjust based on your tier:
- Free tier (legacy): 1.0-2.0s
- Tier 1: 0.5s is safe
- Tier 2+: 0.1-0.2s

### Cost Estimation

Rough token usage (Claude Sonnet 4, March 2025 pricing):

**V3**:
- Input: ~500-800 tokens per paper (context block)
- Output: ~200-400 tokens per paper (structured extraction)
- Total: ~1000 tokens/paper → ~$0.01-0.02/paper

**V4 Phase 1**:
- Input: ~300-500 tokens per paper (abstract)
- Output: ~500-800 tokens per paper (25 concepts)
- Total: ~800 tokens/paper → ~$0.01/paper

**V4 Phase 2**:
- Input: ~20,000-25,000 tokens per paper (full text + concept list)
- Output: ~1,500-2,500 tokens per paper (schema values + quotes)
- Total: ~22,000 tokens/paper → ~$0.05-0.15/paper

For 50 papers:
- V3: $0.50-1.00
- V4: $3.00-8.00

## Error Handling

### Missing PDFs

Both V3 and V4 detect papers without PDF text:

```python
missing = [p['title'] for p in papers.values() if not p['full_text']]
if missing:
    print(f'{len(missing)} papers without PDF text:')
    for t in missing:
        print(f'  - {t}')
```

**V3**: Falls back to abstract-only context (if available), otherwise extracts "Not Specified" for most fields.

**V4**: Uses abstract for Phase 1 (concept extraction), falls back to abstract for Phase 2 if no full text.

### API Errors

No explicit retry logic in current implementation. If Claude API fails (rate limit, timeout, etc.), the script crashes.

**Mitigation**:
- Rate limiting prevents most errors
- Re-run the script — it will reprocess all papers (no checkpointing)

**Future improvement**: Add checkpointing to save progress after each paper.

### Invalid DOI Handling

V3 normalizes DOIs:

```python
doi_val = data.get('doi', 'Not Specified') or 'Not Specified'
if doi_val != 'Not Specified' and not doi_val.startswith('http'):
    doi_val = f'https://doi.org/{doi_val}'
```

So `10.1234/example` → `https://doi.org/10.1234/example`.

V4 doesn't normalize (keeps raw Zotero metadata).

## Security Considerations

### API Keys

**Current state**: API keys are hardcoded in scripts:

```python
API_KEY = 'W3COg3WIiWEvORVM3CiTLwc2'  # Zotero
# Anthropic key read from .env via load_dotenv()
```

**Recommendation**: Move Zotero key to `.env`:

```env
ZOTERO_API_KEY=W3COg3WIiWEvORVM3CiTLwc2
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Then:

```python
import os
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv('ZOTERO_API_KEY')
```

`.env` is already in `.gitignore`, so keys won't be committed.

### Zotero API Permissions

The Zotero API key has read-only access to the group library. It cannot:
- Modify/delete items
- Access private libraries (unless explicitly granted)
- Write to the library

Safe for public sharing if the library itself is public. But still best practice to keep it in `.env`.

## Dependencies

From `pyproject.toml`:

```toml
[project]
requires-python = ">=3.13"
dependencies = [
    "anthropic>=0.49.0",      # Claude API client
    "instructor>=1.3.0",      # Pydantic-first LLM wrapper (V3)
    "pydantic>=2.0.0",        # Data validation (V3)
    "pyzotero>=1.10.0",       # Zotero API client
    "pypdf>=6.7.5",           # PDF text extraction
    "pandas>=3.0.1",          # DataFrames
    "python-dotenv>=1.2.2",   # .env loading
    "keybert>=0.9.0",         # V2 (legacy)
    "spacy>=3.8.11",          # V1 (legacy)
    "scikit-learn>=1.8.0",    # V1/V2 (TF-IDF, legacy)
    # ... other dependencies for UI/viz (not used by core pipeline)
]
```

**Core dependencies** (used by V3/V4):
- `anthropic`, `instructor`, `pydantic` — Claude integration
- `pyzotero` — Zotero API
- `pypdf` — PDF parsing
- `pandas` — CSV output
- `python-dotenv` — environment variables

**Legacy dependencies** (V1/V2 only):
- `spacy`, `keybert`, `scikit-learn`

If you only use V3/V4, you can remove the legacy deps.

## Extensibility

### Adding New Universal Fields (V3)

Edit `_FIXED_FIELDS` in V3:

```python
_FIXED_FIELDS: dict[str, tuple] = {
    'author': (str, Field(description='...')),
    'institution': (str, Field(description='...')),
    # ... existing fields ...
    'publication_year': (int, Field(description='Year published (YYYY)')),
}
```

These will appear in all extractions, before domain-specific concepts.

### Custom Tool Schemas (V4)

Edit `_EXTRACT_TOOL`, `_NORMALIZE_TOOL`, or `_SCHEMA_TOOL` in V4 to change what data Claude returns.

Example: Add confidence scores to Phase 2:

```python
_SCHEMA_TOOL = {
    'name': 'return_schema_values',
    'input_schema': {
        # ... existing properties ...
        'confidence': {
            'type': 'number',
            'description': 'Confidence 0.0-1.0 in the extracted value'
        }
    }
}
```

Then update `populate_schema_row()` to handle the new field.

### Integrating Other Data Sources

Replace `get_collection_with_text()` with a function that reads from:
- Local PDF directory
- Mendeley/EndNote export
- PubMed API
- arXiv API

As long as you return the same dict structure, the rest of the pipeline works unchanged:

```python
{
    'paper_id': {
        'title': '...',
        'doi': '...',
        'abstract': '...',
        'full_text': '...',
    },
    ...
}
```

## Performance Tuning

### Speed vs Accuracy Tradeoffs

**V3**:
- Decrease `RATE_LIMIT_DELAY` (if your API tier allows)
- Use smaller concept lists (fewer columns = less prompt overhead)
- Switch to `claude-haiku` for cheaper/faster (but less accurate)

**V4**:
- Skip Phase 1 (`USE_CSV_CONCEPTS = True`) if you already have a schema
- Decrease `TOP_N_PER_PAPER` (fewer concepts = faster normalization + Phase 2)
- Decrease `FULL_TEXT_MAX_CHARS` (but may miss results from later pages)
- Use `claude-haiku` for Phase 1 only (keep `claude-sonnet-4` for Phase 2)

### Parallel Processing

Current implementation is serial (one paper at a time). For large collections (100+ papers), consider:

- **Thread pool** for Zotero PDF fetches (I/O-bound)
- **Async API calls** for Claude (network-bound)
- **Batch processing** with checkpointing (save progress every N papers)

Example with `asyncio` (V4 Phase 1):

```python
import asyncio

async def extract_all_concepts(papers):
    tasks = [
        extract_concepts_from_abstract_async(p['abstract'])
        for p in papers
    ]
    return await asyncio.gather(*tasks)
```

This can speed up V4 Phase 1 by 5-10x (limited by API rate limits).

## Testing Strategy

No formal tests currently. Recommended testing approach:

1. **Unit tests**: Test individual functions with mock data
   - `build_extraction_model()` → check Pydantic model structure
   - `_build_context()` → verify prompt assembly
   - `model_to_row()` → validate output format

2. **Integration tests**: Test against real Zotero collection (small sample)
   - Run V3 on 5 papers, verify CSV structure
   - Run V4 Phase 1 on 5 papers, verify concepts extraction
   - Compare V3 and V4 outputs on same papers

3. **Regression tests**: Capture baseline outputs, compare on updates
   - Save `extraction_*.csv` and `schema_*.csv` for a known collection
   - After code changes, re-run and diff outputs
   - Flag unexpected changes in extracted values

## Future Directions

### Multi-Modal Extraction

Extend to extract data from figures/tables:
- Use vision models (Claude 3.5 Sonnet with vision) to parse plots
- Extract table data from images when text parsing fails
- Link figure captions to extracted concepts

### Knowledge Graph Export

Convert V4 schema to RDF triples:

```turtle
<doi:10.1234/example>
    schema:name "High-Efficiency CdTe Solar Cells" ;
    ex:absorberComposition "CdSexTe1-x" ;
    ex:deviceEfficiency "22.1%" ;
    ex:evidenceQuote "Champion device achieved 22.1% power conversion efficiency" .
```

### Incremental Updates

Add checkpointing to V3/V4:
- Save state after each paper
- On restart, skip already-processed papers
- Append new rows to existing CSV

### Interactive Schema Builder

Web UI (Shiny app) to:
- Preview extracted concepts from V4 Phase 1
- Manually edit/merge/delete concepts before Phase 2
- Review extractions with source quotes inline

`scripts/app.py` exists but is not documented — likely an early prototype.

## Related Documentation

- [README.md](../README.md) — Quick start, usage examples
- [V3_GUIDE.md](V3_GUIDE.md) — V3 detailed documentation
- [V4_GUIDE.md](V4_GUIDE.md) — V4 detailed documentation
