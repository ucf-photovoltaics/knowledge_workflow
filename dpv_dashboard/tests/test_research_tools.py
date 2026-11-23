"""Scientific views preserve direction, provenance, scope and export safety."""
import copy
import json
from pathlib import Path
import pytest
from rdflib import Graph
from dpv_dashboard import research_tools, viewer, catalog


@pytest.fixture
def payload():
    rdf = Graph().parse(data='''@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<urn:a> a owl:Class; <urn:causes> <urn:b>; rdfs:subClassOf <urn:parent> .
<urn:b> a owl:Class; <urn:affects> <urn:c> .
<urn:c> a owl:Class . <urn:parent> a owl:Class .''', format="turtle")
    return viewer.convert(rdf, show_hierarchy=True)


def test_paths_respect_direction_types_and_depth(payload):
    kinds = ["Scientific relationship"]
    assert research_tools.path(payload, "urn:a", "urn:c", kinds, 1) is None
    steps = research_tools.path(payload, "urn:a", "urn:c", kinds, 2)
    assert len(steps) == 2 and not any(s["reverse"] for s in steps)
    assert research_tools.path(payload, "urn:c", "urn:a", kinds, 2) is None
    reverse = research_tools.path(payload, "urn:c", "urn:a", kinds, 2, "either")
    assert len(reverse) == 2 and all(s["reverse"] for s in reverse)
    assert research_tools.path(payload, "urn:a", "urn:parent", kinds, 2) is None
    with pytest.raises(ValueError):
        research_tools.path(payload, "urn:missing", "urn:a", kinds)
    with pytest.raises(ValueError):
        research_tools.path(payload, "urn:a", "urn:c", kinds, 10)


def test_views_and_hiding_do_not_mutate_projection(payload):
    original = copy.deepcopy(payload)
    local = research_tools.view(payload, focus="urn:a", depth=1)
    assert {n["iri"] for n in local["classAttribute"]} == {"urn:a", "urn:b", "urn:parent"}
    hidden = research_tools.view(payload, hidden=["urn:b"])
    assert "urn:b" not in {n["iri"] for n in hidden["classAttribute"]}
    assert all(e["subject"] != "urn:b" and e["object"] != "urn:b" for e in hidden["_dpv"]["edges"].values())
    structure = research_tools.view(payload, "ontology")
    assert {e["kind"] for e in structure["_dpv"]["edges"].values()} == {"Hierarchy"}
    assert payload == original


def test_exports_include_source_identity_and_no_absolute_mount_paths(payload, tmp_path):
    path = tmp_path / "ontology.ttl"
    path.write_text("example")
    entries = ((str(path), catalog.fingerprint(path), "source-run", "Selected ontology"),)
    data = json.loads(research_tools.export(payload, entries, "example"))
    assert data["metadata"]["subset"] is True
    assert data["metadata"]["source_signature"]
    assert str(tmp_path) not in json.dumps(data)
    assert data["relationships"] == payload["_dpv"]["edges"]
    edge = next(iter(payload["_dpv"]["edges"].values()))
    edge["subject_name"] = "=UNTRUSTED()"
    assert "'=UNTRUSTED()" in research_tools.export(payload, entries, "example", "csv")


def test_papers_deduplicate_by_doi_and_preserve_fallback_title():
    assert research_tools.paper_identity({"doi": "https://doi.org/10.123/ABC"}, "a") == research_tools.paper_identity({"doi": "10.123/abc"}, "b")
    assert research_tools.paper_identity({"title": "First"}, "a") != research_tools.paper_identity({"title": "Second"}, "a")


def test_saved_quality_does_not_invent_missing_checks(tmp_path):
    assert research_tools.saved_checks(tmp_path) == []
    path = tmp_path / "quality/ontology/assessment/summary.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"source": "ontology.ttl", "sha256": "source-fingerprint", "checks": {"hermit": {"status": "unavailable"}}}))
    rows = research_tools.saved_checks(tmp_path)
    assert len(rows) == 1 and rows[0]["status"] == "unavailable"
    assert rows[0]["input_sha256"] == "source-fingerprint"


def test_comparison_uses_only_shared_papers_and_recorded_lineage(tmp_path):
    def run(name, shared_label, extra):
        root = tmp_path / name
        (root / "papers").mkdir(parents=True)
        (root / "normalized").mkdir()
        (root / "run.json").write_text('{}')
        for key, doi in (("shared", "10.1/shared"), ("extra", "10.1/" + name)):
            (root / "papers" / (key + ".json")).write_text(json.dumps({"key": key, "title": key, "doi": doi, "concepts": [{"id": "original", "label": shared_label if key == "shared" else extra}]}))
        (root / "normalized/concepts.json").write_text(json.dumps([{"id": "c1", "label": shared_label, "papers": ["shared"]}, {"id": "c2", "label": extra, "papers": ["extra"]}]))
        (root / "normalized/concept_lineage.json").write_text(json.dumps([{"paper": "shared", "original_id": "original", "canonical_id": "c1"}, {"paper": "extra", "original_id": "original", "canonical_id": "c2"}]))
        return root
    row = research_tools.compare(run("left", "same", "unmatched left"), run("right", "same", "unmatched right"))
    assert row["shared_papers"] == 1
    assert row["shared_labels"] == ["same"]
    assert not any("unmatched" in label for key in ("shared_labels", "left_only_labels", "right_only_labels") for label in row[key])


def test_found_path_renders_graph_and_evidence_in_module_namespace(payload, tmp_path):
    import ast
    from types import SimpleNamespace
    from shiny import ui
    from shiny._namespaces import ResolvedId
    from dpv_dashboard import workspace_tools
    source = Path(workspace_tools.__file__)
    tree = ast.parse(source.read_text(encoding="utf-8"))
    callback = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "path_result")
    callback.decorator_list = []
    steps = research_tools.path(payload, "urn:a", "urn:c", ["Scientific relationship"], 2)
    namespace = {"path_steps": SimpleNamespace(get=lambda: {"scope": "fixture", "steps": steps, "payload": payload}),
                 "scope": lambda: "fixture", "root": lambda: tmp_path, "research_tools": research_tools,
                 "viewer": viewer.viewer, "edge_card": workspace_tools.edge_card, "ui": ui,
                 "session": SimpleNamespace(ns=ResolvedId("exploration"))}
    exec(compile(ast.Module(body=[callback], type_ignores=[]), str(source), "exec"), namespace)
    html = str(namespace["path_result"]())
    assert "exploration-path_vowl" in html and "Step 1" in html and "Step 2" in html
    assert "not a causal conclusion" in html and "Scientific relationship" in html


def test_metadata_discovery_matches_bundle_identity_without_content_probes(tmp_path, monkeypatch):
    from dpv_dashboard import visual_graph
    root = tmp_path / "integration"
    domain = tmp_path / "domain"
    root.mkdir()
    domain.mkdir()
    (domain / "run.json").write_text('{"id":"domain"}')
    (root / "integration.json").write_text(json.dumps({"inputs": [{"run_id": "domain"}]}))
    selected = root / "integrated.ttl"
    selected.write_text("example")
    for name in ("ontology.ttl", "domain_layer.ttl"):
        (domain / name).write_text("example")
    for literature in (True, False):
        expected = visual_graph.files(root, selected, literature)
        assert research_tools.files(root, selected, literature) == expected
    monkeypatch.setattr(catalog, "accessible", lambda *a, **k: pytest.fail("Content probe during metadata polling"))
    assert research_tools.files(root, selected)[0]
    with pytest.raises(ValueError):
        research_tools.available(root, tmp_path / "private.ttl")
