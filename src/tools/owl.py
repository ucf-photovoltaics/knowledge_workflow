"""OWL2 assembly (rdflib) -> JSON-LD, structural validation (no reasoner), and ontology metrics."""
from collections import Counter
from datetime import datetime, timezone
from statistics import mean

import rdflib
from rdflib import BNode, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

from src.config import ONTOLOGY_IRI, ONTOLOGY_TITLE
from src.tools import upper

OBO = "http://purl.obolibrary.org/obo/"
CCO = "https://www.commoncoreontologies.org/"
BFO_CATEGORIES = {  # checked nearest-first along a class's lineage
    f"{OBO}BFO_0000145": "relational quality", f"{OBO}BFO_0000019": "quality", f"{OBO}BFO_0000016": "disposition",
    f"{OBO}BFO_0000034": "function", f"{OBO}BFO_0000023": "role", f"{OBO}BFO_0000029": "site",
    f"{OBO}BFO_0000141": "immaterial entity", f"{OBO}BFO_0000040": "material entity",
    f"{OBO}BFO_0000031": "generically dependent continuant", f"{OBO}BFO_0000144": "process profile",
    f"{OBO}BFO_0000035": "process boundary", f"{OBO}BFO_0000015": "process", f"{OBO}BFO_0000008": "temporal region",
    f"{OBO}BFO_0000006": "spatial region", f"{OBO}BFO_0000011": "spatiotemporal region",
}
ANNOTATIONS = {
    "importanceScore": "importance score", "importanceTier": "importance tier", "paperCount": "paper count",
    "mentionCount": "mention count", "causalRank": "causal rank", "figureReference": "figure reference",
    "support": "supporting paper count", "evidence": "evidence quote", "condition": "stated condition",
    "portalOntology": "source ontology on the MDS-Onto portal", "polarity": "causal polarity",
}
MAPPING_PREDICATES = {"equivalent": OWL.equivalentClass, "subclass": RDFS.subClassOf,
                      "exact": SKOS.exactMatch, "close": SKOS.closeMatch}
BUILTIN = {str(RDF.type), str(RDFS.label), str(RDFS.comment), str(RDFS.subClassOf), str(RDFS.subPropertyOf),
           str(RDFS.domain), str(RDFS.range), str(RDFS.isDefinedBy), str(RDFS.seeAlso)}


def base() -> str:
    b = ONTOLOGY_IRI
    return b if b.endswith(("/", "#")) else b + "/"


def lineage(cid: str, by_id: dict) -> list[str]:
    """Ancestors of a local class, nearest first: local ids, then upper IRIs up to BFO entity."""
    out, cur = [], by_id[cid]["parent"]
    while cur in by_id and cur not in out:
        out.append(cur)
        cur = by_id[cur]["parent"]
    return out + [cur] + upper.ancestors(cur)


def label_of(ref: str, by_id: dict) -> str:
    return by_id[ref]["label"] if ref in by_id else upper.describe(ref).get("label", ref)


def bfo_category(cid: str, by_id: dict) -> str:
    return next((BFO_CATEGORIES[a] for a in lineage(cid, by_id) if a in BFO_CATEGORIES), "other")


def build(classes: list[dict], properties: dict, mappings: list[dict], papers: list[dict], run_id: str,
          domain: str) -> rdflib.Graph:
    """One ontology per domain; local class IRIs are domain-scoped to preserve separate meanings."""
    kw = Namespace(base())
    g = rdflib.Graph()
    for prefix, ns in (("kw", base()), ("obo", OBO), ("cco", CCO), ("skos", SKOS), ("dcterms", DCTERMS), ("owl", OWL)):
        g.bind(prefix, ns)

    onto = URIRef(f"{base()}{domain}")
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, OWL.versionIRI, URIRef(f"{base()}{domain}/version/{run_id}")))
    g.add((onto, OWL.versionInfo, Literal(run_id)))
    g.add((onto, DCTERMS.title, Literal(f"{ONTOLOGY_TITLE}: {domain}", lang="en")))
    g.add((onto, DCTERMS.created, Literal(datetime.now(timezone.utc).isoformat(timespec="seconds"), datatype=XSD.dateTime)))
    g.add((onto, DCTERMS.description, Literal(
        "Draft BFO/CCO-aligned ontology generated from a literature corpus by an LLM-assisted pipeline; "
        "intended as a starting point for domain-expert review.", lang="en")))
    source = {p["key"]: URIRef(f"https://doi.org/{p['doi']}") if p.get("doi") else Literal(f"zotero:{p['key']}")
              for p in papers}
    for s in source.values():
        g.add((onto, DCTERMS.source, s))
    captions = {(p["key"], f["id"]): f"{p.get('doi') or p['key']} {f['label']}: {f['caption'][:150]}"
                for p in papers for f in p.get("figures", [])}

    for name, label in ANNOTATIONS.items():
        g.add((kw[name], RDF.type, OWL.AnnotationProperty))
        g.add((kw[name], RDFS.label, Literal(label, lang="en")))
    for ap in (SKOS.definition, SKOS.altLabel, SKOS.exactMatch, SKOS.closeMatch,
               DCTERMS.source, DCTERMS.title, DCTERMS.created, DCTERMS.description):
        g.add((ap, RDF.type, OWL.AnnotationProperty))

    live = {c["id"]: c for c in classes if not c["excluded"]}
    facet_props = {k: URIRef(v) for k, v in upper.facets()["annotation_properties"].items()}
    for k, P in facet_props.items():
        g.add((P, RDF.type, OWL.AnnotationProperty))
        g.add((P, RDFS.label, Literal({"study_stage": "has study stage", "domain": "has domain",
                                       "subdomain": "has subdomain"}[k], lang="en")))
    g.bind("mds", "https://cwrusdle.bitbucket.io/mds/")

    def add_facets(subject, facets):
        for stage in (facets or {}).get("study_stage", []):
            g.add((subject, facet_props["study_stage"], Literal(stage)))
        for k in ("domain", "subdomain"):
            if (facets or {}).get(k):
                g.add((subject, facet_props[k], Literal(facets[k])))

    def ref(r: str) -> URIRef:
        return URIRef(live[r]["iri"]) if r in live else URIRef(r)

    upper_used = set()
    prop = {}
    for name, p in properties.items():
        P = prop[f"local:{name}"] = kw[name]
        g.add((P, RDF.type, OWL.ObjectProperty))
        g.add((P, RDFS.label, Literal(name, lang="en")))
        g.add((P, SKOS.definition, Literal(p["definition"], lang="en")))
        add_facets(P, p.get("facets"))
        if p.get("parent"):
            g.add((P, RDFS.subPropertyOf, kw[p["parent"]]))
        standard = upper.property_iri(p.get("subproperty_of") or "")
        if standard:
            g.add((P, RDFS.subPropertyOf, URIRef(standard)))
            upper_used.add(standard)
        for key, pred in (("domain", RDFS.domain), ("range", RDFS.range)):
            if p.get(key):
                g.add((P, pred, ref(p[key])))
                if p[key] not in live:
                    upper_used.add(p[key])
        match = upper.property_iri(p.get("close_match") or "")
        if match:
            g.add((P, SKOS.closeMatch, URIRef(match)))
            upper_used.add(match)

    for c in live.values():
        C = URIRef(c["iri"])
        g.add((C, RDF.type, OWL.Class))
        g.add((C, RDFS.label, Literal(c["label"], lang="en")))
        if c.get("definition"):
            g.add((C, SKOS.definition, Literal(c["definition"], lang="en")))
        for a in c.get("alt_labels", []):
            g.add((C, SKOS.altLabel, Literal(a, lang="en")))
        g.add((C, RDFS.subClassOf, ref(c["parent"])))
        add_facets(C, c.get("facets"))
        if c["parent"] not in live:
            upper_used.add(c["parent"])
        for k in c["papers"]:
            if k in source:
                g.add((C, DCTERMS.source, source[k]))
        g.add((C, kw.importanceScore, Literal(c["score"], datatype=XSD.decimal)))
        g.add((C, kw.importanceTier, Literal(c["tier"])))
        g.add((C, kw.paperCount, Literal(c["n_papers"], datatype=XSD.integer)))
        g.add((C, kw.mentionCount, Literal(c["mentions"], datatype=XSD.integer)))
        if c.get("causal_rank") is not None:
            g.add((C, kw.causalRank, Literal(c["causal_rank"], datatype=XSD.integer)))
        for f in c.get("figures", []):
            cap = captions.get(tuple(f.split(":", 1)))
            if cap:
                g.add((C, kw.figureReference, Literal(cap)))
        for r in c.get("restrictions", []):
            if r["o"] not in live:
                continue
            P = prop.get(r["p"]) or URIRef(r["p"])
            if r["p"] not in prop:
                upper_used.add(r["p"])
            node = BNode()
            g.add((node, RDF.type, OWL.Restriction))
            g.add((node, OWL.onProperty, P))
            g.add((node, OWL.someValuesFrom, ref(r["o"])))
            g.add((C, RDFS.subClassOf, node))
            ax = BNode()  # axiom annotation: provenance of the restriction
            g.add((ax, RDF.type, OWL.Axiom))
            g.add((ax, OWL.annotatedSource, C))
            g.add((ax, OWL.annotatedProperty, RDFS.subClassOf))
            g.add((ax, OWL.annotatedTarget, node))
            g.add((ax, kw.support, Literal(r.get("support", 0), datatype=XSD.integer)))
            if r.get("polarity"):
                g.add((ax, kw.polarity, Literal(r["polarity"])))
            for e in r.get("evidence", [])[:1]:
                g.add((ax, kw.evidence, Literal(e["text"])))
            for cond in r.get("conditions", []):
                g.add((ax, kw.condition, Literal(cond)))
            for k in r.get("papers", []):
                if k in source:
                    g.add((ax, DCTERMS.source, source[k]))
        for d in c.get("disjoint_with", []):
            if d in live:
                g.add((C, OWL.disjointWith, ref(d)))

    for m in mappings:
        if m["id"] not in live:
            continue
        T = URIRef(m["iri"])
        g.add((URIRef(live[m["id"]]["iri"]), MAPPING_PREDICATES[m["relation"]], T))
        g.add((T, RDFS.label, Literal(m["label"])))
        if m.get("definition"):
            g.add((T, SKOS.definition, Literal(m["definition"])))
        g.add((T, kw.portalOntology, Literal(m["ontology"])))
        if m["relation"] in ("equivalent", "subclass"):
            g.add((T, RDF.type, OWL.Class))

    # MIREOT-style import: every BFO/CCO term used, plus its full ancestor chain.
    seen, stack = set(), list(upper_used)
    while stack:
        t = stack.pop()
        if t in seen or not upper.describe(t):
            continue
        seen.add(t)
        stack += upper.describe(t)["parents"]
    classes_meta = upper.terms()["classes"]
    for t in seen:
        meta, T = upper.describe(t), URIRef(t)
        is_class = t in classes_meta
        g.add((T, RDF.type, OWL.Class if is_class else OWL.ObjectProperty))
        g.add((T, RDFS.label, Literal(meta["label"], lang="en")))
        if meta.get("definition"):
            g.add((T, SKOS.definition, Literal(meta["definition"], lang="en")))
        g.add((T, RDFS.isDefinedBy, URIRef(upper.terms()["sources"][meta["source"]])))
        for p in meta["parents"]:
            g.add((T, RDFS.subClassOf if is_class else RDFS.subPropertyOf, URIRef(p)))
    return g


def serialize_turtle(g: rdflib.Graph) -> str:
    return g.serialize(format="turtle")


def serialize(g: rdflib.Graph) -> str:
    context = {"kw": base(), "obo": OBO, "cco": CCO, "owl": str(OWL), "rdf": str(RDF), "rdfs": str(RDFS),
               "skos": str(SKOS), "dcterms": str(DCTERMS), "xsd": str(XSD)}
    return g.serialize(format="json-ld", context=context, indent=1)


def _parents(g, c):
    return [o for o in g.objects(c, RDFS.subClassOf) if isinstance(o, URIRef)]


def _depth_to_entity(g, c) -> int | None:
    target, frontier, seen, depth = URIRef(upper.ENTITY), [c], {c}, 0
    while frontier:
        if target in frontier:
            return depth
        nxt = []
        for x in frontier:
            for p in _parents(g, x):
                if p not in seen:
                    seen.add(p)
                    nxt.append(p)
        frontier, depth = nxt, depth + 1
    return None


def validate(g: rdflib.Graph, text: str) -> dict:
    """Structural checks only (no reasoner)."""
    issues = []
    reparsed = rdflib.Graph().parse(data=text, format="json-ld")
    roundtrip = len(reparsed) == len(g)
    if not roundtrip:
        issues.append(f"JSON-LD round trip changed triple count: {len(g)} -> {len(reparsed)}")
    classes = {s for s in g.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)}
    props = set(g.subjects(RDF.type, OWL.ObjectProperty))
    annots = set(g.subjects(RDF.type, OWL.AnnotationProperty))
    local = {c for c in classes if str(c).startswith(base())}

    for s, o in g.subject_objects(RDFS.subClassOf):
        if isinstance(o, URIRef) and o not in classes:
            issues.append(f"undeclared superclass {o} of {s}")
    for s, o in g.subject_objects(OWL.equivalentClass):
        if isinstance(o, URIRef) and o not in classes:
            issues.append(f"undeclared equivalent class {o} of {s}")
    for s, o in g.subject_objects(OWL.disjointWith):
        if o not in classes:
            issues.append(f"undeclared disjoint class {o} of {s}")
    for r in g.subjects(RDF.type, OWL.Restriction):
        if g.value(r, OWL.onProperty) not in props:
            issues.append(f"restriction on undeclared property {g.value(r, OWL.onProperty)}")
        if g.value(r, OWL.someValuesFrom) not in classes:
            issues.append(f"restriction filler not a declared class: {g.value(r, OWL.someValuesFrom)}")
    for p in {p for p in g.predicates() if str(p) not in BUILTIN and not str(p).startswith(str(OWL))}:
        if p not in annots and p not in props:
            issues.append(f"predicate used but not declared: {p}")
    for x in classes & (props | annots | set(g.subjects(RDF.type, OWL.NamedIndividual))):
        issues.append(f"punning: {x} declared as class and property/individual")
    labels = Counter(str(g.value(c, RDFS.label)).lower() for c in local)
    for c in local:
        if g.value(c, RDFS.label) is None:
            issues.append(f"local class without label: {c}")
        elif labels[str(g.value(c, RDFS.label)).lower()] > 1:
            issues.append(f"duplicate label: {g.value(c, RDFS.label)}")
        if _depth_to_entity(g, c) is None:
            issues.append(f"not connected to BFO entity: {c}")
        if c in _ancestors(g, c):
            issues.append(f"subclass cycle through {c}")
    return {"valid": not issues, "n_issues": len(issues), "jsonld_roundtrip": roundtrip,
            "triples": len(g), "issues": sorted(set(issues))[:300]}


def _ancestors(g, c) -> set:
    seen, stack = set(), _parents(g, c)
    while stack:
        p = stack.pop()
        if p not in seen:
            seen.add(p)
            stack += _parents(g, p)
    return seen


def metrics(g: rdflib.Graph, classes: list[dict], mappings: list[dict], properties: dict) -> dict:
    live = {c["id"]: c for c in classes if not c["excluded"]}
    all_classes = {s for s in g.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)}
    local = {c for c in all_classes if str(c).startswith(base())}
    ext = all_classes - local
    obj_props = set(g.subjects(RDF.type, OWL.ObjectProperty))
    annots = set(g.subjects(RDF.type, OWL.AnnotationProperty))
    depths = [d for d in (_depth_to_entity(g, c) for c in local) if d is not None]
    local_depth = [sum(1 for a in lineage(cid, live) if a in live) for cid in live]
    has_child = {c["parent"] for c in live.values()}
    restrictions = [r for c in live.values() for r in c.get("restrictions", []) if r["o"] in live]
    n = len(local) or 1

    def cover(pred):
        return round(sum(1 for c in local if g.value(c, pred) is not None) / n, 3)

    mapped = {m["id"] for m in mappings if m["id"] in live}
    return {
        "classes": len(local),
        "imported_classes": {"BFO": sum(1 for c in ext if "/obo/BFO_" in str(c)),
                             "CCO": sum(1 for c in ext if str(c).startswith(CCO)),
                             "external": sum(1 for c in ext if "/obo/BFO_" not in str(c) and not str(c).startswith(CCO))},
        "object_properties": {"local": sum(1 for p in obj_props if str(p).startswith(base())),
                              **Counter(upper.describe(str(p)).get("source", "other").upper()
                                        for p in obj_props if not str(p).startswith(base()))},
        "causal_restrictions_by_source": dict(Counter(
            "LOCAL" if r["p"].startswith("local:") else upper.describe(r["p"]).get("source", "other").upper()
            for r in restrictions if r["kind"] == "causal")),
        "annotation_properties": len(annots),
        "axioms": {
            "subclass_named": sum(1 for s, o in g.subject_objects(RDFS.subClassOf) if s in local and isinstance(o, URIRef)),
            "subclass_restriction": sum(1 for s, o in g.subject_objects(RDFS.subClassOf) if isinstance(o, BNode)),
            "restriction_causal": sum(1 for r in restrictions if r["kind"] == "causal"),
            "restriction_relation": sum(1 for r in restrictions if r["kind"] == "relation"),
            "equivalent_class": len(list(g.subject_objects(OWL.equivalentClass))),
            "disjoint_with": len(list(g.subject_objects(OWL.disjointWith))),
            "domain": len(list(g.subject_objects(RDFS.domain))),
            "range": len(list(g.subject_objects(RDFS.range))),
            "subproperty": len(list(g.subject_objects(RDFS.subPropertyOf))),
        },
        "annotation_assertions": sum(1 for _, p, _ in g if p in annots or p == RDFS.label),
        "triples": len(g),
        "hierarchy": {"max_depth_to_bfo_entity": max(depths, default=0),
                      "mean_depth_to_bfo_entity": round(mean(depths), 2) if depths else 0,
                      "max_local_depth": max(local_depth, default=0),
                      "local_roots": sum(1 for c in live.values() if c["parent"] not in live),
                      "leaves": sum(1 for cid in live if cid not in has_child),
                      "placement": dict(Counter(c.get("parent_source", "llm") for c in live.values()))},
        "bfo_categories": dict(Counter(bfo_category(cid, live) for cid in live).most_common()),
        "coverage": {"definition": cover(SKOS.definition), "alt_label": cover(SKOS.altLabel),
                     "source_paper": cover(DCTERMS.source),
                     "figure_reference": cover(URIRef(base() + "figureReference")),
                     "external_mapping": round(len(mapped) / n, 3)},
        "mappings": {"by_relation": dict(Counter(m["relation"] for m in mappings)),
                     "label_matched": sum(1 for m in mappings if m.get("label_match")),
                     "downgraded": sum(1 for m in mappings if "downgraded_from" in m),
                     "added_from_label_match": sum(1 for m in mappings if m.get("source") == "label_match"),
                     "mean_confidence": round(sum(m.get("confidence") or 0 for m in mappings) / len(mappings), 3)
                     if mappings else None,
                     "classes_with_label_match_candidate": sum(1 for c in live.values()
                                                               if any(x.get("label_match") for x in c.get("candidates", []))),
                     "by_ontology": dict(Counter(m["ontology"] for m in mappings)),
                     "classes_with_candidates": sum(1 for c in live.values() if c.get("candidates"))},
        "local_properties_used": {k: v.get("uses", 0) for k, v in properties.items()},
        "facets": {"study_stage": dict(Counter((c.get("facets") or {}).get("study_stage", ["none"])[0]
                                               for c in live.values()).most_common()),
                   "domain": dict(Counter((c.get("facets") or {}).get("domain", "none") for c in live.values())),
                   "with_subdomain": sum(1 for c in live.values() if (c.get("facets") or {}).get("subdomain")),
                   "source": dict(Counter((c.get("facets") or {}).get("source", "none") for c in live.values()))},
    }
