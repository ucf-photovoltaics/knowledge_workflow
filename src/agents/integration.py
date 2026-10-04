"""Integration agent: mappings between the domain ontologies of separate runs (the cross-domain stage).

Candidate pairs are deterministic: the same normalized label or synonym, a class IRI already shared by two domains
(runs from before domain-scoped IRIs), and mutual nearest neighbours by label embedding. The model then chooses the
relation of each pair. Checks keep owl:equivalentClass only for same-label pairs in the same BFO category, and never
let an equivalence cluster join two classes of one domain; everything else becomes a SKOS mapping, so the master
ontology does not change the hierarchy of any domain ontology. Every mapping records its source and confidence."""
import re
from collections import Counter, defaultdict
from itertools import combinations

from src.agents.base import Agent, key
from src.config import EMBED, INTEGRATION, MAPPING, tier
from src.tools import llm
from src.tools.lexical import match_key
from src.tools.progress import log

RELATIONS = ("equivalent", "exact", "close", "broader", "narrower", "none")
KIND_RANK = {"shared_iri": 0, "label": 1, "synonym": 2, "embedding": 3}
ID_LIKE = re.compile(r"(?:[cnf]\d+\W*)+", re.I)  # model-internal ids that leaked into labels (n1, f3, c7-c8)
ID_PREFIX = re.compile(r"[cnf]\d+\s*[(:]", re.I)  # "n1 (Auger recombination)"


class _Clusters:
    """Union-find over class IRIs that remembers which domains each cluster holds."""

    def __init__(self):
        self.parent, self.members = {}, {}

    def find(self, x):
        self.parent.setdefault(x, x)
        self.members.setdefault(x, {x})
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def joins_same_domain(self, a, b, domain_of) -> bool:
        ra, rb = self.find(a), self.find(b)
        return ra != rb and bool({domain_of[m] for m in self.members[ra]} & {domain_of[m] for m in self.members[rb]})

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra
            self.members[ra] |= self.members.pop(rb)


def _names(c: dict) -> set[str]:
    return {k for x in [c["label"], *c.get("alt_labels", [])] if isinstance(x, str) and (k := match_key(x))}


class IntegrationAgent(Agent):
    name = "integration"

    def __init__(self, ledger):
        super().__init__(ledger)
        self.stats = Counter()

    def run(self, domains: dict[str, list[dict]]) -> dict:
        """domains: domain name -> live classes (iri, label, alt_labels, category, parent_label, definition, ...)."""
        usable = lambda c: (mk := match_key(c["label"])) and not ID_LIKE.fullmatch(mk) and not ID_PREFIX.match(c["label"].strip())
        self.stats["classes_skipped_label_defect"] = sum(1 for cs in domains.values() for c in cs if not usable(c))
        domains = {d: [c for c in cs if usable(c)] for d, cs in domains.items()}  # leaked ids, parentheses-only labels
        pairs = self._candidates(domains)
        mappings = self._decide(pairs)
        clusters = self._clusters(mappings)
        return {"candidates": pairs, "mappings": mappings, "clusters": clusters, "stats": dict(self.stats)}

    def _candidates(self, domains: dict[str, list[dict]]) -> list[dict]:
        found = {}

        def add(a, b, kind, score=None):
            if a["domain"] > b["domain"]:
                a, b = b, a
            k = (a["iri"], b["iri"])
            if a["iri"] == b["iri"]:
                kind = "shared_iri"
            old = found.get(k)
            if old is None or KIND_RANK[kind] < KIND_RANK[old["kind"]]:
                found[k] = {"a": a, "b": b, "kind": kind, "score": score if old is None else old["score"]}
            if score is not None:
                found[k]["score"] = max(found[k]["score"] or 0, score)

        names = {d: defaultdict(list) for d in domains}
        for d, cs in domains.items():
            for c in cs:
                for n in _names(c):
                    names[d][n].append(c)
        for da, db in combinations(sorted(domains), 2):
            for c in domains[da]:
                label = match_key(c["label"])
                for n in _names(c):
                    for o in names[db].get(n, []):
                        add(c, o, "label" if label and label == match_key(o["label"]) else "synonym")
        self._embedding_candidates(domains, add)
        pairs = sorted(found.values(), key=lambda p: (KIND_RANK[p["kind"]], -(p["score"] or 0), p["a"]["iri"], p["b"]["iri"]))
        for i, p in enumerate(pairs, 1):
            p["id"] = f"p{i}"
        self.stats.update({f"candidates_{k}": v for k, v in Counter(p["kind"] for p in pairs).items()})
        log(f"candidate pairs: {len(pairs)} ({dict(Counter(p['kind'] for p in pairs))})")
        return pairs

    def _embedding_candidates(self, domains, add):
        if not EMBED["model"]:
            self.stats["embedding_off"] = 1
            log("embedding candidates: off (no EMBED model); lexical candidates only")
            return
        import numpy as np
        labels = sorted({c["label"] for cs in domains.values() for c in cs})
        try:
            vectors, usage = llm.embed(labels)
        except Exception as e:  # never lose the stage to the embedding service
            self.stats["embedding_error"] = 1
            self.embedding_error = f"{type(e).__name__}: {e}"[:300]
            log(f"embedding failed ({type(e).__name__}); lexical candidates only")
            return
        self.ledger.log(self.name, "embeddings", EMBED["model"], usage)
        v = np.array(vectors, dtype=float)
        v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-12
        row = {lab: i for i, lab in enumerate(labels)}
        self.vectors = (row, v)
        for da, db in combinations(sorted(domains), 2):
            A, B = domains[da], domains[db]
            if not A or not B:
                continue
            sim = v[[row[c["label"]] for c in A]] @ v[[row[c["label"]] for c in B]].T
            best_b, best_a = sim.argmax(axis=1), sim.argmax(axis=0)
            for i, j in enumerate(best_b):
                if best_a[j] == i and sim[i, j] >= INTEGRATION["min_similarity"]:
                    add(A[i], B[j], "embedding", round(float(sim[i, j]), 4))

    def _similarity(self, a, b):
        if not hasattr(self, "vectors"):
            return None
        row, v = self.vectors
        return round(float(v[row[a["label"]]] @ v[row[b["label"]]]), 4)

    def _decide(self, pairs: list[dict]) -> list[dict]:
        for p in pairs:
            if p["score"] is None:
                p["score"] = self._similarity(p["a"], p["b"])
        shared = [p for p in pairs if p["kind"] == "shared_iri"]
        review = [p for p in pairs if p["kind"] != "shared_iri"]
        cap = INTEGRATION["max_model_pairs"]
        self.stats["candidates_unreviewed_over_cap"] = max(0, len(review) - cap)
        review = review[:cap]
        reviewed = {p["id"] for p in review}
        for p in pairs:
            p["reviewed"] = p["id"] in reviewed
        batch = INTEGRATION["batch"][tier(self.name)]
        side = lambda c: {"label": c["label"], "domain": c["domain"], "kind": c["category"], "parent": c["parent_label"],
                          "def": (c.get("definition") or "")[:140], "alt": [a for a in c.get("alt_labels", [])][:3]}
        answers = {}
        log(f"relation for {len(review)} candidate pairs ({-(-len(review) // batch)} call(s); "
            f"{len(shared)} shared IRIs need no review)")
        rows = [{"id": p["id"], "A": side(p["a"]), "B": side(p["b"]),
                 "match": "=" if p["kind"] in ("label", "synonym") else p["score"]} for p in review]
        for r in self.call_rows(rows, self.system, "pairs", "pairs", "relation", size=batch):
            rel = key(r.get("relation"))
            if rel and rel.lower() in RELATIONS:
                answers[key(r.get("id"))] = rel.lower()
        self.stats["failed_calls"] = sum(self.failures.values())
        self.stats.update({f"pairs_{k}": v for k, v in self.row_stats.get("pairs", {}).items()})
        self.stats.update({f"decision_{k}": v for k, v in Counter(answers.values()).items()})
        self.stats["decision_missing"] = sum(1 for p in review if p["id"] not in answers)

        mappings = [self._mapping(p, "shared_iri", "shared_iri", 1.0) for p in shared]
        for p in review:
            rel = answers.get(p["id"])
            same_category = p["a"]["category"] == p["b"]["category"]
            if rel is None:  # no answer: same label and kind is enough for an exact match, as in interop
                if (p["kind"] == "label" and same_category) or \
                        (p["kind"] == "synonym" and same_category and (p["score"] or 0) >= MAPPING["strong_similarity"]):
                    mappings.append(self._mapping(p, "exact", "label_match", 1.0))
                    self.stats["label_match_added"] += 1
                continue
            p["decision"] = rel
            if rel == "none":
                continue
            chosen = rel
            if rel == "equivalent" and not (p["kind"] == "label" and same_category):
                rel = "exact" if p["kind"] in ("label", "synonym") else "close"
            if rel == "exact" and p["kind"] not in ("label", "synonym"):
                rel = "close"  # meaning claimed identical but the names differ
            m = self._mapping(p, rel, "model", 1.0 if p["kind"] == "label" else p["score"])
            if rel != chosen:
                m["downgraded_from"] = chosen
                self.stats[f"downgraded_{chosen}_to_{rel}"] += 1
            mappings.append(m)
        self._guard_equivalence(mappings)
        self.stats.update({f"mappings_{k}": v for k, v in Counter(m["relation"] for m in mappings).items()})
        log(f"mappings: {len(mappings)} ({dict(Counter(m['relation'] for m in mappings))})")
        return mappings

    @staticmethod
    def _mapping(p, relation, source, confidence) -> dict:
        a, b = p["a"], p["b"]
        return {"a_iri": a["iri"], "a_label": a["label"], "a_domain": a["domain"], "a_run": a["run"],
                "b_iri": b["iri"], "b_label": b["label"], "b_domain": b["domain"], "b_run": b["run"],
                "relation": relation, "source": source, "confidence": confidence, "similarity": p["score"],
                "candidate_kind": p["kind"], "category_a": a["category"], "category_b": b["category"], "pair": p["id"]}

    def _guard_equivalence(self, mappings):
        """Equivalence is transitive: an equivalence cluster must never contain two classes of the same domain."""
        domain_of = {}
        for m in mappings:
            domain_of[m["a_iri"]], domain_of[m["b_iri"]] = m["a_domain"], m["b_domain"]
        uf = _Clusters()
        for m in sorted((m for m in mappings if m["relation"] in ("equivalent", "shared_iri")),
                        key=lambda m: (m["relation"] != "shared_iri", -(m["confidence"] or 0))):
            if m["relation"] == "equivalent" and uf.joins_same_domain(m["a_iri"], m["b_iri"], domain_of):
                m["downgraded_from"], m["relation"] = "equivalent", "exact"
                self.stats["downgraded_equivalent_same_domain_cluster"] += 1
                continue
            uf.union(m["a_iri"], m["b_iri"])

    def _clusters(self, mappings) -> list[dict]:
        """Bridge concepts: connected components of equivalent / exact / shared-IRI mappings."""
        uf, info = _Clusters(), {}
        for m in mappings:
            info[m["a_iri"]] = (m["a_domain"], m["a_label"])
            info[m["b_iri"]] = (m["b_domain"], m["b_label"])
            if m["relation"] in ("equivalent", "exact", "shared_iri"):
                uf.union(m["a_iri"], m["b_iri"])
        groups = defaultdict(list)
        for iri in info:
            groups[uf.find(iri)].append(iri)
        out = []
        for members in groups.values():
            doms = sorted({info[i][0] for i in members})
            if len(doms) < 2:
                continue
            labels = Counter(info[i][1] for i in members)
            out.append({"label": labels.most_common(1)[0][0], "domains": doms, "n_domains": len(doms),
                        "members": [{"domain": info[i][0], "label": info[i][1], "iri": i} for i in sorted(members)]})
        out.sort(key=lambda c: (-c["n_domains"], c["label"].lower()))
        self.stats["bridge_concepts"] = len(out)
        self.stats.update({f"bridge_{n}_domains": v for n, v in Counter(c["n_domains"] for c in out).items()})
        return out
