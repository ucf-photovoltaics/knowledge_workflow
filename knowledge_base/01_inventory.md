# 01 — Inventory

Everything in the repo (excluding `.git`, `.venv`, `__pycache__`), with a
keep/retire recommendation for the rebuild.

## Entry point & modular package (the refactor target)
| Path | Lines | What it is | Rebuild |
|------|-------|-----------|---------|
| `main.py` | 169 | CLI: `--extract` / `--enrich` / `--collection` / `--list-collections`; dispatches to `src.agents.orchestrator` | **Keep** (thin CLI over new package) |
| `src/config.py` | 87 | Central config; OpenAI-compatible LLM via `pydantic_ai.OpenAIModel`; Zotero, pipeline params, dirs | **Keep** (best-designed file) |
| `src/agents/orchestrator.py` | 210 | `run_extraction` / `run_enrichment` / `run_full` — wires Pipeline A + B | **Refactor** into a pipeline/DAG runner |
| `src/agents/extractor.py` | 85 | Phase 1 — per-abstract concept extraction | **Keep → `extract/`** |
| `src/agents/normalizer.py` | 66 | Dedup/normalize raw concept labels | **Keep → `extract/`** |
| `src/agents/schema_builder.py` | 106 | Phase 2 — full-text schema population (value+quote) | **Keep → `extract/`** |
| `src/agents/tagger.py` | 177 | V6 — tag concepts with MDS study stage + supply-chain level | **Keep → `ground/` or `enrich/`** |
| `src/agents/rebel_extractor.py` | 53 | REBEL parallel triples (NEW stub, this session) | **Keep → `extract/`** |
| `src/models/{concept,schema,tag}.py` | 56/38/32 | Pydantic data contracts + PydanticAI result types | **Keep → `core/models`** (single source of truth) |
| `src/tools/zotero_client.py` | 89 | Zotero fetch + PDF text | **Keep → `io/sources/zotero`** |
| `src/tools/csv_writer.py` | 125 | Filenames, save/load CSVs | **Keep → `io/`** |
| `src/tools/drawio_builder.py` | 470 | draw.io XML concept map | **Keep → `emit/drawio`** (dedupe vs cemento_connect) |
| `src/tools/owl_emitter.py` | 65 | OWL/JSON-LD emit (NEW stub, this session) | **Merge** with graphdb_connector logic |
| `src/utils.py` | 7 | trivial | Fold in |

## Standalone scripts (capabilities stranded outside the package)
| Path | Lines | What it is | Rebuild |
|------|-------|-----------|---------|
| `graphdb_connector.py` | 712 | **The real OWL 2 + JSON-LD emitter.** Schema CSV → MDS-Onto Turtle → per-paper + `all.jsonld` for GraphDB. Classifies concepts (Measurement/Material/Process), resolves namespaces | **Harvest** → `ground/` + `emit/owl` + `emit/jsonld` + `publish/graphdb` |
| `cemento_connect.py` | 936 | V6 draw.io generator with MDS tagging; embeds `mds_onto.json` + `cemento-templates.xml` as palette pages | **Harvest** → `emit/drawio`; duplicates tagger + drawio_builder |

## Legacy monoliths (pre-refactor)
| Path | Lines | Rebuild |
|------|-------|---------|
| `knowledge_workflow_v5_codebase.py` | 791 | **Retire** (superseded by `src/`) |
| `knowledge_worklow_v5.py` | 674 | **Retire** (note: filename typo "worklow") |
| `knowledge_workflow_v5.ipynb`, `run_src_workflow.ipynb` | — | **Archive** (keep as scratch/demo, out of package) |
| `knowledge_workflow_v5_architecture.drawio` | — | Archive |

## Ontologies & palette artifacts
| Path | What it is | Rebuild |
|------|-----------|---------|
| `gaas_onto.ttl` | Example output (GaAs PV); rich grounding `bfo:`/`pmd:`/`qudt:`/`mds#`; 7 classes (all aligned), 0 individuals | **Keep** as a reference/gold example |
| `mds_onto.json` | draw.io **mxlibrary** (Cemento shapes) — NOT an ontology file | Keep as a palette asset; rename to avoid confusion |
| `cemento-templates.xml` | draw.io shape library | Keep as palette asset |

## Generated data (should not be in VCS)
| Path | What it is | Rebuild |
|------|-----------|---------|
| `outputs/<domain>/` | Real runs: copper-metallization, electron-microscopy — concepts/schema/enriched CSVs, draw.io, per-paper `.jsonld`, `all.jsonld`, `_onto.ttl` | **Gitignore**; move out of repo |
| `schemas/<domain>/` | Reusable concept/schema CSVs | Keep a curated few; gitignore the rest |

## This session's additions
| Path | What it is |
|------|-----------|
| `docs/PROJECT_BRIEF.md`, `docs/PROJECT_INSTRUCTIONS.md` | Refactor brief + operating instructions |
| `eval/structural_metrics.py` | Reasoner/OOPS!/alignment harness (verified on `gaas_onto.ttl`) |
| `scripts/publish.py` | GitHub + GraphDB publish, gated on metrics |
| `src/agents/rebel_extractor.py`, `src/tools/owl_emitter.py` | Stubs for REBEL + OWL emit |

## Git worktrees (major source of duplication)
`.claude/worktrees/{blissful-leavitt, hungry-sinoussi, naughty-feistel}/` each
hold near-complete variants: a **V6 (1048 lines)**, V5, a `cemento_connector.py`,
`README.md` / `README2.md`, `docs/ARCHITECTURE.md`, and their own `outputs/` +
`schemas/`. The `docs/ARCHITECTURE.md` here is the **best existing documentation**
(full V1–V5 evolution, Zotero integration, cost/perf notes). **Action:** salvage
`ARCHITECTURE.md`, pick ONE V6, delete the rest of the worktrees.

## Config & tooling
`.env` (+ `env.example.txt`), `pyproject.toml` (Python ≥3.13, `uv`), `uv.lock`,
`.python-version`, `.gitignore`. Stack: `anthropic`, `openai`, `instructor`,
`pydantic`, `pydantic-ai`, `pyzotero`, `pypdf`/`fitz`, `pandas`, `keybert`,
`spacy`, `scikit-learn`, `shiny`, `fastmcp`, `matplotlib`.
