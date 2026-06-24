# 02 — Current Architecture

## Version evolution (from `docs/ARCHITECTURE.md`)
| Ver | Method | Key trait | Status |
|-----|--------|-----------|--------|
| V1 | spaCy noun-chunks + TF-IDF | offline, deterministic, not semantic | retired |
| V2 | KeyBERT (BERT keywords + MMR) | semantic, offline, no structured values | retired |
| V3 | Claude + `instructor`, dynamic Pydantic | structured per-paper extraction, known schema | superseded |
| V4 | Two-stage: discovery + full-text mining | schema discovery + source quotes | superseded |
| V5 | Provider-agnostic (OpenAI-compatible) | same as V4, any LLM via base_url | **current core** |
| V6 | Enrichment: MDS tagging + draw.io | study-stage / supply-chain tags, concept maps | **current** |
| — | `graphdb_connector.py` | OWL TTL + JSON-LD for GraphDB | **current, stranded** |

The modular `src/` package is the consolidation of **V5 + V6**.

## The two pipelines (in `src/agents/orchestrator.py`)

### Pipeline A — Extraction (`run_extraction`)
```
Zotero collection id
  → get_collection_map()            resolve name
  → get_collection_with_text()      papers {title: {meta, abstract, full_text(PDF)}}
  → [Phase 1] build_concept_table(papers, top_n=25)   per-abstract concepts
  → normalize_concept_list(all_canonicals)            dedupe → 30–80 concepts
  → [Phase 2] build_schema_rows(papers, concepts)     full-text (≤80k chars), value+quote
  → save concepts_*.csv + schema_*.csv  (+ copy to schemas/<slug>/)
```
Reuse path: set `USE_CSV_CONCEPTS=true` + `CONCEPTS_CSV_PATH` to skip Phase 1.

### Pipeline B — Enrichment (`run_enrichment`)
```
concepts_*.csv
  → tag_concepts(df)        LLM tags each concept:
                              mds:studyStage (sample|tool|recipe|pre-processing|
                                              analysis|modeling|results publishing)
                              mds:supplyChainLevel (materials|subcomponent|component|
                                              assembly|subsystem|system)
  → enriched_*.csv
  → build_drawio_xml(df)    concept map, nodes coloured by study stage
  → add_template_pages()    embed MDS-Onto + Cemento palette pages
  → diagram_*.drawio
```

`run_full` = A then B.

### Stranded — OWL/JSON-LD (`graphdb_connector.py`, NOT in orchestrator)
```
schema_*.csv
  → build_collection_ontology()   OWL 2 TTL: classes under mds:Concept
                                   (Measurement/Material/Process), props from columns
  → load_ttl_property_map()        property IRI resolution
  → row_to_jsonld(paper)           one JSON-LD per paper (typed mds:ResearchPublication)
  → all.jsonld                     combined, for GraphDB bulk import
```
This already produces the project's target output — it just isn't wired in,
doesn't use BFO/CCO, and isn't validated.

## LLM access
- **Provider-agnostic** via `pydantic_ai.OpenAIModel(MODEL, base_url, api_key)` — one
  object works for OpenAI / Anthropic-compat / Groq / Ollama / LM Studio.
- **Structured output** via PydanticAI `result_type` models (each agent declares a
  Pydantic return type; the tool/function schema is auto-generated). This replaced the
  hand-written JSON tool dicts from V4/V5.
- Default model `claude-sonnet-4-6`; `RATE_LIMIT_DELAY=0.5s`; serial processing.

## Data lifecycle
```
Zotero ──► papers dict ──► concepts CSV ──► schema CSV ──┬─► enriched CSV ─► draw.io
                                                          └─► OWL TTL ─► JSON-LD ─► GraphDB
```
CSV is the spine connecting stages. Each handoff is a file on disk, not an in-memory
typed object — a key brittleness (see 05).

## Domains processed so far
GaAs PV, CdTe/CdSeTe PV, perovskites, TEM semiconductors, copper metallization,
electron-microscopy contact corrosion — i.e. Case Western SDLE photovoltaics/materials.
