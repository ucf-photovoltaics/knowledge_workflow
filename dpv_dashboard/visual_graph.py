"""Assemble saved graph layers locally; never fetch imports or rewrite source files.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import os
from functools import lru_cache
from pathlib import Path
from collections import Counter, deque
from threading import RLock
from time import perf_counter
from rdflib import Graph
from dpv_dashboard import catalog, research

# Largest ontology file the viewer accepts. Files over MAX_LIVE are shown only from the viewer cache
# (scripts/build-viewer-cache.py, kw-viewer-cache job), so the cloud viewer never parses them on a request.
MAX_GRAPH = int(os.environ.get("DPV_MAX_GRAPH_MB", "256")) * 1024 * 1024
MAX_LIVE = 64 * 1024 * 1024 if os.environ.get("DPV_VIEWER") == "1" else MAX_GRAPH  # cloud viewer only


def files(root, selected, literature=True):
    if root is None or selected is None:
        return (), []
    root, selected = root.resolve(), selected.resolve()
    entries, missing = [], []
    def add(base, path, kind):
        try:
            value = catalog.accessible(base, str(path.relative_to(base)))
        except ValueError:
            value = None
        stamp = catalog.fingerprint(value) if value else None
        if not stamp or stamp[1] > MAX_GRAPH:
            missing.append(f"{base.name}: {path.name} unavailable or too large")
            return
        item = (str(value), stamp, base.name, kind)
        if not any(e[0] == item[0] for e in entries):
            entries.append(item)
    add(root, selected, "Selected ontology")
    integration = (root / "integration.json").is_file()
    sources = research.source_roots(root)
    if integration:
        known = {p.name for p in sources}
        for entry in research.records(catalog.load(root / "integration.json", {}).get("inputs", [])):
            name = entry.get("run_id")
            if isinstance(name, str) and name not in known:
                missing.append("Recorded source run unavailable: " + name[:160])
    for source in sources:
        if integration:
            add(source, source / "ontology.ttl", "Domain ontology")
        if literature:
            add(source, source / "domain_layer.ttl", "Literature claims")
    return tuple(entries), missing


def triples(path):
    """Distinct triples of one Turtle file as rdflib terms. pyoxigraph parses several times faster than rdflib;
    a file it rejects is read by rdflib instead. Blank nodes stay distinct per file, as with rdflib."""
    from rdflib import BNode, Literal, URIRef
    try:
        import pyoxigraph as ox
        parser = ox.parse(path=str(path), format=ox.RdfFormat.TURTLE, base_iri=Path(path).resolve().as_uri())
        terms, result = {}, {}  # insertion-ordered, so multi-valued lists keep file order as with rdflib
        def term(value):
            known = terms.get(value)
            if known is None:
                if isinstance(value, ox.NamedNode):
                    known = URIRef(value.value)
                elif isinstance(value, ox.BlankNode):
                    known = BNode()
                elif value.language:
                    known = Literal(value.value, lang=value.language)
                else:
                    datatype = value.datatype.value
                    known = Literal(value.value, datatype=None if datatype == "http://www.w3.org/2001/XMLSchema#string" else URIRef(datatype))
                terms[value] = known
            return known
        for quad in parser:
            result[term(quad.subject), term(quad.predicate), term(quad.object)] = None
        return list(result)
    except Exception:
        return list(Graph().parse(Path(path), format="turtle"))


def parse(path):
    graph = Graph()
    for triple in triples(path):
        graph.add(triple)
    return graph


@lru_cache(maxsize=2)
def assemble(entries):
    graph, origins, loaded, failed = Graph(), {}, [], []
    for path, stamp, run, kind in entries:
        try:
            source = triples(path)
        except Exception:
            failed.append(f"{run}: {Path(path).name} could not be read")
            continue
        origin = {"run": run, "file": Path(path).name, "layer": kind}
        loaded.append(origin)
        for triple in source:
            graph.add(triple)
            origins.setdefault(triple, []).append(origin)
    return graph, origins, loaded, failed


_PREPARATION_LOCK = RLock()


@lru_cache(maxsize=4)
def projection(entries, disjoint=False, hierarchy=False, mappings=True, literature=True):
    """Prepare an immutable, reusable projection; callers copy before changing it."""
    from dpv_dashboard.viewer import convert
    from dpv_dashboard import viewer_cache
    started = perf_counter()
    saved = viewer_cache.load_projection(entries, disjoint, hierarchy, mappings, literature)
    if saved is not None:
        return saved
    if any(e[1][1] > MAX_LIVE for e in entries):
        raise ValueError("This ontology is large and is shown once the nightly viewer cache has prepared it.")
    with _PREPARATION_LOCK:
        graph, origins, loaded, failed = assemble(entries)
        payload = convert(graph, show_disjoint=disjoint, show_hierarchy=hierarchy,
                          show_mappings=mappings, show_literature=literature, origins=origins)
    return payload, loaded, failed, round(perf_counter() - started, 2)


def prepare(entries, focus="", limit=160, disjoint=False, hierarchy=False, mappings=True, literature=True):
    """Build a connected, bounded browser view without discarding cached evidence."""
    if limit not in (160, 400, 0):
        raise ValueError("Choose the overview, expanded view, or full graph.")
    from dpv_dashboard import viewer_cache
    saved = viewer_cache.load_view(entries, focus, limit, disjoint, hierarchy, mappings, literature)
    if saved is not None:
        return saved
    payload, loaded, failed, seconds = projection(entries, disjoint, hierarchy, mappings, literature)
    return bounded(payload, focus, limit, loaded, failed, seconds)


def bounded(payload, focus, limit, loaded, failed, seconds):
    """Select a browser view from a prepared projection without reading RDF."""
    attributes = payload["classAttribute"]
    nodes = {row["id"]: row for row in attributes}
    adjacency, degree = {}, Counter()
    for edge in payload["propertyAttribute"]:
        a, b = edge["domain"], edge["range"]
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
        degree.update((a, b))
    ranking = sorted(nodes, key=lambda key: (-degree[key], nodes[key]["iri"]))
    seed = next((key for key, row in nodes.items() if row["iri"] == focus), None)
    if focus and seed is None:
        raise ValueError("The focused concept is absent from this graph. Choose another search result.")
    chosen, queue = set(), deque([seed] if seed else [])
    budget = limit or len(nodes)
    for candidate in ([seed] if seed else ranking):
        if not queue and candidate not in chosen:
            queue.append(candidate)
        while queue and len(chosen) < budget:
            key = queue.popleft()
            if key in chosen:
                continue
            chosen.add(key)
            queue.extend(sorted(adjacency.get(key, set()) - chosen, key=lambda value: (-degree[value], nodes[value]["iri"])))
        if len(chosen) >= budget:
            break
    edges = [row for row in payload["propertyAttribute"] if row["domain"] in chosen and row["range"] in chosen]
    if limit:
        edges = edges[:limit * 2]
    edge_ids = {row["id"] for row in edges}
    result = {**payload, "class": [row for row in payload["class"] if row["id"] in chosen],
              "classAttribute": [row for row in attributes if row["id"] in chosen],
              "property": [row for row in payload["property"] if row["id"] in edge_ids], "propertyAttribute": edges,
              "_dpv": {**payload["_dpv"], "edges": {key: value for key, value in payload["_dpv"]["edges"].items() if key in edge_ids},
                       "coverage": {"total_nodes": len(nodes), "total_edges": len(payload["property"]),
                                    "loaded": loaded, "failed": failed, "preparation_seconds": seconds}}}
    # Each displayed graph has a distinct event version, even when projection data is cached.
    from uuid import uuid4
    result["_dpv"]["token"] = uuid4().hex
    return result
