# 07 — Glossary

## Project / pipeline terms
- **Collection** — a Zotero collection (group library `2189702`); the unit a run processes.
- **Phase 1 (concept extraction)** — per-abstract extraction of top-N concepts.
- **Phase 2 (schema population)** — full-text mining of a value + source quote per concept.
- **Normalization** — LLM dedupe/merge of raw labels into 30–80 clean ontology terms.
- **Enrichment (V6)** — tagging concepts with MDS study stage + supply-chain level, then a draw.io map.
- **canonical vs paper_term** — canonical = normalized label; paper_term = surface term as written in a given paper.
- **value | quote** — the packed cell format in `schema_*.csv` (extracted value + supporting sentence).
- **Wide-format schema** — one row per paper, one column per concept.
- **Concept table** — the flat Phase-1 output (paper × concept rows).

## MDS-Onto vocabulary
- **MDS-Onto** — Materials Data Science ontology from Case Western SDLE (`cwrusdle.bitbucket.io/mds`). The mid-level ontology runs ground to.
- **Study stage** — sample, tool, recipe, pre-processing, analysis, modeling, results-publishing.
- **Supply-chain level** — materials, subcomponent, component, assembly, subsystem, system.
- **SDLE** — Solar Durability and Lifetime Extension (Case Western research center).

## Standards & tools
- **OWL 2** — Web Ontology Language; the ontology output format (DL profile target).
- **RDF / Turtle (TTL)** — triple data model / its text serialization.
- **JSON-LD** — JSON serialization of RDF; per-paper instance docs + `all.jsonld`.
- **BFO** — Basic Formal Ontology (ISO/IEC 21838-2 upper ontology).
- **CCO** — Common Core Ontologies (mid-level, built on BFO).
- **PMD** — Platform MaterialDigital core ontology (used in `gaas_onto.ttl`).
- **QUDT** — Quantities, Units, Dimensions, Types vocabulary.
- **Cemento** — a draw.io-based ontology drawing tool; `cemento-templates.xml` is its shape library.
- **GraphDB** — RDF triplestore; the JSON-LD bulk-import target.
- **SHACL** — Shapes Constraint Language; validates graph structure.
- **OOPS!** — OntOlogy Pitfall Scanner.
- **ROBOT / ELK / HermiT** — OWL tooling / reasoners for consistency checking.
- **Reasoner consistency** — no logical contradictions / unsatisfiable classes.
- **Alignment %** — fraction of classes that subclass a BFO/CCO/MDS parent.

## New-direction terms (project brief)
- **REBEL** — seq2seq (BART) model that emits flat S-P-O triplets from text; runs in parallel with the LLM.
- **LoRA-LLaMA** — a LoRA-fine-tuned LLaMA for strict nested-JSON / schema extraction; the learning component.
- **Routing** — deciding per segment whether prose → REBEL or specs → LoRA.
- **Entity resolution (merge)** — collapsing the same real-world thing named in different streams to one node/URI.
- **Provenance** — source paper + span, tool, model+version, seed, confidence attached to each assertion.

## Tech stack
`uv` (Python ≥3.13), `pydantic` + `pydantic-ai` (structured LLM output via `result_type`),
`OpenAIModel` (provider-agnostic LLM), `pyzotero`, `pypdf`/`fitz`, `pandas`, `rdflib`
(in the OWL path), `instructor` (legacy V3), `keybert`/`spacy`/`scikit-learn` (legacy V1/V2),
`shiny` (UI prototype), `fastmcp` (MCP).
