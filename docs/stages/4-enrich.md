# Stage 4: Enrich (`enrich`)

Adds definitions, alternative labels, restrictions, disjointness and external mapping candidates. Agent: `src/agents/enrichment.py`. Command: `python -m src.run enrich --run-id ID`.

## Steps

1. **Mapping candidates.** Portal searches (MDS-Onto portal: MDS-Onto, IOF, PMDCO, QUDT; MatPortal when `MATPORTAL_API_KEY` is set) with cleaned queries: exact label, full label, general term, spelled-out abbreviation. Local BFO/CCO classes with the same label and the nearest by embedding are added. Candidates are re-ranked by embedding similarity; label matches and those at cosine >= 0.6 are kept, up to 8 per class. Portal results are cached in `outputs/cache/{mds,matportal}`; a failed portal is logged and skipped.
2. **Causal restrictions** (deterministic). Each causal edge keeps a local polarity property (influences > increases, decreases, causes, enables, prevents) and gets the first RO and CCO property whose rule fits the cause and effect BFO categories (`causal_rules` in `menus.json`), with RO "causally related to" as fallback. Polarity, support, evidence and conditions are kept as axiom annotations.
3. **Relation restrictions from predicates** (deterministic). A relation whose predicate an RO/BFO/CCO property formalizes (`upper.RELATION_GROUPS`), with a verified quote, becomes a restriction with the first property in its group whose declared domain and range fit the two classes. Unevidenced relations never become restrictions.
4. **Model passes** (rows left out are retried once in half-size batches):
   - Local tier: `definitions`, `synonyms`, `restrictions` (only relations not handled in step 3), `disjointness`, batches of 25 (50 for synonyms).
   - Frontier tier: one combined call per batch of 25.
5. **Definitions.** Each class row carries paper definitions, relations and up to 3 evidence quotes. The model returns a definition in genus-differentia form and its `basis`. Status:
   - `supported`: a paper definition supports it at the label's generality;
   - `draft_evidence`: written only from the given relations and quotes;
   - `model_generated`: from general domain knowledge, accepted only on profiles in `MODEL_DEFINITION_PROFILES` (the Gemini profiles);
   - `none` (empty) or `unreviewed` (no answer).
   `definition_source` records `profile:model`. `category_conflict` flags a parent that contradicts the concept.
6. **Checks.** Model restrictions must trace back to an extracted relation and fit the property's domain and range; disjointness only between siblings, and dropped where a paper states is-a between the pair. Local property domain and range = most specific common ancestor of the classes that use them.
7. **Review artifacts.** `review_issues.json` (unsupported definitions, unresolved placements, conflicts) and `cross_domain_candidates.json` (same-label classes in completed runs of other domains; suggestions only).

## Outputs

`ontology/enriched.json`, `ontology/properties.json`, `ontology/review_issues.json`, `ontology/cross_domain_candidates.json`.

## Checks and limits

- Reported: `definitions_<status>`, `restrictions_from_predicate`, `restrictions_dropped_{invalid,ungrounded,domain_range,unevidenced,disjoint_vs_is_a}`, row coverage per pass.
- Papers rarely define their terms (development runs found source definitions for about 3% of classes), so `supported` stays low by design; `draft_evidence` and `model_generated` are reported separately and never pooled with it.
- Existential restrictions ("every A has_quality some B") are strong claims drawn from a few papers; they are marked with support and evidence for expert review.
