# Architecture

This document describes the current system design of the `kw` package: the corpus
contract, the ordered pipeline, the module map, configuration, and the data flow.

> **History.** Earlier iterations of this project were a set of versioned scripts
> (`knowledge_workflow_V3/V4/V5`) and a `src/` package. Those are superseded and kept
> only under `_deprecated/` (and in git history). The narrative below describes the
> single refactored pipeline that replaced them. For the point-in-time analysis that
> drove the refactor, see `knowledge_base/`.

## System overview

```
┌─────────────────┐
│  Zotero Group   │
│    Library      │
└────────┬────────┘
         │ pyzotero (metadata + PDF attachments)
         v
┌──────────────────────────────────────────────────────────────┐
│  kw package — one ordered pipeline (Python ≥ 3.13, uv-managed) │
│                                                                │
│  0 INPUT      Zotero → uniform corpus contract                 │
│  1 CONCEPTS   abstracts → canonical concept list (LLM)         │
│  2 MINE       full text → value+quote schema (LLM) + REBEL     │
│  3 CONSOLIDATE normalize predicates + entity resolution        │
│  4 ONTOLOGY   OWL 2 TTL  → validation gate                     │
│  5 JSON-LD    per-paper + combined instances (GraphDB repo)    │
│  5b DIAGRAM   cemento draw.io concept map                      │
│  6 LoRA       fine-tune on final ontology terms                │
│  7 VISUAL     interactive graph + cumulative benchmark         │
└────────┬───────────────────────────────────────────────────────┘
         v
   outputs/<slug>/  — a GraphDB-ready repo + diagram + reports
```

Every run produces two primary deliverables: a **GraphDB-ready repo**
(`<slug>_onto.ttl` + `all.jsonld` + `rebel_triples.jsonld`) and a **cemento
`diagram_*.drawio`**. Ordering invariants are enforced in `kw/pipeline.py`: JSON-LD,
the diagram, LoRA, and the visual all run **only after** the ontology is built; REBEL
runs **together** with the LLM during mining.

## The corpus contract

Every downstream stage consumes one uniform structure produced by `kw/zotero.py`:

```python
{
    title_lower: {
        'key':       str,   # Zotero item key
        'title':     str,
        'doi':       str,
        'abstract':  str,
        'date':      str,
        'authors':   list,  # Zotero creator dicts
        'full_text': str,   # extracted PDF text, '' if unavailable
    },
    ...
}
```

Swapping the data source (local PDFs, arXiv, PubMed) means writing one function that
returns this shape — the rest of the pipeline is unchanged.

## Module map (`kw/`)

One responsibility per module.

| File | Role | Pipeline step |
|------|------|---------------|
| `config.py` | Centralised config + canonical namespace registry; builds the shared `pydantic_model` | — |
| `models.py` | Pydantic data contracts (`ConceptTable`, `SchemaRow`, `Triple`, provenance) | — |
| `taxonomy.py` | MDS study-stage / supply-chain lists — single source of truth | — |
| `llm.py` | Thin LLM helper (retry/backoff wrapper around the shared model) | 1, 2, 4 |
| `zotero.py` | Corpus source: papers + PDF text → corpus contract | 0 |
| `extract.py` | Concept discovery, normalization, full-text mining (LLM) | 1, 2 |
| `rebel.py` | REBEL relation extraction; safe no-op if the model is absent | 2 |
| `relations.py` | Normalize REBEL predicates to the MDS relation vocabulary | 3 |
| `merge.py` | Entity resolution between REBEL triples and concepts | 3 |
| `mdsonto.py` | Ground concepts to real MDS-Onto terms (OntoPortal API) + optional submission | 3, 4 |
| `tagger.py` | MDS `studyStage` + `supplyChainLevel` grounding tags | 5b |
| `ontology.py` | OWL 2 TTL builder + JSON-LD emitter | 4, 5 |
| `validate.py` | Reasoner / OOPS! / alignment gate (degrades gracefully) | 4 |
| `drawio.py` | cemento concept-map diagram with embedded palette pages | 5b |
| `lora.py` | LoRA fine-tune on final ontology terms (dataset-only if no GPU) | 6 |
| `visualize.py` | Interactive knowledge-graph HTML + benchmark row | 7 |
| `graphview.py` | Graph layout/rendering helpers used by `visualize.py` | 7 |
| `store.py` | CSV I/O, filename + slug conventions (single version tag) | — |
| `batch.py` | Run the pipeline over a queue of collections (`collections.example.txt`) | — |
| `pipeline.py` | The ordered runner — enforces step ordering and timing | all |
| `__main__.py` | CLI (`python -m kw …`) | — |
| `sources/` | Alternate corpus sources (e.g. `patents.py`) | 0 |
| `gephi.py` | Standalone Gephi/GEXF export (utility, not wired into the pipeline) | — |

## The ordered pipeline (`pipeline.run`)

### Step 0 — Input
`zotero.get_collection_with_text(collection_id, limit)` returns the corpus contract.
`--limit` caps the number of papers (quick tests). Papers without extractable PDF text
fall back to abstract-only.

### Step 1 — Concepts (unsupervised only)
`extract.infer_domain_context()` frames the corpus, then
`extract.build_concept_table()` pulls `(canonical, paper_term, relevance)` per paper
(source controlled by `CONCEPT_SOURCE`: `abstract` | `abstract+intro` | `full-text`),
and `extract.normalize_concept_list()` dedupes/merges to a clean shared list
(target 30–80, dials: `--top-n`, `--min-relevance`, `--max-concepts`). In **supervised**
mode (`--concepts list.csv`) this step is skipped and your list is used verbatim.

### Step 2 — Mine (LLM + REBEL together)
For each paper, over the full text and all concepts:
`extract.build_schema_rows()` returns per concept a paper-specific `value` and a source
`quote` (`"value | quote"`), with optional chunking (`CHUNK_FULL_TEXT`) and parallel
mining (`MINE_WORKERS`). In parallel, `rebel.extract_corpus()` emits exact S-P-O triples
as stated in the text (no-op if `transformers`/`torch` aren't installed).

### Step 3 — Consolidate
`relations.normalize_triples()` maps REBEL predicates onto the MDS relation vocabulary;
`merge.resolve()` performs entity resolution so a thing named in prose and in a relation
becomes one node (gated by `MERGE_REBEL`, threshold `MERGE_SIM_THRESHOLD`).
`mdsonto.resolve_concepts()` grounds the concept list to real MDS-Onto IRIs via the
OntoPortal API (active only when configured).

### Step 4 → 5 — Ontology then JSON-LD
`ontology.process_schema_file()` builds an OWL 2 / MDS-Onto-compliant Turtle ontology
(`mds:Concept` and subclasses; each schema column a property IRI; per-domain namespace),
then emits one JSON-LD document per paper plus a combined `all.jsonld`. The validation
gate `validate.evaluate()` parses the TTL, computes BFO/CCO/MDS alignment, and (when
enabled) runs the reasoner / OOPS! / SHACL, reporting **PASS** or **CHECK**. When
`SUBMIT_TO_PORTAL` is set and validation passes, `mdsonto.submit_to_portal()` uploads
the ontology.

### Step 5b — Diagram
`tagger.tag_concepts()` adds MDS `studyStage` + `supplyChainLevel` (single-source
taxonomy in `taxonomy.py`), then `drawio.py` lays out a concept map coloured by study
stage and embeds the MDS-Onto and Cemento palette libraries as pages.

### Step 6 — LoRA
`lora.finetune()` builds a supervised dataset from the final ontology terms + mined
(text → value) pairs. With `peft`/`torch` + a GPU it trains and saves an adapter;
otherwise it stops at the dataset + manifest (`status: dataset-only`) so the run still
completes.

### Step 7 — Visual + benchmark
`visualize.run_for_pipeline()` renders an interactive `graph.html` from `all.jsonld` and
appends a row to the cumulative `eval/graph_benchmark.csv`. Wrapped in try/except — never
allowed to break a run.

## Namespace registry

Defined once in `config.NS` and reused everywhere:

| Prefix | IRI |
|--------|-----|
| `mds` | `https://cwrusdle.bitbucket.io/mds/` |
| `bfo` | `http://purl.obolibrary.org/obo/BFO_` |
| `cco` | `https://www.commoncoreontologies.org/` |
| `qudt` | `http://qudt.org/schema/qudt/` |
| `prov` | `http://www.w3.org/ns/prov#` |
| `skos` | `http://www.w3.org/2004/02/skos/core#` |

## Configuration

All configuration lives in `kw/config.py`, sourced from environment variables / `.env`
with code defaults as fallback (precedence: env vars > `.env` > defaults). Nothing is
hardcoded; the LLM provider is any OpenAI-compatible endpoint (Anthropic, OpenAI, Groq,
Ollama, LM Studio). See `env.example.txt` for the full template and `docs/USAGE_GUIDE.md`
for the annotated reference.

**Secrets** (Zotero key, LLM key) are read from the environment only and never committed
— `.env` is gitignored.

## File naming convention

`store.make_filename()` produces, for every artifact:

```
{type}_{slug}-{username}-v{VERSION}-{YYYYMMDD}.csv
```

`VERSION` is a single constant in `store.py` (currently `8`); the slug is a readable,
filesystem-safe form of the collection name (`store.collection_slug`). Examples:
`concepts_fair_ontology-Brent_Thompson-v8-20260623.csv`,
`schema_cdte-Brent_Thompson-v8-20260623.csv`.

## Output directory structure

```
outputs/<slug>/
├── concepts_<…>.csv          # Step 1 flat concept table (unsupervised)
├── schema_<…>.csv            # Step 2 wide schema (value | quote)
├── enriched_<…>.csv          # concepts + MDS tags
├── <slug>_onto.ttl           # OWL 2 ontology (GraphDB)
├── <paper>.jsonld, all.jsonld# JSON-LD instances (GraphDB import)
├── rebel_triples.jsonld, triples_<…>.csv  # REBEL relations
├── diagram_<…>.drawio        # cemento concept map
├── graph.html, graph_report.md  # Step 7 visual + report
└── <slug>.log                # per-run log (stdout + log records)
```

`outputs/`, `schemas/`, `graphdb/`, and `lora_adapters/` are gitignored (generated data).

## Resilience & reproducibility

- **Retries:** LLM calls retry with backoff (`LLM_MAX_RETRIES`, `LLM_BACKOFF`).
- **Checkpointing:** mining can checkpoint per paper (`USE_CHECKPOINT`), so a re-run
  skips already-processed papers.
- **Logging:** each run tees stdout + log records to `outputs/<slug>/<slug>.log` and
  prints per-step timing.
- **Graceful degradation:** REBEL, LoRA training, the reasoner/OOPS!/SHACL checks, and
  the Step 7 visual are all optional and degrade to no-ops if their deps are absent, so
  the pipeline runs end-to-end from a minimal install.

## Related documentation

- [../README.md](../README.md) — quick start
- [PROCESS.md](PROCESS.md) — the end-to-end process, step by step
- [USAGE_GUIDE.md](USAGE_GUIDE.md) — running the tool + environment variable reference
- [PROJECT_BRIEF.md](PROJECT_BRIEF.md) / [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md) — original scope and operating contract
- `knowledge_base/` — the point-in-time analysis that drove the refactor
