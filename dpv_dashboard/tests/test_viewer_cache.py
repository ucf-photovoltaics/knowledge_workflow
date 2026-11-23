"""Persistent bundles work across process restarts and reject changed inputs."""
import json
from itertools import product
import pytest
from rdflib import Graph
from dpv_dashboard import catalog, exploration, viewer_cache, visual_graph
from dpv_dashboard.viewer import convert


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("DPV_SHARE_ROOT", str(tmp_path))
    monkeypatch.setenv("DPV_VIEWER_CACHE", str(tmp_path / "cache"))
    root = tmp_path / "example"
    root.mkdir()
    (root / "run.json").write_text('{}')
    ontology = root / "ontology.ttl"
    ontology.write_text('''@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<urn:a> a owl:Class; rdfs:subClassOf <urn:parent>; owl:disjointWith <urn:b> .
<urn:b> a owl:Class .''')
    return root, ontology


def test_restart_cached_view_focus_and_documents(bundle, monkeypatch):
    root, ontology = bundle
    assert viewer_cache.build(root, ontology) == "built"
    entries, _ = visual_graph.files(root, ontology)
    expected = exploration.documents(root, ontology, use_cache=False)
    visual_graph.assemble.cache_clear()
    visual_graph.projection.cache_clear()
    exploration.graph.cache_clear()
    monkeypatch.setattr(Graph, "parse", lambda *a, **k: pytest.fail("RDF parsed on cache hit"))
    assert visual_graph.prepare(entries)["class"]
    assert visual_graph.prepare(entries, focus="urn:b")["class"]
    assert exploration.documents(root, ontology) == expected
    assert viewer_cache.build(root, ontology) == "unchanged"


def test_changed_sources_and_missing_assets(bundle):
    root, ontology = bundle
    viewer_cache.build(root, ontology)
    entries, _ = visual_graph.files(root, ontology)
    folder, value = viewer_cache.manifest(entries, True)
    (folder / value["projection"]).unlink()
    assert viewer_cache.build(root, ontology) == "built"
    ontology.write_text(ontology.read_text() + '\n<urn:new> a <http://www.w3.org/2002/07/owl#Class> .')
    entries, _ = visual_graph.files(root, ontology)
    assert viewer_cache.manifest(entries, True) is None
    assert viewer_cache.build(root, ontology) == "built"
    (root / "run.json").write_text('{"changed": true}')
    assert viewer_cache.load_documents(root, ontology, []) is None


def test_filtered_projection_matches_converter(bundle):
    root, ontology = bundle
    graph = Graph().parse(ontology, format="turtle")
    base = convert(graph, show_disjoint=True, show_hierarchy=True, show_mappings=True)
    def semantic(payload):
        nodes = {row["id"]: row["iri"] for row in payload["classAttribute"]}
        return set(nodes.values()), {(nodes[row["domain"]], nodes[row["range"]],
                                      payload["_dpv"]["edges"][row["id"]]["kind"])
                                     for row in payload["propertyAttribute"]}
    for disjoint, hierarchy, mappings in product((False, True), repeat=3):
        direct = convert(graph, show_disjoint=disjoint, show_hierarchy=hierarchy, show_mappings=mappings)
        assert semantic(viewer_cache.filtered(base, disjoint, hierarchy, mappings, True)) == semantic(direct)


def test_private_and_path_escape_rejected(bundle):
    root, ontology = bundle
    with pytest.raises(ValueError):
        viewer_cache.relative(root.parent.parent / "outside.ttl")
    with pytest.raises(ValueError):
        viewer_cache.relative(root.parent / "private" / "hidden.ttl")
    with pytest.raises(ValueError):
        viewer_cache.asset(root, "../outside.json.gz")
