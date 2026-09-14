# -*- coding: utf-8 -*-
"""
kw.gephi - export the merged MDS-Onto knowledge graph to Gephi formats.

Reuses kw.graphview.build_merged_graph (the same graph that powers the explorer:
publications + concepts + MDS classes + raw values + REBEL relations, each node
carrying a canonical study stage) and writes it as:

  * GEXF    - Gephi's native format; keeps per-node colour (by study stage) and
              size (by degree) via the viz extension.
  * GraphML - portable XML fallback that Gephi also imports.

Node attributes (all flattened to scalars so both formats serialise cleanly):
  label, type, stage, stages, category, paper, prop, color,
  degree, relevance, confidence, value
Edge attributes:
  etype, predicate, confidence, weight

CLI:
  python -m kw.gephi                      # all collections -> outputs/gephi_export/
  python -m kw.gephi --out DIR            # choose output dir
  python -m kw.gephi --collections outputs/foo outputs_test/bar
"""
from __future__ import annotations

import argparse
import glob
import os

from kw import graphview as gv
from kw.taxonomy import STAGE_COLORS


# ---------------------------------------------------------------------------
def discover_all_collections(roots=("outputs", "outputs_test")) -> list[str]:
    """Every output folder that holds an all.jsonld, most-recent first."""
    found = []
    for base in roots:
        for p in glob.glob(os.path.join(base, "*", "all.jsonld")):
            found.append((os.path.getmtime(p), os.path.dirname(p)))
    found.sort(reverse=True)
    return [folder for _, folder in found]


def _hex_to_rgb(h: str):
    h = (h or "#888888").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return 136, 136, 136


def _clean_graph(G):
    """Return a copy of G with Gephi-safe scalar node/edge attributes."""
    import networkx as nx
    deg = dict(G.degree())
    H = nx.DiGraph()
    for n, d in G.nodes(data=True):
        metrics = d.get("metrics", {}) or {}
        stage = d.get("stage", "unclassified")
        color = STAGE_COLORS.get(stage, "#888888")
        H.add_node(
            str(n),
            label=str(d.get("label", n)),
            type=str(d.get("ntype", "")),
            stage=str(stage),
            stages=";".join(d.get("stages", []) or []),
            category=str(d.get("category", "")),
            paper=str(d.get("paper", "")),
            prop=str(d.get("prop", "")),
            color=color,
            degree=int(deg.get(n, 0)),
            relevance=float(metrics.get("relevance", 0.0) or 0.0),
            confidence=float(metrics.get("confidence", 0.0) or 0.0),
            value=float(metrics["value"]) if metrics.get("value") is not None else 0.0,
        )
    for u, v, d in G.edges(data=True):
        H.add_edge(
            str(u), str(v),
            etype=str(d.get("etype", "")),
            predicate=str(d.get("label", "")),
            confidence=float(d.get("conf", 0.0) or 0.0),
            weight=float(d.get("weight", d.get("conf", 1.0)) or 1.0),
        )
    return H, deg


def _with_viz(H, deg):
    """Copy of H with a GEXF 'viz' block per node (stage colour + degree size)."""
    import copy
    V = copy.deepcopy(H)
    for n, d in V.nodes(data=True):
        r, g, b = _hex_to_rgb(d.get("color", "#888888"))
        size = 10.0 + 3.0 * (max(1, d.get("degree", 1)) ** 0.6)
        d["viz"] = {"color": {"r": r, "g": g, "b": b, "a": 1.0}, "size": size}
    return V


def export_gephi(folders=None, out_dir="outputs/gephi_export",
                 basename="mds_knowledge_graph", formats=("gexf", "graphml")):
    """Build the merged graph for *folders* (all collections if None) and write
    Gephi files. Returns {fmt: path, 'nodes': n, 'edges': m}."""
    import networkx as nx
    folders = folders or discover_all_collections()
    if not folders:
        raise SystemExit("No collections with all.jsonld found.")
    G = gv.build_from_folders(folders)
    H, deg = _clean_graph(G)
    os.makedirs(out_dir, exist_ok=True)
    written = {"nodes": H.number_of_nodes(), "edges": H.number_of_edges(),
               "collections": len(folders)}
    if "gexf" in formats:
        p = os.path.join(out_dir, f"{basename}.gexf")
        nx.write_gexf(_with_viz(H, deg), p)
        written["gexf"] = p
    if "graphml" in formats:
        p = os.path.join(out_dir, f"{basename}.graphml")
        nx.write_graphml(H, p)
        written["graphml"] = p
    return written


def main():
    ap = argparse.ArgumentParser(description="Export merged graph to Gephi (GEXF/GraphML).")
    ap.add_argument("--out", default="outputs/gephi_export", help="output directory")
    ap.add_argument("--basename", default="mds_knowledge_graph")
    ap.add_argument("--collections", nargs="*", default=None,
                    help="specific collection folders (default: all)")
    ap.add_argument("--format", choices=["gexf", "graphml", "both"], default="both")
    a = ap.parse_args()
    fmts = ("gexf", "graphml") if a.format == "both" else (a.format,)
    res = export_gephi(a.collections, out_dir=a.out, basename=a.basename, formats=fmts)
    print(f"Exported {res['nodes']} nodes / {res['edges']} edges "
          f"from {res['collections']} collection(s):")
    for k in ("gexf", "graphml"):
        if k in res:
            print(f"  {k.upper():8s} -> {res[k]}")


if __name__ == "__main__":
    main()
