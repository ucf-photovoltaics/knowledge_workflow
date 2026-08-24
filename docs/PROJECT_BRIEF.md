# Project Brief — Automated Knowledge Extraction → Committee-Ready Ontologies

*Generated from a scoping interview. Extends the existing v5 knowledge-workflow.*

## One line
Extend v5 so that each run over a curated set of domain papers emits a
**committee-ready OWL 2 domain ontology** (plus JSON-LD instance data) grounded
in **MDS-Onto / CCO / BFO**, using a multi-agent pipeline in which **REBEL**
triple extraction runs in parallel with the LLM and a **LoRA-tuned model**
progressively learns domain vocabulary from prior ontologies.

## Positioning (for the journal paper)
The through-line is **automated knowledge extraction from scientific literature**.
Supporting contributions:
1. **REBEL + LLM in parallel** — REBEL records relations as stated in the paper,
   feeding the LLM's term/knowledge extraction so more causal relationships are captured.
2. **Standards grounding** — BFO / CCO / MDS-Onto alignment for interoperable output.
3. **LoRA learning loop** — reuse existing terms/ontologies to ingest new domains over time.
4. **Human-vs-automated framing** — the cost/difficulty of manual ontology building is
   established **from the literature**; no human study required.

## What exists today (v5)
- `src/agents/`: extractor, normalizer, schema_builder, tagger, orchestrator
- `src/tools/`: zotero_client, csv_writer, drawio_builder
- Flow: Zotero collection → concepts CSV + draw.io diagram
- `gaas_onto.ttl`: example output (GaAs PV), real `bfo:`/`pmd:`/`mds:`/`qudt:` namespaces
- `mds_onto.json`: draw.io shape library (Cemento), not an ontology file

## The delta (this project)
1. **OWL / JSON-LD emitter** — turn schema_builder output into `{domain}_onto.ttl`
   + `{domain}_instances.jsonld`, grounded in `mds:`/`cco:`/`bfo:`.
2. **REBEL parallel extractor** — triples alongside LLM concept/term extraction;
   merged by entity resolution (not blind union).
3. **Structural evaluation** — reasoner consistency, OOPS! pitfalls, % classes
   aligned to BFO/CCO/MDS.
4. **LoRA learning loop** — fine-tune on (text → ontology-grounded structure) seeded
   by MDS-Onto + past runs; must extend *beyond* MDS-Onto.
5. **Publish workflow** — push ontology + JSON-LD to a GitHub repo → load into a
   GraphDB sandbox.

## Inputs
- Corpus: curated domain papers (any N). **Abstracts** for a content sketch,
  **full text** for extraction.
- Grounding: MDS-Onto (`https://cwrusdle.bitbucket.io/mds#`), CCO, BFO.
- LoRA seed: MDS-Onto examples + prior pipeline runs.

## Output
- `{domain}_onto.ttl` (OWL 2) + `{domain}_instances.jsonld`
- Pushed to GitHub → GraphDB sandbox.

## Success criteria (structural — defensible in 2 weeks)
- **OWL 2 DL**: passes a reasoner (HermiT/ELK) with no inconsistencies or
  unsatisfiable classes.
- **OOPS!**: no critical pitfalls.
- **Alignment**: a target % of classes trace up to a BFO/CCO/MDS parent.
- **Reproducible**: pinned model + seed, logged routing and provenance.

## Scope for the 2-week deadline
**MVP (must-have):** OWL/JSON-LD emitter + structural-eval harness + REBEL-parallel
triples + publish-to-GitHub/GraphDB. One domain end-to-end (reuse GaAs PV as the test case).

**Stretch:** LoRA fine-tune loop (v0). If data/time are short, ship the *design* + a
small proof-of-concept and frame full training as future work in the paper. This is
the largest feasibility risk — keep it off the critical path.

## 2-week milestone plan
**Week 1**
- Days 1–2: OWL emitter (schema rows → `.ttl` grounded in mds/cco/bfo) + JSON-LD instances.
- Days 3–4: structural-eval harness (reasoner + OOPS! + alignment %).
- Day 5: REBEL parallel extractor integrated; triples merged into concept extraction.

**Week 2**
- Days 6–7: publish workflow (GitHub push + GraphDB load); one full domain run end-to-end.
- Days 8–9: LoRA loop v0 *or* its documented design + POC.
- Day 10: results tables (structural metrics), draft methods + evaluation sections, polish class deliverable.

## Top risks
- **LoRA training data volume** — mitigate by scoping LoRA as stretch.
- **OWL emitter correctness** — mitigate by running the reasoner on every run (fail fast).
- **REBEL/LLM merge** is entity resolution, not union — one node per real-world thing.
