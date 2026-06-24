# -*- coding: utf-8 -*-
"""
Resilient agent calls (T4.2).

Wraps `agent.run_sync(prompt)` with exponential backoff so a transient provider
error (rate limit, 5xx, dropped connection) retries instead of crashing a whole
run. PydanticAI still does its own output-validation retries inside each call;
this adds an outer layer for transport-level failures.
"""
from __future__ import annotations

import time

from kw.config import LLM_MAX_RETRIES, LLM_BACKOFF


def run_sync(agent, prompt: str):
    """Call agent.run_sync(prompt), retrying transient errors with backoff.

    Re-raises the final exception if every attempt fails.
    """
    attempts = max(1, LLM_MAX_RETRIES)
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return agent.run_sync(prompt)
        except Exception as exc:                      # provider/HTTP/validation errors
            last = exc
            if attempt >= attempts:
                break
            wait = LLM_BACKOFF ** attempt
            print(f'    [retry {attempt}/{attempts}] {type(exc).__name__}: {exc}; '
                  f'waiting {wait:.1f}s')
            time.sleep(wait)
    raise last  # type: ignore[misc]
