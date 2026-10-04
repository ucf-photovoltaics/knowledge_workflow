# Stage 3: Ontology placement (`ontology`)

Places each canonical concept under a CCO or BFO class from the ontology store (or a same-name MDS-Onto or PMDCO class), or under another corpus concept, and gives it a stable IRI. Agent: `src/agents/ontology.py`. Command: `python -m src.run ontology --run-id ID`. Needs the ontology store ([docs/ontology-store.md](../ontology-store.md)).

## Steps

1. **Name matches** (deterministic). A concept whose label equals, after normalisation, any label of an MDS-Onto or PMDCO class (`ONTOLOGY_SEARCH["name_match_ontologies"]`, MDS-Onto first) is placed under that class alone. Its route to CCO/BFO is that ontology's own, read from the store; a match whose ancestors do not reach BFO is skipped and counted. Name-matched classes keep their parent through the later checks (no paper is-a or lexical-head move). `name_match_category_conflict` flags a match whose BFO category differs from the concept type's default.
2. **Parent candidates** from the store for every other concept: CCO classes first, then BFO (`parent_ontologies`), found by label, alternative labels and lexical head (exact and trigram) and by the concept's embedding (the three nearest always included), up to 8 (`parents_per_class`); then the default class for the concept's type and, on the local tier, the root of its BFO category. No fixed class menu is shown to the model.
3. **Model placement.** Each row shows the concept with its label, type, alternative labels, up to two source definitions, up to eight extracted relations and its own candidates.
   - Frontier tier: one call per batch of 60 picks the parent (`U:<candidate label>`, a BFO category, or a corpus concept) or excludes the concept.
   - Local tier: pass 1 picks a BFO category (material entity, site, quality, disposition, function, role, process, process profile, information) or "not a class"; candidates are then filtered to that category; pass 2 picks the parent among them and the category's 150 most important corpus concepts. Batches of 25.
   - An answer that is not one of the row's candidates, a category root or a corpus id is not used. Rows the model leaves out are sent once more in half-size batches.
4. **Deterministic checks and repair.**
   - A local parent from another category is replaced by the category root (`category_mismatch`); a pick of another category's root is allowed and counted (`category_override`).
   - No usable answer: the category root (local) or the default parent for the concept's type (`category_default`, `type_default`).
   - Is-a cycles are broken (`cycle_break`); children of excluded concepts move up to the nearest kept ancestor.
   - A verified paper `is_a` edge replaces the model's choice when its BFO category agrees and it creates no cycle (`paper_is_a`); competing or conflicting paper parents are flagged.
   - A concept attached directly to an external class moves under its obvious lexical head ("rear AlOx passivation layer" under "passivation layer") when both share type and category (`lexical_head`).
5. **IRIs.** `<ONTOLOGY_IRI><domain>/class/<Label>_<hash>`, hash of label and type. Stable across reruns of a domain; separate domains never share a class IRI; a duplicate identity stops the run.

## Outputs

`ontology/classes.json` (parent, `parent_source`, IRI, review flags), `ontology/review_issues.json` (unresolved placements, category conflicts, ambiguous paper parents, name-match conflicts).

## Checks and limits

- `placement_*` counts show where each parent came from (`name_match`, `llm`, `paper_is_a`, `lexical_head`, defaults); `ontology_name_matches`, `ontology_parent_candidates_mean` and `parent_candidates_<ontology>` show what the store offered. A hierarchy that is mostly category roots means the model did not answer, not that the concepts have no parent.
- Row coverage (`category_rows_*`, `parent_rows_*`, `hierarchy_rows_*`) is reported. Development runs showed local models silently answering only part of each batch, and answers wrapped in a copy of the JSON schema that were dropped without being counted; both are handled and counted.
