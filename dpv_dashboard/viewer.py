"""Independent RDF-to-WebVOWL projection; never fetch ontology imports or rewrite RDF.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

import json
from rdflib import Graph, OWL, RDF, RDFS, SKOS, URIRef
from shiny import ui


def convert(text, show_disjoint=False, show_hierarchy=True, show_mappings=True, origins=None, show_literature=True):
    from uuid import uuid4
    from rdflib import DCTERMS
    from dpv_dashboard import quality
    graph = text if isinstance(text, Graph) else Graph().parse(data=text, format="turtle")
    origins = origins or {}
    classes = set(graph.subjects(RDF.type, OWL.Class)) | set(graph.subjects(RDF.type, RDFS.Class)) | set(graph.subjects(RDF.type, SKOS.Concept))
    local = lambda term: str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    def label(term):
        return str(graph.value(term, RDFS.label) or graph.value(term, SKOS.prefLabel) or local(term).replace("_", " "))
    aliases = {s: o for s, p, o in graph if local(p) == "ontologyClass" and s in classes and o in classes}
    mapped = lambda term: aliases.get(term, term)
    blocked = {c for c in classes if quality.label_issues(label(c))}
    claim_nodes = {}
    for node, subject in graph.subject_objects(RDF.subject):
        predicate, target = graph.value(node, RDF.predicate), graph.value(node, RDF.object)
        if predicate and target:
            claim_nodes.setdefault((subject, predicate, target), []).append(node)
    edges = {}
    mappings = {OWL.equivalentClass, SKOS.exactMatch, SKOS.closeMatch, SKOS.broadMatch, SKOS.narrowMatch, SKOS.relatedMatch}
    hierarchy = {RDFS.subClassOf, SKOS.broader, SKOS.narrower}
    def add(subject, predicate, target, kind, triple):
        if not isinstance(subject, URIRef) or not isinstance(target, URIRef) or subject in blocked or target in blocked:
            return
        s, o = mapped(subject), mapped(target)
        if s in blocked or o in blocked:
            return
        entry = edges.setdefault((s, predicate, o, kind), {"subject": str(s), "predicate": str(predicate), "object": str(o), "kind": kind,
            "subject_name": label(s), "object_name": label(o), "relation": label(predicate), "sources": [], "claims": []})
        for origin in origins.get(triple, []):
            if origin not in entry["sources"]:
                entry["sources"].append(origin)
        for node in claim_nodes.get(triple, []):
            values = {local(p): list(graph.objects(node, p)) for p in set(graph.predicates(node))}
            claim = {"quotes": [str(v) for v in values.get("evidence", [])], "papers": [str(v) for v in graph.objects(node, DCTERMS.source)],
                "verification": [str(v) for v in values.get("evidenceVerified", [])], "status": [str(v) for v in values.get("evidenceStatus", [])],
                "conditions": [str(v) for v in values.get("condition", [])], "support": [str(v) for v in values.get("support", [])],
                "original_subject": str(subject), "original_object": str(target)}
            if claim not in entry["claims"]:
                entry["claims"].append(claim)
    for s, p, o in graph:
        if p == OWL.disjointWith and show_disjoint:
            add(s, p, o, "Disjointness", (s, p, o))
        elif p in hierarchy and show_hierarchy:
            add(s, p, o, "Hierarchy", (s, p, o))
        elif p in mappings and show_mappings:
            add(s, p, o, "Cross-ontology mapping", (s, p, o))
        elif s in classes and o in classes and p not in hierarchy | mappings | {OWL.disjointWith, RDF.type} and local(p) != "ontologyClass":
            if show_literature or (s, p, o) not in claim_nodes:
                add(s, p, o, "Literature claim" if (s, p, o) in claim_nodes else "Scientific relationship", (s, p, o))
    for subject, restriction in graph.subject_objects(RDFS.subClassOf):
        prop = graph.value(restriction, OWL.onProperty)
        target = graph.value(restriction, OWL.someValuesFrom) or graph.value(restriction, OWL.allValuesFrom)
        if prop and target:
            add(subject, prop, target, "Ontology restriction", (subject, RDFS.subClassOf, restriction))
    for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
        for subject in graph.objects(prop, RDFS.domain):
            for target in graph.objects(prop, RDFS.range):
                add(subject, prop, target, "Property domain/range", (prop, RDFS.domain, subject))
    visible = {mapped(c) for c in classes if c not in blocked and mapped(c) not in blocked and isinstance(c, URIRef)}
    for s, p, o, kind in edges:
        visible.update((s, o))
    ids = {c: str(i) for i, c in enumerate(sorted(visible, key=str), 1)}
    palette = ["#b7d9c5", "#f5d995", "#bad1ef", "#dbbfdf", "#efbfae", "#b8dedf"]
    domain_runs = sorted({v["run"] for values in origins.values() for v in values if v["layer"] == "Domain ontology"})
    if not domain_runs:
        domain_runs = sorted({v["run"] for values in origins.values() for v in values if v["layer"] == "Selected ontology"})
    domain_colors = {run: palette[i % len(palette)] for i, run in enumerate(domain_runs)}
    def node_attributes(c):
        runs = {origin["run"] for triple in graph.triples((c, RDF.type, None)) for origin in origins.get(triple, []) if origin["run"] in domain_colors}
        return {"id": ids[c], "iri": str(c), "label": {"en": label(c)},
                "backgroundColor": domain_colors[next(iter(runs))] if len(runs) == 1 else "#e3e6e0"}
    payload = {"header": {"title": {"en": "UCF DPV Knowledge Workflow"}, "languages": ["en"]}, "namespace": [],
        "class": [{"id": ids[c], "type": "owl:Class"} for c in ids],
        "classAttribute": [node_attributes(c) for c in ids], "property": [], "propertyAttribute": [],
        "_dpv": {"token": uuid4().hex, "edges": {}, "withheld_nodes": len(blocked), "domain_colors": domain_colors,
                 "settings": {"disjoint": show_disjoint, "hierarchy": show_hierarchy, "mappings": show_mappings, "literature": show_literature}}}
    for number, ((subject, prop, target, kind), detail) in enumerate(sorted(edges.items(), key=lambda item: tuple(str(v) for v in item[0]))):
        identifier = "p" + str(number)
        payload["property"].append({"id": identifier, "type": "rdfs:subClassOf" if prop == RDFS.subClassOf else "owl:ObjectProperty"})
        comment = kind + ". " + "; ".join(f"{s['run']} / {s['file']}" for s in detail["sources"])
        payload["propertyAttribute"].append({"id": identifier, "iri": str(prop), "domain": ids[subject], "range": ids[target],
            "label": {"en": detail["relation"] + (" (restriction)" if kind == "Ontology restriction" else "")}, "comment": {"en": comment}})
        payload["_dpv"]["edges"][identifier] = detail
    return payload


def viewer(text, identifier, payload=None):
    payload = json.dumps(payload if payload is not None else convert(text)).replace("<", "\\u003c")
    return ui.div(
        ui.p("Select a relationship to inspect its saved sources and evidence. Literature nodes align to ontology classes only through recorded links; source graphs remain unchanged."),
        ui.p("Waiting for rendered graph counts…", class_="graph-rendered-status muted"),
        ui.tags.button("Full screen", type="button", class_="viewer-fullscreen btn btn-outline-secondary"),
        ui.tags.iframe(src="webvowl/index.html", id=identifier, title="WebVOWL ontology viewer", class_="ontology-frame"),
        ui.tags.script(ui.HTML(payload), type="application/json", class_="vowl-data"), class_="vowl-container")
