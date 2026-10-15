"""Ordered task workers and a run-wide adaptive limit for local model requests (halved on overload)."""
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from contextlib import contextmanager
from threading import Condition

from src.tools.progress import log

requested = 2
active_limit = 2
_active = 0
_timeouts = 0
_generation = 0  # bumped at every step-down
_condition = Condition()
events = []


def configure(count: int):
    global requested, active_limit, _timeouts, _generation
    if count < 1:
        raise ValueError("Workers must be positive")
    with _condition:
        if _active:
            raise RuntimeError("Cannot change workers during model requests")
        requested = active_limit = count
        _timeouts = 0
        _generation += 1
        events.clear()


def fallback(reason: str, timeout: bool = False, generation: int | None = None):
    """Halve the request limit (8 -> 4 -> 2 -> 1) after an overload, a memory error or a second timeout.
    Requests already in flight when the limit last changed (an older generation) do not lower it again, so one
    burst of failures counts once."""
    global active_limit, _timeouts, _generation
    with _condition:
        if generation is not None and generation != _generation:
            return
        if timeout:
            _timeouts += 1
            if _timeouts < 2:
                return
        if active_limit > 1:
            active_limit = max(1, active_limit // 2)
            _timeouts = 0
            _generation += 1
            events.append({"workers": active_limit, "reason": reason})
            log(f"model overload: {reason}; reducing model concurrency to {active_limit} for this run")
            _condition.notify_all()


@contextmanager
def slot():
    """One model request; yields the limit generation it started under (pass it to fallback)."""
    global _active
    with _condition:
        _condition.wait_for(lambda: _active < active_limit)
        _active += 1
        generation = _generation
    try:
        yield generation
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
