# Worked task: Inspect printed readiness checks

Author: Brent Thompson <brent.thompson@ucf.edu>

This is a source-reviewed operational recipe, not a claim that a new model or literature run was executed. The ontology embeds this text and fingerprints the source. Scientific acceptance and live readiness remain separate checks.

## Research task and discovery

A new collection is about to be processed. Establish shared-store readiness, bind the actual configured collection and inspect each readiness result before spending extraction compute.

Start at `kw:CodebaseDocumentation` → `documentsWorkflow` → `hasStep` → `kw:step/preflight`. Read its `skos:definition`, `contractJson`, `hasDataBinding`, `hasOperation`, `hasCheck` and `hasRecovery` links. Follow `implementedBy`/`operationImplementation` to source callables, `hasArgument` to formal names/types/defaults and `bindsArtifact` to source/output artifact specifications. Artifact incoming links identify producers and consumers.

## Bind and initialize

A configured CLI collection and provider settings, not a saved paper corpus. This utility performs real network/model requests and PDF caching.

| Input | Required shape or origin |
|---|---|
| `args.collection` | existing key in config.COLLECTIONS |
| `runtime` | configured credentials, extraction profile, optional embedding profile, portals and existing store |

Use the trusted CLI check invocation after shared-store readiness; configuration is loaded by the runtime. Never copy secret values into RDF or task output.

Side effects: Downloads selected PDFs to the shared cache and contacts services. No run stage is recorded.

### Trusted execution entry points

The following are **unbound argument-vector templates** from workflow.json. Resolve every uppercase placeholder using actual authorized selections; do not execute these literal placeholders. Prefer the existing controller to direct callable invocation. `ontology_agent.py plan` can bind/check templates without executing them. Credentials remain in the runtime.

CLI template:

```json
[
  "uv",
  "run",
  "--with-requirements",
  "requirements.txt",
  "python",
  "-m",
  "src.run",
  "check",
  "--collection",
  "COLLECTION"
]
```

No separate WRAPPER invocation is defined for this stage.

### Data bindings

| Direction | Saved or explicit input | Selector → callable value | Adaptation |
|---|---|---|---|
| input | `explicit configured CLI collection` | `$` → `src/run.py:check` / `args.collection` | Use an actual configured name; wrapper project credentials and collections are a distinct execution mode. |
| output | `preflight observations in terminal` | `$` → `src/run.py:check` / `printed outcomes` | Eight guarded checks print their outcomes. A zero exit status is insufficient; require no FAIL and the final ready line. |

## Follow the source operations

The sequence describes the implemented plan. Profile-dependent branches and guarded optional operations are stated explicitly; it does not assert that every branch runs in every attempt.

1. **Check required credentials** — `src/run.py:check.keys`. Check presence of required credential names in the selected runtime without publishing their values.

2. **Probe extraction model** — `src/run.py:check.model`. Make a small real chat request and require a parseable JSON reply; this checks connectivity, not extraction quality.

3. **Probe optional embeddings** — `src/run.py:check.embeddings`. If embedding is enabled, request a vector; otherwise explicitly report lexical-only operation.

4. **Select and cache a sample corpus** — `src/run.py:check.corpus`. Select citation-ranked PDFs for the configured collection and require a nonempty corpus. This writes the PDF cache.

5. **Check PDF parsing** — `src/run.py:check.parser`. Parse a selected PDF and report its page, section, figure and retained-text counts.

6. **Check ontology portals** — `src/run.py:check.portal`. Check MDS portal acronyms and a sample search. check.matportal_check separately checks its optional portal.

7. **Check shared store** — `src/run.py:check.store`. Inspect configured store status/problems; require a built store and no reported problems.

8. **Read every outcome** — `src/run.py:check`. Catch individual failures and print a final ready or failure-count line. This routine does not guarantee a nonzero failure exit code.

## Handle the return and persistence

- None; printed per-check outcomes and final ready/failure count

The printed model probe returning JSON does not certify correct science. No saved domain manifest can substitute for this live check.

## Assess and choose the next action

Run the read-only helper from the repository root in the documentation environment. `RUN_FOLDER` means an existing run-relative directory under the selected outputs root, not a guessed future run. Guide retrieval requires no run folder. Use the integration folder for integration, the report folder or domain root for reports, and the domain attempt for other stages.

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py guide --step preflight
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step preflight --phase before
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step preflight --phase after
```

The helper never runs pipeline commands or repairs data. `blocked` stops the proposed advance; `runtime-check` requires real environment/scope checks; `review` requires evidence or domain review. A successful bounded predicate does not certify all schema fields or scientific meaning. File hashes are rechecked to detect changes during observation.

| Check | Phase | Scope |
|---|---|---|
| `printed-ready` (runtime_condition) | before, after | Perform the configured live check and require all printed checks plus the final ready line; saved domain artifacts cannot prove readiness. |

Completion rule: Read every printed check and require the final ready message with no [FAIL] lines. src.run.check catches check failures and does not guarantee a nonzero exit code; exit status alone is insufficient.

Recovery: Resolve each failed check and rerun preflight. A zero exit code is insufficient; require the printed ready outcome.

Limit: Printed checks do not create a stage completion record.

Follow `canAdvanceTo` to the next conceptual stage and inspect its mode-specific prerequisites. A rerun requires freshness review of stages linked by `invalidatesStep`; the documentation helper never deletes or reruns them. For reports, completion ends this task; integration is optional when only one domain exists.

## WebVOWL review

At http://127.0.0.1:8058/, select **Check environment and sources** (its shortened tab label may differ). Start with Data flow to trace saved values, switch to Implementation for source operations, and select a function for its definition, formal arguments and fingerprinted source lines. The stage inspector links this worked example. Checks show before/after scope; runtime-only conditions remain visible. Use bounded Code lookup for connected records instead of loading all code nodes at once.
