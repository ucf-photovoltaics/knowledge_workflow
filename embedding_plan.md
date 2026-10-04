# Embedding plan: ontology store for enrichment and interop

Status: approved 2026-10-04 with the decisions below; not implemented yet.

Goal: the enrichment and interoperability stages take every external term (classes, properties, individuals) from a local ontology store with label, fuzzy and embedding search over BFO, CCO, RO, QUDT, PMDCO, IOF and MDS-Onto, plus the existing MDS-Onto portal grounding call. Prompts carry only a general default vocabulary; concrete terms reach the model only as candidates retrieved for that row. Attach as many labels, equivalences, close, broader and narrower matches as the checks allow.

Note on Oxigraph: Oxigraph has no built-in full-text, fuzzy or vector search (open request: https://github.com/oxigraph/oxigraph/issues/48). It is used as the triple store; fuzzy label search and embeddings live in two sidecar indexes next to it.

## 1. Build the store once, reuse it

New module `src/tools/ontostore.py`; command `python -m src.run ontologies build|status|search`.

- **Sources** (`ONTOLOGY_SOURCES` in `src/config.py`): BFO 2020 core, CCO merged, RO, QUDT (quantity kinds and units), PMDCO, IOF core, MDS-Onto. Files cached in `outputs/cache/ontologies` (BFO, CCO, IOF, PMDCO and QUDT are already there). A manifest records URL or path, version and SHA-256 per file.
- **Oxigraph** (`pyoxigraph`, on disk under `outputs/cache/oxigraph/`): one named graph per ontology, so every candidate carries its source. Ancestors, domain and range, inverses and existing mappings are SPARQL queries.
- **Term index** (SQLite next to the store), built by SPARQL over each graph, for classes, object, datatype and annotation properties, and individuals:
  - labels: `rdfs:label`, `skos:prefLabel`, `skos:altLabel`, `skos:hiddenLabel`, oboInOwl exact/related synonyms, IAO alternative term, QUDT symbols;
  - definitions: `skos:definition`, IAO definition (`IAO_0000115`), `rdfs:comment`;
  - named parents (`rdfs:subClassOf`, `rdfs:subPropertyOf`), domain and range, deprecation;
  - the term's own mappings: `owl:equivalentClass`, `owl:sameAs`, `skos:exactMatch`, `closeMatch`, `broadMatch`, `narrowMatch`.
- **Fuzzy search**: SQLite FTS5 index with the trigram tokenizer over all labels, plus a normalised exact-label lookup.
- **Embeddings**: one vector per term (label + alternative labels + start of the definition) with `EMBED` (`nomic-embed-text`), saved beside the store with the model name and a hash of the text recipe; rebuilt only when sources or model change.
- **Search** returns candidates ranked by fusing three signals: exact label match, fuzzy trigram score and embedding cosine. Each candidate carries ontology, kind, labels, definition, parents and the method(s) that found it.

## 2. Enrichment: candidates only from the store and the MDS-Onto API

- **Kept**: the MDS-Onto portal grounding call, unchanged. Its results join the candidate pool, flagged `portal`.
- **Replaced**: MatPortal search, the fixed nearest-BFO/CCO lookup and the `resources/upper/bfo_cco.json` lookups. Per class the store is queried with the label, alternative labels and the head term; results are fused across ontologies and kept by thresholds in a new `ONTOLOGY_SEARCH` setting (candidates per class, minimum fused score, minimum cosine).
- **Restriction properties**: the curated PROPERTIES menu leaves the prompts. Each relation gets its top property candidates from the store (embedding of the predicate phrase plus its quote against property labels and definitions). A property is used only when the store's domain and range fit the two classes.

## 3. Prompts keep only a general default vocabulary

- Mapping relations: equivalent, exact, close, broader, narrower, related, none.
- Annotation properties: `rdfs:label`, `skos:prefLabel`, `skos:altLabel`, `skos:definition`.
- Datatypes: basic XSD types for reported values.
- Every concrete external term or property appears only as a numbered candidate retrieved for that row. The model chooses among candidates; it never proposes terms.

## 4. Interop: attach as much as possible, each with source and check

- **Labels**: `rdfs:label` and `skos:prefLabel` on every class; `skos:altLabel` from the paper synonyms the model kept and from every label of each exactly or equivalently matched external term (annotated with that term's IRI as source); acronyms and spelling variants as `skos:hiddenLabel`.
- **Mappings**:
  - `skos:exactMatch`, `skos:closeMatch`, `skos:broadMatch`, `skos:narrowMatch`, `skos:relatedMatch`;
  - `owl:equivalentClass` and `rdfs:subClassOf` to external classes only when the BFO categories agree, computed through store ancestors for BFO-aligned sources (CCO, IOF, PMDCO, MDS-Onto); QUDT, which is not BFO-aligned, gets SKOS only;
  - `owl:sameAs` only between individuals (QUDT units and quantity kinds), never between classes;
  - every mapping records method, scores, confidence and target ontology as axiom annotations.
- **Imports**: every referenced external term is copied in with its labels, definition and ancestor chain from the store (MIREOT style), not only BFO/CCO, so the exported ontology is self-contained.
- **Validation additions**: every mapped IRI exists in the store; no mapping to a deprecated term; no `rdfs:subClassOf` into a disjoint BFO category; `owl:sameAs` only between individuals.

## 5. Reporting and compatibility

- New `eval_runs.csv` columns: labels added by source; mappings by predicate, target ontology and method; imported terms per ontology; candidates per class. Store manifest (ontology versions and hashes) recorded in `run.json`.
- New workflow revision. Update `docs/stages/4-enrich.md`, `docs/stages/5-interop.md` and add a store doc.
- Older runs stay readable. `python -m src.run check` reports whether the store is built and current.
- Dependencies: `pyoxigraph` (Windows wheels available); `sqlite3` is in the standard library.

## 6. Testing before a live run

- Build the store from the cached files and check searches on known terms: open-circuit voltage, fill factor, solar cell, temperature, kelvin, encapsulant.
- Resume a copy of a finished run from enrichment with a stand-in model; compare candidates and mappings per class against the original run.
- Existing tests and a compile check.
- Then a live run on the 5-paper loop.

## Decisions (2026-10-04)

1. **Ontology placement (stage 3) comes from the store.** The fixed 77-class menu leaves the placement prompt. Each concept gets parent candidates retrieved from the store (label, fuzzy and embedding search over BFO-aligned classes) plus its candidate corpus concepts; the model chooses among them, and the existing checks (category, cycles, paper is-a priority, lexical heads, repair) still apply. Parent order:
   - **CCO first, then BFO.** Every class must reach CCO or BFO.
   - **Name match to MDS-Onto or PMDCO wins.** If the concept matches an MDS-Onto or PMDCO class by name (exact label or synonym after normalization), that class is used alone, with no extra CCO/BFO parent added; its route to CCO/BFO comes from that ontology's own axioms, read from the store. If that route does not reach CCO or BFO, fall back to CCO, then BFO.
   - **Other ontologies (IOF, QUDT, RO, ...)** are never parents, only mappings.
2. **Prefer store search, always keep what the paper says.** Restriction properties and mappings come from store retrieval first (`upper.RELATION_GROUPS` only breaks ties). Whatever the store decides, the paper's own wording is kept: the extracted predicate phrase, quote, support and source papers stay on the claim in the literature layer and as axiom annotations on any restriction or mapping built from it, so a reader can always see the paper's statement next to the formal term chosen for it.
3. **External definitions are imported.** When a class has no paper-supported definition and has an exact or equivalent match, the matched term's definition is attached with status `imported` and its source IRI; reported separately from `supported`, `draft_evidence` and `model_generated`.
4. **Mapping propagation: one hop and two hops.** The matched external term's own mappings (one hop), and their mappings in turn (two hops), are offered as candidates with confidence decaying per hop (`ONTOLOGY_SEARCH["max_hops"] = 2`). Nothing propagated is asserted without the model's decision and the usual checks; each mapping records its hop count and the path of IRIs it came through.
5. **MDS-Onto: newest release.** As of 2026-10-04 the MDS-Onto portal lists 0.3.1.36 (released 2026-07-08) as the latest submission; MatPortal lags at 0.3.1.7 and the legacy checkout holds 0.3.1.31. The store build downloads the latest submission from the MDS-Onto portal API with `MDS_API_KEY` from `.env` (no key in code), records the version and hash in the manifest, and `ontologies status` reports when a newer submission exists.
