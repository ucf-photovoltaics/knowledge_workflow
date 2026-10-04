# Ontology store (`src/tools/ontostore.py`)

Every external term the pipeline uses (placement parents, restriction properties, mapping candidates, imported labels, definitions and ancestor chains) comes from one local store over BFO, CCO, RO, QUDT (quantity kinds and units), PMDCO, IOF and MDS-Onto. Prompts never list concrete external terms; the model only chooses among candidates retrieved for the row it is answering.

```powershell
uv run --with-requirements requirements.txt python -m src.run ontologies build    # once, and after any source changes
uv run --with-requirements requirements.txt python -m src.run ontologies status   # current? newer MDS-Onto on the portal?
uv run --with-requirements requirements.txt python -m src.run ontologies search open-circuit voltage
```

The ontology, enrich and interop stages stop with a message when the store is not built. `python -m src.run check` reports its state.

## What is in it

| Part | File (under `outputs/cache/ontology_store/`) | Holds |
|---|---|---|
| Triple store | `oxigraph/` | One named graph per ontology (`urn:kw:ontology:<name>`), loaded with pyoxigraph |
| Term index | `terms.sqlite` | One row per class, object/datatype/annotation property and individual: labels, definition, named parents, domain, range, inverse, deprecation, own mappings; mapping links in both directions; FTS5 trigram index over every label |
| Embeddings | `vectors.npy`, `vectors.json` | One `EMBED` vector per term (label, up to four other labels, first 200 characters of the definition), with the model name and text recipe |
| Manifest | `manifest.json` | Per ontology: file, download location, version, SHA-256, ontology IRI; term counts; embedding model |

Oxigraph has no built-in full-text or vector search ([issue #48](https://github.com/oxigraph/oxigraph/issues/48)), so fuzzy and semantic search live in the two sidecars. The index is extracted from Oxigraph with SPARQL; lookups during a run read the SQLite index.

**Sources** (`ONTOLOGY_SOURCES` in `src/config.py`) are cached in `outputs/cache/ontologies/` and downloaded only when missing. MDS-Onto is the latest submission from the MDS-Onto portal (`MDS_API_KEY` in `.env`, sent as a header); when the portal cannot be reached the newest cached `MDS-Onto-*` file is used and the manifest says so. `ontologies status` reports a newer submission.

**Home ontology.** Each ontology lists the IRI prefixes it owns. A term re-declared elsewhere (MDS-Onto re-declares CCO classes) is attributed to its home ontology when that ontology declares it, otherwise to the first ontology that does. Labels are pooled across ontologies; the definition and parents come from the home ontology first.

**Labels** indexed: `rdfs:label`, `skos:prefLabel`, `skos:altLabel`, `skos:hiddenLabel`, oboInOwl exact and related synonyms, IAO alternative term, QUDT symbol. **Definitions**: `skos:definition`, IAO definition, IOF natural-language definition, QUDT plain-text description, `dcterms:description`, `rdfs:comment`, in that order. **Mappings**: `owl:equivalentClass`, `owl:equivalentProperty`, `owl:sameAs`, SKOS exact, close, broad, narrow and related matches, QUDT exact and SI exact matches.

## Search

`ontostore.search(texts, vector, kinds, ontologies, k)` fuses three signals per term:

- exact: a normalised label equals one of the query texts (labels shorter than three characters never match);
- fuzzy: trigram similarity between query and label, candidates from the FTS5 trigram index;
- cosine: the concept's embedding against the term vectors.

Fused score = weighted mean of the lexical signal (1 for an exact label, else the trigram similarity) and the cosine (`ONTOLOGY_SEARCH["weights"]`; labels only without embeddings). A candidate needs one signal on its own (exact, fuzzy >= `min_fuzzy`, cosine >= `min_cosine`) and fused >= `min_score`; exact matches rank first. Deprecated terms are never returned.

`ontostore.propagate(iri)` follows mapping links from a term: its mappings (one hop) and theirs (two hops, `max_hops`), keeping only terms in the store and recording the path and relations.

## Where each stage uses it

| Stage | Use |
|---|---|
| Ontology | A concept whose label names an MDS-Onto or PMDCO class (any label) goes under that class alone when its ancestors reach BFO (`name_match`). Otherwise parent candidates per concept: CCO first, then BFO classes by label, synonyms, lexical head and embedding (the three nearest always), plus the type default and, on the local tier, the category root; the model chooses. |
| Enrich | Mapping candidates per class over every ontology, plus MDS-Onto portal and MatPortal hits (all their ontologies; terms outside the store are facet hints only); one- and two-hop propagation; object-property candidates per extracted relation, filtered by domain and range. |
| Interop | Mapping targets must exist in the store and not be deprecated; category checks use store ancestors; matched terms' labels and definitions are imported; every referenced term is copied into the ontology with its ancestor chain. |

## Limits

- The store is as good as its sources: MDS-Onto and PMDCO model some terms with multiple or unusual parents (MDS-Onto places OpenCircuitVoltage under both an information entity and a quality), and a name-matched concept inherits that. `name_match_category_conflict` flags placements whose BFO category differs from the concept type's default.
- Few source ontologies publish mappings to each other, so propagation mostly finds QUDT exact matches and MDS-Onto's links to CCO.
- Search thresholds were set on a handful of known terms (open-circuit voltage, fill factor, temperature, kelvin, encapsulant, has part), not tuned on an annotated set.
