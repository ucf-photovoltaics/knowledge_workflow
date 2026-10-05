import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import openai
import pytest

from src.tools import llm, workers


@pytest.fixture(autouse=True)
def reset_workers():
    workers.configure(2)
    yield
    workers.configure(2)


def test_order_and_two_request_limit():
    lock = threading.Lock()
    active = maximum = 0

    def request(value):
        nonlocal active, maximum
        with workers.slot():
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(.02)
            with lock:
                active -= 1
        return value

    assert workers.ordered(request, range(6)) == list(range(6))
    assert maximum == 2


def test_fallback_serializes_waiting_requests():
    workers.fallback('HTTP 503')
    lock = threading.Lock()
    active = maximum = 0

    def request(_):
        nonlocal active, maximum
        with workers.slot():
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(.01)
            with lock:
                active -= 1

    with ThreadPoolExecutor(4) as executor:
        list(executor.map(request, range(8)))
    assert maximum == 1
    assert len(workers.events) == 1


def test_repeated_timeout_fallback_and_positive_workers():
    workers.fallback('timeout', timeout=True)
    assert workers.active_limit == 2
    workers.fallback('timeout', timeout=True)
    assert workers.active_limit == 1
    with pytest.raises(ValueError):
        workers.configure(0)


def test_overload_retried_and_limit_stays_one(monkeypatch):
    response = httpx.Response(503, request=httpx.Request('POST', 'http://localhost'))
    calls = []

    def request():
        calls.append(workers.active_limit)
        if len(calls) == 1:
            raise openai.InternalServerError('overloaded', response=response, body=None)
        return 'ok'

    monkeypatch.setattr(llm.time, 'sleep', lambda _: None)
    assert llm._outage_safe({'outage_wait_s': 900}, request) == 'ok'
    assert calls == [2, 1]


def test_terminal_error_not_retried_and_transient_budget_exhausts(monkeypatch):
    response = httpx.Response(401, request=httpx.Request('POST', 'http://localhost'))
    calls = []

    def request():
        calls.append(1)
        raise openai.AuthenticationError('unauthorized', response=response, body=None)

    with pytest.raises(openai.AuthenticationError):
        llm._outage_safe({'outage_wait_s': 900}, request)
    assert len(calls) == 1
    calls.clear()

    def unavailable():
        calls.append(1)
        raise openai.APIConnectionError(request=httpx.Request('POST', 'http://localhost'))

    monkeypatch.setattr(llm.time, 'sleep', lambda _: None)
    with pytest.raises(openai.APIConnectionError):
        llm._outage_safe({'outage_wait_s': 900}, unavailable)
    assert len(calls) == 3
    # Slot release must survive exceptions.
    workers.configure(1)


def test_stopping_task_does_not_submit_entire_collection():
    started = []

    def task(i):
        started.append(i)
        if i == 0:
            raise ValueError('stopping failure')
        return i

    with pytest.raises(ValueError):
        workers.ordered(task, range(50))
    assert len(started) <= 2
