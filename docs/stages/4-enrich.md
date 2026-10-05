# Stage 4: Enrich (`enrich`)

Adds definitions, alternative labels, restrictions, disjointness and the external candidate terms for interop. Every external term comes from the ontology store ([docs/ontology-store.md](../ontology-store.md)) or the MDS-Onto portal grounding search; prompts carry no list of terms. Agent: `src/agents/enrichment.py`. Command: `python -m src.run enrich --run-id ID`.

## Steps

1. **Mapping candidates.**
   - Store search over every ontology (BFO, CCO, RO, QUDT, PMDCO, IOF, MDS-Onto) with the class label, up to three alternative labels and the lexical head (exact and trigram), and the class embedding (label + first source definition).
   - MDS-Onto portal and MatPortal searches over every ontology each portal hosts (`MDS_ONTOLOGIES` and `MATPORTAL["ontologies"]` are `None`; exact label, full label, general term, spelled-out abbreviation; up to 10 hits per query; cached in `outputs/cache/mds` and `outputs/cache/matportal`). A hit for a term in the store gets the store's record and score, flagged with the portal(s) that found it; a hit outside the store is kept only as a facet hint (`portal_only`) and counted per portal and ontology (`candidates.portal_hits_off_store` in `run.json`), which shows which ontologies would be worth adding to the store.
   - Ranked label matches first (any label of the term equals the class label or a kept synonym), then fused score; up to 8 per class (`ONTOLOGY_SEARCH["candidates_per_class"]`).
   - **Propagation.** From each label-matched or strong (fused >= 0.6) candidate, terms one and two mapping hops away in the store are added (up to 6 per class), with score x 0.8 per hop and the path of IRIs and relations. They are offered to the model like any other candidate and never asserted without it.
2. **Causal restrictions** (deterministic). Each causal edge keeps a local polarity property (influences > increases, decreases, causes, enables, prevents) and gets the first RO and CCO property whose rule fits the cause and effect BFO categories (`causal_rules` in `menus.json`), with RO "causally related to" as fallback. Polarity, support, evidence and conditions are kept as axiom annotations.
3. **Property candidates per relation.** For each evidenced, non-is-a relation the store returns object properties by the predicate phrase (exact and trigram) and by the embedding of phrase plus quote; only properties whose declared domain and range fit the two classes are kept (up to 5).
4. **Relation restrictions without a model call.** With a verified quote, a relation becomes a restriction directly when the store settles the property: a fitting candidate carries the predicate's name exactly, or the top candidates tie (fused score within 0.05) and `upper.RELATION_GROUPS` names one of them. Several exact names (RO, CCO and IOF all have "has input") are also a tie that `RELATION_GROUPS` breaks. Unevidenced relations never become restrictions.
5. **Model passes** (rows left out are retried once in half-size batches):
   - Local tier: `definitions`, `synonyms`, `restrictions` (only relations left after step 4 that have candidates; each relation lists its own `P:<ONTOLOGY>:<label>` candidates), `disjointness`; batches of 25 (50 for synonyms).
   - Frontier tier: one combined call per batch of 25, relations with their candidates.
   - A restriction answer that names a property not among that relation's candidates is dropped (`not_a_candidate`).
6. **Definitions.** Each class row carries paper definitions, relations and up to 3 evidence quotes. The model returns a definition in genus-differentia form and its `basis`. Status:
   - `supported`: a paper definition supports it at the label's generality;
   - `draft_evidence`: written only from the given relations and quotes;
   - `model_generated`: from general domain knowledge, accepted only on profiles in `MODEL_DEFINITION_PROFILES` (the Gemini profiles);
   - `none` (empty) or `unreviewed` (no answer).
   `definition_source` records `profile:model`. `category_conflict` flags a parent that contradicts the concept. Interop later replaces any definition that is not `supported` with the definition of an exact or equivalent match (`imported`).
7. **What the paper said stays.** Every restriction keeps the extracted predicate phrase (`phrase`), quote, support and source papers; the OWL export writes them as axiom annotations next to the formal property chosen.
8. **Checks.** Model restrictions must trace back to an extracted relation, use one of that relation's candidates, and fit the property's domain and range; disjointness only between siblings, and dropped where a paper states is-a between the pair. Local property domain and range = most specific common ancestor of the classes that use them.
9. **Review artifacts.** `review_issues.json` (unsupported definitions, unresolved placements, conflicts) and `cross_domain_candidates.json` (same-label classes in completed runs of other domains; suggestions only).
10. **Materials Project** (deterministic, `MATERIALS_PROJECT` in config, `MATERIALS_PROJECT_API_KEY` in `.env`). A class in the BFO category material entity is looked up when its label or a synonym is an mp-id, a chemical formula (TiO2, CdTe, Si3N4), an element name (silicon), or either followed by a material-form word (TiO2 layer, silicon wafer). All-capital names without digits (PV, BSF, PERC) are acronyms, not formulas; gases and process liquids (SiH4, NH3, H2O) are skipped. Up to 3 entries per class, most stable first and within 0.1 eV/atom of the hull: id, formula, crystal system, space group, energy above hull, stability, formation energy, band gap (direct or not, metallic), density, volume per atom, bulk and shear moduli (VRH). They are annotations, never mapping candidates: the OWL export writes `rdfs:seeAlso` to each entry, annotated with these values (band gap, density and moduli carry `qudt:hasUnit`), the query and the database version. Cached in `outputs/cache/materials_project` per database version.

## Outputs

`ontology/enriched.json` (classes with `candidates`, `portal_only`, `materials_project`, restrictions, definitions), `ontology/properties.json`, `ontology/materials_project.json` (every lookup: class, name, query, entries, failures; database version), `ontology/review_issues.json`, `ontology/cross_domain_candidates.json`.

## Checks and limits

- Reported: `candidates_mean_per_class`, `candidates_source_*`, `candidates_ontology_*`, `candidates_hop_*`, `property_candidates_*`, `restrictions_from_predicate`, `restrictions_dropped_{invalid,ungrounded,not_a_candidate,domain_range,unevidenced,disjoint_vs_is_a}`, row coverage per pass. Final definition counts (`definitions_<status>`) are taken after interop's imports.
- Papers rarely define their terms (development runs found source definitions for about 3% of classes), so `supported` stays low by design; `draft_evidence`, `model_generated` and `imported` are reported separately and never pooled with it.
- A relation with no fitting store property is not formalized; it stays in the literature layer. Many store properties declare narrow domains (PMDCO, CCO), so the domain/range filter drops most candidates (`property_candidates_dropped_domain_range`).
- Existential restrictions ("every A has_quality some B") are strong claims drawn from a few papers; they are marked with support and evidence for expert review.
