# Reporting, compute and error records

Every stage writes what it did, what it cost and what it could not do. `tools/reports.py`, `tools/ledger.py`, `run.py`.

## Per run (`outputs/<run_id>/`)

- `run.json`: settings (profile, provider, model and tier per agent, embedding model, workflow revision, `ONTOLOGY_SEARCH`), `ontology_store` (version, file, SHA-256 and location of each ontology in the store, embedding model, build time), collection, corpus selection and hash, per-stage completion time, wall time and summary counts, compute totals, errors.
- `ledger.jsonl`: one line per model call (agent, item, model, input, cached and output tokens, latency, cost if `PRICES` is set, attempt, cache hit).
- `calls.jsonl`: raw text of every non-extraction call (extraction keeps `raw_calls` in the paper record).
- `compute_per_paper.csv`, `compute_per_agent.csv`, `corpus_report.md`, `ontology_report.md`.
- `error.log`: tracebacks; also appended to `outputs/errors.csv`.

## Across runs

- `outputs/eval_runs.csv`: one row per run, rebuilt after every stage; new columns are appended and old rows keep blanks. Groups: settings; corpus selection and citations; parsing; extraction counts, evidence status shares and checks; normalization; placement sources and row coverage; ontology store use (name matches, parent, mapping and property candidates by ontology and source, propagation hops, `store_version_<ontology>`); definitions by status (after imports); restrictions; mappings by relation, predicate, method, hop and target ontology; labels by origin; imported terms by ontology; facets; ontology metrics and validation; literature layer; calls, tokens, latency and wall time per agent.
- Each run row carries `workflow_revision`. The first run of a new revision adds one `row_type=workflow_change` row with the revision note. Filter on `row_type=run` for comparisons.
- `outputs/eval_integrations.csv`: one row per integration.

## Reading the numbers

- Row coverage: `<pass>_rows`, `<pass>_rows_recovered`, `<pass>_rows_missing_after_retry`. Missing rows become defaults downstream, so read placement and definition counts together with them.
- Evidence: `<kind>_evidence_verified_share` and `<kind>_unevidenced_share` per relations, causal and measurements.
- Compare runs within one revision and one profile. Cached extractions are keyed by model, prompts and extraction code version, so a cache hit was produced by the same extraction setup.

## Figures (`python -m src.figures`)

Writes PDF (for LaTeX), PNG and the plotted numbers as CSV to `outputs/figures/<revision>/`, plus `index.md` listing each figure and its data source. Only runs of one workflow revision and one profile are plotted together (`--revision`, `--profile`, or `--runs ID ...`; `--outputs DIR` for another outputs folder). Per domain, the run with the most papers is used for the single-run figures.

| Stage | Figure | Shows | Data |
|---|---|---|---|
| Extract | `concept_growth` | Distinct canonical concepts as papers are added, in citation order, with a 5-95% band over 200 random paper orders | `normalized/concepts.json`, selection order in `run.json` |
| Extract | `knowledge_growth` | The same for relations and causal claims, and the cumulative count of reported values | `normalized/*.json` |
| Extract | `scaling_runs` | Separate runs of increasing size (5/10/15...): canonical concepts, classes, share of concepts in 2+ papers | `eval_runs.csv` |
| Extract | `per_paper_yield` | Concepts, relations, causal claims and values per paper, by domain | `papers/*.json` |
| Extract | `parsing` | Characters kept against characters in the PDF (references and running headers removed); concepts against sections sent to the model | `papers/*.json` `parse_stats` |
| Extract | `extraction_checks` | Per paper: quotes re-asked and filled, concepts added by later passes, values not on a property | `extraction_check_*` columns |
| Extract | `evidence_status` | Verified / unverified / unevidenced share per item type and domain | paper verification counts |
| Normalize | `normalization` | Occurrences, lexical groups, canonical concepts; look-alike clusters, accepted merges, type conflicts, causal contradictions | `eval_runs.csv` |
| Normalize | `concept_support` | How many papers each canonical concept appears in | `normalized/concepts.json` |
| Normalize | `concept_types` | Canonical concepts by type | `normalized/concepts.json` |
| Normalize | `causal_polarity` | Causal claims by polarity | `normalized/causal.json` |
| Normalize | `relation_predicates` | Share of each relation predicate per domain (RO/BFO/CCO-grounded and is-a) | `normalized/relations.json` |
| Ontology | `bfo_categories` | Classes by BFO category | `ontology/classes.json` |
| Ontology | `hierarchy_depth` | Share of classes at each number of levels up to BFO entity, and at each number of corpus classes above them | `ontology/classes.json`, BFO/CCO ancestors |
| Ontology | `placement_sources` | Where each class's parent came from | `placement_*` columns |
| Ontology | `review_flags` | Share of classes flagged for expert review, by reason | `ontology/*.json` review flags |
| Ontology | `row_coverage` | Rows answered first, recovered by the retry, still missing, per model pass | `<pass>_rows*` columns |
| Ontology | `layer_vs_ontology` | What the literature layer keeps (all claims, values, is-a links) against the universal axioms the ontology asserts | `ontology/domain_layer_metrics.json`, `ontology/metrics.json` |
| Enrich | `definitions_status` | Definitions by status as a share of classes, including rows not answered and classes with none | `definitions_*`, `final_classes` |
| Enrich | `restriction_sources` | Restrictions from causal claims (local, RO, CCO) and relations (extracted predicate, model) | `ontology/enriched.json` |
| Enrich | `study_stages` | Classes by MDS-Onto study stage | `ontology/facets.json` |
| Interop | `external_mappings` | Classes by strongest external mapping; remainder unmapped | `ontology/mappings.json` |
| Interop | `mapping_targets` | External mappings per domain by target ontology | `ontology/mappings.json` |
| All | `compute_by_stage` | Tokens and wall time per stage and domain (two panels, no shared axis) | `<agent>_*` columns |
| Integrate | `integration` | Mappings per domain pair, mappings by relation, bridge concepts (across integrations of increasing size when there are several) | `eval_integrations.csv`, `integration-*/` |

A figure whose data is missing (for example row coverage on runs before revision 2026-10-04) is skipped and listed in `index.md`. Colours are fixed per domain and per category, with markers and direct labels as a second cue.

