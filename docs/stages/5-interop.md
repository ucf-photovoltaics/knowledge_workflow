# Stage 5: Interoperate, export and validate (`interop`)

Commits external mappings, imports definitions and labels of matched terms, tags MDS-Onto facets, builds the OWL ontology and the literature layer, and validates them. Agent: `src/agents/interoperability.py`; export `tools/owl.py`, `tools/bottomup.py`. Command: `python -m src.run interop --run-id ID`. Needs the ontology store ([docs/ontology-store.md](../ontology-store.md)).

## Steps

1. **Mappings.** Local tier: a screening call keeps candidates about the same thing, a broader or narrower kind or a closely related thing (label-matched candidates are never screened out), then a relation call. Frontier: one call. The prompt carries only the default relations: equivalent, exact, close, broader, narrower, related (or none); candidates are numbered rows, propagated ones marked "via k hop(s)".
   - The target must be in the store and not deprecated (otherwise dropped and counted).
   - Exact and equivalent are kept only for label or synonym matches, otherwise downgraded to close.
   - `owl:equivalentClass` only to a BFO-aligned class (its store ancestors reach BFO) in the same BFO category as the class; otherwise `skos:exactMatch`.
   - broader is always `skos:broadMatch`; it adds `rdfs:subClassOf` only when the target is a BFO-aligned class whose category is the class's own or above it. narrower and related are `skos:narrowMatch` and `skos:relatedMatch`.
   - Individuals (QUDT quantity kinds and units) get SKOS only; `owl:sameAs` is never written for classes.
   - A label-matched candidate the model skipped (not a propagated one) is added as exact when its similarity is >= 0.85 (`MAPPING["strong_similarity"]`).
   - Every mapping records method, scores (fused, trigram, cosine), confidence, target ontology, hop count and path.
2. **Imported definitions.** A class without a paper-supported definition takes the definition of its equivalent or exact match (equivalent first, then confidence), with status `imported` and the term's IRI as `definition_source`; the replaced draft is kept in `ontology/imported_definitions.json`.
3. **Facets.** One or two of MDS-Onto's study stages and an MDS domain and subdomain for every class and local property; MDS-Onto's own facets on matched terms (also portal hits outside the store) are hints; untagged items default by type. Rows left out are retried once.
4. **OWL export.** One ontology per domain run (`<ONTOLOGY_IRI><domain>`), Turtle and JSON-LD.
   - Labels: `rdfs:label` and `skos:prefLabel` on every class; `skos:altLabel` from the paper synonyms the model kept and from every label of each exact or equivalent match (annotated with the term's IRI as `dcterms:source`); acronyms and spelling variants as `skos:hiddenLabel`.
   - Definitions with `kw:definitionStatus` and `kw:definitionSource`, `dcterms:source` DOIs and facets.
   - Restrictions carry the paper's predicate phrase (`kw:paperPredicate`), support, evidence quote, conditions and sources as axiom annotations.
   - Mappings carry `kw:mappingMethod`, `kw:mappingConfidence`, `kw:mappingScore`, `kw:targetOntology` and, when propagated, `kw:mappingHops` and `kw:mappingPath` as axiom annotations.
   - Imports (MIREOT style): every referenced external term (parents, properties, mapping targets, local property domains and ranges) with its labels, definition, `rdfs:isDefinedBy` and full ancestor chain, from `bfo_cco.json` for BFO/CCO/RO and from the store for everything else, so the file is self-contained.
5. **Literature layer** (`domain_layer.ttl`/`.jsonld`). A SKOS concept scheme built only from the corpus: `skos:broader` from extracted is-a and lexical heads; every relation and causal claim as a link plus a `kw:Claim` node (support, evidence, conditions, sources, `kw:evidenceStatus "unevidenced"` when it has no quote); every value as `kw:ReportedValue` (`kw:ofConcept`, `kw:measuredOn`, `kw:propertyMissing`). Relation predicates use the RO/BFO/CCO IRI where one fits. Each concept links to its ontology class.
6. **Validation** (no reasoner): JSON-LD round trip keeps the triple count; superclass, equivalent, disjoint and restriction targets declared; every predicate declared; no punning; every local class labelled, labels unique; no subclass cycle; every local class reaches BFO entity. Mapping checks: every mapped IRI is in the store; no mapping to a deprecated term; no equivalence or subclass axiom into another BFO category; `owl:sameAs` only between individuals.

## Outputs

`ontology.ttl`, `ontology.jsonld`, `domain_layer.ttl`, `domain_layer.jsonld`, `ontology/{mappings,imported_definitions,facets,validation,metrics,domain_layer_metrics}.json`, `ontology_report.md`.

## Checks and limits

- Reported: `mappings_<relation>`, `mappings_predicate_*`, `mappings_method_*`, `mappings_hop_*`, `mappings_to_<ontology>`, `labels_<origin>_<property>`, `imported_terms_<ontology>`, `interop_check_{dropped_not_in_store,dropped_deprecated,definitions_imported}`.
- Passing validation means the file is well formed and internally consistent. It says nothing about whether the classes, parents, definitions or mappings are correct.
- An imported definition is the source ontology's wording for its own term; it fits the local class only as well as the match does.
- A duplicate-label failure usually traces back to two concepts that differ only in type; check `type_conflicts` and `types_settled_by_model` in the same run.
