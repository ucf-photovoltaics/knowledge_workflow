# 08 — Authoritative Pipeline Spec

**This is the single source of truth for the pipeline.** It encodes the defined
logic flow exactly. Anything in the codebase that contradicts it is a bug to fix
(see [09_problems_and_dedup.md](09_problems_and_dedup.md)). Design rule: **one linear
flow, one owner per step, no unnecessary complexity.**

> **AS BUILT (post-refactor).** This spec is now realized by the flat `kw/` package
> (`kw/pipeline.py` is the runner). Each step's owner is a `kw/*.py` module, not the
> pre-refactor `src/`/`graphdb_connector` paths still named in the "today" columns below
> (kept as the migration record). Two deltas from the original plan: the **draw.io
> diagram is emitted by default** (Step 5b, skippable with `--no-diagram`), and **REBEL
> persists its triples** (`rebel_triples.jsonld`) into the GraphDB repo. Owner map:
> Input→`zotero.py`, Concepts/Mine→`extract.py` (+`rebel.py`), Consolidate/Grounding→
> `tagger.py`/`ontology.py`, Ontology+JSON-LD→`ontology.py`, Validate→`validate.py`,
> Diagram→`drawio.py`, LoRA→`lora.py`.

## The flow (one line)
```
INPUT(mode) → CONCEPTS → MINE(LLM + REBEL) → CONSOLIDATE → ONTOLOGY → JSON-LD → LoRA
```

Two hard ordering invariants:
- **JSON-LD is emitted only after the ontology is created.**
- **LoRA fine-tunes only after the ontology is finished.**

REBEL and the LLM run **together** during mining (not routed, not alternated).
LoRA is a **terminal training step**, not a live extractor. (This supersedes the
earlier REBEL-vs-LoRA *router* design — that added complexity the flow doesn't need.)

## Step 0 — Input mode
| Mode | Input | Effect |
|------|-------|--------|
| **Unsupervised** | Zotero collection only | concept list is auto-generated (Step 1) |
| **Supervised** | Zotero collection + provided concept list | Step 1 is skipped; provided list is used as-is |

Owner: `io/sources/zotero.get_collection_with_text` (today: `src/tools/zotero_client.py`).
Returns the uniform corpus contract `{title: {key, title, doi, abstract, date, authors, full_text}}`.

## Step 1 — Concept list (unsupervised only)
Use **abstracts** to generate the shared concept list.
1. Per-abstract concept extraction (canonical label + paper term).
2. Normalize/dedupe across the corpus → 30–80 shared ontology terms.

Owner: `extract/concepts.py` + `extract/normalize.py`
(today: `src/agents/extractor.py`, `src/agents/normalizer.py`). **Already works.**
Input: abstracts. Output: `concept_list: list[str]`.

> Supervised mode loads the provided list here and skips extraction/normalization.

## Step 2 — Mine each paper (LLM + REBEL, in parallel)
For **each paper**, using **all** concepts from Step 1:
- **LLM** pulls the paper-specific value + source quote for every concept.
- **REBEL** is called to extract exact S-P-O triples as stated in the text.

Both outputs are kept **in memory** as typed objects (not CSV) and associated with
the paper for provenance.

Owner: `extract/schema.py` (LLM, today `src/agents/schema_builder.py`, **works**) +
`extract/rebel.py` (REBEL, today a **stub** — net new).
Input: `full_text` + `concept_list`. Output per paper: `{concept: value/quote}` + `list[Triple]`.

> Use full text for mining (abstracts were only for Step 1). REBEL captures
> relational/causal facts the per-concept LLM pass may miss; the LLM captures
> values for the known concept slots. Together = richer, exact extraction.

## Step 3 — Consolidate
Merge the per-paper results across the corpus into the **final ontology terms**:
- Reconcile concepts and REBEL entities by entity resolution (one node per real thing).
- Settle the final class/property/term set for the domain.

Owner: `extract/merge.py` + `ground/` (today: partly in `normalizer` + the classify
logic inside `graphdb_connector._classify_concept`). Output: the consolidated term set.

## Step 4 — Build the ontology
Construct the OWL 2 ontology from the consolidated terms, grounded in **MDS-Onto**,
then **CCO/BFO** where MDS lacks a parent. (MDS study-stage / supply-chain tagging,
if used, happens **here** as grounding metadata — not as a separate pipeline.)

Owner: `ground/*` + `emit/owl.py`
(today: `graphdb_connector.build_collection_ontology` — harvest, don't rewrite).
Output: `{domain}_onto.ttl`.
Gate: must pass `validate/` (reasoner consistency + OOPS! + alignment %) before proceeding.

## Step 5 — Emit JSON-LD  *(only after Step 4)*
With the finished ontology, emit per-paper JSON-LD instance documents from the mined
data, plus a combined `all.jsonld`.

Owner: `emit/jsonld.py` (today: `graphdb_connector.row_to_jsonld` — harvest).
Output: `{paper}.jsonld` × N + `all.jsonld`.

## Step 6 — Fine-tune LoRA  *(only after Step 4)*
Fine-tune the LoRA model on the **final ontology terms**. The adapter updates **once
per finished ontology**, so future runs extract/ground new material better.

Owner: `train/lora.py` (net new). Input: final ontology terms (+ prior ontologies).
Output: a new pinned LoRA adapter version.

## What is intentionally NOT in the core flow
- **Draw.io diagrams** — a visualization side-output. *As built:* emitted **by default**
  as Step 5b (`kw/drawio.py`), skippable with `--no-diagram`; still not a dependency of
  the ontology/JSON-LD path.
- **A live agent loop / planner** — the flow is linear; don't build orchestration it doesn't need.
- **REBEL-vs-LoRA routing** — superseded; REBEL+LLM run together, LoRA trains at the end.

## Canonical owner per step (kills the duplication)
| Step | Canonical source today | Retire / merge |
|------|------------------------|----------------|
| Input | `src/tools/zotero_client.py` | — |
| Concepts | `src/agents/extractor.py` + `normalizer.py` | monolith copies |
| Mine (LLM) | `src/agents/schema_builder.py` | monolith copies |
| Mine (REBEL) | `src/agents/rebel_extractor.py` (stub) | — |
| Consolidate | `normalizer` + `graphdb_connector._classify_concept` | — |
| Ontology | `graphdb_connector.build_collection_ontology` | `src/tools/owl_emitter.py` stub |
| Grounding/tags | `src/agents/tagger.py` (12-stage) | **`cemento_connect.py` tagger (7-stage) — delete** |
| JSON-LD | `graphdb_connector.row_to_jsonld` | — |
| Draw.io (optional) | `src/tools/drawio_builder.py` | **`cemento_connect.py` drawio — merge its library-embed, then delete** |
| LoRA | net new | — |

## Run, end to end (target)
```bash
# unsupervised
python -m knowledge_workflow run --collection <id>
# supervised
python -m knowledge_workflow run --collection <id> --concepts schemas/<domain>.csv
# → concepts → mine → consolidate → ontology (validated) → jsonld → lora
```
