# Knowledge Workflow

Python pipeline for pulling papers from a Zotero group library, extracting concepts, and building structured CSV outputs for knowledge management. Built around solar cell materials research but works with any Zotero collection.

## Setup

Requires Python 3.13 and `uv`.

```bash
uv sync
.venv\Scripts\activate           # Windows
uv run python -m spacy download en_core_web_sm   # required for V1
```

## Scripts

| Script | Method | When to use |
|---|---|---|
| `knowledge_workflow_V1.py` | spaCy + TF-IDF | Fast, no API needed |
| `knowledge_workflow_V2.py` | KeyBERT | Better concept quality, still local |
| `knowledge_workflow_V3.py` | Claude (Anthropic) | Structured parameter extraction per paper |
| `knowledge_workflow_V4.py` | Claude (Anthropic) | Two-stage: concept discovery + schema population |
| `knowledge_workflow_V5.py` | Any OpenAI-compatible API | Same as V4, works with OpenAI, Groq, Ollama, etc. |

Set `collection_name` inside whichever script you're running, then:

```bash
uv run python knowledge_workflow_V4.py
```

## V5 — Provider Configuration

V5 uses the `openai` Python client and works with any service that follows the OpenAI API standard. Set these in your `.env` or as environment variables:

```
LLM_BASE_URL=https://api.openai.com/v1   # or any compatible endpoint
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
```

Common endpoints:

| Provider | Base URL | Example model |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Anthropic | `https://api.anthropic.com/v1` | `claude-sonnet-4-6` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| Together AI | `https://api.together.xyz/v1` | `meta-llama/Llama-3-70b-chat-hf` |
| Mistral | `https://api.mistral.ai/v1` | `mistral-large-latest` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.2` |
| LM Studio | `http://localhost:1234/v1` | *(your loaded model)* |

If your model doesn't support forced tool choice, set `FORCE_TOOL_CHOICE = False` in the script.

## Outputs

All scripts write to `outputs/<collection>/`. Schema files are also copied to `schemas/<collection>/` for reuse in later runs.

File naming: `{type}_{collection}-{username}-v{version}-{YYYYMMDD}.csv`

Types: `extraction`, `concepts`, `rankings`, `ontology`, `schema`

## Credentials

- Zotero API key: set `ZOTERO_API_KEY` in `.env` (V5) or `API_KEY` constant (V1–V4)
- Anthropic API key: set `ANTHROPIC_API_KEY` in `.env` (used by V3/V4 natively; V5 picks it up automatically when `LLM_API_KEY` is not set)
- Zotero group library ID: `2189702`

Don't commit API keys.

## schemas/

Reference CSVs used to supply a fixed concept list instead of auto-extracting. Point `CONCEPTS_CSV_PATH` at one to skip Phase 1 in V4/V5.
