"""Tables for scripts/run-checks.ps1, read from each run's rows.jsonl (one line per answered row) and run.json.

  python scripts/compare_runs.py reuse A B C D   B reused A's answers; C and D asked fresh. For rows B reused that C
                                                 and D also asked (identical row keys): does a reused answer agree
                                                 with a fresh one as often as two fresh answers agree?
  python scripts/compare_runs.py facets C S X    C: stage and domain in one call; S: the same run's interop redone
                                                 with separate calls; X: redone in one call again (the noise floor)
  python scripts/compare_runs.py coverage RUN... rows answered by the model on the first call, per pass
Answers are compared with concept ids replaced by labels and lists as sets."""
import json
import re
import sys
from collections import defaultdict
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


if __name__ == "__main__":
    commands = {"reuse": (reuse, 4), "facets": (facets, 3), "coverage": (coverage, None)}
    if len(sys.argv) < 3 or sys.argv[1] not in commands:
        raise SystemExit(__doc__)
    fn, n = commands[sys.argv[1]]
    if n and len(sys.argv) - 2 != n:
        raise SystemExit(__doc__)
    fn(*sys.argv[2:])
