# Stage 3: Ontology placement (`ontology`)

Places each canonical concept under a curated BFO/CCO class or under another corpus concept, and gives it a stable IRI. Agent: `src/agents/ontology.py`. Command: `python -m src.run ontology --run-id ID`.

## Steps

1. **Context.** Each concept is shown with its label, type, alternative labels, up to two source definitions and up to eight extracted relations. The upper-class menu (`resources/upper/menus.json`, BFO 2020 + CCO) and the concept index sit in the system prompt, unchanged across batches so providers can cache them.
2. **Model placement.**
   - Frontier tier: one call per batch of 60 picks the parent (upper class `U:<label>` or a corpus concept) or excludes the concept.
   - Local tier: pass 1 picks a BFO category (material entity, site, quality, disposition, function, role, process, process profile, information) or "not a class"; pass 2 picks the parent among that category's upper classes and its 150 most important corpus concepts. Batches of 25.
   - Rows the model leaves out are sent once more in half-size batches.
3. **Deterministic checks and repair.**
   - A local parent from another category is replaced by the category root (`category_mismatch`); a pick of another category's root is allowed and counted (`category_override`).
   - No usable answer: the category root (local) or the default parent for the concept's type (`category_default`, `type_default`).
   - Is-a cycles are broken (`cycle_break`); children of excluded concepts move up to the nearest kept ancestor.
   - A verified paper `is_a` edge replaces the model's choice when its BFO category agrees and it creates no cycle (`paper_is_a`); competing or conflicting paper parents are flagged.
   - A concept attached directly to BFO/CCO moves under its obvious lexical head ("rear AlOx passivation layer" under "passivation layer") when both share type and category (`lexical_head`).
4. **IRIs.** `<ONTOLOGY_IRI><domain>/class/<Label>_<hash>`, hash of label and type. Stable across reruns of a domain; separate domains never share a class IRI; a duplicate identity stops the run.

## Outputs

`ontology/classes.json` (parent, `parent_source`, IRI, review flags), `ontology/review_issues.json` (unresolved placements, category conflicts, ambiguous paper parents).

## Checks and limits

- `placement_*` counts show where each parent came from; `ontology_unresolved_placements` counts fallbacks. A hierarchy that is mostly category roots means the model did not answer, not that the concepts have no parent.
- Row coverage (`category_rows_*`, `parent_rows_*`, `hierarchy_rows_*`) is reported. Development runs showed local models silently answering only part of each batch, and answers wrapped in a copy of the JSON schema that were dropped without being counted; both are now handled and counted.
