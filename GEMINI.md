# Gemini free-plan tests

Changes are in `C:\Users\brent\dev\knowledge_workflow`.

## Limits configured

| Profile | Model | RPM | Input TPM | RPD |
|---|---|---:|---:|---:|
| gemini | gemini-3-flash-preview | 10 | 250,000 | 1,500 |
| gemini-lite | gemini-3.1-flash-lite | 15 | Unspecified | 1,000 |

These are your requested ceilings, not a claim about the quota assigned to your Google project. Check your project's active limits in AI Studio and lower `GEMINI_LIMITS` in `src/config.py` if necessary. Add Flash-Lite's TPM there when known.

## What to do

1. Put your Gemini key in the repository's `.env` under `GEMINI_API_KEY`, using your editor. Do not paste it into chat or commit it. Existing Zotero credentials are also required for collection tests.
2. In PowerShell:

```powershell
Set-Location C:\Users\brent\dev\knowledge_workflow
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
$env:LLM_PROFILE = "gemini"
.\.venv\Scripts\python.exe -m src.run all --collection si-topcon --limit 1
```

For Flash-Lite, change only the profile:

```powershell
$env:LLM_PROFILE = "gemini-lite"
.\.venv\Scripts\python.exe -m src.run all --collection si-topcon --limit 1
```

The existing embeddings setting uses local Ollama (`nomic-embed-text`). Keep that service running, or explicitly set `EMBED["model"] = None` in `src/config.py` to use lexical-only candidate handling. These chat-model limits do not apply to embeddings.

## Expected behavior

- Flash requests are spaced at least 6.1 seconds apart; Flash-Lite at least 4.1 seconds, with an additional rolling-minute check.
- Flash also waits when its conservative input-token reservation would exceed 250,000 TPM. The estimate uses UTF-8 byte length plus framing overhead, so it can wait more than Google's exact tokenizer requires. A single input above that estimate budget fails before sending; reduce its batch/input size.
- Every attempt, including retries and unsuccessful requests, reserves quota before sending. SDK retries are disabled for Gemini so no hidden requests bypass the limiter.
- Temporary 429, server, and connection errors retry a bounded number of times, honoring Retry-After or provider retry delays when available. Persistent transient failures stop the run rather than skip remaining papers.
- Daily exhaustion stops the run immediately. Counters and provider-reported daily blocks persist in `outputs/cache/gemini_quota.sqlite3`; they reset by date at midnight America/Los_Angeles, including daylight-saving time. Do not delete this file to bypass limits.
- Resume after the reset with the run ID printed at startup, retaining the original limit:

```powershell
.\.venv\Scripts\python.exe -m src.run all --run-id YOUR_RUN_ID --limit 1
```

Completed stages are skipped. An interrupted stage restarts; completed extraction results can be reused through the existing paper cache. This is stage/paper-level resume, not resume midway through an API call or enrichment batch.

Quota state is shared by processes using this checkout and grouped by model. Calls from other applications/checkouts are invisible to the local counter; Google's responses remain authoritative. Sharing a key does not provide an extra quota because Google applies quotas at project level.

## Change locations and checks

- `src/config.py`: two Gemini profiles, explicit ceilings, and environment-based profile selection. The existing default stays Ollama.
- `src/tools/gemini_quota.py`: persistent SQLite reservations, rolling-minute pacing, Pacific daily accounting, and bounded retries.
- `src/tools/llm.py`: Gemini calls use the limiter and send an output-token cap; other providers retain their existing request path.
- `src/run.py`: propagates quota/transient terminal errors so extraction stops without being marked complete.
- `requirements.txt`: adds `tzdata` for Pacific time on Windows.
- `tests/test_gemini_quota.py`: offline regression tests using simulated time and API responses.

No live Gemini requests were made during implementation.

Google references: [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [Flash model ID](https://ai.google.dev/gemini-api/docs/models/gemini-3-flash-preview), [Flash-Lite model ID](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite).
