# V4 Guide: Two-Stage Concept Discovery & Schema Population

V4 is a two-phase extraction pipeline that discovers domain-specific concepts from paper abstracts, normalizes them into a clean schema, then mines full PDF text to populate that schema with paper-specific values and source sentences.

## When to Use V4

Use V4 when:

- You're exploring a new research domain and don't know what concepts matter
- You want to discover what's actually reported in papers (not just what you think should be there)
- You need source sentences for validation or knowledge graph triples
- You're building a reusable schema to apply across multiple collections
- You care more about discovery than speed

If you already have a schema, use V3 instead — it's faster.

## How It Works

### Phase 1: Concept Extraction

For each paper in the collection:

1. **Extract concepts from abstract** using Claude
2. For each concept, capture:
   - `canonical` — ontology-ready label (e.g., "absorber material")
   - `paper_term` — paper-specific term (e.g., "CdSexTe1-x")
   - `relevance` — score 0.0-1.0

3. Return top N concepts per paper (default: 25)

Output: `concepts_*.csv` (flat table) + list of all raw canonical labels.

### Normalization Pass

After extracting concepts from all papers:

1. **Collect all unique canonical labels** across the corpus
2. **Send to Claude for deduplication**:
   - Merge near-synonyms ("open circuit voltage", "Voc", "open-circuit voltage" → "open circuit voltage")
   - Remove overly specific terms ("CdSeTe" — that's a value, not a concept)
   - Remove overly vague terms ("cell", "material")
   - Return 30-80 high-quality, reusable concept labels

Output: Normalized concept list (used as column headers in Phase 2).

### Phase 2: Schema Population

For each paper in the collection:

1. **Load full PDF text** (up to 80,000 chars by default)
2. **For each normalized concept**, ask Claude to extract:
   - `value` — the exact term/number this paper uses
   - `quote` — the most informative source sentence from the text
3. **Build wide-format row**: `domain | doi | concept1 | concept2 | ...`
4. **Cell format**: `"paper-specific value | source sentence"` (or empty if not found)

Output: `schema_*.csv` (wide format, one row per paper, one column per concept).

## Configuration

Edit these constants at the top of `scripts/knowledge_workflow_V4.py`:

```python
LIBRARY_ID        = '2189702'           # Zotero library ID
LIBRARY_TYPE      = 'group'             # 'user' or 'group'
API_KEY           = ''                  # Reads from .env
MODEL             = 'claude-sonnet-4-6' # Anthropic model
RATE_LIMIT_DELAY  = 0.5                 # Seconds between API calls

# Phase 1 settings
USE_CSV_CONCEPTS  = False               # Skip Phase 1 if True
CONCEPTS_CSV_PATH = ''                  # Path to existing rankings/schema CSV
CONCEPTS_COLUMN   = 'concept'           # Column to read from that CSV
TOP_N_PER_PAPER   = 25                  # Concepts extracted per paper

# Phase 2 settings
FULL_TEXT_MAX_CHARS = 80_000            # Max chars sent to Claude per paper
```

### Fresh Concept Discovery (Default)

Leave `USE_CSV_CONCEPTS = False`. V4 will run both phases:

- Phase 1: Extract 25 concepts per paper from abstracts
- Normalization: Deduplicate and merge near-synonyms
- Phase 2: Mine full text for all normalized concepts

### Reuse Existing Schema

Skip Phase 1 and use a known concept list:

```python
USE_CSV_CONCEPTS  = True
CONCEPTS_CSV_PATH = 'schemas/cdte/schema_cdte-Brent_Thompson-v4-20260311.csv'
```

V4 will load the concept columns from that CSV and jump to Phase 2 (schema population).

This is useful when:
- You've already run V4 on one collection and want to apply the same schema to a different collection
- You have a manually curated concept list and want V4's full-text mining + source quotes

### Adjusting Concept Count

`TOP_N_PER_PAPER = 25` means Claude extracts 25 concepts from each paper's abstract. For a 50-paper collection, you'll get up to 1,250 raw concepts (with duplicates). The normalization step reduces this to 30-80 unique concepts.

If you want fewer columns in the final schema:
- Lower `TOP_N_PER_PAPER` to 15-20
- Or manually prune the normalized concept list before Phase 2

If you want more comprehensive coverage:
- Increase to 30-40 (but normalization will still cap around 80)

### Full-Text Character Limit

`FULL_TEXT_MAX_CHARS = 80_000` limits how much of each PDF is sent to Claude. This is roughly:

- 80,000 chars ≈ 20,000 tokens
- Safe within Claude Sonnet 4's 200k context window
- Covers most papers entirely (typical paper is 30-60k chars)

You can increase this if you have very long review papers, but watch your API costs (longer input = higher cost).

## Running V4

1. **Edit the script**:
   ```python
   collection_name = 'CdTe'  # Change this
   ```

2. **Run**:
   ```bash
   uv run python scripts/knowledge_workflow_V4.py
   ```

3. **Output**:
   ```
   Available collections:
     CdTe
     TEM-Semiconductors

   Loaded 23 papers from "CdTe"

   3 papers without PDF (will use abstract for Phase 2):
     - Some Title

   [Phase 1] Extracting concepts (25/paper) with claude-sonnet-4-6...
     [1/23] Extracting: High-efficiency CdSeTe solar cells...
     [2/23] Extracting: Chlorine passivation mechanisms...
     ...
     575 concept-paper pairs extracted.
     87 unique raw canonical labels.

   [Normalization] Normalizing concept list with claude-sonnet-4-6...
     Normalized to 42 canonical concepts:
       - absorber composition
       - device efficiency
       - open circuit voltage
       - short circuit current
       - fill factor
       - absorber thickness
       - chlorine concentration
       - passivation method
       - carrier lifetime
       - bandgap energy
       ... and 32 more

   [Phase 2] Building schema CSV (42 columns) with claude-sonnet-4-6...
     (Mining full PDF text per paper — this may take a few minutes)
     [1/23] Schema row: High-efficiency CdSeTe solar cells...
     [2/23] Schema row: Chlorine passivation mechanisms...
     ...

   Saved: concepts_cdte-Brent_Thompson-v4-20260325.csv
   Saved: schema_cdte-Brent_Thompson-v4-20260325.csv
   Saved: schemas/cdte/schema_cdte-Brent_Thompson-v4-20260325.csv

   --- Schema CSV preview ---
   Shape: 23 rows × 44 columns
   <preview table>

   All concept columns (42):
     absorber composition
     device efficiency
     ...
   ```

## Output Files

### Phase 1: `concepts_<collection>-<user>-v4-<date>.csv`

Flat table with one row per concept-paper pair:

| paper | doi | canonical | paper_term | relevance |
|-------|-----|-----------|------------|-----------|
| High-efficiency CdSeTe solar cells | 10.xxxx | absorber composition | CdSexTe1-x | 0.92 |
| High-efficiency CdSeTe solar cells | 10.xxxx | device efficiency | 22.1% | 0.88 |
| High-efficiency CdSeTe solar cells | 10.xxxx | chlorine concentration | 2 × 10^16 cm^-3 | 0.85 |
| Chlorine passivation mechanisms | 10.yyyy | passivation method | chlorine treatment | 0.91 |

**Use this to:**
- See which concepts Claude extracted before normalization
- Check concept-to-paper mappings
- Debug why certain papers aren't contributing to the schema

### Phase 2: `schema_<collection>-<user>-v4-<date>.csv`

Wide format, one row per paper, one column per normalized concept:

| domain | doi | absorber composition | device efficiency | open circuit voltage |
|--------|-----|---------------------|-------------------|---------------------|
| cdte | 10.xxxx | CdSexTe1-x \| "The absorber layer consisted of CdSexTe1-x with x=0.3" | 22.1% \| "Champion device achieved 22.1% power conversion efficiency" | 0.87 V \| "Open-circuit voltage (Voc) of 0.87 V was measured" |
| cdte | 10.yyyy | CdTe \| "Standard CdTe absorber was used" | \| | 0.82 V \| "Voc = 0.82 V for the baseline device" |

**Cell format:** `value | quote`

- If both value and quote found: `"value | quote"`
- If only value: `"value"`
- If only quote: `"quote"`
- If neither: `""` (empty string)

**Use this to:**
- Populate a knowledge graph with triples: `(paper DOI, concept, value)` + provenance from quote
- Validate extractions by reading the source sentence
- Build training data for domain-specific NLP models
- Compare parameter reporting across papers

### Copy: `schemas/<collection>/schema_<collection>-<user>-v4-<date>.csv`

The schema CSV is automatically copied to `schemas/<collection>/` so you can reuse it later:

```python
USE_CSV_CONCEPTS  = True
CONCEPTS_CSV_PATH = 'schemas/cdte/schema_cdte-Brent_Thompson-v4-20260325.csv'
```

This lets you apply the same schema to new collections or re-run with updated papers.

## Tool Schemas

V4 uses three Claude tool schemas to structure responses:

### 1. `return_concepts` (Phase 1)

```json
{
  "name": "return_concepts",
  "input_schema": {
    "type": "object",
    "properties": {
      "concepts": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "canonical": "string",     // Ontology-ready label
            "paper_term": "string",     // Paper-specific term
            "relevance": "number"       // 0.0-1.0
          }
        }
      }
    }
  }
}
```

### 2. `return_normalized_concepts` (Normalization)

```json
{
  "name": "return_normalized_concepts",
  "input_schema": {
    "type": "object",
    "properties": {
      "concepts": {
        "type": "array",
        "items": {
          "type": "string"  // Clean canonical label
        }
      }
    }
  }
}
```

### 3. `return_schema_values` (Phase 2)

```json
{
  "name": "return_schema_values",
  "input_schema": {
    "type": "object",
    "properties": {
      "values": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "canonical": "string",  // Concept being answered
            "value": "string",      // Paper-specific value (or empty)
            "quote": "string"       // Source sentence (or empty)
          }
        }
      }
    }
  }
}
```

## System Prompts

### Phase 1: `_EXTRACT_SYSTEM`

```
You are a scientific literature analyst and ontologist specialising in
materials science and solar cell research.

Given a paper abstract, extract domain-specific concepts in TWO forms:

1. canonical — a general ontology-ready label (lowercase, 1-4 words) that
   could serve as a reusable column header across many papers in the field.
   Good examples: "absorber material", "device efficiency", "dopant species"
   Bad examples: "CdSeTe" (too specific), "22.1%" (a value)

2. paper_term — the specific term, compound, percentage, or phrase this
   particular paper uses for that concept.

Focus on technical properties, materials, methods, and performance metrics.
Score each 0.0–1.0 by centrality to the paper's contribution.
```

### Normalization: `_NORMALIZE_SYSTEM`

```
You are a knowledge-graph ontologist.

You will receive a list of candidate concept labels extracted by AI from
multiple scientific papers in the solar cell materials domain.

Your task: return a clean, deduplicated, normalized set of ontology-ready
labels suitable as column headers in a knowledge-graph schema.

Rules:
- Merge near-synonyms into one canonical form
- Keep labels lowercase, 1-4 words, general and reusable
- Remove labels that are too vague ("cell"), too specific ("CdSeTe"), or duplicates
- Aim for 30–80 high-quality, distinct concepts
- Order them roughly by domain importance
```

### Phase 2: `_SCHEMA_SYSTEM`

```
You are a precise scientific data extractor.

You will be given the full text of a scientific paper and a list of
ontology concept labels.

For EACH concept, find and return:
  value  — the exact term, number, or very short phrase this paper uses
           for that concept (use the paper's own wording).
           If not addressed in this paper, use an empty string.

  quote  — the single most informative sentence from the text that
           establishes or describes this concept. Prefer results sections,
           abstracts, or conclusion sentences. If not found, use empty string.

Be precise. Do not paraphrase. Do not invent values not in the text.
```

## Performance

For a 50-paper collection:

**Phase 1 (concept extraction):**
- Time: ~2-3 minutes (with 0.5s rate limit)
- Cost: ~$0.50-1.00
- Output: ~1,000-1,500 concept-paper pairs → 30-80 normalized concepts

**Phase 2 (schema population):**
- Time: ~5-10 minutes (full-text mining is slower)
- Cost: ~$2.50-7.50 (depends on paper length)
- Output: Wide schema CSV

**Total for 50 papers:**
- Time: ~7-13 minutes
- Cost: ~$3-8

If you skip Phase 1 (reuse existing schema), you save the first ~$1 and 2-3 minutes.

## Limitations

1. **Normalization is opaque**: You don't control exactly how Claude merges synonyms. If you need precise control, skip normalization and manually edit the concept list.

2. **No multi-value extraction**: Each cell is `"value | quote"`. If a paper reports multiple values for a concept (e.g., baseline vs champion efficiency), Claude picks one. For structured multi-value extraction, you'd need to modify the tool schema.

3. **Quote selection is subjective**: Claude chooses the "most informative" sentence. Sometimes you might disagree. But having the quote lets you validate the extraction.

4. **80k char limit on full text**: Very long papers (100+ pages) get truncated. Results sections at the end might be missed. Increase `FULL_TEXT_MAX_CHARS` if needed (but watch API costs).

5. **Column explosion**: Large diverse collections can produce 60-80 concept columns. This is useful for comprehensive extraction but unwieldy for manual review. Prune concepts after normalization if needed.

## Tips

### Review Normalized Concepts Before Phase 2

After the normalization step prints the concept list, you can:

1. **Stop the script** (Ctrl+C)
2. **Manually edit the normalized list** in the code
3. **Re-run with `USE_CSV_CONCEPTS = True`**, pointing at your edited list

This gives you control over the final schema without re-running Phase 1.

### Use V4 to Build, V3 to Scale

The most efficient workflow:

1. Run V4 on a representative subset (20-50 papers) to discover the schema
2. Review the `schema_*.csv` output and prune columns if needed
3. Save the final schema to `schemas/<domain>/`
4. Use V3 with that schema for all future extractions (faster, cheaper)

V4 gives you discovery. V3 gives you speed. Use both.

### Validate Extractions

The `quote` field is your validation. If a value looks wrong, read the source sentence. Common issues:

- Claude extracted from the wrong section (e.g., literature review instead of results)
- Concept is ambiguous (e.g., "device efficiency" could be internal quantum efficiency or power conversion efficiency)
- Value is a typo in the paper

Having the quote lets you catch these without re-reading entire papers.

### Cross-Collection Schemas

V4 can apply the same schema to multiple collections:

1. Run V4 on Collection A → get `schema_A.csv`
2. Set `USE_CSV_CONCEPTS = True`, `CONCEPTS_CSV_PATH = 'schema_A.csv'`
3. Change `collection_name` to Collection B
4. Re-run V4 → get `schema_B.csv` with the same columns

Now you can merge `schema_A.csv` and `schema_B.csv` for cross-corpus analysis.

### Debugging Empty Cells

If many cells are empty (`""`), it means:

- The concept isn't reported in those papers (expected for diverse collections)
- Claude couldn't find the concept in the 80k char excerpt (try increasing `FULL_TEXT_MAX_CHARS`)
- The concept label is too vague or specific (check normalization)

Print the full text excerpt sent to Claude to see what it's working with:

```python
# In populate_schema_row(), before the API call:
print(text_excerpt)
```

## Code Structure

### Main Functions

**`extract_concepts_from_abstract(abstract, top_n=25)`**

Phase 1. Sends abstract to Claude with `return_concepts` tool. Returns list of `{canonical, paper_term, relevance}`.

**`build_concept_table(collection_dict, top_n=25)`**

Loops over all papers, runs `extract_concepts_from_abstract()`, returns DataFrame + raw canonical list.

**`normalize_concept_list(all_canonicals)`**

Normalization pass. Sends all unique canonical labels to Claude with `return_normalized_concepts` tool. Returns cleaned list.

**`populate_schema_row(full_text, canonical_concepts)`**

Phase 2, per paper. Sends full text + concept list to Claude with `return_schema_values` tool. Returns `{canonical: {value, quote}}`.

**`build_schema_csv(collection_dict, canonical_concepts, domain)`**

Loops over all papers, runs `populate_schema_row()`, builds wide DataFrame with `domain | doi | concept1 | concept2 | ...`.

### Zotero Integration

Same as V3 — see V3_GUIDE.md for details.

## Example: Building a Materials Database

Scenario: You're building a knowledge graph of solar cell materials and want to extract structured data from 200 papers across 3 sub-domains (CdTe, perovskites, organic).

**Step 1: Discover schema from each sub-domain**

Run V4 on each collection:

```python
# CdTe
collection_name = 'CdTe'
USE_CSV_CONCEPTS = False
# Output: schemas/cdte/schema_cdte-v4-20260325.csv (42 columns)

# Perovskites
collection_name = 'Perovskites'
USE_CSV_CONCEPTS = False
# Output: schemas/perovskites/schema_perovskites-v4-20260325.csv (38 columns)

# Organic
collection_name = 'Organic'
USE_CSV_CONCEPTS = False
# Output: schemas/organic/schema_organic-v4-20260325.csv (45 columns)
```

**Step 2: Merge schemas**

Manually combine the three concept lists into one master schema, removing duplicates and merging synonyms. Save to `schemas/master_solar_cells.csv`.

**Step 3: Re-run V4 on all collections with master schema**

```python
USE_CSV_CONCEPTS  = True
CONCEPTS_CSV_PATH = 'schemas/master_solar_cells.csv'

# Re-run on each collection
# Output: schema_cdte-v4-20260326.csv (now with master schema)
#         schema_perovskites-v4-20260326.csv
#         schema_organic-v4-20260326.csv
```

**Step 4: Concatenate into single table**

```python
import pandas as pd

df_cdte = pd.read_csv('schema_cdte-v4-20260326.csv')
df_pv   = pd.read_csv('schema_perovskites-v4-20260326.csv')
df_org  = pd.read_csv('schema_organic-v4-20260326.csv')

df_all = pd.concat([df_cdte, df_pv, df_org], ignore_index=True)
df_all.to_csv('solar_cells_master_database.csv', index=False)
```

Now you have a unified database with 200 papers, domain labels, and 60+ concept columns with source quotes.
