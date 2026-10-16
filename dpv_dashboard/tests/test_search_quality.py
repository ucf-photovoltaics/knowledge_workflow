"""Test search quality support for the Knowledge Workflow system.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock
from dpv_dashboard import exploration, model, quality, research


BAD = (Path(__file__).parent / "fixtures/malformed-label.txt").read_text(encoding="utf-8")


def test_actual_malformed_label_and_flags_never_enter_chat(monkeypatch):
    assert len(BAD) == 17513
    rows = [{"label": BAD, "text": BAD}, {"label": "Flagged", "quality_flags": ["needs_review"], "text": "Do not use"},
            {"label": "Solar cell", "text": "Saved paper evidence"}]
    assert len(exploration.search(rows, "solar")) == 1
    answer = exploration.evidence_answer("solar", rows)
    assert BAD not in answer and "Flagged" not in answer
    capture = []
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b'{"choices":[{"message":{"content":"Answer [S1]"}}]}'
    def transport(request, timeout):
        capture.append(json.loads(request.data))
        return Reply()
    monkeypatch.setattr(exploration.urllib.request, "urlopen", transport)
    exploration.model_answer("solar", rows, {"DPV_CHAT_BASE_URL": "http://localhost:0/v1"}, "fixture")
    packet = json.loads(capture[0]["messages"][1]["content"])
    assert len(packet["records"]) == 1 and packet["records"][0]["label"] == "Solar cell"
    forbidden = Mock(side_effect=AssertionError("No model call with zero clean evidence"))
    monkeypatch.setattr(exploration.urllib.request, "urlopen", forbidden)
    assert "No matching saved evidence" in exploration.model_answer("solar", rows[:2], {}, "")


def test_documents_exclude_source_and_rdf_copies_without_writing(tmp_path):
    source = tmp_path / "source"
    model.write(source / "run.json", {})
    model.write(source / "papers/P1.json", {"key": "P1", "title": "Valid paper", "concepts": [{"id": "c1", "label": BAD}, {"id": "c2", "label": "Solar cell"}],
        "relations": [{"s": "c2", "o": "c1", "p": "connects", "evidence": "Raw bad dependency"}]})
    model.write(source / "ontology/classes.json", [{"id": "k1", "label": BAD, "iri": "urn:bad"}, {"id": "k2", "label": "Solar cell", "iri": "urn:good", "papers": ["P1"]}])
    path = source / "ontology.ttl"
    path.write_text('@prefix owl: <http://www.w3.org/2002/07/owl#> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . <urn:bad> a owl:Class; rdfs:label "Copied term" . <urn:good> a owl:Class; rdfs:label "Solar cell" .', encoding="utf-8")
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob("*") if p.is_file()}
    excluded = []
    rows = exploration.documents(source, path, excluded)
    assert all(r.get("iri") != "urn:bad" and len(r["label"]) <= quality.MAX_LABEL_CHARS for r in rows)
    assert not any(r.get("kind") == "relation" for r in rows)
    assert excluded and max(len(r["label_preview"]) for r in excluded) <= 161
    match = next(r for r in rows if r.get("kind") == "ontology term")
    resolved = exploration.resolve_source(match, [source])
    assert resolved["canonical"] == "k2" and resolved["open_paper"] == "P1"
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}


def test_integration_ontology_links_are_unique_and_scoped(tmp_path):
    integration = tmp_path / "integration"
    model.write(integration / "integration.json", {"inputs": [{"run_id": "A"}, {"run_id": "B"}]})
    for name in ("A", "B"):
        model.write(tmp_path / name / "run.json", {})
        model.write(tmp_path / name / "ontology/classes.json", [{"id": "k1", "label": name, "iri": "urn:shared"}])
    roots = [integration, tmp_path / "A", tmp_path / "B"]
    row = {"root": str(integration), "iri": "urn:shared"}
    assert exploration.resolve_source(row, roots) is None
    row["root"] = str(tmp_path / "A")
    assert exploration.resolve_source(row, roots)["canonical"] == "k1"
    assert exploration.resolve_source(row, [integration]) is None


def test_repetition_and_legitimate_labels():
    assert quality.label_issues("solar cell efficiency loss " * 4)
    assert quality.label_issues({"label": "Wrong schema"})
    assert not quality.label_issues("temperature coefficient of open-circuit voltage under standard test conditions")
