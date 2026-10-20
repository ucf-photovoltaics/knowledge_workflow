"""A 500 from a live model server costs one answer, not the run (pv-cost-chain-gptoss-20b-n50: vLLM rejected
gpt-oss tool-call tokens under the JSON grammar and every domain stopped)."""
from types import SimpleNamespace

import openai
import pytest

from src.tools import llm

PROFILE = {"provider": "openai", "base_url": "http://localhost:1/v1", "outage_wait_s": 900, "request": {}}


def server_error():
    response = SimpleNamespace(status_code=500, headers={}, request=SimpleNamespace(method="POST", url=PROFILE["base_url"]))
    return openai.InternalServerError("Internal server error", response=response, body=None)


class Client:
    def __init__(self):
        self.calls = 0
        self.chat = self
        self.completions = self

    def create(self, **kw):
        self.calls += 1
        raise server_error()


def test_request_failure_on_live_server_is_an_unusable_reply(monkeypatch):
    client = Client()
    monkeypatch.setattr(llm, "_get_client", lambda profile: client)
    monkeypatch.setattr(llm, "_server_alive", lambda profile: True)
    monkeypatch.setattr(llm.time, "sleep", lambda s: pytest.fail("must not wait for an outage"))
    text, usage = llm.chat("Return ONLY JSON.", "{}", "m", profile=PROFILE)
    assert text == "" and usage.output_tokens == 0
    assert client.calls == 1


def test_server_down_still_raises(monkeypatch):
    monkeypatch.setattr(llm, "_get_client", lambda profile: Client())
    monkeypatch.setattr(llm, "_server_alive", lambda profile: False)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    with pytest.raises(openai.InternalServerError):
        llm.chat("Return ONLY JSON.", "{}", "m", profile=PROFILE)


CONTEXT = ("This model's maximum context length is 24576 tokens. However, you requested 8000 output tokens and your "
           "prompt contains 16757 input tokens, for a total of 24757 tokens.")


def context_error():
    response = SimpleNamespace(status_code=400, headers={}, request=SimpleNamespace(method="POST", url=PROFILE["base_url"]))
    return openai.BadRequestError(CONTEXT, response=response, body=None)


def test_prompt_too_long_for_max_tokens_is_retried_with_the_room_left(monkeypatch):
    sent = []

    class Fits(Client):
        def create(self, **kw):
            sent.append(kw.get("max_tokens"))
            if len(sent) == 1:
                raise context_error()
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
                                   usage=SimpleNamespace(prompt_tokens=16757, completion_tokens=2))
    monkeypatch.setattr(llm, "_get_client", lambda profile: Fits())
    text, _ = llm.chat("Return ONLY JSON.", "{}", "m", profile={**PROFILE, "request": {"max_tokens": 8000}})
    assert text == "{}" and sent == [8000, 24576 - 16757 - 16]


def test_prompt_filling_the_context_is_an_unusable_reply(monkeypatch):
    monkeypatch.setattr(llm, "_context_room", lambda message: 200)

    class Full(Client):
        def create(self, **kw):
            raise context_error()
    monkeypatch.setattr(llm, "_get_client", lambda profile: Full())
    text, usage = llm.chat("Return ONLY JSON.", "{}", "m", profile=PROFILE)
    assert text == "" and usage.output_tokens == 0
