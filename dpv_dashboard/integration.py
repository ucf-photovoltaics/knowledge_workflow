"""Federated, source-scoped views; never merge paper-local or domain-local IDs.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from dpv_dashboard import catalog, research

VIEWS = {"source_papers": ("extract", "papers"), "source_figures": ("extract", "figures"), "source_evidence": ("extract", "claims"),
         "source_concepts": ("normalize", "concepts"), "source_lineage": ("normalize", "lineage"),
         "source_placements": ("ontology", "placements"), "source_definitions": ("enrich", "definitions"),
         "source_restrictions": ("enrich", "restrictions"), "source_external": ("interop", "mappings"),
         "source_contradictions": ("normalize", "contradictions")}


def sources(root):
    manifest = catalog.load(root / "integration.json", {}) if root else {}
    available = {p.name: p for p in research.source_roots(root)} if manifest else {}
    result = []
    for entry in research.records(manifest.get("inputs", [])):
        name = entry.get("run_id")
        if not isinstance(name, str):
            continue
        path = available.get(name)
        result.append({"source_run": name, "domain": entry.get("domain") or name,
                       "availability": "available" if path else "source run unavailable", "root": path})
    return result


def rows(root, view, domain=""):
    result = []
    for source in sources(root):
        if domain and source["source_run"] != domain:
            continue
        common = {k: v for k, v in source.items() if k != "root"}
        if view == "sources":
            data = research.index(source["root"])
            result.append({**common, "papers": len(data.papers), "concepts": len(data.concepts),
                           "definitions": sum(bool(c.get("definition")) for c in data.enriched.values()),
                           "restrictions": sum(len(c.get("restrictions", [])) for c in data.enriched.values()),
                           "external_mappings": len(data.mappings), "review_findings": len(data.review_rows())})
        elif source["root"]:
            data = research.index(source["root"])
            values = data.review_rows() if view == "source_review" else data.stage_rows(*VIEWS[view]) if view in VIEWS else []
            if view == "source_figures":
                values = [{**figure, "paper": key, "title": paper.get("title", key)} for key, paper in data.papers.items()
                          for figure in research.records(paper.get("figures"))]
            result.extend({**value, **common} for value in values)
    return result


def member(root, iri, run=None, domain=None, indexed=None):
    matches = []
    if not isinstance(iri, str) or not iri:
        return None
    available = indexed if indexed is not None else [(s, research.index(s["root"])) for s in sources(root) if s["root"]]
    for source, data in available:
        if not source["root"] or run and source["source_run"] != run or domain and source["domain"] != domain:
            continue
        cid = data.iri_ids.get(iri)
        if cid:
            matches.append((source, data, cid))
    return matches[0] if len(matches) == 1 else None


def summary(root):
    values = rows(root, "sources")
    return (f"Contributing sources: {len(values)}; available: {sum(v['availability'] == 'available' for v in values)}. "
            f"Source records: {sum(v['papers'] for v in values)} papers, {sum(v['concepts'] for v in values)} concepts, "
            f"{sum(v['definitions'] for v in values)} definitions, {sum(v['restrictions'] for v in values)} restrictions, "
            f"{sum(v['external_mappings'] for v in values)} external mappings and {sum(v['review_findings'] for v in values)} review findings. "
            "Counts retain domain/run scope; shared papers are counted in each contributing run. Source details describe saved domain outputs, not new integration decisions.")
