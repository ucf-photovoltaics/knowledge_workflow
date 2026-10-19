"""Cross-domain equivalences never close a subclass cycle (integration-n50-pv-cost-chain-gemma4-26b-n50)."""
from collections import Counter

import rdflib
from rdflib import URIRef
from rdflib.namespace import OWL, RDF, RDFS

from src.agents.integration import IntegrationAgent
from src.tools import integration

A, B = "http://example.org/kw/a/class/", "http://example.org/kw/b/class/"


def graphs(edges):
    out = {}
    for dom, base in (("a", A), ("b", B)):
        g = rdflib.Graph()
        for name in ("x", "y"):
            g.add((URIRef(base + name), RDF.type, OWL.Class))
        out[dom] = {"graph": g, "iri": base}
    for s, o in edges:
        out["a" if s.startswith(A) else "b"]["graph"].add((URIRef(s), RDFS.subClassOf, URIRef(o)))
    return out


def equivalent(a, b, confidence):
    return {"a_iri": a, "b_iri": b, "a_domain": "a", "b_domain": "b", "relation": "equivalent", "confidence": confidence}


def guard(edges, mappings):
    agent = object.__new__(IntegrationAgent)
    agent.stats, agent.superclasses = Counter(), integration.subclass_edges(graphs(edges))
    agent._guard_equivalence(mappings)
    return agent


def test_crossed_hierarchies_keep_one_equivalence_and_validate():
    edges = [(A + "x", A + "y"), (B + "y", B + "x")]  # a:x under a:y, but b:y under b:x
    mappings = [equivalent(A + "x", B + "x", 0.9), equivalent(A + "y", B + "y", 0.8)]
    agent = guard(edges, mappings)
    assert [m["relation"] for m in mappings] == ["equivalent", "exact"]
    assert mappings[1]["downgraded_from"] == "equivalent"
    assert agent.stats["downgraded_equivalent_subclass_cycle"] == 1
    empty = rdflib.Graph()
    assert integration.validate(empty, "[]", graphs(edges), mappings)["valid"]


def test_parallel_hierarchies_keep_both_equivalences():
    edges = [(A + "x", A + "y"), (B + "x", B + "y")]
    mappings = [equivalent(A + "x", B + "x", 0.9), equivalent(A + "y", B + "y", 0.8)]
    guard(edges, mappings)
    assert [m["relation"] for m in mappings] == ["equivalent", "equivalent"]


def test_equivalence_with_own_ancestor_is_downgraded():
    edges = [(B + "x", A + "y")]  # b:x is already a subclass of a:y, so a:y = b:x would be a cycle
    mappings = [equivalent(A + "y", B + "x", 0.9)]
    agent = guard(edges, mappings)
    assert mappings[0]["relation"] == "exact"
    assert agent.stats["downgraded_equivalent_subclass_cycle"] == 1
