# Worked task: Publish an inspectable review package

Author: Brent Thompson <brent.thompson@ucf.edu>

This is a source-reviewed operational recipe, not a claim that a new model or literature run was executed. The ontology embeds this text and fingerprints the source. Scientific acceptance and live readiness remain separate checks.

## Research task and discovery

A reviewer wants a literature-review package for the three selected completed domains and any applicable integration. Bind explicit source IDs and a new report destination before calling figures.build.

Start at `kw:CodebaseDocumentation` → `documentsWorkflow` → `hasStep` → `kw:step/reports`. Read its `skos:definition`, `contractJson`, `hasDataBinding`, `hasOperation`, `hasCheck` and `hasRecovery` links. Follow `implementedBy`/`operationImplementation` to source callables, `hasArgument` to formal names/types/defaults and `bindsArtifact` to source/output artifact specifications. Artifact incoming links identify producers and consumers.

## Bind and initialize

figures.build reads saved results and evaluation tables for explicitly selected run IDs, or revision/profile selection. Integration is optional; sweep_summary can constrain completed selections and retain failed/skipped outcomes.

| Input | Required shape or origin |
|---|---|
| `outputs` | root containing selected source runs/evaluation tables |
| `run_ids` | explicit actual source IDs; None uses revision/profile filtering |
| `out_dir` | explicit new report destination |
| `sweep_summary` | optional CSV requiring kind,limit,run_id,status,detail |

Use the trusted src.figures invocation with explicit --outputs, --runs and --out. Wrapper reports selects domains with recorded completed interoperability.

Side effects: Writes figure PNG/PDF/CSV and report products in out_dir; source pipeline artifacts are read. Per-figure exceptions become skipped entries without aborting other figures.

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
  "src.figures",
  "--runs",
  "RUN_ID",
  "--out",
  "outputs/review-RUN_ID",
  "--title",
  "Domain literature review"
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
  "reports"
]
```

### Data bindings

| Direction | Saved or explicit input | Selector → callable value | Adaptation |
|---|---|---|---|
| input | `explicit completed run IDs` | `$` → `src/figures.py:build` / `run_ids` | Bind actual selected run IDs; optional integration is separate. Reports write to explicit out_dir. |
| input | `explicit report output directory` | `$` → `src/figures.py:build` / `out_dir` | Bind the intended report destination; omission falls back to outputs/figures/<revision>. Source scope and destination are distinct. |
| output | `index.md` | `$` → `src/figures.py:build` / `out.folder` | Write the report package alongside successful plot PDF/PNG/CSV files. index.md records skipped figures; file presence is availability, not proof of recorded stage completion. |
| output | `report.md` | `$` → `src/figures.py:build` / `out.folder` | Write the report package alongside successful plot PDF/PNG/CSV files. index.md records skipped figures; file presence is availability, not proof of recorded stage completion. |
| output | `report.html` | `$` → `src/figures.py:build` / `out.folder` | Write the report package alongside successful plot PDF/PNG/CSV files. index.md records skipped figures; file presence is availability, not proof of recorded stage completion. |
| output | `sweep_summary.csv` | `$` → `src/figures.py:build` / `out.folder` | Write the report package alongside successful plot PDF/PNG/CSV files. index.md records skipped figures; file presence is availability, not proof of recorded stage completion. |

## Follow the source operations

The sequence describes the implemented plan. Profile-dependent branches and guarded optional operations are stated explicitly; it does not assert that every branch runs in every attempt.

1. **Resolve source selection** — `src/figures.py:load_runs`. Read selected runs and evaluation rows, or use revision/profile filters; collect omissions as notes. A sweep summary overrides run selection to completed domain outcomes.

2. **Attempt figures independently** — `src/figures.py:build`. Run configured figure functions plus applicable integration plots. Catch each plot failure, close figures and record its skip so other figures continue.

3. **Save successful plot bundles** — `src/figures.py:Out.save`. Write each figure PDF/PNG and plotted-data CSV, then register it for the index/report.

4. **Record skipped figures** — `src/figures.py:Out.skip`. Preserve figure name and failure/insufficient-data reason. A skip must remain visible during review.

5. **Build sweep review tables** — `src/report.py:sweep`. Assemble selected domain and applicable integration summaries from saved rows and source manifests.

6. **Render report sections** — `src/report.py:sections`. Group successful figures, source descriptions and computed explanatory paragraphs into report sections.

7. **Publish package and return path** — `src/report.py:write`. Write sweep_summary.csv, Markdown and HTML reports, including omitted/failed outcomes and skipped figures; figures.build also writes index.md and returns out.folder.

## Handle the return and persistence

- Path to report folder containing index.md, report.md, report.html, sweep_summary.csv and successfully generated figure files

A readable report can coexist with skipped figures, failed/skipped sweep outcomes or no recorded report stage. Inspect index.md and selection notes. Report availability must not be relabeled as pipeline completion.

## Assess and choose the next action

Run the read-only helper from the repository root in the documentation environment. `RUN_FOLDER` means an existing run-relative directory under the selected outputs root, not a guessed future run. Guide retrieval requires no run folder. Use the integration folder for integration, the report folder or domain root for reports, and the domain attempt for other stages.

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py guide --step reports
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step reports --phase before
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step reports --phase after
```

The helper never runs pipeline commands or repairs data. `blocked` stops the proposed advance; `runtime-check` requires real environment/scope checks; `review` requires evidence or domain review. A successful bounded predicate does not certify all schema fields or scientific meaning. File hashes are rechecked to detect changes during observation.

| Check | Phase | Scope |
|---|---|---|
| `explicit-source-readiness` (runtime_condition) | before | Resolve actual selected completed run IDs and a report destination; inspect source findings and optional integration freshness. This assessor does not generate plots. |
| `readable-package` (report_package) | after | Saved joins |
| `review-findings` (scientific_review) | after | Review skipped figures, empty selections, filtering notes and failed/skipped sweep outcomes; readable HTML does not establish complete coverage or acceptance of upstream scientific claims. |

Completion rule: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: Read index.md skipped-figure findings; regenerate reports from explicit completed run IDs after repairing source artifacts.

Limit: Readable reports do not prove every figure succeeded. Report availability is separate from recorded completion.

Follow `canAdvanceTo` to the next conceptual stage and inspect its mode-specific prerequisites. A rerun requires freshness review of stages linked by `invalidatesStep`; the documentation helper never deletes or reruns them. For reports, completion ends this task; integration is optional when only one domain exists.

## WebVOWL review

At http://127.0.0.1:8058/, select **Produce reports and figures** (its shortened tab label may differ). Start with Data flow to trace saved values, switch to Implementation for source operations, and select a function for its definition, formal arguments and fingerprinted source lines. The stage inspector links this worked example. Checks show before/after scope; runtime-only conditions remain visible. Use bounded Code lookup for connected records instead of loading all code nodes at once.
