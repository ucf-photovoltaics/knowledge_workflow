# Source module and callable reference

Author: Brent Thompson <brent.thompson@ucf.edu>

Generated statically; call expressions are syntactic observations, not a complete resolved call graph. All file links point to first-party code. Third-party code and runtime outputs are excluded.

## docs/ontology/artifact-flow.rq

Summary: Follow shared output specifications from producing to consuming pipeline steps.

[Source](../../docs/ontology/artifact-flow.rq) · SHA256 `7711160bfc55aa0f7e9341d0b2ecbd58cd0d8d871b873f85c67bd39b6fae6478`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/information-flow.rq

Summary: Discover information transformations, their data states and source implementations.

[Source](../../docs/ontology/information-flow.rq) · SHA256 `49d3729a08ec90211c1a167b4f12d346534627be9edc33afd2c2e6230b6bbed4`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/next-step.rq

Summary: Retrieve invocation templates and prerequisite specifications for an explicit step.

[Source](../../docs/ontology/next-step.rq) · SHA256 `c690cb12e1d58f281acc04794e5ee7a42a3e17209e5cfb2126cc0d62e7b47ae5`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/step-functions.rq

Summary: Navigate every operational step to its source callable and expected products.

[Source](../../docs/ontology/step-functions.rq) · SHA256 `ab8ff02b563f563cf7635601e13ff42bffba2e78a0b61530e4925bd9a59cd39d`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/viewer/frame.css

Summary: Hide duplicate upstream details in the generated preview; retain graph controls.

[Source](../../docs/ontology/viewer/frame.css) · SHA256 `1aead3882ea96759ad0e1b6113ca247f4ed71632c190431bf47307fd147ba470`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/viewer/index.html

Summary: Focused, read-only reviewer navigation of the operational codebase ontology.

[Source](../../docs/ontology/viewer/index.html) · SHA256 `c3a66e2a7cb2bee06b5ea4bde11046b78a5aca34c0e56381d47e4da02c26b374`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/viewer/journey.css

Summary: Stable reading-order information flow, explicit handoffs and evidence-bearing concept traces.

[Source](../../docs/ontology/viewer/journey.css) · SHA256 `5cddf625c187a09b02f3d0d4b35a4aa23b2b661dfc53ea9402dfda2bf1bd2732`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/viewer/journey.js

Summary: Present the information journey and a saved concept's evidence-bearing transformations.

[Source](../../docs/ontology/viewer/journey.js) · SHA256 `0d6cef8774543249b315eea67dfbf6d40053bf368de1e4a47409ee3206409162`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/viewer/reviewer-bridge.js

Summary: Connect the standalone reviewer to WebVOWL with coalesced graph framing.

[Source](../../docs/ontology/viewer/reviewer-bridge.js) · SHA256 `eb3a635308050f4d34da64b9c8fd1840580521be5699165621981e6aa8afcb29`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/viewer/reviewer.css

Summary: Accessible reviewer layout for focused WebVOWL stage and source navigation.

[Source](../../docs/ontology/viewer/reviewer.css) · SHA256 `28e932357addd2e6ea14ede3c23066c52e5ce68fe932a8ef8a54955a827f6ac9`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/viewer/reviewer.js

Summary: Read-only stage, definition, contract and source navigation over exported RDF records.

[Source](../../docs/ontology/viewer/reviewer.js) · SHA256 `9c3256e35860db6f17a52f3b39ebbf8afa3e7f31f609972abe10f46726aa0d1e`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/viewer/site-nav.css

Summary: Shared documentation navigation and readable guide/library layouts.

[Source](../../docs/ontology/viewer/site-nav.css) · SHA256 `f1a52394fbf64e4ff5cc6ac9a130b7da1a4ed8e0f7d326fbcf46087b4239b3b4`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## docs/ontology/viewer/site-nav.js

Summary: Return to the serving dashboard and filter the static documentation library.

[Source](../../docs/ontology/viewer/site-nav.js) · SHA256 `48c5d7c3d09f37021b75f355c17d4171850ac95704b8df3b41022a83be86b1a3`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## dpv_dashboard/__init__.py

Standalone UCF DPV dashboard; existing pipeline source is read-only.

[Source](../../dpv_dashboard/__init__.py) · SHA256 `b347355dc78af15f5ca302e72ca88e42f849ca6d0e480756b3a39aabdbb2287f`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## dpv_dashboard/__main__.py

Launch locally: python -m dpv_dashboard [--port 8056] [--viewer] [--host 0.0.0.0].

[Source](../../dpv_dashboard/__main__.py) · SHA256 `796bd9045ac27857594ff2e092b523b0b78c529cac1057d1e321428dda1376ff`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `main` | 13 | `` | Read the linked implementation and its call-site contract. |

Imports: `argparse`, `dpv_dashboard.model`, `os`, `subprocess`, `sys`, `tempfile`, `uvicorn`

## dpv_dashboard/app.py

UCF DPV Knowledge Workflow standalone Shiny application.

[Source](../../dpv_dashboard/app.py) · SHA256 `a7b57cc3d11dafcae970dbf9aa2103094b1a01831ef0413fde22d80da5225d12`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `server` | 54 | `input, output, session` | Read the linked implementation and its call-site contract. |
| `server.discover_outputs` | 60 | `` | Read the linked implementation and its call-site contract. |
| `server.monitored` | 76 | `` | Read the linked implementation and its call-site contract. |
| `server.latest_integration` | 80 | `` | Read the linked implementation and its call-site contract. |
| `server.stage_files` | 103 | `root, stage` | Read the linked implementation and its call-site contract. |
| `server.tick` | 108 | `` | Read the linked implementation and its call-site contract. |
| `server.refresh` | 113 | `` | Read the linked implementation and its call-site contract. |
| `server.poll_project` | 119 | `` | Read the linked implementation and its call-site contract. |
| `server.project` | 129 | `` | Read the linked implementation and its call-site contract. |
| `server.require_project` | 132 | `` | Read the linked implementation and its call-site contract. |
| `server.notice` | 140 | `message, error=False` | Read the linked implementation and its call-site contract. |
| `server.ensure_idle` | 143 | `` | Read the linked implementation and its call-site contract. |
| `server.select_project` | 147 | `identifier` | Read the linked implementation and its call-site contract. |
| `server.project_choices` | 155 | `` | Read the linked implementation and its call-site contract. |
| `server.domain_choices` | 163 | `` | Read the linked implementation and its call-site contract. |
| `server.domain` | 170 | `` | Read the linked implementation and its call-site contract. |
| `server.attempts` | 175 | `` | Read the linked implementation and its call-site contract. |
| `server.folder` | 189 | `stage` | Read the linked implementation and its call-site contract. |
| `server.launch` | 213 | `action, stage=None` | Read the linked implementation and its call-site contract. |
| `server.open_exploration` | 227 | `root, path=None` | Read the linked implementation and its call-site contract. |
| `server.roots` | 234 | `` | Read the linked implementation and its call-site contract. |
| `server.superseded` | 253 | `root` | Read the linked implementation and its call-site contract. |
| `server.inspect_source` | 263 | `root, canonical=None, paper=None, tab=None` | Read the linked implementation and its call-site contract. |
| `server.research_navigation` | 290 | `` | Read the linked implementation and its call-site contract. |
| `server.open_research_reference` | 305 | `` | Read the linked implementation and its call-site contract. |
| `server.graph_provenance` | 326 | `` | Read the linked implementation and its call-site contract. |
| `server.authentication` | 339 | `` | Read the linked implementation and its call-site contract. |
| `server.authenticate` | 347 | `` | Read the linked implementation and its call-site contract. |
| `server.pipeline_status` | 352 | `` | Read the linked implementation and its call-site contract. |
| `server.job_status` | 379 | `` | Read the linked implementation and its call-site contract. |
| `server.logs` | 388 | `` | Read the linked implementation and its call-site contract. |
| `server.view_context` | 397 | `` | Read the linked implementation and its call-site contract. |
| `server.monitor_notice` | 406 | `` | Read the linked implementation and its call-site contract. |
| `server.automatic` | 412 | `` | Read the linked implementation and its call-site contract. |
| `server.resume` | 417 | `` | Read the linked implementation and its call-site contract. |
| `server.cancel` | 422 | `` | Read the linked implementation and its call-site contract. |

Imports: `asyncio`, `datetime`, `dpv_dashboard`, `dpv_dashboard.auth`, `dpv_dashboard.jobs`, `dpv_dashboard.pages.browse`, `dpv_dashboard.pages.exploration`, `dpv_dashboard.pages.home`, `dpv_dashboard.pages.inventory`, `dpv_dashboard.pages.research`, `dpv_dashboard.pages.stage`, `json`, `pathlib`, `shiny`, `types`, `uuid`

## dpv_dashboard/auth.py

Local credentials are saved outside source control and never returned to the browser.

[Source](../../dpv_dashboard/auth.py) · SHA256 `4221cfc756cbea2c7b26c9aabbddea71bd6359d47a8b8aaad7ff1e7ca1f39b77`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `credentials` | 16 | `` | Read the linked implementation and its call-site contract. |
| `save_env` | 20 | `source: Path` | Read the linked implementation and its call-site contract. |
| `redact` | 37 | `text` | Read the linked implementation and its call-site contract. |

Imports: `__future__`, `dotenv`, `dpv_dashboard.model`, `os`, `pathlib`, `re`

## dpv_dashboard/catalog.py

Read-only artifact inventory. Files being written are never treated as completed work.

[Source](../../dpv_dashboard/catalog.py) · SHA256 `01c3ae43ce42a0e4d2c7a184ec28d0182e3868c43fd7e5886138db5652f230bb`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `restricted` | 24 | `path` | Read the linked implementation and its call-site contract. |
| `fingerprint` | 29 | `path` | Read the linked implementation and its call-site contract. |
| `_json` | 38 | `path, stamp` | Read the linked implementation and its call-site contract. |
| `load` | 53 | `path, default=None` | Read the linked implementation and its call-site contract. |
| `classify` | 60 | `relative, kind='run'` | Read the linked implementation and its call-site contract. |
| `inventory` | 98 | `root, kind='run', superseded=False` | Read the linked implementation and its call-site contract. |
| `accessible` | 189 | `root, relative` | Read the linked implementation and its call-site contract. |

Imports: `__future__`, `datetime`, `dpv_dashboard`, `functools`, `json`, `pathlib`, `zoneinfo`

## dpv_dashboard/chat_settings.py

Read existing model profiles without importing or changing pipeline configuration.

[Source](../../dpv_dashboard/chat_settings.py) · SHA256 `0361a0b38599334487d6b4e7d294ea8d19ca56a9e15f6d9992bb7c5d089bebc0`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `profiles` | 17 | `settings` | Read the linked implementation and its call-site contract. |
| `profiles.resolve` | 19 | `node` | Read the linked implementation and its call-site contract. |
| `reachable` | 55 | `base_url` | Whether a model server answers; cached for 30 s so page renders stay fast. |
| `offline` | 71 | `option` | A local model server (e.g. Ollama) that is not running. |
| `model_label` | 77 | `name` | Read the linked implementation and its call-site contract. |
| `choices` | 87 | `root, project, settings` | Read the linked implementation and its call-site contract. |
| `choices.option` | 94 | `profile, name=None, base=None, provider=None` | Read the linked implementation and its call-site contract. |
| `connection` | 136 | `option, settings` | Read the linked implementation and its call-site contract. |

Imports: `ast`, `dpv_dashboard`, `os`, `time`, `urllib.error`, `urllib.parse`, `urllib.request`

## dpv_dashboard/exploration.py

Read-only search and evidence-grounded chat, independent of pipeline execution.

[Source](../../dpv_dashboard/exploration.py) · SHA256 `fdcac7117ac8391c7c8d10494f957ca354e2b570ea37874547201247a7d6ddfc`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `graph` | 15 | `path, stamp` | Read the linked implementation and its call-site contract. |
| `documents` | 21 | `root, ontology=None, excluded=None` | Read the linked implementation and its call-site contract. |
| `documents.add` | 25 | `row, reasons=()` | Read the linked implementation and its call-site contract. |
| `search` | 84 | `rows, query, limit=100` | Read the linked implementation and its call-site contract. |
| `neighborhood` | 104 | `rdf, iri, limit=160, show_disjoint=False, as_graph=False` | Read the linked implementation and its call-site contract. |
| `evidence_answer` | 137 | `question, hits` | Read the linked implementation and its call-site contract. |
| `safe_hits` | 145 | `hits` | Read the linked implementation and its call-site contract. |
| `resolve_source` | 149 | `row, roots` | Resolve ontology-only matches without guessing among repeated IRIs across runs. |
| `model_answer` | 173 | `question, hits, settings, model_name` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `functools`, `json`, `pathlib`, `rdflib`, `re`, `urllib.request`

## dpv_dashboard/external.py

Read-only discovery of existing pipeline outputs; never adopts process ownership.

[Source](../../dpv_dashboard/external.py) · SHA256 `bda2125e8cad48e3fd5a9f88db4c10d52f3774e6ca3052b8511c02cc2b158ae2`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `discover` | 12 | `root=None` | Runs in outputs/ plus any folders listed in DPV_OUTPUT_DIRS (e.g. a mounted Cloud Storage bucket). |
| `files` | 36 | `folder, stage, kind='run'` | Read the linked implementation and its call-site contract. |
| `log` | 53 | `folder` | Read the linked implementation and its call-site contract. |
| `states` | 71 | `folder, kind` | Read the linked implementation and its call-site contract. |
| `summary` | 100 | `folder, stage, kind` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `dpv_dashboard.inspect`, `os`, `pathlib`, `re`, `time`

## dpv_dashboard/highlight.py

Evidence/term text matches and conservative figure regions in disposable PDF copies.

[Source](../../dpv_dashboard/highlight.py) · SHA256 `b7a48ae50db50864e45e0704f4ee8fc2eba1375790b43aa322e580c478453e2d`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `focus` | 9 | `data, paper, canonical=None, figure=None` | Read the linked implementation and its call-site contract. |
| `locate` | 26 | `path, stamp, spec` | Read the linked implementation and its call-site contract. |
| `annotate` | 103 | `document, boxes` | Read the linked implementation and its call-site contract. |
| `pdf_copy` | 118 | `path, stamp, spec` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `functools`, `pymupdf`

## dpv_dashboard/inspect.py

Readable, evidence-derived summaries and artifact table views.

[Source](../../dpv_dashboard/inspect.py) · SHA256 `773760e0a99d6bdcdc32c85c7a42df0138d8b1d8799df07043b7d9d0d9ab99f7`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `rows` | 13 | `value` | Read the linked implementation and its call-site contract. |
| `table` | 21 | `value` | Read the linked implementation and its call-site contract. |
| `summary` | 27 | `folder, stage` | Read the linked implementation and its call-site contract. |

Imports: `__future__`, `collections`, `dpv_dashboard.model`, `json`, `pandas`

## dpv_dashboard/integration.py

Federated, source-scoped views; never merge paper-local or domain-local IDs.

[Source](../../dpv_dashboard/integration.py) · SHA256 `ee41d7583ede678e959b6b7046e5cbe8e44fe6b439cadcc091c69b1250be3c71`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `sources` | 14 | `root` | Read the linked implementation and its call-site contract. |
| `rows` | 28 | `root, view, domain=''` | Read the linked implementation and its call-site contract. |
| `member` | 50 | `root, iri, run=None, domain=None, indexed=None` | Read the linked implementation and its call-site contract. |
| `summary` | 64 | `root` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`

## dpv_dashboard/jobs.py

One local supervised process tree, with durable job history and cancellation.

[Source](../../dpv_dashboard/jobs.py) · SHA256 `09b925c3468658bf8d8481c0ceb5a0785eccb26e2af3d8a3a7f7f8b61ff0972c`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `Jobs.__init__` | 18 | `self` | Read the linked implementation and its call-site contract. |
| `Jobs.running` | 23 | `self` | Read the linked implementation and its call-site contract. |
| `Jobs.start` | 26 | `self, project, action, domain=None, stage=None` | Read the linked implementation and its call-site contract. |
| `Jobs._wait` | 51 | `self, process, job, handle` | Read the linked implementation and its call-site contract. |
| `Jobs.cancel` | 68 | `self, project_id` | Read the linked implementation and its call-site contract. |
| `Jobs.log` | 82 | `self, project` | Read the linked implementation and its call-site contract. |

Imports: `__future__`, `dpv_dashboard`, `dpv_dashboard.auth`, `os`, `signal`, `subprocess`, `sys`, `threading`, `uuid`

## dpv_dashboard/media.py

Explicitly registered local research media; no client-supplied filesystem paths.

[Source](../../dpv_dashboard/media.py) · SHA256 `d12f7f4a91109b14afb8314a86b9f24a2518545213324c0b5c293d0cad7aafd9`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `local_file` | 21 | `data, value, suffixes` | Read the linked implementation and its call-site contract. |
| `register` | 32 | `path, spec=None` | Read the linked implementation and its call-site contract. |
| `serve` | 42 | `request` | Read the linked implementation and its call-site contract. |
| `page_image` | 78 | `path, stamp, page, spec=None` | Read the linked implementation and its call-site contract. |
| `figure_image` | 97 | `path, stamp, spec` | Render only a located figure region; caption-only matches are never crops. |
| `figure_preview` | 118 | `data, key, figure, pdf` | Read the linked implementation and its call-site contract. |
| `paper_view` | 133 | `data, key, figure=None, canonical=None, gallery=False, claim=None` | Read the linked implementation and its call-site contract. |
| `reference` | 198 | `data, label, canonical=None, paper=None, figure=None, claim=None, direct=False` | Read the linked implementation and its call-site contract. |
| `external_reference` | 231 | `label, value` | Link only explicit web IRIs, keeping arbitrary paths and schemes inert. |
| `reference_text` | 245 | `data, value, paper=None` | Resolve explicit identifiers in narratives without guessing unscoped paper IDs. |
| `linked_markdown` | 287 | `data, text` | Link resolved references in rendered report text without nesting links. |
| `linked_markdown.References.__init__` | 292 | `self` | Read the linked implementation and its call-site contract. |
| `linked_markdown.References.handle_starttag` | 296 | `self, tag, attrs` | Read the linked implementation and its call-site contract. |
| `linked_markdown.References.handle_startendtag` | 301 | `self, tag, attrs` | Read the linked implementation and its call-site contract. |
| `linked_markdown.References.handle_endtag` | 304 | `self, tag` | Read the linked implementation and its call-site contract. |
| `linked_markdown.References.handle_data` | 309 | `self, value` | Read the linked implementation and its call-site contract. |
| `cited_reference` | 317 | `row, label` | Read the linked implementation and its call-site contract. |
| `chat_answer` | 326 | `answer, sources` | Keep model text escaped; only citations in this response's source list resolve. |
| `rich_table` | 343 | `data, values` | Render references as escaped Shiny tags, retaining raw IDs in separate columns. |

Imports: `collections`, `dpv_dashboard`, `dpv_dashboard.inspect`, `functools`, `hashlib`, `html`, `html.parser`, `pathlib`, `pymupdf`, `re`, `shiny`, `starlette.concurrency`, `starlette.responses`, `starlette.routing`, `urllib.parse`, `uuid`

## dpv_dashboard/model.py

Project persistence and immutable stage-attempt snapshots, without pipeline imports.

[Source](../../dpv_dashboard/model.py) · SHA256 `064384080fc4c29ae0c2b520d6ee624065fea1c1532778a8ecebda9d40d0d238`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `viewer` | 20 | `` | Viewer mode (DPV_VIEWER=1 or --viewer): saved results only; no projects, jobs or saved settings. |
| `require_editor` | 25 | `` | Read the linked implementation and its call-site contract. |
| `now` | 46 | `` | Read the linked implementation and its call-site contract. |
| `read` | 50 | `path: Path, default=None` | Read the linked implementation and its call-site contract. |
| `write` | 57 | `path: Path, value` | Read the linked implementation and its call-site contract. |
| `slug` | 72 | `name` | Read the linked implementation and its call-site contract. |
| `inside` | 79 | `root: Path, relative: str` | Read the linked implementation and its call-site contract. |
| `project_path` | 86 | `identifier` | Read the linked implementation and its call-site contract. |
| `projects` | 92 | `` | Read the linked implementation and its call-site contract. |
| `create_project` | 99 | `name` | Read the linked implementation and its call-site contract. |
| `load_project` | 108 | `identifier` | Read the linked implementation and its call-site contract. |
| `save_project` | 115 | `project` | Read the linked implementation and its call-site contract. |
| `add_domain` | 120 | `project, name, limit, collections` | Read the linked implementation and its call-site contract. |
| `run_dir` | 131 | `project, domain` | Read the linked implementation and its call-site contract. |
| `new_attempt` | 135 | `project, domain, stage` | Copy only upstream products. Previous attempts are never changed or deleted. |
| `stage_state` | 189 | `folder, stage, status, **extra` | Read the linked implementation and its call-site contract. |
| `artifact_files` | 195 | `folder, stage` | Read the linked implementation and its call-site contract. |

Imports: `__future__`, `datetime`, `json`, `os`, `pathlib`, `re`, `shutil`, `time`, `uuid`

## dpv_dashboard/pages/__init__.py

Pages are independent Shiny modules; the shell supplies shared project context.

[Source](../../dpv_dashboard/pages/__init__.py) · SHA256 `77dc36dddf565f12eb4eb6554c01752d2c3ccce2421415590d4d97f5ecadf383`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## dpv_dashboard/pages/browse.py

Asynchronous Zotero browsing and domain configuration module.

[Source](../../dpv_dashboard/pages/browse.py) · SHA256 `2f16f08b157db9469534cd18f3497609db94447072621a702dd8c2df026e45be`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `browse_ui` | 17 | `` | Read the linked implementation and its call-site contract. |
| `browse_server` | 38 | `input, output, session, context` | Read the linked implementation and its call-site contract. |
| `browse_server.submit` | 45 | `kind, function` | Read the linked implementation and its call-site contract. |
| `browse_server.api` | 51 | `` | Read the linked implementation and its call-site contract. |
| `browse_server.poll` | 55 | `` | Read the linked implementation and its call-site contract. |
| `browse_server.discover` | 86 | `` | Read the linked implementation and its call-site contract. |
| `browse_server.load` | 94 | `` | Read the linked implementation and its call-site contract. |
| `browse_server.preview` | 108 | `` | Read the linked implementation and its call-site contract. |
| `browse_server.add` | 129 | `` | Read the linked implementation and its call-site contract. |
| `browse_server.browse_status` | 143 | `` | Read the linked implementation and its call-site contract. |
| `browse_server.domains` | 147 | `` | Read the linked implementation and its call-site contract. |
| `browse_server.preview_table` | 155 | `` | Read the linked implementation and its call-site contract. |

Imports: `concurrent.futures`, `dpv_dashboard`, `dpv_dashboard.auth`, `dpv_dashboard.inspect`, `dpv_dashboard.zotero`, `pandas`, `shiny`

## dpv_dashboard/pages/exploration.py

Visual Exploration workspace: ontology graph, scoped search and grounded chat.

[Source](../../dpv_dashboard/pages/exploration.py) · SHA256 `e6292763d10082acab10cf984860f49b6a9ce2636493a09505a50092cc512367`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `exploration_ui` | 16 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server` | 50 | `input, output, session, context` | Read the linked implementation and its call-site contract. |
| `exploration_server.keys` | 62 | `` | Saved credentials plus a Gemini key entered for this browser session only (held in memory, never written). |
| `exploration_server.available_models` | 68 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.model_choices` | 73 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.model_info` | 82 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.choices` | 97 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.root` | 109 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.ontologies` | 113 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.path` | 141 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.poll` | 146 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.rdf` | 161 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.scope_reset` | 171 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.graph` | 187 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.graph_payload` | 194 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.graph_summary` | 203 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.edge_detail` | 219 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.search` | 252 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.results` | 265 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.actions` | 270 | `row` | Read the linked implementation and its call-site contract. |
| `exploration_server.coverage` | 288 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.excluded_results` | 292 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.selected` | 296 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.result_detail` | 305 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.use_result` | 316 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.inspect` | 326 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.history` | 336 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.send` | 345 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.model_chat` | 376 | `question, rows, settings, name, scope, revision` | Read the linked implementation and its call-site contract. |
| `exploration_server.receive_model` | 388 | `` | Read the linked implementation and its call-site contract. |
| `exploration_server.clear` | 403 | `` | Read the linked implementation and its call-site contract. |

Imports: `asyncio`, `collections`, `dpv_dashboard`, `dpv_dashboard.auth`, `dpv_dashboard.inspect`, `dpv_dashboard.viewer`, `pathlib`, `shiny`

## dpv_dashboard/pages/home.py

Landing page and local authentication onboarding.

[Source](../../dpv_dashboard/pages/home.py) · SHA256 `8b700bc9d1eb4c69d6ba31ff98e44d67e74eaa117b826cf4182694099a866230`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `home_ui` | 12 | `` | Read the linked implementation and its call-site contract. |
| `home_server` | 46 | `input, output, session, context` | Read the linked implementation and its call-site contract. |
| `home_server.workspace` | 50 | `` | Read the linked implementation and its call-site contract. |
| `home_server.open_results` | 66 | `` | Read the linked implementation and its call-site contract. |
| `home_server.auth` | 70 | `` | Read the linked implementation and its call-site contract. |
| `home_server.upload` | 80 | `` | Read the linked implementation and its call-site contract. |
| `home_server.create` | 93 | `` | Read the linked implementation and its call-site contract. |
| `home_server.begin` | 105 | `` | Read the linked implementation and its call-site contract. |
| `home_server.guide` | 110 | `` | Read the linked implementation and its call-site contract. |
| `home_server.project_info` | 120 | `` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `dpv_dashboard.auth`, `pathlib`, `shiny`

## dpv_dashboard/pages/inventory.py

Complete per-run file inventory with explicit availability and bounded previews.

[Source](../../dpv_dashboard/pages/inventory.py) · SHA256 `f5e4bd51efea9290cce23e97483d1c95c61c951a3d45de1456cd7ac8d15b5999`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `inventory_ui` | 14 | `` | Read the linked implementation and its call-site contract. |
| `inventory_server` | 28 | `input, output, session, context` | Read the linked implementation and its call-site contract. |
| `inventory_server.roots` | 33 | `` | Read the linked implementation and its call-site contract. |
| `inventory_server.folder` | 40 | `` | Read the linked implementation and its call-site contract. |
| `inventory_server.poll` | 45 | `` | Read the linked implementation and its call-site contract. |
| `inventory_server.inventory` | 56 | `` | Read the linked implementation and its call-site contract. |
| `inventory_server.overview` | 62 | `` | Read the linked implementation and its call-site contract. |
| `inventory_server.choose` | 69 | `` | Read the linked implementation and its call-site contract. |
| `inventory_server.selected` | 85 | `` | Read the linked implementation and its call-site contract. |
| `inventory_server.selected_info` | 98 | `` | Read the linked implementation and its call-site contract. |
| `inventory_server.preview` | 104 | `` | Read the linked implementation and its call-site contract. |
| `inventory_server.download` | 117 | `` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `dpv_dashboard.auth`, `dpv_dashboard.inspect`, `pathlib`, `shiny`

## dpv_dashboard/pages/research.py

Stage-specific research tables and clickable paper/ontology provenance.

[Source](../../dpv_dashboard/pages/research.py) · SHA256 `905670d342a4926ffeed8d4b1cdbe7f0398ab9edb6a8a1b3e3f1dd301c3a8ebc`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `research_ui` | 34 | `stage` | Read the linked implementation and its call-site contract. |
| `research_server` | 50 | `input, output, session, stage, context` | Read the linked implementation and its call-site contract. |
| `research_server.source_choices` | 54 | `` | Read the linked implementation and its call-site contract. |
| `research_server.poll` | 64 | `` | Read the linked implementation and its call-site contract. |
| `research_server.progress` | 73 | `` | Read the linked implementation and its call-site contract. |
| `research_server.results` | 84 | `` | Read the linked implementation and its call-site contract. |
| `research_server.record` | 112 | `` | Read the linked implementation and its call-site contract. |
| `research_server.connection` | 123 | `` | Read the linked implementation and its call-site contract. |
| `research_server.inspect` | 159 | `` | Read the linked implementation and its call-site contract. |
| `provenance_ui` | 195 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server` | 218 | `input, output, session, context` | Read the linked implementation and its call-site contract. |
| `provenance_server.requested_tab` | 225 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.sources` | 233 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.poll` | 246 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.concepts` | 257 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.papers` | 272 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.overview` | 290 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.paper_info` | 305 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.claims` | 317 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.claim_detail` | 325 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.lineage` | 332 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.originals` | 338 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.figures` | 345 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.ontology` | 359 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.connections` | 365 | `` | Read the linked implementation and its call-site contract. |
| `provenance_server.contradictions` | 374 | `` | Read the linked implementation and its call-site contract. |

Imports: `__future__`, `collections`, `dpv_dashboard`, `dpv_dashboard.inspect`, `pandas`, `pathlib`, `shiny`, `urllib.parse`

## dpv_dashboard/pages/stage.py

Reusable stage-page module with readable summaries and scoped artifact inspection.

[Source](../../dpv_dashboard/pages/stage.py) · SHA256 `5208be8ff4ed4d207de877c44a14ebbb974ff1bd2c20f40356c2bf1a42591c7b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `stage_ui` | 32 | `stage, lead=None` | Read the linked implementation and its call-site contract. |
| `stage_server` | 61 | `input, output, session, stage, context` | Read the linked implementation and its call-site contract. |
| `stage_server.baselines` | 66 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.comparison` | 79 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.folder` | 85 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.poll_artifacts` | 91 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.choices` | 101 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.selected_file` | 116 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.document` | 127 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.sections` | 132 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.overview` | 142 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.status` | 150 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.notes` | 173 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.review` | 185 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.report_library` | 192 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.report_document` | 214 | `path` | Resolve report image paths against its own folder, within the selected run. |
| `stage_server.report_document.asset_url` | 217 | `value` | Read the linked implementation and its call-site contract. |
| `stage_server.preview_report` | 231 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.results` | 252 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.visual` | 283 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.explore` | 302 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.raw` | 306 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.download` | 316 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.launch` | 324 | `` | Read the linked implementation and its call-site contract. |
| `stage_server.restart` | 329 | `` | Read the linked implementation and its call-site contract. |

Imports: `__future__`, `base64`, `dpv_dashboard`, `dpv_dashboard.auth`, `dpv_dashboard.inspect`, `dpv_dashboard.pages.research`, `json`, `pandas`, `pathlib`, `rdflib`, `re`, `shiny`, `urllib.parse`

## dpv_dashboard/presentation.py

Readable display labels; source keys and artifacts remain unchanged.

[Source](../../dpv_dashboard/presentation.py) · SHA256 `64349c5fbab2f4c3c85f4f56f5f300d364c18ba202d6be98f24deabd24789521`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `heading` | 42 | `key` | Read the linked implementation and its call-site contract. |
| `friendly` | 54 | `value` | Read the linked implementation and its call-site contract. |
| `prose` | 60 | `text` | Read the linked implementation and its call-site contract. |
| `grid` | 64 | `frame, compact=False, **kwargs` | Read the linked implementation and its call-site contract. |
| `selected` | 117 | `renderer` | Read the linked implementation and its call-site contract. |
| `run_label` | 126 | `path` | Read the linked implementation and its call-site contract. |
| `ontology_label` | 136 | `path` | Read the linked implementation and its call-site contract. |
| `stage_step` | 147 | `stage, number, status, style=None` | Read the linked implementation and its call-site contract. |
| `growth_note` | 155 | `` | Read the linked implementation and its call-site contract. |
| `report_html` | 164 | `text, asset_url=None` | Add a dashboard-only interpretation; never rewrite saved reports or images. |
| `report_html.explain` | 166 | `match` | Read the linked implementation and its call-site contract. |

Imports: `html`, `json`, `re`, `shiny`

## dpv_dashboard/quality.py

Conservative malformed-concept checks; flag for review rather than repair labels.

[Source](../../dpv_dashboard/quality.py) · SHA256 `b05769e5cdbe35a8d2145ceaee93118b191e671a89789a9f06ca63d21148d13b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `label_issues` | 13 | `value` | Read the linked implementation and its call-site contract. |
| `concept_issues` | 27 | `record` | Read the linked implementation and its call-site contract. |
| `bounded` | 45 | `value, limit=160` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `re`

## dpv_dashboard/record_view.py

Shared, read-only record inspector and bounded research summaries.

[Source](../../dpv_dashboard/record_view.py) · SHA256 `b6a1a1d328c490df81e34f2be4fd82a330a814662846b03583055f5b8fc231a2`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `value` | 13 | `raw` | Read the linked implementation and its call-site contract. |
| `inspector` | 21 | `data, row` | Read the linked implementation and its call-site contract. |
| `priorities` | 77 | `rows` | Count findings separately from affected concepts; do not invent severity. |
| `compare` | 97 | `current, baseline, stage` | Compare saved counts only; labels never establish identity across runs. |
| `compare.vocabulary` | 104 | `data` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `dpv_dashboard`, `json`, `math`, `numbers`, `re`, `shiny`

## dpv_dashboard/research.py

Read-only joins from ontology results to canonical concepts, papers and evidence.

[Source](../../dpv_dashboard/research.py) · SHA256 `cb0626bd410bb7a1aaced7301b671c4c222b56a124cb679d78beaf1c791582c7`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `records` | 13 | `value` | Read the linked implementation and its call-site contract. |
| `text` | 17 | `value` | Read the linked implementation and its call-site contract. |
| `evidence_status` | 21 | `row` | Read the linked implementation and its call-site contract. |
| `upper_label` | 26 | `iri` | Read the linked implementation and its call-site contract. |
| `source_roots` | 31 | `root` | Read the linked implementation and its call-site contract. |
| `index` | 48 | `root` | Read the linked implementation and its call-site contract. |
| `_index` | 62 | `root, signature` | Read the linked implementation and its call-site contract. |
| `RunIndex.__init__` | 67 | `self, root` | Read the linked implementation and its call-site contract. |
| `RunIndex.label` | 113 | `self, cid` | Read the linked implementation and its call-site contract. |
| `RunIndex._lineage` | 116 | `self, saved` | Read the linked implementation and its call-site contract. |
| `RunIndex.paper_rows` | 158 | `self` | Read the linked implementation and its call-site contract. |
| `RunIndex.claims` | 165 | `self, paper=None, canonical=None` | Read the linked implementation and its call-site contract. |
| `RunIndex.stage_rows` | 192 | `self, stage, view` | Read the linked implementation and its call-site contract. |
| `RunIndex.review_rows` | 256 | `self, stage=None, canonical=None` | Read the linked implementation and its call-site contract. |
| `RunIndex.progress` | 264 | `self, stage` | Read the linked implementation and its call-site contract. |
| `RunIndex.narrative` | 303 | `self, stage` | Read the linked implementation and its call-site contract. |

Imports: `__future__`, `collections`, `dpv_dashboard`, `functools`, `pathlib`

## dpv_dashboard/tests/test_chat_presentation.py

Workflow model inheritance and display changes must not break provenance joins.

[Source](../../dpv_dashboard/tests/test_chat_presentation.py) · SHA256 `c2bc7071501b7cf7ec06eca974635aa23f2cf2563856593b8d38513b9d2c238b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `test_profiles_are_read_without_import_or_environment_changes` | 10 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_chat_inherits_actual_agent_model_and_endpoint` | 20 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_missing_credentials_are_friendly_and_alternatives_filtered` | 35 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_project_model_fallback_and_custom_connection` | 46 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_readable_table_preserves_raw_identity_and_selection` | 53 | `` | Read the linked implementation and its call-site contract. |
| `test_readable_table_preserves_raw_identity_and_selection.Renderer.data` | 61 | `self` | Read the linked implementation and its call-site contract. |
| `test_readable_table_preserves_raw_identity_and_selection.Renderer.data_view` | 62 | `self, selected` | Read the linked implementation and its call-site contract. |
| `test_anthropic_chat_uses_provider_protocol_without_real_requests` | 74 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_anthropic_chat_uses_provider_protocol_without_real_requests.Response.__enter__` | 79 | `self` | Read the linked implementation and its call-site contract. |
| `test_anthropic_chat_uses_provider_protocol_without_real_requests.Response.__exit__` | 80 | `self, *args` | Read the linked implementation and its call-site contract. |
| `test_anthropic_chat_uses_provider_protocol_without_real_requests.Response.read` | 81 | `self, limit` | Read the linked implementation and its call-site contract. |
| `test_anthropic_chat_uses_provider_protocol_without_real_requests.transport` | 82 | `request, timeout` | Read the linked implementation and its call-site contract. |
| `test_report_preview_styles_and_resolves_local_images_without_source_changes` | 89 | `` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `json`, `os`, `pandas`, `pathlib`, `pytest`

## dpv_dashboard/tests/test_dashboard.py

Offline regression coverage for the wrapper's domain and attempt semantics.

[Source](../../dpv_dashboard/tests/test_dashboard.py) · SHA256 `23e20f5476b11ba23278c8757ada0fc7a7434d67ab1c2829b968f4008510377b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `workspace` | 15 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_restart_preserves_upstream_and_invalidates_downstream` | 24 | `workspace` | Read the linked implementation and its call-site contract. |
| `test_stage_requires_completed_inputs` | 45 | `workspace` | Read the linked implementation and its call-site contract. |
| `test_recursive_expansion_deduplicates_overlapping_roots` | 51 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_doi_duplicates_keep_attachment_alternatives` | 59 | `` | Read the linked implementation and its call-site contract. |
| `test_domain_ranking_across_groups_not_per_collection` | 66 | `workspace, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_domain_ranking_across_groups_not_per_collection.Client.__init__` | 77 | `self, identifier, *args` | Read the linked implementation and its call-site contract. |
| `test_domain_ranking_across_groups_not_per_collection.Client.everything` | 79 | `self, result` | Read the linked implementation and its call-site contract. |
| `test_domain_ranking_across_groups_not_per_collection.Client.collection_items_top` | 81 | `self, key` | Read the linked implementation and its call-site contract. |
| `test_domain_ranking_across_groups_not_per_collection.pdf` | 86 | `client, key, destination` | Read the linked implementation and its call-site contract. |
| `test_personal_and_restricted_group_discovery` | 97 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_webvowl_keeps_mapping_and_restriction_iris` | 105 | `` | Read the linked implementation and its call-site contract. |
| `test_paths_cannot_escape_workspace` | 117 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_subprocess_bootstrap_isolates_pipeline_outputs` | 122 | `workspace` | Read the linked implementation and its call-site contract. |
| `test_parser_saves_existing_chunker_windows_without_model` | 141 | `workspace` | Read the linked implementation and its call-site contract. |
| `test_supervised_worker_failure_is_durable_without_network` | 160 | `workspace` | Read the linked implementation and its call-site contract. |
| `test_report_attempts_are_preserved` | 176 | `workspace, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_report_attempts_are_preserved.build` | 183 | `**kwargs` | Read the linked implementation and its call-site contract. |
| `test_restart_filters_downstream_compute` | 198 | `workspace` | Read the linked implementation and its call-site contract. |
| `test_cancel_stops_only_supervised_test_process` | 208 | `workspace, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_cancel_stops_only_supervised_test_process.sleeping_process` | 215 | `command, **kwargs` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `dpv_dashboard.jobs`, `dpv_dashboard.viewer`, `dpv_dashboard.worker`, `dpv_dashboard.zotero`, `json`, `pathlib`, `pymupdf`, `pytest`, `pyzotero`, `src`, `src.tools`, `subprocess`, `sys`, `time`, `types`

## dpv_dashboard/tests/test_external.py

Test external support for the Knowledge Workflow system.

[Source](../../dpv_dashboard/tests/test_external.py) · SHA256 `b8d34ae7ab3673cbbe439fa112df5c09e85bbf5ff3b2a81d69cf4163cd7f015b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `test_discovery_ignores_dashboard_and_finds_original_outputs` | 8 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_external_status_and_available_intermediates` | 19 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_integration_and_sweep_artifacts` | 34 | `tmp_path` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`

## dpv_dashboard/tests/test_highlight_exploration.py

Disposable PDF boxes, provenance scope and offline exploration behavior.

[Source](../../dpv_dashboard/tests/test_highlight_exploration.py) · SHA256 `22210279a8d48a48d0a53385e1cb7b521a25e64462f85753e055e05dc3d9c047`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `focused_run` | 14 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_concept_focus_preserved_and_original_pdf_unchanged` | 36 | `focused_run` | Read the linked implementation and its call-site contract. |
| `test_figure_boxes_caption_and_conservative_image_region` | 52 | `focused_run` | Read the linked implementation and its call-site contract. |
| `test_unlocated_focus_is_not_inferred` | 63 | `focused_run` | Read the linked implementation and its call-site contract. |
| `test_scoped_search_and_graph_neighborhood` | 72 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_model_chat_uses_bounded_cited_context_only_on_explicit_call` | 87 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_model_chat_uses_bounded_cited_context_only_on_explicit_call.Response.__enter__` | 90 | `self` | Read the linked implementation and its call-site contract. |
| `test_model_chat_uses_bounded_cited_context_only_on_explicit_call.Response.__exit__` | 91 | `self, *args` | Read the linked implementation and its call-site contract. |
| `test_model_chat_uses_bounded_cited_context_only_on_explicit_call.Response.read` | 92 | `self, limit` | Read the linked implementation and its call-site contract. |
| `test_model_chat_uses_bounded_cited_context_only_on_explicit_call.transport` | 93 | `request, timeout` | Read the linked implementation and its call-site contract. |
| `test_vector_panel_region_is_explicitly_estimated` | 104 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_rotated_pdf_retains_focus_coordinates` | 119 | `tmp_path` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `hashlib`, `json`, `pathlib`, `pymupdf`, `pytest`

## dpv_dashboard/tests/test_record_views.py

Display compaction must preserve source identity through filtering and sorting.

[Source](../../dpv_dashboard/tests/test_record_views.py) · SHA256 `dc455edd86ca2ba6a591834522783526adb21346e267e43d5ecbc9b52857a80d`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `test_compact_selection_preserves_hidden_identity_and_raw_status` | 11 | `` | Read the linked implementation and its call-site contract. |
| `test_compact_selection_preserves_hidden_identity_and_raw_status.Renderer.data` | 17 | `self` | Read the linked implementation and its call-site contract. |
| `test_compact_selection_preserves_hidden_identity_and_raw_status.Renderer.data_view` | 18 | `self, selected` | Read the linked implementation and its call-site contract. |
| `test_rich_display_can_restore_plain_record_without_html_tags` | 25 | `` | Read the linked implementation and its call-site contract. |
| `test_rich_display_can_restore_plain_record_without_html_tags.Renderer.data` | 31 | `self` | Read the linked implementation and its call-site contract. |
| `test_rich_display_can_restore_plain_record_without_html_tags.Renderer.data_view` | 32 | `self, selected` | Read the linked implementation and its call-site contract. |
| `test_inspector_escapes_evidence_and_explains_missing_provenance` | 36 | `` | Read the linked implementation and its call-site contract. |
| `test_review_summary_distinguishes_repeated_findings_from_concepts` | 44 | `` | Read the linked implementation and its call-site contract. |
| `test_run_comparison_uses_counts_and_literal_labels_without_equivalence` | 51 | `` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `pandas`, `pathlib`, `types`

## dpv_dashboard/tests/test_reference_crops.py

Scoped citations and crop fallbacks must not invent evidence or alter PDFs.

[Source](../../dpv_dashboard/tests/test_reference_crops.py) · SHA256 `a2502e036a2d6891712a5d13e6f2c805cdaaa0f0a80327c4adebe710e0e74017`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `source` | 13 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_inline_citations_are_scoped_escaped_and_open_exact_claim` | 30 | `source` | Read the linked implementation and its call-site contract. |
| `test_crop_dimensions_full_paper_collapsed_and_source_unchanged` | 42 | `source` | Read the linked implementation and its call-site contract. |
| `test_caption_missing_never_falls_back_to_a_full_page_crop` | 54 | `source` | Read the linked implementation and its call-site contract. |
| `test_explicit_references_and_safe_external_schemes` | 63 | `source` | Read the linked implementation and its call-site contract. |
| `test_integration_progress_refers_to_source_domains` | 73 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_crop_rotates_recorded_coordinates_and_keeps_both_panels` | 79 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_report_references_preserve_markdown_and_do_not_nest_links` | 93 | `source` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `hashlib`, `pathlib`, `pymupdf`, `pytest`

## dpv_dashboard/tests/test_research.py

Read-only coverage, scoped joins and explicit uncertainty in research views.

[Source](../../dpv_dashboard/tests/test_research.py) · SHA256 `00809c75de7e9e2e43df548b8858d74493f3dbb9290995b8e75de1f014505c81`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `run` | 12 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_recorded_lineage_is_scoped_and_joins_original_claims` | 34 | `run` | Read the linked implementation and its call-site contract. |
| `test_older_runs_never_claim_recorded_merge_decisions` | 47 | `run` | Read the linked implementation and its call-site contract. |
| `test_ambiguous_alias_does_not_create_a_claim_join` | 54 | `run` | Read the linked implementation and its call-site contract. |
| `test_bad_saved_mapping_is_explicit_not_reconstructed` | 63 | `run` | Read the linked implementation and its call-site contract. |
| `test_unreadable_lineage_never_falls_back_to_an_inferred_map` | 70 | `run` | Read the linked implementation and its call-site contract. |
| `test_conflicting_or_changed_recorded_sources_are_not_used_as_evidence` | 78 | `run` | Read the linked implementation and its call-site contract. |
| `test_inventory_keeps_unknown_partial_and_restricted_files` | 90 | `run` | Read the linked implementation and its call-site contract. |
| `test_reads_do_not_rewrite_source_artifacts` | 107 | `run` | Read the linked implementation and its call-site contract. |
| `test_unreadable_non_json_artifact_is_visible_but_not_downloadable` | 116 | `run, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_unreadable_non_json_artifact_is_visible_but_not_downloadable.open_file` | 120 | `path, *args, **kwargs` | Read the linked implementation and its call-site contract. |
| `test_newer_recorded_upstream_completion_marks_existing_outputs_superseded` | 131 | `run` | Read the linked implementation and its call-site contract. |
| `test_new_files_refresh_index_but_unchanged_files_reuse_it` | 141 | `run` | Read the linked implementation and its call-site contract. |
| `test_enrichment_mapping_and_review_views_retain_provenance` | 149 | `run` | Read the linked implementation and its call-site contract. |
| `test_integration_source_navigation_uses_only_recorded_local_runs` | 165 | `run` | Read the linked implementation and its call-site contract. |
| `test_integration_federation_keeps_domains_and_paper_ids_separate` | 181 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_media_references_escape_content_and_restrict_files` | 199 | `run, tmp_path` | Read the linked implementation and its call-site contract. |
| `test_pdf_page_preview_uses_recorded_page_and_rejects_outside_page` | 214 | `run` | Read the linked implementation and its call-site contract. |
| `test_artifact_relationship_names_preserve_original_scoped_ids` | 227 | `run` | Read the linked implementation and its call-site contract. |
| `test_artifact_relationship_names_preserve_original_scoped_ids.Renderer.data` | 238 | `self` | Read the linked implementation and its call-site contract. |
| `test_artifact_relationship_names_preserve_original_scoped_ids.Renderer.data_view` | 239 | `self, selected` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `hashlib`, `pathlib`, `pymupdf`, `pytest`

## dpv_dashboard/tests/test_search_quality.py

Test search quality support for the Knowledge Workflow system.

[Source](../../dpv_dashboard/tests/test_search_quality.py) · SHA256 `635dfd623767f7fe5ef07ba4300fc9ea2bc1fc7f7c5b9ac0d4899b46e4ef47d1`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `test_actual_malformed_label_and_flags_never_enter_chat` | 15 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_actual_malformed_label_and_flags_never_enter_chat.Reply.__enter__` | 24 | `self` | Read the linked implementation and its call-site contract. |
| `test_actual_malformed_label_and_flags_never_enter_chat.Reply.__exit__` | 25 | `self, *args` | Read the linked implementation and its call-site contract. |
| `test_actual_malformed_label_and_flags_never_enter_chat.Reply.read` | 26 | `self, limit` | Read the linked implementation and its call-site contract. |
| `test_actual_malformed_label_and_flags_never_enter_chat.transport` | 27 | `request, timeout` | Read the linked implementation and its call-site contract. |
| `test_documents_exclude_source_and_rdf_copies_without_writing` | 39 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_integration_ontology_links_are_unique_and_scoped` | 59 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_repetition_and_legitimate_labels` | 73 | `` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `hashlib`, `json`, `pathlib`, `unittest.mock`

## dpv_dashboard/tests/test_stage_navigation.py

Stage controls and figure explanations remain display-only.

[Source](../../dpv_dashboard/tests/test_stage_navigation.py) · SHA256 `1f965dc34a1d8240a952f2086b622fe0095dc463a1a81d03dd630bd8b71e190f`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `test_all_stage_controls_are_named_native_buttons` | 10 | `` | Read the linked implementation and its call-site contract. |
| `test_growth_explanation_states_order_variability_not_confidence` | 21 | `` | Read the linked implementation and its call-site contract. |
| `test_report_preview_explains_only_growth_without_altering_source` | 29 | `` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `html`, `pytest`

## dpv_dashboard/tests/test_visual_graph.py

Test visual graph support for the Knowledge Workflow system.

[Source](../../dpv_dashboard/tests/test_visual_graph.py) · SHA256 `f1c9b1aed10c88c6ad422473937e7dadded443d96aedb3ee7a799651a5aa109d`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `test_scientific_relations_default_and_claim_sources_survive_alignment` | 26 | `` | Read the linked implementation and its call-site contract. |
| `test_focus_keeps_claim_evidence_restrictions_and_aliases` | 44 | `` | Read the linked implementation and its call-site contract. |
| `test_saved_layers_and_missing_coverage_without_source_writes` | 53 | `tmp_path` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `dpv_dashboard.viewer`, `hashlib`, `pathlib`, `rdflib`

## dpv_dashboard/viewer.py

Independent RDF-to-WebVOWL projection; never fetch ontology imports or rewrite RDF.

[Source](../../dpv_dashboard/viewer.py) · SHA256 `520d19afd2380d083fcf1f67afb8a5e2536f6699a84463029e2c4fd0ab7bdbb1`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `convert` | 12 | `text, show_disjoint=False, show_hierarchy=True, show_mappings=True, origins=None, show_literature=True` | Read the linked implementation and its call-site contract. |
| `convert.label` | 20 | `term` | Read the linked implementation and its call-site contract. |
| `convert.add` | 33 | `subject, predicate, target, kind, triple` | Read the linked implementation and its call-site contract. |
| `convert.node_attributes` | 80 | `c` | Read the linked implementation and its call-site contract. |
| `viewer` | 99 | `text, identifier, payload=None` | Read the linked implementation and its call-site contract. |

Imports: `__future__`, `dpv_dashboard`, `json`, `rdflib`, `shiny`, `uuid`

## dpv_dashboard/visual_graph.py

Assemble saved graph layers locally; never fetch imports or rewrite source files.

[Source](../../dpv_dashboard/visual_graph.py) · SHA256 `f25573e608ab571955d37ee95c9526fa79450ff9b1c75f8824302b647c6f0348`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `files` | 11 | `root, selected, literature=True` | Read the linked implementation and its call-site contract. |
| `files.add` | 16 | `base, path, kind` | Read the linked implementation and its call-site contract. |
| `assemble` | 46 | `entries` | Read the linked implementation and its call-site contract. |

Imports: `dpv_dashboard`, `functools`, `pathlib`, `rdflib`

## dpv_dashboard/worker.py

Child-process adapter. Imports existing pipeline functions without editing source files.

[Source](../../dpv_dashboard/worker.py) · SHA256 `593aef6083bfa29a385ca573a2c6ae552a600a1678bc280bffcab095f734bffd`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `bootstrap` | 21 | `project, fresh_cache=None` | Read the linked implementation and its call-site contract. |
| `ingest` | 35 | `run, domain, folder` | Read the linked implementation and its call-site contract. |
| `parse` | 91 | `run, folder` | Read the linked implementation and its call-site contract. |
| `perform` | 112 | `project, domain, stage, restart=False` | Read the linked implementation and its call-site contract. |
| `integrate` | 156 | `project` | Read the linked implementation and its call-site contract. |
| `reports` | 177 | `project` | Read the linked implementation and its call-site contract. |
| `global_stage` | 194 | `project, stage` | Read the linked implementation and its call-site contract. |
| `main` | 206 | `` | Read the linked implementation and its call-site contract. |

Imports: `__future__`, `argparse`, `dpv_dashboard`, `dpv_dashboard.auth`, `dpv_dashboard.zotero`, `hashlib`, `json`, `os`, `pathlib`, `pyzotero.zotero`, `src`, `src.agents.extraction`, `src.config`, `subprocess`, `sys`, `time`, `traceback`, `types`, `uuid`

## dpv_dashboard/www/dashboard.css

Summary: dashboard support for Knowledge Workflow; retain the existing operational notes below.

[Source](../../dpv_dashboard/www/dashboard.css) · SHA256 `15cad2d904f1fffa1660d51f9999a526499434c28c7072699112c08448b0422d`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## dpv_dashboard/www/dashboard.js

Summary: dashboard support for Knowledge Workflow; retain the existing operational notes below.

[Source](../../dpv_dashboard/www/dashboard.js) · SHA256 `4cc4a7dc89e52ad6dab8ff613c2c5cb1cd6f07526befb1208c4f4292863537d5`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## dpv_dashboard/www/vowl-bridge.js

Summary: vowl-bridge support for Knowledge Workflow; retain the existing operational notes below.

[Source](../../dpv_dashboard/www/vowl-bridge.js) · SHA256 `6efecfc597aca3716b34b65523bb3889382a6661b72f75a4fc9080b3775f0436`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## dpv_dashboard/zotero.py

Dashboard-owned Zotero discovery and recursive selection, using authenticated headers.

[Source](../../dpv_dashboard/zotero.py) · SHA256 `1b23305e2d77c4ad88e68f5393d06074419309549a532dc03ac63226ea237b93`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `Libraries.__init__` | 13 | `self, key` | Read the linked implementation and its call-site contract. |
| `Libraries.get` | 19 | `self, path, params=None` | Read the linked implementation and its call-site contract. |
| `Libraries.pages` | 31 | `self, path` | Read the linked implementation and its call-site contract. |
| `Libraries.prefix` | 43 | `library` | Read the linked implementation and its call-site contract. |
| `Libraries.libraries` | 48 | `self` | Read the linked implementation and its call-site contract. |
| `Libraries.collections` | 73 | `self, library` | Read the linked implementation and its call-site contract. |
| `Libraries.expand` | 78 | `self, selected` | Read the linked implementation and its call-site contract. |
| `deduplicate` | 97 | `papers` | Prefer DOI identity; retain all accessible attachment sources for duplicates. |

Imports: `__future__`, `re`, `requests`, `time`

## script.txt

Summary: script support for Knowledge Workflow; retain the existing operational notes below.

[Source](../../script.txt) · SHA256 `ecc8aa927f231b14d87af26ce3c13d7f61c1e62b88b2f5c0a7a884eba1dab449`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## scripts/auto-sweep.ps1

Summary: auto-sweep support for Knowledge Workflow; retain the existing operational notes below.

[Source](../../scripts/auto-sweep.ps1) · SHA256 `c18347bc77a3258a6be0a54339d0f9bdf3345b4605516bc805892af79bab76f4`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## scripts/bench-concurrency.ps1

Summary: bench-concurrency support for Knowledge Workflow; retain the existing operational notes below.

[Source](../../scripts/bench-concurrency.ps1) · SHA256 `7f407a397d420557d0cdd3c419519599b2a1abea8d5d9b5b9d94d1c82b025497`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## scripts/codebase_ontology.py

Enrich the codebase graph with connected contracts, resources and external definitions.

[Source](../../scripts/codebase_ontology.py) · SHA256 `79179bdf841995b01068a3097e49dec60ec575f7f2fe23ee71347b080a2c07a8`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `file_node` | 20 | `path` | Read the linked implementation and its call-site contract. |
| `function_node` | 24 | `path, name` | Read the linked implementation and its call-site contract. |
| `freshness_errors` | 28 | `graph, root` | Reject stale documentation without importing application modules or reading settings. |
| `enrich` | 51 | `graph, root, inventory, contract` | Connect the inventory and make planning/inspection rules machine-readable. |

Imports: `ast`, `hashlib`, `json`, `pathlib`, `rdflib`, `urllib.parse`

## scripts/compare_runs.py

Tables for scripts/run-checks.ps1, read from each run's rows.jsonl (one line per answered row) and run.json.

[Source](../../scripts/compare_runs.py) · SHA256 `a6bbf8e75b582e22c7123c19aaffa6beeaaa6bdf7b57d6706d24fec919fb7945`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `labels` | 22 | `run: str` | Read the linked implementation and its call-site contract. |
| `canon` | 27 | `answer, names: dict` | Read the linked implementation and its call-site contract. |
| `rows` | 37 | `run: str` | Read the linked implementation and its call-site contract. |
| `share` | 45 | `pairs` | Read the linked implementation and its call-site contract. |
| `wall` | 50 | `run: str` | Read the linked implementation and its call-site contract. |
| `reuse` | 55 | `a: str, b: str, c: str, d: str` | Read the linked implementation and its call-site contract. |
| `facets` | 71 | `combined: str, split: str, again: str` | Read the linked implementation and its call-site contract. |
| `facets.tags` | 72 | `run, names` | Read the linked implementation and its call-site contract. |
| `coverage` | 89 | `*runs: str` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `json`, `pathlib`, `re`, `sys`

## scripts/data_journey.py

Model information transformations and export read-only concept journey snapshots.

[Source](../../scripts/data_journey.py) · SHA256 `35949fcebeefef117e9b778fd7666dd03ef8c9f01c353f20fe6d9fde686a6792`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `enrich_journey` | 19 | `graph, root` | Connect information states and transformations to artifacts, stages and source functions. |
| `enrich_journey.entity` | 46 | `node, kind, label, definition` | Read the linked implementation and its call-site contract. |
| `identifier` | 79 | `value` | Accept a simple saved-run or record identifier without path traversal. |
| `label_key` | 85 | `value` | Return a conservative label comparison key; equality is not a recorded merge decision. |
| `Snapshot.__init__` | 92 | `self, root` | Read the linked implementation and its call-site contract. |
| `Snapshot.read` | 95 | `self, relative, optional=False` | Read the linked implementation and its call-site contract. |
| `Snapshot.json` | 108 | `self, relative, optional=False` | Read the linked implementation and its call-site contract. |
| `Snapshot.fingerprints` | 112 | `self` | Read the linked implementation and its call-site contract. |
| `public_record` | 118 | `value, fields` | Select public scientific fields; exclude raw model calls, runtime config and local PDF paths. |
| `build_traces` | 123 | `outputs, run_id, integration_id=None` | Observe saved joins and reconstruct candidate original labels without asserting exact lineage. |
| `export_traces` | 239 | `outputs, destination, run_id, integration_id=None` | Write a separate observation package and escaped, whitelisted artifact previews. |
| `export_traces.write` | 242 | `relative, text` | Read the linked implementation and its call-site contract. |
| `export_traces.preview` | 246 | `relative, data` | Read the linked implementation and its call-site contract. |

Imports: `codebase_ontology`, `datetime`, `hashlib`, `html`, `json`, `operational_contracts`, `pathlib`, `rdflib`, `re`, `unicodedata`, `urllib.parse`

## scripts/document-codebase.py

Generate source-linked codebase documentation and the operational workflow ontology.

[Source](../../scripts/document-codebase.py) · SHA256 `978820ef3433b7efce6f072bef7dfc1316d04f871e9aeb196dc10d9d97eea70b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `code_files` | 28 | `` | Read the linked implementation and its call-site contract. |
| `inventory` | 33 | `` | Read the linked implementation and its call-site contract. |
| `author_headers` | 66 | `` | Apply only headers, recording an exact patch; Python executable AST must match. |
| `build` | 123 | `` | Read the linked implementation and its call-site contract. |
| `build.entity` | 181 | `uri, kind, label` | Read the linked implementation and its call-site contract. |

Imports: `argparse`, `ast`, `codebase_ontology`, `data_journey`, `difflib`, `hashlib`, `json`, `operational_contracts`, `pathlib`, `rdflib`, `re`, `subprocess`, `urllib.parse`

## scripts/documentation_library.py

Publish a local, linked documentation library without exposing the repository root.

[Source](../../scripts/documentation_library.py) · SHA256 `47723ea07287ebc2dc6075c4a3f2f8e52a99b07bb88d4c8ea5e4998c518dd74a`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `build_library` | 23 | `root=ROOT, output=OUT` | Export public docs only; keep external links and resolve published local references. |
| `build_library.relative` | 69 | `target, page` | Read the linked implementation and its call-site contract. |
| `build_library.shell` | 72 | `title, body, page` | Read the linked implementation and its call-site contract. |

Imports: `hashlib`, `html`, `json`, `markdown_it`, `os`, `pathlib`, `re`, `shutil`, `urllib.parse`

## scripts/eval_parent_recall.py

Recall of CCO/BFO parent candidates, measured on concepts the ontology stage name-matched to an MDS-Onto or PMDCO class: the gold parent is that class's nearest CCO/BFO ancestor. No model calls; embeddings come from EMBED (cached).

[Source](../../scripts/eval_parent_recall.py) · SHA256 `60a78bf0aa850ea7732857c307ee8202e1477662f06aafbff9fbc6b807954d76`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `concept_case` | 29 | `c: dict, menu_lc: dict` | Read the linked implementation and its call-site contract. |
| `gold_cases` | 36 | `runs: list[str]` | One case per name-matched label: the concept as the ontology stage saw it, its category root (from its type, as the local tier assigns it) and the matched class's nearest CCO/BFO ancestors. |
| `queries` | 57 | `c: dict` | Read the linked implementation and its call-site contract. |
| `current` | 61 | `c: dict, vec, full: bool=False` | The ontology stage's _candidates: global search, then category filter (exact labels kept), CCO first, top K. |
| `masked` | 69 | `c: dict, vec, pool: dict, how: str` | Every CCO/BFO class under the category root, ranked with no thresholds by fused score, cosine or lexical. |
| `pools` | 82 | `cases: list[dict], vectors: dict \| None` | Per category root: CCO/BFO classes beneath it, their normalised labels and (optionally) their vectors. |
| `store_vectors` | 95 | `` | Read the linked implementation and its call-site contract. |
| `score` | 101 | `cases: list[dict], picks: dict` | Read the linked implementation and its call-site contract. |
| `main` | 109 | `` | Read the linked implementation and its call-site contract. |

Imports: `argparse`, `collections`, `glob`, `json`, `numpy`, `pathlib`, `src.agents.ontology`, `src.config`, `src.tools`, `sys`

## scripts/export-codebase-webvowl.py

Export focused reviewer views and navigable records for the codebase ontology.

[Source](../../scripts/export-codebase-webvowl.py) · SHA256 `4dbcd644cc433e617ca83a87006b1ff17b0ea01410a0bb231d34af98b3d48ce5`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `main` | 24 | `` | Build bounded stage graphs, full downloadable data and source-linked review metadata. |
| `main.payload` | 97 | `selected, edges, title` | Read the linked implementation and its call-site contract. |
| `main.save` | 112 | `name, value` | Read the linked implementation and its call-site contract. |

Imports: `data_journey`, `documentation_library`, `dpv_dashboard.viewer`, `hashlib`, `html`, `json`, `pathlib`, `rdflib`, `re`, `shutil`, `sys`

## scripts/ontology_agent.py

Plan trusted ontology invocations and observe saved runs without executing pipeline work.

[Source](../../scripts/ontology_agent.py) · SHA256 `fd561802f54eec3cbb578ecc1dc83da2f6cb37628d42d500640353bcbb7621ed`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `invocation` | 23 | `graph, step, mode` | Require one unambiguous command in the selected execution mode. |
| `plan` | 31 | `graph, target, mode, bindings` | Topologically bind a mode-specific plan; leave environmental checks explicit. |
| `plan.visit` | 43 | `step, stack` | Read the linked implementation and its call-site contract. |
| `plan.visit.substitute` | 53 | `match` | Read the linked implementation and its call-site contract. |
| `read_artifact` | 74 | `path, root` | Read a bounded, stable artifact and return only public structural metadata. |
| `inspect_run` | 110 | `graph, folder, outputs` | Separate saved completion, readable products and review needs in a read-only snapshot. |
| `inspect_run.read` | 116 | `path` | Read the linked implementation and its call-site contract. |
| `observation_graph` | 259 | `result` | Represent observations as information records, without inventing execution processes. |
| `main` | 294 | `` | Read the linked implementation and its call-site contract. |

Imports: `argparse`, `codebase_ontology`, `datetime`, `hashlib`, `importlib.util`, `json`, `operational_contracts`, `pathlib`, `rdflib`, `re`, `sys`, `urllib.parse`

## scripts/operational_contracts.py

Build source-backed agent contracts, definitions and read-only operational checks.

[Source](../../scripts/operational_contracts.py) · SHA256 `51fa8b9bf152eb627b66b59692ad17b382754a95874a879376eb4fb2185662f3`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `artifact_node` | 16 | `pattern` | Return the same canonical artifact IRI used by the inventory generator. |
| `build_contracts` | 21 | `graph, root, inventory` | Connect reviewed operational contracts and statically observed callable arguments. |
| `build_contracts.entity` | 67 | `node, kind, label, definition` | Read the linked implementation and its call-site contract. |
| `guide` | 200 | `graph, stage` | Retrieve a task recipe from RDF, including actual bound artifacts and formal arguments. |
| `assess` | 227 | `graph, folder, outputs, stage, phase='after'` | Evaluate a bounded set of saved-data checks; never run commands or accept scientific claims. |
| `assess.read` | 234 | `pattern` | Read the linked implementation and its call-site contract. |
| `assess.check` | 239 | `identifier, passed, message, severity='block'` | Read the linked implementation and its call-site contract. |
| `assess.select` | 241 | `data, selector='$'` | Read the linked implementation and its call-site contract. |
| `assess.values` | 248 | `pattern, selector='$'` | Read the linked implementation and its call-site contract. |
| `assess.identifiers` | 254 | `rows, field` | Read the linked implementation and its call-site contract. |

Imports: `ast`, `codebase_ontology`, `hashlib`, `json`, `ontology_agent`, `pathlib`, `rdflib`, `rdflib.compare`, `urllib.parse`

## scripts/run-checks.ps1

Summary: run-checks support for Knowledge Workflow; retain the existing operational notes below.

[Source](../../scripts/run-checks.ps1) · SHA256 `f51ba08cc351a4277ef1b34349e049257b6fd997f1ef5f0669107c82bc03db78`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## scripts/run-sweep.ps1

Summary: run-sweep support for Knowledge Workflow; retain the existing operational notes below.

[Source](../../scripts/run-sweep.ps1) · SHA256 `f54ba5aac75b9285227d739577639eeee04f7342a301889dfe10c287a6f63f71`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## scripts/slurm-sweep.sh

Summary: run/resume a GPU-backed literature sweep, record serving setup and sample GPU power/utilization.

[Source](../../scripts/slurm-sweep.sh) · SHA256 `814b4b2e7acc91497ad73e036fe4ab4f945f31412d063f29c36443c9516b7221`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## scripts/stop-sweep.ps1

Summary: stop-sweep support for Knowledge Workflow; retain the existing operational notes below.

[Source](../../scripts/stop-sweep.ps1) · SHA256 `35844137ffe0e76cb8a7b2ea2d25df6062e21b5a8f49fd62f7ef3139d6995c80`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## scripts/sync-outputs.ps1

Summary: Pull pipeline outputs from the Slurm cluster and push them to the dashboard's Cloud Storage bucket.

[Source](../../scripts/sync-outputs.ps1) · SHA256 `f2ea0025abbd377ae5261973cce66603b2a10a1961007914fb8bd4c8247b15df`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## scripts/validate-codebase-ontology.py

Validate offline ontology imports, operational links, SHACL and bounded OWL-RL consistency.

[Source](../../scripts/validate-codebase-ontology.py) · SHA256 `7f1e03fd24e01c7e24aed4ef9093ee437734718e5bb826d4728103c29c5280ce`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `operational_errors` | 22 | `graph, root, inventory` | Check navigation, mode-specific dependencies and contract/source freshness before reasoning. |
| `main` | 84 | `` | Read the linked implementation and its call-site contract. |
| `main.visit` | 115 | `step, stack` | Read the linked implementation and its call-site contract. |

Imports: `codebase_ontology`, `hashlib`, `importlib.util`, `json`, `ontology_agent`, `owlrl`, `pathlib`, `pyshacl`, `rdflib`, `rdflib.collection`, `rdflib.compare`, `re`

## src/__init__.py

init   support for the Knowledge Workflow system.

[Source](../../src/__init__.py) · SHA256 `4408de16239bb8b380a08827fc3994d8a79ee91dd8bc46990a977f1cbcb79dd4`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## src/agents/__init__.py

init   support for the Knowledge Workflow system.

[Source](../../src/agents/__init__.py) · SHA256 `4408de16239bb8b380a08827fc3994d8a79ee91dd8bc46990a977f1cbcb79dd4`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## src/agents/base.py

Shared agent mechanics: stable system prompt (prompt + schema), JSON call with one retry, ledger logging, and answers reused per row across runs (RowCache).

[Source](../../src/agents/base.py) · SHA256 `40cb46441a29f1303c0946f5ea9cce74458ddd0bd39d63c8c6013d3002ac9f28`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `parse_json` | 36 | `text: str` | Read the linked implementation and its call-site contract. |
| `load_prompt` | 48 | `name: str` | Prompt text plus its compact JSON schema (if any): the stable, cacheable system prefix. |
| `key` | 64 | `value` | A model-supplied id as a plain string. Models sometimes return ["k3"] or 3 instead of "k3". |
| `targets` | 75 | `value` | One or many model-supplied ids as a list of strings. |
| `_hidden_rows` | 80 | `obj, value_key: str \| None` | Answer rows anywhere inside a copy of the JSON schema: lists of dicts that carry an id (and value_key). |
| `_hidden_rows.walk` | 84 | `x` | Read the linked implementation and its call-site contract. |
| `items` | 105 | `obj, field: str, value_key: str \| None=None` | The dict entries of obj[field], ignoring anything malformed. Small models often answer in another shape; with value_key these are read too:   {"k1": "quality", ...} or {field: {"k1": "quality"}}  -> [{"id": "k1", value_key: "quality"}]   {"k1": {...}, ...}                                  -> [{"id": "k1", ...}]   {"<other name>": [{...}]} (a single list under another key) -> that list |
| `_rows` | 120 | `obj: dict, field: str, value_key: str \| None` | Read the linked implementation and its call-site contract. |
| `compact` | 138 | `obj` | Read the linked implementation and its call-site contract. |
| `RowCache.__init__` | 158 | `self, agent: 'Agent', system: str, field: str, value_key` | Read the linked implementation and its call-site contract. |
| `RowCache._swap` | 178 | `obj, whole, part, table: dict` | obj with ids or tokens swapped through table: a string that is one (whole) or holds them in the sibling and relation forms (part). None when one has no entry. |
| `RowCache._swap.sub` | 183 | `m` | Read the linked implementation and its call-site contract. |
| `RowCache._swap.walk` | 189 | `x` | Read the linked implementation and its call-site contract. |
| `RowCache._tokens` | 208 | `self, obj` | Read the linked implementation and its call-site contract. |
| `RowCache._ids` | 211 | `self, obj` | Read the linked implementation and its call-site contract. |
| `RowCache.key` | 214 | `self, row: dict` | Read the linked implementation and its call-site contract. |
| `RowCache.get` | 219 | `self, key: str \| None` | Read the linked implementation and its call-site contract. |
| `RowCache.put` | 230 | `self, key: str \| None, answer: dict` | Read the linked implementation and its call-site contract. |
| `RowCache.close` | 236 | `self` | Read the linked implementation and its call-site contract. |
| `Agent.__init__` | 243 | `self, ledger: Ledger` | Read the linked implementation and its call-site contract. |
| `Agent.doubt` | 256 | `self, kind: str, **item` | Record one uncertain or dropped item (kind names why) for ontology/uncertain.json. |
| `Agent.call` | 261 | `self, user: str, item: str, system: str \| None=None, label: str \| None=None, soft: bool=False, cache_valid=None` | One JSON call with one retry. soft=True returns {} on failure (the pass is skipped, the run goes on). |
| `Agent.call_rows` | 319 | `self, rows: list[dict], system: str, item: str, field: str, value_key: str \| None=None, size: int=25, label: str \| None=None, stat: str \| None=None, retries: int=1` | Rows in batches; rows the model left out are sent again, up to retries times, each time in batches half the size of the last (at least 5). Returns one answer entry per answered row id; coverage counts accumulate in self.row_stats[stat or item] (recovered: by any retry; recovered_retryN: by retry N >= 2; reused: answered from an earlier run with the identical row, see RowCache). value_key may be a tuple of fields that must all be present. |
| `Agent.call_rows.keep` | 344 | `k: str, a: dict, source: str` | Read the linked implementation and its call-site contract. |
| `Agent.call_rows.send` | 354 | `todo, n, tag` | Read the linked implementation and its call-site contract. |
| `Agent.call_rows.send.batch` | 356 | `i` | Read the linked implementation and its call-site contract. |
| `Agent.call_rows.send.batch.valid` | 360 | `a` | Read the linked implementation and its call-site contract. |
| `Agent.call_rows.send.batch.complete` | 363 | `out` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `dataclasses`, `hashlib`, `json`, `re`, `sqlite3`, `src`, `src.config`, `src.tools`, `src.tools.ledger`, `src.tools.progress`, `threading`, `time`

## src/agents/enrichment.py

Enrichment agent: definitions, synonyms, restrictions, disjointness, local property domain/range, and the external candidate terms for interop, all from the ontology store (src/tools/ontostore.py) plus the MDS-Onto portal and MatPortal searches.

[Source](../../src/agents/enrichment.py) · SHA256 `00cf839da23b30b0eb080dfc650b6a1757c510481af653a94e513206bb856cd5`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_public` | 47 | `iri: str` | A term IRI others can resolve: http(s) on a public host (portals also return private-network IRIs). |
| `_same_term` | 55 | `r: dict` | A portal hit from an ontology in the store but under another IRI (e.g. an older CCO release): the store's term of that ontology with the same label. |
| `_portal_fetch` | 64 | `search, onts, folder: str, query: str, exact: bool` | Cache successful searches; empty results expire after one day. Exceptions are never cached. |
| `EnrichmentAgent.run` | 85 | `self, classes: list[dict], relations: list[dict], causal: list[dict]` | Read the linked implementation and its call-site contract. |
| `EnrichmentAgent._prop_line` | 192 | `x: dict` | A property candidate as shown to the model: P:<ONTOLOGY>:<label> (domain; range) - definition. |
| `EnrichmentAgent._rkey` | 199 | `cid: str, r: dict` | Read the linked implementation and its call-site contract. |
| `EnrichmentAgent._property_candidates` | 202 | `self, by_id: dict, rels: dict` | Object-property candidates per extracted relation from the store: the predicate phrase (exact and trigram) and the embedding of phrase plus quote, kept only when the property's domain and range fit the two classes. |
| `EnrichmentAgent._candidates` | 229 | `self, live: list[dict]` | Mapping candidates per class: 1. the ontology store, over every ontology in it: label, synonyms and lexical head (exact and trigram)    and the class's embedding (label + first source definition); 2. the MDS-Onto portal and MatPortal searches over every ontology each portal hosts, with cleaned    queries (exact label, full label, general term, spelled-out synonym of an abbreviation); a hit for a    term in the store (also under another IRI of the same ontology, matched by label) joins the pool with    the store's record, flagged with the portal(s) that found it; a hit outside the store (public IRI only)    is a candidate too, scored on its label, up to portal_per_class per class; 3. ranked label matches first, then score: the store's best candidates_per_class, then the portal-only    ones; then terms one and two mapping hops away from a label-matched or strong store candidate, with    confidence decaying per hop and the path recorded. |
| `EnrichmentAgent._candidates.fetch` | 246 | `portal: str, search, onts, folder: str, query: str, exact: bool` | Read the linked implementation and its call-site contract. |
| `EnrichmentAgent._candidates.queries` | 255 | `c: dict` | Read the linked implementation and its call-site contract. |
| `EnrichmentAgent._candidates.from_store` | 280 | `t: dict, source: str, **extra` | Read the linked implementation and its call-site contract. |
| `EnrichmentAgent._materials` | 366 | `self, live: list[dict], by_id: dict` | Materials Project entries (src/tools/materials_project.py) for material-entity classes whose label or a synonym names a crystalline material: up to per_class entries, most stable first, kept on the class as `materials_project` for the OWL annotations. Every lookup is recorded in self.materials_log. |
| `EnrichmentAgent._materials.fetch` | 386 | `k: tuple` | Read the linked implementation and its call-site contract. |
| `EnrichmentAgent._causal` | 420 | `cls, by_id: dict, causal: list[dict]` | Read the linked implementation and its call-site contract. |
| `EnrichmentAgent._standard_causal` | 433 | `cls, c: dict, o: dict, polarity: str, by_id: dict` | First fitting RO and CCO causal property for this cause/effect pair; RO fallback if no RO rule fits. |
| `EnrichmentAgent._standard_causal.is_a` | 437 | `cid, category` | Read the linked implementation and its call-site contract. |
| `EnrichmentAgent._apply` | 451 | `self, out: dict, by_id: dict, rels: dict, value_key: str \| None=None` | Read the linked implementation and its call-site contract. |
| `EnrichmentAgent._predicate_restrictions` | 501 | `self, by_id: dict, rels: dict` | A relation with verified evidence becomes a restriction without a model call when the store settles the property: one fitting candidate carries the predicate's name exactly, or the top candidates tie (within tie_margin) and RELATION_GROUPS names one of them. Several exact names are also a tie for RELATION_GROUPS. Those relations leave rels; the rest go to the model with their candidates. |
| `EnrichmentAgent._store_choice` | 523 | `self, cid: str, r: dict, by_id: dict` | Read the linked implementation and its call-site contract. |
| `EnrichmentAgent._answer_property` | 537 | `self, cid: str, rel: dict, answer: str` | The IRI of the candidate the model named for this relation ("ONTOLOGY:label" or just the label). |
| `EnrichmentAgent._fits` | 545 | `p_iri: str, c: dict, o: dict, by_id: dict` | BFO/CCO compliance: subject and target must fall under the property's declared domain and range. |
| `EnrichmentAgent._local_properties` | 555 | `live: list[dict], by_id: dict` | Read the linked implementation and its call-site contract. |
| `_lca` | 570 | `ids: list[str], by_id: dict` | Most specific common ancestor (local or upper); None when it is only BFO entity. |
| `_evidenced` | 579 | `r: dict` | A joined relation with at least one usable quote (older runs carry no evidence status). |

Imports: `collections`, `concurrent.futures`, `hashlib`, `json`, `re`, `src.agents.base`, `src.config`, `src.tools`, `src.tools.owl`, `src.tools.progress`, `time`, `urllib.parse`

## src/agents/extraction.py

Extraction agent: one paper -> concepts, relations, causal edges, measurements, figure links.

[Source](../../src/agents/extraction.py) · SHA256 `8134c5f4ea508317b6009110f03a103f6f558688e74c72cf7ea540a876f0c82b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_key` | 42 | `label: str` | Read the linked implementation and its call-site contract. |
| `_type` | 46 | `value` | Map a free-text type onto the schema enum: the last enum word in a short answer ("process parameter" -> parameter), else blank. |
| `_words` | 54 | `text: str` | Read the linked implementation and its call-site contract. |
| `_clean_label` | 58 | `label: str` | 'n1 (Auger recombination)' or 'n1: Auger recombination' -> 'Auger recombination' (a leaked id prefix). |
| `ExtractionAgent.__init__` | 68 | `self, ledger` | Read the linked implementation and its call-site contract. |
| `ExtractionAgent.run` | 81 | `self, paper: dict` | Read the linked implementation and its call-site contract. |
| `ExtractionAgent._multi_pass` | 121 | `self, chunk: str, known_text: str, known: list[dict], where: str, item: str, raw_calls: list` | Local tier: concepts first, then each other pass against the numbered concept list. |
| `ExtractionAgent._fill_evidence` | 167 | `self, chunk: str, out: dict, kinds: tuple, labels: dict, item: str, where: str, raw_calls: list` | Items returned without a usable quote get one more call that asks only for their quotes. |
| `ExtractionAgent._chunks` | 196 | `self, paper: dict` | Pack adjacent short sections; keep long sections separate and split them without dropping text. |
| `ExtractionAgent._merge` | 237 | `parts: list[dict]` | Merge section answers into one paper graph. Relation/causal/measurement ends are resolved by concept id, or - since small models often write the phrase instead of the id - by label or synonym, by the longest known concept named inside the phrase, or (short phrases only) as a new concept taken from the text. |
| `ExtractionAgent._merge.add` | 247 | `label: str, ctype: str='', definition: str='', synonyms=(), figures=()` | Read the linked implementation and its call-site contract. |
| `ExtractionAgent._merge.names` | 261 | `` | Read the linked implementation and its call-site contract. |
| `ExtractionAgent._merge.resolve` | 269 | `ref, local: dict, kind: str` | Read the linked implementation and its call-site contract. |
| `ExtractionAgent._finalize` | 335 | `x: dict, paper: dict` | Read the linked implementation and its call-site contract. |
| `_dedupe` | 373 | `rows: list[dict], keys: tuple` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `hashlib`, `json`, `re`, `src.agents.base`, `src.config`, `src.tools`, `src.tools.llm`, `src.tools.pdf_parse`, `src.tools.progress`, `unicodedata`

## src/agents/integration.py

Integration agent: mappings between the domain ontologies of separate runs (the cross-domain stage).

[Source](../../src/agents/integration.py) · SHA256 `f0f091236479dca379444da3a1eb2e031a6b202ae429f0c94764fa12ba214e96`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_Clusters.__init__` | 30 | `self` | Read the linked implementation and its call-site contract. |
| `_Clusters.find` | 33 | `self, x` | Read the linked implementation and its call-site contract. |
| `_Clusters.joins_same_domain` | 41 | `self, a, b, domain_of` | Read the linked implementation and its call-site contract. |
| `_Clusters.union` | 45 | `self, a, b` | Read the linked implementation and its call-site contract. |
| `_names` | 52 | `c: dict` | Read the linked implementation and its call-site contract. |
| `IntegrationAgent.__init__` | 59 | `self, ledger` | Read the linked implementation and its call-site contract. |
| `IntegrationAgent.run` | 63 | `self, domains: dict[str, list[dict]]` | domains: domain name -> live classes (iri, label, alt_labels, category, parent_label, definition, ...). |
| `IntegrationAgent._candidates` | 73 | `self, domains: dict[str, list[dict]]` | Read the linked implementation and its call-site contract. |
| `IntegrationAgent._candidates.add` | 76 | `a, b, kind, score=None` | Read the linked implementation and its call-site contract. |
| `IntegrationAgent._embedding_candidates` | 107 | `self, domains, add` | Read the linked implementation and its call-site contract. |
| `IntegrationAgent._similarity` | 136 | `self, a, b` | Read the linked implementation and its call-site contract. |
| `IntegrationAgent._decide` | 142 | `self, pairs: list[dict]` | Read the linked implementation and its call-site contract. |
| `IntegrationAgent._mapping` | 200 | `p, relation, source, confidence` | Read the linked implementation and its call-site contract. |
| `IntegrationAgent._guard_equivalence` | 207 | `self, mappings` | Equivalence is transitive: an equivalence cluster must never contain two classes of the same domain. |
| `IntegrationAgent._clusters` | 221 | `self, mappings` | Bridge concepts: connected components of equivalent / exact / shared-IRI mappings. |

Imports: `collections`, `itertools`, `numpy`, `re`, `src.agents.base`, `src.config`, `src.tools`, `src.tools.lexical`, `src.tools.progress`

## src/agents/interoperability.py

Interoperability agent: commit mappings from classes to external terms (ontology store and MDS-Onto portal candidates), import definitions of matched terms, then assemble, validate (structurally, no reasoner) and emit the ontology as OWL2 JSON-LD and Turtle.

[Source](../../src/agents/interoperability.py) · SHA256 `b37289ee535474ba2013123b06b3a775f97227dd9beb09441ca9cd93fa5c12cc`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `InteroperabilityAgent.__init__` | 34 | `self, ledger` | Read the linked implementation and its call-site contract. |
| `InteroperabilityAgent.align` | 38 | `self, classes: list[dict]` | Read the linked implementation and its call-site contract. |
| `InteroperabilityAgent.align.ask` | 71 | `i` | Read the linked implementation and its call-site contract. |
| `InteroperabilityAgent._commit` | 103 | `self, c: dict, cand: dict, rel: str, method: str, by_id: dict, mappings: list, seen: set` | Checks one chosen mapping against the store and BFO categories, then records it. |
| `InteroperabilityAgent.import_definitions` | 138 | `self, classes: list[dict], mappings: list[dict]` | A class without a paper-supported definition takes the definition of its exact or equivalent match (equivalent first, then confidence), with status imported and the term's IRI as source. |
| `InteroperabilityAgent.mapping_issues` | 159 | `self, graph, classes: list[dict], mappings: list[dict]` | Checks the structural validator cannot make: mapped store IRIs exist and are not deprecated, terms outside the store carry SKOS only; owl:sameAs only between individuals; no subclass or equivalence into another BFO category. |
| `InteroperabilityAgent.tag_facets` | 181 | `self, classes: list[dict], properties: dict, mappings: list[dict]` | MDS-Onto study stage(s) and MDSDom domain/subdomain for every class and local property. MDS-Onto's own facets on matched terms are passed as hints; invalid names are dropped; anything left untagged gets a stage from its concept type and the General domain. |
| `InteroperabilityAgent.run` | 243 | `self, classes: list[dict], properties: dict, papers: list[dict], run_id: str, domain: str` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `src.agents.base`, `src.config`, `src.tools`, `src.tools.owl`, `src.tools.progress`

## src/agents/normalization.py

Normalization agent: per-paper concepts -> canonical corpus concepts, importance scores, causal order.

[Source](../../src/agents/normalization.py) · SHA256 `94dde492a9bc14b9ca19b100f2960778aadbb3bd585dc7ff441e29e2e9a3e8fd`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `norm_key` | 23 | `label: str` | Read the linked implementation and its call-site contract. |
| `_UnionFind.__init__` | 36 | `self` | Read the linked implementation and its call-site contract. |
| `_UnionFind.find` | 39 | `self, x` | Read the linked implementation and its call-site contract. |
| `_UnionFind.union` | 46 | `self, a, b` | Read the linked implementation and its call-site contract. |
| `NormalizationAgent.run` | 56 | `self, papers: list[dict]` | Read the linked implementation and its call-site contract. |
| `NormalizationAgent._lexical_groups` | 98 | `papers: list[dict]` | Read the linked implementation and its call-site contract. |
| `NormalizationAgent._semantic_merge` | 110 | `self, groups: list[dict]` | Read the linked implementation and its call-site contract. |
| `NormalizationAgent._semantic_merge.term` | 139 | `i` | Read the linked implementation and its call-site contract. |
| `NormalizationAgent._canonical` | 177 | `groups: list[dict]` | Read the linked implementation and its call-site contract. |
| `NormalizationAgent._lineage` | 219 | `papers: list[dict], concepts: list[dict], cmap: dict` | Persist the exact map already used for relations; never infer it from labels. |
| `NormalizationAgent._settle_types` | 238 | `self, concepts: list[dict]` | One narrow call for concepts the papers typed differently (the rest keep their single type). |
| `NormalizationAgent._summarize` | 257 | `self, concepts: list[dict], causal: list[dict], order: dict, n_papers: int` | Read the linked implementation and its call-site contract. |
| `_text` | 269 | `v` | Model-supplied field as a plain string (small models sometimes return a dict or list for one). |
| `_polarity` | 278 | `v` | Read the linked implementation and its call-site contract. |
| `_clean_concept` | 283 | `c: dict` | Read the linked implementation and its call-site contract. |
| `_aggregate` | 291 | `papers, cmap, field, keys, ends` | Read the linked implementation and its call-site contract. |
| `_contradictions` | 320 | `causal: list[dict]` | Same cause and effect reported with opposite polarity (by different papers or conditions). Nothing is merged or dropped; the conditions usually explain the disagreement. |
| `_pagerank` | 336 | `nodes, edges, d=0.85, iters=50` | Read the linked implementation and its call-site contract. |
| `_score` | 353 | `concepts, relations, causal` | Read the linked implementation and its call-site contract. |
| `_scc` | 371 | `nodes, succ` | Tarjan's strongly connected components (iterative). |
| `_causal_order` | 409 | `concepts, causal` | Causal rank = longest cause->effect path depth after collapsing cycles; chains = deepest paths. |

Imports: `collections`, `math`, `numpy`, `re`, `src.agents.base`, `src.config`, `src.tools`, `src.tools.progress`

## src/agents/ontology.py

Ontology agent: place canonical concepts under CCO/BFO classes from the ontology store (or a same-name MDS-Onto or PMDCO class), or under each other, and assign IRIs.

[Source](../../src/agents/ontology.py) · SHA256 `31ea5802a0956a71560627a4e3755745ba06bc9d5daa18eef229f818108b27b8`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `answer_texts` | 36 | `answer: str` | Readings of a free-form parent answer, most literal first. Small models write 'U:Material Artifact - <def>', 'UMaterial Artifact', 'Material Artifact (or U:material entity)', 'u:k38' or 'molecular_entity'. |
| `answer_texts.add` | 41 | `t: str` | Read the linked implementation and its call-site contract. |
| `_text` | 58 | `c: dict` | A concept as embedded for retrieval: label and the start of its first source definition. |
| `slug` | 63 | `label: str` | Read the linked implementation and its call-site contract. |
| `OntologyAgent.run` | 71 | `self, concepts: list[dict], relations: list[dict], domain: str` | Read the linked implementation and its call-site contract. |
| `OntologyAgent._name_matches` | 140 | `self, concepts: list[dict], menu_lc: dict` | A concept whose label names an MDS-Onto or PMDCO class (any of its labels, normalised) is placed under that class alone; its route to CCO/BFO is that ontology's own. Used only when the route reaches BFO. |
| `OntologyAgent._root` | 162 | `self, iri: str` | The BFO category root (of CATEGORIES) above an external class. |
| `OntologyAgent._candidates` | 167 | `self, concepts: list[dict], menu_lc: dict, cats: dict \| None=None` | Parent candidates per concept from the ontology store: CCO classes first, then BFO, found by label, synonyms and lexical head (exact and trigram) and by embedding; then the type default and, on the local tier, the root of the concept's BFO category. With cats, only candidates inside that category. |
| `OntologyAgent._nearest_corpus` | 191 | `self, members: list[dict]` | Per concept: the NEAREST_CORPUS other concepts of its category closest by embedding of label: definition. Empty without an EMBED model or when embedding fails (the pass then lists the top concepts for every row). |
| `OntologyAgent._resolve` | 205 | `self, cid: str, answer, root: str \| None=None` | A model answer as a parent, and how it was read: a corpus id ('corpus'), one of the concept's candidates ('candidate'), a BFO category root ('root'), a CCO/BFO store class named exactly that, inside the category when one is given ('store_label'), or a close misspelling of a candidate or root ('fuzzy'). Otherwise (None, 'unresolved'); no answer at all is (None, 'no_answer'). |
| `OntologyAgent._parent` | 233 | `self, cid: str, answer, root: str \| None=None, category: str \| None=None` | _resolve, counted in stats parent_answers; unresolved answers are kept for review. |
| `OntologyAgent._pick_combined` | 242 | `self, concepts: list[dict], menu_lc: dict, rows_of` | Frontier tier: one call per batch chooses the parent (a candidate, a BFO category or a corpus concept) and exclusion. |
| `OntologyAgent._pick_split` | 258 | `self, concepts: list[dict], menu_lc: dict, rows_of` | Local tier: pass 1 picks a BFO category (or 'not a class'); pass 2 picks the parent from that concept's store candidates inside the category and the corpus concepts in it. Pass 2 may override a wrong category with another root. |
| `OntologyAgent._default` | 313 | `c: dict, menu_lc: dict` | Read the linked implementation and its call-site contract. |
| `OntologyAgent._lexical_heads` | 318 | `classes: list[dict]` | Where the model attached a concept straight to BFO/CCO, nest it under its obvious lexical head instead - only if the head is kept, falls in the same BFO category, and no cycle results. |
| `OntologyAgent._repair` | 334 | `self, classes: list[dict], menu_lc: dict` | Break is-a cycles, then route children of excluded concepts to the nearest kept ancestor. |

Imports: `collections`, `hashlib`, `numpy`, `re`, `src.agents.base`, `src.config`, `src.tools`, `src.tools.owl`, `src.tools.progress`, `urllib.parse`

## src/config.py

Pipeline settings. API keys live in .env; everything else is set here.

[Source](../../src/config.py) · SHA256 `dce9762b389203809823d8c1209eaa9a9fb22b5487ba5d9856dde49d1542fd32`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `profile_for` | 66 | `agent: str \| None=None` | Read the linked implementation and its call-site contract. |
| `tier` | 82 | `agent: str \| None=None` | Read the linked implementation and its call-site contract. |
| `domain_of` | 246 | `collection: dict` | The field a collection's papers come from, as the prompts name it. |
| `secret` | 379 | `name: str \| None` | Read an API key from .env (blank counts as unset). |
| `model_for` | 384 | `agent: str` | Read the linked implementation and its call-site contract. |

Imports: `dotenv`, `os`, `pathlib`

## src/figures.py

Paper figures from the evaluation tables and run folders.

[Source](../../src/figures.py) · SHA256 `11434e454bdcbf071484394b29592208e07db949b711b1fef8186f4e2abbeba5`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_csv` | 56 | `path: Path` | Read the linked implementation and its call-site contract. |
| `_json` | 63 | `path: Path` | Read the linked implementation and its call-site contract. |
| `num` | 70 | `v, default=0.0` | Read the linked implementation and its call-site contract. |
| `_metric` | 77 | `value` | Missing/unsupported hardware counters stay unavailable rather than becoming zero. |
| `gpu_statistics` | 86 | `folder: Path \| None` | Integrate board power/utilization per GPU and submission, with explicit coverage. |
| `run_context` | 179 | `outputs: Path, rows: list[dict], run_ids, statuses=(), sweep_folder: Path \| None=None` | Read saved setup and model-request tokens, including listed failed attempts. |
| `label` | 242 | `domain: str` | Read the linked implementation and its call-site contract. |
| `load_runs` | 246 | `outputs: Path, revision: str, profile: str \| None, run_ids: list[str] \| None` | Read the linked implementation and its call-site contract. |
| `load_integrations` | 270 | `outputs: Path, selected_ids, integration_ids=None` | Only integrations whose nonempty input set is fully represented in this report. |
| `largest` | 283 | `rows: list[dict], needs: str` | Per domain, the run with the most papers that has the given artifact. |
| `paper_order` | 297 | `run_dir: Path` | Processed papers in selection order (citation rank). |
| `cumulative` | 305 | `order: list[str], first_papers: list[set]` | Distinct items seen after each paper: an item counts from its earliest paper in this order. |
| `Out.__init__` | 315 | `self, folder: Path` | Read the linked implementation and its call-site contract. |
| `Out.save` | 319 | `self, fig, name: str, title: str, source: str, table: list[dict]` | Read the linked implementation and its call-site contract. |
| `Out.skip` | 332 | `self, name: str, why: str` | Read the linked implementation and its call-site contract. |
| `direct_labels` | 337 | `ax, ends: list[tuple[float, float, str, str]]` | Labels at line ends, nudged apart vertically so they do not collide. |
| `stacked_barh` | 351 | `ax, labels: list[str], series: list[tuple[str, str, list[float]]], share: bool, frame=None` | Horizontal stacked bars with a 2px white gap between segments; optional outlined 100% frame. |
| `fig_concept_growth` | 375 | `out: Out, rows: list[dict], permutations: int=200` | Read the linked implementation and its call-site contract. |
| `fig_knowledge_growth` | 410 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_scaling` | 449 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_per_paper_yield` | 487 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_evidence` | 517 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_row_coverage` | 545 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `_domain_shares` | 573 | `out, rows, name, title, source, cols, prefix, total_col=None, frame=False, colors=None` | Read the linked implementation and its call-site contract. |
| `fig_placement` | 594 | `out, rows` | Read the linked implementation and its call-site contract. |
| `fig_definitions` | 602 | `out, rows` | Read the linked implementation and its call-site contract. |
| `fig_restrictions` | 611 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_mappings` | 638 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_compute` | 669 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_integration` | 693 | `out: Out, outputs: Path, rows_runs: list[dict], revision: str, run_ids` | Read the linked implementation and its call-site contract. |
| `grouped_barh` | 778 | `ax, cats: list[str], runs: dict, values: dict, fmt=None` | One bar per domain inside each category group; colour follows the domain. |
| `top_categories` | 794 | `counts: dict[str, Counter], k: int=7` | Read the linked implementation and its call-site contract. |
| `fold` | 802 | `c: Counter, keep: list[str]` | Read the linked implementation and its call-site contract. |
| `share_figure` | 809 | `out, name, title, source, counts: dict[str, Counter], legend_cols=4, k=7` | Stacked share bars per domain over the k most common categories (rest folded into Other). |
| `fig_parsing` | 824 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_extraction_checks` | 860 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_normalization` | 882 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_concept_support` | 907 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_concept_types` | 934 | `out, rows` | Read the linked implementation and its call-site contract. |
| `fig_causal_polarity` | 941 | `out, rows` | Read the linked implementation and its call-site contract. |
| `heatmap` | 948 | `ax, rows_labels, cols_labels, m, fmt='{:.0%}'` | Read the linked implementation and its call-site contract. |
| `fig_relation_predicates` | 963 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `_classes` | 979 | `r` | Read the linked implementation and its call-site contract. |
| `fig_bfo_categories` | 984 | `out, rows` | Read the linked implementation and its call-site contract. |
| `fig_hierarchy` | 995 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_review_flags` | 1036 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_study_stages` | 1056 | `out, rows` | Read the linked implementation and its call-site contract. |
| `fig_mapping_targets` | 1066 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_layer_vs_ontology` | 1083 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `columns` | 1117 | `r: dict, prefix: str, skip=()` | Counter of the numeric columns that start with prefix (suffix -> value). |
| `ontology_series` | 1123 | `counts: dict[str, Counter]` | Share series per ontology with a fixed colour per ontology (case-insensitive), rest as Other. |
| `fig_store_candidates` | 1135 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_store_sources` | 1161 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_store_propagation` | 1193 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_store_imports` | 1216 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_mapping_methods` | 1242 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_parent_answers` | 1275 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_uncertain` | 1284 | `out: Out, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `fig_integration_series` | 1310 | `out: Out, outputs: Path, revision: str, run_ids` | Read the linked implementation and its call-site contract. |
| `build` | 1363 | `outputs: Path \| None=None, revision: str=config.WORKFLOW_REVISION, profile: str \| None=None, run_ids: list[str] \| None=None, out_dir: Path \| None=None, title: str \| None=None, sweep_summary: Path \| None=None` | Every figure (PDF, PNG, CSV), index.md, sweep_summary.csv and the grouped report (report.md, report.html). One failing figure is listed as skipped; it never stops the others. |
| `main` | 1410 | `` | Read the linked implementation and its call-site contract. |

Imports: `argparse`, `collections`, `csv`, `json`, `math`, `matplotlib`, `matplotlib.pyplot`, `numpy`, `pathlib`, `random`, `src`, `src.tools`, `src.tools.reports`

## src/report.py

One report with every figure, grouped by pipeline stage, each with a short paragraph computed from the numbers it plots; plus saved setup, resource totals and sweep summary (one row per run/integration). Written by src.figures.build:

[Source](../../src/report.py) · SHA256 `3b30b089b9df3d410e61b49b357a8f1173a67db3322d29f777ea18c85e725149`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `n` | 129 | `x` | Read the linked implementation and its call-site contract. |
| `pc` | 134 | `a, b=1.0` | Read the linked implementation and its call-site contract. |
| `L` | 139 | `d` | Read the linked implementation and its call-site contract. |
| `by_domain` | 143 | `t: list[dict]` | Read the linked implementation and its call-site contract. |
| `counts` | 151 | `r: dict, skip=('domain', 'run_id', 'total', 'classes', 'papers', 'concepts')` | Read the linked implementation and its call-site contract. |
| `top` | 155 | `r: dict, k: int=2, skip=('domain', 'run_id', 'total', 'classes')` | Read the linked implementation and its call-site contract. |
| `each` | 161 | `t, fn` | Read the linked implementation and its call-site contract. |
| `_growth` | 167 | `t` | Read the linked implementation and its call-site contract. |
| `_growth.one` | 170 | `d, rs` | Read the linked implementation and its call-site contract. |
| `_knowledge` | 180 | `t` | Read the linked implementation and its call-site contract. |
| `_scaling` | 194 | `t` | Read the linked implementation and its call-site contract. |
| `_scaling.one` | 195 | `d, rs` | Read the linked implementation and its call-site contract. |
| `_yield` | 208 | `t` | Read the linked implementation and its call-site contract. |
| `_yield.one` | 211 | `d, rs` | Read the linked implementation and its call-site contract. |
| `_parsing` | 220 | `t` | Read the linked implementation and its call-site contract. |
| `_parsing.one` | 221 | `d, rs` | Read the linked implementation and its call-site contract. |
| `_checks` | 229 | `t` | Read the linked implementation and its call-site contract. |
| `_checks.one` | 230 | `r` | Read the linked implementation and its call-site contract. |
| `_evidence` | 237 | `t` | Read the linked implementation and its call-site contract. |
| `_evidence.one` | 238 | `d, rs` | Read the linked implementation and its call-site contract. |
| `_normalization` | 247 | `t` | Read the linked implementation and its call-site contract. |
| `_normalization.one` | 248 | `r` | Read the linked implementation and its call-site contract. |
| `_support` | 256 | `t` | Read the linked implementation and its call-site contract. |
| `_support.one` | 257 | `r` | Read the linked implementation and its call-site contract. |
| `_shares` | 264 | `t, what='categories'` | Read the linked implementation and its call-site contract. |
| `_hierarchy` | 268 | `t` | Read the linked implementation and its call-site contract. |
| `_placement` | 275 | `t` | Read the linked implementation and its call-site contract. |
| `_placement.one` | 276 | `r` | Read the linked implementation and its call-site contract. |
| `_parent_answers` | 286 | `t` | Read the linked implementation and its call-site contract. |
| `_parent_answers.one` | 287 | `r` | Read the linked implementation and its call-site contract. |
| `_flags` | 297 | `t` | Read the linked implementation and its call-site contract. |
| `_coverage` | 302 | `t` | Read the linked implementation and its call-site contract. |
| `_definitions` | 311 | `t` | Read the linked implementation and its call-site contract. |
| `_definitions.one` | 312 | `r` | Read the linked implementation and its call-site contract. |
| `_restrictions` | 320 | `t` | Read the linked implementation and its call-site contract. |
| `_restrictions.one` | 321 | `r` | Read the linked implementation and its call-site contract. |
| `_layer` | 329 | `t` | Read the linked implementation and its call-site contract. |
| `_layer.one` | 330 | `r` | Read the linked implementation and its call-site contract. |
| `_mappings` | 339 | `t` | Read the linked implementation and its call-site contract. |
| `_mappings.one` | 340 | `r` | Read the linked implementation and its call-site contract. |
| `_methods` | 347 | `t` | Read the linked implementation and its call-site contract. |
| `_methods.one` | 348 | `r` | Read the linked implementation and its call-site contract. |
| `_store_candidates` | 357 | `t` | Read the linked implementation and its call-site contract. |
| `_store_candidates.one` | 358 | `r` | Read the linked implementation and its call-site contract. |
| `_store_sources` | 367 | `t` | Read the linked implementation and its call-site contract. |
| `_store_sources.one` | 368 | `r` | Read the linked implementation and its call-site contract. |
| `_propagation` | 379 | `t` | Read the linked implementation and its call-site contract. |
| `_propagation.one` | 380 | `r` | Read the linked implementation and its call-site contract. |
| `_imports` | 388 | `t` | Read the linked implementation and its call-site contract. |
| `_imports.one` | 389 | `r` | Read the linked implementation and its call-site contract. |
| `_uncertain` | 398 | `t` | Read the linked implementation and its call-site contract. |
| `_uncertain.one` | 399 | `r` | Read the linked implementation and its call-site contract. |
| `_compute` | 406 | `t` | Read the linked implementation and its call-site contract. |
| `_compute.one` | 407 | `r` | Read the linked implementation and its call-site contract. |
| `_integration` | 416 | `t` | Read the linked implementation and its call-site contract. |
| `_integration_series` | 429 | `t` | Read the linked implementation and its call-site contract. |
| `paragraph` | 450 | `name: str, table: list[dict]` | How to read the figure, then what its numbers say. A numbers sentence that fails is left out. |
| `sweep` | 473 | `rows: list[dict], outputs: Path, revision: str, run_ids` | Read the linked implementation and its call-site contract. |
| `_write_csv` | 495 | `path: Path, runs, ints, statuses=()` | Read the linked implementation and its call-site contract. |
| `_cell` | 514 | `k, v` | Read the linked implementation and its call-site contract. |
| `setup_rows` | 524 | `context, revision` | Describe saved execution environments, never the machine rendering an old report. |
| `totals_line` | 575 | `metrics` | A compact total with explicit units and unavailable counters. |
| `totals_line.value` | 577 | `key, suffix, scale=1` | Read the linked implementation and its call-site contract. |
| `sections` | 588 | `out` | Groups with the figures that exist: (group, intro, [(name, heading, title, source, paragraph)]). |
| `write` | 604 | `out, rows: list[dict], outputs: Path, revision: str, run_ids, notes: list[str], title: str \| None=None, statuses=()` | Read the linked implementation and its call-site contract. |

Imports: `base64`, `collections`, `csv`, `datetime`, `html`, `pathlib`, `src`, `statistics`

## src/resources/lora/finetune_colab.ipynb

"cell_type": "markdown",

[Source](../../src/resources/lora/finetune_colab.ipynb) · SHA256 `316d78ad53b1b75ae763abaf0a06dfee703c99f48468c671b43c6f4d5a0dd595`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## src/resources/lora/train_local.py

Train the LoRA adapter on your own GPU (e.g. RTX 5070 Ti, 12 GB) with Unsloth, in WSL2 or Linux.

[Source](../../src/resources/lora/train_local.py) · SHA256 `aacf7ccaf691ec7514322e2de44d623527288bfba42276fdceaa32ca33f80074`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `to_text` | 52 | `example` | Read the linked implementation and its call-site contract. |

Imports: `argparse`, `collections`, `datasets`, `glob`, `json`, `math`, `os`, `pathlib`, `shutil`, `torch`, `trl`, `unsloth`, `unsloth.chat_templates`

## src/run.py

Pipeline entry point with saved settings, invocation environments and compute provenance.

[Source](../../src/run.py) · SHA256 `7d80143417581f228173ce6dd1787185310081084d6605662ce1197caab3a71b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_now` | 56 | `` | Read the linked implementation and its call-site contract. |
| `_git` | 60 | `` | Read the linked implementation and its call-site contract. |
| `_config` | 67 | `` | Run settings for the manifest. Never includes keys. |
| `_environment` | 98 | `` | Bounded, best-effort hardware/serving snapshot. Only named non-secret settings are read. |
| `_environment.integer` | 100 | `name` | Read the linked implementation and its call-site contract. |
| `Run.__init__` | 179 | `self, run_id: str, collection: str` | Read the linked implementation and its call-site contract. |
| `Run.read` | 202 | `self, name: str` | Read the linked implementation and its call-site contract. |
| `Run.write` | 205 | `self, name: str, obj` | Read the linked implementation and its call-site contract. |
| `Run.papers` | 209 | `self` | Read the linked implementation and its call-site contract. |
| `Run.fail` | 212 | `self, stage: str, exc: BaseException` | Keep the error with the run (error.log, run.json "errors") and in the central outputs/errors.csv. |
| `Run.record` | 234 | `self, stage: str, stats: dict, seconds: float` | Read the linked implementation and its call-site contract. |
| `select_papers` | 254 | `coll: dict, top_n: int \| None, limit: int \| None=None` | Rank by citation count and fetch only enough available PDFs for the requested selection. Papers without a DOI or without a count rank last, in Zotero order. |
| `_figures` | 291 | `what: str, **kw` | Figures and the grouped report (src.figures.build); a failure here never fails the run or integration. |
| `_uncertain` | 303 | `run: Run, stage: str, items: list[dict]` | Keep this stage's uncertain items in ontology/uncertain.json; a failure here never fails the run. |
| `extract` | 312 | `run: Run, args` | Read the linked implementation and its call-site contract. |
| `extract.process` | 324 | `entry` | Read the linked implementation and its call-site contract. |
| `normalize` | 373 | `run: Run, args` | Read the linked implementation and its call-site contract. |
| `ontology` | 390 | `run: Run, args` | Read the linked implementation and its call-site contract. |
| `enrich` | 408 | `run: Run, args` | Read the linked implementation and its call-site contract. |
| `interop` | 428 | `run: Run, args` | Read the linked implementation and its call-site contract. |
| `_require` | 460 | `ok, message: str` | Read the linked implementation and its call-site contract. |
| `check` | 465 | `args` | Preflight for one collection. Also downloads the collection's PDFs into the cache. |
| `check.keys` | 471 | `` | Read the linked implementation and its call-site contract. |
| `check.model` | 479 | `` | Read the linked implementation and its call-site contract. |
| `check.embeddings` | 484 | `` | Read the linked implementation and its call-site contract. |
| `check.corpus` | 490 | `` | Read the linked implementation and its call-site contract. |
| `check.parser` | 501 | `` | Read the linked implementation and its call-site contract. |
| `check.portal` | 508 | `` | Read the linked implementation and its call-site contract. |
| `check.matportal_check` | 518 | `` | Read the linked implementation and its call-site contract. |
| `check.store` | 528 | `` | Read the linked implementation and its call-site contract. |
| `collections` | 548 | `args` | Read the linked implementation and its call-site contract. |
| `lora_data` | 554 | `args` | Read the linked implementation and its call-site contract. |
| `lora_eval` | 559 | `args` | Read the linked implementation and its call-site contract. |
| `portal` | 564 | `args` | Read the linked implementation and its call-site contract. |
| `ontologies` | 574 | `args` | build: download missing ontology files, load them into Oxigraph, index labels, embed every term. status: is the store current (files, embedding model, newer MDS-Onto submission). search TEXT: try a query. |
| `integrate` | 592 | `args` | Cross-domain stage: map the domain ontologies of completed runs to each other in one master ontology. Reads the domain runs; never rewrites them. |
| `main` | 664 | `` | Read the linked implementation and its call-site contract. |

Imports: `argparse`, `collections`, `csv`, `ctypes`, `datetime`, `difflib`, `hashlib`, `importlib`, `json`, `openai`, `os`, `pathlib`, `platform`, `shlex`, `src`, `src.agents`, `src.agents.base`, `src.agents.enrichment`, `src.agents.extraction`, `src.agents.integration`, `src.agents.interoperability`, `src.agents.normalization`, `src.agents.ontology`, `src.config`, `src.tools`, `src.tools.ledger`, `src.tools.progress`, `subprocess`, `threading`, `time`, `traceback`

## src/tools/__init__.py

init   support for the Knowledge Workflow system.

[Source](../../src/tools/__init__.py) · SHA256 `4408de16239bb8b380a08827fc3994d8a79ee91dd8bc46990a977f1cbcb79dd4`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## src/tools/bottomup.py

Bottom-up domain layer: the literature's own vocabulary as a SKOS concept scheme, next to the BFO/CCO ontology.

[Source](../../src/tools/bottomup.py) · SHA256 `e6c8ebabee105f8ce18f9b9c8611ea1d2638fdd39ceb8c992eb833bbae39c042`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `build` | 24 | `domain: str, norm: dict, classes: list[dict], papers: list[dict]` | Read the linked implementation and its call-site contract. |
| `build.ancestors` | 80 | `cid` | Read the linked implementation and its call-site contract. |
| `build.claim` | 104 | `s, p, o, r` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `rdflib`, `rdflib.namespace`, `re`, `src.agents.ontology`, `src.tools`, `src.tools.owl`

## src/tools/citations.py

Citation counts per DOI, tried in order: OpenCitations Index (open CC0 data, no key; one DOI per request), then OpenAlex cited_by_count (key optional), then Crossref is-referenced-by-count (no key).

[Source](../../src/tools/citations.py) · SHA256 `1d21ca6434044c9b43173fa3dbba95792bd4c81081834ab096326b86ab615aae`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `norm` | 29 | `doi: str` | Read the linked implementation and its call-site contract. |
| `_get` | 36 | `url: str, params: dict \| None=None, headers: dict \| None=None` | Read the linked implementation and its call-site contract. |
| `_opencitations` | 48 | `dois: list[str]` | Read the linked implementation and its call-site contract. |
| `_openalex` | 62 | `dois: list[str]` | Read the linked implementation and its call-site contract. |
| `_crossref` | 68 | `dois: list[str]` | Read the linked implementation and its call-site contract. |
| `counts` | 78 | `dois: list[str]` | DOI (normalized) -> {"count": int \| None, "source": str \| None, "fetched": ISO date}. |

Imports: `datetime`, `json`, `requests`, `src.config`, `src.tools`, `src.tools.progress`, `time`

## src/tools/concept_quality.py

Quarantine malformed concepts and dependent links while retaining their source records for review.

[Source](../../src/tools/concept_quality.py) · SHA256 `339d72f9373a2c3b5cdf5eb4c70206defad32445c3b69ba2067088577bc6e55b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `label_issues` | 13 | `value` | Read the linked implementation and its call-site contract. |
| `concept_issues` | 27 | `record` | Read the linked implementation and its call-site contract. |
| `bounded` | 45 | `value, limit=160` | Read the linked implementation and its call-site contract. |
| `quarantine` | 51 | `record` | Copy valid outputs; preserve rejected rows and their dependent links for review. |

Imports: `collections`, `re`

## src/tools/files.py

Writes that stay safe when several runs share outputs/ and the cache (e.g. three domains in parallel).

[Source](../../src/tools/files.py) · SHA256 `50ccffa48dff2a2bdc3508da8552936521e1867b41fb7c6ba1af80538e2e031f`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `atomic_write` | 12 | `path: Path, text: str` | Write to a temporary file beside path, then rename: a reader never sees half a file. |
| `locked` | 28 | `path: Path, wait_s: float=120, stale_s: float=300` | Cross-process lock for a read-modify-write of path (a <name>.lock file beside it). A lock older than stale_s is left over from a killed process and is taken over. |

Imports: `contextlib`, `os`, `pathlib`, `time`, `uuid`

## src/tools/gemini_quota.py

Persistent Gemini chat quotas; reservations include every retry attempt.

[Source](../../src/tools/gemini_quota.py) · SHA256 `b450cda2165501a3434436a28aa2d57d3b8d1b6a90a2a8a7769af9d95c5ea370`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `GeminiQuota.__init__` | 25 | `self, path, limits` | Read the linked implementation and its call-site contract. |
| `GeminiQuota.day` | 29 | `self, now` | Read the linked implementation and its call-site contract. |
| `GeminiQuota.reserve` | 32 | `self, model, tokens` | Read the linked implementation and its call-site contract. |
| `GeminiQuota.block_day` | 73 | `self, model` | Read the linked implementation and its call-site contract. |
| `daily_error` | 78 | `error` | Read the linked implementation and its call-site contract. |
| `retry_delay` | 84 | `error, attempt` | Read the linked implementation and its call-site contract. |
| `call` | 100 | `client, model, system, user, options, quota, retries` | Read the linked implementation and its call-site contract. |

Imports: `contextlib`, `datetime`, `email.utils`, `openai`, `re`, `sqlite3`, `src.tools.progress`, `time`, `zoneinfo`

## src/tools/integration.py

Cross-domain integration: input run selection, the master ontology, its validation, report and eval row.

[Source](../../src/tools/integration.py) · SHA256 `6adf9ac43a0102a53190b9d32fedb8676a438518dcb13c84fbe6dd0ca521cfc9`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_manifest` | 31 | `run_dir: Path` | Read the linked implementation and its call-site contract. |
| `select_runs` | 38 | `outputs: Path, collections: list[str] \| None, run_ids: list[str] \| None` | One completed run (interop done, ontology.ttl present) per domain. Returns (selected, notes). |
| `load_domain` | 79 | `s: dict` | Live classes in the shape the integration agent reads, the domain graph and its ontology IRI. |
| `master_name` | 96 | `domains: list[str]` | The master ontology's name: its domains in input order, joined by "_" (domain names may contain "-"). |
| `build_master` | 101 | `selected: list[dict], graphs: dict, mappings: list[dict], integration_id: str` | Read the linked implementation and its call-site contract. |
| `validate` | 154 | `master: rdflib.Graph, master_text: str, graphs: dict, mappings: list[dict]` | Structural checks only (no reasoner). |
| `validate.find` | 171 | `x` | Read the linked implementation and its call-site contract. |
| `validate.cyclic` | 192 | `n` | Read the linked implementation and its call-site contract. |
| `report` | 214 | `path: Path, integration_id: str, selected: list[dict], domains: dict, result: dict, validation: dict, compute: dict, notes: list[str], merged_triples: int` | integration_report.md, and the flat metrics row for outputs/eval_integrations.csv. |
| `merge` | 286 | `master: rdflib.Graph, graphs: dict` | The domain graphs plus the master in one graph, for loading into a single triple store. |
| `public_candidates` | 296 | `pairs: list[dict]` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `datetime`, `json`, `pathlib`, `rdflib`, `rdflib.namespace`, `src`, `src.tools`

## src/tools/ledger.py

Append-only compute ledger: one JSONL row per LLM call (or cache hit), summarized per item or agent.

[Source](../../src/tools/ledger.py) · SHA256 `47f603e03928f105bbb934782baaf9e009fcc50ee565a26eb945e3c8dae41e1f`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `cost` | 17 | `u: Usage` | Read the linked implementation and its call-site contract. |
| `Ledger.__init__` | 27 | `self, path: Path` | Read the linked implementation and its call-site contract. |
| `Ledger.log` | 32 | `self, agent: str, item: str, model: str, usage: Usage, ok=True, attempt=0, cache_hit=False` | Read the linked implementation and its call-site contract. |
| `Ledger.rows` | 38 | `self` | Read the linked implementation and its call-site contract. |
| `Ledger.summary` | 43 | `self, by: str='item'` | Read the linked implementation and its call-site contract. |

Imports: `dataclasses`, `json`, `pathlib`, `src.config`, `src.tools.llm`, `threading`, `time`

## src/tools/lexical.py

Lexical head rule: "rear AlOx passivation layer" sits under "passivation layer" when that is also a concept.

[Source](../../src/tools/lexical.py) · SHA256 `23cfa7a5354012b8193a1411123155a6cb4dac745faba6a9ecb5a67f427bd84f`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `normalize` | 21 | `label: str` | Read the linked implementation and its call-site contract. |
| `validate_search_query` | 25 | `query: str` | Reject oversized external search terms without altering source evidence. |
| `clean_query` | 35 | `label: str` | A portal search query: no parentheses, LaTeX, or hyphen/underscore joins. |
| `match_key` | 41 | `label: str` | Comparable form of a label across ontologies: 'OpenCircuitVoltage' == 'open-circuit voltage (Voc)'. |
| `head_query` | 46 | `label: str` | The general term of a long label ('rear AlOx passivation layer' -> 'passivation layer'). |
| `heads` | 52 | `concepts: list[dict]` | child id -> head concept id, for the longest obvious head of each concept. |
| `_obvious` | 68 | `child: dict, head: dict, modifiers: list[str]` | Read the linked implementation and its call-site contract. |

Imports: `re`, `src.agents.normalization`, `urllib.parse`

## src/tools/llm.py

Provider-agnostic chat call returning (text, usage), with usage normalized across providers.

[Source](../../src/tools/llm.py) · SHA256 `76b4abad288c70fae7dff43e902eb67a04c7ea25a8a9fc3b1815537a3d21a79b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_get_client` | 30 | `profile=None` | Read the linked implementation and its call-site contract. |
| `_outage_safe` | 47 | `profile: dict, request` | A local server (Ollama) that is restarting, reloading the model or briefly gone: after the client's own retries, wait and try again for up to profile['outage_wait_s'] (default 0: fail at once) before giving up. |
| `chat` | 84 | `system: str, user: str, model: str, max_tokens: int=MAX_OUTPUT_TOKENS, profile: dict \| None=None` | One JSON-returning call. The system prompt is the stable, cacheable prefix. |
| `embed` | 121 | `texts: list[str], batch: int=100` | Embeddings from an OpenAI-compatible /embeddings endpoint (OpenAI, Ollama, vLLM, Gemini). Paced to EMBED['inputs_per_minute']; on a quota error it waits the delay the provider asks for. |
| `_embed_uncached` | 170 | `texts: list[str], batch: int` | Provider request for only the texts missing from the persistent embedding cache. |

Imports: `anthropic`, `dataclasses`, `hashlib`, `json`, `math`, `openai`, `re`, `sqlite3`, `src.config`, `src.tools`, `src.tools.progress`, `time`

## src/tools/lora_data.py

Build LoRA training data from a suite of ontologies, in the pipeline's own prompt and JSON formats.

[Source](../../src/tools/lora_data.py) · SHA256 `d845026c3f722304e6be3180770443df88889b3dfd1c17b3a9de68d39e84383b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_owner` | 54 | `iri: str` | Read the linked implementation and its call-site contract. |
| `_text` | 58 | `g, s, props, langs=('en', 'en-us', None)` | Read the linked implementation and its call-site contract. |
| `_all_text` | 67 | `g, s, p` | Read the linked implementation and its call-site contract. |
| `_fetch` | 72 | `name: str, loc: str, folder: Path` | Read the linked implementation and its call-site contract. |
| `load_suite` | 83 | `` | Download (cached) and parse every ontology in LORA['ontologies'] into one graph. |
| `collect_terms` | 104 | `g: rdflib.Graph` | Read the linked implementation and its call-site contract. |
| `_ancestors` | 137 | `iri: str, terms: dict` | Read the linked implementation and its call-site contract. |
| `_split` | 147 | `key: str` | Read the linked implementation and its call-site contract. |
| `_chunks` | 152 | `items: list, size: int` | Read the linked implementation and its call-site contract. |
| `_example` | 156 | `task, key, system, user, answer, meta=None` | Read the linked implementation and its call-site contract. |
| `_category` | 162 | `t: dict` | The local-tier BFO category of a term: the nearest CATEGORIES root among its ancestors. |
| `hierarchy_examples` | 168 | `terms: dict, rng: random.Random, repeat: int` | The ontology agent's two local passes, as the pipeline sends them: category - pick the BFO category of each concept (ontology_category) parent   - pick the parent among that category's upper classes and the corpus concepts in it (ontology_parent) |
| `enrich_examples` | 232 | `terms: dict, rng: random.Random, repeat: int` | The enrichment agent's local passes, as the pipeline sends them: definitions, synonyms (true alt labels among sibling decoys) and disjointness among siblings. Restrictions are the separate restrict task. |
| `restrict_examples` | 286 | `rng: random.Random` | Relations as the restrictions pass sees them ("phrase: target (id) xN"); the answer keeps the ones a menu property formalizes with a fitting domain and range (the first fitting property of the phrase's group) and drops the rest: the same phrase between the wrong kinds of entity, and vague relations to unrelated classes. |
| `restrict_examples.ok` | 297 | `req, iri` | Read the linked implementation and its call-site contract. |
| `restrict_examples.fits` | 300 | `key, need_s, need_o, s, o` | Read the linked implementation and its call-site contract. |
| `restrict_examples.fitting` | 311 | `key, ns, no` | Read the linked implementation and its call-site contract. |
| `align_examples` | 365 | `terms: dict, rng: random.Random` | Read the linked implementation and its call-site contract. |
| `align_examples.lookalikes` | 372 | `t, exclude, k` | Read the linked implementation and its call-site contract. |
| `extract_examples` | 424 | `run_ids: list[str]` | Read the linked implementation and its call-site contract. |
| `build` | 445 | `distill_runs: list[str] \| None=None` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `datetime`, `difflib`, `hashlib`, `json`, `pathlib`, `random`, `rdflib`, `rdflib.namespace`, `re`, `requests`, `src.agents.base`, `src.agents.enrichment`, `src.agents.ontology`, `src.config`, `src.tools`, `src.tools.owl`, `src.tools.progress`, `src.tools.upper`, `zipfile`

## src/tools/lora_eval.py

Score a model (base or fine-tuned, served by the active LLM profile) on the held-out LoRA test split.

[Source](../../src/tools/lora_eval.py) · SHA256 `2381d7a2f0b09e7f02922318b43f8f45e5103be1d8e77698235705391ced5817`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_prf` | 28 | `pred: set, gold: set, acc: dict, name: str` | Read the linked implementation and its call-site contract. |
| `_by_id` | 34 | `obj, key` | Read the linked implementation and its call-site contract. |
| `score` | 38 | `task: str, pred: dict, gold: dict, meta: dict, acc: dict` | Read the linked implementation and its call-site contract. |
| `_summarize` | 123 | `acc: dict` | Read the linked implementation and its call-site contract. |
| `run` | 147 | `model: str, limit: int \| None=None` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `datetime`, `difflib`, `json`, `re`, `src.agents.base`, `src.config`, `src.tools`, `src.tools.lora_data`, `src.tools.progress`, `time`

## src/tools/materials_project.py

Materials Project (materialsproject.org) lookups for enrichment: computed properties of the crystalline material a class names, attached to the class as annotations (never as mapping candidates).

[Source](../../src/tools/materials_project.py) · SHA256 `3183a6c7287249b34f5d3e26e4c13e27e93729783b705c746f1e9a0cae8f34e3`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `formula` | 40 | `text: str` | `text` as a chemical formula the Materials Project can search, or None. |
| `lookup_key` | 51 | `name: str` | ('material_ids', 'mp-149') or ('formula', 'Si') for a class name, or None when it names no crystalline material. |
| `_get` | 67 | `path: str, params: dict` | Read the linked implementation and its call-site contract. |
| `database_version` | 75 | `` | Read the linked implementation and its call-site contract. |
| `_num` | 84 | `x, digits: int=4` | Read the linked implementation and its call-site contract. |
| `_record` | 88 | `d: dict` | Read the linked implementation and its call-site contract. |
| `search` | 101 | `kind: str, value: str, limit: int` | Entries for a formula (most stable first, within max_energy_above_hull) or a material id. |

Imports: `functools`, `re`, `requests`, `src.config`, `src.tools.lexical`, `src.tools.progress`

## src/tools/matportal.py

MatPortal (matportal.org, the materials-science OntoPortal) search over its REST API.

[Source](../../src/tools/matportal.py) · SHA256 `c597e6e75faa62ecc43b31cd7002653fae959e714ec3c053f7a4b41d5f6eff98`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_get` | 16 | `path: str, params: dict` | Read the linked implementation and its call-site contract. |
| `list_ontologies` | 24 | `` | Acronym -> name for every ontology on MatPortal. |
| `check_acronyms` | 30 | `ontologies: str \| None` | Keep only acronyms MatPortal knows (an unknown acronym makes OntoPortal return nothing). |
| `search` | 43 | `query: str, ontologies: str \| None=None, max_results: int=10, exact: bool=False` | Read the linked implementation and its call-site contract. |

Imports: `functools`, `requests`, `src.config`, `src.tools.lexical`, `src.tools.progress`

## src/tools/mds_onto_open_api.py

MDS-Onto portal REST API helpers and FastMCP tool definitions for ontology retrieval.

[Source](../../src/tools/mds_onto_open_api.py) · SHA256 `21b2a33da0fa050d151c4682bd51b0f1b8314a92708ff10041256028f9ed87cc`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `search_mdsonto` | 36 | `query: str, api_key: Optional[str]=None, ontologies: Optional[List[str]]=None, require_exact_match: bool=False, also_search_properties: bool=True, also_search_obsolete: bool=False, max_page_size: int=50, max_records: Optional[int]=None, verbose: bool=False` | Search for ontology terms in BioPortal/OntoPortal using the search endpoint. Modified to include property data in the retrieval. |
| `_extract_property` | 123 | `properties: Dict, uri: str` | Helper to safely extract a property value from the properties dict. |
| `search_mds_ontology` | 138 | `query: str, ontologies: Optional[str]=None, max_results: int=1000, require_exact_match: bool=False, search_in_properties: bool=True, api_key: Optional[str]=None` | Search for terms in the MDS Ontology (or others) and retrieve MDS-specific metadata. |
| `get_ontology_domains` | 234 | `` | Downloads the MDS Ontology OWL file directly and extracts all unique 'mds:hasDomain' values. |
| `main` | 285 | `` | Main entry point. 1. If run normally, starts the MCP Server. 2. If you want to SEE the domains immediately, uncomment the lines below. |

Imports: `fastmcp`, `requests`, `src.tools.lexical`, `src.tools.progress`, `typing`, `xml.etree.ElementTree`

## src/tools/mds_portal.py

Thin wrapper over the MDS-Onto Open Portal client (mds_onto_open_api.py, vendored unchanged).

[Source](../../src/tools/mds_portal.py) · SHA256 `e87ed891488832134d42577ee782dda356f1f25c922eaa223ecf2769497b757a`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `list_ontologies` | 18 | `` | Acronym -> name for every ontology on the portal. |
| `check_acronyms` | 26 | `ontologies: str \| None` | Keep only acronyms the portal knows (one unknown acronym makes the portal return nothing). |
| `search` | 39 | `query: str, ontologies: str \| None=None, max_results: int=10, exact: bool=False` | ontologies: comma-separated portal acronyms, e.g. "MDS-ONTO,IOF,PMDCO,QUDT". Unknown ones are dropped. |
| `domains` | 80 | `` | Read the linked implementation and its call-site contract. |

Imports: `functools`, `requests`, `src.config`, `src.tools`, `src.tools.lexical`, `src.tools.progress`

## src/tools/ontology_review.py

Review artifacts for evidence-backed placements and cross-domain candidates.

[Source](../../src/tools/ontology_review.py) · SHA256 `27113275324b918b12da6a2465544c5446bbd11e810856b71eb69a010196da01`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `context` | 12 | `concepts, relations` | Read the linked implementation and its call-site contract. |
| `paper_parents` | 22 | `classes, relations` | Read the linked implementation and its call-site contract. |
| `issues` | 54 | `classes` | Read the linked implementation and its call-site contract. |
| `correspondences` | 61 | `outputs, run_id, domain, classes` | Read the linked implementation and its call-site contract. |
| `correspondences.key` | 63 | `label` | Read the linked implementation and its call-site contract. |
| `correspondences.parent` | 67 | `c, by_id` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `json`, `re`, `src.tools.owl`

## src/tools/ontostore.py

Local ontology store: every external term the pipeline may use (BFO, CCO, RO, QUDT, PMDCO, IOF, MDS-Onto).

[Source](../../src/tools/ontostore.py) · SHA256 `4427a8e73ad5dd483f14176a946ba2c417f94048a4ee349ec2bda9991f1a06c8`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_portal` | 65 | `path: str, **params` | Read the linked implementation and its call-site contract. |
| `latest_submission` | 75 | `acronym: str` | Version, release date and id of an ontology's latest submission on the MDS-Onto portal. |
| `_rdf_format` | 82 | `data: bytes` | Read the linked implementation and its call-site contract. |
| `_version_key` | 87 | `path` | Read the linked implementation and its call-site contract. |
| `_fetch` | 91 | `name: str, spec: dict` | Path of an ontology file, downloaded into outputs/cache/ontologies when missing. |
| `build` | 127 | `` | Download missing files, load every ontology into Oxigraph, extract the term index, embed every term. |
| `_count` | 163 | `terms: dict, field: str` | Read the linked implementation and its call-site contract. |
| `_query` | 170 | `store, preds` | Read the linked implementation and its call-site contract. |
| `_versions` | 176 | `store` | graph name -> (ontology IRI, version) from each file's owl:Ontology header. |
| `_english` | 190 | `lit` | Read the linked implementation and its call-site contract. |
| `_extract` | 196 | `store, order: list[str]` | One record per typed IRI, merged across graphs. A term belongs to the ontology whose IRI prefix it carries (its home) when that graph declares it, else to the first graph that declares it. |
| `_norm` | 258 | `text: str` | Read the linked implementation and its call-site contract. |
| `_write_index` | 263 | `terms: dict` | Read the linked implementation and its call-site contract. |
| `_text` | 287 | `t: dict` | Read the linked implementation and its call-site contract. |
| `_write_vectors` | 292 | `terms: dict` | Read the linked implementation and its call-site contract. |
| `available` | 313 | `` | Read the linked implementation and its call-site contract. |
| `require` | 317 | `` | Read the linked implementation and its call-site contract. |
| `_db` | 323 | `` | Read the linked implementation and its call-site contract. |
| `manifest` | 328 | `` | Read the linked implementation and its call-site contract. |
| `_reset` | 332 | `` | Read the linked implementation and its call-site contract. |
| `term` | 338 | `iri: str` | The store record of an IRI: ontology, kind, label, definition, labels, parents, domain, range, inverse, mappings, types, deprecated, defined_by (the ontology's IRI). |
| `ancestors` | 354 | `iri: str` | Named ancestors through every ontology in the store, nearest first. |
| `reaches_bfo` | 365 | `iri: str` | Read the linked implementation and its call-site contract. |
| `links` | 369 | `iri: str` | (relation, IRI) for the term's own mappings and every mapping pointing at it (broader/narrower inverted). |
| `propagate` | 379 | `iri: str, max_hops: int \| None=None` | Terms reached through mappings from iri: one hop (its mappings) and two hops (theirs), each with the path of IRIs and relations it came through. Only terms that are in the store. |
| `_vectors` | 399 | `` | (matrix, ids, row of iri, ontology per row, kind per row, deprecated per row) or None when the store has no vectors for the current EMBED model. |
| `has_vectors` | 414 | `` | Read the linked implementation and its call-site contract. |
| `_search_vectors` | 419 | `kinds: tuple, ontologies: tuple` | Reuse eligible vector subsets instead of scoring unrelated ontologies and term kinds. |
| `exact` | 434 | `text: str, kinds=None, ontologies=None` | Terms (not deprecated) with any label that normalises to the same form as text. |
| `similarity` | 444 | `a: str, b: str` | Trigram Dice similarity of two labels after the store's normalisation (0-1). |
| `_words` | 449 | `norm: str` | Read the linked implementation and its call-site contract. |
| `_fuzzy` | 453 | `a: str, b: str` | Trigram similarity of two normalised labels, counted only when they share a whole word ("backsheet" is not "spreadsheet", "PV modules" is not "mode"). |
| `_grams` | 459 | `text: str` | Read the linked implementation and its call-site contract. |
| `_dice` | 464 | `a: str, b: str` | Read the linked implementation and its call-site contract. |
| `search` | 469 | `texts: list[str], vector=None, kinds=None, ontologies=None, k: int=10, pool: int=60, nearest: int=0` | Candidates for one concept, ranked exact label matches first, then by a fused score of three signals: exact (a normalised label equals one of texts), fuzzy (trigram similarity, FTS5 trigram index) and cosine (vector against the term vectors; pass the concept's EMBED vector, or None for labels only). A candidate needs one signal on its own (exact, fuzzy >= min_fuzzy or cosine >= min_cosine) and a fused score >= min_score; the `nearest` closest terms by cosine are kept regardless (placement always sees the nearest classes). kinds / ontologies restrict the result (e.g. kinds=("class",), ontologies=("CCO", "BFO")). |
| `_fuse` | 541 | `exact: float, fuzzy: float, cosine: float \| None` | Weighted mean of the lexical signal (1 for an exact label, else the trigram similarity) and the embedding cosine; without embeddings the lexical signal alone. |
| `score` | 550 | `iri: str, texts: list[str], vector=None` | The search signals and fused score of one known term against a concept (for terms found elsewhere, such as MDS-Onto portal hits). |
| `score_external` | 568 | `label: str, definition: str, texts: list[str], vector=None, term_vector=None` | The same signals and fused score for a term outside the store (a portal hit): term_vector is the term's embedding of label: definition, made with the store's recipe. |
| `external_text` | 582 | `label: str, definition: str` | Read the linked implementation and its call-site contract. |
| `summary` | 588 | `` | What a run records in run.json: ontology versions and hashes, embedding model, build time. |
| `status` | 596 | `check_portal: bool=True` | Is the store built, built from the files and settings in use now, and is a newer MDS-Onto out? |

Imports: `collections`, `datetime`, `functools`, `hashlib`, `json`, `numpy`, `pyoxigraph`, `re`, `requests`, `shutil`, `sqlite3`, `src.config`, `src.tools`, `src.tools.lexical`, `src.tools.progress`

## src/tools/owl.py

OWL2 assembly (rdflib) -> JSON-LD, structural validation (no reasoner), and ontology metrics.

[Source](../../src/tools/owl.py) · SHA256 `d22433c9f2686c30a4d3369e7cb3f9a9421db791f530c3d35f4add4834ce079c`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `base` | 70 | `` | Read the linked implementation and its call-site contract. |
| `lineage` | 75 | `cid: str, by_id: dict` | Ancestors of a local class, nearest first: local ids, then upper IRIs up to BFO entity. |
| `label_of` | 84 | `ref: str, by_id: dict` | Read the linked implementation and its call-site contract. |
| `bfo_category` | 88 | `cid: str, by_id: dict` | Read the linked implementation and its call-site contract. |
| `category_fit` | 92 | `chain: list[str], target: str, same: bool, kind: str='class'` | Can a local class (its lineage `chain`) be equivalent to (same=True) or a subclass of (same=False) the external class `target`? Only a BFO-aligned class: equivalence needs the same BFO category, a subclass needs the target's category to be the class's own or one above it. |
| `same_as_issues` | 105 | `g: rdflib.Graph` | Read the linked implementation and its call-site contract. |
| `_hidden` | 111 | `label: str, alt: str` | Acronyms and spelling variants go to skos:hiddenLabel: 'PERC', 'Voc', 'c-Si'; 'open circuit voltage' for 'open-circuit voltage'. |
| `labels` | 120 | `c: dict, mappings: list[dict]` | (predicate, text, source IRI or None, origin) for a class: its label (rdfs:label and skos:prefLabel), original member labels, reviewed paper synonyms, and labels of exactly or equivalently matched external terms. |
| `_annotate` | 134 | `g, kw, s, p, o, notes: dict` | An owl:Axiom annotating the triple (s, p, o) with notes {annotation property: value or [values]}. |
| `build` | 147 | `classes: list[dict], properties: dict, mappings: list[dict], papers: list[dict], run_id: str, domain: str` | One ontology per domain; local class IRIs are domain-scoped to preserve separate meanings. |
| `build.add_facets` | 196 | `subject, facets` | Read the linked implementation and its call-site contract. |
| `build.ref` | 203 | `r: str` | Read the linked implementation and its call-site contract. |
| `serialize_turtle` | 342 | `g: rdflib.Graph` | Read the linked implementation and its call-site contract. |
| `serialize` | 346 | `g: rdflib.Graph` | Read the linked implementation and its call-site contract. |
| `_parents` | 352 | `g, c` | Read the linked implementation and its call-site contract. |
| `_depth_to_entity` | 356 | `g, c` | Read the linked implementation and its call-site contract. |
| `validate` | 371 | `g: rdflib.Graph, text: str, extra: list[str]=()` | Structural checks only (no reasoner), plus checks made elsewhere (extra: the interop mapping checks). |
| `_ancestors` | 416 | `g, c` | Read the linked implementation and its call-site contract. |
| `metrics` | 426 | `g: rdflib.Graph, classes: list[dict], mappings: list[dict], properties: dict` | Read the linked implementation and its call-site contract. |
| `metrics.cover` | 439 | `pred` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `datetime`, `rdflib`, `rdflib.namespace`, `re`, `src.config`, `src.tools`, `statistics`

## src/tools/pdf_parse.py

Deterministic PDF → sections + figure captions/mentions. Drops back matter and repeated headers/footers.

[Source](../../src/tools/pdf_parse.py) · SHA256 `a211bcafffdb39e2608cc847ab9e3832cda3de0063f8edf4b1883502909080e9`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_clean` | 29 | `text: str` | Read the linked implementation and its call-site contract. |
| `parse` | 35 | `pdf_path: str` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `pymupdf`, `re`, `time`

## src/tools/progress.py

Console progress: every line is 'HH:MM:SS [stage] message'.

[Source](../../src/tools/progress.py) · SHA256 `13362c58b068f56a5ad38945a0e9c88769f1803e80c126d2f885fbf4eccb995b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_DiagnosticHandler.emit` | 23 | `self, record` | Read the linked implementation and its call-site contract. |
| `redact` | 30 | `message: str` | Read the linked implementation and its call-site contract. |
| `configure_logging` | 39 | `folder: Path, run_id: str` | Append console messages and diagnostics independently of the sweep shell. |
| `_warning` | 51 | `message, category, filename, lineno, file=None, line=None` | Read the linked implementation and its call-site contract. |
| `_record` | 55 | `message: str, end: str` | Read the linked implementation and its call-site contract. |
| `set_stage` | 69 | `name: str` | Read the linked implementation and its call-site contract. |
| `log` | 73 | `message: str, end: str='\n'` | Read the linked implementation and its call-site contract. |
| `finish` | 79 | `message: str` | Complete a line started with log(..., end=''). |

Imports: `datetime`, `json`, `logging`, `os`, `pathlib`, `re`, `threading`, `time`, `urllib.parse`, `warnings`

## src/tools/reports.py

Run reports: per-paper compute CSV, corpus report, ontology report (Markdown + JSON stats).

[Source](../../src/tools/reports.py) · SHA256 `767ef3ecde8be2fe2225253267da011086729da13ef1ac898674cd41f7c0293e`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_table` | 18 | `headers: list, rows: list` | Read the linked implementation and its call-site contract. |
| `write_csv` | 24 | `path: Path, rows: list[dict]` | Read the linked implementation and its call-site contract. |
| `paper_compute` | 32 | `papers: list[dict], ledger_by_item: dict` | Compute per paper. `extraction_*` = what extracting the paper cost (kept across cache reuse); `run_*` = what this run actually spent on it (0 on a cache hit). |
| `corpus_report` | 53 | `path: Path, run_id: str, norm: dict, papers: list[dict]` | Read the linked implementation and its call-site contract. |
| `ontology_report` | 122 | `path: Path, run_id: str, m: dict, v: dict, classes: list[dict], by_agent: dict, manifest: dict` | Read the linked implementation and its call-site contract. |
| `write_uncertain` | 184 | `run_dir: Path, run_id: str, stage: str, items: list[dict], updated: str=''` | Replace one stage's items in ontology/uncertain.json; other stages are kept, so a resumed run keeps them. Everything here is otherwise only counted in run.json/eval_runs.csv. |
| `_load` | 200 | `path: Path` | Read the linked implementation and its call-site contract. |
| `_flat` | 204 | `prefix: str, d: dict` | Read the linked implementation and its call-site contract. |
| `_coverage` | 208 | `*sources` | Row coverage per model pass (sent, recovered by the retry, still missing) as flat columns. |
| `_unevidenced` | 220 | `papers: list[dict], kind: str` | Read the linked implementation and its call-site contract. |
| `_share` | 226 | `papers: list[dict], kind: str` | Share of a paper set's extracted items whose evidence quote was found in the paper text. |
| `eval_row` | 232 | `run_dir: Path, m: dict` | Everything worth comparing across runs, as one flat row. Missing stages leave blanks. |
| `upsert_eval` | 382 | `path: Path, row: dict` | Replace this run's row (or append it). New columns are added at the end; old rows keep blanks. Locked and written atomically, so runs in parallel never lose each other's rows. |
| `revision_event` | 402 | `path: Path, revision: str, created: str, description: str=''` | One non-metric event when this revision first starts a new run. |

Imports: `collections`, `csv`, `io`, `json`, `pathlib`, `src.agents.normalization`, `src.tools`, `statistics`

## src/tools/retrieval.py

Normalized retrieval vectors in memory; llm.embed also persists them across runs by endpoint and model.

[Source](../../src/tools/retrieval.py) · SHA256 `15e50376bb4fa79c0f3e91e2a6e18b21dcb129bc8b3f1cbb0c5ee851492c1de1`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `enabled` | 14 | `` | Read the linked implementation and its call-site contract. |
| `embed` | 18 | `texts: list[str], ledger=None, agent: str='enrichment'` | Read the linked implementation and its call-site contract. |
| `query` | 35 | `texts: list[str], ledger=None, agent: str='enrichment'` | Vectors for texts searched against the ontology store (EMBED query prefix). |
| `document` | 40 | `texts: list[str], ledger=None, agent: str='enrichment'` | Vectors for texts scored as store terms (EMBED document prefix, as the store's own vectors). |
| `similarity` | 45 | `a: str, b: str` | Read the linked implementation and its call-site contract. |

Imports: `numpy`, `src.config`, `src.tools`

## src/tools/upper.py

BFO 2020 + CCO terms and OBO Relations Ontology (RO) properties, cached in resources/upper/bfo_cco.json, the curated menus (category roots, type defaults, causal rules, LoRA tasks), and lookups of any other external term through the ontology store (src/tools/ontostore.py).

[Source](../../src/tools/upper.py) · SHA256 `5c66a935b9158061701a5c1ca289d5165585044ea33e82234a5b571db601158a`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `build` | 20 | `` | Refresh bfo_cco.json from the CCO and RO repositories (only needed for new CCO/BFO/RO releases). |
| `build.txt` | 28 | `s, p` | Read the linked implementation and its call-site contract. |
| `build.named` | 32 | `objs` | Read the linked implementation and its call-site contract. |
| `build.src` | 35 | `s` | Read the linked implementation and its call-site contract. |
| `terms` | 73 | `` | Read the linked implementation and its call-site contract. |
| `facets` | 78 | `` | MDS-Onto study stages and MDSDom domains/subdomains (resources/upper/mds_facets.json). |
| `menus` | 84 | `` | Read the linked implementation and its call-site contract. |
| `class_menu` | 88 | `` | Curated upper classes: label -> IRI. |
| `_property_index` | 95 | `` | 'SOURCE:label' (lowercase) -> IRI, e.g. 'ro:has quality'. Labels repeat across BFO/CCO/RO. |
| `property_menu` | 100 | `` | Curated BFO/CCO/RO properties side by side: 'SOURCE:label' -> IRI. |
| `property_iri` | 105 | `key: str` | IRI for 'SOURCE:label', e.g. 'CCO:affects'. |
| `ancestors` | 110 | `iri: str` | All named ancestors of an external class or property, nearest first: BFO/CCO from bfo_cco.json, every other ontology (MDS-Onto, PMDCO, IOF, ...) from the ontology store, followed up to BFO. |
| `describe` | 122 | `iri: str` | label, definition, source, parents (and domain, range, inverse for properties) of an external term: the curated BFO/CCO/RO cache first, then the ontology store when it is built. |
| `relation_group` | 171 | `pred: str` | (properties, subject category, object category) for an extracted predicate, or None (is_a, related_to, or a phrase no group formalizes). |
| `relation_iri` | 178 | `pred: str` | One IRI for a predicate in the literature layer: the group's first property without a domain/range restriction (BFO/RO generic), else its first property. |

Imports: `functools`, `json`, `rdflib`, `rdflib.namespace`, `src.config`, `src.tools`

## src/tools/workers.py

Ordered task workers and a run-wide adaptive limit for local model requests (halved on overload).

[Source](../../src/tools/workers.py) · SHA256 `6ee973a481da06dd1aa93d706c8d1853dc5bc1473c5f1dd2903f31e40c85d292`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `configure` | 21 | `count: int` | Read the linked implementation and its call-site contract. |
| `fallback` | 34 | `reason: str, timeout: bool=False, generation: int \| None=None` | Halve the request limit (8 -> 4 -> 2 -> 1) after an overload, a memory error or a second timeout. Requests already in flight when the limit last changed (an older generation) do not lower it again, so one burst of failures counts once. |
| `slot` | 56 | `` | One model request; yields the limit generation it started under (pass it to fallback). |
| `ordered` | 71 | `function, values` | Return results in input order; dependent work stays inside each task. |
| `summary` | 96 | `` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `concurrent.futures`, `contextlib`, `src.tools.progress`, `threading`

## src/tools/zotero.py

Zotero: list collections, fetch a collection's top-level items, and cache their PDFs.

[Source](../../src/tools/zotero.py) · SHA256 `0cce62a3d03ebc03522d8b57a32f9bdd5a73c08d6c7f73830d4faf7741476148`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_client` | 17 | `library_id: str` | Read the linked implementation and its call-site contract. |
| `list_collections` | 21 | `library_id: str` | Read the linked implementation and its call-site contract. |
| `_local_copy` | 27 | `att: dict` | Read the linked implementation and its call-site contract. |
| `_fetch_pdf` | 42 | `z, item_key: str, path: Path` | Copy the item's first available PDF to `path`; return where it came from. |
| `list_items` | 58 | `library_id: str, collection_key: str` | Top-level items of a collection (metadata only, no PDFs). |
| `attach_pdf` | 78 | `paper: dict, pdf_dir: Path, library_id: str` | Set paper["pdf"] / paper["pdf_source"] (cache, zotero.org, local, or None). |

Imports: `functools`, `pathlib`, `pyzotero`, `shutil`, `src.config`

## start-dashboard.ps1

Summary: start-dashboard support for Knowledge Workflow; retain the existing operational notes below.

[Source](../../start-dashboard.ps1) · SHA256 `0af7ba4d682e22214814a285473f9765b3b0ff6fbdcabde5113e61ed657c61d3`

| Callable | Line | Signature | Summary |
|---|---:|---|---|

Imports: 

## tests/test_codebase_ontology.py

Verify ontology-guided planning and read-only provenance against guarded fixtures.

[Source](../../tests/test_codebase_ontology.py) · SHA256 `2c6d0987fa0f81e9b4c1cdd178384fc527c0bdfdfa63e7a604edd7a311d59d68`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `graph` | 21 | `` | Read the linked implementation and its call-site contract. |
| `write` | 25 | `path, value` | Read the linked implementation and its call-site contract. |
| `run_fixture` | 30 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `extraction` | 37 | `result` | Read the linked implementation and its call-site contract. |
| `test_modes_plan_different_extraction_work` | 41 | `graph` | Read the linked implementation and its call-site contract. |
| `test_binding_failures` | 52 | `graph, bindings` | Read the linked implementation and its call-site contract. |
| `test_mode_cycle_rejected` | 56 | `graph` | Read the linked implementation and its call-site contract. |
| `test_missing_mode_does_not_fall_back` | 61 | `graph` | Read the linked implementation and its call-site contract. |
| `test_recorded_completion_requires_readable_products` | 65 | `graph, tmp_path` | Read the linked implementation and its call-site contract. |
| `test_presence_not_completion_or_semantic_acceptance` | 74 | `graph, tmp_path` | Read the linked implementation and its call-site contract. |
| `test_partial_extraction_and_later_failure_block` | 82 | `graph, tmp_path` | Read the linked implementation and its call-site contract. |
| `test_observations_are_records_not_executions` | 95 | `graph, tmp_path` | Read the linked implementation and its call-site contract. |
| `test_freshness_checks_contracts_and_source` | 105 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_remote_context_not_fetched` | 113 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_duplicate_domains_block_integration` | 119 | `graph, tmp_path` | Read the linked implementation and its call-site contract. |
| `test_out_of_scope_run_rejected` | 128 | `graph, tmp_path` | Read the linked implementation and its call-site contract. |
| `test_source_rerun_blocks_old_integration` | 133 | `graph, tmp_path` | Read the linked implementation and its call-site contract. |
| `test_cli_intermediate_products_are_not_wrapper_requirements` | 152 | `graph, tmp_path` | Read the linked implementation and its call-site contract. |
| `test_reports_found_in_figures_without_inventing_completion` | 159 | `graph, tmp_path` | Read the linked implementation and its call-site contract. |
| `test_missing_implementation_rejected_by_shape` | 174 | `graph` | Read the linked implementation and its call-site contract. |
| `test_validator_detects_disconnected_units` | 181 | `graph` | Read the linked implementation and its call-site contract. |

Imports: `codebase_ontology`, `hashlib`, `importlib.util`, `json`, `ontology_agent`, `pathlib`, `pytest`, `rdflib`, `sys`

## tests/test_concept_lineage.py

Verify exact normalization identity and original-label provenance through downstream export.

[Source](../../tests/test_concept_lineage.py) · SHA256 `573fbf42e2e3f6ed5034a5b3e22c1899b3ef2221023a286e8775cc055c40202c`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `concept` | 20 | `cid, label, synonyms=()` | Read the linked implementation and its call-site contract. |
| `papers` | 25 | `` | Read the linked implementation and its call-site contract. |
| `OfflineNormalization.__init__` | 35 | `self, ledger=None` | Read the linked implementation and its call-site contract. |
| `OfflineNormalization._semantic_merge` | 38 | `self, groups` | Read the linked implementation and its call-site contract. |
| `OfflineNormalization._summarize` | 42 | `self, *args` | Read the linked implementation and its call-site contract. |
| `test_exact_map_scopes_local_ids_to_their_papers` | 46 | `` | Read the linked implementation and its call-site contract. |
| `test_cleaning_and_normalization_return_recorded_lineage` | 66 | `` | Read the linked implementation and its call-site contract. |
| `test_same_final_label_fold_retains_every_original` | 78 | `` | Read the linked implementation and its call-site contract. |
| `test_case_dedup_keeps_original_spelling_in_lineage` | 88 | `` | Read the linked implementation and its call-site contract. |
| `test_invalid_identity_map_fails_with_source_identified` | 97 | `` | Read the linked implementation and its call-site contract. |
| `test_enrichment_preserves_originals_but_can_reject_synonyms` | 107 | `` | Read the linked implementation and its call-site contract. |
| `test_old_classes_without_label_sources_keep_existing_review_behavior` | 121 | `` | Read the linked implementation and its call-site contract. |
| `test_placement_carries_label_provenance_forward` | 130 | `` | Read the linked implementation and its call-site contract. |
| `test_owl_export_cites_label_sources_and_preserves_hidden_label_policy` | 144 | `` | Read the linked implementation and its call-site contract. |
| `test_owl_export_cites_label_sources_and_preserves_hidden_label_policy.sources` | 157 | `predicate, label` | Read the linked implementation and its call-site contract. |
| `test_pipeline_writer_saves_lineage_and_other_artifacts` | 167 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_pipeline_writer_saves_lineage_and_other_artifacts.SavedRun.papers` | 174 | `self` | Read the linked implementation and its call-site contract. |
| `test_pipeline_writer_saves_lineage_and_other_artifacts.SavedRun.write` | 176 | `self, name, value` | Read the linked implementation and its call-site contract. |
| `test_quarantine_and_exact_lineage_work_together` | 188 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_quarantine_and_exact_lineage_work_together.SavedRun.papers` | 197 | `self` | Read the linked implementation and its call-site contract. |
| `test_quarantine_and_exact_lineage_work_together.SavedRun.write` | 199 | `self, name, value` | Read the linked implementation and its call-site contract. |

Imports: `copy`, `json`, `pytest`, `rdflib`, `rdflib.namespace`, `src`, `src.agents.enrichment`, `src.agents.normalization`, `src.agents.ontology`, `src.tools`, `types`, `unittest.mock`

## tests/test_data_journey.py

Verify information flow and saved concept provenance without executing the pipeline.

[Source](../../tests/test_data_journey.py) · SHA256 `806f92cf54b1b07cab2964a997b667e8baa1315f96486bf686a017b2af52b6c0`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `write` | 18 | `path, value` | Read the linked implementation and its call-site contract. |
| `saved` | 23 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `target` | 52 | `package` | Read the linked implementation and its call-site contract. |
| `test_ontology_models_information_transformations_with_real_implementations` | 56 | `` | Read the linked implementation and its call-site contract. |
| `test_agent_guide_exposes_retained_and_omitted_information` | 69 | `` | Read the linked implementation and its call-site contract. |
| `test_repeated_paper_local_ids_remain_distinct_candidates` | 80 | `saved` | Read the linked implementation and its call-site contract. |
| `test_original_label_shared_by_canonical_targets_is_ambiguous` | 89 | `saved` | Read the linked implementation and its call-site contract. |
| `test_partial_recorded_map_is_not_filled_with_inferred_merges` | 97 | `saved` | Read the linked implementation and its call-site contract. |
| `test_changed_saved_lineage_label_requires_review` | 105 | `saved` | Read the linked implementation and its call-site contract. |
| `test_merged_membership_is_independent_of_cross_domain_mapping` | 111 | `saved` | Read the linked implementation and its call-site contract. |
| `test_integration_not_selecting_run_does_not_claim_membership` | 119 | `saved` | Read the linked implementation and its call-site contract. |
| `test_changed_iri_and_reviewed_aliases_are_not_hidden` | 126 | `saved` | Read the linked implementation and its call-site contract. |
| `test_snapshots_are_read_only_redacted_and_links_resolve` | 134 | `saved, tmp_path` | Read the linked implementation and its call-site contract. |
| `test_snapshot_detects_source_change` | 148 | `saved` | Read the linked implementation and its call-site contract. |
| `test_unsafe_identifiers_are_rejected` | 155 | `bad` | Read the linked implementation and its call-site contract. |

Imports: `codebase_ontology`, `data_journey`, `json`, `operational_contracts`, `pathlib`, `pytest`, `rdflib`, `sys`

## tests/test_documentation_library.py

Verify documentation navigation, safe publication boundaries and Markdown rendering.

[Source](../../tests/test_documentation_library.py) · SHA256 `af1eb55635c65e1f862abc9d9cfa3fabbd75533ee9d9d0ae800cffe9bf7ff358`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `library_root` | 18 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_links_headings_and_safe_sources` | 39 | `library_root` | Read the linked implementation and its call-site contract. |
| `test_missing_graph_is_explained` | 64 | `library_root` | Read the linked implementation and its call-site contract. |
| `test_output_cannot_escape_outputs` | 73 | `library_root` | Read the linked implementation and its call-site contract. |

Imports: `documentation_library`, `json`, `pathlib`, `pytest`, `sys`

## tests/test_extraction_quality.py

Verify malformed extraction quarantine across cached, merged and normalization boundaries.

[Source](../../tests/test_extraction_quality.py) · SHA256 `1bc762129a47cc11872ca6f7f8eb0aa554e8369bf79a62e326f6ea635f6068ee`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `record` | 18 | `` | Read the linked implementation and its call-site contract. |
| `test_actual_label_is_quarantined_with_dependent_records_and_preserved_raw` | 25 | `` | Read the linked implementation and its call-site contract. |
| `test_merge_and_finalize_preserve_valid_claims_after_id_renumbering` | 39 | `` | Read the linked implementation and its call-site contract. |
| `test_mult_pass_does_not_feed_bad_labels_forward_or_confuse_old_ids` | 51 | `` | Read the linked implementation and its call-site contract. |
| `test_legacy_cache_is_guarded_without_overwriting_cache` | 67 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_normalization_boundary_guards_existing_paper_records` | 84 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_normalization_boundary_guards_existing_paper_records.Run.papers` | 91 | `self` | Read the linked implementation and its call-site contract. |
| `test_normalization_boundary_guards_existing_paper_records.Run.write` | 92 | `self, name, data` | Read the linked implementation and its call-site contract. |
| `test_normalization_boundary_guards_existing_paper_records.Agent.__init__` | 95 | `self, ledger` | Read the linked implementation and its call-site contract. |
| `test_normalization_boundary_guards_existing_paper_records.Agent.run` | 96 | `self, papers` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `copy`, `hashlib`, `json`, `pathlib`, `src`, `src.agents`, `src.agents.extraction`, `src.tools`, `unittest.mock`

## tests/test_gemini_quota.py

Test gemini quota support for the Knowledge Workflow system.

[Source](../../tests/test_gemini_quota.py) · SHA256 `0ebc1417e12fb14d5cb742068ab5fcfc8819423d2290efc3773198f4e5d54c6f`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `QuotaTests.setUp` | 21 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.advance` | 32 | `self, seconds` | Read the linked implementation and its call-site contract. |
| `QuotaTests.error` | 35 | `self, body, status=429, headers=None` | Read the linked implementation and its call-site contract. |
| `QuotaTests.client` | 40 | `self, effects` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_rpm_survives_restart` | 44 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_rolling_rpm` | 50 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_models_have_separate_budgets` | 55 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_llm_integration_and_sdk_retry_disabled` | 61 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_tpm_waits_for_window` | 77 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_large_input_fails_before_request` | 83 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_daily_persistent_and_resets` | 86 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_pacific_dst` | 94 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_unknown_model_and_bad_limits` | 98 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_lite_pacing` | 103 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_every_retry_reserved_and_output_cap` | 109 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_provider_daily_stops_and_blocks_restart` | 118 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_retry_exhaustion_is_terminal` | 124 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_5xx_retries` | 129 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_retry_hints` | 133 | `self` | Read the linked implementation and its call-site contract. |
| `QuotaTests.test_400_not_retried` | 137 | `self` | Read the linked implementation and its call-site contract. |

Imports: `datetime`, `httpx`, `openai`, `os`, `pathlib`, `src.tools`, `sys`, `tempfile`, `types`, `unittest`, `unittest.mock`

## tests/test_identity.py

Concepts that end up with the same name are folded into one at normalization.

[Source](../../tests/test_identity.py) · SHA256 `bd7e6a621759e950e637266234d88607bf126ed209fd56ffbb08dc0ca3b5c17b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `test_groups_with_the_same_final_label_are_one_concept` | 12 | `` | Read the linked implementation and its call-site contract. |

Imports: `pathlib`, `src.agents.normalization`, `sys`

## tests/test_interoperability_alignment.py

Alignment replies may reference only candidates shown in the current batch.

[Source](../../tests/test_interoperability_alignment.py) · SHA256 `df3f61f9020007c33bfa2cc361ece80e0d8a6a2ab04cf6eb5a906e88d2e33214`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `candidate` | 15 | `label_match=False` | Read the linked implementation and its call-site contract. |
| `concept` | 20 | `cid, candidates=None, excluded=False` | Read the linked implementation and its call-site contract. |
| `mapping` | 25 | `cid, n=1, relation='close'` | Read the linked implementation and its call-site contract. |
| `AlignmentTests.align` | 30 | `self, classes, replies, local=False, screening=None, batch=20` | Read the linked implementation and its call-site contract. |
| `AlignmentTests.test_no_candidate_class_reply_does_not_crash` | 43 | `self` | Read the linked implementation and its call-site contract. |
| `AlignmentTests.test_class_from_another_batch_is_not_accepted` | 48 | `self` | Read the linked implementation and its call-site contract. |
| `AlignmentTests.test_unknown_excluded_and_invalid_candidates_are_ignored` | 53 | `self` | Read the linked implementation and its call-site contract. |
| `AlignmentTests.test_screened_class_and_screened_candidate_are_ignored` | 59 | `self` | Read the linked implementation and its call-site contract. |
| `AlignmentTests.test_valid_mapping_normalization_and_downgrade_are_preserved` | 66 | `self` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `pathlib`, `src.agents.interoperability`, `sys`, `unittest`, `unittest.mock`

## tests/test_materials_project.py

Only names of crystalline materials are looked up in the Materials Project; acronyms and gases are not.

[Source](../../tests/test_materials_project.py) · SHA256 `46e177a911b3f68b426fa623fa0450317acb89e4c16609f8b486c6c58f71d252`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `test_formulas_element_names_and_material_forms` | 12 | `` | Read the linked implementation and its call-site contract. |
| `test_acronyms_gases_and_non_stoichiometric_names_are_skipped` | 22 | `` | Read the linked implementation and its call-site contract. |
| `test_every_element_has_a_name` | 28 | `` | Read the linked implementation and its call-site contract. |

Imports: `pathlib`, `src.tools.materials_project`, `sys`

## tests/test_ontostore.py

Ontology store on two tiny ontologies: home attribution, label search, ancestors, mapping propagation.

[Source](../../tests/test_ontostore.py) · SHA256 `17e59344d8d9dbe6d0c27dbf70cbd102b7dedfdcc0fd21a5a862e6a564cffe9c`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `store` | 31 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_build_and_lookups` | 50 | `store` | Read the linked implementation and its call-site contract. |

Imports: `pytest`, `src.tools`

## tests/test_operational_contracts.py

Test task navigation, paper bindings, documented checks and explicit definition coverage.

[Source](../../tests/test_operational_contracts.py) · SHA256 `41e4612709a8aee162ae75807ef5c4fd98017329a8dbb7baff8af87f8e514a8d`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `graph` | 19 | `` | Read the linked implementation and its call-site contract. |
| `write` | 23 | `path, data` | Read the linked implementation and its call-site contract. |
| `run` | 29 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_every_project_node_has_nonempty_skos_definition` | 40 | `graph` | Read the linked implementation and its call-site contract. |
| `test_structural_descriptions_do_not_claim_reviewed_behavior` | 46 | `graph` | Read the linked implementation and its call-site contract. |
| `test_normalization_recipe_answers_binding_and_call_questions` | 51 | `graph` | Read the linked implementation and its call-site contract. |
| `test_contracts_cover_every_stage_with_reviewed_operations_and_inputs` | 68 | `graph` | Read the linked implementation and its call-site contract. |
| `test_before_checks_accept_fixture_but_do_not_execute` | 78 | `graph, run` | Read the linked implementation and its call-site contract. |
| `test_after_checks_require_scientific_review_even_with_valid_joins` | 86 | `graph, run` | Read the linked implementation and its call-site contract. |
| `test_malformed_concepts_block_normalization` | 94 | `graph, run, broken` | Read the linked implementation and its call-site contract. |
| `test_unresolved_paper_reference_blocks` | 99 | `graph, run` | Read the linked implementation and its call-site contract. |
| `test_wrong_canonical_endpoint_blocks_downstream` | 105 | `graph, run` | Read the linked implementation and its call-site contract. |
| `test_paper_coverage_loss_blocks_without_inventing_lineage` | 112 | `graph, run` | Read the linked implementation and its call-site contract. |
| `test_no_saved_completion_is_not_success` | 120 | `graph, run` | Read the linked implementation and its call-site contract. |
| `test_direct_invocation_remains_distinct_from_orchestrator` | 125 | `graph` | Read the linked implementation and its call-site contract. |
| `test_agent_can_follow_graph_from_stage_to_argument_artifact_and_checker` | 132 | `graph` | Read the linked implementation and its call-site contract. |
| `scientific_run` | 145 | `run` | Read the linked implementation and its call-site contract. |
| `test_scientific_stages_check_actual_saved_joins` | 172 | `graph, scientific_run, stage` | Read the linked implementation and its call-site contract. |
| `test_missing_canonical_identity_is_not_silent_loss` | 179 | `graph, scientific_run, stage, path` | Read the linked implementation and its call-site contract. |
| `test_excluded_classes_do_not_require_live_enrichment` | 185 | `graph, scientific_run` | Read the linked implementation and its call-site contract. |
| `test_unresolved_ontology_endpoints_block` | 195 | `graph, scientific_run, stage, path, field, value` | Read the linked implementation and its call-site contract. |
| `test_false_saved_validation_is_not_success` | 200 | `graph, scientific_run` | Read the linked implementation and its call-site contract. |
| `test_parseable_but_different_exports_are_rejected` | 206 | `graph, scientific_run` | Read the linked implementation and its call-site contract. |
| `test_large_export_comparison_is_explicitly_deferred` | 212 | `graph, scientific_run` | Read the linked implementation and its call-site contract. |
| `test_mapping_local_identifier_must_exist` | 223 | `graph, scientific_run` | Read the linked implementation and its call-site contract. |
| `test_one_concept_can_map_to_multiple_external_terms` | 229 | `graph, scientific_run` | Read the linked implementation and its call-site contract. |
| `test_extraction_coverage_checks_selection_not_only_completion` | 237 | `graph, scientific_run` | Read the linked implementation and its call-site contract. |
| `wrapper_run` | 246 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_wrapper_parsing_coverage_and_sections_are_checked` | 254 | `graph, wrapper_run` | Read the linked implementation and its call-site contract. |
| `test_wrapper_ingestion_requires_selected_pdf_metadata` | 260 | `graph, wrapper_run` | Read the linked implementation and its call-site contract. |
| `test_setup_never_invents_ready_from_domain_outputs` | 267 | `graph, scientific_run, stage` | Read the linked implementation and its call-site contract. |
| `test_before_checks_do_not_require_later_outputs` | 271 | `graph, scientific_run` | Read the linked implementation and its call-site contract. |
| `test_report_availability_and_skips_are_distinct_from_completion` | 278 | `graph, tmp_path` | Read the linked implementation and its call-site contract. |
| `integration_run` | 292 | `scientific_run` | Read the linked implementation and its call-site contract. |
| `test_integration_resolves_mapping_and_bridge_provenance` | 312 | `graph, integration_run` | Read the linked implementation and its call-site contract. |
| `test_integration_unknown_bridge_member_blocks` | 320 | `graph, integration_run` | Read the linked implementation and its call-site contract. |
| `test_integration_rejects_path_escape_and_malformed_endpoints` | 326 | `graph, integration_run` | Read the linked implementation and its call-site contract. |

Imports: `codebase_ontology`, `json`, `operational_contracts`, `pathlib`, `pytest`, `rdflib`, `shutil`, `sys`

## tests/test_parent_answers.py

Free-form parent answers from small models are read tolerantly, but never guessed.

[Source](../../tests/test_parent_answers.py) · SHA256 `d59ee6d169386fa9cc08d838537d197bd8501528e65ad680ea04a6fb15fca145`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `ParentAnswerTests.setUp` | 11 | `self` | Read the linked implementation and its call-site contract. |
| `ParentAnswerTests.test_readings` | 19 | `self` | Read the linked implementation and its call-site contract. |
| `ParentAnswerTests.test_resolve` | 25 | `self` | Read the linked implementation and its call-site contract. |

Imports: `src.agents.ontology`, `unittest`

## tests/test_row_retries.py

Rows the model leaves out are re-sent in smaller batches; answers inside an echoed schema are read.

[Source](../../tests/test_row_retries.py) · SHA256 `f7e2b7cde798f07b574a7bc807e746f72ac582391ecf3a40588f709938bb94a3`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `Fake.__init__` | 15 | `self` | Read the linked implementation and its call-site contract. |
| `Fake.call` | 18 | `self, user, item, system=None, label=None, soft=False, cache_valid=None` | Read the linked implementation and its call-site contract. |
| `RowRetryTests.test_third_try_in_smaller_batches` | 27 | `self` | Read the linked implementation and its call-site contract. |
| `RowRetryTests.test_answers_inside_schema_echo` | 38 | `self` | Read the linked implementation and its call-site contract. |

Imports: `collections`, `json`, `src.agents.base`, `unittest`

## tests/test_runtime.py

Runtime changes must preserve coverage, cache identity, evidence text, and search ranking.

[Source](../../tests/test_runtime.py) · SHA256 `0fe347e3ae9110eef2d247608f978ef5d3b8c30d48c88d352b78de8a7d54c2a5`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `row_agent` | 25 | `reply` | Read the linked implementation and its call-site contract. |
| `test_empty_answers_complete_but_missing_values_and_other_batches_retry` | 32 | `` | Read the linked implementation and its call-site contract. |
| `test_empty_string_counts_and_id_only_stays_unanswered` | 45 | `` | Read the linked implementation and its call-site contract. |
| `test_call_cache_identity_and_provenance` | 53 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_incomplete_calls_are_not_cached` | 75 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_complete_empty_row_is_cached` | 86 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_corrupt_call_cache_is_replaced` | 98 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_embedding_cache_preserves_order_and_model_namespace` | 111 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_bad_embeddings_do_not_enter_cache` | 129 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_retrieval_memory_is_scoped_by_model` | 141 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_limit_stops_pdf_fetch_but_skips_missing_pdfs` | 153 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_limit_stops_pdf_fetch_but_skips_missing_pdfs.fetch` | 159 | `paper, *args` | Read the linked implementation and its call-site contract. |
| `test_chunk_packing_preserves_text_headings_and_captions` | 172 | `` | Read the linked implementation and its call-site contract. |
| `test_empty_portal_results_expire_and_failures_are_not_cached` | 191 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_portal_jobs_are_deduplicated_across_classes` | 208 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_mds_search_preserves_metadata_and_propagates_failures` | 223 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_vector_search_matches_full_sort` | 240 | `monkeypatch, pool, restricted, ties` | Read the linked implementation and its call-site contract. |

Imports: `json`, `numpy`, `os`, `pytest`, `src`, `src.agents`, `src.agents.base`, `src.agents.extraction`, `src.tools`, `src.tools.ledger`, `time`, `unittest.mock`

## tests/test_search_diagnostics.py

Oversized queries never reach providers; repeated diagnostics remain reviewable.

[Source](../../tests/test_search_diagnostics.py) · SHA256 `88aee4ecfb6c82e67e4d6a0cc2b74faecdb1a71eba0a92fc12a7dbece0fb792e`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `test_bad_portal_queries_fail_before_network` | 16 | `monkeypatch, provider, query` | Read the linked implementation and its call-site contract. |
| `test_bad_portal_queries_fail_before_network.unexpected` | 17 | `*args, **kwargs` | Read the linked implementation and its call-site contract. |
| `test_query_boundary_and_materials_guard` | 24 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_repeated_diagnostics_are_redacted_and_thread_safe` | 34 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |

Imports: `concurrent.futures`, `json`, `logging`, `pytest`, `src.tools`

## tests/test_shared_files.py

Runs in parallel share eval_runs.csv: no row may be lost.

[Source](../../tests/test_shared_files.py) · SHA256 `b272e4698cb9e284ed204160e33c353dc27788b9acd797a9a7ff8aaac412413b`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `_write` | 14 | `args` | Read the linked implementation and its call-site contract. |
| `SharedFileTests.test_parallel_upserts_keep_every_row` | 21 | `self` | Read the linked implementation and its call-site contract. |

Imports: `csv`, `multiprocessing`, `pathlib`, `src.tools`, `tempfile`, `unittest`

## tests/test_slurm_metrics.py

Check saved environments and Slurm sweep accounting without a GPU or model server.

[Source](../../tests/test_slurm_metrics.py) · SHA256 `29ef8dcc4e228b0e653089bbcbd699a2303ff133370d7fb352b5283c498a0251`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `write` | 21 | `path, value` | Read the linked implementation and its call-site contract. |
| `samples` | 26 | `folder, name, rows` | Read the linked implementation and its call-site contract. |
| `test_environment_queries_selected_devices_and_excludes_secrets` | 34 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_missing_gpu_probe_is_nonfatal` | 60 | `monkeypatch, error` | Read the linked implementation and its call-site contract. |
| `test_run_saves_environment_before_work_and_keeps_resume_history` | 68 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_power_integral_weighted_utilization_and_allocation_totals` | 86 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_resume_sessions_do_not_bridge_idle_gaps_or_double_count_samples` | 98 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_missing_power_and_long_gaps_stay_explicit` | 110 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_failed_attempt_tokens_and_cache_hits_are_accounted_once` | 119 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_parallel_runs_use_submission_wall_and_gpu_allocation_once` | 133 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_partial_ledger_and_legacy_wall_are_labeled` | 145 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_setup_and_totals_in_both_reports_without_probe` | 156 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_bad_run_id_cannot_read_outside_outputs` | 174 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_sampler_cleanup_and_exit_status_in_bash` | 180 | `tmp_path, termination, expected` | Read the linked implementation and its call-site contract. |
| `test_slurm_retry_exports_its_reduced_worker_limit` | 216 | `tmp_path` | Read the linked implementation and its call-site contract. |

Imports: `csv`, `json`, `os`, `pathlib`, `pytest`, `shutil`, `src`, `subprocess`, `sys`, `types`, `unittest.mock`

## tests/test_speedups.py

Overload step-down, answers reused per row across runs, and calls that need two fields per row.

[Source](../../tests/test_speedups.py) · SHA256 `8a388187f51b9e8dee1852bfdb1e79531265ffa4f8dadba83c6908eff2a6bde1`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `reset_workers` | 17 | `` | Read the linked implementation and its call-site contract. |
| `test_step_down_halves_and_counts_one_burst_once` | 23 | `` | Read the linked implementation and its call-site contract. |
| `Rows.__init__` | 46 | `self, run_dir, labels` | Read the linked implementation and its call-site contract. |
| `Rows.call` | 52 | `self, user, item, system=None, label=None, soft=False, cache_valid=None` | Read the linked implementation and its call-site contract. |
| `sibling_rows` | 59 | `ids, labels, evidence=None` | One row per id; each lists the next id as a sibling, as enrichment does. |
| `row_cache` | 66 | `tmp_path, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_rows_reused_across_runs_with_renumbered_ids` | 72 | `row_cache` | Read the linked implementation and its call-site contract. |
| `test_shared_label_and_fresh_mode_are_never_reused` | 89 | `row_cache, monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_two_required_fields` | 101 | `` | Read the linked implementation and its call-site contract. |
| `test_two_required_fields.Tags.call` | 103 | `self, user, item, system=None, label=None, soft=False, cache_valid=None` | Read the linked implementation and its call-site contract. |

Imports: `json`, `pytest`, `src.agents`, `src.agents.base`, `src.tools`, `src.tools.ledger`, `threading`

## tests/test_sweep.py

Exercise the actual PowerShell driver with a fake CLI, never remote services.

[Source](../../tests/test_sweep.py) · SHA256 `0d87dc3b64ca3ebb879d26e76a68b0982005db255c596d3fc3bf4199a1cc2131`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `test_sweep_retries_skips_and_continues` | 18 | `tmp_path, extended, last_limit, shell_name` | Read the linked implementation and its call-site contract. |

Imports: `csv`, `pathlib`, `pytest`, `shutil`, `subprocess`, `sys`

## tests/test_sweep_reporting.py

Sweep reports must preserve failed attempts and consistent integration selection.

[Source](../../tests/test_sweep_reporting.py) · SHA256 `10ee648ed5accbc0e6b14962dc300a869fdc7b83f07dc989b4bf978f8ddb8c67`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `write_csv` | 11 | `path, rows` | Read the linked implementation and its call-site contract. |
| `test_integration_selection_requires_all_inputs_and_nonempty_set` | 18 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_explicit_empty_selection_does_not_load_other_runs` | 30 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_csv_keeps_one_header_and_failed_outcomes` | 40 | `tmp_path` | Read the linked implementation and its call-site contract. |
| `test_report_with_no_completed_runs_still_lists_failures` | 56 | `tmp_path` | Read the linked implementation and its call-site contract. |

Imports: `csv`, `src`, `types`

## tests/test_workers.py

Test workers support for the Knowledge Workflow system.

[Source](../../tests/test_workers.py) · SHA256 `b6f42a67604d59d7bf4889ada863d6841d66ae2debe74ae465abc518524055a5`

| Callable | Line | Signature | Summary |
|---|---:|---|---|
| `reset_workers` | 17 | `` | Read the linked implementation and its call-site contract. |
| `test_order_and_two_request_limit` | 23 | `` | Read the linked implementation and its call-site contract. |
| `test_order_and_two_request_limit.request` | 27 | `value` | Read the linked implementation and its call-site contract. |
| `test_fallback_serializes_waiting_requests` | 42 | `` | Read the linked implementation and its call-site contract. |
| `test_fallback_serializes_waiting_requests.request` | 47 | `_` | Read the linked implementation and its call-site contract. |
| `test_repeated_timeout_fallback_and_positive_workers` | 63 | `` | Read the linked implementation and its call-site contract. |
| `test_overload_retried_and_limit_stays_one` | 72 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_overload_retried_and_limit_stays_one.request` | 76 | `` | Read the linked implementation and its call-site contract. |
| `test_terminal_error_not_retried_and_transient_budget_exhausts` | 87 | `monkeypatch` | Read the linked implementation and its call-site contract. |
| `test_terminal_error_not_retried_and_transient_budget_exhausts.request` | 91 | `` | Read the linked implementation and its call-site contract. |
| `test_terminal_error_not_retried_and_transient_budget_exhausts.unavailable` | 100 | `` | Read the linked implementation and its call-site contract. |
| `test_stopping_task_does_not_submit_entire_collection` | 112 | `` | Read the linked implementation and its call-site contract. |
| `test_stopping_task_does_not_submit_entire_collection.task` | 115 | `i` | Read the linked implementation and its call-site contract. |

Imports: `concurrent.futures`, `httpx`, `openai`, `pytest`, `src.tools`, `threading`, `time`

