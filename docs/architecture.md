# Codebase architecture and maintenance guide

## Entry points and ownership

| Entry | Responsibility |
|---|---|
| `python -m src.run` | Pipeline CLI, fixed stage order, run/resume orchestration and checks |
| `python -m src.figures` | Reports, plots and saved figure tables |
| `start-dashboard.ps1` / `python -m dpv_dashboard` | Local wrapper server, default loopback port 8056 |
| `python -m dpv_dashboard.worker` | Dashboard-owned supervised pipeline work; launched by jobs.py |
| `scripts/run-sweep.ps1`, `auto-sweep.ps1`, `slurm-sweep.sh` | Cumulative sweeps, unattended continuation and cluster execution |

The CLI pipeline and dashboard are separate entry points. The dashboard can monitor existing CLI outputs
without modifying them, or create its own project runs. Closing a browser tab does not cancel a worker.
Restarting the server can lose its in-memory process ownership; keep it running while dashboard jobs execute.
Never restart or modify active pipeline code, dependencies, caches or stores as part of a presentation change.

## Pipeline implementation

`src/config.py` defines model profiles, providers, ontology sources, collection settings and revision policy.
Credentials belong in local environment files, never in code or documentation examples.
`src/agents/base.py` supplies agent infrastructure; extraction, normalization, ontology, enrichment,
interoperability and integration agents implement their respective stages.
`src/resources/prompts/` and `schemas/` are the model-facing contracts. Treat changes as behavior changes:
inspect coverage, caching/revision implications and downstream artifact consumers before editing.

Tool modules are grouped by responsibility:

| Area | Modules under src/tools |
|---|---|
| Sources and text | zotero, citations, pdf_parse, files |
| Model execution | llm, workers, gemini_quota, ledger, progress |
| Vocabulary and placement | lexical, retrieval, upper, bottomup, ontostore, ontology_review |
| External knowledge | mds_portal, mds_onto_open_api, matportal, materials_project |
| Export and synthesis | owl, integration, reports |
| Optional model training/evaluation | lora_data, lora_eval; training instructions under src/resources/lora |

See the root README and `docs/stages/1-extract.md` through `7-reporting.md` for stage contracts and validation
limits, and `docs/ontology-store.md` for store preparation. The dashboard presents ingestion and parsing
separately, resulting in nine UI stages; these are not nine independent CLI agents.

## Dashboard implementation

| Modules | Responsibility |
|---|---|
| app, __main__ | App composition, shared context, navigation, loopback serving and default port |
| pages/home, browse | Local onboarding, Zotero libraries/collections and domain configuration |
| pages/stage, research, inventory, exploration | Stage results, evidence, file coverage, graph/search/chat |
| model, jobs, worker, zotero | Project/attempt state, process ownership, stage execution and library access |
| auth, chat_settings | Local credentials and workflow/chat model selection; redact displayed diagnostics |
| external, catalog | Read-only discovery, file classification, availability and access guards |
| research, integration | Scoped joins and federated domain evidence; recorded versus reconstructed lineage |
| inspect, presentation, record_view | Saved-result summaries, readable tables, record detail and report presentation |
| exploration, quality | Search/chat retrieval and malformed-record filtering; not scientific adjudication |
| media, highlight | Registered local media, disposable PDF annotations and crop-first previews |
| viewer, visual_graph | WebVOWL conversion, selected graph layers and edge provenance |
| www/dashboard.*, vowl-bridge.js | Layout, navigation, media actions and same-origin graph communication |
| www/webvowl | Vendored third-party viewer; licensing in THIRD_PARTY.md |
| tests, reviews | Offline fixtures and dated evidence-backed change/audit notes |

Page modules consume the context supplied by app.py; preserve module IDs when moving UI controls.
Keep reference identity scoped by source run, paper, original/canonical concept and claim/figure ID.
IDs such as c1 and F1 repeat across papers. Ambiguous links must not become invented unique provenance.

## Storage and data flow

CLI outputs live in `outputs/<run-id>/` and integrations in their own folders. Shared caches/store live under
`outputs/cache/`. Dashboard environment, private settings, projects, attempts and caches are under
`outputs/dashboard/`; inspect model.py for the current on-disk layout before writing a migration.
The dashboard worker configures process-local output/cache locations before importing existing agents;
it does not rewrite the pipeline's configuration source. It reads the existing prepared ontology store.

Typical artifact flow:

`Zotero/PDF cache → paper records → normalized vocabulary/claims → ontology placement → enrichment → formal ontology + literature layer → cross-domain master/union → reports/figures`.

Formal ontology and literature claims are distinct layers. Integration imports/unions the selected formal
domain graphs; the dashboard additionally loads recorded domain literature layers for provenance views.
Counts can differ because some canonical concepts are excluded from formal classes. Source-domain rows
remain separate rather than silently deduplicated across domains.

## Safe extension and verification

For presentation work, change dashboard renderers/styles rather than saved outputs or pipeline agents.
Register media only after catalog/path validation; do not expose unrestricted client-supplied filesystem paths.
Report styling and image URL resolution affect previews only. Estimated figure crops are not recorded
scientific regions; caption-only and unavailable cases need explicit fallback. Chat uses bounded saved
records and validated response citations; a matched quote does not prove the assertion is correct.

Use the dashboard test command in its README. The suite uses offline fixtures, including scoped joins,
source integrity, malformed data, graph layers, crop rotation and supervised child-process behavior.
Then check representative saved domain and integration runs in the browser. Keep the distinction between
fixture checks, browser checks, live model/pipeline verification and researcher usability testing explicit.
Historical reviews are evidence of past checks, not a guarantee about every future run.

For pipeline changes, follow the relevant stage docs, inspect actual artifacts/logs, use isolated runs and
review downstream schema/provenance effects. Never claim structural validation establishes scientific validity.
