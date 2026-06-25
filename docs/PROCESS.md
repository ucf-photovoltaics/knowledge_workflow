# The Knowledge Workflow Process

End-to-end: a curated Zotero library of papers becomes **two deliverables** —
a GraphDB-ready ontology repo and a cemento draw.io diagram. One command runs it:
`python -m kw run -c <collection_id>`.

```
Zotero collection
      │
      ▼
 ┌──────────┐   abstracts    ┌──────────┐   full text   ┌──────────┐
 │  INPUT   │──────────────▶ │ CONCEPTS │ ────────────▶ │   MINE   │
 │ (mode)   │                │ (Step 1) │               │ (Step 2) │
 └──────────┘                └──────────┘               └────┬─────┘
   supervised: provided list   normalize 30–80           LLM values+quotes
   unsupervised: auto                                     + REBEL triples
                                                               │
                                            consolidate (Step 3)│
                                                               ▼
                                                        ┌──────────────┐
                                                        │  ONTOLOGY    │  Step 4
                                                        │  OWL 2 TTL   │  (validation gate)
                                                        └──────┬───────┘
                                          ┌────────────────────┼────────────────────┐
                                          ▼                    ▼                     ▼
                                   ┌────────────┐       ┌─────────────┐       ┌────────────┐
                                   │  JSON-LD   │       │   DIAGRAM   │       │   LoRA     │
                                   │  Step 5    │       │  Step 5b    │       │  Step 6    │
                                   │ GraphDB    │       │ cemento     │       │ fine-tune  │
                                   └─────┬──────┘       └─────────────┘       └────────────┘
                                         ▼
                                   ┌────────────┐
                                   │  VISUAL    │  Step 7  (interactive graph + benchmark)
                                   └────────────┘
```

**Ordering invariants** (enforced in `kw/pipeline.py`): JSON-LD, the diagram, and the
LoRA fine-tune all run **only after** the ontology is built. REBEL runs **together**
with the LLM during mining — not as a separate router.

## Step 0 — Input
Pull the collection from Zotero (`kw/zotero.py`), returning, per paper:
`{key, title, doi, abstract, date, authors, full_text}` (PDF text via `pypdf`).

Two modes:
- **Unsupervised** — no concept list supplied; Step 1 generates it from abstracts.
- **Supervised** — you pass `--concepts list.csv`; Step 1 is skipped and your list is used.

## Step 1 — Concepts (unsupervised only)
`kw/extract.py`:
1. **Per-abstract extraction** — each paper's abstract yields concepts as
   `(canonical label, paper-specific term, relevance)`.
2. **Normalization** — all canonical labels are deduped/merged into a clean shared
   list of ~30–80 ontology-ready terms.

Output: `outputs/<slug>/concepts_<…>.csv`.

## Step 2 — Mine each paper (LLM + REBEL together)
For every paper, using the **full text** and **all** concepts:
- **LLM** (`extract.build_schema_rows`) returns, per concept, the paper-specific
  `value` and a source `quote` ("value | quote").
- **REBEL** (`kw/rebel.py`) extracts exact S-P-O triples as stated in the text.
  (Safe no-op if the REBEL model isn't installed.)

Output: `outputs/<slug>/schema_<…>.csv` (wide format: domain, doi, one column per concept).

## Step 3 — Consolidate
The normalized concept set + mined values define the **final ontology terms** for the
domain. REBEL output is reconciled, not blindly unioned:
- `kw/relations.py` maps REBEL predicates onto the MDS relation vocabulary
  (`relations.normalize_triples`) and reports coverage.
- `kw/merge.py` performs entity resolution (`merge.resolve`, gated by `MERGE_REBEL`,
  similarity threshold `MERGE_SIM_THRESHOLD`) so a thing named in prose and in a
  relation becomes one node.
- `kw/mdsonto.py` grounds concepts to real MDS-Onto IRIs via the OntoPortal API
  (`mdsonto.resolve_concepts`); active only when configured.

## Step 4 — Ontology (OWL 2 TTL)  →  validation gate
`kw/ontology.py` builds an OWL 2 / MDS-Onto-compliant Turtle ontology:
- Declares `mds:Concept` and subclasses (`Measurement`, `Material`, `Process`,
  `Device`, `Characterization`, `Reliability`, `Sample`, `Economics`).
- Each schema column becomes a property IRI; each concept is classified into a branch.
- Namespace is resolved per domain (e.g. `…/mds/characterization/electronmicroscopy/`).

Output: `outputs/<slug>/<slug>_onto.ttl`.

**Validation gate** (`kw/validate.py`) — a registry of checks, each **required** or
**advisory**. The gate PASSES only when every required check passes; strict semantics
mean a required check that errors or cannot run counts as not-pass.

- **Required (block the MDS-Onto upload):**
  - `ontocheck` — the CWRU SDLE [OntoCheck](https://pypi.org/project/OntoCheck/) suite.
    Gate metrics: `duplicateLabels`==0, `missingDomainRange` (0 missing domain & range),
    `mdsDesignCheck` coverage ≥ `MDS_DESIGN_TARGET` (0.90), `humanLicense`==1,
    `isolatedElements`==0, and definition coverage ≥ `DEFINITION_COVERAGE_TARGET` (0.90).
    All other OntoCheck metrics run as advisory.
  - `oops` — OOPS! scan; fails on any critical pitfall.
- **Advisory (reported, never block):** `alignment` % to BFO/CCO/MDS/PMD, `reasoner`
  (opt-in), `shacl` (opt-in), and the non-gate OntoCheck metrics.

Every run writes a detailed **`validation_report.md`** (+ `.json`) into the output
folder: a PASS/FAIL banner, whether the upload is allowed, and per-check / per-metric
findings. The MDS-Onto upload in Step 5/portal runs **only** when the gate passes; the
run otherwise finishes normally and produces all local artifacts.

Which checks are required is configurable via `REQUIRED_CHECKS` (default
`ontocheck,oops`). The next planned required check is **TTL-PAWIKAN** — it slots in as
another registry entry.

## Step 5 — JSON-LD (the GraphDB repo)  *after the ontology*
`kw/ontology.py` emits one JSON-LD document per paper (typed `mds:ResearchPublication`,
with each concept as an `mds:hasConcept` node carrying value/quote/relevance), then a
combined `all.jsonld` for bulk import.

Output: `outputs/<slug>/<paper>.jsonld` × N + `outputs/<slug>/all.jsonld`.
**This folder is the GraphDB-ready repo** — push it and import `all.jsonld`.

## Step 5b — Diagram (the cemento draw.io)  *after the ontology*
`kw/tagger.py` tags each concept with MDS `studyStage` + `supplyChainLevel`
(single-source taxonomy in `kw/taxonomy.py`), then `kw/drawio.py` lays out a concept
map coloured by study stage and embeds the **MDS-Onto** and **Cemento** template
libraries as palette pages.

Output: `outputs/<slug>/enriched_<…>.csv` + `outputs/<slug>/diagram_<…>.drawio`.
**Open this in draw.io / cemento.**

## Step 6 — LoRA fine-tune  *after the ontology*
`kw/lora.py` builds a supervised dataset from the **final ontology terms** + the mined
(text → value) pairs, then fine-tunes a LoRA adapter on the base model so future runs
improve. Updates once per finished ontology. Training is **guarded**: with
`peft`/`torch` (+ a GPU) it trains and saves an adapter; otherwise it writes the dataset
+ manifest (`status: dataset-only`) so the run still completes.

Output: `lora_adapters/run-<…>/lora_dataset.jsonl` + `lora_manifest.json` (+ adapter when trained).

## Step 7 — Visual + benchmark  *last; never breaks the run*
`kw/visualize.py` reads `all.jsonld` and renders an interactive `graph.html`
knowledge-graph view (+ `graph_report.md`), then appends a one-row summary of the run to
the cumulative `eval/graph_benchmark.csv`. Skipped with `--no-visual` or
`EMIT_VISUAL=false`, and wrapped in try/except so a visualization error can never fail an
otherwise-complete run. (The richer merged graph in `kw/graphview.py` — used by the
shiny explorer and `kw/gephi.py` — is a separate, standalone view, not part of the run.)

Output: `outputs/<slug>/graph.html` + `graph_report.md`; one appended row in `eval/graph_benchmark.csv`.

## What a run produces (in `outputs/<slug>/`)
| File | Purpose |
|------|---------|
| `concepts_<…>.csv` | Step 1 flat concept table (unsupervised) |
| `schema_<…>.csv` | Step 2 wide schema (value + quote) |
| `<slug>_onto.ttl` | OWL 2 ontology (GraphDB) |
| `<paper>.jsonld`, `all.jsonld` | JSON-LD instances (GraphDB import) |
| `rebel_triples.jsonld`, `triples_<…>.csv` | REBEL relations, as stated in text (GraphDB import) |
| `enriched_<…>.csv` | concepts + MDS tags |
| `diagram_<…>.drawio` | cemento concept map |
| `graph.html`, `graph_report.md` | Step 7 interactive graph + report |
| `validation_report.md`, `validation_report.json` | Step 4 gate verdict + per-check findings |
| `ontocheck_scores.csv`, `ontocheck.log` | OntoCheck's own per-metric scores + detailed log |
| `<slug>.log` | per-run log (stdout + log records) |
| `lora_adapters/run-<…>/` | LoRA dataset + manifest (+ adapter when trained) |

All files share one version tag (`v8`) and a readable slug. REBEL triples are written
only when REBEL is installed; the LoRA folder is written every run (dataset always,
adapter when training deps are present).
