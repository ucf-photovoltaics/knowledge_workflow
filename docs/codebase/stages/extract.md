# Worked task: Create evidence-backed per-paper records

Author: Brent Thompson <brent.thompson@ucf.edu>

This is a source-reviewed operational recipe, not a claim that a new model or literature run was executed. The ontology embeds this text and fingerprints the source. Scientific acceptance and live readiness remain separate checks.

## Research task and discovery

A selected paper contains TOPCon device concepts, reported efficiency measurements and a captioned figure. The orchestrator combines source metadata with parser output before supplying one paper dictionary to ExtractionAgent.run.

Start at `kw:CodebaseDocumentation` → `documentsWorkflow` → `hasStep` → `kw:step/extract`. Read its `skos:definition`, `contractJson`, `hasDataBinding`, `hasOperation`, `hasCheck` and `hasRecovery` links. Follow `implementedBy`/`operationImplementation` to source callables, `hasArgument` to formal names/types/defaults and `bindsArtifact` to source/output artifact specifications. Artifact incoming links identify producers and consumers.

## Bind and initialize

One parsed paper dictionary, including source metadata, sections and figures, is passed to the agent. The saved paper record is composed by the orchestrator, not returned wholesale by the agent.

| Input | Required shape or origin |
|---|---|
| `paper` | {key,title,sections:[{heading,text}],figures:[{id,caption}], source metadata} |
| `saved measurements` | concept stores the property concept ID; entity is optional |

Instantiate ExtractionAgent(run.ledger) under the configured profile. Use CLI extract for combined selection/parsing/extraction or wrapper extract after separately completed ingestion/parsing.

Side effects: The agent writes extraction cache and ledger records. src.run.extract writes finalized papers and updates corpus selection/failures; wrapper raises after partial extraction.

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
  "extract",
  "--collection",
  "COLLECTION",
  "--run-id",
  "RUN_ID",
  "--limit",
  "15",
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
  "extract"
]
```

### Data bindings

| Direction | Saved or explicit input | Selector → callable value | Adaptation |
|---|---|---|---|
| input | `parsed/*.json` | `$` → `src/agents/extraction.py:ExtractionAgent.run` / `paper` | CLI constructs paper context from selected PDFs and parser output; wrapper can reuse parsed records. This port describes parser context, not independent CLI parse completion. Mode: wrapper. |
| output | `papers/*.json` | `$` → `src/run.py:extract` / `record` | One finalized record per paper; cache/failed-paper handling belongs to the orchestrator. |
| input | `explicit CLI collection selection or wrapper ingestion papers` | `$` → `src/run.py:extract` / `papers, selection` | CLI select_papers selects/caches its corpus; wrapper overrides selection and parser adapters to reuse ingestion/parsed products. |
| output | `run.json` | `$.corpus` → `src/run.py:extract` / `run.manifest.corpus` | Record selected items, processed/failed papers and corpus hash separately from each saved paper. |
| output | `compute_per_paper.csv` | `$` → `src/run.py:extract` / `reports.paper_compute(...)` | Save per-paper compute from finalized records and ledger summaries; not evidence of scientific quality. |

## Follow the source operations

The sequence describes the implemented plan. Profile-dependent branches and guarded optional operations are stated explicitly; it does not assert that every branch runs in every attempt.

1. **Select corpus and parse under lock** — `src/run.py:extract`. Obtain selected source metadata and parse each PDF under the PyMuPDF lock; the wrapper supplies saved selection/parser adapters.

2. **Check extraction cache** — `src/agents/extraction.py:ExtractionAgent.run`. Calculate the text/prompt/model/settings fingerprint; reuse a matching cache with zero new model tokens, otherwise process all text windows.

3. **Build windows** — `src/agents/extraction.py:ExtractionAgent._chunks`. Regenerate chunk strings from paper sections/title/cited captions under the current extraction profile.

4. **Extract combined or narrow passes** — `src/agents/extraction.py:ExtractionAgent._multi_pass`. Local-tier windows extract concepts first then relations/causal/measurements against numbered concepts; frontier-tier run instead uses the combined prompt. These are alternative branches.

5. **Request missing evidence** — `src/agents/extraction.py:ExtractionAgent._fill_evidence`. Re-ask claims missing a usable quote once, using section text and the concept labels. A filled quote still requires verification.

6. **Reconcile one paper** — `src/agents/extraction.py:ExtractionAgent._merge`. Merge all windows into one concept vocabulary, remap endpoints by IDs/labels/synonyms, retain unresolved-end findings and deduplicate claims.

7. **Verify quotes and figure links** — `src/agents/extraction.py:ExtractionAgent._finalize`. Check evidence word-trigram overlap against source text; attach status and parser figure links. Quote overlap is not entailment or numeric validation.

8. **Persist corpus results and failures** — `src/run.py:extract`. Combine source metadata with agent result and parse_stats, save papers/<key>.json, compute and uncertainty records. Failed papers remain in manifest.corpus.failed; CLI may record partial completion.

## Handle the return and persistence

- concepts
- relations
- causal
- measurements
- figures
- resolution
- unresolved_ends
- verification
- checks
- n_chunks
- extraction_tier
- extraction_passes
- raw_calls
- compute
- cache_hit on reuse

The agent result omits source metadata until src.run.extract composes the saved record. Raw measurement property becomes saved concept. Quotes may match text without supporting the asserted relationship. Inspect unresolved ends and failures.

## Assess and choose the next action

Run the read-only helper from the repository root in the documentation environment. `RUN_FOLDER` means an existing run-relative directory under the selected outputs root, not a guessed future run. Guide retrieval requires no run folder. Use the integration folder for integration, the report folder or domain root for reports, and the domain attempt for other stages.

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py guide --step extract
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step extract --phase before
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/ontology_agent.py assess --run RUN_FOLDER --step extract --phase after
```

The helper never runs pipeline commands or repairs data. `blocked` stops the proposed advance; `runtime-check` requires real environment/scope checks; `review` requires evidence or domain review. A successful bounded predicate does not certify all schema fields or scientific meaning. File hashes are rechecked to detect changes during observation.

| Check | Phase | Scope |
|---|---|---|
| `shape-papers-all` (shape) | after | papers/*.json |
| `saved-paper-contract` (paper_contract) | after | Saved joins |
| `selected-extracted-coverage` (corpus_coverage) | after | papers/*.json |
| `review-findings` (scientific_review) | after | Review unevidenced claims, unresolved endpoints, malformed or overly broad concepts, measurement property/entity assignments, figure links and failed calls. Verified text overlap alone is insufficient. |

Completion rule: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: Inspect failed papers and verification flags; resume/retry extraction under the selected controller before normalization.

Limit: Quote overlap does not establish entailment; partial CLI extraction may still be recorded complete.

Follow `canAdvanceTo` to the next conceptual stage and inspect its mode-specific prerequisites. A rerun requires freshness review of stages linked by `invalidatesStep`; the documentation helper never deletes or reruns them. For reports, completion ends this task; integration is optional when only one domain exists.

## WebVOWL review

At http://127.0.0.1:8058/, select **Extract evidence-backed paper records** (its shortened tab label may differ). Start with Data flow to trace saved values, switch to Implementation for source operations, and select a function for its definition, formal arguments and fingerprinted source lines. The stage inspector links this worked example. Checks show before/after scope; runtime-only conditions remain visible. Use bounded Code lookup for connected records instead of loading all code nodes at once.
