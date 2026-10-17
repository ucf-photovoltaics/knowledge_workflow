"""Which embedding model separates synonyms from look-alikes best, for normalization's synonym clusters?
No pipeline LLM calls: gold pairs come from curated labels in the ontology store, so the test is model-independent.

    ollama pull mxbai-embed-large   (and the other models to compare)
    uv run --with-requirements requirements.txt python scripts/eval_embeddings.py [--models M ...] [--base-url URL]

Synonyms: a class's preferred label vs. each of its curated alternative labels (MDS-Onto, PMDCO, CCO, RO, BFO), after
dropping pairs that are the same words (normalization's lexical step merges those before any embedding).
Look-alikes: the same label vs. a sibling class (same parent) and vs. another class sharing a word.
A model is "name" or "name|prefix" (text prepended to every label, e.g. "nomic-embed-text|clustering: ").
Reported per model: ROC AUC; recall and false-positive rate at normalization's cosine threshold; the threshold that
lets 5% of look-alikes through, and the recall there (the threshold to use with that model). Rates, not precision,
so the result does not depend on how many look-alikes the test includes. Results: outputs/eval_embeddings/.
"""
import argparse
import csv
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.agents.normalization import SIM_THRESHOLD  # noqa: E402
from src.config import EMBED, OUTPUTS  # noqa: E402
from src.tools import ontostore  # noqa: E402

DEFAULT_MODELS = ["nomic-embed-text", "nomic-embed-text|clustering: ", "mxbai-embed-large", "snowflake-arctic-embed2",
                  "embeddinggemma|task: sentence similarity | query: ", "granite-embedding:278m"]
ONTOLOGIES = ("MDS-Onto", "PMDCO", "CCO", "RO", "BFO")
STOP = {"of", "the", "a", "an", "and", "or", "in", "on", "for", "to", "by", "with", "at", "process", "entity"}


def readable(label):
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label).replace("_", " ").strip()


def form(label):
    s = re.sub(r"[^a-z0-9]+", " ", readable(label).lower()).strip()
    return " ".join(w[:-1] if w.endswith("s") and len(w) > 3 else w for w in s.split())


def words(label):
    return {w for w in form(label).split() if w not in STOP and len(w) > 2}


def pairs(seed=1):
    rng = random.Random(seed)
    rows = ontostore._db().execute("SELECT iri, ontology, kind, deprecated FROM terms").fetchall()
    terms = {}
    for iri, ont, kind, dep in rows:
        if dep or kind != "class" or ont not in ONTOLOGIES:
            continue
        t = ontostore.term(iri)
        labels = list(dict.fromkeys(readable(x["text"]) for x in t["labels"] if x["text"].strip()))
        if labels:
            terms[iri] = {"ont": ont, "labels": labels, "forms": {form(x) for x in labels}, "parents": t["parents"]}
    children, by_word = {}, {}
    for iri, t in terms.items():
        for p in t["parents"]:
            children.setdefault(p, []).append(iri)
        for w in words(t["labels"][0]):
            by_word.setdefault(w, []).append(iri)
    out = []
    for iri, t in terms.items():
        pref = t["labels"][0]
        alts = [a for a in t["labels"][1:] if form(a) != form(pref)]
        if not alts:
            continue
        for a in alts:
            out.append({"a": pref, "b": a, "same": 1, "kind": "synonym", "ontology": t["ont"]})

        def other(pool, kind):
            pool = [o for o in pool if o != iri and not (terms[o]["forms"] & t["forms"])]
            if pool:
                o = rng.choice(pool)
                out.append({"a": pref, "b": terms[o]["labels"][0], "same": 0, "kind": kind, "ontology": t["ont"]})
        other([c for p in t["parents"] for c in children.get(p, [])], "sibling")
        other([o for w in words(pref) for o in by_word.get(w, [])], "shared word")
    return out


def embed(client, model, prefix, texts, batch=100):
    vecs = {}
    todo = list(dict.fromkeys(texts))
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        res = client.embeddings.create(model=model, input=[prefix + t for t in chunk])
        for t, d in zip(chunk, res.data):
            v = np.array(d.embedding, dtype=float)
            vecs[t] = v / (np.linalg.norm(v) + 1e-12)
    return vecs


def auc(pos, neg):
    """Probability a synonym pair scores above a look-alike pair (Mann-Whitney)."""
    allv = np.concatenate([pos, neg])
    ranks = allv.argsort().argsort() + 1.0
    return (ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def evaluate(cos, same, kinds):
    pos, neg = cos[same == 1], cos[same == 0]
    at = lambda t: ((pos >= t).mean(), (neg >= t).mean())  # noqa: E731
    t05 = float(np.quantile(neg, 0.95))
    r_cur, f_cur = at(SIM_THRESHOLD)
    r05, _ = at(t05)
    out = {"auc": auc(pos, neg), f"recall@{SIM_THRESHOLD}": r_cur, f"fpr@{SIM_THRESHOLD}": f_cur,
           "threshold_fpr5": t05, "recall_fpr5": r05,
           "median_synonym": float(np.median(pos)), "median_lookalike": float(np.median(neg))}
    for k in ("sibling", "shared word"):
        out[f"fpr5_{k.replace(' ', '_')}"] = float((cos[kinds == k] >= t05).mean())
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS, help='"name" or "name|prefix"')
    ap.add_argument("--base-url", default=EMBED["base_url"], help="OpenAI-compatible endpoint (default: EMBED)")
    ap.add_argument("--api-key-env", help="environment variable holding the key (hosted endpoints)")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    ontostore.require()
    data = pairs(args.seed)
    same = np.array([p["same"] for p in data])
    kinds = np.array([p["kind"] for p in data])
    print(f"{int(same.sum())} synonym pairs, {int((same == 0).sum())} look-alike pairs from {', '.join(ONTOLOGIES)}")
    out = OUTPUTS / "eval_embeddings" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    client = OpenAI(base_url=args.base_url, api_key=os.environ.get(args.api_key_env or "", "") or "none")
    results = []
    for spec in args.models:
        model, _, prefix = spec.partition("|")
        try:
            vecs = embed(client, model, prefix, [p["a"] for p in data] + [p["b"] for p in data])
        except Exception as e:  # a model that isn't pulled shouldn't stop the others
            print(f"{spec}: skipped ({type(e).__name__}: {str(e)[:120]})")
            continue
        cos = np.array([vecs[p["a"]] @ vecs[p["b"]] for p in data])
        for p, c in zip(data, cos):
            p[spec] = round(float(c), 4)
        r = {"model": spec, **evaluate(cos, same, kinds)}
        results.append(r)
        print(f"{spec:52} AUC {r['auc']:.3f} | at {SIM_THRESHOLD}: recall {r[f'recall@{SIM_THRESHOLD}']:.0%}, "
              f"look-alikes {r[f'fpr@{SIM_THRESHOLD}']:.0%} | threshold {r['threshold_fpr5']:.2f} lets 5% through, "
              f"recall {r['recall_fpr5']:.0%}")
    if not results:
        sys.exit("no model could be embedded; is the endpoint running and are the models pulled?")
    with open(out / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(results[0]))
        w.writeheader()
        w.writerows({k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()} for r in results)
    with open(out / "pairs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(data[0]))
        w.writeheader()
        w.writerows(data)
    print(f"results: {out / 'results.csv'}; every pair with each model's cosine: {out / 'pairs.csv'}")


if __name__ == "__main__":
    main()
