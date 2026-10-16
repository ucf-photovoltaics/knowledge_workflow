# Worked task: Choose a reproducible domain corpus

Author: Brent Thompson <brent.thompson@ucf.edu>

This is a source-reviewed operational recipe, not a claim that a new model or literature run was executed. The ontology embeds this text and fingerprints the source. Scientific acceptance and live readiness remain separate checks.

## Research task and discovery

A researcher assigns two TOPCon collections from different authorized groups to one named domain with a cap of30. Expand descendants, deduplicate memberships and rank citations across both collections together.

Start at `kw:CodebaseDocumentation` → `documentsWorkflow` → `hasStep` → `kw:step/ingest`. Read its `skos:definition`, `contractJson`, `hasDataBinding`, `hasOperation`, `hasCheck` and `hasRecovery` links. Follow `implementedBy`/`operationImplementation` to source callables, `hasArgument` to formal names/types/defaults and `bindsArtifact` to source/output artifact specifications. Artifact incoming links identify producers and consumers.

## Bind and initialize

Dashboard domain selections span key-authorized personal/group libraries and descendant collections. CLI extraction uses its separately configured collection.

| Input | Required shape or origin |
|---|---|
| `domain.collections` | list of {library:{type,id,name}, key, name} |
| `domain.limit` | positive citation-ranked per-domain cap |
| `folder` | selected wrapper attempt directory |

The worker bootstrap selects the project profile, credentials, cache and output root before importing the pipeline. Prefer worker stage ingest; no separate CLI ingest command exists.

Side effects: Downloads PDFs into the dashboard cache and writes partial/final selection files in the selected attempt; Zotero source items are read.

### Trusted execution entry points

The following are **unbound argument-vector templates** from workflow.json. Resolve every uppercase placeholder using actual authorized selections; do not execute these literal placeholders. Prefer the existing controller to direct callable invocation. `ontology_agent.py plan` can bind/check templates without executing them. Credentials remain in the runtime.

No separate CLI invocation is defined for this stage.

WRAPPER template:

```json
[
  "outputs/dashboard/.venv/Scripts/python.exe",
  "-m",
  "dpv_dashboard.worker",
  "PROJECT_ID",
  "stage",
  "--domain",
  "DOMAIN_ID",
  "--stage",
  "ingest"
]
```

CLI mode performs this operation inside extraction; do not call extract repeatedly to simulate separate ingestion/parsing commands.

### Data bindings

| Direction | Saved or explicit input | Selector → callable value | Adaptation |
|---|---|---|---|
| output | `ingestion.json` | `$.papers` → `dpv_dashboard/worker.py:ingest` / `chosen` | Citation-ranked domain selections are saved by the wrapper, not by the single-collection CLI. |
| input | `explicit selected project domain collections and limit` | `$` → `dpv_dashboard/worker.py:ingest` / `domain` | Bind actual key-authorized collection records and the domain cap; do not invent library identifiers. |
| output | `ingestion.partial.json` | `$` → `dpv_dashboard/worker.py:ingest` / `chosen, skipped` | After PDF attempts, save selected/skipped_no_pdf progress. A partial file does not establish completion. |

## Follow the source operations

The sequence describes the implemented plan. Profile-dependent branches and guarded optional operations are stated explicitly; it does not assert that every branch runs in every attempt.

1. **Expand descendant collections** — `dpv_dashboard/zotero.py:Libraries.expand`. Expand selected library/collection records to include descendants before gathering items across the named domain.

2. **Gather and deduplicate papers** — `dpv_dashboard/zotero.py:deduplicate`. Merge duplicate paper memberships while retaining source library/item/collection information.

3. **Count citations** — `src/tools/citations.py:counts`. Resolve DOI citation counts through configured providers and cache; missing counts remain explicitly unknown.

4. **Rank across the domain** — `dpv_dashboard/worker.py:ingest`. Sort all deduplicated papers by citation count, missing counts last and stable key ties; apply one cap across the domain, not one per collection.

5. **Find available PDFs** — `src/tools/zotero.py:_fetch_pdf`. Reuse cached PDFs or fetch them for each paper source; skip unavailable PDFs and continue down the citation ranking until the cap or candidates are exhausted.

6. **Persist selected corpus** — `dpv_dashboard/worker.py:ingest`. Require at least one available PDF; save selected paper metadata, source memberships, ranking rules, expanded collections and skipped-PDF findings.

## Handle the return and persistence

- None; ingestion.json and incremental ingestion.partial.json

The cap is30 available-PDF papers across the domain. It is not30 per collection. Missing citation counts rank last; unavailable PDFs are skipped and remain review findings.

## Assess and choose the next action

Run the read-only helper from the repository root in the documentation environment. `RUN_FOLDER` means an existing run-relative directory under the selected outputs root, not a guessed future run. Guide retrieval requires no run folder. Use the integration folder for integration, the report folder or domain root for reports, and the domain attempt for other stages.

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py guide --step ingest
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step ingest --phase before
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step ingest --phase after
```

The helper never runs pipeline commands or repairs data. `blocked` stops the proposed advance; `runtime-check` requires real environment/scope checks; `review` requires evidence or domain review. A successful bounded predicate does not certify all schema fields or scientific meaning. File hashes are rechecked to detect changes during observation.

| Check | Phase | Scope |
|---|---|---|
| `shape-ingestion` (shape) | after | ingestion.json |
| `selected-paper-fields` (shape) | after | ingestion.json |
| `review-findings` (scientific_review) | after | Review selected scope, missing citation counts, skipped PDFs and duplicate memberships. A smaller available corpus is not proof of complete literature coverage. |

Completion rule: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: Check key-authorized libraries, descendant collections, citation ranking and PDF availability; retry ingestion in a new wrapper attempt when selections change.

Limit: A citation-ranked selected corpus may contain fewer papers when PDFs are unavailable.

Follow `canAdvanceTo` to the next conceptual stage and inspect its mode-specific prerequisites. A rerun requires freshness review of stages linked by `invalidatesStep`; the documentation helper never deletes or reruns them. For reports, completion ends this task; integration is optional when only one domain exists.

## WebVOWL review

At http://127.0.0.1:8058/, select **Select literature across collections** (its shortened tab label may differ). Start with Data flow to trace saved values, switch to Implementation for source operations, and select a function for its definition, formal arguments and fingerprinted source lines. The stage inspector links this worked example. Checks show before/after scope; runtime-only conditions remain visible. Use bounded Code lookup for connected records instead of loading all code nodes at once.
