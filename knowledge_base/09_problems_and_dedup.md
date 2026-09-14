# 09 — Problems Found & Deduplication Actions

Concrete issues from a read of every implementation file, plus the actions to reach
one efficient pipeline ([08_pipeline_spec.md](08_pipeline_spec.md)). Ordered by severity.

> **STATUS — resolved by the refactor.** P1 (taxonomy) → single source `kw/taxonomy.py`;
> P2/P3 (fragmentation + ordering) → one ordered `kw/pipeline.py`; P4 (REBEL/LoRA) →
> completed in `kw/rebel.py` + `kw/lora.py`; P5 (namespace) → `kw/config.NS`; P6 →
> ontology/JSON-LD are the primary artifacts, diagram by default; P9 → monoliths/connectors
> moved to `_deprecated/`, generated data gitignored. Remaining/optional: P7 slug polish (done
> in `store.collection_slug`), P8 resilience (retry/checkpoint — still TODO), P10 naming (the
> flat `kw/` modules are stages, not an agent loop), P11 dependency trimming (TODO).

## Verified NON-issues (checked, they're fine)
- `load_concepts` **does** remap `canonical → concept` and compute `doc_frequency`, so
  the Phase-1 CSV feeds the tagger correctly. Not a bug.
- Within `src/`, the tagger prompt matches its 12-stage `STUDY_STAGES` enum. Consistent.
- `src/` compiles cleanly (`py_compile` of the whole tree passes).

## P1 — Diverged study-stage taxonomy (data-correctness bug) — HIGH
Two different, incompatible taxonomies exist:
- `src/tools/drawio_builder.py` + `src/agents/tagger.py`: **12 stages** (synthesis,
  formulation, materials processing, sample, tool, recipe, data, data processing,
  result, analysis, modeling, results and metadata).
- `cemento_connect.py` + worktree V6: a **7-stage** set (sample, tool, recipe,
  **pre-processing**, analysis, modeling, **results publishing**) — values that don't
  exist in `src`.
Same concept gets tagged differently depending on which entry point ran.
**Action:** adopt the `src/` 12-stage set as canonical; delete the 7-stage copy.

## P2 — Capability fragmentation: no end-to-end run — HIGH
Ontology + JSON-LD (`graphdb_connector.py`) and draw.io (`cemento_connect.py`) are
standalone scripts that **don't import `src/`**. No single command runs
concepts → ontology → JSON-LD (your Steps 1→5).
**Action:** harvest `graphdb_connector` into `ground/` + `emit/owl` + `emit/jsonld`;
wire it into the orchestrator so the spec's one-command run works.

## P3 — Ordering invariants not enforced — HIGH
Nothing guarantees "JSON-LD only after ontology" and "LoRA only after ontology" — they
are separate manual scripts. Your flow depends on this ordering.
**Action:** make them pipeline stages with explicit dependencies; the runner enforces order.

## P4 — Missing steps: REBEL + LoRA — HIGH (net new)
Mining's REBEL call and the terminal LoRA fine-tune are **stubs / absent**.
**Action:** implement `extract/rebel.py` (parallel triples in Step 2) and `train/lora.py`
(Step 6, trains once per finished ontology).

## P5 — Namespace inconsistency — MEDIUM
`mds:` = `…/mds#` in `gaas_onto.ttl` vs `…/mds/` (slash, with sub-paths) in
`graphdb_connector` output. Breaks IRI joins / interoperability.
**Action:** one canonical MDS IRI in a `ground/namespaces.py` registry; use everywhere.

## P6 — Wrong primary artifact — MEDIUM
Current core pipeline treats CSV + draw.io as the deliverable; your flow makes
**ontology + JSON-LD** primary and draw.io optional.
**Action:** move tagging into grounding; make `emit/drawio` optional, off the critical path.

## P7 — Filename / slug mangling — LOW
`collection_slug` strips both `-` and `>`, producing run-together names
(`indevelopmentelectronmicroscopy…`); version tags (v5/v6/v7) are sprinkled ad hoc.
**Action:** slugify to readable kebab/underscore; drive version from one constant.

## P8 — Silent failures & no resilience — MEDIUM
`get_pdf_text` swallows all exceptions (`except: pass` → `''`); LLM calls have only
`retries=2`, no backoff; processing is serial; **no checkpointing** — a crash near the
end reprocesses everything.
**Action:** log skipped PDFs; add retry/backoff; checkpoint per paper so runs resume.

## P9 — Repo bloat & duplication — MEDIUM
Generated `outputs/` and `schemas/` are committed; **three near-duplicate git worktrees**
under `.claude/worktrees/` each carry a full variant (one V6 is 1048 lines).
**Action:** salvage `worktrees/*/docs/ARCHITECTURE.md` + one V6, delete the rest;
gitignore `outputs/` and `schemas/`.

## P10 — "agents" that aren't agents — LOW (clarity)
`src/agents/*` are LLM-calling functions, not an agent loop. For a linear flow this
naming implies complexity that isn't there.
**Action:** rename to `stages/` (or `extract/`, `ground/`) per the spec.

## P11 — Dependency bloat — LOW
`fitz`/PyMuPDF is in deps but `pypdf` is what's used; `keybert`/`spacy`/`scikit-learn`
support only retired V1/V2.
**Action:** drop unused PDF lib; gate legacy NLP deps behind an optional extra.

## Retire / merge ledger
| File | Action |
|------|--------|
| `knowledge_workflow_v5_codebase.py`, `knowledge_worklow_v5.py` | **delete** (superseded by `src/`) |
| `.claude/worktrees/{blissful,hungry,naughty}/` | **delete** after salvaging ARCHITECTURE.md + one V6 |
| `cemento_connect.py` | **merge** its library-page embedding into `emit/drawio`, then delete (it duplicates tagger + drawio with a worse taxonomy) |
| `graphdb_connector.py` | **split** into `ground/` + `emit/owl` + `emit/jsonld` + `publish/graphdb` |
| `src/tools/owl_emitter.py` (stub) | replace with harvested `graphdb_connector` logic |
| `mds_onto.json`, `cemento-templates.xml` | keep as palette assets (rename `mds_onto.json` — it's a draw.io library, not an ontology) |
| `outputs/`, `schemas/` | gitignore; keep a curated few schemas |

## Suggested fix order
1. P1 (taxonomy) + P5 (namespace) — quick correctness fixes.
2. P2 + P3 — wire ontology/JSON-LD into one ordered pipeline (your Steps 4→5).
3. P9 + P10 + P11 — delete duplicates, rename, trim deps.
4. P4 — add REBEL (Step 2) then LoRA (Step 6).
5. P8 — resilience (retry/checkpoint) once the flow is correct.
