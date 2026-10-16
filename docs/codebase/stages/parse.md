# Worked task: Prepare text windows without extracting claims

Author: Brent Thompson <brent.thompson@ucf.edu>

This is a source-reviewed operational recipe, not a claim that a new model or literature run was executed. The ontology embeds this text and fingerprints the source. Scientific acceptance and live readiness remain separate checks.

## Research task and discovery

A wrapper attempt contains ingestion.json with selected source PDFs. Discover each papers[*].pdf and paper key, read its bytes for the source hash, then parse and chunk under the current extraction profile.

Start at `kw:CodebaseDocumentation` → `documentsWorkflow` → `hasStep` → `kw:step/parse`. Read its `skos:definition`, `contractJson`, `hasDataBinding`, `hasOperation`, `hasCheck` and `hasRecovery` links. Follow `implementedBy`/`operationImplementation` to source callables, `hasArgument` to formal names/types/defaults and `bindsArtifact` to source/output artifact specifications. Artifact incoming links identify producers and consumers.

## Bind and initialize

Selected paper PDF paths come from wrapper ingestion.json. The deterministic parser returns sections, figures and parse_stats; the wrapper separately hashes PDFs and calculates chunks.

| Input | Required shape or origin |
|---|---|
| `paper.pdf` | local PDF path from ingestion papers |
| `sections[]` | parser {heading,text} records |
| `figures[]` | parser {id,label,page,caption,mentions} records |

Use worker stage parse after ingestion. It constructs only the chunker profile, without a model instance; CLI extract performs this operation internally.

Side effects: Reads PDFs and writes parsed/<key>.json. An existing matching PDF hash skips work; that shortcut does not fingerprint chunker profile changes.

### Trusted execution entry points

The following are **unbound argument-vector templates** from workflow.json. Resolve every uppercase placeholder using actual authorized selections; do not execute these literal placeholders. Prefer the existing controller to direct callable invocation. `ontology_agent.py plan` can bind/check templates without executing them. Credentials remain in the runtime.

No separate CLI invocation is defined for this stage.

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
  "parse"
]
```

CLI mode performs this operation inside extraction; do not call extract repeatedly to simulate separate ingestion/parsing commands.

### Data bindings

| Direction | Saved or explicit input | Selector → callable value | Adaptation |
|---|---|---|---|
| input | `ingestion.json` | `$.papers[*].pdf` → `src/tools/pdf_parse.py:parse` / `pdf_path` | For each selected paper, read the PDF path; wrapper saves parser/chunker output in parsed/<key>.json. Mode: wrapper. |
| input | `ingestion.json` | `$.papers` → `src/agents/extraction.py:ExtractionAgent._chunks` / `paper` | Combine each selected paper title with parsed sections/figures; the worker passes this in-memory dictionary to the configured chunker. Mode: wrapper. |
| output | `parsed/*.json` | `$` → `dpv_dashboard/worker.py:parse` / `parsed, digest, chunks` | Persist parser fields plus key/title, SHA256 of the PDF and chunk strings. These separate products are wrapper-specific. |

## Follow the source operations

The sequence describes the implemented plan. Profile-dependent branches and guarded optional operations are stated explicitly; it does not assert that every branch runs in every attempt.

1. **Resolve selected PDFs and hashes** — `dpv_dashboard/worker.py:parse`. Load ingestion papers and fingerprint each PDF. Reuse an existing parsed record only when its recorded PDF hash matches.

2. **Clean and section PDF text** — `src/tools/pdf_parse.py:parse`. Read text blocks, remove short repeated headers/footers and page numbers, detect headings and omit configured back matter.

3. **Retain captions and mentions** — `src/tools/pdf_parse.py:parse`. Capture figure number, one-based page and caption; attach up to three citing sentences. No image crop or exact bounding box is produced here.

4. **Build extraction windows** — `src/agents/extraction.py:ExtractionAgent._chunks`. Pack adjacent sections, split oversized text and include title/cited captions within the configured input budget; fail if the budget is too small.

5. **Persist wrapper intermediates** — `dpv_dashboard/worker.py:parse`. Save sections, figures, parse_stats, key/title, PDF hash and chunks. Extraction recalculates chunks from sections rather than trusting saved chunks as its direct argument.

## Handle the return and persistence

- parse(pdf_path): {sections,figures,parse_stats}
- _chunks(paper): list[str]
- worker.parse: None; persisted parser record

Saved chunks are useful inspection artifacts, but ExtractionAgent.run rebuilds windows from sections/figures. PDF-hash reuse alone does not detect a changed chunker profile. CLI extraction does not require parsed/*.json.

## Assess and choose the next action

Run the read-only helper from the repository root in the documentation environment. `RUN_FOLDER` means an existing run-relative directory under the selected outputs root, not a guessed future run. Guide retrieval requires no run folder. Use the integration folder for integration, the report folder or domain root for reports, and the domain attempt for other stages.

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py guide --step parse
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step parse --phase before
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step parse --phase after
```

The helper never runs pipeline commands or repairs data. `blocked` stops the proposed advance; `runtime-check` requires real environment/scope checks; `review` requires evidence or domain review. A successful bounded predicate does not certify all schema fields or scientific meaning. File hashes are rechecked to detect changes during observation.

| Check | Phase | Scope |
|---|---|---|
| `shape-parsed-all` (shape) | after | parsed/*.json |
| `parser-sections` (shape) | after | parsed/*.json |
| `parser-figures` (shape) | after | parsed/*.json |
| `selected-parsed-coverage` (corpus_coverage) | after | parsed/*.json |
| `review-findings` (scientific_review) | after | Review retained text, missing captions, scanned PDFs, over-aggressive back-matter removal and window sizes. Text extraction is not OCR or figure localization. |

Completion rule: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: Inspect missing/corrupt PDFs and PDF hashes; retry parsing for affected inputs before extraction.

Limit: Retained captions do not establish exact bounding boxes or assertion correctness.

Follow `canAdvanceTo` to the next conceptual stage and inspect its mode-specific prerequisites. A rerun requires freshness review of stages linked by `invalidatesStep`; the documentation helper never deletes or reruns them. For reports, completion ends this task; integration is optional when only one domain exists.

## WebVOWL review

At http://127.0.0.1:8058/, select **Parse PDFs and prepare text windows** (its shortened tab label may differ). Start with Data flow to trace saved values, switch to Implementation for source operations, and select a function for its definition, formal arguments and fingerprinted source lines. The stage inspector links this worked example. Checks show before/after scope; runtime-only conditions remain visible. Use bounded Code lookup for connected records instead of loading all code nodes at once.
