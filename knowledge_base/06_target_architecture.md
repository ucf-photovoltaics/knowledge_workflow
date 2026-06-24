# 06 — Target Architecture (proposed modular rebuild)

Goal: one installable package, one pipeline, one data contract. Every stage is
pluggable and consumes/produces typed `core` models — never raw CSV.

> **AS BUILT.** The refactor delivered the goals above as a **flat `kw/` package**
> (one module per step: `config`, `models`, `taxonomy`, `zotero`, `store`, `extract`,
> `rebel`, `tagger`, `ontology`, `validate`, `drawio`, `lora`, `pipeline`, `__main__`)
> rather than the nested `core/ io/ extract/ …` tree sketched below. The flat layout was
> chosen deliberately for "no unnecessary complexity" at this size. The mapping is 1:1
> (e.g. proposed `emit/owl.py`+`emit/jsonld.py`+`publish/graphdb.py` → harvested into
> `kw/ontology.py`; `core/models.py` → `kw/models.py`). Treat the tree below as the
> conceptual target; `kw/README.md` documents the as-built modules.

## Package layout
```
knowledge_workflow/                # or a fresh name, e.g. "kweave"
  core/
    models.py        Paper, Concept, SchemaRow, Triple, OntologyClass,
                     Provenance, Tag, Confidence            (Pydantic — single source of truth)
    config.py        (keep today's config.py almost as-is)
    provenance.py    build/attach provenance + run trace
  io/
    sources/zotero.py   get_collection_with_text -> Corpus      (from src/tools/zotero_client)
    sources/pdf.py      local PDF dir source
    store.py            read/write CSV + JSON-LD + TTL (serialize at edges only)
  extract/
    concepts.py      Phase 1            (from agents/extractor)
    normalize.py     dedupe             (from agents/normalizer)
    schema.py        Phase 2 full-text  (from agents/schema_builder)
    rebel.py         parallel triples   (from agents/rebel_extractor)
    router.py        REBEL vs LoRA routing (new; see PROJECT_INSTRUCTIONS)
    merge.py         entity resolution across LLM + REBEL (new)
  ground/
    mds.py           MDS-Onto mapping   (harvest graphdb_connector classify/IRI logic)
    bfo_cco.py       BFO/CCO alignment  (NEW — the real net-new work)
    namespaces.py    one canonical registry (fix mds# vs mds/)
    tagger.py        study-stage / supply-chain tags (from agents/tagger)
  emit/
    owl.py           OWL 2 TTL          (harvest build_collection_ontology)
    jsonld.py        per-paper + all.jsonld (harvest row_to_jsonld)
    drawio.py        concept maps + palette pages (merge drawio_builder + cemento_connect)
    csv.py           CSV writer         (from tools/csv_writer)
  validate/
    reasoner.py      ELK/ROBOT consistency
    oops.py          OOPS! pitfalls
    shacl.py         shape constraints
    metrics.py       structural_metrics (already written this session)
  publish/
    github.py        push artifacts     (from scripts/publish.py)
    graphdb.py       load into GraphDB  (harvest graphdb_connector)
  pipeline/
    runner.py        DAG: extract -> ground -> emit -> validate -> publish
    checkpoint.py    per-paper resume
  cli.py             thin argparse over pipeline (from main.py)
```

## The one pipeline
```
Corpus ─► extract (concepts, schema, REBEL triples)
       ─► merge (entity resolution)
       ─► ground (MDS, then BFO/CCO; tags)
       ─► emit (OWL TTL + JSON-LD [+ draw.io])
       ─► validate (reasoner + OOPS! + SHACL + alignment %)   ← GATE
       ─► publish (GitHub → GraphDB)
```
Stages are optional and ordered by a config-driven DAG. A run that fails `validate`
is not published.

## Design principles
1. **One data contract.** Every stage speaks `core.models`. CSV/TTL/JSON-LD are only
   serialization at the boundaries (`io/`, `emit/`).
2. **One implementation per capability.** Delete duplicates (tagger×2, drawio×2, OWL stub vs connector).
3. **Provenance everywhere.** Each `Triple` carries a `Provenance` (source span, tool,
   model+version, seed, confidence). Enables the explainability/reproducibility claims.
4. **Validation is mandatory, not optional.** `validate/` gates `publish/`.
5. **Reproducible by construction.** Pin model + seed + (REBEL revision / LoRA adapter hash);
   log the routing decision and the run trace.
6. **Generated data out of VCS.** `outputs/`, `schemas/` gitignored; worktrees removed.
7. **Provider-agnostic stays.** Keep the `OpenAIModel(base_url=...)` design.

## Migration map (harvest, don't rewrite)
| New module | Source today |
|------------|--------------|
| `core/config.py` | `src/config.py` (nearly verbatim) |
| `core/models.py` | `src/models/*` + new Paper/Triple/Provenance/OntologyClass |
| `io/sources/zotero.py` | `src/tools/zotero_client.py` |
| `extract/*` | `src/agents/{extractor,normalizer,schema_builder,rebel_extractor}` |
| `ground/mds.py`, `emit/owl.py`, `emit/jsonld.py`, `publish/graphdb.py` | **split `graphdb_connector.py`** |
| `ground/tagger.py`, `emit/drawio.py` | merge `src/agents/tagger.py` + `src/tools/drawio_builder.py` + `cemento_connect.py` |
| `ground/bfo_cco.py` | NEW |
| `validate/*` | `eval/structural_metrics.py` + new reasoner/OOPS!/SHACL |
| `publish/github.py` | `scripts/publish.py` |
| `cli.py` | `main.py` |
| retire | V5/V6 monoliths, all `.claude/worktrees/*` (after salvaging ARCHITECTURE.md + one V6) |

## Suggested rebuild order (maps to the 2-week brief)
1. `core/models.py` + `core/config.py` (the contract).
2. `io` + `extract` (port working V5/V6 onto the contract).
3. `ground` + `emit` (harvest graphdb_connector → produce OWL+JSON-LD from models).
4. `validate` (wire the gate; run on the GaAs/electron-microscopy samples).
5. `publish` (GitHub → GraphDB).
6. Stretch: `extract/router` + `extract/rebel` + LoRA loop.
