# Knowledge Workflow codebase documentation

Author: Brent Thompson <brent.thompson@ucf.edu>

This documentation covers first-party pipeline, dashboard, scripts, tests and the optional training
notebook. Generated corpus/results, private settings, environments, third-party WebVOWL and imported
ontology snapshots are not first-party source and do not receive Brent's authorship headers.

- [Architecture](../architecture.md): system boundaries and ownership.
- [Module/callable reference](modules.md): file summaries, imports, function signatures, source lines and hashes.
- [Agent execution guide](agent-guide.md): how to run new literature one step at a time.
- [Information and concept journeys](data-journey.md): follow transformations, evidence, concept identities and provenance gaps across the pipeline.
- [Normalization worked example](normalization-walkthrough.md): source-reviewed bindings, checks and reviewer navigation.
- [All stage worked tasks](stages/README.md): ingestion through reports, including setup, return/persistence boundaries and failure recovery.
- [Operational recipes](operations.json): curated input contracts, field bindings, source operations and read-only before/after checks embedded in RDF.
- [Generated step reference](agent-steps.md) and [machine-readable contracts](workflow.json).
- [Review findings](review.md): implementation and data-quality limitations, separated from fixes.
- [Operational ontology](../ontology/README.md): navigable RDF, validation and example queries.
- [Ontology usability audit](../ontology/usability-review-2026-10-16.md): connections, execution safeguards and verification scope.
- [Author header ledger](author-headers.json): coverage and applied header status.

The inventory is static analysis, not a proof that every branch, provider or GPU configuration works.
Syntactic call names are recorded as text when dynamic dispatch prevents reliable resolution. The
curated step-to-function links are checked against actual AST symbols. File hashes detect stale guides.

## Regenerate and validate

Use an isolated documentation environment with rdflib, pyshacl and owlrl; do not install into an active
pipeline environment. From the repository root:

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/document-codebase.py
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/validate-codebase-ontology.py
```

`--author-headers` applies approved first-party header edits and writes a review patch under
`outputs/development/codebase-docs/author-headers.patch`. It is not needed for ordinary regeneration.
Python executable ASTs must remain identical after removing only the module docstring. Header edits
change source hashes/line numbers and therefore require regenerating the inventory/ontology.

Fresh environment setup, if needed, is explicit:

```powershell
uv venv --python outputs/dashboard/.venv/Scripts/python.exe outputs/development/codebase-docs/.venv
uv pip install --python outputs/development/codebase-docs/.venv/Scripts/python.exe rdflib pyshacl owlrl pytest
```

The working validation versions are recorded in the ontology guide. The normal dashboard launcher
remains `./start-dashboard.ps1`, default port8056. Code/documentation generation never starts a model run.
