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
