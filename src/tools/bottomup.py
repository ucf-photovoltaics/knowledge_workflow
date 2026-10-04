"""Bottom-up domain layer: the literature's own vocabulary as a SKOS concept scheme, next to the BFO/CCO ontology.

Built only from what the papers say, with no upper ontology:
- skos:broader from extracted is_a relations and obvious lexical heads (cycles skipped);
- every extracted relation and causal claim as a direct link plus a kw:Claim node (support, evidence, condition,
  source papers), whether or not it holds universally;
- every reported value as a kw:ReportedValue node;
- kw:ontologyClass links each concept to its class in the run's BFO/CCO ontology.
"""
import re
from collections import Counter

import rdflib
from rdflib import BNode, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS, XSD

from src.agents.ontology import slug
from src.tools import lexical, upper
from src.tools.owl import base


def build(domain: str, norm: dict, classes: list[dict], papers: list[dict]) -> tuple[rdflib.Graph, dict]:
    kw, rel = Namespace(base()), Namespace(f"{base()}rel/")
    ns = Namespace(f"{base()}{domain}/concept/")
    g = rdflib.Graph()
    for prefix, n in (("kw", base()), ("rel", str(rel)), ("c", str(ns)), ("skos", SKOS), ("dcterms", DCTERMS),
                      ("obo", "http://purl.obolibrary.org/obo/"), ("cco", "https://www.commoncoreontologies.org/")):
        g.bind(prefix, n)
    scheme = URIRef(f"{base()}{domain}/concepts")
    g.add((scheme, RDF.type, SKOS.ConceptScheme))
    g.add((scheme, DCTERMS.title, Literal(f"Literature concept layer: {domain}", lang="en")))
    g.add((scheme, RDFS.comment, Literal("Bottom-up layer built only from the corpus: concepts, is-a and lexical "
                                         "hierarchy, reported relations, causal claims and values, with provenance.",
                                         lang="en")))

    concepts = norm["concepts"]
    iri, used = {}, set()
    for c in concepts:
        name = slug(c["label"])
        name = name if name not in used else f"{name}_{c['id']}"
        used.add(name)
        iri[c["id"]] = ns[name]
    ontology_class = {c["id"]: c["iri"] for c in classes if not c.get("excluded")}
    facets = {c["id"]: c.get("facets") for c in classes if c.get("facets")}
    facet_props = {k: URIRef(v) for k, v in upper.facets()["annotation_properties"].items()}
    source = {p["key"]: URIRef(f"https://doi.org/{p['doi']}") if p.get("doi") else Literal(f"zotero:{p['key']}")
              for p in papers}

    for c in concepts:
        C = iri[c["id"]]
        g.add((C, RDF.type, SKOS.Concept))
        g.add((C, SKOS.inScheme, scheme))
        g.add((C, SKOS.prefLabel, Literal(c["label"], lang="en")))
        for a in c.get("alt_labels", []):
            g.add((C, SKOS.altLabel, Literal(a, lang="en")))
        for d in c.get("definitions", []):
            g.add((C, SKOS.definition, Literal(d["text"], lang="en")))
        g.add((C, kw.conceptType, Literal(c.get("type", ""))))
        g.add((C, kw.importanceScore, Literal(c["score"], datatype=XSD.decimal)))
        g.add((C, kw.importanceTier, Literal(c["tier"])))
        g.add((C, kw.paperCount, Literal(c["n_papers"], datatype=XSD.integer)))
        if c.get("causal_rank") is not None:
            g.add((C, kw.causalRank, Literal(c["causal_rank"], datatype=XSD.integer)))
        for k in c["papers"]:
            if k in source:
                g.add((C, DCTERMS.source, source[k]))
        if c["id"] in ontology_class:
            g.add((C, kw.ontologyClass, URIRef(ontology_class[c["id"]])))
        for stage in (facets.get(c["id"]) or {}).get("study_stage", []):
            g.add((C, facet_props["study_stage"], Literal(stage)))
        for k in ("domain", "subdomain"):
            if (facets.get(c["id"]) or {}).get(k):
                g.add((C, facet_props[k], Literal(facets[c["id"]][k])))

    # hierarchy from the literature: extracted is_a first (best supported first), then obvious lexical heads
    broader, counts = {}, Counter()

    def ancestors(cid):
        seen = []
        while cid in broader and broader[cid] not in seen:
            cid = broader[cid]
            seen.append(cid)
        return seen

    candidates = [(r["s"], r["o"], "is_a") for r in sorted(norm["relations"], key=lambda r: -r["support"])
                  if r["p"] == "is_a"]
    candidates += [(child, head, "lexical") for child, head in lexical.heads(concepts).items()]
    for child, parent, kind in candidates:
        if child in broader:
            continue
        if child == parent or child in ancestors(parent):
            counts[f"cycle_skipped_{kind}"] += 1
            continue
        broader[child] = parent
        counts[f"broader_{kind}"] += 1
        g.add((iri[child], SKOS.broader, iri[parent]))
    for c in concepts:
        if c["id"] not in broader:
            g.add((iri[c["id"]], SKOS.topConceptOf, scheme))
            g.add((scheme, SKOS.hasTopConcept, iri[c["id"]]))

    def claim(s, p, o, r):
        g.add((iri[s], p, iri[o]))
        node = BNode()
        g.add((node, RDF.type, kw.Claim))
        g.add((node, RDF.subject, iri[s]))
        g.add((node, RDF.predicate, p))
        g.add((node, RDF.object, iri[o]))
        g.add((node, kw.support, Literal(r["support"], datatype=XSD.integer)))
        for e in r.get("evidence", [])[:2]:
            g.add((node, kw.evidence, Literal(e["text"])))
        if any(e.get("verified") for e in r.get("evidence", [])):
            g.add((node, kw.evidenceVerified, Literal(True)))
        if not any(e.get("text") and e.get("status") != "unevidenced" for e in r.get("evidence", [])):
            g.add((node, kw.evidenceStatus, Literal("unevidenced")))
        for cond in r.get("conditions", []):
            g.add((node, kw.condition, Literal(cond)))
        for k in r["papers"]:
            if k in source:
                g.add((node, DCTERMS.source, source[k]))

    predicates = Counter()
    # predicates become IRIs: keep letters and digits only ("provides (enables/creates)" -> provides_enables_creates;
    # ">=" -> dropped). Also covers runs normalized before normalization cleaned them.
    pred = lambda p: re.sub(r"[^a-z0-9]+", "_", str(p or "").lower()).strip("_")
    norm = {**norm, "relations": [{**r, "p": pred(r.get("p"))} for r in norm["relations"] if pred(r.get("p"))],
            "causal": [{**r, "polarity": pred(r.get("polarity")) or "affects"} for r in norm["causal"]]}
    standard = {p: upper.relation_iri(p) for p in {r["p"] for r in norm["relations"]}}  # RO/BFO/CCO where one fits
    for r in norm["relations"]:
        if r["p"] != "is_a":
            claim(r["s"], URIRef(standard[r["p"]]) if standard[r["p"]] else rel[r["p"]], r["o"], r)
            predicates[r["p"]] += 1
    for r in norm["causal"]:
        claim(r["cause"], rel[r["polarity"]], r["effect"], r)
        predicates[f"causal:{r['polarity']}"] += 1
    for p in {r["p"] for r in norm["relations"]} | {r["polarity"] for r in norm["causal"]}:
        P = URIRef(standard[p]) if standard.get(p) else rel[p]
        g.add((P, RDF.type, RDF.Property))
        g.add((P, RDFS.label, Literal(upper.describe(standard[p]).get("label", p) if standard.get(p)
                                      else p.replace("_", " "), lang="en")))

    for m in norm.get("measurements", []):
        if m["concept"] not in iri:
            continue
        node = BNode()
        g.add((node, RDF.type, kw.ReportedValue))
        g.add((node, kw.ofConcept, iri[m["concept"]]))
        if m.get("entity") in iri:
            g.add((node, kw.measuredOn, iri[m["entity"]]))
        if m.get("property_missing"):
            g.add((node, kw.propertyMissing, Literal(True)))
        g.add((node, kw.value, Literal(m["value"])))
        for k in ("unit", "condition", "evidence"):
            if m.get(k):
                g.add((node, kw[k], Literal(m[k])))
        if m.get("paper") in source:
            g.add((node, DCTERMS.source, source[m["paper"]]))

    depths = [len(ancestors(c["id"])) for c in concepts]
    metrics = {
        "concepts": len(concepts), **counts,
        "top_concepts": sum(1 for c in concepts if c["id"] not in broader),
        "max_depth": max(depths, default=0), "mean_depth": round(sum(depths) / len(depths), 2) if depths else 0,
        "relation_links": sum(v for k, v in predicates.items() if not k.startswith("causal:")),
        "causal_links": sum(v for k, v in predicates.items() if k.startswith("causal:")),
        "reported_values": len(norm.get("measurements", [])),
        "linked_to_ontology_class": sum(1 for c in concepts if c["id"] in ontology_class),
        "triples": len(g), "predicates": dict(predicates.most_common()),
        "relation_links_standard_property": sum(v for k, v in predicates.items() if standard.get(k)),
        "relation_links_unevidenced": sum(1 for r in norm["relations"] if r["p"] != "is_a" and not any(
            e.get("text") and e.get("status") != "unevidenced" for e in r.get("evidence", []))),
    }
    return g, metrics
