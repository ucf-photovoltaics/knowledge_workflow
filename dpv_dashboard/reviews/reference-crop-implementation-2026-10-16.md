# Reference and crop implementation — 2026-10-16

Implemented the dashboard portion of the approved n15 audit plan. Pipeline code, source PDFs and saved run artifacts were not edited. Only the enhanced dashboard on8056 was restarted;8055 and pipeline processes were not stopped.

## Changes by file

- `media.py`: shared direct evidence actions; exact claim tokens scoped to run/paper; safe inline chat source-marker rendering; explicit concept, paper, figure, DOI, web IRI and contributing-run references; Markdown report reference rendering; PDF crop endpoint/cache with bounded resolution and rotated coordinates; saved-image/recorded-bound/estimated-bound precedence; explicit unavailable fallback; collapsed full-paper viewer; cache-origin and assertion-verification explanations.
- `pages/exploration.py`: clickable answer citations and direct cited-evidence controls; link-aware selected search text/IRIs and graph source citations.
- `www/dashboard.js`, `app.py`: forward claim identity into the paper inspector; version navigation assets to prevent old cached JavaScript losing claim context.
- `record_view.py`, `pages/research.py`: actionable technical identifiers, parents, restrictions and external mappings; cached-extraction notice.
- `pages/stage.py`: apply the shared reference renderer to CSV artifacts and Markdown reports as well as existing JSON/Turtle views.
- `external.py`: integration's inherited upstream stages say “see contributing domains” instead of appearing to be unexecuted waiting stages.
- `tests/test_reference_crops.py`: new scoped citation, escaped text, safe URL, precise claim, crop dimension/fallback, source-integrity, rotation/multipanel, report and progress regressions.

## Verification

69 dashboard tests passed in the existing dashboard environment. The initial sandbox attempt could not allocate default temporary fixtures; a workspace-local temporary directory resolved that. The existing process-cancellation fixture required execution outside the sandbox to stop its own test process. No dependency installation or changes were needed.

Browser checked completed integration-n15-20261015-150628: inline[S2] opened causal claim3 from si-topcon paper ZPYMKLE2 with its quote and verification explanation. Expanded the five-figure gallery; Figures1–4 had estimated crop previews, Figure5 had an explicit unavailable fallback. Figure1 opened crop-first with full paper collapsed, then expanded at source page2. The screenshot was visually checked for crop presentation. Integration stage navigation and clickable source-figure records were also checked. Evidence mode was used; no live model request was sent. Both answer modes use the same citation renderer; arbitrary future model citation syntax is not exhaustively tested. Fixture coverage includes unknown[S99].

The locator's407 estimated regions across480 n15 figures remain estimates, not407 scientifically/visually adjudicated crops. Missing or ambiguous records do not acquire invented provenance. Bare figure numbers without a paper context are not guessed. Raw source downloads and historical report content remain available. HTML report attachments retain their existing sandbox; link enhancement applies to Markdown reports and structured artifact views, not executable content inside sandboxed HTML attachments.

The dashboard directory was already untracked before this work. `outputs/development/n15-audit-2026-10-16/dashboard-reference-files.patch` is therefore a full-file Git addition snapshot of the nine touched/new implementation files, rather than a precise incremental diff against the pre-turn dashboard. The file-specific change list above records this iteration's scope.

Pipeline quality repairs identified in `n15-reference-and-data-audit-2026-10-16.md` remain separate future-run changes. This implementation does not rewrite or repair the n15 scientific records.
