# Validation — 2026-10-15

## Search actions and malformed-concept safeguards

The dashboard suite passed **50 tests**. The isolated extraction quality checkout passed **31 tests** (five new safeguard tests and the existing runtime module). The exact 17,513-character label is a regression fixture. Checks cover dependent claims and RDF copies, safe ontology-source joins, repeated IRIs, bounded review previews, guarded chat packets, no provider call when clean evidence is empty, original file/cache hashes, extraction pass prompts, ID renumbering, cached extraction, and the normalization boundary.

Browser checks against n20 integration outputs verified visible row actions into the correct evidence/provenance tab and source concept, filtering the virtualized quality table to the actual malformed label, and an evidence-only no-match answer for its unrelated word stream. No live model requests were made. Screenshots: `outputs/dashboard/search-evidence-actions.png` and `search-quality-review.png`.

The pipeline guard is prepared only in `C:/Users/brent/.codex/worktrees/extraction-quality/knowledge_workflow`; its patch is `outputs/development/extraction-quality/extraction-quality.patch`. `git apply --check` passes against the unchanged main checkout. Pipeline source, current runs, source PDFs, caches, credentials and port 8055 remain untouched. Only the enhanced 8056 dashboard was reloaded.


## Workflow chat models and readable labels

The dashboard suite passed **46 tests**. Added coverage verifies recorded agent routing/model inheritance, configured model alternatives, missing-credential messages, profile reads without environment changes, project fallback, readable table headings with preserved source keys, unchanged scientific variable names, and mocked OpenAI-compatible/Anthropic requests. No live model calls were made.

Browser checks confirmed the default Same as workflow dropdown for the saved integration, friendly model labels and table headings, evidence-only chat without raw review codes, graph focus from selected search rows, source concept provenance navigation, and inventory preview selection. Exact saved field names remain in raw artifact previews. Screenshot: `outputs/dashboard/chat-model-selector.png`. Only the separate 8056 server was reloaded; pipeline files, current runs, credentials and the original dashboard were left unchanged.


## Focus boxes and Visual Exploration

The dashboard suite passed **40 tests**. New fixtures verify term and evidence boxes, recorded figure-page focus, raster/vector region estimates, unmatched-focus behavior, unchanged original PDF hashes, annotated-copy coordinates including rotated PDFs, scoped search, graph neighborhoods, and a mocked provider request with bounded cited context. Model transport is mocked; no live provider or model is used by these checks.

Browser checks used saved n20 integration/domain outputs on port 8056. Search and saved-evidence chat rendered, selected concepts focused the graph, and a real concept produced 161 boxes in an annotated PDF copy. A real vector figure displayed a caption box and explicitly estimated plot-region box. Original real-PDF hashes were unchanged. Stage-to-exploration source/file handoff, graph persistence and chat persistence across polling cycles also passed. Screenshots are under `outputs/dashboard/`: `concept-boxed-preview.png`, `figure-boxed-preview.png`, `visual-exploration-chat.png` and `visual-exploration-graph.png`.

This feature reuses the Neurosymbolic layout pattern only; no Neurosymbolic code was imported or changed. Pipeline code, requirements, ontology stores, current runs and the port-8055 dashboard were preserved. Only the separate 8056 server was reloaded.


## Integration detail and source media update

The dashboard suite passed **33 tests**. New fixtures cover repeated paper/concept IDs across domains, domain filters, missing source runs, ambiguous shared IRIs, escaped reference labels, scoped media files, recorded figure links, and PDF page rendering/bounds.

Browser checks against the saved n20 integration rendered every source-result view, opened real PDFs and recorded figure-page images (HTTP 200), displayed paper thumbnails on hover, compared both mapping endpoints and all available selected bridge members, filtered by domain, and navigated to the correct source provenance record. Screenshots: `outputs/dashboard/integration-paper-hover.png` and `integration-source-comparison.png`. Source joins are batched per table to avoid repeated filesystem scans.

Only the separate port-8056 dashboard was reloaded. Pipeline source, saved runs, dependency environments, ontology stores and the original port-8055 dashboard were preserved. Figures without saved standalone images are shown as labeled source-page previews, not inferred crops.


## Research views update

The complete dashboard regression suite passed **30 tests**. Added coverage includes complete/unknown/partial/restricted artifacts, missing outputs, superseded stages, per-paper concept ID scoping, recorded versus reconstructed versus ambiguous lineage, conflicting and unreadable mapping files, evidence filters, definition/candidate/mapping joins, integration source boundaries, and unchanged source-file hashes after inspection.

Browser verification used a separate server on port **8056**, leaving the existing port-8055 dashboard and pipeline processes untouched. Real saved runs verified stage-table rendering, filtered paper selection and canonical provenance navigation; the latest integration opened a source domain record. An isolated synthetic dashboard project verified recorded lineage and evidence-status filtering, unknown-file preview/download, and an actual visible WebVOWL class click into the corresponding provenance inspector. The viewer now fits its graph after initial layout. The fixture is test data, not a live scientific run. Final browser checks also verified that explicitly opened artifacts remain stable as new files arrive, downloads retain the selected filename, and paper-only navigation clears an earlier canonical filter.

These views do not apply the isolated pipeline-lineage patch and do not backfill existing runs. No live model run or ontology-store update was performed.

## Existing-output monitoring update

The expanded focused suite passed **17 tests**. Browser verification discovered 183 existing output folders, automatically selected `reliability-n25-20261014-154503`, showed recent enrichment activity, listed 26 extraction artifacts, and blocked execution controls for the externally monitored run. No JavaScript or Shiny output errors occurred. Existing-run monitoring reads only the original output folders; only the dashboard server was reloaded.

## Focused offline checks

Command:

```powershell
outputs/dashboard/.venv/Scripts/python.exe -m pytest dpv_dashboard/tests -q --basetemp outputs/dashboard/test-tmp-verified
```

Result: **14 passed in 3.06 seconds**. These cover recursive selection, DOI deduplication, domain-wide citation ranking across personal/group libraries, restricted library discovery, prerequisite guards, restart snapshots, upstream compute filtering, existing parser/chunker reuse, child-process configuration isolation, durable supervised failure, cancellation of a temporary child process, report attempt preservation, scoped file access, and WebVOWL mapping/restriction projection.

The cancellation check ran outside the execution sandbox so Windows could exercise native process-tree termination. It exposed a Windows reader/atomic-replacement race, now covered by the bounded replacement retry in the new persistence code.

## Browser checks

Used headless Microsoft Edge against the local app with synthetic, clearly named verification projects. No real literature/model execution was launched.

- All nine stage tabs rendered without Shiny output errors.
- Home project creation selected the new project and opened Zotero ingestion.
- Selected Turtle downloaded as `ontology.ttl`.
- The embedded upstream WebVOWL viewer showed the selected fixture's Solar cell/Device graph.
- A marker in the iframe persisted across multiple polling cycles, verifying that polling no longer recreates the viewer.
- No JavaScript page errors occurred during the verified flow.
- Screenshots are saved under `outputs/dashboard/home-screen.png` and `ontology-screen.png`; the latter uses synthetic ontology data.

## Scope and limits

The original pipeline and neurosymbolic source were not edited. The existing pipeline environment and requirements were not changed; dashboard dependencies were installed separately.

Live authenticated Zotero discovery, provider/model calls, full scientific extraction, ontology-store compatibility during a real run, and production hosting were not verified. The application is a local first implementation. Existing long-running jobs outside this dashboard were not stopped or modified.

## Scientific graph defaults and provenance verification

The dashboard suite passed **53 tests in 5.06 seconds**. Added fixtures verify scientific defaults, optional disjointness, literature toggling, recorded concept alignment, claim evidence in focused neighborhoods, missing-source coverage, and preservation of input files.

Headless Edge verified the existing integration-n5-20261015-150628 run on port 8056: 1,614 default edges, including 675 literature relationships, with disjointness hidden. A native SVG relationship selection opened its evidence/source panel; disjointness and literature controls changed the displayed payload correctly. No JavaScript or Shiny output errors were observed. Dense labels can overlap; the final automated selection dispatched a click to the intended SVG label. Screenshot: outputs/dashboard/scientific-graph-provenance.png.

No pipeline/model execution, saved ontology modification, dependency installation, or original port-8055 dashboard restart was performed.

## Approved dashboard presentation improvements

The offline suite passed **58 tests in 8.43 seconds**. New regression checks cover compact-table selection after reordered rows, retention of hidden source/run identifiers, restoration of plain records from HTML displays, escaped inspector content, repeated findings versus affected concepts, and paper-scoped relationship-name resolution.

Browser checks on the isolated 8057 preview verified: read-only execution buttons disabled; the review shortcut selects claims with the review-only filter; selecting a claim opens its named inspector; an integration source concept resolves to its original Tea run; saved plot previews open; a source-paper gallery shows five captioned figure records and caption search isolates Raman Figure 3; graph counts distinguish 650 supplied nodes / 502 relationships from WebVOWL's rendered subset; graph-specific controls hide on Chat. No provider/model or Zotero calls were made. The port-8056 dashboard was then reloaded with the verified code; port 8055 and pipeline jobs were left running.

Limits: galleries show up to 100 files/figures; research previews show up to 10,000 rows, with limits stated and original files available. No scientific correctness, mapping calibration, new model outputs, or missing historical provenance is inferred. Source-page thumbnails are explicitly distinguished from cropped figures. Review categories are grouped without inventing severity. Run-to-run semantic change comparison and a structured human review-decision workflow remain separate future features.

Saved-run comparison now offers an explicitly selected baseline within the same named run family. It reports saved-count deltas and literal label differences, with a warning that these do not establish semantic identity or merge decisions. The final suite passed **59 tests in 8.91 seconds**, adding a regression for this distinction. The final port-8056 process is the enhanced dashboard only; the temporary port-8057 preview was stopped.

Final visual-density polish collapses long alternative-label lists and bounds visible reference labels while preserving full originals in metadata. The affected presentation/provenance suites passed **28 tests in 2.43 seconds** after the 59-test full suite. Port-8056 browser verification also confirmed the explicit Reliability-5 baseline against Reliability-10 (648 → 1,433 canonical records), correct selected-record inspection and suspicious caption-like alias warnings, with no Shiny output errors.

## Concept growth legend and top-stage navigation

All nine pipeline-strip steps are native named buttons, including waiting stages and read-only monitored runs. Clicking a step activates its existing stage tab, scrolls to its heading and moves keyboard focus there; navigation does not launch work. Concept growth previews show a solid-line/shaded-band legend and explain the empirical 5th–95th percentile over randomized orders of the same papers. The explanation distinguishes ordering variability from scientific correctness or a confidence interval. HTML report previews add the same explanation and correct the overly strong statement that a line inside the band proves order does not matter. Saved reports and PNGs are not rewritten.

Validation: **62 tests passed in 5.07 seconds**. Browser checks verified all nine destinations, heading scroll position/focus, Enter activation, standalone growth explanation, and one explanation in the embedded integration report. No Shiny output errors were observed. Only dashboard files and its enhanced server were changed; pipeline source and saved results remain intact.

## Launcher, documentation and report presentation — 2026-10-16

Launcher and Python module now default to loopback port 8056, with explicit port overrides retained. PowerShell parsed the launcher successfully and Python CLI help completed without starting a listener. Local links in the updated root README, dashboard guide and architecture guide resolved.

70 dashboard fixture tests passed, including styled HTML report rendering and local-image URL resolution. Browser verification on integration-n15-20261015-150628 confirmed the existing-output selector inside the top workflow toolbar, the scrollable figure library above Report & findings, and all 31 embedded report images loading. This n15 report already embeds images as data URLs; relative image resolution is a compatibility fix, not the explanation of its original spacing. Saved reports and pipeline source were not rewritten. Only enhanced dashboard 8056 was restarted. The suite does not establish scientific validity or complete documentation of every internal function.

## Codebase documentation, operational ontology and toolbar — 2026-10-16

Browser checked the three-column desktop toolbar: execution left, saved-output selector middle, latest integration right. Source run identity remains in one compact summary; technical ID is collapsed. First-party author headers and summaries were added with Python executable-AST preservation checks; source digests and line references regenerated.

Dashboard fixtures:70 passed. Pipeline fixtures:87 passed in an isolated documentation/test environment with workspace-local temp files. The operational codebase ontology contains11 step specifications and18 source-checked command templates, backed by109 code files and997 callable references. SHACL, negative-shape fixture, query examples, snapshot integrity and bounded OWL-RL/disjointness checks passed. Full OWL2DL classification and live execution of all literature/provider templates were not performed. See docs/codebase/verification.md and docs/ontology/validation.json for precise scope.
