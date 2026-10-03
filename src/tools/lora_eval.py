"""Score a model (base or fine-tuned, served by the active LLM profile) on the held-out LoRA test split.

Per task: JSON validity, plus
  category  - category accuracy          parent - parent exact match; parent is a correct ancestor
  definitions - similarity to the gold definition; synonyms / disjointness - precision, recall, F1
  filter    - kept-candidate precision, recall, F1
  align     - mapping precision, recall, F1; relation accuracy on correct mappings
  restrict  - property precision, recall, F1 (any fitting property counts); share of vague/ill-fitting relations dropped
  extract   - concept-label and causal-pair F1 against the teacher
Writes outputs/lora/eval/<model>-<time>.json and a row in outputs/lora/eval_summary.csv.
"""
import json
import re
import time
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher

from src.agents.base import parse_json
from src.config import LLM_PROFILE
from src.tools import llm, reports
from src.tools.lora_data import OUT
from src.tools.progress import log


def _prf(pred: set, gold: set, acc: dict, name: str):
    acc[f"{name}_tp"] += len(pred & gold)
    acc[f"{name}_pred"] += len(pred)
    acc[f"{name}_gold"] += len(gold)


def _by_id(obj, key):
    return {r.get("id"): r for r in (obj or {}).get(key, []) if isinstance(r, dict)}


def score(task: str, pred: dict, gold: dict, meta: dict, acc: dict):
    if task == "category":
        p = _by_id(pred, "classes")
        for cid, g in _by_id(gold, "classes").items():
            acc["categories"] += 1
            acc["category_correct"] += str(p.get(cid, {}).get("category", "")).strip().lower() == g["category"]
    elif task == "definitions":
        p = _by_id(pred, "classes")
        for cid, g in _by_id(gold, "classes").items():
            acc["definitions"] += 1
            acc["definition_similarity"] += SequenceMatcher(None, str(p.get(cid, {}).get("definition", "")).lower(),
                                                            g["definition"].lower()).ratio()
    elif task == "synonyms":
        p = _by_id(pred, "classes")
        for cid, g in _by_id(gold, "classes").items():
            _prf({str(a).lower() for a in p.get(cid, {}).get("alt_labels", []) or []},
                 {a.lower() for a in g["alt_labels"]}, acc, "synonym")
    elif task == "disjointness":
        p = _by_id(pred, "classes")
        for cid, g in _by_id(gold, "classes").items():
            _prf(set(map(str, p.get(cid, {}).get("disjoint_with", []) or [])), set(g["disjoint_with"]), acc, "disjoint")
    elif task == "filter":
        pairs = lambda obj: {(str(k.get("id")), str(n)) for k in (obj or {}).get("keep", []) if isinstance(k, dict)
                             for n in (k.get("candidates") or []) if isinstance(k.get("candidates"), list)}
        _prf(pairs(pred), pairs(gold), acc, "keep")
    elif task in ("hierarchy", "parent"):
        p = _by_id(pred, "classes")
        for cid, g in _by_id(gold, "classes").items():
            guess = str(p.get(cid, {}).get("parent", "")).strip()
            acc["parents"] += 1
            acc["parent_exact"] += guess == g["parent"]
            acc["parent_ancestor"] += guess in meta["acceptable"].get(cid, [])
    elif task == "enrich":
        p = _by_id(pred, "classes")
        for cid, g in _by_id(gold, "classes").items():
            q = p.get(cid, {})
            acc["definitions"] += 1
            acc["definition_similarity"] += SequenceMatcher(None, str(q.get("definition", "")).lower(),
                                                            g["definition"].lower()).ratio()
            _prf({(r.get("p"), r.get("o")) for r in q.get("restrictions", []) if isinstance(r, dict)},
                 {(r["p"], r["o"]) for r in g["restrictions"]}, acc, "restriction")
            _prf({str(a).lower() for a in q.get("alt_labels", [])}, {a.lower() for a in g["alt_labels"]}, acc, "synonym")
            _prf(set(map(str, q.get("disjoint_with", []))), set(g["disjoint_with"]), acc, "disjoint")
    elif task == "align":
        pm = {(m.get("id"), m.get("candidate")): m.get("relation") for m in (pred or {}).get("mappings", [])
              if isinstance(m, dict)}
        gm = {(m["id"], m["candidate"]): m["relation"] for m in gold["mappings"]}
        _prf(set(pm), set(gm), acc, "mapping")
        hits = set(pm) & set(gm)
        acc["relation_checked"] += len(hits)
        acc["relation_correct"] += sum(pm[k] == gm[k] for k in hits)
    elif task == "restrict":
        prop = lambda v: str(v or "").strip().lower().removeprefix("p:").strip()
        said = {(str(cid), str(r.get("o"))): prop(r.get("p")) for cid, q in _by_id(pred, "classes").items()
                for r in q.get("restrictions", []) if isinstance(r, dict)}
        for pair, ok in meta["acceptable"].items():
            cid, o = pair.split("|")
            if ok:
                acc["restriction_gold"] += 1
                acc["restriction_tp"] += said.get((cid, o)) in {prop(k) for k in ok}
            else:
                acc["drops"] += 1
                acc["drops_correct"] += (cid, o) not in said
        acc["restriction_pred"] += len(said)
        norm = lambda s: re.sub(r"\s+", " ", str(s).lower()).strip()
        rows = lambda obj, f: [r for r in (obj or {}).get(f, []) if isinstance(r, dict)]
        if "concepts" in gold:  # combined call or concepts pass: compare by label
            lab = lambda obj: {c.get("id"): norm(c.get("label")) for c in rows(obj, "concepts")}
            pl, gl = lab(pred), lab(gold)
            _prf(set(pl.values()), set(gl.values()), acc, "concept")
            if "causal" in gold:
                pairs = lambda obj, m: {(m.get(r.get("cause")), m.get(r.get("effect"))) for r in rows(obj, "causal")}
                _prf(pairs(pred, pl), pairs(gold, gl), acc, "causal")
        else:  # later passes share the input concept list, so ids are comparable
            if "causal" in gold:
                _prf({(r.get("cause"), r.get("effect")) for r in rows(pred, "causal")},
                     {(r.get("cause"), r.get("effect")) for r in rows(gold, "causal")}, acc, "causal")
            if "relations" in gold:
                _prf({(r.get("s"), r.get("p"), r.get("o")) for r in rows(pred, "relations")},
                     {(r.get("s"), r.get("p"), r.get("o")) for r in rows(gold, "relations")}, acc, "relation")
            if "measurements" in gold:
                _prf({(r.get("concept"), norm(r.get("value"))) for r in rows(pred, "measurements")},
                     {(r.get("concept"), norm(r.get("value"))) for r in rows(gold, "measurements")}, acc, "measurement")

def _summarize(acc: dict) -> dict:
    out = {"examples": acc["examples"], "json_valid": round(acc["valid"] / acc["examples"], 3) if acc["examples"] else None}
    for name in ("restriction", "synonym", "disjoint", "keep", "mapping", "concept", "causal", "relation", "measurement"):
        if acc[f"{name}_gold"] or acc[f"{name}_pred"]:
            p = acc[f"{name}_tp"] / acc[f"{name}_pred"] if acc[f"{name}_pred"] else 0
            r = acc[f"{name}_tp"] / acc[f"{name}_gold"] if acc[f"{name}_gold"] else 0
            out.update({f"{name}_precision": round(p, 3), f"{name}_recall": round(r, 3),
                        f"{name}_f1": round(2 * p * r / (p + r), 3) if p + r else 0})
    if acc["categories"]:
        out["category_accuracy"] = round(acc["category_correct"] / acc["categories"], 3)
    if acc["parents"]:
        out["parent_exact"] = round(acc["parent_exact"] / acc["parents"], 3)
        out["parent_ancestor"] = round(acc["parent_ancestor"] / acc["parents"], 3)
    if acc["definitions"]:
        out["definition_similarity"] = round(acc["definition_similarity"] / acc["definitions"], 3)
    if acc["drops"]:
        out["dropped_correctly"] = round(acc["drops_correct"] / acc["drops"], 3)
    if acc["relation_checked"]:
        out["relation_accuracy"] = round(acc["relation_correct"] / acc["relation_checked"], 3)
    out["mean_latency_s"] = round(acc["latency"] / acc["examples"], 2) if acc["examples"] else None
    out["output_tokens"] = acc["output_tokens"]
    return out


def run(model: str, limit: int | None = None) -> dict:
    rows = [json.loads(line) for line in (OUT / "data" / "test.jsonl").read_text(encoding="utf-8").splitlines() if line]
    rows = rows[:limit] if limit else rows
    per_task = defaultdict(lambda: defaultdict(float))
    log(f"evaluating {model} (profile {LLM_PROFILE}) on {len(rows)} held-out examples")
    for n, ex in enumerate(rows, 1):
        system, user, answer = (m["content"] for m in ex["messages"])
        t0 = time.perf_counter()
        try:
            text, usage = llm.chat(system, user, model)
        except Exception as e:
            log(f"  {n}/{len(rows)} {ex['task']}: call failed ({type(e).__name__}: {e})")
            text, usage = "", llm.Usage()
        pred = parse_json(text)
        acc = per_task[ex["task"]]
        acc["examples"] += 1
        acc["valid"] += pred is not None
        acc["latency"] += time.perf_counter() - t0
        acc["output_tokens"] += usage.output_tokens
        score(ex["task"], pred or {}, json.loads(answer), ex["meta"], acc)
        if n % 10 == 0 or n == len(rows):
            log(f"  {n}/{len(rows)} scored")
    result = {"model": model, "profile": LLM_PROFILE, "evaluated": datetime.now().isoformat(timespec="seconds"),
              "tasks": {task: _summarize(acc) for task, acc in sorted(per_task.items())}}
    folder = OUT / "eval"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (folder / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', model)}-{stamp}.json").write_text(json.dumps(result, indent=1),
                                                                                    encoding="utf-8")
    row = {"run_id": f"{model}-{stamp}", "model": model, "profile": LLM_PROFILE, "evaluated": result["evaluated"]}
    for task, metrics in result["tasks"].items():
        row.update({f"{task}_{k}": v for k, v in metrics.items()})
    reports.upsert_eval(OUT / "eval_summary.csv", row)
    for task, metrics in result["tasks"].items():
        log(f"{task}: {metrics}")
    return result
