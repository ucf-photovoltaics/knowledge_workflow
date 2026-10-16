# Worked task: Add definitions, restrictions and candidates

Author: Brent Thompson <brent.thompson@ucf.edu>

This is a source-reviewed operational recipe, not a claim that a new model or literature run was executed. The ontology embeds this text and fingerprints the source. Scientific acceptance and live readiness remain separate checks.

## Research task and discovery

Placed TOPCon classes have stable IDs and parents. Read them with normalized scientific and causal relations, then discover EnrichmentAgent.run(classes,relations,causal) and its two-element return tuple.

Start at `kw:CodebaseDocumentation` → `documentsWorkflow` → `hasStep` → `kw:step/enrich`. Read its `skos:definition`, `contractJson`, `hasDataBinding`, `hasOperation`, `hasCheck` and `hasRecovery` links. Follow `implementedBy`/`operationImplementation` to source callables, `hasArgument` to formal names/types/defaults and `bindsArtifact` to source/output artifact specifications. Artifact incoming links identify producers and consumers.

## Bind and initialize

Placed class records and normalized relation/causal lists are independent arguments. Only non-excluded classes are enriched, but all class identities are returned.

| Input | Required shape or origin |
|---|---|
| `classes[]` | placed canonical fields including id,label,parent,excluded,alt_labels,definitions,iri |
| `relations[]` | canonical s,p,o and evidence/support |
| `causal[]` | canonical cause,effect,polarity and evidence/support |

Require the shared ontology store, construct EnrichmentAgent(run.ledger), then call run(classes,relations,causal) via the existing stage.

Side effects: Mutates live class dictionaries in memory: initializes definitions/restrictions/disjointness, adds candidates and annotations. The orchestrator saves enriched classes separately from placement classes.

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
  "enrich",
  "--run-id",
  "RUN_ID",
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
  "--domain",
  "DOMAIN_ID",
  "--stage",
  "enrich"
]
```

### Data bindings

| Direction | Saved or explicit input | Selector → callable value | Adaptation |
|---|---|---|---|
| input | `ontology/classes.json` | `$` → `src/agents/enrichment.py:EnrichmentAgent.run` / `classes` | Read the corresponding saved JSON value; pass classes and normalized claims as separate arguments, not a combined ontology graph. |
| input | `normalized/relations.json` | `$` → `src/agents/enrichment.py:EnrichmentAgent.run` / `relations` | Read the corresponding saved JSON value; pass classes and normalized claims as separate arguments, not a combined ontology graph. |
| input | `normalized/causal.json` | `$` → `src/agents/enrichment.py:EnrichmentAgent.run` / `causal` | Read the corresponding saved JSON value; pass classes and normalized claims as separate arguments, not a combined ontology graph. |
| output | `ontology/enriched.json` | `$` → `src/run.py:enrich` / `classes` | Unpack the agent tuple (classes, properties), then serialize each component. |
| output | `ontology/properties.json` | `$` → `src/run.py:enrich` / `properties` | Unpack the agent tuple (classes, properties), then serialize each component. |
| output | `ontology/materials_project.json` | `$` → `src/run.py:enrich` / `agent.materials_log` | Persist optional Materials Project lookup/annotation results and review provenance. |
| output | `ontology/review_issues.json` | `$` → `src/run.py:enrich` / `ontology_review.issues(classes)` | Refresh the shared class review findings from enriched classes. |
| output | `ontology/cross_domain_candidates.json` | `$` → `src/run.py:enrich` / `ontology_review.correspondences(...)` | Advisory historical correspondences; these do not replace explicit source-run selection for integration. |

## Follow the source operations

The sequence describes the implemented plan. Profile-dependent branches and guarded optional operations are stated explicitly; it does not assert that every branch runs in every attempt.

1. **Initialize live class enrichment** — `src/agents/enrichment.py:EnrichmentAgent.run`. Retain excluded records, initialize live definitions/restrictions/disjointness and determine whether the configured profile permits model-knowledge definitions.

2. **Gather mapping candidates** — `src/agents/enrichment.py:EnrichmentAgent._candidates`. Combine store candidates, bounded portal searches and propagated mappings, preserving source, score, path and label-match distinctions.

3. **Add optional material annotations** — `src/agents/enrichment.py:EnrichmentAgent._materials`. Annotate applicable material classes using configured Materials Project support, retaining lookup evidence and review results.

4. **Translate evidenced causal claims** — `src/agents/enrichment.py:EnrichmentAgent._causal`. Create local and appropriate RO/CCO causal restrictions for eligible evidence-backed canonical claims.

5. **Resolve scientific property candidates** — `src/agents/enrichment.py:EnrichmentAgent._property_candidates`. Retrieve object properties for evidenced non-is_a relations and retain only candidates fitting domain and range.

6. **Commit deterministic predicate matches** — `src/agents/enrichment.py:EnrichmentAgent._predicate_restrictions`. Use exact or configured tie-broken property matches directly, leaving other eligible relations for model review.

7. **Apply profile-specific enrichment** — `src/agents/enrichment.py:EnrichmentAgent._apply`. Apply local split-pass or frontier combined answers; retain definition basis/status, validate restrictions against source relations and flag unsupported results.

8. **Check disjointness and persist tuple** — `src/agents/enrichment.py:EnrichmentAgent._local_properties`. After dropping disjointness conflicting with paper is_a, build local property descriptions. The orchestrator unpacks classes/properties and saves sidecars.

## Handle the return and persistence

- tuple[classes, properties dictionary]
- agent.materials_log and agent.doubts are saved separately

Unpack classes,properties. Preserve all class identities, but require definition/restriction fields only for live classes. Generated, evidence-draft and supported definitions have different authority; external candidates are not committed mappings.

## Assess and choose the next action

Run the read-only helper from the repository root in the documentation environment. `RUN_FOLDER` means an existing run-relative directory under the selected outputs root, not a guessed future run. Guide retrieval requires no run folder. Use the integration folder for integration, the report folder or domain root for reports, and the domain attempt for other stages.

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py guide --step enrich
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step enrich --phase before
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step enrich --phase after
```

The helper never runs pipeline commands or repairs data. `blocked` stops the proposed advance; `runtime-check` requires real environment/scope checks; `review` requires evidence or domain review. A successful bounded predicate does not certify all schema fields or scientific meaning. File hashes are rechecked to detect changes during observation.

| Check | Phase | Scope |
|---|---|---|
| `shape-ontology-enriched` (shape) | after | ontology/enriched.json |
| `review-findings` (scientific_review) | after | Generated definitions, imported definitions and evidence-supported definitions have different authority. |
| `placed-input` (shape) | before | ontology/classes.json |
| `properties-object` (shape) | after | ontology/properties.json |
| `placed-enriched-coverage` (identity_coverage) | after | ontology/classes.json |
| `restriction-targets` (references) | after | ontology/enriched.json |
| `disjoint-targets` (references) | after | ontology/enriched.json |
| `canonical-input-endpoints` (canonical_references) | before | Saved joins |
| `placed-input-parents` (references) | before | ontology/classes.json |

Completion rule: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: Inspect unsupported definitions, failed rows and restrictions dropped; reattempt enrichment and regenerate interop/integration/reports from the new results.

Limit: Generated definitions, imported definitions and evidence-supported definitions have different authority.

Follow `canAdvanceTo` to the next conceptual stage and inspect its mode-specific prerequisites. A rerun requires freshness review of stages linked by `invalidatesStep`; the documentation helper never deletes or reruns them. For reports, completion ends this task; integration is optional when only one domain exists.

## WebVOWL review

At http://127.0.0.1:8058/, select **Add definitions and formal relationships** (its shortened tab label may differ). Start with Data flow to trace saved values, switch to Implementation for source operations, and select a function for its definition, formal arguments and fingerprinted source lines. The stage inspector links this worked example. Checks show before/after scope; runtime-only conditions remain visible. Use bounded Code lookup for connected records instead of loading all code nodes at once.
