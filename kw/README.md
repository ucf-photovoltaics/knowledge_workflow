# kw — Knowledge Workflow (refactored)

One installable package, one ordered pipeline, one data contract. Replaces the
old `src/` package, the V5/V6 monoliths, and the standalone `graphdb_connector.py`
/ `cemento_connect.py` scripts (now in `_deprecated/`).

## The flow (see ../knowledge_base/08_pipeline_spec.md)
```
INPUT(mode) → CONCEPTS → MINE(LLM + REBEL) → CONSOLIDATE → ONTOLOGY → JSON-LD → DIAGRAM → LoRA → VISUAL
```
Invariants enforced in `pipeline.py`: JSON-LD, the diagram, LoRA, and the visual all run
only *after* the ontology. Every run produces **both** deliverables — a GraphDB-ready repo
(`<slug>_onto.ttl` + `all.jsonld` + `rebel_triples.jsonld`) and a cemento `diagram_*.drawio`.

## Run
```bash
python -m kw --list-collections                        # discover Zotero collections
python -m kw run -c <collection_id>                    # unsupervised (auto concepts), both outputs
python -m kw run -c <collection_id> --concepts list.csv # supervised (provided concepts)
python -m kw run -c <collection_id> --no-diagram --no-lora --no-visual # ontology/JSON-LD only
```

## Modules (one responsibility each)
| File | Role | Pipeline step |
|------|------|---------------|
| `config.py` | config + canonical namespace registry; builds the shared model (fixes P5) | — |
| `models.py` | all Pydantic data contracts (incl. Triple, Provenance) | — |
| `taxonomy.py` | MDS study-stage / supply-chain lists — single source (fixes P1) | — |
| `llm.py` | thin LLM helper (retry/backoff around the shared model) | 1, 2, 4 |
| `zotero.py` | corpus source (papers + PDF text) | 0 |
| `extract.py` | concepts + normalize + full-text mining (LLM) | 1, 2 |
| `rebel.py` | REBEL triples, run with the LLM (no-op if model absent) | 2 |
| `relations.py` | normalize REBEL predicates → MDS relation vocab | 3 |
| `merge.py` | entity resolution (REBEL triples ↔ concepts) | 3 |
| `mdsonto.py` | ground concepts to MDS-Onto IRIs + optional OntoPortal submission | 3, 4 |
| `tagger.py` | MDS grounding tags (studyStage / supplyChainLevel) | 5b |
| `ontology.py` | OWL 2 TTL builder + JSON-LD emitter (harvested) | 4, 5 |
| `validate.py` | validation gate: OntoCheck + OOPS! (required), alignment/reasoner/SHACL (advisory); writes `validation_report.md`/`.json` | 4 |
| `lora.py` | terminal LoRA fine-tune on final ontology terms | 6 |
| `drawio.py` | cemento concept-map diagram (emitted by default; `--no-diagram` to skip) | 5b |
| `visualize.py` | interactive graph HTML + benchmark row (`--no-visual` to skip) | 7 |
| `graphview.py` | merged provenance-rich graph + interactive viewer (imports from `visualize`; powers the shiny explorer & `gephi`) | — |
| `store.py` | CSV I/O + filenames (readable slugs, single version tag) | — |
| `batch.py` | run the pipeline over a queue of collections | — |
| `pipeline.py` | the ordered runner | all |
| `__main__.py` | CLI | — |
| `sources/` | alternate corpus sources (e.g. `patents.py`) | 0 |
| `gephi.py` | standalone Gephi/GEXF export (utility, not wired into the pipeline) | — |

## Notes
- Targets current `pydantic-ai` (uses `output_type` / `.output`; the older `result_type`
  / `.data` API was removed upstream). `config.py` builds the model in a version-robust
  way (provider object *or* legacy kwargs).
- REBEL and LoRA are **complete**: REBEL runs inference and persists triples; LoRA builds
  the SFT dataset and runs real PEFT training when `LORA_TRAIN=true` and
  `transformers`/`peft`/`torch` (+ GPU) are present. By default (`LORA_TRAIN` unset) it
  writes the dataset + manifest only, so the pipeline completes without pulling a large
  base model. Both degrade gracefully, so the pipeline runs end-to-end even before those
  optional deps are installed (`uv pip install transformers torch peft datasets accelerate`).
- Generated data (`outputs/`, `schemas/`, `graphdb/`, `lora_adapters/`) is gitignored.
- `_deprecated/` holds the old code (recoverable from git too). The three
  `.claude/worktrees/` are gitignored; remove them with `git worktree remove` if desired.
