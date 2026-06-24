# Knowledge Base — knowledge_workflow

A recursive synthesis of all material in this repository, written to support a
clean, modular rebuild. Read in order, or jump to what you need.

| Doc | Purpose |
|-----|---------|
| [01_inventory.md](01_inventory.md) | Every file and folder, what it is, keep/retire |
| [02_current_architecture.md](02_current_architecture.md) | How the system actually works today (two pipelines + a stranded OWL emitter) |
| [03_components.md](03_components.md) | Module-by-module responsibilities and interfaces |
| [04_data_models_and_ontologies.md](04_data_models_and_ontologies.md) | Pydantic contracts, CSV shapes, ontology grounding, namespaces |
| [05_lessons_learned.md](05_lessons_learned.md) | What hurts today — the case for the refactor |
| [06_target_architecture.md](06_target_architecture.md) | Proposed modular package + migration map |
| [07_glossary.md](07_glossary.md) | Domain and project terms |

## The one-paragraph summary

`knowledge_workflow` pulls curated papers from a Zotero group library and turns
them into structured knowledge. It has evolved through **six versions** (V1 spaCy →
V6 MDS-tagging), and the current direction is a modular `src/` package exposing two
pipelines: **Extraction** (concepts → normalized list → wide-format schema with
source quotes) and **Enrichment** (MDS-Onto study-stage / supply-chain tagging →
draw.io concept map). A **third capability — OWL 2 Turtle + JSON-LD emission — already
exists** but lives in a standalone script (`graphdb_connector.py`), disconnected from
the package. The refactor's job is to unify these scattered capabilities into one
pluggable pipeline (extract → ground → emit → validate → publish), add BFO/CCO grounding
and validation, and retire the V1–V6 monoliths and duplicated git worktrees.

## Most important finding

The "committee-ready ontology" output the project wants is **not missing — it's
fragmented**. `graphdb_connector.py` builds MDS-Onto-grounded OWL TTL + per-paper
JSON-LD today; `cemento_connect.py` builds the draw.io maps; `src/` does extraction.
Three entry points, heavy duplication, no shared data contract, no validation gate.
Consolidation — not greenfield reinvention — is the win.
