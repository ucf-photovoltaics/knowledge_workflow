"""Portable viewer bundles. Readers never write to research outputs or the cache mount."""
from functools import lru_cache
from pathlib import Path
from itertools import product
from uuid import uuid4
import gzip
import hashlib
import json
import os
from dpv_dashboard import catalog, model

MAX_ASSET = 256 * 1024 * 1024


@lru_cache(maxsize=1)
def version():
    import rdflib
    digest = hashlib.sha256(rdflib.__version__.encode())
    for name in ("viewer_cache.py", "visual_graph.py", "viewer.py", "quality.py", "exploration.py", "research.py"):
        digest.update((Path(__file__).parent / name).read_bytes())
    return digest.hexdigest()


def source_root():
    return Path(os.environ.get("DPV_SHARE_ROOT", model.ROOT / "outputs")).resolve()


def relative(path):
    path = Path(path).resolve()
    value = path.relative_to(source_root())
    if catalog.restricted(value):
        raise ValueError("Private files cannot be cached.")
    return value.as_posix()


def identity(entries, literature):
    if not entries:
        raise ValueError("A viewer bundle needs a selected ontology.")
    key = hashlib.sha256(json.dumps([relative(entries[0][0]), bool(literature)]).encode()).hexdigest()
    sources = [(relative(path), stamp, run, kind) for path, stamp, run, kind in entries]
    signature = hashlib.sha256(json.dumps([version(), sources], sort_keys=True).encode()).hexdigest()
    return key, signature


def directory(entries, literature):
    configured = os.environ.get("DPV_VIEWER_CACHE", "").strip()
    if not configured:
        return None, None
    key, signature = identity(entries, literature)
    return Path(configured).resolve() / key, signature


def manifest(entries, literature):
    try:
        folder, signature = directory(entries, literature)
        if folder is None:
            return None
        path = folder / "manifest.json"
        if path.stat().st_size > 1024 * 1024:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("signature") != signature or value.get("version") != version():
            return None
        return folder, value
    except (OSError, ValueError, TypeError, KeyError):
        return None


@lru_cache(maxsize=2)
def _asset(path, stamp):
    if stamp is None or stamp[1] > MAX_ASSET:
        raise ValueError("Viewer cache asset is unavailable or too large.")
    with gzip.open(path, "rb") as handle:
        contents = handle.read(MAX_ASSET + 1)
    if len(contents) > MAX_ASSET:
        raise ValueError("Viewer cache asset exceeds its expanded size limit.")
    return json.loads(contents)


def asset(folder, name):
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".json.gz"):
        raise ValueError("Invalid viewer cache asset name.")
    path = folder / name
    if not path.resolve().is_relative_to(folder.resolve()):
        raise ValueError("Viewer cache asset escapes its bundle.")
    return _asset(str(path), catalog.fingerprint(path))


def flags(disjoint, hierarchy, mappings):
    return "".join(str(int(bool(value))) for value in (disjoint, hierarchy, mappings))


def fresh(payload):
    return {**payload, "_dpv": {**payload["_dpv"], "token": uuid4().hex}}


def load_view(entries, focus, limit, disjoint, hierarchy, mappings, literature):
    if focus or limit not in (160, 400):
        return None
    try:
        saved = manifest(entries, literature)
        if saved is None:
            return None
        folder, value = saved
        return fresh(asset(folder, value["views"][flags(disjoint, hierarchy, mappings) + "-" + str(limit)]))
    except (OSError, ValueError, TypeError, KeyError, EOFError):
        return None


def filtered(payload, disjoint, hierarchy, mappings, literature):
    hidden = set()
    for enabled, kind in ((disjoint, "Disjointness"), (hierarchy, "Hierarchy"),
                          (mappings, "Cross-ontology mapping"), (literature, "Literature claim")):
        if not enabled:
            hidden.add(kind)
    details = {key: row for key, row in payload["_dpv"]["edges"].items() if row["kind"] not in hidden}
    edges = [row for row in payload["propertyAttribute"] if row["id"] in details]
    nodes = set(payload["_dpv"]["base_nodes"])
    nodes.update(value for edge in edges for value in (edge["domain"], edge["range"]))
    return {**payload, "class": [row for row in payload["class"] if row["id"] in nodes],
            "classAttribute": [row for row in payload["classAttribute"] if row["id"] in nodes],
            "property": [row for row in payload["property"] if row["id"] in details], "propertyAttribute": edges,
            "_dpv": {**payload["_dpv"], "edges": details,
                     "settings": {"disjoint": disjoint, "hierarchy": hierarchy, "mappings": mappings, "literature": literature}}}


def load_projection(entries, disjoint, hierarchy, mappings, literature):
    try:
        saved = manifest(entries, literature)
        if saved is None:
            return None
        folder, value = saved
        payload = filtered(asset(folder, value["projection"]), disjoint, hierarchy, mappings, literature)
        return payload, value["loaded"], value["failed"], 0
    except (OSError, ValueError, TypeError, KeyError, EOFError):
        return None


def research_signature(root):
    from dpv_dashboard import research
    paths = []
    for source in research.source_roots(root):
        paths.extend(path for path in source.rglob("*.json") if not catalog.restricted(path.relative_to(source)))
    return hashlib.sha256(json.dumps(sorted((relative(path), catalog.fingerprint(path)) for path in paths)).encode()).hexdigest()


def load_documents(root, ontology, excluded):
    if ontology is None:
        return None
    try:
        from dpv_dashboard import visual_graph
        entries, missing = visual_graph.files(root, ontology, True)
        saved = manifest(entries, True)
        if saved is None:
            return None
        folder, value = saved
        if value.get("research_signature") != research_signature(root):
            return None
        documents = asset(folder, value["documents"])
        rows = [{**row, "root": str(model.inside(source_root(), row["root"]))} for row in documents["rows"]]
        if excluded is not None:
            excluded.extend(documents["excluded"])
        return rows
    except (OSError, ValueError, TypeError, KeyError, EOFError):
        return None


def write_asset(folder, name, value):
    path = folder / name
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))


def build(root, ontology, literature=True, force=False):
    """Publish immutable assets first, then a manifest; never publish mid-write inputs."""
    from dpv_dashboard import visual_graph, exploration
    from dpv_dashboard.viewer import convert
    entries, missing = visual_graph.files(root, ontology, literature)
    if not entries or Path(entries[0][0]) != ontology.resolve():
        raise ValueError("Selected ontology is unavailable or too large.")
    folder, signature = directory(entries, literature)
    if folder is None:
        raise ValueError("Set DPV_VIEWER_CACHE to the builder's writable cache directory.")
    research_stamp = research_signature(root) if literature else None
    existing = manifest(entries, literature)
    if not force and existing and existing[1].get("research_signature") == research_stamp:
        saved = existing[1]
        names = [saved.get("projection"), saved.get("index"), *saved.get("views", {}).values()]
        if literature:
            names.append(saved.get("documents"))
        try:
            if len(saved.get("views", {})) == 16:
                for name in names:
                    asset(folder, name)
                return "unchanged"
        except (OSError, ValueError, TypeError, KeyError, EOFError):
            pass
    folder.mkdir(parents=True, exist_ok=True)
    graph, origins, loaded, failed = visual_graph.assemble(entries)
    if failed:
        raise ValueError("Source files could not be parsed: " + "; ".join(failed))
    payload = convert(graph, show_disjoint=True, show_hierarchy=True, show_mappings=True,
                      show_literature=literature, origins=origins)
    generation = uuid4().hex
    value = {"version": version(), "signature": signature, "selected": relative(ontology),
             "loaded": loaded, "failed": failed, "missing": missing, "views": {}, "research_signature": research_stamp,
             "projection": generation + "-projection.json.gz"}
    write_asset(folder, value["projection"], payload)
    for disjoint, hierarchy, mappings in product((False, True), repeat=3):
        view = filtered(payload, disjoint, hierarchy, mappings, literature)
        for limit in (160, 400):
            name = generation + "-" + flags(disjoint, hierarchy, mappings) + "-" + str(limit) + ".json.gz"
            write_asset(folder, name, visual_graph.bounded(view, "", limit, loaded, failed, 0))
            value["views"][flags(disjoint, hierarchy, mappings) + "-" + str(limit)] = name
    value["index"] = generation + "-index.json.gz"
    references = {}
    for edge in payload["propertyAttribute"]:
        for node in (edge["domain"], edge["range"]):
            references.setdefault(node, []).append(edge["id"])
    write_asset(folder, value["index"], {"concepts": payload["classAttribute"], "evidence_edges": references})
    if literature:
        withheld = []
        rows = exploration.documents(root, ontology, withheld, use_cache=False)
        rows = [{**row, "root": relative(row["root"])} for row in rows]
        value["documents"] = generation + "-documents.json.gz"
        write_asset(folder, value["documents"], {"rows": rows, "excluded": withheld})
    if any(catalog.fingerprint(Path(path)) != stamp for path, stamp, run, kind in entries):
        raise ValueError("Sources changed during preparation; retry after the run settles.")
    if literature and research_signature(root) != research_stamp:
        raise ValueError("Research records changed during preparation; retry after the run settles.")
    temporary = folder / (generation + ".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(folder / "manifest.json")
    return "built"
