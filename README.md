# Knowledge Workflow (`kw`)

Turn a curated Zotero library of scientific papers into **two deliverables** in one
command: a **GraphDB-ready ontology repo** (OWL 2 TTL + JSON-LD instances) and a
**cemento draw.io concept map** — grounded in MDS-Onto / CCO / BFO.

```bash
python -m kw run -c <collection_id>
```

## What it does

```
Zotero collection
   → concepts (LLM)          discover + normalize a domain concept list
   → mine (LLM + REBEL)      per-paper values + quotes, and S-P-O triples
   → consolidate             normalize relations, resolve entities, ground to MDS-Onto
   → ontology (OWL 2 TTL)    + validation gate (alignment / reasoner / OOPS!)
   → JSON-LD                 per-paper + combined all.jsonld (the GraphDB repo)
   → diagram (cemento)       concept map with embedded palettes
   → LoRA                    fine-tune on the run's final ontology terms
   → visual                  interactive graph + cumulative benchmark
```

Every run writes a self-contained `outputs/<slug>/` folder that is the GraphDB-ready
repo. REBEL, LoRA training, the reasoner/OOPS!/SHACL checks, and the visual step are all
optional and degrade to no-ops if their dependencies aren't installed, so the pipeline
runs end-to-end from a minimal install.

## Install

Requires Python ≥ 3.13 and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync                                 # core dependencies
uv pip install transformers torch       # optional: REBEL triples (Step 2)
uv pip install peft datasets accelerate # optional: LoRA training (Step 6, GPU recommended)
```

## Configure

Copy `env.example.txt` to `.env` and fill in your Zotero key and LLM endpoint. The LLM
can be any OpenAI-compatible endpoint (Anthropic, OpenAI, Groq, or a local Ollama /
LM Studio model). Minimal `.env`:

```env
ZOTERO_LIBRARY_ID=2189702
ZOTERO_LIBRARY_TYPE=group
ZOTERO_API_KEY=your_zotero_key

LLM_BASE_URL=https://api.anthropic.com/v1
LLM_API_KEY=your_llm_key
LLM_MODEL=claude-sonnet-4-6
```

`.env` is gitignored — no key is ever committed. Full variable reference:
[docs/USAGE_GUIDE.md](docs/USAGE_GUIDE.md).

## Run

```bash
# discover your collections (prints  <id>  <name>)
python -m kw --list-collections

# unsupervised — auto-generate the concept list from the corpus
python -m kw run -c <collection_id>

# supervised — provide your own concept list (skips Step 1)
python -m kw run -c <collection_id> --concepts list.csv

# only the GraphDB repo (skip diagram, LoRA, visual)
python -m kw run -c <collection_id> --no-diagram --no-lora --no-visual

# tuning dials
python -m kw run -c <id> --limit 20 --top-n 15 --min-relevance 0.4 --max-concepts 50

# run a whole queue of collections
python -m kw.batch K7LGYHKZ ABC123        # collection keys/names as args
python -m kw.batch --file collections.txt # or one key/name per line
python -m kw.batch --all                  # every collection in the library
```

## Outputs (`outputs/<slug>/`)

| File | Use |
|------|-----|
| `<slug>_onto.ttl` | OWL 2 ontology → GraphDB |
| `all.jsonld` + per-paper `*.jsonld` | instances → GraphDB bulk import |
| `rebel_triples.jsonld` + `triples_<…>.csv` | REBEL relations (as stated in text) |
| `diagram_<…>.drawio` | concept map → draw.io / cemento |
| `concepts_<…>.csv`, `schema_<…>.csv`, `enriched_<…>.csv` | intermediate data |
| `graph.html`, `graph_report.md` | interactive graph + report |
| `<slug>.log` | per-run log |

Push the folder and import `all.jsonld` + the TTL into a GraphDB repository
(`scripts/publish.py` automates this once validation passes).

## Repository layout

```
kw/              the pipeline package (see kw/README.md for the module map)
scripts/         publish.py (GraphDB load), reproduce.py
eval/            benchmark + ablation harness (run_all.py, spot_check.py, …)
shiny/           explorer.py — Shiny UI for browsing extractions
queries/         saved SPARQL queries
docs/            ARCHITECTURE, PROCESS, USAGE_GUIDE, PROJECT_BRIEF, PROJECT_INSTRUCTIONS
knowledge_base/  point-in-time analysis that drove the current refactor
_deprecated/     superseded scripts/packages, kept for reference (gitignored)
```

## Documentation

- [docs/USAGE_GUIDE.md](docs/USAGE_GUIDE.md) — run the tool, full env-var reference, troubleshooting
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design, module map, data flow
- [docs/PROCESS.md](docs/PROCESS.md) — the end-to-end process, step by step
- [kw/README.md](kw/README.md) — package-level module reference
- [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) / [docs/PROJECT_INSTRUCTIONS.md](docs/PROJECT_INSTRUCTIONS.md) — original scope + operating contract
