"""Bounded, read-only research views over prepared graph projections."""
from collections import deque
from pathlib import Path
import csv
import hashlib
import io
import json
from uuid import uuid4
from dpv_dashboard import catalog, research, visual_graph, model

PRESETS = {"overview": "Combined overview", "findings": "Research findings",
           "ontology": "Ontology structure", "connections": "Cross-domain connections"}
KINDS = {"findings": {"Literature claim"},
         "ontology": {"Hierarchy", "Ontology restriction", "Property domain/range", "Disjointness", "Cross-ontology mapping"},
         "connections": {"Cross-ontology mapping"}}


def available(root, path):
    """Validate scope with metadata; content is read only when a view actually needs it."""
    root, path = Path(root).resolve(), Path(path).resolve()
    relative = path.relative_to(root)
    path = model.inside(root, str(relative))
    if catalog.restricted(relative) or not path.is_file():
        raise ValueError("This ontology is unavailable or restricted.")
    return path


def files(root, selected, literature=True):
    """Match viewer bundle identities without repeated GCS content probes during polling."""
    if root is None or selected is None:
        return (), []
    root, selected = Path(root).resolve(), Path(selected).resolve()
    entries, missing = [], []
    def add(base, path, kind):
        try:
            value = available(base, path)
        except (OSError, ValueError):
            value = None
        stamp = catalog.fingerprint(value) if value else None
        if not stamp or stamp[1] > 64 * 1024 * 1024:
            missing.append(f"{base.name}: {path.name} unavailable or too large")
            return
        if not any(e[0] == str(value) for e in entries):
            entries.append((str(value), stamp, base.name, kind))
    add(root, selected, "Selected ontology")
    integrated = (root / "integration.json").is_file()
    sources = research.source_roots(root)
    if integrated:
        known = {p.name for p in sources}
        for entry in research.records(catalog.load(root / "integration.json", {}).get("inputs", [])):
            name = entry.get("run_id")
            if isinstance(name, str) and name not in known:
                missing.append("Recorded source run unavailable: " + name[:160])
    for source in sources:
        if integrated:
            add(source, source / "ontology.ttl", "Domain ontology")
        if literature:
            add(source, source / "domain_layer.ttl", "Literature claims")
    return tuple(entries), missing


def subset(payload, node_ids, edge_ids=None):
    nodes = set(node_ids)
    edges = [e for e in payload["propertyAttribute"] if e["domain"] in nodes and e["range"] in nodes
             and (edge_ids is None or e["id"] in edge_ids)]
    ids = {e["id"] for e in edges}
    return {**payload, "class": [n for n in payload["class"] if n["id"] in nodes],
            "classAttribute": [n for n in payload["classAttribute"] if n["id"] in nodes],
            "property": [e for e in payload["property"] if e["id"] in ids], "propertyAttribute": edges,
            "_dpv": {**payload["_dpv"], "token": uuid4().hex,
                     "edges": {k: v for k, v in payload["_dpv"]["edges"].items() if k in ids}}}


def view(payload, preset="overview", focus="", depth=0, relation="", domain="", hidden=()):
    if preset not in PRESETS or depth not in (0, 1, 2):
        raise ValueError("Choose a supported graph preset and depth (one or two hops).")
    attrs = {n["id"]: n for n in payload["classAttribute"]}
    details = payload["_dpv"]["edges"]
    edges = [e for e in payload["propertyAttribute"] if
             (preset == "overview" or details[e["id"]]["kind"] in KINDS[preset])
             and (not relation or details[e["id"]]["relation"] == relation)
             and (not domain or any(s["run"] == domain for s in details[e["id"]]["sources"]))]
    seed = next((k for k, v in attrs.items() if v["iri"] == focus), None)
    if focus and seed is None:
        raise ValueError("This concept is absent from the selected graph settings.")
    nodes = set(attrs) if preset == "overview" and not relation and not domain else {x for e in edges for x in (e["domain"], e["range"])}
    if seed and depth:
        adjacency = {}
        for edge in edges:
            a, b = edge["domain"], edge["range"]
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
        nodes, frontier = {seed}, {seed}
        for _ in range(depth):
            frontier = {n for x in frontier for n in adjacency.get(x, ())} - nodes
            nodes.update(frontier)
    nodes -= {k for k, v in attrs.items() if v["iri"] in hidden}
    result = subset(payload, nodes, {e["id"] for e in edges})
    result["_dpv"]["view"] = {"preset": preset, "focus": focus, "depth": depth,
                               "relation": relation, "domain": domain}
    return result


def prepare(request):
    base, preset, depth, relation, domain, hidden = request
    # Default overview retains the persisted ready-to-load bundle path.
    if preset == "overview" and not depth and not relation and not domain and not hidden:
        return visual_graph.prepare(*base)
    entries, focus, limit, disjoint, hierarchy, mappings, literature = base
    payload, loaded, failed, seconds = visual_graph.projection(entries, disjoint, hierarchy, mappings, literature)
    selected = view(payload, preset, focus, depth, relation, domain, hidden)
    return visual_graph.bounded(selected, focus if focus and not hidden else "", limit, loaded, failed, seconds)


def path(payload, start, end, kinds, max_hops=3, direction="outgoing"):
    if not 1 <= max_hops <= 6 or direction not in ("outgoing", "either"):
        raise ValueError("Use one to six hops and a supported direction.")
    nodes = {v["iri"]: v["id"] for v in payload["classAttribute"]}
    if start not in nodes or end not in nodes:
        raise ValueError("Choose both endpoint concepts from this graph scope.")
    if not kinds or not set(kinds) <= {v["kind"] for v in payload["_dpv"]["edges"].values()}:
        raise ValueError("Choose recorded relationship types for the path.")
    source, target = nodes[start], nodes[end]
    adjacency = {}
    for e in payload["propertyAttribute"]:
        if payload["_dpv"]["edges"][e["id"]]["kind"] in kinds:
            adjacency.setdefault(e["domain"], []).append((e["range"], e["id"], False))
            if direction == "either":
                adjacency.setdefault(e["range"], []).append((e["domain"], e["id"], True))
    queue, seen = deque([(source, [])]), {source}
    while queue:
        node, steps = queue.popleft()
        if node == target:
            return steps
        if len(steps) >= max_hops:
            continue
        for neighbor, edge, reverse in sorted(adjacency.get(node, ())):
            if neighbor not in seen:
                if len(seen) >= 50000:
                    raise ValueError("Path search reached its 50,000-node limit. Narrow the relationship types.")
                seen.add(neighbor)
                queue.append((neighbor, [*steps, {"edge": edge, "reverse": reverse}]))
    return None


def paper_identity(paper, key):
    doi = str(paper.get("doi", "")).strip().lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    return "doi:" + doi if doi else "record:" + key + ":" + str(paper.get("title", "")).strip().casefold()


def fingerprint(entries):
    sources = [(Path(path).name, stamp, run, kind) for path, stamp, run, kind in entries]
    return hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()


def compare(left, right):
    def records(root):
        papers, concepts = {}, {}
        for source in research.source_roots(root):
            data = research.index(source)
            for key, paper in data.papers.items():
                identity = paper_identity(paper, key)
                papers[identity] = paper.get("title", key)
                labels = {data.label(row.get("canonical_id")).casefold() for row in data.lineage if row.get("paper") == key and row.get("lineage_status") == "recorded"}
                concepts.setdefault(identity, set()).update(labels)
        return papers, concepts
    lp, lc = records(left)
    rp, rc = records(right)
    shared = set(lp) & set(rp)
    a = set().union(*(lc.get(k, set()) for k in shared)) if shared else set()
    b = set().union(*(rc.get(k, set()) for k in shared)) if shared else set()
    return {"shared_papers": len(shared), "shared_papers_with_lineage": sum(bool(lc.get(k)) and bool(rc.get(k)) for k in shared), "left_papers": len(lp), "right_papers": len(rp),
            "shared_labels": sorted(a & b), "left_only_labels": sorted(a - b), "right_only_labels": sorted(b - a),
            "method": "DOI match, otherwise exact paper key and title; labels compared only within shared papers using recorded lineage. Label agreement is not semantic agreement or a quality ranking."}


def export(payload, entries, scope, format="json", papers=None):
    if format not in ("json", "csv", "bib"):
        raise ValueError("Choose JSON, CSV or BibTeX export.")
    sources = [{"run": run, "file": Path(p).name, "mtime_ns": stamp[0], "bytes": stamp[1], "layer": kind}
               for p, stamp, run, kind in entries]
    signature = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    edges = payload["_dpv"]["edges"]
    metadata = {"scope": scope, "source_signature": signature, "sources": sources,
                "view": payload["_dpv"].get("view", {}), "settings": payload["_dpv"].get("settings", {}), "coverage": payload["_dpv"].get("coverage", {}),
                "subset": True, "interpretation": "Recorded graph relationships; a graph path does not establish causation."}
    if format == "json":
        return json.dumps({"metadata": metadata, "nodes": payload["classAttribute"], "relationships": edges}, ensure_ascii=False, indent=2)
    if format == "csv":
        handle = io.StringIO(newline="")
        writer = csv.writer(handle)
        writer.writerow(["scope", "source_signature", "subject", "relation", "object", "origin", "quote", "conditions", "papers", "source_files"])
        def cell(value):
            text = str(value)
            return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text
        for e in edges.values():
            for claim in e["claims"] or [{}]:
                writer.writerow([cell(v) for v in (scope, signature, e["subject_name"], e["relation"], e["object_name"], e["kind"],
                    " | ".join(claim.get("quotes", [])), " | ".join(claim.get("conditions", [])), " | ".join(claim.get("papers", [])),
                    " | ".join(s["run"] + "/" + s["file"] for s in e["sources"]))])
        return handle.getvalue()
    citations = sorted({p for e in edges.values() for c in e["claims"] for p in c["papers"]})
    def escaped(value):
        return str(value).replace("\\", "\\textbackslash ").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")
    records = []
    seen = set()
    for citation in citations:
        paper = (papers or {}).get(citation, {})
        identity = paper_identity(paper, citation) if paper else citation
        if identity in seen:
            continue
        seen.add(identity)
        fields = {k: paper.get(k) for k in ("title", "year", "doi", "journal") if paper.get(k)}
        if paper.get("authors") and isinstance(paper["authors"], list):
            fields["author"] = " and ".join(str(a) for a in paper["authors"])
        fields["note"] = "Recorded citation " + citation + "; scope " + scope + "; source signature " + signature
        records.append("@misc{source" + str(len(records) + 1) + ",\n" + ",\n".join("  " + k + " = {" + escaped(v) + "}" for k, v in fields.items()) + "\n}")
    return "\n\n".join(records)


def saved_checks(root):
    rows = []
    if root is None:
        return rows
    for report in sorted((root / "quality").glob("**/summary.json")):
        allowed = catalog.accessible(root, str(report.relative_to(root)))
        if allowed is None:
            continue
        value = catalog.load(allowed, {})
        if not isinstance(value, dict) or not isinstance(value.get("checks"), dict):
            continue
        robot = value.get("robot_version", {})
        robot = robot.get("value", "Not recorded") if isinstance(robot, dict) else robot
        for name, check in value["checks"].items():
            if not isinstance(check, dict):
                continue
            rows.append({"target": Path(value.get("source", "")).name, "check": name,
                         "status": check.get("status", "not_recorded"), "assessed": value.get("created", "Not recorded"),
                         "input_sha256": value.get("sha256", "Not recorded"),
                         "tool_version": value.get(name + "_version", robot),
                         "message": check.get("message", ""), "metrics": check.get("metric_count", ""),
                         "report": str(report.relative_to(root)), "results": check.get("results", [])})
    return rows
