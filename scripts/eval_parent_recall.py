"""Recall of CCO/BFO parent candidates, measured on concepts the ontology stage name-matched to an MDS-Onto or PMDCO
class: the gold parent is that class's nearest CCO/BFO ancestor. No model calls; embeddings come from EMBED (cached).

    uv run --with-requirements requirements.txt python scripts/eval_parent_recall.py [--runs RUN ...] [--show LABEL ...]

--show prints the candidates the ontology stage would offer for those concept labels (from the same runs).
"""
import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import EMBED, ONTOLOGY_SEARCH, OUTPUTS  # noqa: E402
from src.tools import lexical, ontostore, retrieval, upper  # noqa: E402
from src.agents.ontology import CATEGORIES, OntologyAgent  # noqa: E402

ORDER = ONTOLOGY_SEARCH["parent_ontologies"]
K = ONTOLOGY_SEARCH["parents_per_class"]
ROOTS = set(CATEGORIES.values()) | {upper.ENTITY, "http://purl.obolibrary.org/obo/BFO_0000002",
                                    "http://purl.obolibrary.org/obo/BFO_0000003", "http://purl.obolibrary.org/obo/BFO_0000004",
                                    "http://purl.obolibrary.org/obo/BFO_0000020", "http://purl.obolibrary.org/obo/BFO_0000017"}


def concept_case(c: dict, menu_lc: dict) -> dict:
    default = OntologyAgent._default(c, menu_lc)
    root = next((r for r in CATEGORIES.values() if r in [default, *upper.ancestors(default)]), CATEGORIES["material entity"])
    return {"label": c["label"], "alt": c["alt_labels"][:2], "root": root,
            "text": f"{c['label']}: {(c['definitions'][0]['text'] if c['definitions'] else '')[:200]}"}


def gold_cases(runs: list[str]) -> list[dict]:
    """One case per name-matched label: the concept as the ontology stage saw it, its category root (from its type,
    as the local tier assigns it) and the matched class's nearest CCO/BFO ancestors."""
    menu_lc = {k.lower(): v for k, v in upper.class_menu().items()}
    cases, seen = [], set()
    for run in runs:
        for c in json.loads((OUTPUTS / run / "ontology" / "classes.json").read_text(encoding="utf-8")):
            if c.get("parent_source") != "name_match" or c["label"].lower() in seen:
                continue
            chain = ontostore.ancestors(c["parent"])
            upper_chain = [a for a in chain if (ontostore.term(a) or {}).get("ontology") in ORDER]
            if not upper_chain:
                continue
            first = next(i for i, a in enumerate(chain) if a in upper_chain)
            depth = lambda a: chain.index(a)  # noqa: E731
            near = {a for a in upper_chain if depth(a) <= first + 1} - ROOTS or {upper_chain[0]}
            seen.add(c["label"].lower())
            cases.append({**concept_case(c, menu_lc), "near": near, "chain": set(upper_chain) - ROOTS})
    return cases


def queries(c: dict) -> list[str]:
    return [c["label"], *c["alt"], lexical.head_query(c["label"]) or ""]


def current(c: dict, vec, full: bool = False) -> list:
    """The ontology stage's _candidates: global search, then category filter (exact labels kept), CCO first, top K."""
    found = ontostore.search(queries(c), vec, kinds=("class",), ontologies=ORDER, k=K * 3, nearest=5)
    found = [x for x in found if x["exact"] or c["root"] in [x["iri"], *upper.ancestors(x["iri"])]]
    found.sort(key=lambda x: (ORDER.index(x["ontology"]), -x["score"]))
    return found[:K] if full else [x["iri"] for x in found[:K]]


def masked(c: dict, vec, pool: dict, how: str) -> list[str]:
    """Every CCO/BFO class under the category root, ranked with no thresholds by fused score, cosine or lexical."""
    ids, labels, mat = pool[c["root"]]
    qs = [ontostore._norm(q) for q in queries(c) if q and len(ontostore._norm(q)) >= 3]
    lex = np.array([max((1.0 if q == lab else ontostore._dice(q, lab) for q in qs for lab in labs), default=0.0)
                    for labs in labels])
    cos = mat @ vec if vec is not None and mat is not None else np.zeros(len(ids))
    w = ONTOLOGY_SEARCH["weights"]
    score = {"lexical": lex, "cosine": cos,
             "fused": (w["lexical"] * lex + w["cosine"] * np.clip(cos, 0, None)) / (w["lexical"] + w["cosine"])}[how]
    return [ids[i] for i in np.argsort(-(score + (lex == 1.0)))[:K]]  # exact labels first, as in search


def pools(cases: list[dict], vectors: dict | None) -> dict:
    """Per category root: CCO/BFO classes beneath it, their normalised labels and (optionally) their vectors."""
    rows = ontostore._db().execute("SELECT iri, ontology, kind, deprecated FROM terms").fetchall()
    classes = [i for i, ont, kind, dep in rows if ont in ORDER and kind == "class" and not dep]
    out = {}
    for root in {c["root"] for c in cases}:
        ids = [i for i in classes if root == i or root in ontostore.ancestors(i)]
        labels = [[ontostore._norm(x["text"]) for x in ontostore.term(i)["labels"]] for i in ids]
        mat = np.stack([vectors[i] for i in ids]) if vectors else None
        out[root] = (ids, labels, mat)
    return out


def store_vectors() -> dict:
    m, ids, row, *_ = ontostore._vectors()
    m = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-12)
    return {i: m[row[i]] for i in ids}


def score(cases: list[dict], picks: dict) -> dict:
    n = len(cases)
    hit = lambda k: sum(bool(set(picks[c["label"]][:k]) & c["near"]) for c in cases) / n  # noqa: E731
    return {"recall@1": hit(1), "recall@3": hit(3), f"recall@{K}": hit(K),
            f"chain@{K}": sum(bool(set(picks[c["label"]]) & c["chain"]) for c in cases) / n,
            "mean_offered": sum(len(picks[c["label"]]) for c in cases) / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", help="run ids (default: the n25 runs of the latest sweep)")
    ap.add_argument("--show", nargs="+", default=[], help="concept labels whose candidates to print")
    args = ap.parse_args()
    ontostore.require()
    latest = sorted(glob.glob(str(OUTPUTS / "*-n25-*" / "ontology" / "classes.json")), key=lambda p: Path(p).stat().st_mtime)
    sweep = Path(latest[-1]).parent.parent.name.split("-n25-")[1]  # the newest sweep's n25 domain runs
    runs = args.runs or sorted(Path(p).parent.parent.name for p in latest
                               if Path(p).parent.parent.name.endswith(f"-n25-{sweep}"))
    cases = gold_cases(runs)
    inside = sum(any(c["root"] in [g, *upper.ancestors(g)] for g in c["near"]) for c in cases)
    print(f"runs: {', '.join(runs)}\n{len(cases)} name-matched concepts; gold inside the type's category: {inside}"
          f" ({inside / len(cases):.0%}); gold by ontology: {dict(Counter(ontostore.term(g)['ontology'] for c in cases for g in c['near']))}")
    if not ontostore.has_vectors():
        print("store vectors do not match EMBED (model or prefixes): run `python -m src.run ontologies build`; lexical only")
    vecs = dict(zip([c["label"] for c in cases], retrieval.query([c["text"] for c in cases])))
    plain = pools(cases, store_vectors() if ontostore.has_vectors() else None)
    results = {"current (search, filter, CCO first)": {c["label"]: current(c, vecs[c["label"]]) for c in cases}}
    for how in ("fused", "cosine", "lexical"):
        results[f"masked {how}"] = {c["label"]: masked(c, vecs[c["label"]], plain, how) for c in cases}
    print(f"\n{'variant':42} " + " ".join(f"{m:>11}" for m in score(cases, results[next(iter(results))])))
    for name, picks in results.items():
        print(f"{name:42} " + " ".join(f"{v:11.2f}" for v in score(cases, picks).values()))
    print(f"\nembedding model: {EMBED['model']}. recall@k: the matched class's nearest CCO/BFO parent is among the first k"
          f" candidates; chain@{K}: any CCO/BFO class on its ancestor chain (bare BFO roots excluded) is offered.")
    if args.show:
        menu_lc = {k.lower(): v for k, v in upper.class_menu().items()}
        by_label = {}
        for run in runs:
            for c in json.loads((OUTPUTS / run / "ontology" / "classes.json").read_text(encoding="utf-8")):
                by_label.setdefault(c["label"].lower(), c)
        shown = [concept_case(by_label[x.lower()], menu_lc) for x in args.show if x.lower() in by_label]
        for c, v in zip(shown, retrieval.query([c["text"] for c in shown])):
            print(f"  {c['label'][:32]:32} " + "; ".join(
                f"{x['label']} ({x['score']:.2f}" + ("" if x["cosine"] is None else f", cos {x['cosine']:.2f}") + ")"
                for x in current(c, v, full=True)[:5]))


if __name__ == "__main__":
    main()
