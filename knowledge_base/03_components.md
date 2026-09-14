# 03 — Components

Module-by-module responsibilities and the key functions/interfaces.

## `src/config.py`
Single source of configuration. Loads `.env`, exposes Zotero creds, the
OpenAI-compatible LLM settings, pipeline knobs, and a shared
`pydantic_model = OpenAIModel(MODEL, base_url=LLM_BASE_URL, api_key=LLM_API_KEY)`.
Notable knobs: `TOP_N_PER_PAPER=25`, `FULL_TEXT_MAX_CHARS=80000`, `BATCH_SIZE=40`
(tagging), `USE_CSV_CONCEPTS`/`CONCEPTS_CSV_PATH` (skip Phase 1),
`MDS_ONTO_LIBRARY`/`CEMENTO_TEMPLATES_LIBRARY` (palette files).
*This is the model the rebuild should follow everywhere.*

## Agents (`src/agents/`)
| Module | Responsibility | Key functions | Returns |
|--------|---------------|---------------|---------|
| `extractor.py` | Phase 1 concept extraction from abstracts | `build_concept_table(papers, top_n)` | `ConceptTable` |
| `normalizer.py` | Dedupe/merge raw labels into clean ontology terms | `normalize_concept_list(all_canonicals)` | `list[str]` |
| `schema_builder.py` | Phase 2 full-text population (value + source quote) | `build_schema_rows(papers, concepts, domain)` | `list[SchemaRow]` |
| `tagger.py` | V6 MDS-Onto enrichment | `tag_concepts(df)` (`_tag_batch`) | tagged `DataFrame` |
| `orchestrator.py` | Wire pipelines A/B | `run_extraction`, `run_enrichment`, `run_full` | result dicts |
| `rebel_extractor.py` | (NEW stub) REBEL parallel triples + entity-resolution merge | `extract_triplets`, `merge_with_concepts` | `list[Triplet]` |

> Naming note: these are called "agents" but are really **stages/functions** with
> LLM calls — there is no agent loop, planner, or tool-calling controller yet. The
> multi-agent / REBEL+LoRA routing from the project brief is still aspirational.

## Tools (`src/tools/`)
| Module | Responsibility | Key functions |
|--------|---------------|---------------|
| `zotero_client.py` | Zotero API access | `get_collection_map()`, `get_collection_with_text(id)`, `get_pdf_text(key)` |
| `csv_writer.py` | Filenames + persistence | `make_filename`, `collection_slug`, `save_concepts_csv`, `save_schema_csv`, `load_concepts`, `find_latest_file` |
| `drawio_builder.py` | draw.io concept map XML | `build_drawio_xml(df)`, `add_template_pages`, `serialize_drawio` |
| `owl_emitter.py` | (NEW stub) OWL + JSON-LD | `emit_ontology(domain, classes, triples, out_dir)` |

## Standalone connectors
### `graphdb_connector.py` — the real OWL/JSON-LD emitter
- `build_collection_ontology(...)` — assembles OWL 2 TTL: declares `mds:Concept` and
  subclasses (`Measurement`, `Material`, `Process`), turns schema columns into
  properties, classifies each concept via `_classify_concept(label)`.
- `load_ttl_property_map(ttl)` — maps column → property IRI.
- `resolve_ns(domain_value)` / `prop_iri(...)` / `to_camel` / `safe_slug` — IRI helpers.
- `row_to_jsonld(...)` — one JSON-LD doc per paper, typed `mds:ResearchPublication`,
  with `@context` (mds, qudt, schema, prov, skos, dcterms).
- `discover_schema_files()` / `process_schema_file()` / `main()` — batch driver with
  `--schema`, `--dry-run`, `--limit`, `--verbose`.

### `cemento_connect.py` — draw.io concept maps (V6)
- `tag_concepts` / `_tag_batch` — duplicate of `src/agents/tagger.py` logic.
- `build_drawio_xml` + swimlane/grouping helpers — duplicate of `src/tools/drawio_builder.py`.
- `_load_mxlibrary` / `_embed_library_page` / `_add_template_pages` — embed
  `mds_onto.json` + `cemento-templates.xml` as palette pages in the diagram.
- `_process_one(csv_path)` — per-file driver.

## CLI (`main.py`)
Argparse front end: `--list-collections`, `--extract`, `--enrich [CSV]`,
`--collection/-c`. Calls the orchestrator and prints previews/summaries.

## Dependency map (who imports what)
```
main.py
 └─ src.agents.orchestrator
     ├─ src.config            (MODEL, dirs, knobs, pydantic_model)
     ├─ src.agents.{extractor, normalizer, schema_builder, tagger}
     │     └─ src.models.{concept, schema, tag}   (result_types)
     └─ src.tools.{zotero_client, csv_writer, drawio_builder}

graphdb_connector.py   (standalone — imports nothing from src/)
cemento_connect.py     (standalone — re-implements tagger + drawio_builder)
```
The standalone scripts not importing `src/` is the structural problem the refactor fixes.
