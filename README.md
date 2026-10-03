# Knowledge Workflow

This repository now contains the implementation migrated from `opus_knowledge_workflow`. The former `kw/` and Kweave implementations are deprecated; their committed history remains available in Git. New development and runs use this checkout.

The pipeline selects literature from Zotero, extracts concepts and claims, normalizes them, builds and enriches a domain ontology, and exports OWL JSON-LD/Turtle plus an evidence-preserving literature layer. Run reports and the cross-run eval dataset remain local under `outputs/`.

## Setup and run

```powershell
uv venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally with the credentials required by your providers and Zotero. Skip the copy if `.env` already exists. Credentials, runtime environments, caches, PDFs, and generated results are excluded from Git.

For Gemini hybrid routing, keep Ollama running with the configured local model and embedding model:

```powershell
$env:LLM_PROFILE = "gemini"  # or gemini-lite
.\.venv\Scripts\python.exe -m src.run all --collection si-topcon --limit 1
```

Extraction and interoperability run locally. Normalization, ontology, and enrichment use Gemini with persistent quota accounting. See [Gemini setup](GEMINI.md), [hybrid routing](GEMINI_HYBRID.md), and [ontology revision](ONTOLOGY_REVISION.md).

Start a new run without `--run-id` to use the latest workflow revision and preserve older results. Its first run adds a workflow-change event to the local eval dataset. Structural validation is included; semantic correctness and reasoner validation are not established by that check.

## Migration

The migration preserves the existing GitHub repository and history. `legacy/pre-opus-20261003` records the pre-migration commit. The original checkout's files, uncommitted changes, credentials, environment, and outputs were preserved locally at `C:\Users\brent\dev\knowledge_workflow_legacy_20261003`. The Opus folder remains untouched as the source copy.

Existing Opus outputs and quota state were copied into this checkout locally. Legacy outputs remain in the separate backup. No tests or live model requests were run during migration. A hardcoded demo-key fallback was removed before publication; callers must supply their configured MDS API key.
