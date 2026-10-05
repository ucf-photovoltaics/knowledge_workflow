"""Ordered task workers and a run-wide adaptive limit for local model requests."""
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from contextlib import contextmanager
from threading import Condition

from src.tools.progress import log

requested = 2
active_limit = 2
_active = 0
_timeouts = 0
_condition = Condition()
events = []


def configure(count: int):
    global requested, active_limit, _timeouts
    if count < 1:
        raise ValueError("Workers must be positive")
    with _condition:
        if _active:
            raise RuntimeError("Cannot change workers during model requests")
        requested = active_limit = count
        _timeouts = 0
        events.clear()


def fallback(reason: str, timeout: bool = False):
    global active_limit, _timeouts
    with _condition:
        if timeout:
            _timeouts += 1
            if _timeouts < 2:
                return
        if active_limit > 1:
            active_limit = 1
            events.append({"workers": 1, "reason": reason})
            log(f"model overload: {reason}; reducing model concurrency to 1 for this run")
            _condition.notify_all()


@contextmanager
def slot():
    global _active
    with _condition:
        _condition.wait_for(lambda: _active < active_limit)
        _active += 1
    try:
        yield
    finally:
        with _condition:
            _active -= 1
            _condition.notify_all()


def ordered(function, values):
    """Return results in input order; dependent work stays inside each task."""
    if requested == 1:
        return [function(value) for value in values]
    values = iter(values)
    pending, results = deque(), []
    with ThreadPoolExecutor(max_workers=requested) as executor:
        try:
            for _ in range(requested):
                try:
                    pending.append(executor.submit(function, next(values)))
                except StopIteration:
                    break
            while pending:
                results.append(pending.popleft().result())
                try:
                    pending.append(executor.submit(function, next(values)))
                except StopIteration:
                    pass
        finally:
            for future in pending:
                future.cancel()
    return results


def summary():
    return {"requested": requested, "active_model_limit": active_limit, "fallbacks": list(events)}
