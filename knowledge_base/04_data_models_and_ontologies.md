# 04 — Data Models & Ontologies

## Pydantic data contracts (`src/models/`)

### Concepts (Phase 1) — `concept.py`
```python
ExtractedConcept(canonical: str, paper_term: str, relevance: float[0..1])
ConceptRow(paper, doi, canonical, paper_term, relevance)
ConceptTable(rows: list[ConceptRow])  # .all_canonicals -> list[str]
ConceptList(concepts: list[ExtractedConcept])            # extractor result_type
NormalizedConceptList(concepts: list[str])               # normalizer result_type
```
`canonical` = normalized label; `paper_term` = the surface term as written in that paper.

### Schema (Phase 2) — `schema.py`
```python
SchemaValue(canonical, value='', quote='')   # .formatted() -> "value | quote"
SchemaRow(domain, doi, cells: dict[str,str]) # cells[concept] = "value | quote"
SchemaValueList(values: list[SchemaValue])   # schema_builder result_type
```
The **wide-format schema**: one row per paper, one column per concept, each cell the
packed string `"value | quote"`. 30–80 columns is common (comprehensive but unwieldy).

### Tags (V6 enrichment) — `tag.py`
```python
TaggedConcept(concept, doc_frequency=1, mds_study_stage='', mds_supply_chain_level='')
TaggedConceptOutput(concept, mds_study_stage: list[str], mds_supply_chain_level: list[str])
TaggedConceptBatch(tagged_concepts: list[TaggedConceptOutput])   # tagger result_type
```

> Refactor note: there is **no** model for a Triple, a Paper, an Ontology class, or a
> Provenance record. Those live implicitly inside `graphdb_connector.py` and CSV
> strings. The rebuild should promote all of these to first-class `core/models`.

## CSV artifact shapes
| File | Shape | Produced by |
|------|-------|-------------|
| `concepts_*.csv` | flat: paper, doi, canonical, paper_term, relevance | Phase 1 |
| `schema_*.csv` | wide: domain, doi, concept1..N (cells `"value | quote"`) | Phase 2 |
| `enriched_*.csv` | concepts + `mds_study_stage`, `mds_supply_chain_level` | V6 tagger |
| `rankings_*.csv` | concept frequency aggregates | legacy V2 |
| `ontology_*.csv` | paper × concept matrix | legacy |

Filename convention: `{type}_{collection}-{username}-v{version}-{YYYYMMDD}.csv`.

## Ontology grounding

### MDS-Onto (Case Western SDLE)
The mid-level ontology everything grounds to. **Two namespace forms are in use — fix this:**
- `gaas_onto.ttl` (reference): `mds:` = `https://cwrusdle.bitbucket.io/mds#` (**hash**)
- `graphdb_connector` output: `mds:` = `https://cwrusdle.bitbucket.io/mds/` (**slash**),
  with sub-paths like `/characterization/electronmicroscopy/`.

### Two grounding styles observed
| | `gaas_onto.ttl` (richer, earlier) | `graphdb_connector.py` output (current generator) |
|--|--|--|
| Upper/mid | `bfo:`, `pmd:`, `qudt:`, `unit:`, `mds:`, `skos:` | `mds:` only (+ `schema:`, `qudt:`, `prov:`, `dcterms:`) |
| Class tree | domain classes → BFO/PMD parents | `mds:Concept` → Measurement / Material / Process |
| Individuals | 0 (schema only) | per-paper instances typed `mds:ResearchPublication` |
| Alignment (measured) | 7/7 classes aligned (1.0) | MDS-grounded, **no BFO/CCO** |

### The gap vs the project goal
The project brief wants **OWL 2 + JSON-LD grounded in BFO/CCO/MDS, validated**.
Today: JSON-LD ✔ (per paper + `all.jsonld`), OWL ✔ (MDS only), BFO/CCO ✘,
validation ✘ (no reasoner/OOPS!/SHACL gate). So the rebuild's net-new work is
**BFO/CCO alignment + a validation gate + provenance/confidence**, layered on top of
the emit logic that already exists in `graphdb_connector.py`.

## Palette assets (not ontologies)
- `mds_onto.json` — a draw.io **mxlibrary** of MDS shapes (despite the name).
- `cemento-templates.xml` — draw.io shape library for the Cemento ontology-drawing tool.
Both are embedded as diagram palette pages by the V6 / cemento path.
