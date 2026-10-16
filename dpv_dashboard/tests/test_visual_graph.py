"""Test visual graph support for the Knowledge Workflow system.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import hashlib
from pathlib import Path
from rdflib import Graph, RDF, RDFS, OWL, URIRef
from dpv_dashboard import model, visual_graph, exploration
from dpv_dashboard.viewer import convert

TEXT = '''@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix kw: <http://example.org/kw/> .
@prefix dct: <http://purl.org/dc/terms/> .
<urn:a> a owl:Class; rdfs:label "Solar cell"; owl:disjointWith <urn:b>; rdfs:subClassOf [a owl:Restriction; owl:onProperty <urn:part>; owl:someValuesFrom <urn:b>] .
<urn:b> a owl:Class; rdfs:label "Silicon" .
<urn:part> a owl:ObjectProperty; rdfs:label "has part" .
<urn:la> a skos:Concept; skos:prefLabel "Solar cell"; kw:ontologyClass <urn:a>; <urn:made> <urn:lb> .
<urn:lb> a skos:Concept; skos:prefLabel "Silicon"; kw:ontologyClass <urn:b> .
<urn:made> a rdf:Property; rdfs:label "made from" .
[] a kw:Claim; rdf:subject <urn:la>; rdf:predicate <urn:made>; rdf:object <urn:lb>; kw:evidence "The cell is made from silicon."; kw:evidenceVerified true; dct:source <https://doi.org/10.1/example> .'''


def test_scientific_relations_default_and_claim_sources_survive_alignment():
    graph = Graph().parse(data=TEXT, format="turtle")
    triple = (URIRef("urn:la"), URIRef("urn:made"), URIRef("urn:lb"))
    out = convert(graph, show_hierarchy=False, origins={triple: [{"run": "domain", "file": "domain_layer.ttl", "layer": "Literature claims"}]})
    edges = list(out["_dpv"]["edges"].values())
    assert not any(e["kind"] == "Disjointness" for e in edges)
    claim = next(e for e in edges if e["kind"] == "Literature claim")
    assert claim["subject"] == "urn:a" and claim["object"] == "urn:b"
    assert claim["sources"][0]["run"] == "domain"
    assert claim["claims"][0]["quotes"] == ["The cell is made from silicon."]
    assert claim["claims"][0]["verification"] == ["true"]
    assert any(e["kind"] == "Ontology restriction" for e in edges)
    enabled = convert(graph, show_disjoint=True)
    assert sum(e["kind"] == "Disjointness" for e in enabled["_dpv"]["edges"].values()) == 1
    disabled = convert(graph, show_literature=False)
    assert not any(e["kind"] == "Literature claim" for e in disabled["_dpv"]["edges"].values())


def test_focus_keeps_claim_evidence_restrictions_and_aliases():
    graph = Graph().parse(data=TEXT, format="turtle")
    focused = exploration.neighborhood(graph, "urn:a", as_graph=True)
    out = convert(focused, show_hierarchy=False)
    kinds = {e["kind"] for e in out["_dpv"]["edges"].values()}
    assert {"Literature claim", "Ontology restriction"} <= kinds
    assert any(e["claims"] for e in out["_dpv"]["edges"].values())


def test_saved_layers_and_missing_coverage_without_source_writes(tmp_path):
    source, root = tmp_path / "domain", tmp_path / "integration"
    model.write(source / "run.json", {})
    model.write(root / "integration.json", {"inputs": [{"run_id": "domain"}]})
    source.joinpath("ontology.ttl").write_text(TEXT, encoding="utf-8")
    root.joinpath("master.ttl").write_text('<urn:master> a <http://www.w3.org/2002/07/owl#Ontology> .', encoding="utf-8")
    paths = list(tmp_path.rglob("*.ttl"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    entries, missing = visual_graph.files(root, root / "master.ttl")
    graph, origins, loaded, failed = visual_graph.assemble(entries)
    assert len(loaded) == 2 and len(missing) == 1 and "domain_layer.ttl" in missing[0]
    assert not failed and origins
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
