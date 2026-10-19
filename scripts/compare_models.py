"""Model comparison across sweeps: which model does what better, with figures.

  python scripts/compare_models.py --match pv-cost-chain                 # every pv-cost-chain sweep in outputs/
  python scripts/compare_models.py --outputs outputs/bucket --match pv-cost-chain --size 2
  python scripts/compare_models.py --sweeps pv-cost-chain-llama31-8b-n2 pv-cost-chain-gptoss-20b-n2 --out DIR

One sweep is one model: outputs/sweep-<id>/ with its domain runs <collection>-n<size>-<id>/ and
integration-n<size>-<id>/. Everything is read from those folders (run.json, papers/, ledger.jsonl, ontology/,
normalized/), not from eval_runs.csv, so a copy synced from the bucket works. Sweeps are compared at one corpus
size (--size, default: the largest size most sweeps reached). Unfinished sweeps are compared on what exists.

Writes to --out (default outputs/model-comparison/<match>-n<size>/): model_metrics.csv, domain_metrics.csv, one
PDF/PNG/CSV per figure, report.md and report.html. Matched paper reports and paper_metrics.csv
compare all saved papers; --top-papers (default 1) controls citation-ranked detail per domain. Counts measure output volume; evidence shares are the automatic
precision proxy. Correctness needs expert review (scripts/review_sample.py).

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import argparse
import base64
import csv
import html
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.figures import (BLUES, DOMAINS, GRID, INK, INK2, SLOTS, Out, _csv, _json, gpu_statistics,  # noqa: E402
                         grouped_barh, matplotlib, plt)
import numpy as np  # noqa: E402

KINDS = ("relations", "causal", "measurements")
BEST, REST = BLUES[5], BLUES[2]

# (key, label, format, higher is better, group): the scorecard and the report tables, in order.
METRICS = [
    ("json_first_try", "Valid JSON, first try", "pct", True, "Reliability"),
    ("truncated_share", "Replies cut off at cap", "pct", False, "Reliability"),
    ("lost_share", "Calls lost after retry", "pct", False, "Reliability"),
    ("completed_share", "Domain runs completed", "pct", True, "Reliability"),
    ("concepts_pp", "Concepts / paper", "f1", True, "Extraction"),
    ("relations_pp", "Relations / paper", "f1", True, "Extraction"),
    ("causal_pp", "Causal claims / paper", "f1", True, "Extraction"),
    ("measurements_pp", "Reported values / paper", "f1", True, "Extraction"),
    ("relations_found", "Relation evidence found", "pct", True, "Grounding"),
    ("causal_found", "Causal evidence found", "pct", True, "Grounding"),
    ("measurements_found", "Value evidence found", "pct", True, "Grounding"),
    ("multi_paper_share", "Concepts in 2+ papers", "pct", True, "Normalization"),
    ("cluster_merge_share", "Synonym merges per look-alike cluster", "f2", True, "Normalization"),
    ("classes", "Final classes", "int", True, "Ontology"),
    ("unresolved_share", "Unresolved placements", "pct", False, "Ontology"),
    ("unsupported_share", "Unsupported definitions", "pct", False, "Ontology"),
    ("defined_share", "Classes with a definition", "pct", True, "Ontology"),
    ("external_share", "Classes mapped externally", "pct", True, "Ontology"),
    ("mean_depth", "Mean depth to BFO entity", "f1", True, "Hierarchy"),
    ("max_local_depth", "Deepest local chain", "int", True, "Hierarchy"),
    ("local_root_share", "Classes with no local parent", "pct", False, "Hierarchy"),
    ("default_placement_share", "Placed by category default", "pct", False, "Hierarchy"),
    ("bridges", "Bridge concepts", "int", True, "Integration"),
    ("cross_mappings", "Cross-domain mappings", "int", True, "Integration"),
    ("gpu_hours", "GPU-hours", "f2", False, "Cost"),
    ("min_per_paper", "Pipeline minutes / paper", "f1", False, "Cost"),
    ("tokens_per_class", "Tokens / final class", "int", False, "Cost"),
]
NAMES = {k: (lab, fmt, hi, grp) for k, lab, fmt, hi, grp in METRICS}


def fmt(v, kind) -> str:
    if v is None:
        return "-"
    if kind == "pct":
        return f"{v:.1%}" if 0 < v < 0.1 else f"{v:.0%}"
    return {"f1": f"{v:.1f}", "f2": f"{v:.2f}", "int": f"{v:,.0f}"}[kind]


def same(a, b) -> bool:
    """Within 0.5% of each other: no real difference between models."""
    return abs(a - b) <= 1e-9 + 0.005 * max(abs(a), abs(b))


def spread(models, key) -> bool:
    have = [m[key] for m in models if m.get(key) is not None]
    return len(have) > 1 and not same(min(have), max(have))


def ratio(a, b):
    return a / b if b else None


# ---------------------------------------------------------------- reading

def ledger(folder: Path, cap: int) -> dict:
    """Model calls (cache hits excluded): first attempts, their failures, failed retries, replies at the token cap."""
    s = defaultdict(int)
    path = folder / "ledger.jsonl"
    if not path.is_file():
        return s
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("cache_hit"):
            continue
        s["calls"] += 1
        s["tokens"] += (r.get("input_tokens") or 0) + (r.get("output_tokens") or 0)
        s["truncated"] += (r.get("output_tokens") or 0) >= cap * 0.98
        first = not r.get("attempt")
        s["first"] += first
        s["first_failed"] += first and not r.get("ok", True)
        s["retry_failed"] += (not first) and not r.get("ok", True)
    return s


def domain_run(folder: Path) -> dict | None:
    m = _json(folder / "run.json")
    if not isinstance(m, dict):
        return None
    cfg, stages, corpus = m.get("config", {}), m.get("stages", {}), m.get("corpus", {})
    papers = [p for p in (_json(f) for f in sorted((folder / "papers").glob("*.json"))) if isinstance(p, dict)]
    cs = _json(folder / "normalized" / "corpus_stats.json") or {}
    om = _json(folder / "ontology" / "metrics.json") or {}
    val = _json(folder / "ontology" / "validation.json") or {}
    cap = int((cfg.get("request_options") or {}).get("max_tokens") or cfg.get("max_output_tokens") or 8000)  # served cap
    r = {"collection": (m.get("collection") or {}).get("name") or folder.name.split("-n")[0],
         "model": cfg.get("model_extraction") or "", "revision": cfg.get("workflow_revision") or "",
         "papers": corpus.get("processed") or len(papers), "papers_failed": len(corpus.get("failed", [])),
         "concepts": sum(len(p.get("concepts", [])) for p in papers),
         "canonical": cs.get("canonical_concepts") or 0, "multi_paper": cs.get("concepts_in_2plus_papers") or 0,
         "classes": om.get("classes") or 0,
         "clusters": cs.get("candidate_clusters") or 0, "merges": cs.get("semantic_merges") or 0,
         "mean_depth": (om.get("hierarchy") or {}).get("mean_depth_to_bfo_entity"),
         "max_local_depth": (om.get("hierarchy") or {}).get("max_local_depth"),
         "local_roots": (om.get("hierarchy") or {}).get("local_roots"),
         "default_placed": ((om.get("hierarchy") or {}).get("placement") or {}).get("category_default"),
         "unresolved": (stages.get("ontology") or {}).get("unresolved_placements") or 0,
         "unsupported": (stages.get("enrich") or {}).get("unsupported_definitions") or 0,
         "undefined": (om.get("definitions_by_status") or {}).get("none"),
         "external": (om.get("coverage") or {}).get("external_mapping"),
         "complete": "interop" in stages and val.get("valid") is True,
         "wall_s": sum((s or {}).get("wall_s") or 0 for s in stages.values()), **ledger(folder, cap)}
    for k in KINDS:
        r[k] = sum(len(p.get(k, [])) for p in papers)
        v = [p.get("verification", {}).get(k, {}) for p in papers]
        r[k + "_items"], r[k + "_verified"] = sum(x.get("items", 0) for x in v), sum(x.get("verified", 0) for x in v)
    return r


def integration_run(folder: Path) -> dict:
    m = _json(folder / "integration.json") or {}
    cap = int((m.get("config") or {}).get("max_output_tokens") or 8000)
    maps, bridges = _json(folder / "mappings.json"), _json(folder / "bridge_concepts.json")
    return {"valid": (m.get("validation") or {}).get("valid"), "bridges": len(bridges) if isinstance(bridges, list) else None,
            "cross_mappings": len(maps) if isinstance(maps, list) else None,
            "wall_s": (m.get("compute") or {}).get("wall_s") or 0, **ledger(folder, cap)}


def discover(outputs: Path, match: str, sweeps: list[str] | None) -> dict[str, dict[int, dict]]:
    """sweep id -> size -> {'domains': [run folders], 'integration': folder or None}."""
    ids = [s.removeprefix("sweep-") for s in sweeps] if sweeps else sorted(
        p.name.removeprefix("sweep-") for p in outputs.glob("sweep-*") if p.is_dir() and match in p.name)
    found = {}
    for sid in ids:
        sizes = defaultdict(lambda: {"domains": [], "integration": None})
        for p in outputs.glob(f"*-n*-{sid}"):
            hit = re.fullmatch(rf"(.+)-n(\d+)-{re.escape(sid)}", p.name)
            if not hit or not p.is_dir():
                continue
            name, n = hit.group(1), int(hit.group(2))
            if name == "integration":
                sizes[n]["integration"] = p
            elif (p / "run.json").is_file():
                sizes[n]["domains"].append(p)
        found[sid] = dict(sizes)
    return found


def tag(sid: str, match: str, model: str) -> str:
    t = re.sub(r"-n\d+$", "", sid.removeprefix(match).strip("-")) if match else sid
    if not t or re.fullmatch(r"[\d-]+", t):
        t = f"{model.split('/')[-1] or 'model'} ({sid})"
    return t


def summarize(sid: str, entry: dict, size: int, outputs: Path, match: str) -> tuple[dict, list[dict]]:
    runs = [r for r in (domain_run(p) for p in sorted(entry["domains"])) if r]
    integ = integration_run(entry["integration"]) if entry.get("integration") else {}
    statuses = [s for s in _csv(outputs / f"sweep-{sid}" / "summary.csv")
                if s.get("kind") == "domain" and str(s.get("limit")) == str(size)]
    gpu = gpu_statistics(outputs / f"sweep-{sid}")
    tot = lambda k: sum(r.get(k) or 0 for r in runs)
    papers, classes, first = tot("papers"), tot("classes"), tot("first") + (integ.get("first") or 0)
    model = next((r["model"] for r in runs if r["model"]), "")
    m = {"label": tag(sid, match, model), "model": model, "sweep": sid, "size": size,
         "revision": "; ".join(sorted({r["revision"] for r in runs if r["revision"]})),
         "domains": "+".join(r["collection"] for r in runs), "papers": papers, "papers_failed": tot("papers_failed"),
         "calls": tot("calls") + (integ.get("calls") or 0),
         "json_first_try": 1 - ratio(tot("first_failed") + (integ.get("first_failed") or 0), first) if first else None,
         "truncated_share": ratio(tot("truncated") + (integ.get("truncated") or 0), tot("calls") + (integ.get("calls") or 0)),
         "lost_share": ratio(tot("retry_failed") + (integ.get("retry_failed") or 0), first),
         "completed_share": ratio(sum(s.get("status") == "completed" for s in statuses), len(statuses))
         if statuses else ratio(sum(r["complete"] for r in runs), len(runs)),
         "concepts_pp": ratio(tot("concepts"), papers),
         **{f"{k}_pp": ratio(tot(k), papers) for k in KINDS},
         **{f"{k}_found": ratio(tot(k + "_verified"), tot(k + "_items")) for k in KINDS},
         "classes": classes or None, "multi_paper_share": ratio(tot("multi_paper"), tot("canonical")),
         "cluster_merge_share": ratio(tot("merges"), tot("clusters")),
         "mean_depth": ratio(sum(r["mean_depth"] * r["classes"] for r in runs if r["mean_depth"] is not None),
                             sum(r["classes"] for r in runs if r["mean_depth"] is not None)),
         "max_local_depth": max((r["max_local_depth"] for r in runs if r["max_local_depth"] is not None), default=None),
         "local_root_share": ratio(tot("local_roots"), classes) if any(r["local_roots"] is not None for r in runs) else None,
         "default_placement_share": ratio(tot("default_placed"), classes)
         if any(r["default_placed"] is not None for r in runs) else None,
         "unresolved_share": ratio(tot("unresolved"), classes), "unsupported_share": ratio(tot("unsupported"), classes),
         "defined_share": (1 - ratio(tot("undefined"), classes)) if classes and all(r["undefined"] is not None for r in runs) else None,
         "external_share": ratio(sum((r["external"] or 0) * r["classes"] for r in runs), classes)
         if classes and any(r["external"] is not None for r in runs) else None,
         "bridges": integ.get("bridges"), "cross_mappings": integ.get("cross_mappings"),
         "integration_valid": integ.get("valid"),
         "gpu_hours": gpu.get("gpu_hours"), "gpu_utilization_pct": gpu.get("gpu_utilization_pct"),
         "min_per_paper": ratio(tot("wall_s") / 60, papers) if tot("wall_s") else None,
         "tokens_per_class": ratio(tot("tokens") + (integ.get("tokens") or 0), classes)}
    rows = [{"model": m["label"], "domain": r["collection"], "papers": r["papers"], "complete": r["complete"],
             "canonical_concepts": r["canonical"], "final_classes": r["classes"],
             "concepts_per_paper": ratio(r["concepts"], r["papers"]),
             **{f"{k}_evidence_found": ratio(r[k + "_verified"], r[k + "_items"]) for k in KINDS},
             "concepts_in_2plus_papers": ratio(r["multi_paper"], r["canonical"]),
             "cluster_merge_share": ratio(r["merges"], r["clusters"]),
             "mean_depth_to_bfo": r["mean_depth"], "max_local_depth": r["max_local_depth"],
             "local_root_share": ratio(r["local_roots"] or 0, r["classes"]) if r["local_roots"] is not None else None,
             "json_first_try": 1 - ratio(r.get("first_failed", 0), r["first"]) if r.get("first") else None} for r in runs]
    return m, rows


# ---------------------------------------------------------------- figures

def bars(ax, models, key):
    lab, kind, hi, _ = NAMES[key]
    items = sorted(((m["label"], m[key]) for m in models if m.get(key) is not None), key=lambda x: x[1], reverse=hi)
    ax.set_title(lab + (" (higher is better)" if hi else " (lower is better)"), loc="left")
    if not items:
        ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes, color=INK2)
        ax.set_yticks([])
        return
    y = np.arange(len(items))
    vals = [v for _, v in items]
    lead = spread(models, key)  # highlight the leader(s) only when the models really differ
    ax.barh(y, vals, height=0.62, color=[BEST if lead and same(v, vals[0]) else REST for v in vals],
            edgecolor="white", linewidth=1.0)
    top = max(vals) or 1
    for i, v in enumerate(vals):
        ax.text(v + top * 0.02, i, fmt(v, kind), va="center", fontsize=7, color=INK)
    ax.set_xlim(0, top * 1.22)
    if kind == "pct":
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_yticks(y, [n for n, _ in items])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)


def panels(out, models, name, title, keys, cols=None):
    if not any(m.get(k) is not None for m in models for k in keys):
        return out.skip(name, "no data for these metrics yet")
    cols = cols or len(keys)
    rows = -(-len(keys) // cols)
    width = 2.4 + 0.055 * max(len(m["label"]) for m in models)
    fig, axes = plt.subplots(rows, cols, figsize=(width * cols, 0.3 * len(models) * rows + 1.1 * rows), squeeze=False,
                             layout="constrained")
    for ax, k in zip(axes.flat, keys):
        bars(ax, models, k)
    for ax in list(axes.flat)[len(keys):]:
        ax.set_visible(False)
    out.save(fig, name, title, "model_metrics.csv " + ", ".join(keys),
             [{"model": m["label"], **{k: m.get(k) for k in keys}} for m in models])


def scorecard(out, models):
    """Each metric scaled across models (best darkest), with the value printed in the cell."""
    keys = [k for k, *_ in METRICS if sum(m.get(k) is not None for m in models) >= 1]
    if not keys:
        return out.skip("scorecard", "no metrics yet")
    order = sorted(models, key=lambda m: -wins(models, m))
    grid = np.full((len(order), len(keys)), np.nan)
    for j, k in enumerate(keys):
        vals = [m.get(k) for m in order]
        have = [v for v in vals if v is not None]
        lo, hi = min(have), max(have)
        for i, v in enumerate(vals):
            if v is not None and spread(models, k):
                t = 1.0 if hi == lo else (v - lo) / (hi - lo)
                grid[i, j] = t if NAMES[k][2] else 1 - t
    fig, ax = plt.subplots(figsize=(0.62 * len(keys) + 2.2, 0.36 * len(order) + 1.9))
    cmap = matplotlib.colors.ListedColormap(BLUES)
    cmap.set_bad("#f3f2ee")
    ax.imshow(np.ma.masked_invalid(grid), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i, m in enumerate(order):
        for j, k in enumerate(keys):
            ax.text(j, i, fmt(m.get(k), NAMES[k][1]), ha="center", va="center", fontsize=6,
                    color="white" if not np.isnan(grid[i, j]) and grid[i, j] > 0.6 else INK)
    ax.set_xticks(range(len(keys)), [NAMES[k][0] + (" ↑" if NAMES[k][2] else " ↓") for k in keys],
                  rotation=40, ha="right")
    ax.set_yticks(range(len(order)), [f"{m['label']} ({wins(models, m)})" for m in order])
    groups = [NAMES[k][3] for k in keys]
    for j in range(1, len(keys)):
        if groups[j] != groups[j - 1]:
            ax.axvline(j - 0.5, color="white", linewidth=2.5)
    ax.grid(False)
    ax.set_title("Model scorecard: darker is better within each column (pale: no real difference); "
                 "(n) = metrics where the model is best", loc="left")
    out.save(fig, "scorecard", "Every metric across models, scaled per column so the best model is darkest",
             "model_metrics.csv", [{"model": m["label"], **{k: m.get(k) for k in keys}} for m in order])


def wins(models, m) -> int:
    n = 0
    for k, _, _, hi, _ in METRICS:
        have = [x[k] for x in models if x.get(k) is not None]
        if m.get(k) is not None and spread(models, k) and same(m[k], max(have) if hi else min(have)):
            n += 1
    return n


def per_domain(out, models, rows, name, title, specs):
    """One panel per metric; inside it, one bar per domain for each model (colour follows the domain)."""
    doms = [d for d in DOMAINS if any(r["domain"] == d for r in rows)]
    labels = [m["label"] for m in models]
    specs = [s for s in specs if any(r.get(s[0]) is not None for r in rows)]
    if not doms or not rows or not specs:
        return out.skip(name, "no domain runs with these metrics yet")
    fig, axes = plt.subplots(1, len(specs), figsize=(0.055 * max(len(x) for x in labels) + 3.0 * len(specs),
                                                     0.42 * len(labels) * max(1, len(doms)) / 2 + 1.6),
                             layout="constrained", squeeze=False)
    for j, (ax, (key, head, kind)) in enumerate(zip(axes.flat, specs)):
        values = {d: {r["model"]: r.get(key) or 0 for r in rows if r["domain"] == d} for d in doms}
        grouped_barh(ax, labels, {d: None for d in doms}, values, kind)
        ax.set_title(head, loc="left")
        if j:  # same model order in every panel: label it once
            ax.tick_params(labelleft=False)
    axes[0, 0].legend(loc="lower left", bbox_to_anchor=(0, 1.08), ncol=len(doms))
    keys = [k for k, *_ in specs]
    out.save(fig, name, title, "domain_metrics.csv " + ", ".join(keys),
             [{"model": r["model"], "domain": r["domain"], **{k: r.get(k) for k in keys}} for r in rows])


def cost_quality(out, models):
    pts = [(m["label"], m["min_per_paper"], np.mean([m[f"{k}_found"] for k in KINDS if m.get(f"{k}_found") is not None]))
           for m in models if m.get("min_per_paper") is not None and any(m.get(f"{k}_found") is not None for k in KINDS)]
    if not pts:
        return out.skip("cost_quality", "needs pipeline time and evidence checks")
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.scatter([p[1] for p in pts], [p[2] for p in pts], s=48, color=SLOTS[0], edgecolor="white", linewidth=1.5, zorder=3)
    xs, ys = [p[1] for p in pts], [p[2] for p in pts]
    xr, yr = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1
    placed = []
    for name, x, y in sorted(pts, key=lambda p: (p[2], p[1])):
        k = sum(1 for px, py in placed if abs(px - x) / xr < 0.25 and abs(py - y) / yr < 0.08)
        placed.append((x, y))
        ax.annotate(name, (x, y), xytext=(5, 3 + 9 * k), textcoords="offset points", fontsize=7, color=INK,
                    arrowprops=dict(arrowstyle="-", color=INK2, linewidth=0.5) if k else None)
    ax.set_xlabel("Pipeline minutes per paper (lower is better)")
    ax.set_ylabel("Evidence found, mean of relations, causal, values")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_title("Cost against grounding: up and to the left is better", loc="left")
    out.save(fig, "cost_quality", "Pipeline time per paper against the share of extracted items whose evidence was found",
             "model_metrics.csv min_per_paper, *_found", [{"model": n, "min_per_paper": x, "evidence_found_mean": y}
                                                          for n, x, y in pts])


# ---------------------------------------------------------------- report

def leaders(models) -> list[str]:
    lines = []
    for k, lab, kind, hi, grp in METRICS:
        have = [m for m in models if m.get(k) is not None]
        if not spread(models, k):
            continue
        best = sorted(have, key=lambda m: m[k], reverse=hi)
        tie = [m["label"] for m in best if same(m[k], best[0][k])]
        runner = next((m for m in best if not same(m[k], best[0][k])), None)
        lines.append(f"{grp} · {lab}: {', '.join(tie)} ({fmt(best[0][k], kind)})"
                     + (f"; next {runner['label']} ({fmt(runner[k], kind)})" if runner else ""))
    return lines


FIGS = [("scorecard", "Scorecard", "Every metric at once. Use it to see which model leads where, then read the panels."),
        ("reliability", "Reliability", "Whether the model returns usable JSON: first-try validity, replies cut off at the "
         "output cap (runaway generation), calls still invalid after the retry (their items are lost), and finished domains."),
        ("extraction", "Extraction yield", "Items extracted per paper. More is better recall only if the evidence holds up."),
        ("grounding", "Grounding", "Share of extracted items whose evidence quote was found in the paper text: the "
         "automatic precision proxy."),
        ("normalization", "Normalization", "How much the corpus joins up: concepts found in two or more papers, and the "
         "share of embedding look-alike clusters the model agreed to merge as synonyms. A low merge share with many "
         "clusters means near-duplicates stay separate concepts."),
        ("domain_normalization", "Normalization by domain", "The same two measures per domain (corpus)."),
        ("ontology", "Ontology", "The final domain ontologies: size, placement and definition quality, external alignment."),
        ("domain_classes", "By domain", "The same comparison per domain, to see whether a model's lead holds everywhere."),
        ("hierarchy", "Hierarchy", "Depth of the class hierarchy: mean steps from a class to the BFO entity root, the "
         "longest chain of local (paper-derived) classes, the share of classes with no local parent (a flat ontology "
         "hangs most classes straight off imported categories), and classes placed only by their BFO category default."),
        ("domain_depth", "Depth by domain", "Class depth per domain (corpus) and model."),
        ("integration", "Integration", "Cross-domain integration at this size."),
        ("cost", "Cost", "GPU-hours cover the whole sweep (every size it ran)."),
        ("cost_quality", "Cost against quality", "Trade-off between pipeline time and grounding.")]


def write_report(out, models, size, outputs, notes):
    made = {n: (t, s) for n, t, s in out.index}
    cols = [("label", "Model tag"), ("model", "Model"), ("domains", "Domains"), ("papers", "Papers"),
            ("calls", "Calls"), ("revision", "Revision")]
    title = f"Model comparison at n={size}"
    lead = (f"{len(models)} model(s) from {outputs}. Generated {datetime.now():%Y-%m-%d %H:%M}. Counts measure output volume; "
            "evidence shares are the automatic precision proxy; correctness needs expert review "
            "(scripts/review_sample.py). Each figure is also saved as PDF, PNG and CSV.")
    md = [f"# {title}", "", lead, *[f"\n> Note: {n}" for n in notes], "", "## Models", "",
          "| " + " | ".join(h for _, h in cols) + " |", "|" + "---|" * len(cols),
          *["| " + " | ".join(str(m.get(k) if m.get(k) not in (None, "") else "-") for k, _ in cols) + " |" for m in models],
          "", "## Leaders", "", "Metrics where the models differ by more than 0.5%.", "",
          *[f"- {x}" for x in leaders(models)], "", "## Metrics", "",
          "| Metric | " + " | ".join(m["label"] for m in models) + " |", "|" + "---|" * (len(models) + 1),
          *[f"| {lab} {'↑' if hi else '↓'} | " + " | ".join(fmt(m.get(k), kind) for m in models) + " |"
            for k, lab, kind, hi, _ in METRICS]]
    for nm, h, intro in FIGS:
        if nm in made:
            md += ["", f"## {h}", "", intro, "", f"![{made[nm][0]}]({nm}.png)", "",
                   f"<sub>Data: {made[nm][1]}. Files: `{nm}.pdf`, `{nm}.png`, `{nm}.csv`.</sub>"]
    if out.skipped:
        md += ["", "## Not drawn", "", *[f"- `{n}`: {w}" for n, w in out.skipped]]
    (out.folder / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    e = html.escape
    table = lambda head, body: ("<div class=scroll><table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head)
                                + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in r)
                                                                   + "</tr>" for r in body) + "</tbody></table></div>")
    body = [f"<h1>{e(title)}</h1>", f"<p class=lead>{e(lead)}</p>", *[f"<p class=note>Note: {e(n)}</p>" for n in notes],
            "<h2>Models</h2>", table([h for _, h in cols], [[m.get(k) if m.get(k) not in (None, "") else "-"
                                                           for k, _ in cols] for m in models]),
            "<h2>Leaders</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in leaders(models)) + "</ul>",
            "<h2>Metrics</h2>", table(["Metric"] + [m["label"] for m in models],
                                      [[f"{lab} {'↑' if hi else '↓'}"] + [fmt(m.get(k), kind) for m in models]
                                       for k, lab, kind, hi, _ in METRICS])]
    for nm, h, intro in FIGS:
        if nm in made:
            png = base64.b64encode((out.folder / f"{nm}.png").read_bytes()).decode()
            body.append(f"<section><h2>{e(h)}</h2><p class=intro>{e(intro)}</p><img alt='{e(made[nm][0])}' "
                        f"src='data:image/png;base64,{png}'><p class=src>Data: {e(made[nm][1])}.</p></section>")
    if out.skipped:
        body.append("<h2>Not drawn</h2><ul>" + "".join(f"<li><code>{e(n)}</code>: {e(w)}</li>" for n, w in out.skipped)
                    + "</ul>")
    css = ("body{font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif;color:#1b1b19;background:#fff;max-width:1080px;"
           f"margin:0 auto;padding:24px 16px}}h2{{margin-top:40px;border-bottom:1px solid {GRID};padding-bottom:6px}}"
           "img{max-width:100%;height:auto;border:1px solid #eee}.src{font-size:12px;color:#77756f}"
           ".lead,.intro{color:#3a3936}.note{background:#fff7e0;padding:6px 10px}.scroll{overflow-x:auto}"
           f"table{{border-collapse:collapse;font-size:13px;margin:10px 0}}th,td{{border-bottom:1px solid {GRID};"
           "padding:4px 8px;text-align:left;white-space:nowrap}"
           "@media (prefers-color-scheme: dark){body{background:#161615;color:#e8e6e1}img{background:#fff}"
           ".lead,.intro{color:#c8c7c2}.src{color:#b4b2aa}.note{background:#3a3220}th,td{border-color:#333}}")
    (out.folder / "report.html").write_text(
        f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,"
        f"initial-scale=1'><title>{e(title)}</title><style>{css}</style></head><body>{''.join(body)}</body></html>",
        encoding="utf-8")


def write_csv(path: Path, rows: list[dict]):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)


def compare_papers(outputs: Path, models: list[dict], found: dict, size: int, out: Path, top: int):
    """Match saved paper keys within domains; rank frozen citations without model calls."""
    if top < 1:
        raise ValueError("--top-papers must be at least 1")
    records, domains = {}, set()
    for model in models:
        for folder in found[model["sweep"]][size]["domains"]:
            manifest = _json(folder / "run.json") or {}
            domain = (manifest.get("collection") or {}).get("name") or folder.name.split("-n")[0]
            domains.add(domain)
            for path in sorted((folder / "papers").glob("*.json")):
                paper = _json(path)
                if not isinstance(paper, dict) or not paper.get("key"):
                    raise ValueError(f"Missing paper object or key: {path}")
                key = (domain, str(paper["key"]), model["sweep"])
                if key in records:
                    raise ValueError(f"Duplicate paper within domain and sweep: {key}")
                records[key] = (paper, path)
    rows, coverage, lines = [], [], ["# Matched paper comparison", "",
        "Citation counts are frozen run metadata. Rank is within the union of saved papers in each domain; "
        "unknown counts rank last. Ties use paper keys. Evidence matching checks quote presence, not scientific "
        "correctness. Counts describe output volume, not measured recall. Missing records stay blank. "
        "Latency is summed request latency and can overlap across concurrent calls; it is not wall time.", ""]
    def cell(value):
        return str(value if value is not None else "-").replace("|", " / ").replace("\n", " ")
    for domain in sorted(domains):
        keys = sorted({key for dom, key, sweep in records if dom == domain})
        metadata = {}
        for key in keys:
            copies = [paper for (dom, pk, sweep), (paper, path) in records.items() if dom == domain and pk == key]
            counts = {p.get("citations") for p in copies if isinstance(p.get("citations"), (int, float))}
            dois = {str(p.get("doi")).strip().lower() for p in copies if p.get("doi")}
            metadata[key] = (max(counts) if counts else None, len(counts) > 1, len(dois) > 1)
        ranked = sorted(keys, key=lambda key: (metadata[key][0] is None, -(metadata[key][0] or 0), key))
        sets = [{key for dom, key, sweep in records if dom == domain and sweep == m["sweep"]} for m in models]
        common = set.intersection(*sets) if sets else set()
        lines += [f"## {domain}", "", f"{len(common)} papers shared by all {len(models)} models; "
                  f"{len(keys)} distinct saved paper keys. Identical paper sets: {all(s == sets[0] for s in sets)}.", ""]
        for model, paper_set in zip(models, sets):
            coverage.append({"domain": domain, "model": model["label"], "sweep": model["sweep"],
                             "papers": len(paper_set), "shared_by_all": len(common),
                             "missing_keys": ";".join(sorted(set(keys) - paper_set))})
        for rank, key in enumerate(ranked, 1):
            count, citation_conflict, doi_conflict = metadata[key]
            paper_rows = []
            for model in models:
                saved = records.get((domain, key, model["sweep"]))
                paper, path = saved if saved else ({}, None)
                compute = paper.get("compute") or {}
                row = {"domain": domain, "citation_rank": rank, "paper_key": key,
                       "title": paper.get("title"), "doi": paper.get("doi"), "citations": count,
                       "recorded_citations": paper.get("citations"),
                       "citations_source": paper.get("citations_source"), "citations_fetched": paper.get("citations_fetched"),
                       "citation_conflict": citation_conflict, "doi_conflict": doi_conflict,
                       "shared_by_all": key in common, "model": model["label"], "sweep": model["sweep"],
                       "present": saved is not None, "source": str(path.resolve()) if path else None,
                       **{kind: len(paper.get(kind, [])) if saved else None for kind in ("concepts", *KINDS)},
                       **{k: compute.get(k) for k in ("calls", "input_tokens", "output_tokens", "latency_s")}}
                for kind in KINDS:
                    verification = (paper.get("verification") or {}).get(kind) or {}
                    row[kind + "_checked"] = verification.get("items")
                    row[kind + "_verified"] = verification.get("verified")
                    row[kind + "_evidence_found"] = ratio(verification["verified"], verification.get("items")) if verification.get("verified") is not None else None
                rows.append(row)
                paper_rows.append(row)
            if rank > top:
                continue
            title = next((r["title"] for r in paper_rows if r["title"]), key)
            lines += [f"### {rank}. {cell(title)}", "", f"Paper `{key}`; citations: {cell(count)}. "
                      f"Shared by all models: {key in common}. Citation conflict: {citation_conflict}; "
                      f"DOI conflict: {doi_conflict}.", "",
                      "| Model | Concepts | Relations | Causal | Values | Relation evidence | Causal evidence | Value evidence | Output tokens | Request seconds |",
                      "|---|---|---|---|---|---|---|---|---|---|"]
            for row in paper_rows:
                values = [row["model"], *[row[k] for k in ("concepts", *KINDS)],
                          *[fmt(row[k + "_evidence_found"], "pct") for k in KINDS],
                          row["output_tokens"], row["latency_s"]]
                lines.append("| " + " | ".join(cell(v) for v in values) + " |")
            lines.append("")
            available = [r for r in paper_rows if r["present"]]
            if available:
                largest = max(available, key=lambda r: r["concepts"])
                lines += [f"Largest concept output: {largest['model']} ({largest['concepts']:,}). "
                          "This is an output-volume comparison, not a correctness ranking.", ""]
    write_csv(out / "paper_metrics.csv", rows)
    write_csv(out / "paper_coverage.csv", coverage)
    (out / "paper_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    body, in_table = [], False
    for line in lines:
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(c == "---" for c in cells):
                continue
            tag_name = "td" if in_table else "th"
            if not in_table:
                body.append("<div style='overflow-x:auto'><table>")
            body.append("<tr>" + "".join(f"<{tag_name}>{html.escape(c)}</{tag_name}>" for c in cells) + "</tr>")
            in_table = True
            continue
        if in_table:
            body.append("</table></div>")
            in_table = False
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            body.append(f"<h{level}>{html.escape(line[level:].strip())}</h{level}>")
        elif line:
            body.append(f"<p>{html.escape(line)}</p>")
    if in_table:
        body.append("</table></div>")
    (out / "paper_comparison.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Matched paper comparison</title>"
        "<style>body{font:14px/1.5 system-ui;margin:24px}table{border-collapse:collapse}"
        "td,th{border:1px solid #ddd;padding:6px;text-align:left;white-space:nowrap}</style>"
        + "".join(body), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Compare models across sweeps, with figures and a report")
    ap.add_argument("--outputs", default=str(ROOT / "outputs"), help="folder holding the sweep and run folders")
    ap.add_argument("--match", default="", help="only sweeps whose name contains this, e.g. pv-cost-chain")
    ap.add_argument("--sweeps", nargs="*", help="explicit sweep ids (with or without the sweep- prefix)")
    ap.add_argument("--size", type=int, help="corpus size to compare (default: largest size most sweeps reached)")
    ap.add_argument("--out", help="report folder (default: outputs/model-comparison/<match>-n<size>)")
    ap.add_argument("--top-papers", type=int, default=1, help="highest-cited papers per domain shown in the paper report")
    args = ap.parse_args()
    if args.top_papers < 1:
        ap.error("--top-papers must be at least 1")
    outputs = Path(args.outputs).resolve()
    found = {s: e for s, e in discover(outputs, args.match, args.sweeps).items() if e}
    if not found:
        sys.exit(f"No sweeps with runs in {outputs}" + (f" matching '{args.match}'" if args.match else ""))
    reach = defaultdict(int)
    for sizes in found.values():
        for n in sizes:
            reach[n] += 1
    size = args.size or max(reach, key=lambda n: (reach[n], n))
    notes = [f"Not at n={size}, so not compared: {', '.join(s for s in found if size not in found[s])}"] \
        if any(size not in found[s] for s in found) else []
    models, rows = [], []
    for sid, sizes in found.items():
        if size in sizes:
            m, r = summarize(sid, sizes[size], size, outputs, args.match)
            models.append(m)
            rows += r
    if len({m["domains"] for m in models}) > 1:
        notes.append("Models finished different domains at this size (see Models); totals such as final classes are "
                     "not comparable across them, per-paper and share metrics are.")
    labels = [m["label"] for m in models]
    if len(set(labels)) < len(labels):
        for m in models:
            m["label"] = m["sweep"]
    out = Out(Path(args.out) if args.out else outputs / "model-comparison" / f"{args.match or 'all'}-n{size}")
    print(f"{len(models)} model(s) at n={size} -> {out.folder}")
    write_csv(out.folder / "model_metrics.csv", models)
    if rows:
        write_csv(out.folder / "domain_metrics.csv", rows)
    compare_papers(outputs, models, found, size, out.folder, args.top_papers)
    notes.append("Matched paper details: paper_comparison.md / paper_comparison.html; all papers: paper_metrics.csv; corpus matching: paper_coverage.csv.")
    steps = [("scorecard", lambda: scorecard(out, models)),
             ("reliability", lambda: panels(out, models, "reliability", "JSON validity, cut-off replies, lost calls, "
                                            "completed runs", [k for k, *_, g in METRICS if g == "Reliability"])),
             ("extraction", lambda: panels(out, models, "extraction", "Items extracted per paper",
                                           [k for k, *_, g in METRICS if g == "Extraction"])),
             ("grounding", lambda: panels(out, models, "grounding", "Share of items whose evidence was found",
                                          [k for k, *_, g in METRICS if g == "Grounding"])),
             ("ontology", lambda: panels(out, models, "ontology", "Final ontology size and quality",
                                         [k for k, *_, g in METRICS if g == "Ontology"], cols=3)),
             ("domain_classes", lambda: per_domain(out, models, rows, "domain_classes",
                                                   "Final classes and relation evidence per model and domain",
                                                   [("final_classes", "Final classes", None),
                                                    ("relations_evidence_found", "Relation evidence found", "share")])),
             ("normalization", lambda: panels(out, models, "normalization", "Concepts shared across papers and "
                                              "synonym merges", [k for k, *_, g in METRICS if g == "Normalization"])),
             ("domain_normalization", lambda: per_domain(out, models, rows, "domain_normalization",
                                                         "Cross-paper concepts and synonym merges per model and domain",
                                                         [("concepts_in_2plus_papers", "Concepts in 2+ papers", "share"),
                                                          ("cluster_merge_share", "Synonym merges per look-alike cluster",
                                                           None)])),
             ("hierarchy", lambda: panels(out, models, "hierarchy", "Class hierarchy depth and flatness",
                                          [k for k, *_, g in METRICS if g == "Hierarchy"])),
             ("domain_depth", lambda: per_domain(out, models, rows, "domain_depth",
                                                 "Class depth per model and domain (corpus)",
                                                 [("mean_depth_to_bfo", "Mean depth to BFO entity", None),
                                                  ("max_local_depth", "Deepest local chain", None),
                                                  ("local_root_share", "Classes with no local parent", "share")])),
             ("integration", lambda: panels(out, models, "integration", "Cross-domain integration",
                                            [k for k, *_, g in METRICS if g == "Integration"])),
             ("cost", lambda: panels(out, models, "cost", "Compute per model",
                                     [k for k, *_, g in METRICS if g == "Cost"])),
             ("cost_quality", lambda: cost_quality(out, models))]
    for name, step in steps:
        try:
            step()
        except Exception as e:  # one figure with unexpected data must not cost the rest
            plt.close("all")
            out.skip(name, f"failed: {type(e).__name__}: {str(e)[:160]}")
    write_report(out, models, size, outputs, notes)
    print(f"  report.md, report.html, model_metrics.csv in {out.folder}")


if __name__ == "__main__":
    main()
