"""Bounded graph views preserve source evidence and reuse expensive projections."""
import ast
from pathlib import Path
from types import SimpleNamespace
import pytest
from dpv_dashboard import catalog, visual_graph


def entries(tmp_path):
    path = tmp_path / "ontology.ttl"
    triples = ['@prefix owl: <http://www.w3.org/2002/07/owl#> .']
    for i in range(450):
        triples.append(f'<urn:c{i}> a owl:Class .')
        if i:
            triples.append(f'<urn:c{i-1}> <urn:connects> <urn:c{i}> .')
    path.write_text('\n'.join(triples), encoding="utf-8")
    return ((str(path), catalog.fingerprint(path), "source-run", "Selected ontology"),)


def test_overview_expansion_full_and_evidence(tmp_path):
    source = entries(tmp_path)
    overview = visual_graph.prepare(source)
    assert len(overview["class"]) == 160
    assert len(overview["property"]) <= 320
    assert overview["_dpv"]["coverage"]["total_nodes"] == 450
    assert all(edge["sources"][0]["run"] == "source-run" for edge in overview["_dpv"]["edges"].values())
    before = visual_graph.projection.cache_info().hits
    expanded = visual_graph.prepare(source, limit=400)
    full = visual_graph.prepare(source, limit=0)
    assert len(expanded["class"]) == 400 and len(full["class"]) == 450
    assert visual_graph.projection.cache_info().hits >= before + 2
    assert overview["_dpv"]["token"] != expanded["_dpv"]["token"]
    assert len(visual_graph.projection(source)[0]["class"]) == 450


def test_focus_outside_overview_and_changed_file(tmp_path):
    source = entries(tmp_path)
    focused = visual_graph.prepare(source, focus="urn:c449")
    assert any(row["iri"] == "urn:c449" for row in focused["classAttribute"])
    with pytest.raises(ValueError, match="absent"):
        visual_graph.prepare(source, focus="urn:missing")
    with pytest.raises(ValueError, match="overview"):
        visual_graph.prepare(source, limit=-1)
    path = Path(source[0][0])
    with path.open("a", encoding="utf-8") as handle:
        handle.write('\n<urn:new> a owl:Class .')
    changed = ((str(path), catalog.fingerprint(path), "source-run", "Selected ontology"),)
    assert visual_graph.prepare(changed)["_dpv"]["coverage"]["total_nodes"] == 451


def test_stale_background_result_cannot_replace_current_graph():
    source = Path(__file__).parents[1] / "pages/exploration.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    callback = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "receive_graph")
    callback.decorator_list = []
    received = []
    namespace = {"prepare_graph": SimpleNamespace(result=lambda: {"request": "old", "payload": {}}),
                 "graph_request": lambda: "current", "prepared": SimpleNamespace(set=received.append)}
    exec(compile(ast.Module(body=[callback], type_ignores=[]), str(source), "exec"), namespace)
    namespace["receive_graph"]()
    assert not received
