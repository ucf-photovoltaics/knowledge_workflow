# Worked task: Place canonical concepts and assign IRIs

Author: Brent Thompson <brent.thompson@ucf.edu>

This is a source-reviewed operational recipe, not a claim that a new model or literature run was executed. The ontology embeds this text and fingerprints the source. Scientific acceptance and live readiness remain separate checks.

## Research task and discovery

Normalization has produced a canonical TOPCon concept vocabulary. Read normalized/concepts.json and relations.json, bind the nonempty selected domain name and discover OntologyAgent.run(concepts,relations,domain).

Start at `kw:CodebaseDocumentation` → `documentsWorkflow` → `hasStep` → `kw:step/ontology`. Read its `skos:definition`, `contractJson`, `hasDataBinding`, `hasOperation`, `hasCheck` and `hasRecovery` links. Follow `implementedBy`/`operationImplementation` to source callables, `hasArgument` to formal names/types/defaults and `bindsArtifact` to source/output artifact specifications. Artifact incoming links identify producers and consumers.

## Bind and initialize

Canonical concepts and relations are read from normalized files; the nonempty domain is run.manifest.collection.name. No raw paper concept IDs should be supplied here.

| Input | Required shape or origin |
|---|---|
| `concepts[]` | id,label,type,alt_labels,definitions and preserved canonical evidence/support fields |
| `relations[]` | canonical s,p,o with evidence/support |
| `domain` | nonempty selected domain name |

Require the existing ontology store, then construct OntologyAgent(run.ledger) through src.run.ontology or the wrapper stage.

Side effects: Constructs new class dictionaries and repairs their hierarchy; source normalized files are not rewritten by the orchestrator.

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
  "ontology",
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
  "ontology"
]
```

### Data bindings

| Direction | Saved or explicit input | Selector → callable value | Adaptation |
|---|---|---|---|
| input | `normalized/concepts.json` | `$` → `src/agents/ontology.py:OntologyAgent.run` / `concepts` | src.run.ontology reads this saved canonical JSON value and passes it unchanged to the corresponding agent argument. |
| input | `normalized/relations.json` | `$` → `src/agents/ontology.py:OntologyAgent.run` / `relations` | src.run.ontology reads this saved canonical JSON value and passes it unchanged to the corresponding agent argument. |
| output | `ontology/classes.json` | `$` → `src/run.py:ontology` / `classes` | Serialize the returned class list; review issues are written separately. |
| input | `run.json` | `$.collection.name` → `src/agents/ontology.py:OntologyAgent.run` / `domain` | Bind the selected nonempty domain name from the run collection context; it forms the domain segment of stable class IRIs. |
| output | `ontology/review_issues.json` | `$` → `src/run.py:ontology` / `ontology_review.issues(classes)` | Save class-level review findings separately from classes; enrichment later refreshes this shared artifact. |

## Follow the source operations

The sequence describes the implemented plan. Profile-dependent branches and guarded optional operations are stated explicitly; it does not assert that every branch runs in every attempt.

1. **Gather corpus context** — `src/tools/ontology_review.py:context`. Collect canonical relations and evidence context for placement choices.

2. **Prefer known named classes** — `src/agents/ontology.py:OntologyAgent._name_matches`. Use configured ontology name matches only when their store hierarchy reaches BFO; retain unaligned-match doubts.

3. **Choose category and parent** — `src/agents/ontology.py:OntologyAgent._pick_split`. Local-tier category/exclusion and parent passes use type-derived defaults and candidate menus. Frontier-tier _pick_combined is the alternative branch.

4. **Assign stable domain IRIs** — `src/agents/ontology.py:OntologyAgent.run`. Preserve canonical IDs; derive domain class IRIs from label/type hashes. Preserve excluded records and flag duplicate identities rather than silently dropping them.

5. **Repair hierarchy and fallbacks** — `src/agents/ontology.py:OntologyAgent._repair`. Check parents and cycles, apply configured fallbacks and preserve review information; a parseable fallback is not a validated scientific placement.

6. **Apply evidenced paper parents** — `src/tools/ontology_review.py:paper_parents`. Apply supported paper is_a parent information with category-conflict review safeguards.

7. **Apply lexical heads and save** — `src/agents/ontology.py:OntologyAgent._lexical_heads`. Consider lexical-head corpus parents after repairs; src.run.ontology saves classes, uncertainty and review findings.

## Handle the return and persistence

- list of classes preserving canonical IDs, plus iri,parent,parent_source,excluded and optional review_flags

Canonical IDs remain the join key even after a domain IRI is assigned. Keep excluded records when comparing input/output coverage. Type/category fallbacks and lexical parents require review, even when the graph is structurally usable.

## Assess and choose the next action

Run the read-only helper from the repository root in the documentation environment. `RUN_FOLDER` means an existing run-relative directory under the selected outputs root, not a guessed future run. Guide retrieval requires no run folder. Use the integration folder for integration, the report folder or domain root for reports, and the domain attempt for other stages.

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py guide --step ontology
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step ontology --phase before
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step ontology --phase after
```

The helper never runs pipeline commands or repairs data. `blocked` stops the proposed advance; `runtime-check` requires real environment/scope checks; `review` requires evidence or domain review. A successful bounded predicate does not certify all schema fields or scientific meaning. File hashes are rechecked to detect changes during observation.

| Check | Phase | Scope |
|---|---|---|
| `shape-ontology-classes` (shape) | after | ontology/classes.json |
| `review-findings` (scientific_review) | after | Fallback placement, exclusions and review flags require domain review. |
| `canonical-input` (shape) | before | normalized/concepts.json |
| `canonical-class-coverage` (identity_coverage) | after | normalized/concepts.json |
| `parent-endpoints` (references) | after | ontology/classes.json |
| `canonical-input-endpoints` (canonical_references) | before | Saved joins |

Completion rule: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: Check shared-store readiness and unresolved parents/exclusions; retry placement in a new attempt, then regenerate dependent enrichment and exports.

Limit: Fallback placement, exclusions and review flags require domain review.

Follow `canAdvanceTo` to the next conceptual stage and inspect its mode-specific prerequisites. A rerun requires freshness review of stages linked by `invalidatesStep`; the documentation helper never deletes or reruns them. For reports, completion ends this task; integration is optional when only one domain exists.

## WebVOWL review

At http://127.0.0.1:8058/, select **Place canonical concepts** (its shortened tab label may differ). Start with Data flow to trace saved values, switch to Implementation for source operations, and select a function for its definition, formal arguments and fingerprinted source lines. The stage inspector links this worked example. Checks show before/after scope; runtime-only conditions remain visible. Use bounded Code lookup for connected records instead of loading all code nodes at once.
