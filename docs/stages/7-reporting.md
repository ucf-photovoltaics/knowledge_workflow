# Reporting, compute and error records

Every stage writes what it did, what it cost and what it could not do. `tools/reports.py`, `tools/ledger.py`, `run.py`.

## Per run (`outputs/<run_id>/`)

- `run.json`: settings (profile, provider, model and tier per agent, embedding model, workflow revision), collection, corpus selection and hash, per-stage completion time, wall time and summary counts, compute totals, errors.
- `ledger.jsonl`: one line per model call (agent, item, model, input, cached and output tokens, latency, cost if `PRICES` is set, attempt, cache hit).
- `calls.jsonl`: raw text of every non-extraction call (extraction keeps `raw_calls` in the paper record).
- `compute_per_paper.csv`, `compute_per_agent.csv`, `corpus_report.md`, `ontology_report.md`.
- `error.log`: tracebacks; also appended to `outputs/errors.csv`.

## Across runs

- `outputs/eval_runs.csv`: one row per run, rebuilt after every stage; new columns are appended and old rows keep blanks. Groups: settings; corpus selection and citations; parsing; extraction counts, evidence status shares and checks; normalization; placement sources and row coverage; definitions by status; restrictions; mappings and facets; ontology metrics and validation; literature layer; calls, tokens, latency and wall time per agent.
- Each run row carries `workflow_revision`. The first run of a new revision adds one `row_type=workflow_change` row with the revision note. Filter on `row_type=run` for comparisons.
- `outputs/eval_integrations.csv`: one row per integration.

## Reading the numbers

- Row coverage: `<pass>_rows`, `<pass>_rows_recovered`, `<pass>_rows_missing_after_retry`. Missing rows become defaults downstream, so read placement and definition counts together with them.
- Evidence: `<kind>_evidence_verified_share` and `<kind>_unevidenced_share` per relations, causal and measurements.
- Compare runs within one revision and one profile. Cached extractions are keyed by model, prompts and extraction code version, so a cache hit was produced by the same extraction setup.
