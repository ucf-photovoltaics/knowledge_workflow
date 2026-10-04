# New-run revision 2026-10-04-ontology-store-v1

Build the ontology store first (`python -m src.run ontologies build`), then start a new run or resume an existing one from `ontology` (delete those stages from its `run.json`). Extraction and normalization are unchanged, so cached extractions are reused. Older run folders stay readable by the figures, the literature layer and `integrate`. Plan and decisions: [embedding_plan.md](embedding_plan.md); store: [docs/ontology-store.md](docs/ontology-store.md).

- Ontology store (`src/tools/ontostore.py`): BFO, CCO, RO, QUDT quantity kinds and units, PMDCO, IOF and the latest MDS-Onto (portal API) in Oxigraph, one named graph each; SQLite term index with an FTS5 trigram label index; one `nomic-embed-text` vector per term; manifest of versions and hashes, recorded in each run's `run.json`.
- Placement: no fixed class menu in the prompt. A concept that names an MDS-Onto or PMDCO class is placed under it when its ancestors reach BFO (`name_match`); otherwise the model chooses among store candidates (CCO first, then BFO), the type default and the category root.
- Enrichment: MatPortal and the nearest-BFO/CCO lookup are gone; candidates come from the store (every ontology) and the MDS-Onto portal, with one- and two-hop propagation through mappings. Restriction properties come from the store per relation (domain and range must fit); exact names and `RELATION_GROUPS` tie-breaks need no model call. The paper's predicate phrase stays on every restriction.
- Interop: relations equivalent, exact, close, broader, narrower, related. OWL axioms only for BFO-aligned classes of a matching category; individuals SKOS only. Targets must be in the store and not deprecated. Definitions of exact or equivalent matches are imported (`imported`) for classes without a paper-supported one; their labels become `skos:altLabel`, acronyms and spelling variants `skos:hiddenLabel`. Every referenced term is imported with its ancestor chain. Mappings carry method, scores, confidence, target ontology, hop count and path.
- Reporting: new `eval_runs.csv` columns for store use, mappings by predicate, method and hop, labels by origin, imported terms by ontology and store versions; `definitions_<status>` counts after imports.

Tested with a stand-in model and stand-in embeddings (the VM has no Ollama and cannot reach the MDS-Onto portal): store build from the cached files plus MDS-Onto 0.3.1.31, searches on known terms, resume of a copy of `tea-20261003-234327` from `ontology` through `interop` (ontology valid), unit tests. No live model run yet.

# Previous revision 2026-10-04-coverage-evidence-ro-v1

Start a new run to use it; old run folders stay readable by normalization, the literature layer and `integrate`. Extraction prompts changed, so cached extractions are redone.

- Row coverage: unanswered rows in every batched pass are retried once (`Agent.call_rows`); counts per pass in `run.json` and `eval_runs.csv`.
- Definitions: status `supported`, `draft_evidence`, `model_generated` (only on profiles in `MODEL_DEFINITION_PROFILES`), `none` or `unreviewed`; exported as `skos:definition` with `kw:definitionStatus` and `kw:definitionSource`. Coverage is reported per status (`definitions_<status>`).
- Measurements: `property` and `entity` instead of `concept`; a value attached to a non-property concept with no entity is moved to `entity` and flagged `property_missing`. Older records with `concept` are still read.
- Evidence: items whose quote has fewer than 3 words get one follow-up call; still empty, `evidence_status: unevidenced`. Unevidenced relations are kept in the literature layer (`kw:evidenceStatus`) but never become restrictions.
- Relations: predicates are `is_a` plus RO/BFO/CCO-grounded names (`upper.RELATION_GROUPS`, `upper.relation_group`); older names (`made_of`, `has_property`, `measured_by`, `used_for`) resolve through aliases. Verified relations become restrictions with the first property in their group whose domain/range fit; the literature layer uses the RO/BFO/CCO IRI.
- Leaked id labels: `n1 (Auger recombination)` becomes `Auger recombination` at extraction; `integrate` skips id-like labels after parentheses are stripped.

Tested with a stand-in model only (backward-compatible resume on an older run, a frontier-tier run, extraction unit cases, `integrate`); no live model runs.

# Previous revision

Revision: `2026-10-03-evidence-hierarchy-domain-iris-v1`.

Past output directories and `eval_runs.csv` were not modified during implementation. Start a new run to use this revision; leave old runs available for comparison. No tests or API calls were executed.

## Behavior

- Parent selection receives source definitions and relationship evidence. Verified paper-extracted `is_a` edges take priority when their categories agree and they cannot create a cycle. Multiple competing parents, category conflicts, and fallback placements are recorded for review. “Verified” here means a matched evidence quote, not proof that a claim is universally true.
- Source definitions remain evidence. The enrichment model must explicitly report that a definition is supported at the concept's generality; otherwise the exported definition is left blank and flagged. Prompts distinguish general concepts from experimental configurations and flag category conflicts. This is model-assisted review, not an independent factual guarantee.
- Classes use `<base>/<domain>/class/<label>_<identity-hash>` IRIs. The hash derives from label/type rather than processing order; duplicate identities or hash collisions fail clearly. Changing a concept's label/type changes its identity. Separate domains no longer silently identify same-named classes.
- `ontology/review_issues.json` records unresolved placements, conflicts, and unsupported definitions.
- `ontology/cross_domain_candidates.json` lists same-label candidates from completed runs in other domains, including parent/category differences and both definitions. It reads historical outputs without altering them and asserts no equivalence. Matching is deliberately limited to case-insensitive labels; wider semantic matching remains future work.

## Reporting

Existing metrics and report sections remain. The ontology report adds revision and review counts. New eval rows include `row_type=run`, `workflow_revision`, unresolved-placement/category-conflict counts, and unsupported-definition counts.

When the first new run starts, the eval dataset adds one event row with `row_type=workflow_change`, the revision, timestamp, and change description. Its metric fields are blank. Filter to run rows for aggregate performance comparisons; historical rows have blank new fields. Existing metric values are preserved when the CSV expands to include the new fields.

The event row is added once per revision. It is not added immediately by the source edit. If the eval CSV is open in Excel, the existing writer reports that it could not save; close the workbook before starting the run.

## Use

With Ollama available and credentials already configured:

```powershell
Set-Location C:\Users\brent\dev\knowledge_workflow
$env:LLM_PROFILE = "gemini"
.\.venv\Scripts\python.exe -m src.run all --collection si-topcon --limit 1
```

Omit `--run-id` to create a new run. Use `gemini-lite` for Flash-Lite. Hybrid routing remains local extraction/interoperability and Gemini normalization/ontology/enrichment. Existing Gemini quota blocks still apply.

## Source changes

- `src/agents/ontology.py`: evidence context, paper-parent priority, review counts, domain-scoped stable class identifiers.
- `src/agents/enrichment.py`: reviewed definition acceptance and unsupported/category-conflict flags.
- `src/tools/ontology_review.py`: context, hierarchy review, review artifacts, and cross-domain candidate reporting.
- `src/resources/prompts/ontology*.md`, `enrichment.md`, `enrichment_definitions.md`, and corresponding enrichment schemas: generality/support guidance and explicit support/conflict responses.
- `src/config.py`: revision constant.
- `src/run.py`: new inputs/artifacts and first-new-run change event.
- `src/tools/reports.py`: additive review/report fields and revision-event row.
- `src/tools/owl.py`: corrected documentation of domain-scoped class identity.

Reusing earlier normalized concepts would retain any distinctions already lost there. A new complete run uses the previously implemented synonym-union correction as well.
