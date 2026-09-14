# -*- coding: utf-8 -*-
"""
Resilient agent calls (T4.2).

Wraps the agent call with exponential backoff so a transient provider error
(rate limit, 5xx, dropped connection) retries instead of crashing a whole run.
PydanticAI still does its own output-validation retries inside each call; this
adds an outer layer for transport-level failures.

Event-loop safety: `agent.run_sync()` calls `loop.run_until_complete()`, which
fails with "This event loop is already running" inside Spyder/Jupyter/IPython
(their kernel keeps an asyncio loop running). `_invoke` detects that case and
runs the async `agent.run()` in a dedicated worker thread with its own loop, so
the same code works both from the plain CLI and inside a notebook/kernel.
"""
from __future__ import annotations

import asyncio
import threading
import time

from kw.config import LLM_MAX_RETRIES, LLM_BACKOFF


def _running_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _invoke(agent, prompt: str):
    """One agent call that works whether or not an event loop is already running."""
    if not _running_loop():
        return agent.run_sync(prompt)            # plain CLI: no loop yet

    # A loop is already running (Spyder/Jupyter): run the async API in a worker
    # thread that owns a fresh event loop.
    box: dict = {}

    def _worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            box['value'] = loop.run_until_complete(agent.run(prompt))
        except Exception as exc:                  # noqa: BLE001
            box['error'] = exc
        finally:
            loop.close()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join()
    if 'error' in box:
        raise box['error']
    return box['value']


def run_sync(agent, prompt: str):
    """Call the agent, retrying transient errors with backoff.

    Re-raises the final exception if every attempt fails.
    """
    attempts = max(1, LLM_MAX_RETRIES)
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _invoke(agent, prompt)
        except Exception as exc:                      # provider/HTTP/validation errors
            last = exc
            if attempt >= attempts:
                break
            wait = LLM_BACKOFF ** attempt
            print(f'    [retry {attempt}/{attempts}] {type(exc).__name__}: {exc}; '
                  f'waiting {wait:.1f}s')
            time.sleep(wait)
    raise last  # type: ignore[misc]
