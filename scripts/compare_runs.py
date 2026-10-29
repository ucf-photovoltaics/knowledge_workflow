"""Tables for scripts/run-checks.ps1, read from each run's rows.jsonl (one line per answered row) and run.json.

  python scripts/compare_runs.py reuse A B C D   B reused A's answers; C and D asked fresh. For rows B reused that C
                                                 and D also asked (identical row keys): does a reused answer agree
                                                 with a fresh one as often as two fresh answers agree?
  python scripts/compare_runs.py facets C S X    C: stage and domain in one call; S: the same run's interop redone
                                                 with separate calls; X: redone in one call again (the noise floor)
  python scripts/compare_runs.py coverage RUN... rows answered by the model on the first call, per pass
  python scripts/compare_runs.py repeats SWEEP...  the same sweep repeated (scripts/slurm-repeat.sh): how much of
                                                 each run's content the repeats share
Answers are compared with concept ids replaced by labels and lists as sets.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import json
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "outputs"


def labels(run: str) -> dict:
    path = OUT / run / "normalized" / "concepts.json"
    return {c["id"]: c["label"].lower() for c in json.loads(path.read_text(encoding="utf-8"))} if path.exists() else {}


def canon(answer, names: dict):
    if isinstance(answer, dict):
        return {k: canon(v, names) for k, v in sorted(answer.items()) if k != "id"}
    if isinstance(answer, list):
        return sorted({json.dumps(canon(v, names), sort_keys=True) for v in answer})
    if isinstance(answer, str):
        return names.get(answer, answer.strip().lower()) if re.fullmatch(r"k\d+", answer) else answer.strip().lower()
    return answer


def rows(run: str) -> list[dict]:
    path, names = OUT / run / "rows.jsonl", labels(run)
    out = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    for r in out:
        r["canon"] = canon(r["answer"], names)
    return out


def share(pairs) -> str:
    pairs = list(pairs)
    return f"{sum(a == b for a, b in pairs) / len(pairs):6.1%}" if pairs else "     -"


def wall(run: str) -> float:
    m = json.loads((OUT / run / "run.json").read_text(encoding="utf-8"))
    return sum(s.get("wall_s", 0) for s in m.get("stages", {}).values())


def reuse(a: str, b: str, c: str, d: str):
    by = {run: {r["key"]: r for r in rows(run) if r.get("key")} for run in (b, c, d)}
    print(f"Wall time: {b} {wall(b) / 60:.0f} min (reusing {a}), {c} {wall(c) / 60:.0f} min, {d} {wall(d) / 60:.0f} min (fresh)\n")
    print(f"{'pass':24} {'rows':>6} {'reused':>7} {'compared':>9} {'reused=fresh':>13} {'fresh=fresh':>12}")
    passes = defaultdict(list)
    for r in rows(b):
        passes[r["pass"]].append(r)
    for name, rs in sorted(passes.items()):
        used = [r for r in rs if r["source"] == "reused"]
        common = [r["key"] for r in used if r["key"] in by[c] and r["key"] in by[d]]
        print(f"{name:24} {len(rs):6} {len(used):7} {len(common):9} "
              f"{share((by[b][k]['canon'], by[c][k]['canon']) for k in common):>13} "
              f"{share((by[c][k]['canon'], by[d][k]['canon']) for k in common):>12}")
    print("\nReuse is safe for a pass when reused=fresh is within a few points of fresh=fresh (or higher).")


def facets(combined: str, split: str, again: str):
    def tags(run, names):
        out = defaultdict(dict)
        for r in rows(run):
            if r["pass"] in names:
                out[r["id"]].update({k: v for k, v in r["canon"].items() if k in ("study_stage", "domain", "subdomain")})
        return out
    one, two, noise = tags(combined, {"facets"}), tags(split, {"stage", "domain"}), tags(again, {"facets"})
    ids = sorted(set(one) & set(two) & set(noise))
    print(f"{len(ids)} classes and properties tagged in all three runs\n")
    print(f"{'field':12} {'one call vs separate':>21} {'one call vs one call':>21}")
    for f in ("study_stage", "domain", "subdomain"):
        print(f"{f:12} {share((one[i].get(f), two[i].get(f)) for i in ids):>21} "
              f"{share((one[i].get(f), noise[i].get(f)) for i in ids):>21}")
    print("\nOne call is fine when 'one call vs separate' is close to 'one call vs one call' (the model's own noise).\n")
    coverage(combined, split, again)


def coverage(*runs: str):
    print(f"{'run':44} {'pass':22} {'rows':>6} {'first call':>11} {'missing':>8}")
    for run in runs:
        m = json.loads((OUT / run / "run.json").read_text(encoding="utf-8"))
        st = m.get("stages", {})
        found = {**st.get("ontology", {}).get("row_coverage", {}), **st.get("enrich", {}).get("row_coverage", {}),
                 **(st.get("interop", {}).get("checks") or {}).get("row_coverage", {})}
        for name, s in found.items():
            sent = s["rows"] - s.get("reused", 0)  # rows the model was actually asked
            first = s["answered_first"] - s.get("reused", 0)
            rate = f"{first / sent:.0%}" if sent else "all reused"
            print(f"{run[:44]:44} {name:22} {s['rows']:6} {rate:>11} {s.get('missing', 0):8}")


def _read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def _content(d: Path) -> dict:
    """What one run produced, as label sets keyed so that two runs can be compared item by item."""
    papers = {p.stem: {c["label"].strip().lower() for c in _read(p, {}).get("concepts", []) if c.get("label")}
              for p in sorted((d / "papers").glob("*.json"))}
    classes = _read(d / "ontology" / "enriched.json", None) or _read(d / "ontology" / "classes.json", [])
    names = {c["id"]: c["label"].strip().lower() for c in classes if c.get("id") and c.get("label")}
    live = {c["label"].strip().lower(): (names.get(c.get("parent"), c.get("parent")), c.get("category"))
            for c in classes if not c.get("excluded") and c.get("label")}
    maps = {(frozenset({(m["a_domain"], m["a_label"].lower()), (m["b_domain"], m["b_label"].lower())}), m["relation"])
            for m in _read(d / "mappings.json", [])}
    return {"papers": papers, "concepts": set(labels(d.name).values()), "classes": live, "mappings": maps}


def repeats(*sweeps: str):
    sweeps = [s.removeprefix("sweep-") for s in sweeps]
    groups = defaultdict(dict)  # run name without its sweep id, e.g. tea-n5 -> {sweep: content}
    for s in sweeps:
        for d in sorted(OUT.glob(f"*-{s}")):
            if (d / "run.json").exists() or (d / "integration.json").exists():
                groups[d.name[: -len(s) - 1]][s] = _content(d)
    if not groups:
        raise SystemExit(f"no runs of {', '.join(sweeps)} in {OUT}")
    mean = lambda xs: f"{sum(xs) / len(xs):6.1%}" if xs else "     -"
    low = lambda xs: f"{min(xs):6.1%}" if xs else "     -"
    print("Mean (and lowest) over each pair of repeats. Same papers: every repeat used the same paper keys.\n")
    print(f"{'run':28} {'n':>2} {'same papers':>11} {'paper concepts':>16} {'corpus concepts':>16} {'classes':>16} "
          f"{'same parent':>16} {'same category':>16} {'mappings':>16}")
    for name, runs in sorted(groups.items()):
        pairs = list(combinations(runs.values(), 2))
        same_papers = all(set(a["papers"]) == set(b["papers"]) for a, b in pairs)
        per_paper = [sum(_jaccard(a["papers"][k], b["papers"][k]) for k in a["papers"].keys() & b["papers"].keys())
                     / max(1, len(a["papers"].keys() & b["papers"].keys())) for a, b in pairs]
        shared = [(a["classes"], b["classes"], a["classes"].keys() & b["classes"].keys()) for a, b in pairs]
        col = lambda xs: f"{mean(xs)} ({low(xs).strip()})"
        cell = lambda key: col([_jaccard(set(a[key]), set(b[key])) for a, b in pairs])
        agree = lambda i: col([sum(x[k][i] == y[k][i] for k in ks) / len(ks) for x, y, ks in shared if ks])
        if name.startswith("integration"):
            cells = ["-"] * 6 + [cell("mappings")]
        else:
            cells = ["yes" if same_papers else "NO", col(per_paper), cell("concepts"), cell("classes"), agree(0), agree(1), "-"]
        print(f"{name[:28]:28} {len(runs):2} " + " ".join(f"{c:>{w}}" for c, w in zip(cells, (11, 16, 16, 16, 16, 16, 16))))
    print("\nLabels are compared lowercased; parents and categories only for classes both repeats kept. Concepts and classes:"
          "\nshare of the labels in either run found in both (Jaccard). Mappings: the same two classes with the same relation.")
    print(f"\n{'run':28} " + " ".join(f"{s[-16:]:>17}" for s in sweeps) + "   (classes, or mappings for integrations)")
    for name, runs in sorted(groups.items()):
        key = "mappings" if name.startswith("integration") else "classes"
        print(f"{name[:28]:28} " + " ".join(f"{len(runs[s][key]) if s in runs else '-':>17}" for s in sweeps))


if __name__ == "__main__":
    commands = {"reuse": (reuse, 4), "facets": (facets, 3), "coverage": (coverage, None), "repeats": (repeats, None)}
    if len(sys.argv) < 3 or sys.argv[1] not in commands:
        raise SystemExit(__doc__)
    fn, n = commands[sys.argv[1]]
    if n and len(sys.argv) - 2 != n:
        raise SystemExit(__doc__)
    fn(*sys.argv[2:])
