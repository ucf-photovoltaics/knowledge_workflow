# Stage 5: Interoperate, export and validate (`interop`)

Commits external mappings, tags MDS-Onto facets, builds the OWL ontology and the literature layer, and validates them structurally. Agent: `src/agents/interoperability.py`; export `tools/owl.py`, `tools/bottomup.py`. Command: `python -m src.run interop --run-id ID`.

## Steps

1. **Mappings.** Local tier: a screening call keeps candidates about the same or a broader thing (label-matched candidates are never screened out), then a relation call. Frontier: one call. Relations: `owl:equivalentClass`, `rdfs:subClassOf`, `skos:exactMatch`, `skos:closeMatch`.
   - Exact and equivalent are kept only for label or synonym matches, otherwise downgraded to close.
   - QUDT quantity kinds and units are individuals: equivalent/subclass downgraded to SKOS.
   - A label-matched candidate the model skipped is added as exact when its similarity is >= 0.85.
   - Every mapping records confidence and source (model or label match).
2. **Facets.** One or two of MDS-Onto's study stages and an MDS domain and subdomain for every class and local property; MDS-Onto's own facets on matched terms are hints; untagged items default by type. Rows left out are retried once.
3. **OWL export.** One ontology per domain run (`<ONTOLOGY_IRI><domain>`), Turtle and JSON-LD. Imports only the BFO/CCO terms used plus their ancestor chains (from the cached `resources/upper/bfo_cco.json`). Classes carry labels, alternative labels, definitions with `kw:definitionStatus` and `kw:definitionSource`, `dcterms:source` DOIs and facets; restrictions carry support, evidence quote, condition and sources as axiom annotations.
4. **Literature layer** (`domain_layer.ttl`/`.jsonld`). A SKOS concept scheme built only from the corpus: `skos:broader` from extracted is-a and lexical heads; every relation and causal claim as a link plus a `kw:Claim` node (support, evidence, conditions, sources, `kw:evidenceStatus "unevidenced"` when it has no quote); every value as `kw:ReportedValue` (`kw:ofConcept`, `kw:measuredOn`, `kw:propertyMissing`). Relation predicates use the RO/BFO/CCO IRI where one fits. Each concept links to its ontology class.
5. **Validation** (structural, no reasoner): JSON-LD round trip keeps the triple count; superclass, equivalent, disjoint and restriction targets declared; every predicate declared; no punning; every local class labelled, labels unique; no subclass cycle; every local class reaches BFO entity.

## Outputs

`ontology.ttl`, `ontology.jsonld`, `domain_layer.ttl`, `domain_layer.jsonld`, `ontology/{mappings,facets,validation,metrics,domain_layer_metrics}.json`, `ontology_report.md`.

## Checks and limits

- Passing validation means the file is well formed and internally consistent. It says nothing about whether the classes, parents, definitions or mappings are correct.
- A duplicate-label failure usually traces back to two concepts that differ only in type; check `type_conflicts` and `types_settled_by_model` in the same run.
