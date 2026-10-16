# Dashboard usability layout — 2026-10-16

Approved presentation-only pass; no pipeline, source-result, dependency or store changes.

- `pages/stage.py`: purpose statements for all nine stages; Zotero setup exposed directly; separate collapsible run controls; primary research results first; review priorities expanded; comparison and artifact/raw detail collapsed. Reports show their readable preview first and locate nested report.html/report.md files by default.
- `pages/research.py`: evidence tracing guidance, primary inspect action before tables, technical display options collapsed; extraction defaults to claims and integration to bridge concepts.
- `pages/exploration.py`: explains Search/Graph/Chat value; search above graph configuration; chat question and Send above history, model settings collapsed; graph-specific controls grouped.
- `www/dashboard.js`: graph configuration visible only on WebVOWL, refreshed when switching tabs.
- `pages/inventory.py`: purpose and workflow guidance; preview/download controls above the inventory.
- `pages/home.py`: explains exploring saved findings versus setup; onboarding remains available in an expanded, collapsible setup section.

Verification: 69 existing dashboard regression tests passed. Browser checked n15 integration defaults, top-level action placement, collapsed technical detail, chat question/settings layout, graph controls hidden on Chat, and Reports iframe visible without opening artifact selectors. Final nested-report selection adjustment was verified in the browser. This is a layout review, not a researcher usability study or exhaustive walkthrough of every record.

Only enhanced dashboard8056 restarted to load changes; active pipeline processes and original8055 were not stopped. Incremental diff against pre-change snapshots: `outputs/development/usability-20261016/usability.patch`.
