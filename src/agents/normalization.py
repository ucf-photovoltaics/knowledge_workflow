"""Normalization agent: per-paper concepts -> canonical corpus concepts, importance scores, causal order.

Lexical merging and scoring are deterministic; embeddings propose synonym clusters and the LLM only settles those.
"""
import math
import re
from collections import Counter, defaultdict

from src.agents.base import Agent, compact, items, key, load_prompt
from src.config import EMBED
from src.tools import llm, upper
from src.tools.progress import log

WEIGHTS = {"papers": 0.35, "mentions": 0.25, "centrality": 0.20, "causal": 0.10, "figures": 0.10}
TIERS = ((0.10, "core"), (0.30, "major"), (1.00, "minor"))  # cumulative share of ranked concepts
SIM_THRESHOLD = 0.85
MAX_CLUSTER = 12
TERMS_PER_CALL = 150


def norm_key(label: str) -> str:
    words = re.sub(r"\s+", " ", re.sub(r"[-_/]", " ", label.lower())).strip().split()
    if words:
        w = words[-1]
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("s") and not w.endswith(("ss", "us", "is")) and len(w) > 3:
            w = w[:-1]
        words[-1] = w
    return " ".join(words)


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)


POLARITIES = set(upper.menus()["causal_polarity"])  # an unknown or missing polarity becomes "affects"


class NormalizationAgent(Agent):
    name = "normalization"

    def run(self, papers: list[dict]) -> dict:
        for p in papers:  # small models sometimes return a list or dict where a string belongs
            p["concepts"] = [_clean_concept(c) for c in p["concepts"] if isinstance(c, dict) and _text(c.get("label"))]
            p["relations"] = [{**r, "p": pred} for r in p.get("relations", []) if isinstance(r, dict)
                              and (pred := re.sub(r"[^a-z0-9]+", "_", str(_text(r.get("p")) or "").lower()).strip("_"))]
            p["causal"] = [{**r, "polarity": _polarity(r.get("polarity"))} for r in p.get("causal", [])
                           if isinstance(r, dict)]
        self.stats = {"concept_occurrences": sum(len(p["concepts"]) for p in papers)}
        log(f"joining {self.stats['concept_occurrences']:,} concept occurrences from {len(papers)} papers")
        groups = self._lexical_groups(papers)
        self.stats["lexical_groups"] = len(groups)
        log(f"lexical merge (same wording and plurals only; synonyms require model review): {len(groups):,} groups")
        groups = self._semantic_merge(groups)
        concepts, cmap = self._canonical(groups)
        log(f"canonical concepts: {len(concepts):,} ({self.stats['semantic_merges']} merged by meaning)")
        self._settle_types(concepts)
        relations = _aggregate(papers, cmap, "relations", ("s", "p", "o"), ("s", "o"))
        causal = _aggregate(papers, cmap, "causal", ("cause", "effect", "polarity"), ("cause", "effect"))
        measurements = [{**m, "concept": cmap[(p["key"], m["concept"])], "paper": p["key"],
                         "entity": cmap.get((p["key"], m.get("entity")), "")}
                        for p in papers for m in p.get("measurements", []) if (p["key"], m["concept"]) in cmap]
        log(f"joined edges: {len(relations):,} distinct relations, {len(causal):,} distinct causal edges, "
            f"{len(measurements):,} reported values")
        contradictions = _contradictions(causal)
        self.stats["causal_contradictions"] = len(contradictions)
        if contradictions:
            log(f"causal contradictions across papers (kept, flagged): {len(contradictions)}")
        _score(concepts, relations, causal)
        tiers = Counter(c["tier"] for c in concepts)
        log(f"importance scored: core {tiers['core']}, major {tiers['major']}, minor {tiers['minor']}")
        order = _causal_order(concepts, causal)
        log(f"causal order: {order['n_nodes']} concepts, depth {order['max_rank']}, {len(order['cycles'])} cycles")
        log("writing corpus summary")
        summary = self._summarize(concepts, causal, order, len(papers))
        return {"concepts": concepts, "relations": relations, "causal": causal, "measurements": measurements,
                "contradictions": contradictions,
                "causal_order": order,
                "summary": summary, "stats": self.stats}

    @staticmethod
    def _lexical_groups(papers: list[dict]) -> list[dict]:
        uf, members = _UnionFind(), []
        for p in papers:
            for c in p["concepts"]:
                k = norm_key(c["label"])
                uf.find(k)
                members.append((p["key"], c, k))
        groups = defaultdict(list)
        for key, c, k in members:
            groups[uf.find(k)].append((key, c))
        return [{"members": m, "label": None} for m in groups.values()]

    def _semantic_merge(self, groups: list[dict]) -> list[dict]:
        if not EMBED["model"] or len(groups) < 2:
            self.stats["semantic_merges"] = 0
            log("embedding merge: off (no EMBED model)")
            return groups
        log(f"embedding {len(groups):,} labels with {EMBED['model']}")
        import numpy as np
        labels = [Counter(c["label"] for _, c in g["members"]).most_common(1)[0][0] for g in groups]
        try:
            vectors, usage = llm.embed(labels)
        except Exception as e:  # never lose a run to the embedding service; fall back to lexical merging
            self.stats.update(semantic_merges=0, embedding_error=f"{type(e).__name__}: {e}"[:300])
            log(f"embedding failed ({type(e).__name__}); continuing with lexical merging only")
            return groups
        self.ledger.log(self.name, "embeddings", EMBED["model"], usage)
        log(f"  embedded in {usage.latency_s:.1f}s")
        v = np.array(vectors, dtype=float)
        v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-12
        rows, cols = np.where(np.triu(v @ v.T, 1) >= SIM_THRESHOLD)
        uf = _UnionFind()
        for a, b in zip(rows.tolist(), cols.tolist()):
            uf.union(a, b)
        comps = defaultdict(list)
        for a in set(rows.tolist()) | set(cols.tolist()):
            comps[uf.find(a)].append(a)
        clusters = [c[i:i + MAX_CLUSTER] for c in (sorted(c) for c in comps.values()) for i in range(0, len(c), MAX_CLUSTER)]
        clusters = [c for c in clusters if len(c) > 1]
        self.stats["candidate_clusters"] = len(clusters)

        def term(i):
            c = groups[i]["members"][0][1]
            return {"id": f"g{i}", "label": labels[i], "type": c.get("type", ""), "def": c.get("definition", "")[:120]}

        batches, current, size = [], [], 0
        for cluster in clusters:
            if current and size + len(cluster) > TERMS_PER_CALL:
                batches.append(current)
                current, size = [], 0
            current.append(cluster)
            size += len(cluster)
        if current:
            batches.append(current)

        log(f"{len(clusters)} look-alike clusters (similarity >= {SIM_THRESHOLD}) -> {len(batches)} model call(s) to settle them")
        merged, preferred = _UnionFind(), {}
        for n, batch in enumerate(batches, 1):
            out = self.call(compact({"clusters": [[term(i) for i in c] for c in batch]}), item="synonym_clusters",
                            label=f"synonym clusters {n}/{len(batches)}")
            allowed = [{f"g{i}" for i in c} for c in batch]
            for m in items(out, "merges"):
                ids = [x for x in m.get("ids", []) if isinstance(x, str)]
                if len(ids) > 1 and any(set(ids) <= a for a in allowed):
                    idx = [int(x[1:]) for x in ids]
                    for i in idx[1:]:
                        merged.union(i, idx[0])
                    preferred[idx[0]] = m.get("label")

        out = defaultdict(lambda: {"members": [], "label": None})
        for i, g in enumerate(groups):
            out[merged.find(i)]["members"] += g["members"]
        for i, label in preferred.items():
            if label:
                out[merged.find(i)]["label"] = label
        self.stats["semantic_merges"] = len(groups) - len(out)
        return list(out.values())

    @staticmethod
    def _canonical(groups: list[dict]) -> tuple[list[dict], dict]:
        # Groups that end up with the same name are one concept: a label the model gave a merged cluster can equal
        # the label of a group it did not see (two "boron-doped emitter" concepts stopped a run at placement).
        named = {}
        for g in groups:
            label = g["label"] or Counter(c["label"] for _, c in g["members"]).most_common(1)[0][0]
            same = named.setdefault(norm_key(label), {"members": [], "label": g["label"]})
            same["members"] += g["members"]
            same["label"] = same["label"] or g["label"]
        groups = list(named.values())
        concepts, cmap = [], {}
        for g in sorted(groups, key=lambda g: -len(g["members"])):
            kid = f"k{len(concepts) + 1}"
            members = g["members"]
            label = g["label"] or Counter(c["label"] for _, c in members).most_common(1)[0][0]
            alts, defs = {}, {}
            for key, c in members:
                for t in [c["label"], *c.get("synonyms", [])]:
                    if t.lower() != label.lower():
                        alts.setdefault(t.lower(), t)
                d = c.get("definition", "").strip()
                if d:
                    defs.setdefault(d.lower(), {"text": d, "paper": key})
                cmap[(key, c["id"])] = kid
            papers = sorted({key for key, _ in members})
            concepts.append({
                "id": kid, "label": label, "alt_labels": sorted(alts.values()),
                "type": Counter(c.get("type", "") for _, c in members).most_common(1)[0][0],
                "type_votes": dict(Counter(c.get("type", "") for _, c in members if c.get("type"))),
                "definitions": sorted(defs.values(), key=lambda d: -len(d["text"]))[:3],
                "papers": papers, "n_papers": len(papers),
                "mentions": sum(c.get("mentions", 0) for _, c in members),
                "figures": sorted({f"{key}:{f}" for key, c in members for f in c.get("figures", [])}),
            })
        return concepts, cmap

    def _settle_types(self, concepts: list[dict]):
        """One narrow call for concepts the papers typed differently (the rest keep their single type)."""
        mixed = [c for c in concepts if len(c.get("type_votes", {})) > 1]
        self.stats["type_conflicts"] = len(mixed)
        if not mixed:
            return
        log(f"settling types for {len(mixed)} concepts typed differently across papers")
        by_id, settled = {c["id"]: c for c in mixed}, 0
        rows = [{"id": c["id"], "label": c["label"], "types": sorted(c["type_votes"], key=lambda t: -c["type_votes"][t]),
                 "def": (c["definitions"][0]["text"] if c["definitions"] else "")[:140]} for c in mixed]
        for t in self.call_rows(rows, load_prompt("normalization_types"), "type_conflicts", "types", "type",
                                label="types"):
            c = by_id.get(key(t.get("id")))
            if c and t.get("type") in c["type_votes"]:  # only one of the types the papers actually used
                c["type"], settled = t["type"], settled + 1
        self.stats["types_settled_by_model"] = settled
        self.stats["row_coverage"] = {k: dict(v) for k, v in self.row_stats.items()}

    def _summarize(self, concepts: list[dict], causal: list[dict], order: dict, n_papers: int) -> dict:
        label = {c["id"]: c["label"] for c in concepts}
        user = compact({
            "n_papers": n_papers,
            "top_concepts": [{"label": c["label"], "tier": c["tier"], "papers": c["n_papers"], "mentions": c["mentions"]}
                             for c in concepts[:40]],
            "top_causal": [f"{label[r['cause']]} -{r['polarity']}-> {label[r['effect']]} (papers: {r['support']})"
                           for r in sorted(causal, key=lambda r: -r["support"])[:20]],
            "chains": order["chains"][:5]})
        return self.call(user, item="corpus_summary", system=load_prompt("normalization_summary"), label="corpus summary")


def _text(v):
    """Model-supplied field as a plain string (small models sometimes return a dict or list for one)."""
    if v is None or isinstance(v, (str, bool, int, float)):
        return v
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_text(x)}" for k, x in v.items())
    return "; ".join(str(_text(x)) for x in v) if isinstance(v, list) else str(v)


def _polarity(v) -> str:
    pol = str(_text(v) or "").strip().lower()
    return pol if pol in POLARITIES else "affects"


def _clean_concept(c: dict) -> dict:
    as_list = lambda v: [str(_text(x)) for x in (v if isinstance(v, list) else [v]) if _text(x)]
    return {**c, "label": str(_text(c["label"])).strip(), "type": str(_text(c.get("type")) or "").strip(),
            "definition": str(_text(c.get("definition")) or "").strip(), "synonyms": as_list(c.get("synonyms")),
            "figures": as_list(c.get("figures")),
            "mentions": c.get("mentions") if isinstance(c.get("mentions"), int) else 0}


def _aggregate(papers, cmap, field, keys, ends) -> list[dict]:
    agg = {}
    for p in papers:
        for r in p[field]:
            a, b = cmap.get((p["key"], r[ends[0]])), cmap.get((p["key"], r[ends[1]]))
            if not a or not b or a == b:
                continue
            r = {**{k: _text(v) for k, v in r.items() if k not in ends}, ends[0]: a, ends[1]: b}
            e = agg.setdefault(tuple(r.get(k) for k in keys),
                               {**{k: r.get(k) for k in keys}, "papers": set(), "conditions": set(), "evidence": []})
            e["papers"].add(p["key"])
            if r.get("condition"):
                e["conditions"].add(r["condition"])
            if r.get("evidence") and len(e["evidence"]) < 2:
                e["evidence"].append({"paper": p["key"], "text": r["evidence"], "verified": r.get("verified"),
                                      "status": r.get("evidence_status")})
    out = []
    for e in agg.values():
        e["papers"], e["support"] = sorted(e["papers"]), len(e["papers"])
        e["conditions"] = sorted(e["conditions"])
        if not e["conditions"]:
            del e["conditions"]
        out.append(e)
    return sorted(out, key=lambda e: -e["support"])


OPPOSED = ({"increases", "enables"}, {"decreases", "prevents"})


def _contradictions(causal: list[dict]) -> list[dict]:
    """Same cause and effect reported with opposite polarity (by different papers or conditions).
    Nothing is merged or dropped; the conditions usually explain the disagreement."""
    by_pair = defaultdict(list)
    for r in causal:
        by_pair[(r["cause"], r["effect"])].append(r)
    out = []
    for (cause, effect), rows in by_pair.items():
        pols = {r["polarity"] for r in rows}
        if pols & OPPOSED[0] and pols & OPPOSED[1]:
            out.append({"cause": cause, "effect": effect,
                        "claims": [{"polarity": r["polarity"], "papers": r["papers"],
                                    "conditions": r.get("conditions", [])} for r in rows]})
    return out


def _pagerank(nodes, edges, d=0.85, iters=50) -> dict:
    if not nodes:
        return {}
    out = defaultdict(set)
    for a, b in edges:
        out[a].add(b)
    n, pr = len(nodes), dict.fromkeys(nodes, 1 / len(nodes))
    for _ in range(iters):
        dangling = sum(pr[v] for v in nodes if not out[v])
        nxt = dict.fromkeys(nodes, (1 - d) / n + d * dangling / n)
        for v in nodes:
            for w in out[v]:
                nxt[w] += d * pr[v] / len(out[v])
        pr = nxt
    return pr


def _score(concepts, relations, causal):
    pr = _pagerank([c["id"] for c in concepts],
                   [(r["s"], r["o"]) for r in relations] + [(r["cause"], r["effect"]) for r in causal])
    c_in, c_out = Counter(r["effect"] for r in causal), Counter(r["cause"] for r in causal)
    raw = {c["id"]: {"papers": c["n_papers"], "mentions": math.log1p(c["mentions"]), "centrality": pr[c["id"]],
                     "causal": c_in[c["id"]] + c_out[c["id"]], "figures": len(c["figures"])} for c in concepts}
    top = {k: max((r[k] for r in raw.values()), default=0) or 1 for k in WEIGHTS}
    for c in concepts:
        parts = {k: raw[c["id"]][k] / top[k] for k in WEIGHTS}
        c.update(score=round(sum(WEIGHTS[k] * v for k, v in parts.items()), 4),
                 score_parts={k: round(v, 3) for k, v in parts.items()},
                 pagerank=round(pr[c["id"]], 6), causal_in=c_in[c["id"]], causal_out=c_out[c["id"]])
    concepts.sort(key=lambda c: -c["score"])
    for rank, c in enumerate(concepts, 1):
        c["rank"] = rank
        c["tier"] = next(t for share, t in TIERS if rank <= max(1, round(share * len(concepts))) or share == 1.0)


def _scc(nodes, succ) -> list[list]:
    """Tarjan's strongly connected components (iterative)."""
    index, low, on, stack, comps, counter = {}, {}, set(), [], [], 0
    for root in nodes:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on.add(root)
        work = [(root, iter(sorted(succ[root])))]
        while work:
            v, it = work[-1]
            w = next(it, None)
            if w is None:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[v])
                if low[v] == index[v]:
                    comp = []
                    while True:
                        x = stack.pop()
                        on.discard(x)
                        comp.append(x)
                        if x == v:
                            break
                    comps.append(comp)
            elif w not in index:
                index[w] = low[w] = counter
                counter += 1
                stack.append(w)
                on.add(w)
                work.append((w, iter(sorted(succ[w]))))
            elif w in on:
                low[v] = min(low[v], index[w])
    return comps


def _causal_order(concepts, causal) -> dict:
    """Causal rank = longest cause->effect path depth after collapsing cycles; chains = deepest paths."""
    label = {c["id"]: c["label"] for c in concepts}
    succ = defaultdict(set)
    for r in causal:
        succ[r["cause"]].add(r["effect"])
    nodes = sorted(set(succ) | {w for s in list(succ.values()) for w in s})
    comps = _scc(nodes, succ)
    comp_of = {v: i for i, comp in enumerate(comps) for v in comp}
    dag = defaultdict(set)
    for v in nodes:
        for w in succ[v]:
            if comp_of[v] != comp_of[w]:
                dag[comp_of[v]].add(comp_of[w])
    indeg = Counter(b for a in dag for b in dag[a])
    queue = [i for i in range(len(comps)) if not indeg[i]]
    rank, pred = dict.fromkeys(range(len(comps)), 0), {}
    while queue:
        a = queue.pop()
        for b in dag[a]:
            if rank[a] + 1 > rank[b]:
                rank[b], pred[b] = rank[a] + 1, a
            indeg[b] -= 1
            if not indeg[b]:
                queue.append(b)
    for c in concepts:
        c["causal_rank"] = rank[comp_of[c["id"]]] if c["id"] in comp_of else None
    chains = []
    for s in sorted((i for i in rank if rank[i] > 0 and not dag[i]), key=lambda i: -rank[i])[:10]:
        path = [s]
        while path[-1] in pred:
            path.append(pred[path[-1]])
        chains.append([" / ".join(label[v] for v in comps[i]) for i in reversed(path)])
    return {"n_nodes": len(nodes), "n_edges": sum(len(s) for s in succ.values()),
            "max_rank": max(rank.values(), default=0), "chains": chains,
            "cycles": [[label[v] for v in comp] for comp in comps if len(comp) > 1]}
