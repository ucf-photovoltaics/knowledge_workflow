"""Assessment boundaries: preserve artifacts, resolve imports, and surface tool failures."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
import rdflib
from rdflib.namespace import OWL

from src.tools import ontology_quality as quality


ONTOLOGY = '''@prefix : <https://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
:ontology a owl:Ontology .
:Material a owl:Class ; rdfs:label "Material" .
'''


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "ontology.ttl"
    path.write_text(ONTOLOGY, encoding="utf-8")
    return path


@pytest.fixture
def no_tools(monkeypatch):
    monkeypatch.setattr(quality, "_robot", lambda: None)
    def missing(name):
        raise quality.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(quality.metadata, "version", missing)


def test_missing_tools_never_pass_and_source_is_unchanged(source, no_tools):
    before = source.read_bytes()
    result = quality.assess(source)
    assert result["status"] == "incomplete"
    assert result["checks"]["hermit"]["status"] == "unavailable"
    assert result["checks"]["ontocheck"]["metrics"] == "all"
    assert source.read_bytes() == before
    assert result["sha256"] == hashlib.sha256(before).hexdigest()
    assert json.loads((source.parent / "quality/ontology/summary.json").read_text())["status"] == "incomplete"


def test_malformed_graph_is_reported(source, no_tools):
    source.write_text("not turtle", encoding="utf-8")
    result = quality.assess(source)
    assert result["status"] == "needs_review"
    assert result["checks"]["parse"]["status"] == "error"


def test_import_closure_preserves_constraints_and_removes_only_snapshot_imports(source, no_tools):
    source.write_text(ONTOLOGY + ':ontology owl:imports <https://example.org/domain> .', encoding="utf-8")
    imported = source.parent / "domain.ttl"
    imported.write_text(ONTOLOGY + ':Material owl:disjointWith :Measurement . :Measurement a owl:Class .', encoding="utf-8")
    result = quality.assess(source, imports={"https://example.org/domain": imported})
    snapshot = rdflib.Graph().parse(Path(result["directory"]) / "assessment.ttl")
    assert len(list(snapshot.triples((None, OWL.disjointWith, None)))) == 1
    assert not list(snapshot.triples((None, OWL.imports, None)))
    assert "owl:imports" in source.read_text()
    assert len(result["imports"]) == 2


def test_unresolved_imports_block_reasoner(source, monkeypatch, no_tools):
    source.write_text(ONTOLOGY + ':ontology owl:imports <https://example.org/missing> .', encoding="utf-8")
    monkeypatch.setattr(quality, "_robot", lambda: ["robot"])
    result = quality.assess(source)
    assert result["unresolved_imports"] == ["https://example.org/missing"]
    assert result["checks"]["hermit"]["status"] == "skipped"


def test_timeout_is_explicit(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1)
    monkeypatch.setattr(quality.subprocess, "run", timeout)
    assert quality._execute(["tool"], tmp_path, "tool", 1)["status"] == "timeout"


def test_metric_errors_override_successful_process_exit(source, monkeypatch):
    monkeypatch.setattr(quality, "_robot", lambda: None)
    monkeypatch.setattr(quality.metadata, "version", lambda name: "0.1.3")
    def execute(command, folder, name, timeout):
        assert "--metrics" in command and command[command.index("--metrics") + 1] == "all"
        assert "--search-term" in command
        (folder / "ontocheck.csv").write_text('Metric,Score,Status\nspellCheck,N/A,Error: unavailable dictionary\n')
        return {"status": "completed"}
    monkeypatch.setattr(quality, "_execute", execute)
    result = quality.assess(source)
    assert result["checks"]["ontocheck"]["status"] == "error"
    assert result["status"] == "needs_review"


def test_repeated_assessments_keep_separate_reports(source, no_tools):
    first = quality.assess(source)
    second = quality.assess(source)
    assert first["directory"] != second["directory"]
    assert (Path(first["directory"]) / "summary.json").exists()


def test_invalid_options_fail_early(source):
    with pytest.raises(ValueError, match="positive"):
        quality.assess(source, timeout=0)
    questions = source.parent / "questions.json"
    questions.write_text("[]")
    with pytest.raises(ValueError, match="domain_prefixes"):
        quality.assess(source, questions=questions)


@pytest.mark.skipif(not os.environ.get("ROBOT_JAR"), reason="requires official ROBOT and Java")
@pytest.mark.parametrize("individual", [False, True])
def test_real_hermit_detects_impossible_class_and_inconsistency(source, individual):
    source.write_text(ONTOLOGY + '''
:Measurement a owl:Class .
:Material owl:disjointWith :Measurement .
:Sample a owl:Class ; rdfs:subClassOf :Material, :Measurement .
''' + (':sample a :Sample .' if individual else ''), encoding="utf-8")
    result = quality.assess(source, timeout=120)
    assert result["checks"]["owl_profile"]["status"] == "completed"
    assert result["checks"]["hermit"]["status"] == "error"
    assert result["checks"]["robot_report"]["status"] == "completed"


@pytest.mark.skipif(not os.environ.get("QUALITY_LIVE"), reason="runs all installed OntoCheck metrics")
def test_real_ontocheck_runs_every_registered_metric(source):
    from ontocheck.run_assessment import METRIC_DISPATCHER
    result = quality.assess(source, timeout=120)
    rows = result["checks"]["ontocheck"]["results"]
    assert {row["Metric"] for row in rows} == set(METRIC_DISPATCHER)
    assert not any(row["Status"].startswith("Skipped") for row in rows)


@pytest.mark.skipif(not os.environ.get("ROBOT_JAR"), reason="requires official ROBOT and Java")
def test_real_integrated_closure_exposes_cross_domain_contradiction(source):
    source.write_text(ONTOLOGY + ':ontology owl:imports <https://example.org/domain> .\n'
                      ':Material owl:equivalentClass :Measurement .', encoding="utf-8")
    domain = source.parent / "domain.ttl"
    domain.write_text(ONTOLOGY + ':Measurement a owl:Class . :Material owl:disjointWith :Measurement .', encoding="utf-8")
    result = quality.assess(source, imports={"https://example.org/domain": domain}, timeout=120)
    assert not result["unresolved_imports"]
    assert result["checks"]["hermit"]["status"] == "error"


@pytest.mark.skipif(not os.environ.get("ROBOT_JAR"), reason="requires official ROBOT and Java")
def test_real_coherent_ontology_passes_reasoner(source):
    source.write_text(ONTOLOGY + ':Material rdfs:label "Material µ" .', encoding="utf-8")
    result = quality.assess(source, timeout=120)
    assert result["checks"]["hermit"]["status"] == "completed"
    assert result["checks"]["robot_report"]["status"] == "completed"
    assert "µ" in json.dumps(result["checks"]["robot_report"]["findings"], ensure_ascii=False)
