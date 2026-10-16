"""Workflow model inheritance and display changes must not break provenance joins.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from pathlib import Path
import pandas as pd
from dpv_dashboard import chat_settings, model, presentation


def test_profiles_are_read_without_import_or_environment_changes(monkeypatch):
    import os
    before = dict(os.environ)
    values = chat_settings.profiles({"VLLM_MODEL": "chosen-model"})
    assert values["ollama"]["model"] == "kw-qwen3.5-9b-32k"
    assert values["vllm"]["model"] == "chosen-model"
    assert values["gemini-lite"]["api_key_env"] == "GEMINI_API_KEY"
    assert dict(os.environ) == before


def test_chat_inherits_actual_agent_model_and_endpoint(tmp_path):
    model.write(tmp_path / "integration.json", {"config": {"llm_profile": "gemini", "model_interoperability": "workflow-agent-model",
        "llm_base_url": "https://unused.example/v1", "agent_profiles": {"interoperability": {"profile": "ollama", "provider": "openai", "base_url": "http://localhost:11434/v1"}}}})
    values = chat_settings.choices(tmp_path, None, {})
    option = values["workflow"]
    assert option["model"] == "workflow-agent-model" and option["profile"] == "ollama"
    settings, name = chat_settings.connection(option, {})
    assert settings["DPV_CHAT_BASE_URL"] == "http://localhost:11434/v1"
    assert settings["DPV_CHAT_REQUEST"]["reasoning_effort"] == "none"
    assert name == "workflow-agent-model"
    assert "DPV_CHAT_API_KEY" not in settings


def test_missing_credentials_are_friendly_and_alternatives_filtered(tmp_path):
    import pytest
    model.write(tmp_path / "run.json", {"config": {"llm_profile": "gemini", "model_interoperability": "gemini-3-flash-preview"}})
    values = chat_settings.choices(tmp_path, None, {})
    assert "workflow" in values and "gemini-lite" not in values
    with pytest.raises(ValueError) as failure:
        chat_settings.connection(values["workflow"], {})
    assert "Home" in str(failure.value)
    assert "GEMINI_API_KEY" not in str(failure.value) and "BASE_URL" not in str(failure.value)


def test_project_model_fallback_and_custom_connection(tmp_path):
    values = chat_settings.choices(tmp_path, {"profile": "ollama-lora"}, {})
    assert values["workflow"]["model"] == "kw-qwen3.5-9b-lora-32k"
    values = chat_settings.choices(None, None, {"DPV_CHAT_MODEL": "custom-model", "DPV_CHAT_BASE_URL": "http://localhost:1234/v1"})
    assert values["saved_chat"]["model"] == "custom-model"


def test_readable_table_preserves_raw_identity_and_selection():
    frame = pd.DataFrame([{"canonical_id": "k1", "source_run": "domain-one", "placement_source": "type_default", "review_flags": '["unsupported_definition"]'}])
    grid = presentation.grid(frame)
    shown = grid.data
    assert "Canonical concept ID" in shown and "canonical_id" not in shown
    assert shown.iloc[0]["Placement source"] == "Default placement by concept type"
    assert shown.iloc[0]["Review flags"] == "Definition needs supporting evidence"
    class Renderer:
        def data(self): return shown
        def data_view(self, selected): return shown.iloc[[0]].copy()
    selected = presentation.selected(Renderer())
    assert selected.iloc[0]["canonical_id"] == "k1" and selected.iloc[0]["source_run"] == "domain-one"
    assert frame.iloc[0]["placement_source"] == "type_default"
    assert presentation.heading("a_iri") == "First ontology identifier"
    assert presentation.run_label(Path("reliability-n20-20261014-154503")).startswith("Reliability · 20 papers")
    assert "20 per domain" in presentation.run_label(Path("integration-n20-20261014-154503"))
    assert presentation.ontology_label(Path("ontology.ttl")) == "Domain ontology"
    assert "Parent class needs review" in presentation.prose("Review: unresolved_parent_answer")
    assert presentation.prose("Concept: R_s and i_t") == "Concept: R_s and i_t"


def test_anthropic_chat_uses_provider_protocol_without_real_requests(monkeypatch):
    import json
    from dpv_dashboard import exploration
    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b'{"content":[{"type":"text","text":"Answer [S1]"}]}'
    def transport(request, timeout):
        calls.append((request.full_url, json.loads(request.data)))
        return Response()
    monkeypatch.setattr(exploration.urllib.request, "urlopen", transport)
    result = exploration.model_answer("solar", [{"label": "Solar cell", "text": "Saved evidence"}], {"DPV_CHAT_BASE_URL": "https://unused.example/v1", "DPV_CHAT_PROVIDER": "anthropic"}, "fixture-model")
    assert result == "Answer [S1]"
    assert calls[0][0].endswith("/messages") and "system" in calls[0][1]
def test_report_preview_styles_and_resolves_local_images_without_source_changes():
    from dpv_dashboard import presentation
    source = '<html><head></head><body><h1>Findings</h1><img src="plot.png"><table><tr><td>1</td></tr></table></body></html>'
    result = presentation.report_html(source, lambda value: '/research-media/fixture' if value == 'plot.png' else None)
    assert 'src="/research-media/fixture"' in result
    assert 'padding:18px 22px' in result and 'th,td' in result
    assert 'src="plot.png"' in source

