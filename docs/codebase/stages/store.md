# Worked task: Establish shared ontology-store readiness

Author: Brent Thompson <brent.thompson@ucf.edu>

This is a source-reviewed operational recipe, not a claim that a new model or literature run was executed. The ontology embeds this text and fingerprints the source. Scientific acceptance and live readiness remain separate checks.

## Research task and discovery

Placement reports that the store is unavailable. Inspect the configured store status first. If a build is necessary, establish that no active pipeline uses it and select the existing trusted build invocation.

Start at `kw:CodebaseDocumentation` → `documentsWorkflow` → `hasStep` → `kw:step/store`. Read its `skos:definition`, `contractJson`, `hasDataBinding`, `hasOperation`, `hasCheck` and `hasRecovery` links. Follow `implementedBy`/`operationImplementation` to source callables, `hasArgument` to formal names/types/defaults and `bindsArtifact` to source/output artifact specifications. Artifact incoming links identify producers and consumers.

## Bind and initialize

Shared ontology sources and configured store location. Building is destructive to an existing store directory; first inspect status and establish exclusive ownership.

| Input | Required shape or origin |
|---|---|
| `ONTOLOGY_SOURCES` | configured source specifications |
| `ONTOLOGY_STORE` | configured shared output directory |
| `EMBED` | optional embedding settings |

Use ontologies status first. Build only when needed and no active process uses shared assets; do not run a build as an ordinary per-domain retry.

Side effects: build removes an existing configured store directory, downloads/caches source files, writes Oxigraph, SQLite index, vectors and manifest, and resets process caches.

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
  "ontologies",
  "build"
]
```

No separate WRAPPER invocation is defined for this stage.

### Data bindings

| Direction | Saved or explicit input | Selector → callable value | Adaptation |
|---|---|---|---|
| input | `explicit configured ontology source specifications` | `$` → `src/tools/ontostore.py:build` / `ONTOLOGY_SOURCES` | Resolve source configuration in the trusted runtime. This is not a run-relative artifact glob. |
| output | `configured ONTOLOGY_STORE (default outputs/cache/ontology_store/)` | `$` → `src/tools/ontostore.py:build` / `manifest` | The returned manifest describes sources/index/embedding recipe; the store is shared and has no per-domain stage record. |

## Follow the source operations

The sequence describes the implemented plan. Profile-dependent branches and guarded optional operations are stated explicitly; it does not assert that every branch runs in every attempt.

1. **Inspect readiness and ownership** — `src/tools/ontostore.py:status`. Inspect status and readiness before considering a rebuild. Runtime process ownership must be established separately.

2. **Fetch configured sources** — `src/tools/ontostore.py:_fetch`. Resolve the configured source or current submission into a cached file; build fingerprints the bytes and detects RDF format.

3. **Load source graphs** — `src/tools/ontostore.py:build`. Replace the configured store only under exclusive safe write scope; bulk-load source graphs into Oxigraph and discover versions.

4. **Extract term records** — `src/tools/ontostore.py:_extract`. Extract class/property labels, definitions, hierarchy and mappings from the loaded store.

5. **Write searchable index** — `src/tools/ontostore.py:_write_index`. Write the SQLite term index used by read-only ontology retrieval.

6. **Build optional vectors** — `src/tools/ontostore.py:_write_vectors`. Embed indexed term descriptions when configured, then persist vectors and embedding recipe information.

7. **Save manifest and inspect status** — `src/tools/ontostore.py:build`. Write source hashes, counts and embedding metadata, reset process caches and return the manifest. require checks file presence only, so inspect status for fuller readiness.

## Handle the return and persistence

- manifest dictionary; status reports readiness separately

The build deletes an existing configured store before rebuilding. require() checks index/manifest existence only; status() supplies additional readiness findings. This guide never executes a build.

## Assess and choose the next action

Run the read-only helper from the repository root in the documentation environment. `RUN_FOLDER` means an existing run-relative directory under the selected outputs root, not a guessed future run. Guide retrieval requires no run folder. Use the integration folder for integration, the report folder or domain root for reports, and the domain attempt for other stages.

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py guide --step store
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step store --phase before
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step store --phase after
```

The helper never runs pipeline commands or repairs data. `blocked` stops the proposed advance; `runtime-check` requires real environment/scope checks; `review` requires evidence or domain review. A successful bounded predicate does not certify all schema fields or scientific meaning. File hashes are rechecked to detect changes during observation.

| Check | Phase | Scope |
|---|---|---|
| `exclusive-ready-store` (runtime_condition) | before, after | Inspect the actual configured store status and exclusive safe write scope. This assessor never opens, builds or repairs the shared store. |

Completion rule: Confirm the configured ontology-store DB and manifest exist and inspect ontologies status; build/require implementations define readiness. Do not rebuild an already-valid active store.

Recovery: Inspect configured DB/manifest and status; build only a missing/unusable store when no active job uses it.

Limit: Store readiness and exclusive safe write scope require runtime confirmation.

Follow `canAdvanceTo` to the next conceptual stage and inspect its mode-specific prerequisites. A rerun requires freshness review of stages linked by `invalidatesStep`; the documentation helper never deletes or reruns them. For reports, completion ends this task; integration is optional when only one domain exists.

## WebVOWL review

At http://127.0.0.1:8058/, select **Prepare ontology store** (its shortened tab label may differ). Start with Data flow to trace saved values, switch to Implementation for source operations, and select a function for its definition, formal arguments and fingerprinted source lines. The stage inspector links this worked example. Checks show before/after scope; runtime-only conditions remain visible. Use bounded Code lookup for connected records instead of loading all code nodes at once.
