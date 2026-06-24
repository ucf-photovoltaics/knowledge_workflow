# Usage Guide — Knowledge Workflow (`kw`)

How to run the tool end-to-end and get the two deliverables: a **GraphDB-ready repo**
(ontology + JSON-LD) and a **cemento draw.io diagram**. Tested target: a Zotero library
+ a local 7B Llama model.

---

## 1. Prerequisites
- Python ≥ 3.13 and [`uv`](https://docs.astral.sh/uv/).
- A Zotero account + API key (read access to your group/user library).
- An LLM endpoint. This guide assumes a **local 7B Llama** via an OpenAI-compatible
  server (Ollama or LM Studio).

```bash
cd knowledge_workflow
uv sync                       # install dependencies from pyproject
# optional, only if you want REBEL triples:
uv pip install transformers torch
```

---

## 2. Configure `.env`
Create `.env` in the project root (it's gitignored):

```env
# --- Zotero ---
ZOTERO_LIBRARY_ID=2189702
ZOTERO_LIBRARY_TYPE=group          # or "user"
ZOTERO_API_KEY=your_zotero_key

# --- LLM provider (local 7B Llama via Ollama) ---
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama                 # any non-empty string for local servers
LLM_MODEL=llama3.1:8b              # your pulled 7–8B tool-capable model

# --- tuning for small local models (recommended) ---
TOP_N_PER_PAPER=15                 # fewer concepts per abstract = more reliable
BATCH_SIZE=20                      # smaller tagging batches
RATE_LIMIT_DELAY=0.0               # local model: no rate limit needed
```

### Local 7B Llama notes
- **Ollama:** `ollama serve`, then `ollama pull llama3.1:8b`. Base URL
  `http://localhost:11434/v1`. **LM Studio:** start its server → base URL
  `http://localhost:1234/v1`, model = the loaded model's name.
- **Tool/function calling is required.** The pipeline uses structured (typed) output,
  so pick a model that supports tools (Llama 3.1 instruct variants do via Ollama). If
  extraction errors out with schema/validation failures, your model/endpoint likely
  doesn't support function calling well — try a tool-capable model, or set
  `FORCE_TOOL_CHOICE=false` in `.env`.
- 7B models are weaker at strict JSON. The tagger uses fixed-choice enums (robust);
  the concept/value extractors are free-form (less robust) — keeping `TOP_N_PER_PAPER`
  low and rerunning failed papers helps.

---

## 3. Run

```bash
# discover your collections (prints  <id>  <name>)
uv run python -m kw --list-collections

# UNSUPERVISED — auto-generate the concept list from abstracts
uv run python -m kw run -c <collection_id>

# SUPERVISED — provide your own concept list (skips Step 1)
uv run python -m kw run -c <collection_id> --concepts schemas/<domain>.csv

# only the GraphDB repo (skip diagram + LoRA)
uv run python -m kw run -c <collection_id> --no-diagram --no-lora
```

A run prints each step and finishes with the output paths.

---

## 4. What you get  (`outputs/<slug>/`)
| File | Use |
|------|-----|
| `<slug>_onto.ttl` | OWL 2 ontology → **GraphDB** |
| `all.jsonld` + per-paper `*.jsonld` | instances → **GraphDB** bulk import |
| `rebel_triples.jsonld` + `triples_<…>.csv` | REBEL relations (as stated in text) → **GraphDB** |
| `diagram_<…>.drawio` | concept map → **draw.io / cemento** |
| `concepts_<…>.csv`, `schema_<…>.csv`, `enriched_<…>.csv` | intermediate data |
| `lora_adapters/run-<…>/` | LoRA dataset (`lora_dataset.jsonl`) + adapter + manifest |

The whole `outputs/<slug>/` folder is the GraphDB-ready repo.

---

## 5. Push the repo + import into GraphDB sandbox
```bash
# commit + push the artifacts, then load into GraphDB (gated on validation passing)
export GRAPHDB_URL=http://localhost:7200
export GRAPHDB_REPO=your_sandbox_repo
uv run python scripts/publish.py outputs/<slug>/<slug>_onto.ttl outputs/<slug>/all.jsonld
```
Or manually in the GraphDB Workbench:
1. Create/select a repository (your sandbox).
2. **Import → RDF → Upload RDF files** → choose `all.jsonld` (format: JSON-LD) → Import.
   (Or **Import → Get RDF data from a URL** → paste the raw GitHub URL of `all.jsonld`.)
3. Load `<slug>_onto.ttl` the same way to bring in the class/property schema.
4. Explore with SPARQL or the visual graph.

---

## 6. Open the diagram in draw.io / cemento
1. Open `diagram_<…>.drawio` in draw.io (desktop or app.diagrams.net).
2. The file has multiple pages: **Concepts** (the map), **MDS-Onto Library**, and
   **Cemento Templates** — the palettes are embedded, so no manual "Load Library" step.
3. In cemento, use the embedded template shapes to refine the ontology visually.

---

## 7. Troubleshooting
| Symptom | Fix |
|--------|-----|
| Extraction validation/schema errors | model lacks tool calling — use a tool-capable Llama or `FORCE_TOOL_CHOICE=false`; lower `TOP_N_PER_PAPER` |
| "papers without PDF text" warnings | those PDFs are scanned/locked; the run falls back to abstracts |
| `[rebel] unavailable …` | expected if `transformers`/`torch` aren't installed; REBEL is optional |
| `[lora] manifest written …` | LoRA training is a stub — it records terms; wire real PEFT where marked `TODO` |
| validation shows `CHECK` not `PASS` | low BFO/CCO/MDS alignment or unsatisfiable classes — inspect the TTL |
| empty/odd ontology | a 7B model produced weak concepts — try supervised mode with a curated list |

---

## 7b. Enabling REBEL and LoRA
Both are wired into the flow and degrade gracefully — the pipeline runs without them.
To turn them on:

```bash
uv pip install transformers torch          # REBEL (Step 2 triples)
uv pip install peft datasets accelerate    # LoRA training (Step 6); GPU strongly recommended
```

- **REBEL** then runs during mining and writes `rebel_triples.jsonld` (+ CSV) into the
  GraphDB repo — import it alongside `all.jsonld` to get the relational facts.
- **LoRA** always builds the training set (`lora_adapters/run-<…>/lora_dataset.jsonl`)
  from the run's final ontology terms. If `peft`/`torch` + a GPU are present it trains
  an adapter; otherwise it stops at the dataset (status `dataset-only`) and you can train
  later. Point `LORA_BASE_MODEL` at your local 7B Llama (e.g. a HF path or local dir).
- The trained adapter is meant to be loaded by the next run's extractor to improve
  domain term recall (wire-in point: `kw/extract.py` agents).

## 8. Environment variable reference
| Var | Default | Meaning |
|-----|---------|---------|
| `ZOTERO_LIBRARY_ID` / `_TYPE` / `_API_KEY` | 2189702 / group / — | Zotero access |
| `COLLECTION_ID` | VWMCLGL5 | default collection if `-c` omitted |
| `LLM_BASE_URL` | anthropic | OpenAI-compatible endpoint |
| `LLM_API_KEY` | — | provider key (any string for local) |
| `LLM_MODEL` | claude-sonnet-4-6 | model name |
| `FORCE_TOOL_CHOICE` | true | set false for models without forced tool choice |
| `TOP_N_PER_PAPER` | 25 | concepts per abstract (Step 1) |
| `FULL_TEXT_MAX_CHARS` | 80000 | full-text window for mining (Step 2) |
| `BATCH_SIZE` | 40 | concepts per tagging call |
| `RATE_LIMIT_DELAY` | 0.5 | seconds between LLM calls |
| `OUTPUTS_DIR` / `SCHEMAS_DIR` | outputs / schemas | output locations |
| `MDS_ONTO_LIBRARY` / `CEMENTO_TEMPLATES_LIBRARY` | mds_onto.json / cemento-templates.xml | draw.io palettes |
| `REBEL_MODEL` / `REBEL_REVISION` | Babelscape/rebel-large / main | REBEL model + pin |
| `LORA_BASE_MODEL` | meta-llama/Llama-3.1-8B | base model the adapter trains on |
| `LORA_ADAPTER_DIR` / `LORA_EPOCHS` | lora_adapters / 3 | adapter output dir + training epochs |
