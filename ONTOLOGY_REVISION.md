# New-run ontology revision

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
