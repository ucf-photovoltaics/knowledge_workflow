# Worked task: Connect explicitly selected domain ontologies

Author: Brent Thompson <brent.thompson@ucf.edu>

This is a source-reviewed operational recipe, not a claim that a new model or literature run was executed. The ontology embeds this text and fingerprints the source. Scientific acceptance and live readiness remain separate checks.

## Research task and discovery

TOPCon, reliability and techno-economic domain runs have completed interoperability. Bind their explicit recorded IDs, one per distinct domain, and create a new integration identifier.

Start at `kw:CodebaseDocumentation` → `documentsWorkflow` → `hasStep` → `kw:step/integrate`. Read its `skos:definition`, `contractJson`, `hasDataBinding`, `hasOperation`, `hasCheck` and `hasRecovery` links. Follow `implementedBy`/`operationImplementation` to source callables, `hasArgument` to formal names/types/defaults and `bindsArtifact` to source/output artifact specifications. Artifact incoming links identify producers and consumers.

## Bind and initialize

Select at least two distinct completed domain runs explicitly. load_domain adapts enriched class records into live comparison records and parses each source formal ontology; the agent does not open run folders itself.

| Input | Required shape or origin |
|---|---|
| `selected[]` | one completed run per distinct domain |
| `domains` | dict[domain,list[{iri,label,domain,run,alt_labels,category,parent_label,definition,type,score}]] |
| `graphs` | dict[domain,{graph,iri}] for master construction |

src.run.integrate resolves outputs and explicit run IDs, creates the integration directory and an IntegrationAgent with its own ledger. Wrapper integration selects every configured domain run and a fresh integration ID.

Side effects: Reads source runs without rewriting them; writes a new integration folder and updates the aggregate evaluation table. Reusing a CLI integration ID can overwrite its products.

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
  "integrate",
  "--runs",
  "DOMAIN_A_RUN_ID",
  "DOMAIN_B_RUN_ID",
  "--run-id",
  "INTEGRATION_RUN_ID",
  "--no-figures"
]
```

WRAPPER template:

```json
[
  "outputs/dashboard/.venv/Scripts/python.exe",
  "-m",
  "dpv_dashboard.worker",
  "PROJECT_ID",
  "stage",
  "--stage",
  "integrate"
]
```

### Data bindings

| Direction | Saved or explicit input | Selector → callable value | Adaptation |
|---|---|---|---|
| input | `explicit domain ontology/enriched.json inputs` | `$` → `src/agents/integration.py:IntegrationAgent.run` / `domains` | src.run.integrate selects distinct completed domain runs and constructs domain name to live class list. The artifact text is a descriptive multi-run requirement, not a relative file glob. |
| input | `explicit selected domain ontology.ttl and run.json inputs` | `$` → `src/tools/integration.py:load_domain` / `s` | Select readable completed source runs, one per distinct domain, before adapting live classes and parsing formal graphs. Explicit IDs avoid latest-run ambiguity. |
| output | `candidates.json` | `$` → `src/run.py:integrate` / `integration.public_candidates(result.candidates)` | The name is computed from selected domains and recorded in integration.json. Master imports source formal ontologies; merged unions them. Source literature layers remain separate. |
| output | `mappings.json` | `$.mappings` → `src/run.py:integrate` / `result` | The name is computed from selected domains and recorded in integration.json. Master imports source formal ontologies; merged unions them. Source literature layers remain separate. |
| output | `bridge_concepts.json` | `$.clusters` → `src/run.py:integrate` / `result` | The name is computed from selected domains and recorded in integration.json. Master imports source formal ontologies; merged unions them. Source literature layers remain separate. |
| output | `integration.json` | `$` → `src/run.py:integrate` / `integration manifest` | The name is computed from selected domains and recorded in integration.json. Master imports source formal ontologies; merged unions them. Source literature layers remain separate. |
| output | `validation.json` | `$` → `src/run.py:integrate` / `validation` | The name is computed from selected domains and recorded in integration.json. Master imports source formal ontologies; merged unions them. Source literature layers remain separate. |
| output | `<name>.ttl` | `$` → `src/run.py:integrate` / `master` | The name is computed from selected domains and recorded in integration.json. Master imports source formal ontologies; merged unions them. Source literature layers remain separate. |
| output | `<name>.jsonld` | `$` → `src/run.py:integrate` / `master` | The name is computed from selected domains and recorded in integration.json. Master imports source formal ontologies; merged unions them. Source literature layers remain separate. |
| output | `<name>_merged.ttl` | `$` → `src/run.py:integrate` / `merged` | The name is computed from selected domains and recorded in integration.json. Master imports source formal ontologies; merged unions them. Source literature layers remain separate. |
| output | `integration_report.md` | `$` → `src/run.py:integrate` / `integration.report(...)` | The name is computed from selected domains and recorded in integration.json. Master imports source formal ontologies; merged unions them. Source literature layers remain separate. |

## Follow the source operations

The sequence describes the implemented plan. Profile-dependent branches and guarded optional operations are stated explicitly; it does not assert that every branch runs in every attempt.

1. **Select explicit distinct domains** — `src/tools/integration.py:select_runs`. Require completed interop, formal export and enriched records, reject duplicate domain runs and record revision mismatch notes.

2. **Adapt classes and load graphs** — `src/tools/integration.py:load_domain`. Exclude non-live classes; compute category/parent labels and attach source run/domain context. Parse the full source formal graph independently of the comparison records.

3. **Generate candidate pairs** — `src/agents/integration.py:IntegrationAgent._candidates`. Find cross-domain label/synonym and optional embedding candidates, rank them and assign pair IDs after unusable labels are filtered.

4. **Review bounded mappings** — `src/agents/integration.py:IntegrationAgent._decide`. Apply configured review cap, retain unreviewed/missing decisions, guard equivalence and downgrade unsafe claims. Missing decisions can still yield guarded label-based exact mappings.

5. **Build bridge groups** — `src/agents/integration.py:IntegrationAgent._clusters`. Group equivalent/exact/shared-IRI connections across domains. A bridge group is a saved cluster summary, not necessarily a newly minted OWL bridge class.

6. **Build master imports and links** — `src/tools/integration.py:build_master`. Preserve source ontology imports and attach selected cross-domain mappings/provenance to the master graph.

7. **Validate and merge formal graphs** — `src/tools/integration.py:validate`. Check master round trip and integration structure. merge then unions master and all source formal graphs; it does not union domain_layer literature graphs.

8. **Save provenance and reports** — `src/run.py:integrate`. Write exports, public candidates, mappings, bridge summaries, validation, compute/report and manifest source identities; update aggregate evaluation. No source run is modified.

## Handle the return and persistence

- agent returns candidates,mappings,clusters,stats
- orchestrator saves master/imports, merged formal union, mappings/bridges, validation, report and integration manifest

load_domain adapts only live classes for matching but also loads each full formal source graph. Master imports sources; merged unions formal graphs. Literature claims remain in source domain_layer files. Bridge records describe mapping-connected clusters, not guaranteed new OWL classes.

## Assess and choose the next action

Run the read-only helper from the repository root in the documentation environment. `RUN_FOLDER` means an existing run-relative directory under the selected outputs root, not a guessed future run. Guide retrieval requires no run folder. Use the integration folder for integration, the report folder or domain root for reports, and the domain attempt for other stages.

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py guide --step integrate
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step integrate --phase before
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step integrate --phase after
```

The helper never runs pipeline commands or repairs data. `blocked` stops the proposed advance; `runtime-check` requires real environment/scope checks; `review` requires evidence or domain review. A successful bounded predicate does not certify all schema fields or scientific meaning. File hashes are rechecked to detect changes during observation.

| Check | Phase | Scope |
|---|---|---|
| `shape-validation` (shape) | after | validation.json |
| `mapping-records` (shape) | after | mappings.json |
| `bridge-records` (shape) | after | bridge_concepts.json |
| `source-readiness` (runtime_condition) | before | Bind explicit source run IDs and inspect each completed interop export before creating a new integration. An old integration folder cannot establish readiness of a proposed new selection. |
| `mapping-and-bridge-provenance` (integration_links) | after | Saved joins |
| `structural-validation` (saved_validation) | after | validation.json |
| `master-roundtrip` (rdf_pair) | after | Parse local Turtle/JSON-LD exports without fetching imports/remote contexts; compare exact graph equality up to 12000 triples per graph and 40 distinct blank-node identifiers across the pair. Larger comparisons remain unverified review findings. |
| `review-findings` (scientific_review) | after | Review capped/unreviewed candidates, missing decisions, exact versus equivalent semantics, downgraded mappings, bridge membership and source freshness. Full source ontologies are preserved in merged formal output; literature layers remain separate. |

Completion rule: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: Resolve missing/duplicate-domain source runs, stale source revisions and validation failures; create a new integration ID after corrected domain exports.

Limit: Cross-domain links are not a replacement for source domain graphs; literature claims remain in their source layers.

Follow `canAdvanceTo` to the next conceptual stage and inspect its mode-specific prerequisites. A rerun requires freshness review of stages linked by `invalidatesStep`; the documentation helper never deletes or reruns them. For reports, completion ends this task; integration is optional when only one domain exists.

## WebVOWL review

At http://127.0.0.1:8058/, select **Integrate completed domain ontologies** (its shortened tab label may differ). Start with Data flow to trace saved values, switch to Implementation for source operations, and select a function for its definition, formal arguments and fingerprinted source lines. The stage inspector links this worked example. Checks show before/after scope; runtime-only conditions remain visible. Use bounded Code lookup for connected records instead of loading all code nodes at once.
