"""Cross-domain integration: input run selection, the master ontology, its validation, report and eval row.

The master ontology owl:imports every domain ontology unchanged and adds only mapping axioms between their classes
(plus the declarations and labels of the mapped classes, copied from the domain graphs). master_merged.ttl is the
union of the domain graphs and the master, for loading into one triple store."""
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import rdflib
from rdflib import BNode, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

from src import config
from src.tools import owl, reports

PREDICATES = {"equivalent": OWL.equivalentClass, "exact": SKOS.exactMatch, "close": SKOS.closeMatch,
              "broader": SKOS.narrowMatch, "narrower": SKOS.broadMatch}  # A broader than B -> A skos:narrowMatch B
PREDICATE_NAMES = {"equivalent": "owl:equivalentClass", "exact": "skos:exactMatch", "close": "skos:closeMatch",
                   "broader": "skos:narrowMatch", "narrower": "skos:broadMatch", "shared_iri": "(same IRI)"}
ANNOTATIONS = {"mappingConfidence": "mapping confidence", "mappingSource": "mapping source",
               "embeddingSimilarity": "label embedding similarity", "downgradedFrom": "relation proposed before checks",
               "candidateKind": "candidate kind", "sourceRun": "source run"}


def _manifest(run_dir: Path) -> dict | None:
    try:
        return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def select_runs(outputs: Path, collections: list[str] | None, run_ids: list[str] | None) -> tuple[list[dict], list[str]]:
    """One completed run (interop done, ontology.ttl present) per domain. Returns (selected, notes)."""
    notes, chosen = [], []
    complete = lambda m, d: m and "interop" in m.get("stages", {}) and (d / "ontology.ttl").exists() \
        and (d / "ontology" / "enriched.json").exists()
    if run_ids:
        for rid in run_ids:
            d = outputs / rid
            m = _manifest(d)
            if not complete(m, d):
                raise SystemExit(f"{rid}: not a completed run in {outputs} (needs interop, ontology.ttl, enriched.json)")
            chosen.append((d, m))
    else:
        runs = defaultdict(list)
        for d in outputs.iterdir():
            m = _manifest(d) if d.is_dir() else None
            if complete(m, d):
                runs[m["collection"]["name"]].append((d, m))
        for name in collections or config.INTEGRATION["collections"]:
            options = sorted(runs.get(name, []), key=lambda x: x[1].get("created", ""))
            if not options:
                notes.append(f"{name}: no completed run; left out")
                continue
            current = [x for x in options if x[1]["config"].get("workflow_revision") == config.WORKFLOW_REVISION]
            if not current:
                notes.append(f"{name}: no run at revision {config.WORKFLOW_REVISION}; using the latest older run")
            chosen.append((current or options)[-1])
    domains = Counter(m["collection"]["name"] for _, m in chosen)
    if dup := [d for d, n in domains.items() if n > 1]:
        raise SystemExit(f"more than one run for domain(s) {dup}; pass one run id per domain")
    selected = []
    for d, m in chosen:
        selected.append({"run_id": d.name, "dir": d, "domain": m["collection"]["name"], "manifest": m,
                         "revision": m["config"].get("workflow_revision"), "profile": m["config"].get("llm_profile"),
                         "created": m.get("created")})
    if len({s["revision"] for s in selected}) > 1:
        notes.append("input runs come from different workflow revisions: " +
                     ", ".join(f"{s['domain']}={s['revision'] or 'none'}" for s in selected))
    return selected, notes


def load_domain(s: dict) -> tuple[list[dict], rdflib.Graph, str]:
    """Live classes in the shape the integration agent reads, the domain graph and its ontology IRI."""
    classes = json.loads((s["dir"] / "ontology" / "enriched.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in classes}
    out = []
    for c in classes:
        if c.get("excluded"):
            continue
        out.append({"iri": c["iri"], "label": c["label"], "domain": s["domain"], "run": s["run_id"],
                    "alt_labels": [a for a in c.get("alt_labels", []) if isinstance(a, str)],
                    "category": owl.bfo_category(c["id"], by_id), "parent_label": owl.label_of(c["parent"], by_id),
                    "definition": c.get("definition") or "", "type": c.get("type", ""), "score": c.get("score")})
    g = rdflib.Graph().parse(s["dir"] / "ontology.ttl", format="turtle")
    onto = next((str(o) for o in g.subjects(RDF.type, OWL.Ontology)), f"{owl.base()}{s['domain']}")
    return out, g, onto


def build_master(selected: list[dict], graphs: dict, mappings: list[dict], integration_id: str) -> rdflib.Graph:
    kw = Namespace(owl.base())
    g = rdflib.Graph()
    for prefix, ns in (("kw", owl.base()), ("skos", SKOS), ("dcterms", DCTERMS), ("owl", OWL)):
        g.bind(prefix, ns)
    onto = URIRef(f"{owl.base()}master")
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, OWL.versionIRI, URIRef(f"{owl.base()}master/version/{integration_id}")))
    g.add((onto, OWL.versionInfo, Literal(integration_id)))
    g.add((onto, DCTERMS.title, Literal(f"{config.ONTOLOGY_TITLE}: cross-domain master", lang="en")))
    g.add((onto, DCTERMS.created, Literal(datetime.now(timezone.utc).isoformat(timespec="seconds"), datatype=XSD.dateTime)))
    g.add((onto, DCTERMS.description, Literal(
        "Imports the domain ontologies of one run set unchanged and maps their classes to each other. Mappings are "
        "LLM-assisted with deterministic checks and are intended for domain-expert review.", lang="en")))
    for s in selected:
        g.add((onto, OWL.imports, URIRef(graphs[s["domain"]]["iri"])))
        g.add((onto, DCTERMS.source, Literal(s["run_id"])))
    for name, label in ANNOTATIONS.items():
        g.add((kw[name], RDF.type, OWL.AnnotationProperty))
        g.add((kw[name], RDFS.label, Literal(label, lang="en")))
    for ap in (SKOS.exactMatch, SKOS.closeMatch, SKOS.broadMatch, SKOS.narrowMatch,
               DCTERMS.title, DCTERMS.created, DCTERMS.description, DCTERMS.source):
        g.add((ap, RDF.type, OWL.AnnotationProperty))
    declared = set()
    for m in mappings:
        for side in ("a", "b"):
            iri = URIRef(m[f"{side}_iri"])
            if iri not in declared:
                declared.add(iri)
                g.add((iri, RDF.type, OWL.Class))
                for lab in graphs[m[f"{side}_domain"]]["graph"].objects(iri, RDFS.label):
                    g.add((iri, RDFS.label, lab))
        if m["relation"] not in PREDICATES:
            continue  # shared_iri: the domains already use the same class IRI
        A, P, B = URIRef(m["a_iri"]), PREDICATES[m["relation"]], URIRef(m["b_iri"])
        g.add((A, P, B))
        ax = BNode()
        g.add((ax, RDF.type, OWL.Axiom))
        g.add((ax, OWL.annotatedSource, A))
        g.add((ax, OWL.annotatedProperty, P))
        g.add((ax, OWL.annotatedTarget, B))
        g.add((ax, kw.mappingSource, Literal(m["source"])))
        g.add((ax, kw.candidateKind, Literal(m["candidate_kind"])))
        if m.get("confidence") is not None:
            g.add((ax, kw.mappingConfidence, Literal(round(float(m["confidence"]), 4), datatype=XSD.decimal)))
        if m.get("similarity") is not None:
            g.add((ax, kw.embeddingSimilarity, Literal(round(float(m["similarity"]), 4), datatype=XSD.decimal)))
        if m.get("downgraded_from"):
            g.add((ax, kw.downgradedFrom, Literal(m["downgraded_from"])))
    return g


def validate(master: rdflib.Graph, master_text: str, graphs: dict, mappings: list[dict]) -> dict:
    """Structural checks only (no reasoner)."""
    issues = []
    reparsed = rdflib.Graph().parse(data=master_text, format="json-ld")
    roundtrip = len(reparsed) == len(master)
    if not roundtrip:
        issues.append(f"JSON-LD round trip changed triple count: {len(master)} -> {len(reparsed)}")
    domain_of = {}
    for m in mappings:
        for side in ("a", "b"):
            iri, dom = m[f"{side}_iri"], m[f"{side}_domain"]
            domain_of[iri] = dom
            if (URIRef(iri), RDF.type, OWL.Class) not in graphs[dom]["graph"]:
                issues.append(f"mapped class not declared in the {dom} ontology: {iri}")
        if m["a_domain"] == m["b_domain"]:
            issues.append(f"mapping within one domain: {m['a_iri']} {m['relation']} {m['b_iri']}")
    eq = {}  # equivalence clusters must not hold two classes of one domain
    def find(x):
        eq.setdefault(x, x)
        while eq[x] != x:
            x = eq[x]
        return x
    for m in mappings:
        if m["relation"] in ("equivalent", "shared_iri"):
            eq[find(m["a_iri"])] = find(m["b_iri"])
    clusters = defaultdict(list)
    for iri in list(eq):
        clusters[find(iri)].append(iri)
    for members in clusters.values():
        doms = Counter(domain_of.get(i) for i in members)
        if any(n > 1 for d, n in doms.items() if d):
            issues.append(f"equivalence cluster joins classes of one domain: {sorted(members)[:4]}")
    merged_sub = defaultdict(set)  # subclass cycles across domains once equivalent classes are identified
    for g in [master, *(x["graph"] for x in graphs.values())]:
        for s, o in g.subject_objects(RDFS.subClassOf):
            if isinstance(s, URIRef) and isinstance(o, URIRef):
                merged_sub[find(str(s)) if str(s) in eq else str(s)].add(find(str(o)) if str(o) in eq else str(o))
    state = {}
    def cyclic(n):
        stack = [(n, iter(merged_sub.get(n, ())))]
        state[n] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = 2
                stack.pop()
            elif state.get(nxt) == 1:
                return nxt
            elif nxt not in state:
                state[nxt] = 1
                stack.append((nxt, iter(merged_sub.get(nxt, ()))))
        return None
    for n in list(merged_sub):
        if n not in state and (c := cyclic(n)):
            issues.append(f"subclass cycle after identifying equivalent classes, through {c}")
    return {"valid": not issues, "n_issues": len(issues), "jsonld_roundtrip": roundtrip, "triples": len(master),
            "issues": sorted(set(issues))[:300]}


def report(path: Path, integration_id: str, selected: list[dict], domains: dict, result: dict, validation: dict,
           compute: dict, notes: list[str], merged_triples: int) -> dict:
    """integration_report.md, and the flat metrics row for outputs/eval_integrations.csv."""
    st, maps, cands = result["stats"], result["mappings"], result["candidates"]
    names = [s["domain"] for s in selected]
    mapped = defaultdict(set)
    pair = Counter()
    for m in maps:
        mapped[m["a_domain"]].add(m["a_iri"])
        mapped[m["b_domain"]].add(m["b_iri"])
        pair[(m["a_domain"], m["b_domain"])] += 1
    lines = [f"# Cross-domain integration report: {integration_id}", "",
             "Mappings between the domain ontologies listed below. The master ontology imports them unchanged; only "
             "`owl:equivalentClass` is a logical axiom, every other mapping is SKOS. Structural validation does not "
             "establish that a mapping is correct.", ""]
    if notes:
        lines += ["## Notes", "", *[f"- {n}" for n in notes], ""]
    lines += ["## Inputs", "", reports._table(
        ["Domain", "Run", "Revision", "Profile", "Classes", "Classes mapped"],
        [[s["domain"], s["run_id"], s["revision"] or "-", s["profile"], len(domains[s["domain"]]),
          f"{len(mapped[s['domain']])} ({len(mapped[s['domain']]) / max(1, len(domains[s['domain']])):.0%})"]
         for s in selected]), ""]
    kinds = Counter(p["kind"] for p in cands)
    lines += ["## Candidates and decisions", "", reports._table(["Item", "Count"], [
        *[[f"candidates: {k}", v] for k, v in kinds.most_common()],
        ["reviewed by the model", sum(1 for p in cands if p.get("reviewed"))],
        ["not reviewed (over max_model_pairs)", st.get("candidates_unreviewed_over_cap", 0)],
        *[[f"model decision: {r}", st.get(f"decision_{r}", 0)] for r in ("equivalent", "exact", "close", "broader", "narrower", "none")],
        ["no model answer", st.get("decision_missing", 0)],
        ["added from same-label match", st.get("label_match_added", 0)],
        *[[k.replace("_", " "), v] for k, v in sorted(st.items()) if k.startswith("downgraded_")],
        ["failed calls", st.get("failed_calls", 0)]]), ""]
    rel = Counter(m["relation"] for m in maps)
    lines += ["## Mappings", "", reports._table(["Relation", "Predicate", "Count"], [
        [r, PREDICATE_NAMES[r], rel[r]]
        for r in ("equivalent", "exact", "close", "broader", "narrower", "shared_iri") if rel[r]]), ""]
    lines += ["### By domain pair", "", reports._table(["Domain A", "Domain B", "Mappings"],
                                                         [[a, b, n] for (a, b), n in sorted(pair.items())]), ""]
    bridges = result["clusters"]
    lines += ["## Bridge concepts", "",
              f"Concepts joined by equivalent, exact or shared-IRI mappings across two or more domains: {len(bridges)}.", ""]
    if bridges:
        lines += [reports._table(["Concept", "Domains", "Labels"],
                                 [[b["label"], ", ".join(b["domains"]),
                                   "; ".join(sorted({f"{m['domain']}: {m['label']}" for m in b["members"]}))[:200]]
                                  for b in bridges[:60]]), ""]
    lines += ["## Validation", "", f"- valid: {validation['valid']} ({validation['n_issues']} issues)",
              f"- master triples: {validation['triples']}; merged triples: {merged_triples}",
              *[f"- {i}" for i in validation["issues"][:30]], "",
              "## Compute", "", reports._table(["Calls", "Input tokens", "Output tokens", "Latency (s)", "Wall (s)"],
                                               [[compute["calls"], compute["input_tokens"], compute["output_tokens"],
                                                 round(compute["latency_s"], 1), round(compute["wall_s"], 1)]]), ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    row = {"run_id": integration_id, "row_type": "integration", "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "workflow_revision": config.WORKFLOW_REVISION, "llm_profile": config.LLM_PROFILE,
           "model_integration": config.model_for("integration"), "tier": config.tier("integration"),
           "embed_model": config.EMBED["model"], "domains": "+".join(names),
           "input_runs": "+".join(s["run_id"] for s in selected),
           "input_revisions": "+".join(sorted({s["revision"] or "none" for s in selected})),
           "classes_total": sum(len(domains[d]) for d in names),
           **{f"classes_{d}": len(domains[d]) for d in names},
           **{f"classes_mapped_share_{d}": round(len(mapped[d]) / max(1, len(domains[d])), 3) for d in names},
           "candidates_total": len(cands), **{f"candidates_{k}": v for k, v in kinds.items()},
           **{k: v for k, v in st.items() if not k.startswith("candidates_") or k == "candidates_unreviewed_over_cap"},
           "mappings_total": len(maps), **{f"pair_{a}__{b}": n for (a, b), n in pair.items()},
           "triples_master": validation["triples"], "triples_merged": merged_triples,
           "validation_valid": validation["valid"], "validation_issues": validation["n_issues"],
           **{f"compute_{k}": v for k, v in compute.items()}}
    return row


def merge(master: rdflib.Graph, graphs: dict) -> rdflib.Graph:
    """The domain graphs plus the master in one graph, for loading into a single triple store."""
    merged = rdflib.Graph()
    for prefix, ns in master.namespaces():
        merged.bind(prefix, ns)
    for g in [*(x["graph"] for x in graphs.values()), master]:
        merged += g
    return merged


def public_candidates(pairs: list[dict]) -> list[dict]:
    side = lambda c: {k: c[k] for k in ("domain", "label", "iri", "category", "parent_label")}
    return [{"id": p["id"], "kind": p["kind"], "similarity": p["score"], "reviewed": p.get("reviewed", False),
             "decision": p.get("decision"), "a": side(p["a"]), "b": side(p["b"])} for p in pairs]
