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
                                   └────────────┘       └─────────────┘       └────────────┘
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
domain. (Entity resolution between REBEL triples and concepts is the place to deepen
this — see the stub in `rebel.merge`-style logic / `knowledge_base`.)

## Step 4 — Ontology (OWL 2 TTL)  →  validation gate
`kw/ontology.py` builds an OWL 2 / MDS-Onto-compliant Turtle ontology:
- Declares `mds:Concept` and subclasses (`Measurement`, `Material`, `Process`,
  `Device`, `Characterization`, `Reliability`, `Sample`, `Economics`).
- Each schema column becomes a property IRI; each concept is classified into a branch.
- Namespace is resolved per domain (e.g. `…/mds/characterization/electronmicroscopy/`).

Output: `outputs/<slug>/<slug>_onto.ttl`.
**Gate** (`kw/validate.py`): parses the TTL, computes alignment % to BFO/CCO/MDS, and
(stubs for) reasoner consistency + OOPS! pitfalls. A run reports PASS/CHECK.

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
| `lora_adapters/run-<…>/` | LoRA dataset + manifest (+ adapter when trained) |

All files share one version tag (`v8`) and a readable slug. REBEL triples are written
only when REBEL is installed; the LoRA folder is written every run (dataset always,
adapter when training deps are present).
