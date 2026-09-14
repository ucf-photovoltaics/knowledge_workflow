# -*- coding: utf-8 -*-
"""
kw.graphview — merged, provenance-rich knowledge graph + interactive viewer.

Where kw.visualize renders the *publication -> concept -> class* skeleton from a
single all.jsonld, this module MERGES that skeleton with the standalone REBEL
relations (rebel_triples.jsonld / triples_*.csv) and any extracted raw values,
so every fact lives in one graph and every node/edge carries the provenance
needed to trace it back to its source paper.

Public entry points:
  build_merged_graph(jsonld_paths, rebel_paths=..., csv_paths=...) -> networkx.DiGraph
  build_from_folders(folders, ...)                                 -> networkx.DiGraph
  render_app_html(G, height='820px') -> str
      A self-contained single-page app: a full-bleed vis-network graph with
      floating, draggable, resizable panels (Details + Data/Plot), live search,
      node-type toggles, a confidence slider, and a Plotly panel that plots the
      numeric values of the user's selected nodes on a configurable X-Y chart.

networkx is imported lazily so importing this module stays cheap.
"""
from __future__ import annotations

import glob
import html as _html
import json
import os
import re

from kw.visualize import (
    localname, shorten, get_val, TYPE_COLOR, TYPE_SHAPE, EDGE_COLOR,
)
from kw.taxonomy import (
    STUDY_STAGES, STAGE_ORDER, STAGE_COLORS, normalize_stage, normalize_stages,
)

TYPE_COLOR = {**TYPE_COLOR, "entity": "#17becf"}
TYPE_SHAPE = {**TYPE_SHAPE, "entity": "hexagon"}
EDGE_COLOR = {**EDGE_COLOR, "relation": "#7f7f7f", "mentions": "#bbbbbb"}

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

# Keyword classifier that buckets a node into a coarse MDS category so the viewer
# can lay categories out in fixed screen regions. measurement is checked first so
# e.g. "contact resistance" -> measurement (not material via "contact").
_CAT_KEYWORDS = (
    ("measurement", (
        "efficiency", "voltage", "current", "resistance", "resistivity",
        "conductivity", "fill factor", "power", "loss", "absorption", "measure",
        "measurement", "metric", "temperature", "bandgap", "band gap", "wavelength",
        "reflectance", "transmittance", "lifetime", "mobility", "density", "ratio",
        "yield", "performance", "rate", "doping concentration")),
    ("process", (
        "process", "deposition", "printing", "sintering", "curing", "plating",
        "annealing", "etching", "method", "fabrication", "growth", "synthesis",
        "treatment", "lamination", "texturing", "patterning", "sputter",
        "evaporation", "cvd", "ald", "laser", "spin coat", "calcination")),
    ("material", (
        "material", "layer", "oxide", "metallization", "absorber", "contact",
        "coating", "composition", "perovskite", "silicon", "substrate", "electrode",
        "semiconductor", "passivation", "buffer", "emitter", "dopant", "alloy",
        "film", "compound", "ink", "paste", "nanoparticle", "tco", "wafer")),
)


def _categorize(*parts) -> str:
    text = " ".join(str(p) for p in parts if p).lower()
    for cat, kws in _CAT_KEYWORDS:
        if any(k in text for k in kws):
            return cat
    return "other"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _esc(text) -> str:
    return _html.escape(str(text if text is not None else ""))


def _num(text):
    """Best-effort numeric parse: first number in a string, else None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = _NUM_RE.search(str(text))
    return float(m.group()) if m else None


def _discover(folder: str) -> dict:
    jsonld = sorted(glob.glob(os.path.join(folder, "all.jsonld")))
    if not jsonld:
        jsonld = [p for p in sorted(glob.glob(os.path.join(folder, "*.jsonld")))
                  if not p.endswith("rebel_triples.jsonld")]
    return {
        "jsonld": jsonld,
        "rebel": sorted(glob.glob(os.path.join(folder, "rebel_triples.jsonld"))),
        "csv":   sorted(glob.glob(os.path.join(folder, "triples_*.csv"))),
        "enriched": sorted(glob.glob(os.path.join(folder, "enriched_*.csv"))),
    }


# ---------------------------------------------------------------------------
# study-stage assignment
# ---------------------------------------------------------------------------
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _camel_to_words(text) -> str:
    """`FabricationChallenges` -> `fabrication challenges` (for enriched lookup)."""
    s = _CAMEL_RE.sub(" ", str(text or ""))
    return _norm(s.replace("_", " "))


# Keyword -> study-stage fallback used only when a node carries no explicit tag.
# Earliest match (in canonical order, most specific first) wins.
_STAGE_KEYWORDS = (
    ("data processing", ("data processing", "normalization", "calibration",
                         "segmentation", "filtering", "fitting", "preprocessing")),
    ("characterization tool", ("microscop", "spectroscop", "tem", "sem", "xrd",
                               "afm", "instrument", "detector", "imaging", "metrology")),
    ("materials processing", ("deposition", "anneal", "etch", "sputter", "cvd",
                              "ald", "sinter", "fabricat", "lamination", "texturing",
                              "passivation", "coating", "processing", "growth")),
    ("synthesis", ("synthesis", "epitax", "crystal grow")),
    ("formulation", ("formulation", "precursor", "ink", "paste", "solution", "slurry")),
    ("sample", ("sample", "wafer", "substrate", "film", "device", "specimen",
                "layer", "absorber", "cell", "electrode", "junction")),
    ("modeling", ("model", "simulation", "dft", "calculation", "theoret", "predict")),
    ("inference", ("inference", "mechanism", "conclusion", "causal")),
    ("insights", ("insight", "finding", "implication", "trend")),
    ("reports", ("report", "review", "publication", "metadata", "documentation")),
    ("analysis", ("analysis", "correlation", "statistic", "evaluation",
                  "characterization", "comparison")),
    ("results", ("result", "efficiency", "voltage", "current", "performance",
                 "yield", "fill factor", "resistance", "mobility", "lifetime",
                 "bandgap", "band gap", "output", "measurement")),
    ("data", ("data", "dataset", "signal", "spectrum", "image")),
)


def _stage_from_keywords(*parts) -> str:
    text = " ".join(str(p) for p in parts if p).lower()
    for stage, kws in _STAGE_KEYWORDS:
        if any(k in text for k in kws):
            return stage
    return "unclassified"


def _earliest_stage(stages) -> str:
    """Pick the earliest canonical stage in a list (drives layout position)."""
    cands = [s for s in (stages or []) if s in STAGE_ORDER]
    return min(cands, key=lambda s: STAGE_ORDER[s]) if cands else "unclassified"


def _load_stage_map(enriched_paths) -> dict:
    """{lower concept name -> [canonical stages]} from enriched_*.csv files."""
    import csv as _csv
    out = {}
    for p in enriched_paths or []:
        try:
            with open(p, newline="", encoding="utf-8") as fh:
                for row in _csv.DictReader(fh):
                    key = _norm(row.get("concept", ""))
                    if key:
                        out[key] = normalize_stages(row.get("mds:studyStage", ""))
        except Exception:
            continue
    return out


# ---------------------------------------------------------------------------
# graph construction
# ---------------------------------------------------------------------------
def build_merged_graph(jsonld_paths, rebel_paths=None, csv_paths=None,
                       enriched_paths=None, with_values=True, min_relevance=0.0):
    """Merge the JSON-LD skeleton + REBEL relations + raw values into one DiGraph.

    Node attrs: ntype, label, title (hover), detail (panel HTML), metrics (dict of
    numeric fields for plotting), stage (canonical study stage), stages (full
    list). Edge attrs: etype, label, title, detail, conf.
    """
    import networkx as nx
    G = nx.DiGraph()

    concept_by_norm: dict[str, str] = {}
    pub_by_title: dict[str, str] = {}
    stage_map = _load_stage_map(enriched_paths)

    def add(nid, ntype, label=None, title=None, detail=None, metrics=None, **extra):
        if nid not in G:
            G.add_node(nid, ntype=ntype, label=label or nid,
                       title=title or label or nid,
                       detail=detail or f"<b>{_esc(label or nid)}</b>",
                       metrics=metrics or {}, stage="unclassified", stages=[], **extra)
        return nid

    def set_stage(nid, stages):
        """Attach study stages to a node (keeps the union, earliest drives layout)."""
        stages = [s for s in (stages or []) if s in STAGE_ORDER]
        if not stages:
            return
        cur = set(G.nodes[nid].get("stages") or [])
        cur.update(stages)
        ordered = sorted(cur, key=lambda s: STAGE_ORDER[s])
        G.nodes[nid]["stages"] = ordered
        G.nodes[nid]["stage"] = ordered[0]

    for path in jsonld_paths or []:
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"  ! skip {path}: {exc}")
            continue
        nodes = data.get("@graph", data if isinstance(data, list) else [data])
        src = os.path.basename(os.path.dirname(path)) or os.path.basename(path)

        for node in nodes:
            if not isinstance(node, dict) or "@id" not in node:
                continue
            pid = node["@id"]
            name = node.get("schema:name") or localname(pid)
            doi = node.get("schema:identifier", "")
            dom = node.get("mds:hasDomain", "")
            detail = (
                f"<b>{_esc(name)}</b>"
                f"<div class='kv'><span>Type</span>Publication</div>"
                f"<div class='kv'><span>DOI</span>{_esc(doi) or '—'}</div>"
                f"<div class='kv'><span>Domain</span>{_esc(dom) or '—'}</div>"
                f"<div class='kv'><span>Source</span>{_esc(src)}</div>"
            )
            add(pid, "publication", label=shorten(name, 40),
                title=f"<b>{_esc(name)}</b><br>DOI: {_esc(doi)}", detail=detail,
                source=src, paper=name)
            pub_by_title[_norm(name)] = pid

            if dom:
                did = f"domain::{dom}"
                add(did, "domain", label=str(dom),
                    detail=f"<b>{_esc(dom)}</b><div class='kv'><span>Type</span>Domain</div>")
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
                rel = _num(get_val(c.get("mds:relevance", {}), "@value"))
                rel = 0.5 if rel is None else rel
                if rel < min_relevance:
                    continue
                cid = f"concept::{_norm(term)}"
                paper_term = c.get("mds:paperTerm", "")
                broader = c.get("skos:broader")
                bid = get_val(broader, "@id") if isinstance(broader, dict) else broader
                cdetail = (
                    f"<b>{_esc(term)}</b>"
                    f"<div class='kv'><span>Type</span>Canonical concept</div>"
                    f"<div class='kv'><span>Paper term</span>{_esc(paper_term) or '—'}</div>"
                    f"<div class='kv'><span>Relevance</span>{rel:.2f}</div>"
                    f"<div class='kv'><span>MDS class</span>{_esc(localname(bid)) if bid else '—'}</div>"
                )
                add(cid, "concept", label=shorten(term, 30), detail=cdetail,
                    title=f"<b>{_esc(term)}</b>", paper=name)
                # keep the max relevance seen for this concept
                m = G.nodes[cid]["metrics"]
                m["relevance"] = max(m.get("relevance", 0.0), rel)
                concept_by_norm[_norm(term)] = cid
                # study stage: explicit tag from the concept, then enriched map,
                # then a keyword guess from the term + its MDS class.
                c_stages = normalize_stages(
                    ",".join(c.get("mds:studyStage"))
                    if isinstance(c.get("mds:studyStage"), list)
                    else c.get("mds:studyStage", "")
                )
                c_stages = c_stages or stage_map.get(_norm(term), [])
                if not c_stages:
                    kw = _stage_from_keywords(term, localname(bid) if bid else "")
                    c_stages = [kw] if kw != "unclassified" else []
                set_stage(cid, c_stages)
                G.add_edge(pid, cid, etype="hasConcept", weight=rel,
                           title=f"relevance {rel:.2f}", detail=f"relevance {rel:.2f}")
                if bid:
                    oc = f"onto::{localname(bid)}"
                    G.nodes[cid]["cat_hint"] = localname(bid)
                    add(oc, "ontoclass", label=localname(bid),
                        detail=f"<b>{_esc(localname(bid))}</b>"
                               f"<div class='kv'><span>Type</span>MDS-Onto class</div>"
                               f"<div class='kv'><span>IRI</span>{_esc(bid)}</div>")
                    G.add_edge(cid, oc, etype="broader", detail="subClassOf")

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
                    vid = f"value::{prop}::{_norm(val)[:60]}"
                    vnum = _num(val)
                    metrics = {"value": vnum} if vnum is not None else {}
                    # explicit stage from the property entry, else enriched map
                    # (joined on the de-camel-cased property name), else keyword.
                    v_stages = []
                    if isinstance(v, dict):
                        v_stages = normalize_stages(
                            ",".join(v.get("mds:studyStage"))
                            if isinstance(v.get("mds:studyStage"), list)
                            else v.get("mds:studyStage", ""))
                    v_stages = v_stages or stage_map.get(_camel_to_words(prop), [])
                    if not v_stages:
                        kw = _stage_from_keywords(prop, val)
                        v_stages = [kw] if kw != "unclassified" else []
                    add(vid, "value", label=shorten(val, 28), metrics=metrics,
                        detail=f"<b>{_esc(val)}</b>"
                               f"<div class='kv'><span>Type</span>Raw value</div>"
                               f"<div class='kv'><span>Property</span>{_esc(prop)}</div>"
                               f"<div class='kv'><span>Numeric</span>{vnum if vnum is not None else '—'}</div>"
                               f"<div class='kv'><span>From</span>{_esc(name)}</div>",
                        prop=prop, paper=name)
                    set_stage(vid, v_stages)
                    G.add_edge(pid, vid, etype="hasProperty", label=prop, detail=_esc(prop))

    # ---- REBEL relations ------------------------------------------------------
    for r in _read_rebel(rebel_paths, csv_paths):
        subj, obj = r["subject"], r["object"]
        pred = r["predicate"] or "related to"
        pred_norm = r.get("predicate_norm", "")
        conf = r.get("confidence", 0.0)
        paper = r.get("source_paper", "")

        s_id = _endpoint_node(G, add, subj, r.get("subject_id"), concept_by_norm)
        o_id = _endpoint_node(G, add, obj, r.get("object_id"), concept_by_norm)
        if not s_id or not o_id or s_id == o_id:
            continue
        for nid in (s_id, o_id):
            mm = G.nodes[nid]["metrics"]
            mm["confidence"] = max(mm.get("confidence", 0.0), float(conf))

        paper_html = _esc(paper) or "—"
        pid = pub_by_title.get(_norm(paper))
        if pid:
            paper_html = f"<a href='#' data-focus='{_esc(pid)}'>{_esc(paper)}</a>"
        edetail = (
            f"<b>{_esc(subj)} → {_esc(obj)}</b>"
            f"<div class='kv'><span>Type</span>REBEL relation</div>"
            f"<div class='kv'><span>Predicate</span>{_esc(pred)}"
            f"{(' (' + _esc(pred_norm) + ')') if pred_norm else ''}</div>"
            f"<div class='kv'><span>Confidence</span>{conf:.2f}</div>"
            f"<div class='kv'><span>Source</span>{paper_html}</div>"
        )
        if G.has_edge(s_id, o_id) and G[s_id][o_id].get("etype") == "relation":
            if conf <= G[s_id][o_id].get("conf", 0):
                continue
        G.add_edge(s_id, o_id, etype="relation", label=pred, conf=float(conf),
                   title=f"{_esc(pred)} (conf {conf:.2f})", detail=edetail,
                   weight=float(conf))
    return G


def _endpoint_node(G, add, text, concept_id, concept_by_norm):
    if not text or not str(text).strip():
        return None
    n = _norm(text)
    if n in concept_by_norm:
        return concept_by_norm[n]
    if concept_id:
        alt = _norm(localname(concept_id).replace("_", " "))
        if alt in concept_by_norm:
            return concept_by_norm[alt]
    eid = f"entity::{n}"
    add(eid, "entity", label=shorten(text, 30),
        detail=f"<b>{_esc(text)}</b>"
               f"<div class='kv'><span>Type</span>Extracted entity (REBEL)</div>")
    kw = _stage_from_keywords(text)
    if kw != "unclassified":
        G.nodes[eid]["stage"] = kw
        G.nodes[eid]["stages"] = [kw]
    return eid


def _read_rebel(rebel_paths, csv_paths):
    out, seen = [], False
    for p in rebel_paths or []:
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for n in data.get("@graph", []):
            if not isinstance(n, dict):
                continue
            out.append({
                "subject": n.get("mds:subject", ""),
                "object": n.get("mds:object", ""),
                "predicate": n.get("mds:predicate", ""),
                "predicate_norm": get_val(n.get("mds:relation", {}), "@id") or "",
                "confidence": _num(get_val(n.get("mds:confidence", {}), "@value")) or 0.0,
                "source_paper": n.get("prov:wasDerivedFrom", ""),
                "subject_id": get_val(n.get("mds:subjectConcept", {}), "@id"),
                "object_id": get_val(n.get("mds:objectConcept", {}), "@id"),
            })
            seen = True
    if seen:
        return out
    import csv as _csv
    for p in csv_paths or []:
        try:
            with open(p, newline="", encoding="utf-8") as fh:
                for row in _csv.DictReader(fh):
                    out.append({
                        "subject": row.get("subject", ""),
                        "object": row.get("object", ""),
                        "predicate": row.get("predicate", ""),
                        "predicate_norm": row.get("predicate_norm", ""),
                        "confidence": _num(row.get("confidence")) or 0.0,
                        "source_paper": row.get("source_paper", ""),
                        "subject_id": row.get("subject_id", ""),
                        "object_id": row.get("object_id", ""),
                    })
        except Exception:
            continue
    return out


def build_from_folders(folders, **kwargs):
    jsonld, rebel, csvs, enriched = [], [], [], []
    for f in folders:
        d = _discover(f)
        jsonld += d["jsonld"]
        rebel += d["rebel"]
        csvs += d["csv"]
        enriched += d.get("enriched", [])
    return build_merged_graph(jsonld, rebel_paths=rebel, csv_paths=csvs,
                              enriched_paths=enriched, **kwargs)


# ---------------------------------------------------------------------------
# interactive app renderer
# ---------------------------------------------------------------------------
def _category_of(d):
    t = d["ntype"]
    if t in ("publication", "domain"):
        return "other"
    return _categorize(d.get("label", ""), d.get("cat_hint", ""), d.get("prop", ""))


def _to_visdata(G):
    deg = dict(G.degree())
    nodes, edges = [], []
    for n, d in G.nodes(data=True):
        t = d["ntype"]
        size = 10 + 3.0 * (deg.get(n, 1) ** 0.6)
        if t == "ontoclass":
            size = max(size, 20)
        metrics = dict(d.get("metrics", {}))
        metrics["degree"] = deg.get(n, 0)
        nodes.append({
            "id": n, "label": d["label"], "title": d.get("title", d["label"]),
            "group": t, "value": size, "shape": TYPE_SHAPE.get(t, "dot"),
            "color": TYPE_COLOR.get(t, "#888"), "detail": d.get("detail", ""),
            "metrics": metrics, "paper": d.get("paper", ""), "prop": d.get("prop", ""),
            "category": _category_of(d),
            "stage": d.get("stage", "unclassified"),
            "stages": d.get("stages", []),
            "raw": d.get("label", "") if t == "value" else "",
            "valnum": metrics.get("value"),
        })
    for i, (u, v, d) in enumerate(G.edges(data=True)):
        et = d.get("etype", "")
        edges.append({
            "id": f"e{i}", "from": u, "to": v, "label": d.get("label", ""),
            "title": d.get("title", et), "etype": et,
            "conf": float(d.get("conf", 1.0)),
            "color": EDGE_COLOR.get(et, "#cccccc"),
            "dashes": et == "relation", "detail": d.get("detail", ""), "arrows": "to",
        })
    return nodes, edges


def render_app_html(G, height="820px"):
    """Self-contained single-page explorer app for embedding in an <iframe srcdoc>."""
    nodes, edges = _to_visdata(G)
    present_types = sorted({d["ntype"] for _, d in G.nodes(data=True)})
    type_labels = {
        "publication": "Publication", "concept": "Concept", "ontoclass": "MDS class",
        "domain": "Domain", "value": "Raw value", "entity": "Entity (REBEL)",
    }
    checks = "".join(
        f"<label class='chk'><input type='checkbox' checked data-type='{t}'>"
        f"<span class='swatch' style='background:{TYPE_COLOR.get(t, '#888')}'></span>"
        f"{type_labels.get(t, t)}</label>"
        for t in present_types
    )
    has_relations = any(e["etype"] == "relation" for e in edges)
    # Only the stages actually present, in canonical left-to-right / cycle order.
    present_stages = [s for s in STUDY_STAGES
                      if any(n["stage"] == s for n in nodes)]
    if any(n["stage"] == "unclassified" for n in nodes):
        present_stages.append("unclassified")
    return _TEMPLATE \
        .replace("__HEIGHT__", height) \
        .replace("__CHECKS__", checks) \
        .replace("__SLIDER_DISPLAY__", "inline-flex" if has_relations else "none") \
        .replace("__STAGES__", json.dumps(present_stages, ensure_ascii=False)) \
        .replace("__STAGECOLORS__", json.dumps(STAGE_COLORS, ensure_ascii=False)) \
        .replace("__NODES__", json.dumps(nodes, ensure_ascii=False)) \
        .replace("__EDGES__", json.dumps(edges, ensure_ascii=False))


# Backwards-compatible alias.
render_interactive_html = render_app_html


_TEMPLATE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.6/dist/vis-network.min.js"></script>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  html,body{margin:0;padding:0;height:100%;font:13px/1.45 system-ui,sans-serif;color:#222;overflow:hidden}
  #stage{position:relative;width:100%;height:__HEIGHT__;background:#fff}
  #net{position:absolute;inset:0}
  .float{position:absolute;background:rgba(255,255,255,.97);border:1px solid #d6d6d6;
    border-radius:10px;box-shadow:0 4px 18px rgba(0,0,0,.16);display:flex;flex-direction:column;
    overflow:hidden;min-width:220px;min-height:90px}
  .float>header{cursor:move;user-select:none;padding:7px 10px;background:#f3f4f6;border-bottom:1px solid #e3e3e3;
    font-weight:600;display:flex;align-items:center;justify-content:space-between;gap:8px}
  .float>header .acts{font-weight:400;color:#888}
  .float>header .acts span{cursor:pointer;padding:0 4px}
  .body{padding:10px;overflow:auto;flex:1;resize:both}
  #toolbar{top:10px;left:10px;right:10px;width:auto;flex-direction:row;flex-wrap:wrap;gap:8px;
    align-items:center;padding:7px 10px}
  #toolbar input#search{flex:1;min-width:120px;padding:5px 8px;border:1px solid #ccc;border-radius:6px}
  .chk{display:inline-flex;align-items:center;gap:4px;cursor:pointer;white-space:nowrap;font-size:12px}
  .swatch{display:inline-block;width:10px;height:10px;border-radius:2px}
  #slidewrap{display:__SLIDER_DISPLAY__;align-items:center;gap:6px;white-space:nowrap;font-size:12px}
  #count{color:#666;font-size:12px;white-space:nowrap;margin-left:auto}
  .kv{display:flex;gap:8px;padding:3px 0;border-bottom:1px solid #eee;font-size:12px}
  .kv span:first-child{color:#888;min-width:78px;flex-shrink:0}
  .muted{color:#999;font-style:italic}
  a{color:#1f77b4}
  #valtable{width:100%;border-collapse:collapse;font-size:11px;margin-bottom:8px;
    display:block;max-height:130px;overflow:auto}
  #valtable th,#valtable td{border-bottom:1px solid #eee;padding:2px 4px;text-align:left}
  .row1{display:flex;gap:6px;align-items:center;margin:4px 0;flex-wrap:wrap}
  .row1 select,.row1 button{padding:3px 6px;border:1px solid #ccc;border-radius:5px;background:#fff}
  .row1 button{cursor:pointer;background:#1f77b4;color:#fff;border-color:#1f77b4}
  .row1 button.ghost{background:#fff;color:#444}
  #viewbtns button{padding:3px 7px;border:1px solid #ccc;border-radius:5px;background:#fff;
    cursor:pointer;font-size:12px}
  #viewbtns button:hover{background:#eef3fb;border-color:#1f77b4}
  #plot{width:100%;height:240px}
  .hint{font-size:11px;color:#888;margin-top:4px}
</style></head>
<body>
<div id="stage">
  <div id="net"></div>

  <div id="toolbar" class="float">
    <input id="search" placeholder="Search nodes…">
    __CHECKS__
    <span id="slidewrap">| <b>min conf</b>
      <input id="conf" type="range" min="0" max="1" step="0.05" value="0">
      <span id="confval">0.00</span></span>
    <span id="viewbtns">| <button id="fitbtn" title="Recenter / fit graph">&#10530; Center</button>
      <button id="stagebtn" title="Pin nodes into the study-stage cycle">&#9678; Stages</button>
      <button id="freebtn" title="Release into free physics layout">&#10022; Free</button>
      <label class="chk" title="Rotate the whole stage cycle">&#8635;
        <input id="rot" type="range" min="0" max="360" step="5" value="0" style="width:84px">
      </label></span>
    <span id="count"></span>
  </div>

  <div id="pLegend" class="float" style="bottom:14px;left:12px;width:184px;max-height:46vh">
    <header>Study stages <span class="acts"><span data-min>&mdash;</span></span></header>
    <div class="body"><div id="legendbody"></div></div>
  </div>

  <div id="pDetails" class="float" style="top:64px;right:12px;width:300px;height:300px">
    <header>Details <span class="acts"><span data-min>&mdash;</span></span></header>
    <div class="body"><div id="detailbody" class="muted">Click any node or edge to
      inspect its provenance and metadata.</div></div>
  </div>

  <div id="pData" class="float" style="bottom:14px;right:12px;width:380px;height:360px">
    <header>Data &amp; Plot <span class="acts"><span data-min>&mdash;</span></span></header>
    <div class="body">
      <div class="row1">
        <label>Property
          <select id="propsel" title="Every raw value papers reported for this property"></select>
        </label>
        <label>Chart <select id="ctype">
          <option value="scatter">scatter</option>
          <option value="bar">bar</option>
          <option value="box">box</option>
          <option value="line">line</option>
        </select></label>
        <button id="plotbtn">Plot</button>
      </div>
      <table id="valtable"><thead><tr><th>Paper</th><th>Raw value</th></tr></thead><tbody></tbody></table>
      <div id="plot"></div>
      <div class="row1">
        <button class="ghost" id="pngbtn">&#11015; PNG</button>
        <button class="ghost" id="csvbtn">&#11015; CSV</button>
        <span id="plotinfo" class="hint"></span>
      </div>
      <div class="hint">Click a node (an efficiency concept, a measurement, or a
        raw value) to load every value papers reported for it.</div>
    </div>
  </div>
</div>

<script>
var RAW_NODES = __NODES__, RAW_EDGES = __EDGES__;
var STAGES = __STAGES__, STAGECOLORS = __STAGECOLORS__, ROT = 0;
RAW_NODES.forEach(function(n){ n.color = STAGECOLORS[n.stage] || STAGECOLORS['unclassified']; });
var nodes = new vis.DataSet(RAW_NODES), edges = new vis.DataSet(RAW_EDGES);
var NMAP = {}; RAW_NODES.forEach(function(n){ NMAP[n.id]=n; });
var network = new vis.Network(document.getElementById('net'),
  {nodes:nodes, edges:edges}, {
  interaction:{hover:true, tooltipDelay:120, navigationButtons:true, keyboard:true, multiselect:true},
  physics:{barnesHut:{gravitationalConstant:-16000, springLength:120,
    springConstant:0.02, damping:0.4, avoidOverlap:0.5},
    minVelocity:0.6, stabilization:{iterations:300}},
  nodes:{font:{size:13}, scaling:{min:8,max:42}},
  edges:{smooth:{type:'dynamic'}, font:{size:9,align:'middle'}, arrows:'to'}
});
network.once('stabilizationIterationsDone', function(){ stageLayout(); });

var detailBody = document.getElementById('detailbody');
function showDetail(html){ detailBody.className=''; detailBody.innerHTML = html || '<span class="muted">No details.</span>'; }
detailBody.addEventListener('click', function(ev){
  var t = ev.target.closest('[data-focus]'); if(!t) return; ev.preventDefault();
  var id=t.getAttribute('data-focus'); network.selectNodes([id]);
  network.focus(id,{scale:1.1,animation:true}); if(NMAP[id]) showDetail(NMAP[id].detail);
});

var VALNODES = RAW_NODES.filter(function(n){ return n.group==='value' && n.prop; });
var PROPS = {};
VALNODES.forEach(function(n){ (PROPS[n.prop] = PROPS[n.prop] || []).push(n); });
var LAST_ROWS = [];
function shorten(s,n){ s=String(s||''); return s.length<=n ? s : s.slice(0,n-1)+'…'; }
function fillProps(){
  var sel=document.getElementById('propsel'), keys=Object.keys(PROPS).sort();
  if(!keys.length){ sel.innerHTML='<option value="">(no raw values extracted)</option>'; return; }
  sel.innerHTML = keys.map(function(k){
    return '<option value="'+escapeHtml(k)+'">'+escapeHtml(k)+' ('+PROPS[k].length+')</option>';
  }).join('');
}
function setProp(p){ var s=document.getElementById('propsel'); if(p in PROPS){ s.value=p; return true; } return false; }
function matchProp(node){
  if(node.group==='value' && node.prop) return node.prop;
  var toks=(node.label.toLowerCase().match(/[a-z]{4,}/g))||[];
  var best=null, bestn=0;
  Object.keys(PROPS).forEach(function(p){
    var pl=p.toLowerCase(), c=0;
    toks.forEach(function(t){ if(pl.indexOf(t)>=0) c++; });
    if(c>bestn){ bestn=c; best=p; }
  });
  return best;
}
function plotProperty(){
  var prop=document.getElementById('propsel').value;
  var rows=(PROPS[prop]||[]).map(function(n){ return {paper:n.paper, raw:n.raw, value:n.valnum}; });
  LAST_ROWS=rows.map(function(r){ return {property:prop, paper:r.paper, raw:r.raw, value:r.value}; });
  var tb=document.querySelector('#valtable tbody'); tb.innerHTML='';
  rows.forEach(function(r){
    var tr=document.createElement('tr');
    tr.innerHTML='<td title="'+escapeHtml(r.paper)+'">'+escapeHtml(shorten(r.paper,26))+
                 '</td><td>'+escapeHtml(r.raw)+'</td>';
    tb.appendChild(tr);
  });
  var num=rows.filter(function(r){ return r.value!==null && r.value!==undefined; });
  document.getElementById('plotinfo').textContent = rows.length+' value(s), '+num.length+' numeric';
  if(!num.length){ Plotly.purge('plot'); return; }
  var ctype=document.getElementById('ctype').value;
  var xs=num.map(function(r){ return shorten(r.paper,16); });
  var ys=num.map(function(r){ return r.value; });
  var txt=num.map(function(r){ return r.raw+'<br>'+r.paper; });
  var trace=(ctype==='box')
    ? {type:'box', y:ys, name:prop, boxpoints:'all', text:txt, hoverinfo:'y+text'}
    : {type:(ctype==='line'?'scatter':ctype), mode:(ctype==='line'?'lines+markers':'markers'),
       x:xs, y:ys, text:txt, hovertemplate:'%{text}<br>'+escapeHtml(prop)+'=%{y}<extra></extra>',
       marker:{size:11,color:'#1f77b4'}};
  Plotly.newPlot('plot',[trace],
    {margin:{t:8,r:10,b:80,l:50}, xaxis:{tickangle:-40, automargin:true},
     yaxis:{title:prop, automargin:true}},
    {displayModeBar:true, displaylogo:false, responsive:true,
     modeBarButtonsToRemove:['lasso2d','select2d','autoScale2d']});
}
document.getElementById('plotbtn').onclick=plotProperty;
document.getElementById('propsel').onchange=plotProperty;
document.getElementById('ctype').onchange=plotProperty;
document.getElementById('pngbtn').onclick=function(){
  Plotly.downloadImage('plot',{format:'png',width:820,height:500,
    filename:'mds_'+(document.getElementById('propsel').value||'plot')});
};
document.getElementById('csvbtn').onclick=function(){
  if(!LAST_ROWS.length){ return; }
  var hdr=['property','paper','raw','value'];
  var lines=[hdr.join(',')].concat(LAST_ROWS.map(function(r){
    return hdr.map(function(h){ var v=(r[h]==null?'':String(r[h])); return '"'+v.replace(/"/g,'""')+'"'; }).join(',');
  }));
  var blob=new Blob([lines.join('\n')],{type:'text/csv'});
  var a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='mds_'+(document.getElementById('propsel').value||'values')+'.csv'; a.click();
};
network.on('click', function(p){
  if(p.nodes.length){
    var n=NMAP[p.nodes[0]]; if(!n) return;
    showDetail(n.detail);
    var mp=matchProp(n);
    if(mp && setProp(mp)) plotProperty();
  } else if(p.edges.length){
    var e=edges.get(p.edges[0]); showDetail(e && e.detail);
  }
});

// ---- study-stage cycle layout (fixed positions, rotatable) ---------------
var HIDDEN={};
var RING = STAGES.filter(function(s){ return s!=='unclassified'; });
var STAGE_LABELS_ADDED=false;
function ensureStageLabels(){
  if(STAGE_LABELS_ADDED) return; STAGE_LABELS_ADDED=true;
  RING.forEach(function(s){
    nodes.add({id:'__stage__'+s, label:s, shape:'text',
      font:{size:17, color:STAGECOLORS[s]||'#777', face:'system-ui', bold:true},
      physics:false, fixed:true, chosen:false});
  });
}
function stageLayout(){
  network.setOptions({physics:false});
  ensureStageLabels();
  var N=RING.length||1, R=Math.max(480, N*95), upd=[];
  var ang={}; RING.forEach(function(s,i){ ang[s]=(-Math.PI/2)+2*Math.PI*i/N+ROT; });
  var groups={}, center=[];
  RAW_NODES.forEach(function(n){
    if(HIDDEN[n.id]) return;
    if(n.group==='publication'||n.group==='domain'||ang[n.stage]===undefined){ center.push(n.id); }
    else { (groups[n.stage]=groups[n.stage]||[]).push(n.id); }
  });
  Object.keys(groups).forEach(function(s){
    var ids=groups[s], th=ang[s], ax=Math.cos(th)*R, ay=Math.sin(th)*R;
    var cols=Math.max(1,Math.ceil(Math.sqrt(ids.length))), d=72;
    ids.forEach(function(id,i){ var r=Math.floor(i/cols), c=i%cols;
      upd.push({id:id, x:ax+(c-cols/2)*d, y:ay+(r-cols/2)*d, fixed:false}); });
    upd.push({id:'__stage__'+s, x:Math.cos(th)*(R*1.16), y:Math.sin(th)*(R*1.16)});
  });
  var cc=Math.max(1,Math.ceil(Math.sqrt(center.length||1))), cd=64;
  center.forEach(function(id,i){ var r=Math.floor(i/cc), c=i%cc;
    upd.push({id:id, x:(c-cc/2)*cd, y:(r-cc/2)*cd, fixed:false}); });
  nodes.update(upd); network.fit({animation:{duration:450}});
}
function recenter(){ network.fit({animation:{duration:500}}); }
function freeLayout(){
  RAW_NODES.forEach(function(n){ nodes.update({id:n.id, fixed:false}); });
  network.setOptions({physics:true});
}
document.getElementById('fitbtn').onclick=recenter;
document.getElementById('stagebtn').onclick=function(){ ROT=0;
  document.getElementById('rot').value=0; stageLayout(); };
document.getElementById('freebtn').onclick=freeLayout;
document.getElementById('rot').addEventListener('input',function(){
  ROT=parseFloat(this.value)*Math.PI/180; stageLayout(); });

(function buildLegend(){
  var lb=document.getElementById('legendbody');
  lb.innerHTML = STAGES.map(function(s,i){
    return '<label class="chk" style="display:flex;width:100%;gap:6px">'+
      '<span class="swatch" style="background:'+(STAGECOLORS[s]||'#888')+'"></span>'+
      '<span>'+(s==='unclassified'?'—':(i+1)+'.')+' '+escapeHtml(s)+'</span></label>';
  }).join('');
})();

var search=document.getElementById('search'), conf=document.getElementById('conf'),
    confval=document.getElementById('confval'), count=document.getElementById('count');
function enabledTypes(){ var s={}; document.querySelectorAll('[data-type]').forEach(function(c){ s[c.getAttribute('data-type')]=c.checked; }); return s; }
function applyFilters(){
  var q=search.value.trim().toLowerCase(), th=parseFloat(conf.value);
  confval.textContent=th.toFixed(2); var types=enabledTypes(), hidden={}, shown=0;
  nodes.update(RAW_NODES.map(function(n){
    var hide=!types[n.group]||(q && n.label.toLowerCase().indexOf(q)<0);
    hidden[n.id]=hide; if(!hide) shown++; return {id:n.id, hidden:hide};
  }));
  edges.update(RAW_EDGES.map(function(e){
    var hide=hidden[e.from]||hidden[e.to]||(e.etype==='relation' && e.conf<th);
    return {id:e.id, hidden:hide};
  }));
  HIDDEN=hidden;
  count.textContent=shown+' / '+RAW_NODES.length+' nodes';
}
search.addEventListener('input',applyFilters); conf.addEventListener('input',applyFilters);
document.querySelectorAll('[data-type]').forEach(function(c){ c.addEventListener('change',applyFilters); });

function makeDraggable(panel){
  var h=panel.querySelector('header'); var sx,sy,ox,oy,drag=false;
  h.addEventListener('mousedown',function(e){
    if(e.target.closest('[data-min]')) return;
    drag=true; sx=e.clientX; sy=e.clientY;
    var r=panel.getBoundingClientRect(), pr=panel.parentElement.getBoundingClientRect();
    ox=r.left-pr.left; oy=r.top-pr.top;
    panel.style.left=ox+'px'; panel.style.top=oy+'px';
    panel.style.right='auto'; panel.style.bottom='auto'; e.preventDefault();
  });
  document.addEventListener('mousemove',function(e){
    if(!drag) return; panel.style.left=(ox+e.clientX-sx)+'px'; panel.style.top=(oy+e.clientY-sy)+'px';
  });
  document.addEventListener('mouseup',function(){ drag=false; });
  var mn=panel.querySelector('[data-min]'); var body=panel.querySelector('.body');
  if(mn){ mn.onclick=function(){ var hidden=body.style.display==='none';
    body.style.display=hidden?'':'none'; mn.textContent=hidden?'—':'+'; }; }
}
['pDetails','pData','pLegend','toolbar'].forEach(function(id){ makeDraggable(document.getElementById(id)); });

function escapeHtml(s){ return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }

fillProps(); applyFilters(); if(Object.keys(PROPS).length){ plotProperty(); }
</script>
</body></html>
"""
