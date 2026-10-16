# Worked task: Export formal ontology and literature claims

Author: Brent Thompson <brent.thompson@ucf.edu>

This is a source-reviewed operational recipe, not a claim that a new model or literature run was executed. The ontology embeds this text and fingerprints the source. Scientific acceptance and live readiness remain separate checks.

## Research task and discovery

A domain has enriched classes and local properties. Supply those, Run.papers(), the selected run ID and domain to InteroperabilityAgent.run. Trace each returned field to its separately saved artifact.

Start at `kw:CodebaseDocumentation` → `documentsWorkflow` → `hasStep` → `kw:step/interop`. Read its `skos:definition`, `contractJson`, `hasDataBinding`, `hasOperation`, `hasCheck` and `hasRecovery` links. Follow `implementedBy`/`operationImplementation` to source callables, `hasArgument` to formal names/types/defaults and `bindsArtifact` to source/output artifact specifications. Artifact incoming links identify producers and consumers.

## Bind and initialize

The agent receives enriched class dictionaries, a local property dictionary, saved source papers, run ID and domain. The orchestrator separately rereads normalized concepts/claims to build the literature layer.

| Input | Required shape or origin |
|---|---|
| `classes[]` | enriched placed class records |
| `properties` | dictionary, not list |
| `papers[]` | Run.papers() persisted records |
| `run_id/domain` | selected run context |
| `norm` | separate canonical concepts/relations/causal/measurements dictionary for bottomup.build |

Require the existing store and use InteroperabilityAgent(run.ledger) through src.run.interop. Preserve source run context for provenance.

Side effects: Agent alignment/import/facet passes mutate the in-memory class records; src.run.interop does not rewrite enriched.json afterward. Persisted mapping/definition/facet sidecars record these later decisions.

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
  "interop",
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
  "interop"
]
```

### Data bindings

| Direction | Saved or explicit input | Selector → callable value | Adaptation |
|---|---|---|---|
| input | `ontology/enriched.json` | `$` → `src/agents/interoperability.py:InteroperabilityAgent.run` / `classes` | Read the saved JSON value; papers is assembled by Run.papers(). Other context arguments come from the selected run, not model-generated text. |
| input | `ontology/properties.json` | `$` → `src/agents/interoperability.py:InteroperabilityAgent.run` / `properties` | Read the saved JSON value; papers is assembled by Run.papers(). Other context arguments come from the selected run, not model-generated text. |
| input | `papers/*.json` | `$` → `src/agents/interoperability.py:InteroperabilityAgent.run` / `papers` | Read the saved JSON value; papers is assembled by Run.papers(). Other context arguments come from the selected run, not model-generated text. |
| output | `ontology.ttl` | `$.turtle` → `src/run.py:interop` / `out` | Serialize the returned result field; domain_layer is built separately by bottomup.build. |
| output | `ontology.jsonld` | `$.jsonld` → `src/run.py:interop` / `out` | Serialize the returned result field; domain_layer is built separately by bottomup.build. |
| output | `ontology/mappings.json` | `$.mappings` → `src/run.py:interop` / `out` | Serialize the returned result field; domain_layer is built separately by bottomup.build. |
| output | `ontology/validation.json` | `$.validation` → `src/run.py:interop` / `out` | Serialize the returned result field; domain_layer is built separately by bottomup.build. |
| input | `run.json` | `$.collection.name` → `src/agents/interoperability.py:InteroperabilityAgent.run` / `domain` | Bind selected domain name; run_id is run.id from the owning Run object. |
| input | `normalized/concepts.json` | `$` → `src/tools/bottomup.py:build` / `norm` | Add this canonical list to norm for the separate literature-claims layer. Runtime falls back to [] if absent; the stricter documentation boundary requires all four to avoid silent loss. |
| input | `normalized/relations.json` | `$` → `src/tools/bottomup.py:build` / `norm` | Add this canonical list to norm for the separate literature-claims layer. Runtime falls back to [] if absent; the stricter documentation boundary requires all four to avoid silent loss. |
| input | `normalized/causal.json` | `$` → `src/tools/bottomup.py:build` / `norm` | Add this canonical list to norm for the separate literature-claims layer. Runtime falls back to [] if absent; the stricter documentation boundary requires all four to avoid silent loss. |
| input | `normalized/measurements.json` | `$` → `src/tools/bottomup.py:build` / `norm` | Add this canonical list to norm for the separate literature-claims layer. Runtime falls back to [] if absent; the stricter documentation boundary requires all four to avoid silent loss. |
| output | `domain_layer.ttl` | `$` → `src/run.py:interop` / `layer` | Save this stage product separately; preserve the distinction between formal OWL, literature claims, imported definitions, facets and report metrics. |
| output | `domain_layer.jsonld` | `$` → `src/run.py:interop` / `layer` | Save this stage product separately; preserve the distinction between formal OWL, literature claims, imported definitions, facets and report metrics. |
| output | `ontology/domain_layer_metrics.json` | `$` → `src/run.py:interop` / `layer_metrics` | Save this stage product separately; preserve the distinction between formal OWL, literature claims, imported definitions, facets and report metrics. |
| output | `ontology/imported_definitions.json` | `$.imported_definitions` → `src/run.py:interop` / `out` | Save this stage product separately; preserve the distinction between formal OWL, literature claims, imported definitions, facets and report metrics. |
| output | `ontology/facets.json` | `$.facets` → `src/run.py:interop` / `out` | Save this stage product separately; preserve the distinction between formal OWL, literature claims, imported definitions, facets and report metrics. |
| output | `ontology/metrics.json` | `$.metrics` → `src/run.py:interop` / `out` | Save this stage product separately; preserve the distinction between formal OWL, literature claims, imported definitions, facets and report metrics. |
| output | `ontology_report.md` | `$` → `src/run.py:interop` / `reports.ontology_report(...)` | Save this stage product separately; preserve the distinction between formal OWL, literature claims, imported definitions, facets and report metrics. |

## Follow the source operations

The sequence describes the implemented plan. Profile-dependent branches and guarded optional operations are stated explicitly; it does not assert that every branch runs in every attempt.

1. **Commit external alignments** — `src/agents/interoperability.py:InteroperabilityAgent.align`. Choose mappings from enriched candidates using recorded methods, guards and mapping semantics; candidates alone are not accepted mappings.

2. **Import mapped definitions** — `src/agents/interoperability.py:InteroperabilityAgent.import_definitions`. Import appropriate mapped labels/definitions into in-memory classes and return an explicit import log.

3. **Assign MDS facets** — `src/agents/interoperability.py:InteroperabilityAgent.tag_facets`. Tag applicable process/study/domain facets and local properties; retain missing/failed row findings.

4. **Build formal OWL** — `src/tools/owl.py:build`. Construct formal classes/properties, hierarchy, supported restrictions, selected mappings, source provenance and store imports.

5. **Serialize and validate formal graph** — `src/agents/interoperability.py:InteroperabilityAgent.run`. Serialize the same graph to JSON-LD/Turtle, run structural and mapping checks, and return metrics and sidecars. A false validation result is still saved by the runtime.

6. **Build separate literature claims** — `src/tools/bottomup.py:build`. Use canonical concepts/claims and papers to create a separate evidence-preserving domain layer; do not assume every literature relation became an OWL axiom.

7. **Save exports and report** — `src/run.py:interop`. Save both layers and sidecars; refresh interop compute record before ontology_report reads it, then return final stage statistics for the controller to record.

## Handle the return and persistence

- mappings
- facets
- checks
- jsonld
- turtle
- validation
- imported_definitions
- metrics
- bottomup.build separately returns (Graph, metrics)

src.run.interop separately builds domain_layer from normalized evidence. It does not rewrite enriched.json after imported definitions/facets modify in-memory classes; use imported_definitions/facets sidecars for those decisions. Failed structural validation is saved, not silently repaired.

## Assess and choose the next action

Run the read-only helper from the repository root in the documentation environment. `RUN_FOLDER` means an existing run-relative directory under the selected outputs root, not a guessed future run. Guide retrieval requires no run folder. Use the integration folder for integration, the report folder or domain root for reports, and the domain attempt for other stages.

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py guide --step interop
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step interop --phase before
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step interop --phase after
```

The helper never runs pipeline commands or repairs data. `blocked` stops the proposed advance; `runtime-check` requires real environment/scope checks; `review` requires evidence or domain review. A successful bounded predicate does not certify all schema fields or scientific meaning. File hashes are rechecked to detect changes during observation.

| Check | Phase | Scope |
|---|---|---|
| `shape-ontology-validation` (shape) | after | ontology/validation.json |
| `review-findings` (scientific_review) | after | Structural validation does not validate every scientific claim or mapping. |
| `properties-input` (shape) | before | ontology/properties.json |
| `mapping-records` (shape) | after | ontology/mappings.json |
| `mapping-local-ids` (references) | after | ontology/mappings.json |
| `structural-validation` (saved_validation) | after | ontology/validation.json |
| `formal-roundtrip` (rdf_pair) | after | Parse local Turtle/JSON-LD exports without fetching imports/remote contexts; compare exact graph equality up to 12000 triples per graph and 40 distinct blank-node identifiers across the pair. Larger comparisons remain unverified review findings. |
| `claims-roundtrip` (rdf_pair) | after | Parse local Turtle/JSON-LD exports without fetching imports/remote contexts; compare exact graph equality up to 12000 triples per graph and 40 distinct blank-node identifiers across the pair. Larger comparisons remain unverified review findings. |
| `canonical-input-endpoints` (canonical_references) | before | Saved joins |
| `placed-input-parents` (references) | before | ontology/enriched.json |

Completion rule: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: Inspect saved validation issues, mappings and imported definitions; repair the originating stage and regenerate exports before integration.

Limit: Structural validation does not validate every scientific claim or mapping.

Follow `canAdvanceTo` to the next conceptual stage and inspect its mode-specific prerequisites. A rerun requires freshness review of stages linked by `invalidatesStep`; the documentation helper never deletes or reruns them. For reports, completion ends this task; integration is optional when only one domain exists.

## WebVOWL review

At http://127.0.0.1:8058/, select **Map, export and validate domain layers** (its shortened tab label may differ). Start with Data flow to trace saved values, switch to Implementation for source operations, and select a function for its definition, formal arguments and fingerprinted source lines. The stage inspector links this worked example. Checks show before/after scope; runtime-only conditions remain visible. Use bounded Code lookup for connected records instead of loading all code nodes at once.
