# V3 Guide: Structured Extraction with Dynamic Pydantic Models

V3 is a single-stage extraction pipeline. You define a schema (either manually via default concepts or by pointing at a CSV), and Claude extracts those specific data points from each paper. Output is one row per paper with fixed columns.

## How It Works

1. **Build Pydantic model dynamically** from your concept list
2. **Read papers** from Zotero collection (metadata + PDF text)
3. **Extract structured data** using Claude with instructor library
4. **Validate & output** to CSV

The Pydantic model defines what Claude should extract. The `instructor` library turns that model into a tool schema for Claude's function-calling API and validates the response against your model.

## Key Features

### Fixed Universal Fields

Every extraction includes these six fields (always first):

- **Title** — Paper title from Zotero metadata
- **Author** — Last name of first author (extracted from paper text or metadata)
- **Institution** — First author's institution (extracted from paper text)
- **Country** — Country of that institution (extracted from paper text)
- **DOI** — Full DOI URL (`https://doi.org/...`)
- **Device Type** — Enum: `photovoltaic cell`, `light emitting diode`, `photodetector`, `Not Specified`

These are hardcoded in `_FIXED_FIELDS` and apply to any domain.

### Domain-Specific Concepts

After the universal fields, V3 adds one column per concept from your schema. Concepts are either:

- **Default concepts** (`_DEFAULT_CONCEPTS` in the script):
  ```python
  _DEFAULT_CONCEPTS = [
      'absorber composition',
      'absorber crystallinity',
      'absorber bandgap type',
      'absorber bandgap eV',
  ]
  ```

- **Loaded from CSV** (`CONCEPTS_CSV_PATH`):
  - V4 schema CSV: column headers after `domain`/`doi` become concepts
  - Rankings CSV: values in the `concept` column (or `CONCEPTS_COLUMN` if different)

### Dynamic Model Building

The `build_extraction_model(concepts)` function uses `pydantic.create_model()` to construct a Pydantic model at runtime:

```python
def build_extraction_model(concepts: list[str]) -> type[BaseModel]:
    fields: dict[str, Any] = dict(_FIXED_FIELDS)
    for concept in concepts:
        slug = _slug(concept)  # "absorber bandgap eV" → "absorber_bandgap_ev"
        fields[slug] = (
            str,
            Field(
                description=(
                    f'For "{concept}": the exact term, value, or measurement '
                    f'this paper reports. Output "Not Specified" if not stated.'
                )
            )
        )
    return create_model('PaperExtraction', **fields)
```

This model becomes the `response_model` for instructor, which auto-generates the Claude tool schema and validates responses.

### Context Assembly

For each paper, V3 sends Claude a context block built from:

1. **Title** (from Zotero metadata)
2. **DOI** (from metadata, if available)
3. **Authors** (last names from metadata)
4. **Opening 2000 characters of PDF text** (usually contains affiliations)
5. **Abstract** (from Zotero metadata)

Limiting the PDF excerpt to 2000 chars keeps token usage low while capturing institution info that's usually in the first page.

### System Prompt

Dynamically built by `build_system_prompt(concepts)`. Key instructions:

- Act as an expert materials scientist
- **Do not infer, guess, or calculate** — output "Not Specified" if value is absent
- Extract universal fields (author, institution, country, DOI, device type)
- Extract domain-specific concepts (one per concept in the list)

Concept descriptions are injected into the prompt so Claude knows what to look for.

## Configuration

Edit these constants at the top of `scripts/knowledge_workflow_V3.py`:

```python
LIBRARY_ID        = '2189702'           # Zotero library ID
LIBRARY_TYPE      = 'group'             # 'user' or 'group'
API_KEY           = ''                  # Now reads from .env
MODEL             = 'claude-sonnet-4-6' # Anthropic model name
RATE_LIMIT_DELAY  = 0.5                 # Seconds between API calls

# Concept source (leave blank to use _DEFAULT_CONCEPTS)
CONCEPTS_CSV_PATH = ''                  # Path to CSV
CONCEPTS_COLUMN   = 'concept'           # Column to read
```

### Using Default Concepts

Leave `CONCEPTS_CSV_PATH = ''`. The script will use:

```python
_DEFAULT_CONCEPTS = [
    'absorber composition',
    'absorber crystallinity',
    'absorber bandgap type',
    'absorber bandgap eV',
]
```

Output columns: `Title | Author | Institution | Country | DOI | Device Type | absorber composition | absorber crystallinity | absorber bandgap type | absorber bandgap eV`

### Loading Concepts from a V4 Schema CSV

Point `CONCEPTS_CSV_PATH` at a V4 schema file:

```python
CONCEPTS_CSV_PATH = 'schemas/cdte/schema_cdte-Brent_Thompson-v4-20260311.csv'
CONCEPTS_COLUMN   = 'concept'  # Not used for V4 schema CSVs
```

V4 schema CSVs have columns like `domain | doi | concept1 | concept2 | ...`. V3 ignores `domain`, `doi`, `title`, `paper` and treats everything else as concept labels.

### Loading Concepts from a Rankings CSV

If you have a `rankings_*.csv` from an older run:

```python
CONCEPTS_CSV_PATH = 'outputs/rankings_perovskites-Brent_Thompson-v1-20260305.csv'
CONCEPTS_COLUMN   = 'concept'  # Column name in that CSV
```

V3 reads the `concept` column and uses those as your schema.

## Running V3

1. **Edit the script**:
   ```python
   collection_name = 'TEM-Semiconductors'  # Change this
   ```

2. **Run**:
   ```bash
   uv run python scripts/knowledge_workflow_V3.py
   ```

3. **Output**:
   ```
   Available collections:
     CdTe
     TEM-Semiconductors
     Perovskites

   Loaded 23 papers from "TEM-Semiconductors"

   3 papers without PDF text:
     - Some Title Without PDF

   Using default concepts: ['absorber composition', 'absorber crystallinity', ...]

   Extracting parameters with claude-sonnet-4-6...
     [1/23] High-resolution transmission electron microscopy of...
     [2/23] Atomic-scale imaging of...
     ...

   Extracted 23 rows × 10 columns
   Saved: extraction_tem-semiconductors-Brent_Thompson-v3-20260325.csv

   --- Extraction Results ---
   <markdown table preview>
   ```

## Output Format

CSV with one row per paper, columns in this order:

1. **Title** — from Zotero metadata
2. **Author** — last name of first author (extracted)
3. **Institution** — first author's institution (extracted)
4. **Country** — country of institution (extracted)
5. **DOI** — full URL (extracted or from metadata)
6. **Device Type** — enum value or "Not Specified"
7. **Concept columns** — one per concept in your schema

### Example Row

| Title | Author | Institution | Country | DOI | Device Type | absorber composition | absorber bandgap eV | absorber crystallinity |
|-------|--------|-------------|---------|-----|-------------|---------------------|---------------------|----------------------|
| CdTe solar cells with chlorine passivation | Smith | MIT | USA | https://doi.org/10.xxxx | photovoltaic cell | CdSexTe1-x | 1.45 | polycrystalline |

### Handling Missing Data

If Claude can't find a value in the paper text:
- Universal fields: `"Not Specified"`
- Device Type: `"Not Specified"` (since it's an enum with that option)
- Concept columns: `"Not Specified"`

**Important**: V3 never guesses or infers. The system prompt explicitly forbids it. If the paper doesn't state a value, you get "Not Specified".

## Code Structure

### Main Functions

**`build_extraction_model(concepts: list[str]) -> type[BaseModel]`**

Dynamically creates a Pydantic model with universal fields + one field per concept.

**`build_system_prompt(concepts: list[str]) -> str`**

Builds the system prompt by injecting concept descriptions.

**`model_to_row(instance: BaseModel, title: str, concepts: list[str]) -> dict`**

Converts a validated Pydantic model instance to a flat dict for DataFrame.

**`extract_paper_data(paper, model_class, system_prompt, concepts) -> dict`**

Calls Claude with instructor to get structured extraction for one paper:

```python
result = client.messages.create(
    model=MODEL,
    max_tokens=2048,
    system=system_prompt,
    messages=[{'role': 'user', 'content': _build_context(paper)}],
    response_model=model_class,  # instructor validates against this
)
return model_to_row(result, paper['title'], concepts)
```

**`build_extraction_table(collection_dict, concepts) -> pd.DataFrame`**

Loops over all papers, extracts data, returns DataFrame.

### Zotero Integration

**`get_collection_map()`**

Returns `{collection_name: collection_id}` for all collections in the library.

**`get_pdf_text(item_key)`**

Downloads the PDF attachment from Zotero and extracts full text with pypdf.

**`get_collection_with_text(collection_id)`**

Returns a dict of papers with metadata + full text:

```python
{
    'paper title': {
        'key': 'ABC123',
        'title': 'Paper Title',
        'doi': '10.xxxx',
        'abstract': '...',
        'date': '2024',
        'authors': [...],
        'full_text': '...'  # Full PDF text
    },
    ...
}
```

## Performance

For a collection of 50 papers with 10 concepts:

- **Time**: ~2-4 minutes (depends on `RATE_LIMIT_DELAY`)
- **Cost**: ~$1-2 (Claude Sonnet 4 pricing as of March 2025)
- **Token usage**: ~1000-1500 tokens per paper (input + output)

Rate limiting prevents hitting API tier limits. With `RATE_LIMIT_DELAY = 0.5`, you'll process ~100 papers/hour.

## Limitations

1. **No full-text mining**: V3 only sends the first 2000 chars + abstract to Claude. For deep extraction from results sections, use V4.

2. **Schema must be known upfront**: You can't discover new concepts with V3. If you add a concept to your schema later, you need to re-run the entire collection.

3. **No source provenance**: Output is just the extracted value, not the source sentence. If you need "value | source quote" format, use V4.

4. **Enum validation only for device_type**: Other fields are strings. If you want enum validation for concepts, you'd need to modify `build_extraction_model()`.

## When to Use V3

V3 is the right choice when:

- You have a stable schema (from a V4 run or domain knowledge)
- You're adding new papers to an existing dataset
- Speed matters more than discovery
- You don't need source sentences for validation
- You're building a production pipeline with predictable output

For exploratory work or schema discovery, use V4.

## Tips

### Reuse V4 Schemas in V3

The most efficient workflow:

1. Run V4 on a representative sample (20-50 papers)
2. Review the `schema_*.csv` output
3. Optionally prune/edit the concept columns
4. Point V3 at that schema file via `CONCEPTS_CSV_PATH`
5. Use V3 for all future extractions on new papers in that domain

This gives you V4's discovery power and V3's speed.

### Custom Default Concepts

Edit `_DEFAULT_CONCEPTS` directly in the script if you're working in a specific domain and don't want to manage external CSVs:

```python
_DEFAULT_CONCEPTS = [
    'absorber composition',
    'absorber thickness nm',
    'device efficiency percent',
    'open circuit voltage v',
    'short circuit current ma/cm2',
    'fill factor percent',
]
```

### Handling Multi-Value Concepts

If a paper reports multiple values for a concept (e.g., "device efficiency: 18.5% (average), 22.1% (champion)"), Claude will typically return one of them or concatenate. The Pydantic model is `str`, so it's up to Claude's prompt interpretation.

If you need structured multi-value extraction, you'd need to change the field type to `list[str]` and update the prompt.

### DOI Normalization

V3 automatically prefixes DOIs with `https://doi.org/` if they don't already start with `http`:

```python
doi_val = data.get('doi', 'Not Specified') or 'Not Specified'
if doi_val != 'Not Specified' and not doi_val.startswith('http'):
    doi_val = f'https://doi.org/{doi_val}'
```

So both `10.1234/example` and `https://doi.org/10.1234/example` end up as the full URL.

## Debugging

### Check What Claude Sees

Print the context block being sent to Claude:

```python
# In extract_paper_data(), before the API call:
context = _build_context(paper)
print(context)
```

### Check the Pydantic Model

Print the dynamically built model to see field names and descriptions:

```python
model_class = build_extraction_model(concepts)
print(model_class.model_json_schema())
```

### Check the System Prompt

```python
system_prompt = build_system_prompt(concepts)
print(system_prompt)
```

### Validate Against a Single Paper

Comment out the loop in `build_extraction_table()` and test on one paper:

```python
papers = list(collection_dict.values())
single_paper = papers[0]
row = extract_paper_data(single_paper, model_class, system_prompt, concepts)
print(row)
```

This helps isolate whether issues are in the extraction logic or the loop/DataFrame construction.
