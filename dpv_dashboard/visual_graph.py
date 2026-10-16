"""Assemble saved graph layers locally; never fetch imports or rewrite source files.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from functools import lru_cache
from pathlib import Path
from rdflib import Graph
from dpv_dashboard import catalog, research


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
        if not stamp or stamp[1] > 64 * 1024 * 1024:
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


@lru_cache(maxsize=4)
def assemble(entries):
    graph, origins, loaded, failed = Graph(), {}, [], []
    for path, stamp, run, kind in entries:
        try:
            source = Graph().parse(Path(path), format="turtle")
        except Exception:
            failed.append(f"{run}: {Path(path).name} could not be read")
            continue
        origin = {"run": run, "file": Path(path).name, "layer": kind}
        loaded.append(origin)
        for triple in source:
            graph.add(triple)
            origins.setdefault(triple, []).append(origin)
    return graph, origins, loaded, failed
