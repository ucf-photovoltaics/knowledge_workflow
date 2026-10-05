"""Paper figures from the evaluation tables and run folders.

  python -m src.figures                                   # current workflow revision -> outputs/figures/<revision>/
  python -m src.figures --revision REV --profile ollama   # another revision, one profile
  python -m src.figures --runs ID ID ... --out DIR        # explicit runs
  python -m src.figures --outputs DIR                     # runs kept in another outputs folder

Reads outputs/eval_runs.csv (row_type=run), outputs/eval_integrations.csv and each run's folder. Only runs of one
workflow revision and one profile are plotted together. Each figure is written as PDF (for LaTeX) and PNG with the
plotted numbers as CSV beside it; index.md lists every figure and its data source. A figure whose data is missing
is skipped and listed as skipped."""
import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src import config  # noqa: E402

# Fixed colour per domain (never by rank) plus a marker as secondary encoding. Palette validated (light surface).
DOMAINS = {"tea": ("Techno-economic", "#2a78d6", "o"), "reliability": ("Reliability", "#eb6834", "s"),
           "si-topcon": ("Si-TOPCon", "#1baf7a", "^"), "si-perc": ("Si-PERC", "#eda100", "D")}
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]  # categorical, fixed order
COVERAGE = ["#2a78d6", "#1baf7a", "#eb6834"]  # answered first, recovered, missing
EVIDENCE = ["#1c5cab", "#3987e5", "#86b6ef"]  # ordinal: verified, unverified, unevidenced
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
AGENTS = ("extraction", "normalization", "ontology", "enrichment", "interoperability")
KINDS = (("concepts", "Concepts"), ("relations", "Relations"), ("causal", "Causal claims"),
         ("measurements", "Reported values"))

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5, "axes.edgecolor": INK2, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "lines.linewidth": 1.5, "lines.markersize": 6, "legend.frameon": False, "savefig.bbox": "tight",
    "figure.facecolor": "white", "axes.facecolor": "white", "pdf.fonttype": 42,
})


# ---------------------------------------------------------------- data

def _csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def num(v, default=0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


def label(domain: str) -> str:
    return DOMAINS.get(domain, (domain,))[0]


def load_runs(outputs: Path, revision: str, profile: str | None, run_ids: list[str] | None) -> tuple[list[dict], list[str]]:
    notes = []
    rows = [r for r in _csv(outputs / "eval_runs.csv") if r.get("row_type", "run") in ("run", "")]
    if run_ids:
        rows = [r for r in rows if r["run_id"] in run_ids]
    else:
        rows = [r for r in rows if r.get("workflow_revision") == revision and r.get("collection") in DOMAINS]
        profiles = Counter(r.get("llm_profile") for r in rows)
        if profile:
            rows = [r for r in rows if r.get("llm_profile") == profile]
        elif len(profiles) > 1:
            keep = profiles.most_common(1)[0][0]
            notes.append(f"runs from several profiles {dict(profiles)}; plotted only '{keep}' (use --profile)")
            rows = [r for r in rows if r.get("llm_profile") == keep]
    for r in rows:
        r["_dir"] = outputs / r["run_id"]
    return [r for r in rows if r["_dir"].exists()], notes


def largest(rows: list[dict], needs: str) -> dict[str, dict]:
    """Per domain, the run with the most papers that has the given artifact."""
    best = {}
    for r in rows:
        if not (r["_dir"] / needs).exists():
            continue
        d = r.get("collection")
        rank = lambda x: ("interop" in (x.get("stages_completed") or ""), num(x.get("papers_processed")),
                          len((x.get("stages_completed") or "").split("+")))  # finished runs first, then the largest
        if d not in best or rank(r) > rank(best[d]):
            best[d] = r
    return {d: best[d] for d in DOMAINS if d in best}


def paper_order(run_dir: Path) -> list[str]:
    """Processed papers in selection order (citation rank)."""
    processed = {p.stem for p in (run_dir / "papers").glob("*.json")}
    manifest = _json(run_dir / "run.json") or {}
    ranked = [s["key"] for s in manifest.get("corpus", {}).get("selection", {}).get("selected", [])]
    return [k for k in ranked if k in processed] + sorted(processed - set(ranked))


def cumulative(order: list[str], first_papers: list[set]) -> np.ndarray:
    """Distinct items seen after each paper: an item counts from its earliest paper in this order."""
    pos = {k: i for i, k in enumerate(order)}
    firsts = [min(pos[k] for k in ps if k in pos) for ps in first_papers if any(k in pos for k in ps)]
    return np.cumsum(np.bincount(firsts, minlength=len(order)))


# ---------------------------------------------------------------- output

class Out:
    def __init__(self, folder: Path):
        self.folder, self.index, self.skipped, self.tables = folder, [], [], {}
        folder.mkdir(parents=True, exist_ok=True)

    def save(self, fig, name: str, title: str, source: str, table: list[dict]):
        fig.savefig(self.folder / f"{name}.pdf")
        fig.savefig(self.folder / f"{name}.png", dpi=220)
        plt.close(fig)
        if table:
            with (self.folder / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for row in table for k in row)))
                w.writeheader()
                w.writerows(table)
        self.index.append((name, title, source))
        self.tables[name] = table
        print(f"  {name}.pdf/.png  {title}")

    def skip(self, name: str, why: str):
        self.skipped.append((name, why))
        print(f"  skipped {name}: {why}")


def direct_labels(ax, ends: list[tuple[float, float, str, str]]):
    """Labels at line ends, nudged apart vertically so they do not collide."""
    if not ends:
        return
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * 0.065
    placed = []
    for x, y, text, color in sorted(ends, key=lambda e: e[1]):
        while any(abs(y - p) < gap for p in placed):
            y += gap
        placed.append(y)
        ax.annotate(text, (x, y), xytext=(4, 0), textcoords="offset points", va="center", fontsize=7.5, color=INK)


def stacked_barh(ax, labels: list[str], series: list[tuple[str, str, list[float]]], share: bool, frame=None):
    """Horizontal stacked bars with a 2px white gap between segments; optional outlined 100% frame."""
    y = np.arange(len(labels))
    left = np.zeros(len(labels))
    for name, color, values in series:
        v = np.array(values, dtype=float)
        ax.barh(y, v, left=left, color=color, edgecolor="white", linewidth=1.0, height=0.62, label=name)
        for i, (l, w) in enumerate(zip(left, v)):
            if share and w >= 0.08 and l + w <= 1.001:
                ax.text(l + w / 2, i, f"{w:.0%}", ha="center", va="center", fontsize=6.5,
                        color="white" if color in (EVIDENCE[0], SLOTS[0], SLOTS[5], SLOTS[6], BLUES[5]) else INK)
        left += v
    if frame is not None:
        ax.barh(y, frame, left=0, fill=False, edgecolor=INK2, linewidth=0.6, height=0.62, zorder=0)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    if share:
        ax.set_xlim(0, 1)
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))


# ---------------------------------------------------------------- figures

def fig_concept_growth(out: Out, rows: list[dict], permutations: int = 200):
    runs = largest(rows, "normalized/concepts.json")
    if not runs:
        return out.skip("concept_growth", "no run with normalized/concepts.json")
    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    table, ends, rng = [], [], random.Random(13)
    for d, r in runs.items():
        order = paper_order(r["_dir"])
        concepts = _json(r["_dir"] / "normalized/concepts.json") or []
        sets = [set(c.get("papers", [])) for c in concepts]
        y = cumulative(order, sets)
        x = np.arange(1, len(order) + 1)
        perms = np.array([cumulative(rng.sample(order, len(order)), sets) for _ in range(permutations)])
        name, color, marker = DOMAINS[d]
        ax.fill_between(x, np.percentile(perms, 5, axis=0), np.percentile(perms, 95, axis=0), color=color,
                        alpha=0.15, linewidth=0)
        ax.plot(x, y, color=color, label=name)
        ax.plot(x[-1], y[-1], marker=marker, color=color, markeredgecolor="white", markeredgewidth=1.0)
        ends.append((x[-1], y[-1], name, color))
        table += [{"domain": d, "run_id": r["run_id"], "papers": int(i), "canonical_concepts_citation_order": int(v),
                   "random_order_p5": float(np.percentile(perms[:, i - 1], 5)),
                   "random_order_mean": float(perms[:, i - 1].mean()),
                   "random_order_p95": float(np.percentile(perms[:, i - 1], 95))} for i, v in zip(x, y)]
    ax.set_xlabel("Papers processed (citation order)")
    ax.set_ylabel("Distinct canonical concepts")
    ax.set_ylim(bottom=0)
    ax.set_xlim(left=1, right=ax.get_xlim()[1] * 1.18)
    direct_labels(ax, ends)
    if len(runs) > 1:
        ax.legend(loc="upper left")
    out.save(fig, "concept_growth", "Distinct canonical concepts as papers are added (line: citation order; band: "
             f"5-95% of {permutations} random paper orders)", "normalized/concepts.json papers lists; run.json selection order",
             table)


def fig_knowledge_growth(out: Out, rows: list[dict]):
    runs = largest(rows, "normalized/relations.json")
    if not runs:
        return out.skip("knowledge_growth", "no run with normalized relations")
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.6))
    table = []
    for ax, (kind, title) in zip(axes.flat, KINDS):
        ends = []
        for d, r in runs.items():
            order = paper_order(r["_dir"])
            if kind == "measurements":
                vals = _json(r["_dir"] / "normalized/measurements.json") or []
                per = Counter(m.get("paper") for m in vals)
                y = np.cumsum([per.get(k, 0) for k in order])
            else:
                items = _json(r["_dir"] / f"normalized/{kind}.json") or []
                y = cumulative(order, [set(i.get("papers", [])) for i in items])
            x = np.arange(1, len(order) + 1)
            name, color, marker = DOMAINS[d]
            ax.plot(x, y, color=color, label=name)
            ax.plot(x[-1], y[-1], marker=marker, color=color, markeredgecolor="white", markeredgewidth=1.0)
            ends.append((x[-1], y[-1], name, color))
            table += [{"panel": kind, "domain": d, "run_id": r["run_id"], "papers": int(i), "cumulative": int(v)}
                      for i, v in zip(x, y)]
        ax.set_title(title, loc="left")
        ax.set_ylim(bottom=0)
        ax.set_xlim(left=1, right=ax.get_xlim()[1] * 1.2)
        direct_labels(ax, ends)
    for ax in axes[1]:
        ax.set_xlabel("Papers processed (citation order)")
    axes[0][0].set_ylabel("Distinct (canonical)")
    axes[1][0].set_ylabel("Count")
    if len(runs) > 1:
        axes[0][0].legend(loc="upper left")
    fig.tight_layout()
    out.save(fig, "knowledge_growth", "Cumulative distinct concepts, relations and causal claims, and reported values, "
             "as papers are added", "normalized/{concepts,relations,causal,measurements}.json", table)


def fig_scaling(out: Out, rows: list[dict]):
    pts = defaultdict(list)
    for r in rows:
        if num(r.get("canonical_concepts")) and r.get("collection") in DOMAINS:
            pts[r["collection"]].append(r)
    if not any(len(v) > 1 for v in pts.values()):
        return out.skip("scaling_runs", "needs two or more runs of different sizes for a domain")
    panels = (("canonical_concepts", "Canonical concepts"), ("final_classes", "Ontology classes"),
              ("share_concepts_2plus_papers", "Concepts in 2+ papers"))
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.4))
    table = []
    for ax, (col, title) in zip(axes, panels):
        for d in DOMAINS:
            if d not in pts:
                continue
            by_n = defaultdict(list)
            for r in pts[d]:
                if r.get(col) not in (None, ""):
                    by_n[int(num(r.get("papers_processed")))].append(num(r[col]))
            if not by_n:
                continue
            xs = sorted(by_n)
            ys = [float(np.mean(by_n[n])) for n in xs]
            name, color, marker = DOMAINS[d]
            ax.plot(xs, ys, color=color, marker=marker, markeredgecolor="white", markeredgewidth=1.0, label=name)
            table += [{"panel": col, "domain": d, "papers": n, "mean": float(np.mean(by_n[n])), "runs": len(by_n[n])}
                      for n in xs]
        ax.set_title(title, loc="left")
        ax.set_xlabel("Papers per run")
        ax.set_ylim(bottom=0)
        if col.startswith("share"):
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    axes[0].legend(loc="upper left")
    fig.tight_layout()
    out.save(fig, "scaling_runs", "Separate runs of increasing size: canonical concepts, ontology classes and the share "
             "of concepts found in two or more papers", "eval_runs.csv", table)


def fig_per_paper_yield(out: Out, rows: list[dict]):
    runs = largest(rows, "papers")
    if not runs:
        return out.skip("per_paper_yield", "no run with paper records")
    fig, axes = plt.subplots(1, 4, figsize=(7.0, 2.4))
    table = []
    data = {d: [_json(p) or {} for p in sorted((r["_dir"] / "papers").glob("*.json"))] for d, r in runs.items()}
    for ax, (kind, title) in zip(axes, KINDS):
        vals = [[len(p.get(kind, [])) for p in data[d]] for d in runs]
        bp = ax.boxplot(vals, widths=0.5, patch_artist=True, showfliers=False,
                        medianprops={"color": INK, "linewidth": 1.2}, whiskerprops={"color": INK2, "linewidth": 0.8},
                        capprops={"color": INK2, "linewidth": 0.8}, boxprops={"linewidth": 0.8, "edgecolor": INK2})
        for patch, d in zip(bp["boxes"], runs):
            patch.set_facecolor(DOMAINS[d][1])
            patch.set_alpha(0.35)
        for i, (d, v) in enumerate(zip(runs, vals), 1):
            jitter = np.random.default_rng(i).uniform(-0.12, 0.12, len(v))
            ax.scatter(np.full(len(v), i) + jitter, v, s=12, color=DOMAINS[d][1], edgecolor="white", linewidth=0.5,
                       zorder=3, marker=DOMAINS[d][2])
            table += [{"panel": kind, "domain": d, "paper": p.get("key"), "count": n} for p, n in zip(data[d], v)]
        ax.set_xticks(range(1, len(runs) + 1), [label(d) for d in runs], rotation=30, ha="right")
        ax.set_title(title, loc="left")
        ax.grid(axis="x", visible=False)
        ax.set_ylim(bottom=0)
    axes[0].set_ylabel("Per paper")
    fig.tight_layout()
    out.save(fig, "per_paper_yield", "Items extracted per paper, by domain (box: quartiles; dots: papers)",
             "papers/*.json", table)


def fig_evidence(out: Out, rows: list[dict]):
    runs = largest(rows, "papers")
    labels, series, table = [], [[], [], []], []
    for d, r in runs.items():
        papers = [_json(p) or {} for p in (r["_dir"] / "papers").glob("*.json")]
        for kind in ("relations", "causal", "measurements"):
            n = sum(p.get("verification", {}).get(kind, {}).get("items", 0) for p in papers)
            if not n:
                continue
            ver = sum(p.get("verification", {}).get(kind, {}).get("verified", 0) for p in papers)
            une = sum(p.get("verification", {}).get(kind, {}).get("unevidenced", 0) for p in papers)
            labels.append(f"{label(d)} · {dict(KINDS)[kind].lower()}")
            for s, v in zip(series, (ver / n, (n - ver - une) / n, une / n)):
                s.append(v)
            table.append({"domain": d, "run_id": r["run_id"], "kind": kind, "items": n, "verified": ver,
                          "unverified": n - ver - une, "unevidenced": une})
    if not labels:
        return out.skip("evidence_status", "no verification counts in paper records")
    fig, ax = plt.subplots(figsize=(7.0, 0.32 * len(labels) + 0.9))
    stacked_barh(ax, labels, [("Verified", EVIDENCE[0], series[0]), ("Unverified", EVIDENCE[1], series[1]),
                              ("Unevidenced", EVIDENCE[2], series[2])], share=True)
    ax.set_xlabel("Share of extracted items")
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    out.save(fig, "evidence_status", "Evidence status of extracted relations, causal claims and reported values "
             "(verified: quote found in the paper; unevidenced: no usable quote after one re-ask)", "papers/*.json "
             "verification", table)


def fig_row_coverage(out: Out, rows: list[dict]):
    runs = largest(rows, "run.json")
    passes = defaultdict(lambda: [0.0, 0.0, 0.0])
    for r in runs.values():
        for k, v in r.items():
            if k.endswith("_rows") and v not in ("", None):
                name = k[:-5]
                rec, miss = num(r.get(f"{name}_rows_recovered")), num(r.get(f"{name}_rows_missing_after_retry"))
                passes[name][0] += num(v) - rec - miss
                passes[name][1] += rec
                passes[name][2] += miss
    passes = {k: v for k, v in passes.items() if sum(v)}
    if not passes:
        return out.skip("row_coverage", "no row-coverage columns (runs before revision 2026-10-04)")
    names = list(passes)
    shares = [[passes[n][i] / sum(passes[n]) for n in names] for i in range(3)]
    fig, ax = plt.subplots(figsize=(7.0, 0.3 * len(names) + 0.9))
    stacked_barh(ax, [n.replace("_", " ") for n in names],
                 [("Answered first", COVERAGE[0], shares[0]), ("Recovered by retry", COVERAGE[1], shares[1]),
                  ("Still missing", COVERAGE[2], shares[2])], share=True)
    ax.set_xlabel(f"Share of rows sent (pooled over {', '.join(label(d) for d in runs)})")
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    out.save(fig, "row_coverage", "Rows answered by the model per pass: first attempt, recovered by the retry, still "
             "missing (missing rows fall back to defaults)", "eval_runs.csv <pass>_rows*",
             [{"pass": n, "answered_first": passes[n][0], "recovered": passes[n][1], "missing": passes[n][2]}
              for n in names])


def _domain_shares(out, rows, name, title, source, cols, prefix, total_col=None, frame=False, colors=None):
    runs = largest(rows, "run.json")
    present = [(c, t) for c, t in cols if any(num(r.get(f"{prefix}{c}")) for r in runs.values())]
    if not present:
        return out.skip(name, f"no {prefix}* columns")
    labels, series, table = [label(d) for d in runs], [], []
    cols_total = [total_col] if isinstance(total_col, str) else list(total_col or [])
    totals = {d: next((num(r.get(t)) for t in cols_total if num(r.get(t))), 0)
              or sum(num(r.get(f"{prefix}{c}")) for c, _ in present) or 1 for d, r in runs.items()}
    for c, t in present:  # colour follows the category's fixed slot, not its position among those present
        series.append((t, (colors or SLOTS)[[k for k, _ in cols].index(c)], [num(r.get(f"{prefix}{c}")) / totals[d] for d, r in runs.items()]))
    for d, r in runs.items():
        table.append({"domain": d, "run_id": r["run_id"], "total": totals[d],
                      **{c: num(r.get(f"{prefix}{c}")) for c, _ in present}})
    fig, ax = plt.subplots(figsize=(7.0, 0.36 * len(labels) + 1.0))
    stacked_barh(ax, labels, series, share=True, frame=np.ones(len(labels)) if frame else None)
    ax.legend(ncol=min(len(present), 4), loc="lower left", bbox_to_anchor=(0, 1.0))
    out.save(fig, name, title, source, table)
    return ax


def fig_placement(out, rows):
    _domain_shares(out, rows, "placement_sources", "Where each class's parent came from",
                   "eval_runs.csv placement_*", [("llm", "Model choice"), ("paper_is_a", "Paper is-a"),
                                                 ("lexical_head", "Lexical head"), ("category_default", "Category root (no usable answer)"),
                                                 ("type_default", "Type default"), ("cycle_break", "Cycle break"),
                                                 ("name_match", "Same-name MDS-Onto/PMDCO class")], "placement_")


def fig_definitions(out, rows):
    _domain_shares(out, rows, "definitions_status", "Definitions by status, as a share of classes (not answered: row "
                   "still missing after the retry)", "eval_runs.csv definitions_*, final_classes",
                   [("supported", "Supported by a paper definition"), ("draft_evidence", "Draft from evidence"),
                    ("model_generated", "Model generated"), ("imported", "Imported from a matched term"),
                    ("unreviewed", "Not answered"), ("none", "No definition")], "definitions_", total_col="final_classes",
                   frame=True, colors=[SLOTS[0], SLOTS[1], SLOTS[2], SLOTS[6], SLOTS[3], "#d9d8d3"])


def fig_restrictions(out: Out, rows: list[dict]):
    runs = largest(rows, "ontology/enriched.json")
    if not runs:
        return out.skip("restriction_sources", "no enriched.json")
    cats = ["Causal (local polarity)", "Causal (RO)", "Causal (CCO)", "Relation (extracted predicate)", "Relation (model)"]
    counts, table = {}, []
    for d, r in runs.items():
        c = Counter()
        for cls in _json(r["_dir"] / "ontology/enriched.json") or []:
            for x in cls.get("restrictions", []):
                if x.get("kind") == "causal":
                    p = str(x.get("p", ""))
                    c[cats[0] if p.startswith("local:") else cats[2] if "commoncoreontologies" in p else cats[1]] += 1
                else:
                    c[cats[3] if x.get("source") == "extracted_predicate" else cats[4]] += 1
        counts[d] = c
        table.append({"domain": d, "run_id": r["run_id"], **{k: c[k] for k in cats}})
    fig, ax = plt.subplots(figsize=(7.0, 0.36 * len(runs) + 1.0))
    used = [k for k in cats if any(counts[d][k] for d in runs)]  # colour stays with the category, not its position
    stacked_barh(ax, [label(d) for d in runs], [(k, SLOTS[cats.index(k)], [counts[d][k] for d in runs]) for k in used],
                 share=False)
    ax.set_xlabel("Restrictions")
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    out.save(fig, "restriction_sources", "Restrictions by source: causal claims (local, RO, CCO properties) and "
             "relations (formalized from the extracted predicate, or chosen by the model)", "ontology/enriched.json", table)


def fig_mappings(out: Out, rows: list[dict]):
    runs = largest(rows, "ontology/mappings.json")
    if not runs:
        return out.skip("external_mappings", "no ontology/mappings.json")
    rank = ["equivalent", "exact", "subclass", "broader", "close", "narrower", "related"]
    names = {"equivalent": "Equivalent class", "exact": "Exact match", "subclass": "Subclass of", "broader": "Broader match",
             "close": "Close match", "narrower": "Narrower match", "related": "Related match"}
    series = {k: [] for k in rank}
    table = []
    for d, r in runs.items():
        best = {}
        for m in _json(r["_dir"] / "ontology/mappings.json") or []:
            if m.get("relation") in rank:
                cur = best.get(m["id"])
                best[m["id"]] = m["relation"] if cur is None or rank.index(m["relation"]) < rank.index(cur) else cur
        classes = num(r.get("final_classes")) or len(best) or 1
        c = Counter(best.values())
        for k in rank:
            series[k].append(c[k] / classes)
        table.append({"domain": d, "run_id": r["run_id"], "classes": classes, **{k: c[k] for k in rank},
                      "unmapped": classes - sum(c.values())})
    fig, ax = plt.subplots(figsize=(7.0, 0.36 * len(runs) + 1.0))
    used = [k for k in rank if any(series[k])]  # colour stays with the relation's slot
    stacked_barh(ax, [label(d) for d in runs], [(names[k], SLOTS[rank.index(k)], series[k]) for k in used],
                 share=True, frame=np.ones(len(runs)))
    ax.set_xlabel("Share of classes, by strongest external mapping (empty remainder: unmapped)")
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0))
    out.save(fig, "external_mappings", "Classes mapped to external ontologies (ontology store and MDS-Onto portal), by "
             "strongest mapping", "ontology/mappings.json", table)


def fig_compute(out: Out, rows: list[dict]):
    runs = largest(rows, "run.json")
    if not runs:
        return out.skip("compute_by_stage", "no runs")
    labels = [label(d) for d in runs]
    tokens = [(a, SLOTS[i], [(num(r.get(f"{a}_input_tokens")) + num(r.get(f"{a}_output_tokens"))) / 1e3 for r in runs.values()])
              for i, a in enumerate(AGENTS)]
    wall = [(a, SLOTS[i], [num(r.get(f"{a}_wall_s")) / 60 for r in runs.values()]) for i, a in enumerate(AGENTS)]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 0.36 * len(labels) + 1.3))
    stacked_barh(axes[0], labels, tokens, share=False)
    stacked_barh(axes[1], labels, wall, share=False)
    axes[1].set_yticklabels([])
    axes[0].set_xlabel("Tokens (thousands)")
    axes[1].set_xlabel("Wall time (minutes)")
    fig.legend(*axes[0].get_legend_handles_labels(), ncol=5, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    papers = ", ".join(f"{label(d)} {int(num(r.get('papers_processed')))}" for d, r in runs.items())
    fig.tight_layout()
    out.save(fig, "compute_by_stage", f"Tokens and wall time per stage (papers: {papers}); cached extractions cost no "
             "tokens", "eval_runs.csv <agent>_input_tokens, _output_tokens, _wall_s",
             [{"domain": d, "run_id": r["run_id"], "papers": r.get("papers_processed"),
               **{f"{a}_tokens": num(r.get(f"{a}_input_tokens")) + num(r.get(f"{a}_output_tokens")) for a in AGENTS},
               **{f"{a}_wall_s": num(r.get(f"{a}_wall_s")) for a in AGENTS}} for d, r in runs.items()])


def fig_integration(out: Out, outputs: Path, rows_runs: list[dict], revision: str, run_ids):
    ints = [r for r in _csv(outputs / "eval_integrations.csv") if r.get("row_type") == "integration"]
    if run_ids:  # only integrations built from the given runs
        ints = [r for r in ints if set(filter(None, r.get("input_runs", "").split("+"))) <= set(run_ids)]
    else:
        ints = [r for r in ints if r.get("workflow_revision") == revision]
    ints = [r for r in ints if (outputs / r["run_id"] / "mappings.json").exists()]
    if not ints:
        return out.skip("integration", "no integration at this revision")
    papers = {r["run_id"]: num(r.get("papers_processed")) for r in _csv(outputs / "eval_runs.csv")
              if r.get("row_type") == "run"}  # inputs may come from older revisions
    latest = max(ints, key=lambda r: r.get("created", ""))
    folder = outputs / latest["run_id"]
    maps = _json(folder / "mappings.json") or []
    bridges = _json(folder / "bridge_concepts.json") or []
    doms = [d for d in DOMAINS if d in latest.get("domains", "").split("+")]
    m = np.zeros((len(doms), len(doms)))
    for x in maps:
        if x["a_domain"] in doms and x["b_domain"] in doms and x["relation"] != "shared_iri":
            i, j = doms.index(x["a_domain"]), doms.index(x["b_domain"])
            m[i, j] += 1
            m[j, i] += 1
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.5), gridspec_kw={"width_ratios": [1.15, 1, 1]})
    ax = axes[0]
    cmap = matplotlib.colors.ListedColormap(BLUES)
    im = ax.imshow(np.where(np.eye(len(doms)) == 1, np.nan, m), cmap=cmap, vmin=0)
    for i in range(len(doms)):
        for j in range(len(doms)):
            if i != j:
                ax.text(j, i, int(m[i, j]), ha="center", va="center", fontsize=7.5,
                        color="white" if m[i, j] > 0.6 * max(m.max(), 1) else INK)
    ax.set_xticks(range(len(doms)), [label(d) for d in doms], rotation=30, ha="right")
    ax.set_yticks(range(len(doms)), [label(d) for d in doms])
    ax.grid(False)
    ax.set_title("Mappings per domain pair", loc="left")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax = axes[1]
    rel_order = ["equivalent", "exact", "close", "broader", "narrower"]
    rc = Counter(x["relation"] for x in maps)
    ax.bar(range(len(rel_order)), [rc[k] for k in rel_order], color=SLOTS[0], edgecolor="white", linewidth=1.0, width=0.62)
    ax.set_xticks(range(len(rel_order)), rel_order, rotation=30, ha="right")
    ax.set_title("Mappings by relation", loc="left")
    ax.grid(axis="x", visible=False)
    ax = axes[2]
    series = []
    ordered = sorted(ints, key=lambda r: r.get("created", ""))
    for r in ordered:
        per = [papers.get(k, 0) for k in r.get("input_runs", "").split("+") if k]
        if per:
            series.append((min(per), num(r.get("bridge_concepts")), r["run_id"]))
    repeats = len(ordered) > 1 and len({r.get("input_runs") for r in ordered}) == 1
    if repeats:  # the same inputs integrated several times: run-to-run spread of a nondeterministic stage
        xs = np.arange(1, len(ordered) + 1)
        for k, (col, name) in enumerate((("mappings_total", "Mappings"), ("bridge_concepts", "Bridge concepts"))):
            ys = [num(r.get(col)) for r in ordered]
            ax.plot(xs, ys, color=SLOTS[k], marker="o", markeredgecolor="white", markeredgewidth=1.0, linewidth=0, label=name)
            ax.axhline(np.mean(ys), color=SLOTS[k], linewidth=0.8, linestyle="--")
            ax.text(xs[-1] + 0.3, np.mean(ys), f"{name}\n{min(ys):.0f}-{max(ys):.0f}", va="center", fontsize=6.5, color=INK2)
        ax.set_xticks(xs)
        ax.set_xlim(0.5, len(xs) + 2.2)
        ax.set_xlabel("Repeat (same input runs)")
        ax.set_title("Repeat integrations", loc="left")
        series = [(i, num(r.get("bridge_concepts")), r["run_id"]) for i, r in zip(xs, ordered)]
    elif len(series) > 1:
        xs, ys = zip(*[(a, b) for a, b, _ in series])
        ax.plot(xs, ys, color=SLOTS[0], marker="o", markeredgecolor="white", markeredgewidth=1.0)
        ax.set_xlabel("Papers per domain")
        ax.set_title("Bridge concepts across runs", loc="left")
    else:
        nd = Counter(b["n_domains"] for b in bridges)
        ks = sorted(nd) or [2]
        ax.bar(range(len(ks)), [nd[k] for k in ks], color=SLOTS[0], edgecolor="white", linewidth=1.0, width=0.62)
        ax.set_xticks(range(len(ks)), [f"{k} domains" for k in ks])
        ax.set_title("Bridge concepts", loc="left")
        ax.grid(axis="x", visible=False)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    out.save(fig, "integration", f"Cross-domain integration {latest['run_id']}: mappings per domain pair, mappings by "
             "relation, and bridge concepts", "eval_integrations.csv; integration-*/mappings.json, bridge_concepts.json",
             [{"integration": latest["run_id"], "a": a, "b": b, "mappings": int(m[i, j])}
              for i, a in enumerate(doms) for j, b in enumerate(doms) if i < j]
             + [{"integration": latest["run_id"], "relation": k, "count": rc[k]} for k in rel_order]
             + [{"integration": rid, ("repeat" if repeats else "papers_per_domain"): x, "bridge_concepts": y}
                for x, y, rid in series])


# ---------------------------------------------------------------- stage detail

def grouped_barh(ax, cats: list[str], runs: dict, values: dict, fmt=None):
    """One bar per domain inside each category group; colour follows the domain."""
    n = len(runs)
    h = 0.8 / max(n, 1)
    y = np.arange(len(cats))
    for i, d in enumerate(runs):
        name, color, _ = DOMAINS[d]
        ax.barh(y - 0.4 + h * (i + 0.5), [values[d].get(c, 0) for c in cats], height=h * 0.92, color=color,
                edgecolor="white", linewidth=1.0, label=name)
    ax.set_yticks(y, cats)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    if fmt == "share":
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))


def top_categories(counts: dict[str, Counter], k: int = 7) -> list[str]:
    total = Counter()
    for c in counts.values():
        total.update(c)
    keep = [x for x, _ in total.most_common(k)]
    return keep + (["Other"] if len(total) > k else [])


def fold(c: Counter, keep: list[str]) -> Counter:
    out = Counter({k: c.get(k, 0) for k in keep if k != "Other"})
    if "Other" in keep:
        out["Other"] = sum(v for k, v in c.items() if k not in keep)
    return out


def share_figure(out, name, title, source, counts: dict[str, Counter], legend_cols=4, k=7):
    """Stacked share bars per domain over the k most common categories (rest folded into Other)."""
    runs = [d for d in counts if sum(counts[d].values())]
    if not runs:
        return out.skip(name, "no data")
    keep = top_categories({d: counts[d] for d in runs}, k)
    folded = {d: fold(counts[d], keep) for d in runs}
    series = [(c or "(none)", SLOTS[i], [folded[d][c] / (sum(folded[d].values()) or 1) for d in runs])
              for i, c in enumerate(keep)]
    fig, ax = plt.subplots(figsize=(7.0, 0.36 * len(runs) + 1.2))
    stacked_barh(ax, [label(d) for d in runs], series, share=True)
    ax.legend(ncol=legend_cols, loc="lower left", bbox_to_anchor=(0, 1.0))
    out.save(fig, name, title, source, [{"domain": d, **{c: folded[d][c] for c in keep}} for d in runs])


def fig_parsing(out: Out, rows: list[dict]):
    runs = largest(rows, "papers")
    if not runs:
        return out.skip("parsing", "no paper records")
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6))
    table = []
    for d, r in runs.items():
        papers = [_json(p) or {} for p in sorted((r["_dir"] / "papers").glob("*.json"))]
        ps = [p.get("parse_stats", {}) for p in papers]
        raw = np.array([x.get("chars_raw", 0) for x in ps]) / 1e3
        kept = np.array([x.get("chars_kept", 0) for x in ps]) / 1e3
        chunks = np.array([p.get("n_chunks", 0) for p in papers])
        name, color, marker = DOMAINS[d]
        axes[0].scatter(raw, kept, s=16, color=color, marker=marker, edgecolor="white", linewidth=0.5, label=name)
        conc = np.array([len(p.get("concepts", [])) for p in papers])
        axes[1].scatter(chunks, conc, s=16, color=color, marker=marker, edgecolor="white", linewidth=0.5, label=name)
        table += [{"domain": d, "paper": p.get("key"), "chars_raw": x.get("chars_raw"), "chars_kept": x.get("chars_kept"),
                   "chunks": p.get("n_chunks"), "concepts": len(p.get("concepts", []))} for p, x in zip(papers, ps)]
    lim = max(axes[0].get_xlim()[1], axes[0].get_ylim()[1])
    axes[0].plot([0, lim], [0, lim], color=INK2, linewidth=0.8, linestyle="--")
    axes[0].set_xlabel("Characters in PDF (thousands)")
    axes[0].set_ylabel("Characters kept (thousands)")
    axes[0].set_title("Parsing", loc="left")
    axes[1].set_xlabel("Sections sent to the model")
    axes[1].set_ylabel("Concepts extracted")
    axes[1].set_title("Extraction effort and yield", loc="left")
    axes[0].legend(loc="upper left")
    for ax in axes:
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)
    fig.tight_layout()
    out.save(fig, "parsing", "Per paper: characters kept after removing references and running headers (dashed: "
             "nothing removed), and concepts extracted against sections sent to the model", "papers/*.json parse_stats",
             table)


def fig_extraction_checks(out: Out, rows: list[dict]):
    runs = largest(rows, "papers")
    checks = {"extraction_check_evidence_asked": "Quotes re-asked", "extraction_check_evidence_filled": "Quotes filled by re-ask",
              "extraction_check_new_concepts_by_pass_relations": "Concepts added by relations pass",
              "extraction_check_new_concepts_by_pass_causal": "Concepts added by causal pass",
              "extraction_check_new_concepts_by_pass_measurements": "Concepts added by measurements pass",
              "extraction_check_measurements_on_non_property": "Values not on a property",
              "extraction_check_measurements_property_missing": "Values missing their property",
              "extraction_check_pairs_both_relation_and_causal": "Pairs both relation and causal"}
    present = [k for k in checks if any(num(r.get(k)) for r in runs.values())]
    if not present:
        return out.skip("extraction_checks", "no extraction check columns")
    values = {d: {checks[k]: num(r.get(k)) / max(num(r.get("papers_processed")), 1) for k in present} for d, r in runs.items()}
    fig, ax = plt.subplots(figsize=(7.0, 0.42 * len(present) * max(len(runs), 1) ** 0.5 + 1.0))
    grouped_barh(ax, [checks[k] for k in present], runs, values)
    ax.set_xlabel("Per paper")
    ax.legend(ncol=len(runs), loc="lower left", bbox_to_anchor=(0, 1.0))
    out.save(fig, "extraction_checks", "Extraction checks per paper: quotes re-asked and filled, concepts added by later "
             "passes, values without a property", "eval_runs.csv extraction_check_*",
             [{"domain": d, **values[d]} for d in runs])


def fig_normalization(out: Out, rows: list[dict]):
    runs = largest(rows, "normalized/concepts.json")
    if not runs:
        return out.skip("normalization", "no normalized runs")
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))
    stages = [("concept_occurrences", "Occurrences"), ("lexical_groups", "Lexical groups"),
              ("canonical_concepts", "Canonical concepts")]
    vals = {d: {t: num(r.get(c)) for c, t in stages} for d, r in runs.items()}
    grouped_barh(axes[0], [t for _, t in stages], runs, vals)
    axes[0].set_xlabel("Count")
    axes[0].set_title("From occurrences to concepts", loc="left")
    merges = [("embedding_candidate_clusters", "Look-alike clusters"), ("semantic_merges", "Merges accepted"),
              ("type_conflicts", "Type conflicts"), ("types_settled_by_model", "Types settled"),
              ("causal_contradictions", "Causal contradictions")]
    mv = {d: {t: num(r.get(c)) for c, t in merges} for d, r in runs.items()}
    grouped_barh(axes[1], [t for _, t in merges], runs, mv)
    axes[1].set_xlabel("Count")
    axes[1].set_title("Merge and conflict decisions", loc="left")
    fig.tight_layout()
    fig.legend(*axes[0].get_legend_handles_labels(), ncol=len(runs), loc="lower center", bbox_to_anchor=(0.5, 1.0))
    out.save(fig, "normalization", "Normalization: concept occurrences, lexical groups and canonical concepts; "
             "embedding look-alike clusters, merges the model accepted, type conflicts and causal contradictions",
             "eval_runs.csv", [{"domain": d, **vals[d], **mv[d]} for d in runs])


def fig_concept_support(out: Out, rows: list[dict]):
    runs = largest(rows, "normalized/concepts.json")
    if not runs:
        return out.skip("concept_support", "no normalized concepts")
    bins = ["1", "2", "3", "4", "5+"]
    vals, table = {}, []
    for d, r in runs.items():
        cs = _json(r["_dir"] / "normalized/concepts.json") or []
        c = Counter(str(min(int(x.get("n_papers", 1) or 1), 5)).replace("5", "5+") for x in cs)
        vals[d] = {b: c.get(b, 0) / (len(cs) or 1) for b in bins}
        table.append({"domain": d, "concepts": len(cs), **{b: c.get(b, 0) for b in bins}})
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    n = len(runs)
    w = 0.8 / n
    for i, d in enumerate(runs):
        name, color, _ = DOMAINS[d]
        ax.bar(np.arange(len(bins)) - 0.4 + w * (i + 0.5), [vals[d][b] for b in bins], width=w * 0.92, color=color,
               edgecolor="white", linewidth=1.0, label=name)
    ax.set_xticks(range(len(bins)), bins)
    ax.set_xlabel("Papers a concept appears in")
    ax.set_ylabel("Share of canonical concepts")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.grid(axis="x", visible=False)
    ax.legend()
    out.save(fig, "concept_support", "How many papers each canonical concept appears in", "normalized/concepts.json", table)


def fig_concept_types(out, rows):
    runs = largest(rows, "normalized/concepts.json")
    share_figure(out, "concept_types", "Canonical concepts by type", "normalized/concepts.json",
                 {d: Counter(c.get("type") or "(untyped)" for c in _json(r["_dir"] / "normalized/concepts.json") or [])
                  for d, r in runs.items()})


def fig_causal_polarity(out, rows):
    runs = largest(rows, "normalized/causal.json")
    share_figure(out, "causal_polarity", "Causal claims by polarity", "normalized/causal.json",
                 {d: Counter(c.get("polarity") for c in _json(r["_dir"] / "normalized/causal.json") or [])
                  for d, r in runs.items()}, legend_cols=6)


def heatmap(ax, rows_labels, cols_labels, m, fmt="{:.0%}"):
    cmap = matplotlib.colors.ListedColormap(BLUES)
    im = ax.imshow(m, cmap=cmap, vmin=0, aspect="auto")
    top = m.max() if m.size else 1
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            if m[i, j]:
                ax.text(j, i, fmt.format(m[i, j]), ha="center", va="center", fontsize=6.5,
                        color="white" if m[i, j] > 0.6 * top else INK)
    ax.set_xticks(range(len(cols_labels)), cols_labels, rotation=35, ha="right")
    ax.set_yticks(range(len(rows_labels)), rows_labels)
    ax.grid(False)
    return im


def fig_relation_predicates(out: Out, rows: list[dict]):
    runs = largest(rows, "normalized/relations.json")
    counts = {d: Counter(x.get("p") for x in _json(r["_dir"] / "normalized/relations.json") or []) for d, r in runs.items()}
    counts = {d: c for d, c in counts.items() if c}
    if not counts:
        return out.skip("relation_predicates", "no relations")
    keep = [k for k in top_categories(counts, 14) if k != "Other"]
    m = np.array([[counts[d].get(k, 0) / sum(counts[d].values()) for k in keep] for d in counts])
    fig, ax = plt.subplots(figsize=(7.0, 0.4 * len(counts) + 1.6))
    im = heatmap(ax, [label(d) for d in counts], [k.replace("_", " ") for k in keep], m)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, format=matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("Share of each domain's relations, by predicate", loc="left")
    out.save(fig, "relation_predicates", "Extracted relation predicates (RO/BFO/CCO-grounded and is-a), share per domain",
             "normalized/relations.json", [{"domain": d, **{k: counts[d].get(k, 0) for k in keep}} for d in counts])


def _classes(r):
    classes = _json(r["_dir"] / "ontology/enriched.json") or _json(r["_dir"] / "ontology/classes.json") or []
    return classes, {c["id"]: c for c in classes}


def fig_bfo_categories(out, rows):
    from src.tools import owl
    runs = largest(rows, "ontology/classes.json")
    counts = {}
    for d, r in runs.items():
        classes, by_id = _classes(r)
        counts[d] = Counter(owl.bfo_category(c["id"], by_id) for c in classes if not c.get("excluded"))
    share_figure(out, "bfo_categories", "Ontology classes by BFO category", "ontology/classes.json, BFO/CCO ancestors",
                 counts)


def fig_hierarchy(out: Out, rows: list[dict]):
    from src.tools import owl
    runs = largest(rows, "ontology/classes.json")
    if not runs:
        return out.skip("hierarchy_depth", "no ontology classes")
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.5))
    table = []
    data = {}
    for d, r in runs.items():
        classes, by_id = _classes(r)
        live = {c["id"]: c for c in classes if not c.get("excluded")}
        bfo, local = [], []
        for cid in live:
            lin = owl.lineage(cid, live)
            bfo.append(len(lin))
            local.append(sum(1 for a in lin if a in live))
        data[d] = (bfo, local)
        table.append({"domain": d, "classes": len(live), "mean_depth_to_bfo": float(np.mean(bfo)) if bfo else 0,
                      "max_depth_to_bfo": max(bfo, default=0), "classes_with_local_parent": sum(1 for x in local if x),
                      "max_local_depth": max(local, default=0)})
    for ax, idx, title in ((axes[0], 0, "Levels up to BFO entity"), (axes[1], 1, "Corpus classes above it")):
        top = max((max(data[d][idx], default=0) for d in runs), default=0)
        levels = np.arange(0, top + 1)
        w = 0.8 / max(len(runs), 1)
        for i, d in enumerate(runs):
            v = np.array(data[d][idx])
            share = np.array([(v == k).mean() if len(v) else 0 for k in levels])
            ax.bar(levels - 0.4 + w * (i + 0.5), share, width=w * 0.92, color=DOMAINS[d][1], edgecolor="white",
                   linewidth=1.0, label=DOMAINS[d][0])
        ax.set_xticks(levels)
        ax.set_xlabel("Levels")
        ax.set_title(title, loc="left")
        ax.grid(axis="x", visible=False)
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    axes[0].set_ylabel("Share of classes")
    fig.tight_layout()
    fig.legend(*axes[0].get_legend_handles_labels(), ncol=len(runs), loc="lower center", bbox_to_anchor=(0.5, 1.0))
    out.save(fig, "hierarchy_depth", "Hierarchy shape: levels from each class up to BFO entity, and how many corpus "
             "classes sit above it", "ontology/classes.json or enriched.json; BFO/CCO ancestors", table)


def fig_review_flags(out: Out, rows: list[dict]):
    runs = largest(rows, "ontology/review_issues.json")
    if not runs:
        return out.skip("review_flags", "no review_issues.json")
    vals, flags = {}, Counter()
    for d, r in runs.items():
        classes, _ = _classes(r)
        n = sum(1 for c in classes if not c.get("excluded")) or 1
        c = Counter(f for x in _json(r["_dir"] / "ontology/review_issues.json") or [] for f in x.get("flags", []))
        flags.update(c)
        vals[d] = {k.replace("_", " "): v / n for k, v in c.items()}
    cats = [k.replace("_", " ") for k, _ in flags.most_common()]
    fig, ax = plt.subplots(figsize=(7.0, 0.36 * len(cats) * max(len(runs), 1) ** 0.5 + 1.0))
    grouped_barh(ax, cats, runs, vals, fmt="share")
    ax.set_xlabel("Share of classes flagged for review")
    ax.legend(ncol=len(runs), loc="lower left", bbox_to_anchor=(0, 1.0))
    out.save(fig, "review_flags", "Classes flagged for expert review, by reason", "ontology/review_issues.json",
             [{"domain": d, **vals[d]} for d in runs])


def fig_study_stages(out, rows):
    runs = largest(rows, "ontology/enriched.json")
    counts = {}
    for d, r in runs.items():
        facets = _json(r["_dir"] / "ontology/facets.json") or {}
        counts[d] = Counter((v.get("study_stage") or ["(none)"])[0] for k, v in facets.items() if not k.startswith("p:"))
    share_figure(out, "study_stages", "Classes by MDS-Onto study stage (first stage assigned)", "ontology/facets.json",
                 {d: c for d, c in counts.items() if c})


def fig_mapping_targets(out: Out, rows: list[dict]):
    runs = largest(rows, "ontology/mappings.json")
    counts = {d: Counter(m.get("ontology") or "?" for m in _json(r["_dir"] / "ontology/mappings.json") or [])
              for d, r in runs.items()}
    counts = {d: c for d, c in counts.items() if c}
    if not counts:
        return out.skip("mapping_targets", "no mappings")
    keep = [k for k in top_categories(counts, 12) if k != "Other"]
    m = np.array([[counts[d].get(k, 0) for k in keep] for d in counts], dtype=float)
    fig, ax = plt.subplots(figsize=(7.0, 0.4 * len(counts) + 1.5))
    im = heatmap(ax, [label(d) for d in counts], keep, m, fmt="{:.0f}")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    ax.set_title("External mappings by target ontology", loc="left")
    out.save(fig, "mapping_targets", "External mappings per domain by target ontology (counts)", "ontology/mappings.json",
             [{"domain": d, **{k: counts[d].get(k, 0) for k in keep}} for d in counts])


def fig_layer_vs_ontology(out: Out, rows: list[dict]):
    runs = largest(rows, "ontology/domain_layer_metrics.json")
    if not runs:
        return out.skip("layer_vs_ontology", "no literature layer")
    layer = {d: _json(r["_dir"] / "ontology/domain_layer_metrics.json") or {} for d, r in runs.items()}
    metr = {d: _json(r["_dir"] / "ontology/metrics.json") or {} for d, r in runs.items()}
    lcats = [("relation_links", "Relation claims"), ("causal_links", "Causal claims"), ("reported_values", "Reported values"),
             ("broader_is_a", "Is-a links")]
    ocats = [("restriction_causal", "Causal restrictions"), ("restriction_relation", "Relation restrictions"),
             ("subclass_named", "Named subclass axioms"), ("disjoint_with", "Disjointness")]
    lv = {d: {t: num(layer[d].get(k)) for k, t in lcats} for d in runs}
    ov = {d: {t: num(metr[d].get("axioms", {}).get(k)) for k, t in ocats} for d in runs}
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))
    grouped_barh(axes[0], [t for _, t in lcats], runs, lv)
    grouped_barh(axes[1], [t for _, t in ocats], runs, ov)
    axes[0].set_title("Literature layer (everything the papers state)", loc="left")
    axes[1].set_title("Ontology (universal axioms only)", loc="left")
    for ax in axes:
        ax.set_xlabel("Count")
    fig.tight_layout()
    fig.legend(*axes[0].get_legend_handles_labels(), ncol=len(runs), loc="lower center", bbox_to_anchor=(0.5, 1.0))
    out.save(fig, "layer_vs_ontology", "What the literature layer keeps against what the ontology asserts",
             "ontology/domain_layer_metrics.json, ontology/metrics.json", [{"domain": d, **lv[d], **ov[d]} for d in runs])


# ---------------------------------------------------------------- ontology store

ONTOLOGY_SLOTS = {"cco": SLOTS[0], "bfo": SLOTS[1], "mds-onto": SLOTS[2], "pmdco": SLOTS[3], "ro": SLOTS[4],
                  "iof": SLOTS[5], "qudt": SLOTS[6], "qudt-units": SLOTS[7]}
ONTOLOGY_NAMES = {"cco": "CCO", "bfo": "BFO", "mds-onto": "MDS-Onto", "pmdco": "PMDCO", "ro": "RO", "iof": "IOF",
                  "qudt": "QUDT", "qudt-units": "QUDT units"}
OTHER = "#b9b8b2"


def columns(r: dict, prefix: str, skip=()) -> Counter:
    """Counter of the numeric columns that start with prefix (suffix -> value)."""
    return Counter({k[len(prefix):]: num(v) for k, v in r.items()
                    if k.startswith(prefix) and v not in ("", None) and k[len(prefix):] not in skip and num(v)})


def ontology_series(counts: dict[str, Counter]) -> list[tuple[str, str, list[float]]]:
    """Share series per ontology with a fixed colour per ontology (case-insensitive), rest as Other."""
    runs = list(counts)
    norm = {d: Counter() for d in runs}
    for d in runs:
        for k, v in counts[d].items():
            norm[d][k.lower() if k.lower() in ONTOLOGY_SLOTS else "other"] += v
    keys = [k for k in [*ONTOLOGY_SLOTS, "other"] if any(norm[d][k] for d in runs)]
    return [(ONTOLOGY_NAMES.get(k, "Other"), ONTOLOGY_SLOTS.get(k, OTHER),
             [norm[d][k] / (sum(norm[d].values()) or 1) for d in runs]) for k in keys]


def fig_store_candidates(out: Out, rows: list[dict]):
    runs = largest(rows, "run.json")
    panels = (("parent_candidates_", "Parent candidates (placement)"), ("candidates_ontology_", "Mapping candidates"),
              ("property_candidates_ontology_", "Property candidates"))
    data = {p: {d: columns(r, p) for d, r in runs.items()} for p, _ in panels}
    panels = [(p, t) for p, t in panels if any(sum(c.values()) for c in data[p].values())]
    if not panels:
        return out.skip("store_candidates", "no store candidate columns (runs before the ontology store)")
    fig, axes = plt.subplots(len(panels), 1, figsize=(7.0, (0.3 * len(runs) + 0.75) * len(panels) + 0.4))
    axes = np.atleast_1d(axes)
    table, handles = [], {}
    for ax, (p, title) in zip(axes, panels):
        ds = [d for d in runs if sum(data[p][d].values())]
        stacked_barh(ax, [label(d) for d in ds], ontology_series({d: data[p][d] for d in ds}), share=True)
        ax.set_title(title, loc="left")
        for h, lab in zip(*ax.get_legend_handles_labels()):
            handles.setdefault(lab, h)
        table += [{"panel": p.rstrip("_"), "domain": d, "total": sum(data[p][d].values()), **data[p][d]} for d in ds]
    axes[-1].set_xlabel("Share of candidates, by ontology")
    fig.tight_layout()
    fig.legend(handles.values(), handles.keys(), ncol=min(len(handles), 5), loc="lower center", bbox_to_anchor=(0.5, 1.0))
    out.save(fig, "store_candidates", "Candidates drawn from the ontology store, by ontology: parents for placement, "
             "terms for mappings, properties for restrictions", "eval_runs.csv parent_candidates_*, candidates_ontology_*, "
             "property_candidates_ontology_*", table)


def fig_store_sources(out: Out, rows: list[dict]):
    runs = largest(rows, "run.json")
    src = {d: columns(r, "candidates_source_") for d, r in runs.items()}
    hits = {d: columns(r, "portal_hits_") for d, r in runs.items()}
    if not any(sum(c.values()) for c in src.values()):
        return out.skip("store_sources", "no candidates_source_* columns")
    names = {"store": "Store search", "propagated": "Propagated (mappings)"}
    keys = sorted({k for c in src.values() for k in c}, key=lambda k: (k != "store", k != "propagated", "+" in k, k))
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 0.36 * len(runs) + 1.4), gridspec_kw={"width_ratios": [1.6, 1]})
    ds = [d for d in runs if sum(src[d].values())]
    stacked_barh(axes[0], [label(d) for d in ds],
                 [(names.get(k, k.replace("_", " ").replace("+", " + ")), SLOTS[i % len(SLOTS)],
                   [src[d][k] / sum(src[d].values()) for d in ds]) for i, k in enumerate(keys)], share=True)
    axes[0].set_title("Where mapping candidates were found", loc="left")
    axes[0].legend(ncol=2, loc="upper left", bbox_to_anchor=(0, -0.18 - 0.02 * len(ds)), fontsize=6.5)
    portals = sorted({k for c in hits.values() for k in c})
    classes = {d: num(r.get("final_classes")) or num(r.get("canonical_concepts")) or 1 for d, r in runs.items()}
    if portals:
        grouped_barh(axes[1], [p.replace("_", " ") for p in portals], {d: None for d in ds},
                     {d: {p.replace("_", " "): hits[d][p] / classes[d] for p in portals} for d in ds})
        axes[1].set_xlabel("Portal hits per class")
        axes[1].set_title("Portal search hits", loc="left")
        axes[1].legend(loc="upper left", bbox_to_anchor=(0, -0.18 - 0.02 * len(ds)), fontsize=6.5)
    else:
        axes[1].axis("off")
    fig.tight_layout()
    out.save(fig, "store_sources", "Mapping candidates by where they were found (store search, MDS-Onto portal, "
             "MatPortal, propagation) and portal hits per class", "eval_runs.csv candidates_source_*, portal_hits_*",
             [{"domain": d, "classes": classes[d], **{f"source_{k}": v for k, v in src[d].items()},
               **{f"hits_{k}": v for k, v in hits[d].items()}} for d in ds])


def fig_store_propagation(out: Out, rows: list[dict]):
    runs = largest(rows, "run.json")
    cand = {d: columns(r, "candidates_hop_") for d, r in runs.items()}
    maps = {d: columns(r, "mappings_hop_") for d, r in runs.items()}
    if not any(sum(c.values()) for c in list(cand.values()) + list(maps.values())):
        return out.skip("store_propagation", "no candidates_hop_* or mappings_hop_* columns")
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.4))
    hops = sorted({k for c in list(cand.values()) + list(maps.values()) for k in c}, key=lambda k: num(k))
    lab = lambda h: "direct" if h == "0" else f"{h} hop{'s' if h != '1' else ''}"
    grouped_barh(axes[0], [lab(h) for h in hops if h != "0"], runs, {d: {lab(h): cand[d][h] for h in hops} for d in runs})
    axes[0].set_title("Candidates added by propagation", loc="left")
    axes[0].set_xlabel("Candidates")
    grouped_barh(axes[1], [lab(h) for h in hops], runs, {d: {lab(h): maps[d][h] for h in hops} for d in runs})
    axes[1].set_title("Mappings committed", loc="left")
    axes[1].set_xlabel("Mappings")
    fig.tight_layout()
    fig.legend(*axes[1].get_legend_handles_labels(), ncol=len(runs), loc="lower center", bbox_to_anchor=(0.5, 1.0))
    out.save(fig, "store_propagation", "Propagation through the store's own mappings: candidates reached in one or two "
             "hops, and mappings committed directly or through a hop", "eval_runs.csv candidates_hop_*, mappings_hop_*",
             [{"domain": d, **{f"candidates_hop_{h}": cand[d][h] for h in hops},
               **{f"mappings_hop_{h}": maps[d][h] for h in hops}} for d in runs])


def fig_store_imports(out: Out, rows: list[dict]):
    runs = largest(rows, "run.json")
    imp = {d: columns(r, "imported_terms_") for d, r in runs.items()}
    labs = {d: columns(r, "labels_") for d, r in runs.items()}
    if not any(sum(c.values()) for c in imp.values()):
        return out.skip("store_imports", "no imported_terms_* columns")
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 0.36 * len(runs) + 1.5))
    ds = list(runs)
    stacked_barh(axes[0], [label(d) for d in ds], [(n, c, [v * sum(imp[d].values()) for v, d in zip(vals, ds)])
                                                    for n, c, vals in ontology_series(imp)], share=False)
    axes[0].set_title("Imported terms (count), by ontology", loc="left")
    axes[0].legend(ncol=2, loc="upper left", bbox_to_anchor=(0, -0.22 - 0.02 * len(ds)), fontsize=6.5)
    keys = sorted({k for c in labs.values() for k in c}, key=lambda k: -sum(labs[d][k] for d in ds))
    stacked_barh(axes[1], [label(d) for d in ds],
                 [(k.replace("_", " "), SLOTS[i % len(SLOTS)], [labs[d][k] / (sum(labs[d].values()) or 1) for d in ds])
                  for i, k in enumerate(keys)], share=True)
    axes[1].set_yticklabels([])
    axes[1].set_title("Class labels, by origin and property", loc="left")
    axes[1].legend(ncol=2, loc="upper left", bbox_to_anchor=(0, -0.22 - 0.02 * len(ds)), fontsize=6.5)
    fig.tight_layout()
    out.save(fig, "store_imports", "External terms the ontology imports from the store, by ontology, and class labels by "
             "origin (paper, external match, preferred label)", "eval_runs.csv imported_terms_*, labels_*",
             [{"domain": d, **{f"imported_{k}": v for k, v in imp[d].items()},
               **{f"labels_{k}": v for k, v in labs[d].items()}} for d in ds])


def fig_mapping_methods(out: Out, rows: list[dict]):
    runs = largest(rows, "run.json")
    pred = {d: columns(r, "mappings_predicate_") for d, r in runs.items()}
    meth = {d: columns(r, "mappings_method_") for d, r in runs.items()}
    if not any(sum(c.values()) for c in pred.values()):
        return out.skip("mapping_methods", "no mappings_predicate_* columns")
    order = ["owl:equivalentClass", "skos:exactMatch", "rdfs:subClassOf", "skos:broadMatch", "skos:closeMatch",
             "skos:narrowMatch", "skos:relatedMatch"]
    keys = [k for k in order if any(pred[d][k] for d in runs)] + sorted(
        {k for c in pred.values() for k in c} - set(order))
    ds = [d for d in runs if sum(pred[d].values())]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 0.36 * len(ds) + 1.5), gridspec_kw={"width_ratios": [1.6, 1]})
    stacked_barh(axes[0], [label(d) for d in ds], [(k, SLOTS[i % len(SLOTS)], [pred[d][k] / sum(pred[d].values())
                                                                              for d in ds]) for i, k in enumerate(keys)],
                 share=True)
    axes[0].set_title("Mappings by predicate written", loc="left")
    axes[0].legend(ncol=3, loc="upper left", bbox_to_anchor=(0, -0.2 - 0.02 * len(ds)), fontsize=6.5)
    mk = sorted({k for c in meth.values() for k in c})
    down = {d: num(runs[d].get("mappings_downgraded")) for d in ds}
    cats = [k.replace("_", " ") for k in mk] + ["downgraded"]
    grouped_barh(axes[1], cats, {d: None for d in ds},
                 {d: {**{k.replace("_", " "): meth[d][k] for k in mk}, "downgraded": down[d]} for d in ds})
    axes[1].set_title("How mappings were chosen", loc="left")
    axes[1].set_xlabel("Mappings")
    axes[1].legend(loc="upper left", bbox_to_anchor=(0, -0.3 - 0.02 * len(ds)), fontsize=6.5)
    fig.tight_layout()
    out.save(fig, "mapping_methods", "Mappings by the predicate written to the ontology, and how they were chosen (model "
             "choice or same-name label match; downgraded: kept with a weaker relation)",
             "eval_runs.csv mappings_predicate_*, mappings_method_*, mappings_downgraded",
             [{"domain": d, **pred[d], **{f"method_{k}": v for k, v in meth[d].items()}, "downgraded": down[d]}
              for d in ds])


def fig_parent_answers(out: Out, rows: list[dict]):
    order = [("candidate", "A store candidate"), ("corpus", "A corpus concept"), ("root", "A BFO category root"),
             ("store_label", "A CCO/BFO class by name"), ("fuzzy", "Close spelling of an offered parent"),
             ("unresolved", "Unresolved (category root used)"), ("no_answer", "No answer")]
    _domain_shares(out, rows, "parent_answers", "How the model's parent answers were read (local tier, pass 2)",
                   "eval_runs.csv parent_answers_*", order, "parent_answers_",
                   colors=[SLOTS[0], SLOTS[1], SLOTS[2], SLOTS[6], SLOTS[3], SLOTS[7], "#d9d8d3"])


def fig_uncertain(out: Out, rows: list[dict]):
    runs = largest(rows, "ontology/uncertain.json")
    if not runs:
        return out.skip("uncertain_items", "no ontology/uncertain.json (runs before this revision)")
    from src.tools.reports import UNCERTAIN_KINDS
    counts = {}
    for d, r in runs.items():
        data = _json(r["_dir"] / "ontology/uncertain.json") or {}
        counts[d] = Counter()
        for stage, c in (data.get("counts") or {}).items():
            for k, n in c.items():
                counts[d][f"{stage}: {k.replace('_', ' ')}"] += n
    cats = [k for k, _ in sum(counts.values(), Counter()).most_common()]
    if not cats:
        return out.skip("uncertain_items", "uncertain.json lists nothing")
    classes = {d: num(r.get("final_classes")) or 1 for d, r in runs.items()}
    fig, ax = plt.subplots(figsize=(7.0, 0.3 * len(cats) * max(len(runs), 1) ** 0.5 + 1.0))
    grouped_barh(ax, cats, runs, {d: dict(counts[d]) for d in runs})
    ax.set_xlabel("Items listed in ontology/uncertain.json")
    ax.set_xscale("symlog", linthresh=10)
    ax.legend(ncol=len(runs), loc="lower left", bbox_to_anchor=(0, 1.0))
    out.save(fig, "uncertain_items", "Uncertain or dropped items listed for review, by stage and kind (log scale above 10)",
             "ontology/uncertain.json counts; kinds: " + "; ".join(f"{k}: {v}" for k, v in UNCERTAIN_KINDS.items()),
             [{"domain": d, "classes": classes[d], **counts[d]} for d in runs])


def fig_integration_series(out: Out, outputs: Path, revision: str, run_ids):
    ints = [r for r in _csv(outputs / "eval_integrations.csv") if r.get("row_type") == "integration"]
    ints = [r for r in ints if (set(filter(None, r.get("input_runs", "").split("+"))) <= set(run_ids) if run_ids
                                else r.get("workflow_revision") == revision)]
    papers = {r["run_id"]: num(r.get("papers_processed")) for r in _csv(outputs / "eval_runs.csv")
              if r.get("row_type") == "run"}
    pts = []
    for r in ints:
        per = [papers.get(k, 0) for k in r.get("input_runs", "").split("+") if k]
        if per and min(per):
            pts.append((int(min(per)), r))
    if len({n for n, _ in pts}) < 2:
        return out.skip("integration_series", "needs integrations at two or more corpus sizes")
    latest = {}
    for n, r in sorted(pts, key=lambda x: x[1].get("created", "")):
        latest[n] = r  # the newest integration per size
    xs = sorted(latest)
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.5))
    for k, (col, name) in enumerate((("mappings_total", "Mappings"), ("bridge_concepts", "Bridge concepts"))):
        axes[0].plot(xs, [num(latest[n].get(col)) for n in xs], color=SLOTS[k], marker="o", markeredgecolor="white",
                     markeredgewidth=1.0, label=name)
    axes[0].set_title("Cross-domain links", loc="left")
    axes[0].legend(loc="upper left", ncol=2)
    doms = [d for d in DOMAINS if any(latest[n].get(f"classes_mapped_share_{d}") not in (None, "") for n in xs)]
    for d in doms:
        name, color, marker = DOMAINS[d]
        axes[1].plot(xs, [num(latest[n].get(f"classes_mapped_share_{d}"), np.nan) for n in xs], color=color, marker=marker,
                     markeredgecolor="white", markeredgewidth=1.0, label=name)
    axes[1].set_title("Share of each domain's classes mapped", loc="left")
    axes[1].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    if doms:
        axes[1].legend(loc="upper left", ncol=len(doms), fontsize=6.5)
    for ax in axes:
        ax.set_xlabel("Papers per domain")
        ax.set_xticks(xs)
        ax.set_ylim(0, ax.get_ylim()[1] * 1.3)  # room for the legend above the lines
    fig.tight_layout()
    out.save(fig, "integration_series", "Cross-domain integration as the corpus grows: mappings and bridge concepts, and "
             "the share of each domain's classes mapped (newest integration per size)", "eval_integrations.csv",
             [{"papers_per_domain": n, "integration": latest[n]["run_id"], "mappings": num(latest[n].get("mappings_total")),
               "bridge_concepts": num(latest[n].get("bridge_concepts")),
               **{f"mapped_share_{d}": num(latest[n].get(f"classes_mapped_share_{d}")) for d in doms}} for n in xs])


# ---------------------------------------------------------------- main

FIGURES = (fig_concept_growth, fig_knowledge_growth, fig_scaling, fig_per_paper_yield, fig_parsing,
           fig_extraction_checks, fig_evidence, fig_normalization, fig_concept_support, fig_concept_types,
           fig_causal_polarity, fig_relation_predicates, fig_bfo_categories, fig_hierarchy, fig_placement,
           fig_parent_answers, fig_review_flags, fig_row_coverage, fig_definitions, fig_restrictions,
           fig_layer_vs_ontology, fig_mappings, fig_mapping_targets, fig_mapping_methods, fig_study_stages,
           fig_store_candidates, fig_store_sources, fig_store_propagation, fig_store_imports, fig_uncertain, fig_compute)


def build(outputs: Path | None = None, revision: str = config.WORKFLOW_REVISION, profile: str | None = None,
          run_ids: list[str] | None = None, out_dir: Path | None = None, title: str | None = None) -> Path:
    """Every figure (PDF, PNG, CSV), index.md, sweep_summary.csv and the grouped report (report.md, report.html).
    One failing figure is listed as skipped; it never stops the others."""
    from src import report
    outputs = Path(outputs).resolve() if outputs else config.OUTPUTS
    rows, notes = load_runs(outputs, revision, profile, run_ids)
    out = Out(Path(out_dir) if out_dir else outputs / "figures" / revision)
    print(f"{len(rows)} run(s) at revision {revision}" + (f"; {'; '.join(notes)}" if notes else ""))
    steps = [(f.__name__[4:], lambda f=f: f(out, rows)) for f in FIGURES]
    steps += [("integration", lambda: fig_integration(out, outputs, rows, revision, run_ids)),
              ("integration_series", lambda: fig_integration_series(out, outputs, revision, run_ids))]
    for name, step in steps:
        try:
            step()
        except Exception as e:  # a figure whose data has an unexpected shape must not cost the rest
            plt.close("all")
            out.skip(name, f"failed: {type(e).__name__}: {str(e)[:160]}")
    lines = [f"# Figures: revision {revision}", "",
             f"Runs: {', '.join(r['run_id'] for r in rows) or 'none'}", *[f"Note: {n}" for n in notes], "",
             "| Figure | Shows | Data |", "|---|---|---|"]
    lines += [f"| `{n}.pdf` | {t} | {s} |" for n, t, s in out.index]
    if out.skipped:
        lines += ["", "Skipped:", *[f"- `{n}`: {w}" for n, w in out.skipped]]
    (out.folder / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        report.write(out, rows, outputs, revision, run_ids, notes, title)
    except Exception as e:
        print(f"  report not written: {type(e).__name__}: {e}")
    print(f"wrote {len(out.index)} figure(s) and the report to {out.folder}")
    return out.folder


def main():
    ap = argparse.ArgumentParser(description="Paper figures and the grouped report from eval tables and run folders")
    ap.add_argument("--outputs", help="outputs folder (default: this checkout's outputs)")
    ap.add_argument("--revision", default=config.WORKFLOW_REVISION, help="workflow revision to plot")
    ap.add_argument("--profile", help="LLM profile to plot (default: the most common one at this revision)")
    ap.add_argument("--runs", nargs="*", help="explicit run ids instead of revision/profile filtering")
    ap.add_argument("--out", help="figure folder (default: outputs/figures/<revision>)")
    ap.add_argument("--title", help="report title")
    args = ap.parse_args()
    build(args.outputs, args.revision, args.profile, args.runs, args.out, args.title)


if __name__ == "__main__":
    main()
