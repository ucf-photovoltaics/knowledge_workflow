# UCF DPV Knowledge Workflow

A standalone local Shiny app with modular Home, Zotero/domain configuration, and nine pipeline pages. All implementation is in new files. Nothing imports dashboard code from neurosymbolic or changes existing pipeline source.

## Start

From the repository root in PowerShell:

```powershell
.\start-dashboard.ps1
```

Open http://127.0.0.1:8056. The launcher creates a separate environment under `outputs/dashboard/.venv` when needed. To install explicitly or update its dependencies:

```powershell
uv --cache-dir outputs/dashboard/uv-cache venv --python .venv/Scripts/python.exe outputs/dashboard/.venv
uv --cache-dir outputs/dashboard/uv-cache pip install --python outputs/dashboard/.venv/Scripts/python.exe -r dpv_dashboard/requirements.txt
outputs/dashboard/.venv/Scripts/python.exe -m dpv_dashboard
```

## Finding your way around

Select **Documentation**, immediately left of the institutional caption in the header, to open
the searchable documentation library. It includes the dashboard guide, architecture, stage contracts,
agent instructions, code references, and ontology/validation guides. **Information journey & WebVOWL**
opens the interactive codebase ontology when its export is available. Every guide, code reference,
and interactive view has a matching **Dashboard** return button.

The launcher refreshes the written guides at startup and serves them at
`/documentation/library.html` on the dashboard's own port (8056 by default). A separate documentation
server is not required. The standalone 8058 reviewer remains usable and returns to dashboard8056.
For a dashboard left running during this update, the header uses the existing 8058 documentation
viewer until the next normal dashboard launch. This avoids restarting a supervised pipeline worker.
To refresh written documentation without restarting a running dashboard:

```powershell
outputs/dashboard/.venv/Scripts/python.exe scripts/documentation_library.py
```

This command copies only documentation artifacts and inventoried first-party source snapshots into
the generated bundle; it never serves the repository root, private environment settings, or run configs.
It refreshes the guides/source pages, not the ontology graph. To regenerate the ontology and interactive
projections after code changes, follow [the codebase regeneration guide](../docs/codebase/README.md).

The top action row places Run workflow, Resume and Cancel on the left,
**EXISTING OUTPUTS · READ-ONLY MONITOR** in the middle, and the latest integration on the right.
Choose a saved run/integration to explore it; choose Dashboard project to enable
project execution. Monitoring does not adopt or cancel an externally launched pipeline process.

Each stage starts with its research purpose, saved-result summary and primary controls. Extraction
opens on claims/evidence; integration opens on bridge concepts. Choose **Explore** to switch views,
select a row for its record inspector, and use the action above the table to open its full evidence trace.
**What needs attention** exposes review priorities. **Run controls**, baseline comparisons and
**Files & technical details** retain execution, raw previews and downloads without dominating the page.
Zotero configuration is exposed directly on the first stage.

**Reports & figures** shows a scrollable figure/download library above the main report. Report preview
headings, tables and spacing use dashboard styling, and local image paths resolve against the saved
report's directory. Saved HTML, Markdown and figure files are never reformatted on disk.

**Evidence & provenance** traces canonical concepts to original terms, claims, papers and figures.
Recorded lineage and reconstructed/ambiguous older-run links remain distinct. **All artifacts** is the
complete file inventory, including partial, missing, unreadable and superseded outputs.

**Visual Exploration** offers Search, WebVOWL and Chat. Search remains prominent; graph-only settings
hide on other tabs. Chat starts with the question box and uses the workflow model by default; expand
Answer style & model to choose saved-evidence mode or a configured AI model. Inline [S1] citations open
the exact cited claim when available. Unknown citations do not resolve to invented sources. DOI and
web links are separate from local evidence actions. No model is called merely to display saved results.

Figures open crop-first, with **Expand full paper at source page** for context. Crops may be saved,
recorded or estimated; missing geometry/PDFs remain explicit. The dashboard cannot infer an internal
scientific focus region that the extraction did not record. Quote-match status concerns source text,
not measurement correctness, causal direction or expert approval.

## Running a project

1. Upload your existing `.env` on Home. It is saved at `outputs/dashboard/private/.env`, outside version control. Setting names and connection statuses are shown; values are not returned to the interface. Reauthentication replaces this local file. No keys are included in the source. Local Ollama needs no model API key.
2. Create a project. On Zotero ingestion, discover the personal/group libraries permitted by the key, load collections from several libraries, and select the collections to assign to a named domain.
3. Set a paper limit for the whole domain. Every descendant collection is included. DOI duplicates and repeated memberships are consolidated, preserving alternate PDF sources. Citation counts come from the existing provider code. Papers with missing counts rank last; unavailable PDFs are skipped until the limit is reached or the domain is exhausted.
4. Add other domains to the same project. Run workflow processes domains and their stages in order, then integrates them (when at least two exist) and generates reports. The same project-wide model profile and worker setting apply to every domain.
5. Alternatively, Run stage advances the selected domain one stage. Resume skips stages recorded as completed and retries unfinished stages. It uses existing extraction caches where available; partial paper extraction is flagged as failed, rather than advancing silently.
6. Restart stage creates an immutable new attempt at that stage, copies upstream artifacts and their compute provenance, and excludes downstream results. Model caches for that restarted stage are fresh. Previous attempts remain selectable. Ingestion/PDF caches and the frozen upstream selection remain reusable as applicable. Integration and report attempts are also retained separately.
7. Cancel terminates only the dashboard-launched process tree. Saved products remain. Interrupted stages may repeat unfinished work on resume. Restarting an upstream stage marks the project's previous integration/report outdated until regenerated.

The project selector identifies the research workspace; the domain selector identifies an ontology; the attempt selector switches between current and historical products. Execution controls act on the latest attempt. Saved files are previewed as tables, reports, figures or WebVOWL, and can be downloaded. Raw previews are bounded; table previews show up to 10,000 rows. Full downloads preserve the complete artifact.

## Research views

The stage pages now include readable research tables alongside the original file previews:

- Extraction lists papers and their relations, causal claims, reported values and quote-verification states.
- Normalization shows canonical concepts, original-to-canonical lineage and contradictions, retaining the supporting papers and conditions.
- Ontology placement shows parent choices, placement sources, fallback/review flags, parent evidence and root-to-class hierarchy paths.
- Enrichment separates definition status/source, restrictions, external candidates and Materials Project records. Review findings retain recorded rejection and downgrade reasons.
- Interoperability compares local and external labels/definitions alongside mapping type, confidence, scores and source ontology.
- Integration shows domain mappings, bridge members, candidate decisions and unreviewed pairs. Selecting a member can open its recorded source run.

Integration also presents the contributing domains' papers, figures/captions, claims, canonical vocabulary, lineage, placement rationale, definitions, restrictions, external mappings, contradictions and review findings. Use **Contributing source** to filter these tables. Source run and domain identifiers remain attached to each row; missing runs are listed in coverage. Selecting a cross-domain mapping compares both source records, and selecting a bridge compares its recorded members. Ambiguous source identities remain unresolved.

Underlined concept and paper labels have hover cards showing supporting papers, quote/lineage status and a lazily rendered first-page thumbnail. Click a reference to open the paper/figure inspector. Figure links open saved images or bounded PDF crops with captions. Estimated boundaries are labeled; unavailable crops stay explicit. Expand full paper opens the original page when desired. **Source figures & captions** provides a combined integration figure browser. A row's figure links preserve paper scope; a figure in a supporting paper is not itself evidence for a concept unless that link was saved. Media is read from the run or pipeline PDF cache, served through opaque registered URLs, and rendered only in bounded dashboard memory. No figure extraction writes to pipeline outputs. Missing PDFs/images/pages are identified explicitly.

Select a result row and choose **Inspect selected row → evidence & provenance**. The dedicated **Evidence & provenance** page follows the selected class/canonical concept back to paper-local concept IDs, paper metadata, quotes, figures and related contradictions. IDs are scoped to their source papers; `c1` in one paper is never assumed to be `c1` in another. Clicking an available local class in WebVOWL opens the same inspector. Property/external nodes without a recorded local class show a notice rather than a fabricated trace.

`normalized/concept_lineage.json`, when present and readable, is authoritative. Missing rows, malformed/conflicting identities and changed labels are identified, not silently replaced. Older runs without that file may show **reconstructed (unique label + paper)** links from saved canonical labels/alternative labels and paper membership. Ambiguous matches remain unresolved, and reconstructed matches are never described as recorded merge decisions. The separate pipeline-lineage worktree is not applied by these views.

**All artifacts** inventories every regular file within the selected run/report folder, including unknown filenames and audit logs. It shows stage/purpose, size, timestamp, availability and completion evidence. It also lists missing expected products, selected papers without saved extraction, and lineage/parsing windows that older pipeline versions do not record. Superseded status is based on recorded attempt history or a newer recorded upstream completion, not simply an older modification time. Paths escaping the selected directory and credential/private-key files cannot be previewed or downloaded. Large JSON files over 64 MB are marked as not inspected rather than declared readable.

Progress and top-of-page paragraphs summarize saved outputs, dominant types/labels, definition statuses, mapping ontologies, fallback counts and review priorities. Recorded completion remains distinct from recent log activity. The dashboard does not claim that its structural or quote-match checks establish scientific correctness.

Research joins and file inspections are cached by path, size and modification time, in dashboard memory. They do not write to source run folders, call a model, backfill lineage, or update ontology stores. Verification can run as a separate instance using `python -m dpv_dashboard --port 8057`, leaving the normal 8056 server and its jobs alone.

## Focused paper and figure viewing

Concept references carry their canonical identity and source paper into the viewer. The dashboard matches saved original terms, alternative labels and linked evidence quotes against PDF text. Hover thumbnails and the opened PDF use the same focus; the opened view starts at an evidence-match page when available. Blue rectangles mark text matches; a text match does not establish scientific support. Unmatched terms are explicitly reported, without invented coordinates.

Figure references use their recorded page and caption. Recorded PDF-point bounding boxes are honored where available; otherwise the dashboard searches the caption and estimates a nearby image region or connected vector plot panels. Estimated boundaries and caption-only fallbacks are labeled. The inspector displays the saved image or cropped region with its caption first. Expand full paper reveals the source-page PDF and its focus boxes; a caption-only match is never presented as a figure crop. The original PDF remains separately available.

Matching and PDF annotation run in bounded dashboard memory, with no writes to the original PDF or run directories. Focus previews are limited to 64 MB PDFs, 1,000 pages and 300 text boxes; scanned/non-searchable text may remain unlocated. Figure boundaries are geometric estimates and can include surrounding chart content.

## Visual Exploration

**Visual Exploration** appears beneath Reports. It independently follows Neurosymbolic's workspace format: a source/ontology sidebar, WebVOWL graph, search/results and chat. Stage Turtle previews now link here and preserve their selected source/file. Search covers the selected ontology plus saved concepts, definitions, papers and claims in its run or recorded integration inputs. Select a result to read its source detail, focus its graph neighborhood or open paper evidence. Graph nodes retain provenance navigation.

Chat defaults to finding supporting evidence without model calls. For **AI answer with citations**, **Chat model** automatically selects **Same as workflow**, using the selected run's recorded interoperability/integration model and routed provider. Other configured models appear in the dropdown, including stage-specific models and credential-backed provider profiles. A project without saved results uses its selected model profile. Model profile definitions are read as data from the pipeline configuration without importing it, changing environment variables or modifying files.

Existing saved credentials are reused; a separate chat endpoint or typed model name is unnecessary. Previously saved custom chat connections remain available as an optional dropdown entry. Model details are expandable, and missing sign-ins point to Home using plain language. Both OpenAI-compatible and Anthropic providers are supported. Requests occur only on an explicit Send with AI answers selected; verification uses mocked transports rather than a live provider.

Table headings, progress labels, review codes and run selectors use readable wording through a display-only presentation layer. Table selection restores original column keys before provenance or artifact navigation. Scientific labels and exact IDs remain intact, while original field names and recorded codes remain available in saved artifact previews/downloads.

## Search evidence actions and quality review

Visual Exploration search results provide **View evidence**, **View provenance** and **Open paper** actions directly in the table. Actions retain the contributing source run and resolve ontology-only hits to a unique available source concept by IRI. Missing or ambiguous links are stated explicitly. Evidence opens the paper/evidence tab; provenance opens original-to-canonical lineage, retaining recorded/reconstructed status.

Search and chat withhold malformed concepts, their dependent claims and copied RDF terms. Checks cover invalid labels, labels over 240 characters or 32 words, repeated four-word sequences, malformed aliases, explicit quality flags and already-excluded source concepts. Other scientific review flags remain visible as caveats rather than automatically classifying valid concepts as malformed. **Quality review** lists withheld records with bounded previews, original label lengths and reasons; full originals remain in All artifacts. Counts include separate saved representations and dependent records, not just unique concepts.

Both chat response paths validate inputs again and bound displayed/source-packet labels. If no clean evidence remains, chat explains that without calling a provider. Existing output files and caches are never rewritten by dashboard filtering.

The extraction safeguard is prepared separately in the attached `extraction-quality` worktree and saved as `outputs/development/extraction-quality/extraction-quality.patch`. It is **not applied to the active pipeline checkout**. Once applied, it quarantines malformed concepts before later extraction passes/merging, checks cached extraction and existing-paper normalization boundaries, and preserves rejected concepts/links in `quality_review` and `extraction_review/*.json`. It keeps raw model responses and does not rewrite legacy caches or paper files during normalization. The extraction version changes for future cache identity. This patch is separate from the earlier concept-lineage worktree; combining them requires reviewing their shared `src/run.py` edits.

## Output discovery

The **Existing outputs · read-only monitor** selector discovers domain runs, integration outputs and sweep reports directly under the repository's `outputs/` directory. It initially selects the most recently updated discovered output. Stage pages show its existing artifacts and the execution log follows its saved log file. The dashboard never writes to these folders or takes control of their processes. Recent log activity is labeled as observed activity; it is not proof that a process is still running. Older runs do not save separate parsing windows, so parsing shows their paper records and parsing statistics instead.

Choose **Dashboard project (enable execution controls)** in that selector to return to dashboard-managed projects. Run, resume, restart and cancel are blocked for externally monitored outputs.

## Wrapper boundary (implementation)

`worker.py` starts in a separate interpreter. Before loading the existing pipeline agents, it sets process-local output/cache constants. The existing ontology store remains at its original location and is read by the existing store's read-only SQLite connection. Build that store through the existing workflow before ontology placement.

Ingestion and parsing are dashboard-owned preparation steps. They save `ingestion.json` and `parsed/*.json`, including windows produced by the existing extraction chunker. Extraction receives those saved inputs through process-local function adapters. Normalization, placement, enrichment, interoperability, integration, and figures call the existing processing functions. No existing Python files, collection settings, requirements, or `.env` files are rewritten.

App data and caches live under `outputs/dashboard/`. The dashboard allows one supervised job at a time. Keep its server running while jobs execute; cancellation attaches to jobs launched by that server process. This first version is local-only, bound to loopback, and is not a multiuser Connect deployment. Closing a browser tab does not cancel a job.

Status derives from persisted stage records, with logs available throughout execution. No estimated percentage is invented for model calls. The opening paragraphs summarize saved outputs deterministically; they do not issue extra model requests. Successful structural checks do not establish scientific or semantic correctness.

## Modular pages

- `app.py`: navigation, project/domain/attempt context, execution controls.
- `pages/home.py`: Home and authentication onboarding.
- `pages/browse.py`: asynchronous Zotero browsing and domain assignment.
- `pages/stage.py`: independently namespaced Shiny stage module, instantiated for each of the nine stages.
- `model.py`, `jobs.py`, `worker.py`: persistence, supervision, and the separate pipeline adapter.
- `inspect.py`, `viewer.py`: artifact summaries/tables and RDF projection for WebVOWL.
- `catalog.py`, `research.py`: complete read-only inventory, scoped joins and cached research views.
- `pages/research.py`, `pages/inventory.py`: evidence/provenance navigation and the file inventory.

The page modules accept a shared context instead of importing a parent app. A future host can register them with unique module IDs and provide the same context interface. Neurosymbolic remains only a structural reference.

## Validation

For the codebase/module map and wrapper boundaries, see [architecture](../docs/architecture.md).
Stage contracts remain in [pipeline stage documentation](../docs/stages/1-extract.md).

## Troubleshooting

- **Port already in use:** open the existing 8056 dashboard. To start an independent instance, use
  `.\start-dashboard.ps1 -Port 8057`; the launcher never stops another listener automatically.
- **Old layout or click behavior:** refresh the page after updating/restarting the dashboard. CSS and
  navigation JavaScript URLs are versioned. Restart only the intended server when it owns no active job.
- **No current run:** select it in the top existing-output selector; choose integration for combined
  source-domain views. Check that its manifest/files are under this checkout's outputs directory.
- **Missing figure/evidence:** inspect coverage and source artifacts. A crop requires a saved image or
  locatable region in an accessible PDF; ambiguous lineage is not evidence of a recorded merge.
- **Chat unavailable:** verify saved model settings through Home reauthentication. Chat inherits the
  selected workflow connection; expand its model settings to choose another configured option.
- **Dependency installation:** the launcher installs dashboard dependencies only when creating its
  separate environment. Use the explicit installation command above to update an existing environment,
  with no dashboard-owned job running. This does not upgrade the pipeline environment.

## Verification command

```powershell
outputs/dashboard/.venv/Scripts/python.exe -m pytest dpv_dashboard/tests -q --basetemp outputs/dashboard/test-tmp
```

Tests use offline fixtures; they do not launch a literature/model run. Browser verification covers navigation, project creation, artifact downloads and the actual selected WebVOWL graph. A real Zotero/model pipeline run must still be verified with the user's selected project and saved authentication.

See `THIRD_PARTY.md` for the upstream WebVOWL build and official branding asset sources.

## Scientific graph and literature provenance

Visual Exploration defaults to scientific relationships, restrictions, mappings, and the literature-claims layer. Hierarchy and disjointness are optional controls. Integration views assemble the selected graph and recorded source-domain ontology and claims files in memory; saved Turtle files are not rewritten. Missing sources are listed in graph coverage.

Selecting a relationship opens its source files and, when recorded, supporting quotes, verification status, conditions, and source-paper links. Literature concepts align with formal classes only through recorded ontologyClass links. Ontology restrictions without paper-level evidence are explicitly identified. Quote matching does not establish scientific correctness.

## Dashboard record presentation update

Research tables now have compact defaults and an optional technical-columns control. Selection restores the complete raw row by index, including hidden run and concept identifiers, so sorting and filtering do not change join scope. A shared record inspector shows meaning, quotes, provenance, source-paper access, normalization links, review notes and expandable original metadata. Artifact relationships resolve names within the original paper; the saved identifiers remain unchanged.

Read-only monitoring visibly disables execution controls and hides unrelated project selectors. Home shows current-workspace guidance; service and provider labels are readable. Stage summaries show quote-review proportions, definition-status denominators, and the distinction between integration decisions and inherited source records. Review actions select the appropriate findings/evidence view. Technical findings are grouped with affected-concept counts; severity is not invented.

Long figure lists open a bounded caption-searchable gallery. Previews identify saved figure images versus full source pages. Reports and saved plots have a gallery with scoped previews and downloads. Raw files and complete inventories remain available; table and gallery limits are stated. Graph source colors and supplied/rendered counts make domain provenance and WebVOWL collapsing visible; graph controls are hidden in chat.

Implementation: presentation.py (display/identity), record_view.py (shared inspector/review counts), media.py (scoped names and galleries), pages/research.py (selection/navigation), pages/stage.py (review and reports), app.py/www (view context), viewer.py (domain colors), and pages/home.py/pages/browse.py/pages/exploration.py (contextual presentation). Pipeline source and existing outputs are not rewritten.

Each stage also offers an explicitly selected saved-run baseline for count and literal-label comparisons. It never treats a label match as semantic equivalence.

The top progress steps open their corresponding stage details and support keyboard activation. Concept growth previews explain citation-order lines and the shaded 5th–95th percentile over random paper orders; embedded HTML reports receive the same dashboard-only explanation. Original report and figure downloads are preserved.
