# An agent task: normalize a saved paper corpus

Author: Brent Thompson <brent.thompson@ucf.edu>

This is the detailed worked example for the operational ontology. It is a source-reviewed plan with
read-only fixture checks, not a claim that a new model run has been executed. The
[other stage worked tasks](stages/README.md) now extend this structure across the pipeline; many
internal helpers still have explicitly marked structural-only descriptions.

## Discover and bind

Start at `kw:CodebaseDocumentation`, follow `documentsWorkflow`, then `hasStep` to `kw:step/normalize`.
Read its English `skos:definition`, `contractJson`, `hasRecovery`, `hasCheck` and `hasDataBinding` links.
Follow the papers binding through `implementedBy` to `NormalizationAgent.run`, `hasArgument` to the
`papers: list[dict]` argument, and `bindsArtifact` to `papers/*.json`. This expresses the value binding;
it does not say the bound method opens the files itself.

`Run.papers()` loads sorted saved paper records; `src.run.normalize()` constructs
`NormalizationAgent(run.ledger)` and calls its `run(papers)` method. Use the CLI or wrapper invocation
for orchestration so credentials, settings, ledger and completion recording remain with the existing
runtime. Direct calls require reproducing that context and are not the default execution path.

Saved records are a different boundary from raw model-response JSON. A paper must identify its `key`
and contain concept/relation/causal/measurement lists. Concept IDs and labels must be usable strings.
Saved measurements reference the property concept through `concept`; the raw extraction schema names
that field `property`. The documented check validates this saved boundary, not an assumed raw schema.

## Assess before work

Run in the isolated documentation environment, from the repository root:

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py guide --step normalize
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run si-topcon-n15-20261015-150628 --step normalize --phase before
```

The recipe comes from RDF. The second command reads an existing run without writing it. It checks
recorded extraction/readable products and the paper contract. Missing fields, duplicate paper/concept
IDs, malformed labels and unresolved within-paper endpoints block the proposed action. Partial
extraction is not accepted merely because the CLI saved a completion key.

`ready-for-runtime-conditions` means the saved data passed these bounded checks. It does not establish
live provider readiness, safe ownership, authorized write scope or permission to rebuild a shared store.
Resolve mode-specific prerequisites/conditions before using the existing trusted invocation template.

## Follow the implementation

`hasOperation` and `nextOperation` describe the reviewed source order: clean fields → lexical groups →
semantic merge review → canonical identities → type votes → claim aggregation → contradictions/scoring →
causal ordering → summary. Each operation links through `operationImplementation` to its source function.
The method mutates the supplied paper lists in memory; this stage's orchestrator does not rewrite the
saved `papers/*.json` inputs.

The returned dictionary has concepts, relations, causal, measurements, contradictions, causal_order,
summary and internal stats. The orchestrator saves seven returned fields. `reports.corpus_report()`
writes Markdown and returns separate report-derived statistics for `normalized/corpus_stats.json`.
Do not serialize internal `norm.stats` as a substitute for the report-derived artifact.

## Assess after work and choose the next action

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run si-topcon-n15-20261015-150628 --step normalize --phase after
```

The documentation checks require recorded completion, readable required outputs, documented field
types, unique canonical IDs, canonical endpoints and supporting-paper coverage. Artifact digests are
rechecked before returning. The evaluator is linked from each check through `evaluatedBy`; its bounded
predicate description is in `checkRule`, with CLI argument templates in `evaluationArguments`.

Even when structural checks pass, aliases, contradictory claims, type decisions and evidence need
review. The helper returns `review-required`, not scientific acceptance. These stricter agent boundary
checks do not change the pipeline's own runtime acceptance rules or repair source results.

`canAdvanceTo` identifies placement as the next conceptual stage; its own runtime/store conditions
still apply. If normalization is rerun, `invalidatesStep` identifies placement, enrichment, interop,
integration and reports for freshness review. It never deletes or reruns them automatically.

Exact `(paper key, original concept ID) → canonical ID` merge lineage is transient and not persisted by
the current normalizer. Alternate labels and supporting papers are useful but cannot reconstruct every
reviewed merge decision. The ontology records this limitation rather than inventing provenance.

## Reviewer navigation

Open the local WebVOWL preview at http://127.0.0.1:8058/. Normalization opens with a bounded data-flow
graph and an inspector containing its `skos:definition`, bindings, checks and recovery. Switch to
implementation for functions/substeps; use code lookup for bounded neighborhoods instead of rendering
all records at once. Artifact connections expose producers, consumers and bindings in both directions.
Function records expose source lines, signatures, formal arguments/defaults and return annotations.
Unannotated types and unreviewed behavior remain visible gaps.

On smaller windows the inspector stacks beneath the graph; **Selected record** and **Back to graph**
provide direct navigation. Source links open generated, fingerprinted code snapshots rather than
unregistered public ontology IRIs. Full graph JSON remains downloadable, with projection semantics
explicitly separated from the original formal RDF types.
