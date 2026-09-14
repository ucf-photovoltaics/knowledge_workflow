# -*- coding: utf-8 -*-
"""
kw.visualize — interactive knowledge-graph view + benchmark metrics for MDS-Onto JSON-LD.

Runs at the end of the pipeline (see kw.pipeline.run, guarded by config.EMIT_VISUAL) and
is also usable standalone:

    python -m kw.visualize FILE1.jsonld [FILE2 ...] --out graph.html --report report.md
    python -m kw.visualize --glob "outputs/*/all.jsonld" --out combined.html

Graph model
  publication -> concept   (mds:hasConcept, weighted by mds:relevance)   etype=hasConcept
  concept     -> ontoclass (skos:broader, subClassOf-like)               etype=broader
  publication -> domain    (mds:hasDomain)                               etype=inDomain
  publication -> value     (mds:hasX extractions; --with-values)         etype=hasProperty

This module deliberately imports nothing from kw.config (which pulls heavy LLM deps),
so it stays cheap to import. networkx/pyvis are imported lazily inside functions.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import glob
import json
import os
import re
import sys
from collections import Counter

# ---- palette ---------------------------------------------------------------
TYPE_COLOR = {
    "publication": "#1f77b4", "ontoclass": "#d62728", "concept": "#2ca02c",
    "domain": "#9467bd", "value": "#ff7f0e",
}
TYPE_SHAPE = {
    "publication": "dot", "ontoclass": "diamond", "concept": "dot",
    "domain": "square", "value": "triangle",
}
EDGE_COLOR = {
    "hasConcept": "#2ca02c", "broader": "#d62728", "inDomain": "#9467bd",
    "hasProperty": "#ffbb78",
}
GENERIC_CLASS = "Concept"  # the catch-all MDS-Onto upper class we flag as over-used

BENCHMARK_FIELDS = [
    "timestamp", "collection", "domain", "inferred_domain", "publications", "concepts", "ontoclasses",
    "edges", "concept_edges", "pct_generic_concept", "mean_concepts_per_paper",
    "mean_relevance", "bridge_concepts", "components", "orphan_nodes",
    "concepts_without_class", "html", "report",
]


# ---- helpers ---------------------------------------------------------------
def localname(uri):
    if not isinstance(uri, str):
        return str(uri)
    s = uri.rstrip("/")
    for sep in ("#", "/"):
        if sep in s:
            s = s.split(sep)[-1]
    return s or uri


def shorten(text, n=60):
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def get_val(obj, *keys):
    if isinstance(obj, dict):
        for k in keys:
            if k in obj:
                v = obj[k]
                if isinstance(v, dict):
                    return v.get("@value", v.get("@id", json.dumps(v)))
                return v
    return None


def load_files(paths):
    graphs = []
    for p in paths:
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  ! skip {p}: {e}", file=sys.stderr)
            continue
        nodes = data.get("@graph", data if isinstance(data, list) else [data])
        graphs.append((p, nodes))
    return graphs


def build_graph(graphs, with_values=False, min_relevance=0.0):
    import networkx as nx
    G = nx.DiGraph()

    def add(nid, ntype, label=None, title=None, **extra):
        if nid not in G:
            G.add_node(nid, ntype=ntype, label=label or nid, title=title or label or nid, **extra)
        return nid

    for path, nodes in graphs:
        src = os.path.basename(os.path.dirname(path)) or os.path.basename(path)
        for node in nodes:
            if not isinstance(node, dict) or "@id" not in node:
                continue
            pid = node["@id"]
            name = node.get("schema:name") or localname(pid)
            doi = node.get("schema:identifier", "")
            add(pid, "publication", label=shorten(name, 40),
                title=f"<b>{name}</b><br>DOI: {doi}<br>source: {src}", source=src)

            dom = node.get("mds:hasDomain")
            if dom:
                did = f"domain::{dom}"
                add(did, "domain", label=str(dom))
                G.add_edge(pid, did, etype="inDomain")

            concepts = node.get("mds:hasConcept") or []
            if isinstance(concepts, dict):
                concepts = [concepts]
            for c in concepts:
                if not isinstance(c, dict):
                    continue
                term = c.get("mds:canonicalTerm")
                if not term:
                    continue
                rel = get_val(c.get("mds:relevance", {}), "@value")
                try:
                    rel = float(rel)
                except (TypeError, ValueError):
                    rel = 0.5
                if rel < min_relevance:
                    continue
                cid = f"concept::{str(term).lower().strip()}"
                add(cid, "concept", label=shorten(term, 30),
                    title=f"<b>{term}</b><br>paper term: {c.get('mds:paperTerm','')}")
                G.add_edge(pid, cid, etype="hasConcept", weight=rel,
                           title=f"relevance {rel:.2f}")
                broader = c.get("skos:broader")
                bid = get_val(broader, "@id") if isinstance(broader, dict) else broader
                if bid:
                    oc = f"onto::{localname(bid)}"
                    add(oc, "ontoclass", label=localname(bid),
                        title=f"MDS-Onto class<br>{bid}")
                    G.add_edge(cid, oc, etype="broader")

            if with_values:
                for k, v in node.items():
                    if k.startswith("@") or k.startswith("schema:") or k in (
                        "mds:hasConcept", "mds:hasDomain", "mds:derivedFrom", "owl:sameAs"):
                        continue
                    val = get_val(v, "mds:value") if isinstance(v, dict) else (
                        v if isinstance(v, str) else None)
                    if not val:
                        continue
                    prop = localname(k)
                    vid = f"value::{prop}::{str(val).lower().strip()[:60]}"
                    add(vid, "value", label=shorten(val, 28),
                        title=f"<b>{prop}</b><br>{val}")
                    G.add_edge(pid, vid, etype="hasProperty", title=prop, label=prop)
    return G


# ---- rendering -------------------------------------------------------------
LEGEND = """
<div id="mds-legend" style="position:fixed;top:12px;left:12px;z-index:999;background:rgba(255,255,255,.95);
border:1px solid #ccc;border-radius:8px;padding:10px 14px;font:13px/1.5 system-ui,sans-serif;
box-shadow:0 2px 8px rgba(0,0,0,.12); resize:both; overflow:auto; cursor:grab; min-width:200px; max-width:400px;">
<div id="mds-legend-header" style="font-weight:bold; margin-bottom:5px; padding-bottom:5px; border-bottom:1px solid #eee;">
    &#10021; MDS-Onto Knowledge Graph
</div>
<span style="color:#1f77b4">&#9679;</span> Publication &nbsp;
<span style="color:#d62728">&#9670;</span> MDS-Onto class<br>
<span style="color:#2ca02c">&#9679;</span> Canonical concept &nbsp;
<span style="color:#9467bd">&#9632;</span> Domain<br>
<span style="color:#ff7f0e">&#9650;</span> Extracted value<br>
<small style="display:block; margin-top:8px; color:#666;">node size = connectivity &middot; drag to explore &middot; scroll to zoom</small>
</div>

<script>
// Simple drag script for the legend
const legend = document.getElementById('mds-legend');
const header = document.getElementById('mds-legend-header');
let isDragging = false, startX, startY, currentX = 0, currentY = 0;

header.addEventListener('mousedown', (e) => {
    isDragging = true;
    legend.style.cursor = 'grabbing';
    startX = e.clientX - currentX;
    startY = e.clientY - currentY;
});

document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    e.preventDefault();
    currentX = e.clientX - startX;
    currentY = e.clientY - startY;
    legend.style.transform = `translate(${currentX}px, ${currentY}px)`;
});

document.addEventListener('mouseup', () => {
    isDragging = false;
    legend.style.cursor = 'grab';
});
</script>
"""


SLIDER = """
<div id="mds-slider" style="position:fixed;bottom:14px;left:12px;z-index:999;
background:rgba(255,255,255,.96);border:1px solid #ccc;border-radius:8px;padding:10px 14px;
font:13px/1.4 system-ui,sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.12)">
  <label for="relSlider"><b>Min concept relevance:</b> <span id="relVal">0.00</span></label><br>
  <input id="relSlider" type="range" min="0" max="1" step="0.05" value="0" style="width:260px">
  <div id="relCount" style="color:#666;margin-top:4px"></div>
</div>
<script>
(function () {
  function ready() {
    if (typeof network === 'undefined' || !network || !network.body) {
      return setTimeout(ready, 150);
    }
    var nodesDS = network.body.data.nodes, edgesDS = network.body.data.edges;
    var allNodes = nodesDS.get(), allEdges = edgesDS.get();
    var slider = document.getElementById('relSlider');
    var relVal = document.getElementById('relVal');
    var relCount = document.getElementById('relCount');
    function isConcept(n) { return n.id && String(n.id).indexOf('concept::') === 0; }
    var total = allNodes.filter(isConcept).length;
    function apply() {
      var th = parseFloat(slider.value);
      relVal.textContent = th.toFixed(2);
      var hidden = {};
      nodesDS.update(allNodes.map(function (n) {
        var rel = (typeof n.rel === 'number') ? n.rel : 1.0;
        var hide = isConcept(n) && rel < th;
        hidden[n.id] = hide;
        return { id: n.id, hidden: hide };
      }));
      edgesDS.update(allEdges.map(function (e) {
        return { id: e.id, hidden: !!(hidden[e.from] || hidden[e.to]) };
      }));
      var shown = allNodes.filter(function (n) { return isConcept(n) && !hidden[n.id]; }).length;
      relCount.textContent = shown + ' / ' + total + ' concepts shown';
    }
    slider.addEventListener('input', apply);
    apply();
  }
  ready();
})();
</script>
"""


def render_html(G, out):
    from pyvis.network import Network
    net = Network(height="820px", width="100%", directed=True, bgcolor="#ffffff",
                  font_color="#222222", notebook=False, cdn_resources="in_line")
    deg = dict(G.degree())
    # Max incoming hasConcept relevance per concept node -> drives the slider.
    concept_rel = {}
    for _u, _v, _d in G.edges(data=True):
        if _d.get("etype") == "hasConcept":
            concept_rel[_v] = max(concept_rel.get(_v, 0.0), float(_d.get("weight", 0) or 0))
    for n, d in G.nodes(data=True):
        t = d["ntype"]
        size = 12 + 3.2 * (deg.get(n, 1) ** 0.6)
        if t == "ontoclass":
            size = max(size, 22)
        rel = round(concept_rel.get(n, 1.0), 3) if t == "concept" else 1.0
        net.add_node(n, label=d["label"], title=d["title"],
                     color=TYPE_COLOR.get(t, "#888"), shape=TYPE_SHAPE.get(t, "dot"),
                     size=size, rel=rel)
    for u, v, d in G.edges(data=True):
        et = d.get("etype", "")
        net.add_edge(u, v, color=EDGE_COLOR.get(et, "#cccccc"),
                     title=d.get("title", et), label=d.get("label", ""),
                     width=1 + 2 * float(d.get("weight", 0)) if et == "hasConcept" else 1,
                     arrows="to")
    net.set_options("""
    var options = {
      "interaction": {"hover": true, "tooltipDelay": 80, "navigationButtons": true, "keyboard": true},
      "physics": {"barnesHut": {"gravitationalConstant": -18000, "springLength": 130,
                  "springConstant": 0.02, "damping": 0.4, "avoidOverlap": 0.6},
                  "minVelocity": 0.6, "stabilization": {"iterations": 350}},
      "edges": {"smooth": {"type": "dynamic"}, "font": {"size": 9, "align": "middle"}},
      "nodes": {"font": {"size": 13}}
    }
    """)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    # pyvis's write_html opens the file without an explicit encoding (cp1252 on
    # Windows), which crashes on unicode node labels. Generate the HTML string
    # and write it as UTF-8 ourselves.
    html = net.generate_html(notebook=False)
    html = html.replace("<body>", "<body>" + LEGEND, 1)
    html = html.replace("</body>", SLIDER + "</body>", 1)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out


# ---- metrics + report ------------------------------------------------------
def metrics(G, collection="", html="", report="", inferred_domain=""):
    """Return a flat benchmark row (dict) summarising graph structure + ontology coverage."""
    import networkx as nx
    UG = G.to_undirected()
    ntypes = Counter(d["ntype"] for _, d in G.nodes(data=True))

    broader_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("etype") == "broader"]
    generic = sum(1 for _, v in broader_edges if G.nodes[v]["label"] == GENERIC_CLASS)
    pct_generic = round(100 * generic / len(broader_edges), 1) if broader_edges else 0.0

    concept_edges = [(u, v, d) for u, v, d in G.edges(data=True) if d.get("etype") == "hasConcept"]
    pubs = ntypes.get("publication", 0)
    mean_cpp = round(len(concept_edges) / pubs, 2) if pubs else 0.0
    rels = [float(d.get("weight", 0)) for _, _, d in concept_edges]
    mean_rel = round(sum(rels) / len(rels), 3) if rels else 0.0

    bridges = sum(1 for n, d in G.nodes(data=True)
                  if d["ntype"] == "concept" and G.in_degree(n) > 1)
    no_class = sum(1 for n, d in G.nodes(data=True)
                   if d["ntype"] == "concept" and G.out_degree(n) == 0)
    orphans = sum(1 for n in G.nodes if UG.degree(n) <= 1)
    comps = nx.number_connected_components(UG) if G.number_of_nodes() else 0
    domains = sorted({d["label"] for _, d in G.nodes(data=True) if d["ntype"] == "domain"})

    return {
        "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        "collection": collection,
        "domain": "; ".join(domains),
        "inferred_domain": inferred_domain,
        "publications": pubs,
        "concepts": ntypes.get("concept", 0),
        "ontoclasses": ntypes.get("ontoclass", 0),
        "edges": G.number_of_edges(),
        "concept_edges": len(concept_edges),
        "pct_generic_concept": pct_generic,
        "mean_concepts_per_paper": mean_cpp,
        "mean_relevance": mean_rel,
        "bridge_concepts": bridges,
        "components": comps,
        "orphan_nodes": orphans,
        "concepts_without_class": no_class,
        "html": html,
        "report": report,
    }


def analyze(G, collection=""):
    import networkx as nx
    m = metrics(G, collection)
    L = ["# MDS-Onto Knowledge Graph — Centrality & Gap Analysis\n"]
    if collection:
        L.append(f"_Collection: **{collection}**  ({m['timestamp']})_\n")
    L.append(f"**Nodes:** {G.number_of_nodes()}  |  **Edges:** {G.number_of_edges()}\n")
    types = Counter(d["ntype"] for _, d in G.nodes(data=True))
    L.append("Node types: " + ", ".join(f"{k}={v}" for k, v in types.items()) + "\n")

    UG = G.to_undirected()
    deg = dict(G.degree())
    btw = nx.betweenness_centrality(UG) if G.number_of_nodes() > 2 else {}
    L.append("\n## Most central nodes (by degree)\n")
    for n, d in sorted(deg.items(), key=lambda x: -x[1])[:15]:
        nd = G.nodes[n]
        L.append(f"- **{nd['label']}** ({nd['ntype']}) — degree {d}, betweenness {btw.get(n,0):.3f}")

    L.append("\n## MDS-Onto upper classes by concept coverage\n")
    oc = [(n, G.in_degree(n)) for n, d in G.nodes(data=True) if d["ntype"] == "ontoclass"]
    for n, c in sorted(oc, key=lambda x: -x[1]):
        flag = "  ⟵ over-used catch-all" if G.nodes[n]["label"] == GENERIC_CLASS else ""
        L.append(f"- **{G.nodes[n]['label']}** — {c} concept(s) mapped{flag}")

    L.append("\n## Bridge concepts (shared by multiple publications)\n")
    shared = [(n, G.in_degree(n)) for n, d in G.nodes(data=True)
              if d["ntype"] == "concept" and G.in_degree(n) > 1]
    if shared:
        for n, c in sorted(shared, key=lambda x: -x[1]):
            L.append(f"- **{G.nodes[n]['label']}** — links {c} publications")
    else:
        L.append("- _None_: every canonical concept appears in only one publication.")

    comps = list(nx.connected_components(UG))
    L.append(f"\n## Connected components (clusters): {len(comps)}\n")
    for i, comp in enumerate(sorted(comps, key=len, reverse=True), 1):
        pubs = [G.nodes[x]["label"] for x in comp if G.nodes[x]["ntype"] == "publication"]
        L.append(f"- Cluster {i}: {len(comp)} nodes, {len(pubs)} publication(s)"
                 + (f" — {', '.join(pubs[:4])}" if pubs else ""))

    L.append("\n## Gap analysis\n")
    L.append(f"- **Generic-class overload:** {m['pct_generic_concept']}% of concept mappings "
             f"land on the catch-all `{GENERIC_CLASS}` class — lower is better.")
    L.append(f"- **Orphan/leaf nodes (degree <= 1):** {m['orphan_nodes']} — mentioned once; "
             "candidates for consolidation or enrichment.")
    L.append(f"- **Concepts with no skos:broader mapping:** {m['concepts_without_class']} — "
             "extracted terms not yet anchored to an MDS-Onto class.")
    L.append(f"- **Disconnected clusters:** {m['components']} "
             "(more than 1 = some papers share no concepts with the rest).")
    return "\n".join(L) + "\n"


def append_benchmark(row, csv_path):
    """Append one row. If the existing file's header doesn't match BENCHMARK_FIELDS
    (e.g. new columns were added), the file is migrated in place: old rows are
    preserved and missing columns filled blank."""
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
    existing, header_ok = [], False
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        if rows:
            header_ok = rows[0] == BENCHMARK_FIELDS
            if not header_ok:
                existing = [dict(zip(rows[0], rec)) for rec in rows[1:]]
    if header_ok:
        with open(csv_path, "a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=BENCHMARK_FIELDS).writerow(
                {k: row.get(k, "") for k in BENCHMARK_FIELDS})
    else:
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=BENCHMARK_FIELDS)
            w.writeheader()
            for old in existing:
                w.writerow({k: old.get(k, "") for k in BENCHMARK_FIELDS})
            w.writerow({k: row.get(k, "") for k in BENCHMARK_FIELDS})
    return csv_path


# ---- pipeline entry point --------------------------------------------------
def run_for_pipeline(jsonld_path, out_dir, collection="", with_values=False,
                     benchmark_csv=None, min_relevance=0.0, inferred_domain=""):
    """Build graph + HTML + report for one all.jsonld, append a benchmark row. Returns dict."""
    if not jsonld_path or not os.path.exists(jsonld_path):
        print(f"[visual] no JSON-LD at {jsonld_path}; skipping graph.")
        return None
    html = os.path.join(out_dir, "graph.html")
    report = os.path.join(out_dir, "graph_report.md")
    G = build_graph(load_files([jsonld_path]), with_values=with_values, min_relevance=min_relevance)
    render_html(G, html)
    open(report, "w", encoding="utf-8").write(analyze(G, collection))
    row = metrics(G, collection=collection, html=html, report=report,
                  inferred_domain=inferred_domain)
    bench = None
    if benchmark_csv:
        bench = append_benchmark(row, benchmark_csv)
    print(f"[visual] graph -> {html}  ({row['publications']} papers, "
          f"{row['concepts']} concepts, {row['pct_generic_concept']}% generic-class)")
    if bench:
        print(f"[visual] benchmark row appended -> {bench}")
    return {"html": html, "report": report, "benchmark": bench, "metrics": row}


# ---- CLI -------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(prog="kw.visualize")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--glob")
    ap.add_argument("--out", default="graph.html")
    ap.add_argu