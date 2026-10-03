# Gemini hybrid workflow

Implemented in `C:\Users\brent\dev\knowledge_workflow`.

When `LLM_PROFILE` is `gemini` or `gemini-lite`:

| Agent | Profile | Work |
|---|---|---|
| Extraction | ollama | Local split-pass paper extraction |
| Normalization | selected Gemini | Semantic merge review, type conflicts, corpus summary |
| Ontology | selected Gemini | Hierarchy and upper-category selection |
| Enrichment | selected Gemini | Definitions, synonym filtering, relation-property selection |
| Interoperability | ollama | Local mapping/filter passes and facets |

Embeddings retain their existing local configuration. Gemini calls keep persistent quota accounting. Other active profiles retain their existing routing.

## Use

Keep Ollama running with `kw-qwen3.5-9b-32k` and the configured embedding model `nomic-embed-text`. Keep `GEMINI_API_KEY` in the repository's `.env`.

```powershell
Set-Location C:\Users\brent\dev\knowledge_workflow
$env:LLM_PROFILE = "gemini"
.\.venv\Scripts\python.exe -m src.run all --collection si-topcon --limit 1
```

Use `gemini-lite` instead to select Flash-Lite for the three frontier stages. No manual profile switching between stages is needed.

`AGENT_PROFILES` in `src/config.py` controls local routing. Change its `ollama` entries to `ollama-lora` if you intend to use the adapter profile and have that model installed. Leave `PIPELINE_TIER = None` to get each profile's intended passes. `AGENT_MODELS` overrides the model within the agent's routed endpoint, so its names must be available on that endpoint.

## Synonym correction

Normalization automatically groups matching normalized labels and plurals only. An extracted synonym list can no longer union distinct concepts through transitive links. The existing embedding candidate/model-review path still performs semantic merges; raw synonym strings remain available as alternative-label candidates for enrichment to filter. They are not independently guaranteed correct.

If embeddings are disabled or unavailable, semantic candidate generation is skipped, and matching synonyms with different wording can remain separate. The change deliberately prefers preserving distinct concepts over silently collapsing them.

## Existing runs

Resuming `all --run-id` skips stages already marked complete, so it does not repair their old normalization. To reuse paper extraction but regenerate subsequent results, run these stages explicitly, retaining the profile above:

```powershell
.\.venv\Scripts\python.exe -m src.run normalize --run-id YOUR_RUN_ID
.\.venv\Scripts\python.exe -m src.run ontology --run-id YOUR_RUN_ID
.\.venv\Scripts\python.exe -m src.run enrich --run-id YOUR_RUN_ID
.\.venv\Scripts\python.exe -m src.run interop --run-id YOUR_RUN_ID
```

These commands replace those stages' saved artifacts in the selected run. A new run is preferable if you need to preserve the old results for comparison. Gemini daily blocks remain in force for frontier stages; local interoperability can continue independently when its enrichment inputs already exist.

## Changes

- `src/agents/normalization.py`: removed synonym-based automatic unions and corrected the progress message.
- `src/config.py`: per-agent profile selection, model selection, and tier selection.
- `src/agents/base.py` and `src/tools/llm.py`: pass the agent's profile to the request client; cache clients by endpoint/provider and retain Gemini quota protection.
- `src/agents/extraction.py`: local extraction tier and local input budget.
- `src/agents/ontology.py`, `enrichment.py`, `interoperability.py`: use each agent's tier.
- `src/run.py`: stage routing in logs, run configuration, completion metadata, and extraction preflight.
- `tests/test_gemini_quota.py`: updated existing mocks for the new client routing interface; not executed.

Source was reviewed as text. No tests, workflow runs, or API calls were executed for this change.
