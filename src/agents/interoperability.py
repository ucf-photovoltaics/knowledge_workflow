"""Interoperability agent: commit mappings from classes to external terms (portal and local BFO/CCO candidates),
then assemble, validate (structurally, no reasoner) and emit the ontology as OWL2 JSON-LD.

Mapping checks: exact/equivalent are kept only when the labels (or a synonym) actually match - otherwise they are
downgraded to close; label-matched candidates the model skipped are added when their embedding similarity is
high. Every mapping carries a confidence (1.0 for a label match, else the embedding similarity)."""
from collections import Counter, defaultdict

from src.agents.base import Agent, compact, items, key, load_prompt, targets
from src.config import MAPPING, tier
from src.tools import owl, upper
from src.tools.owl import label_of
from src.tools.progress import log

BATCH = 20
FACET_BATCH = 40
RELATIONS = {"equivalent", "subclass", "exact", "close"}
DOWNGRADE = {"equivalent": "exact", "subclass": "close"}


class InteroperabilityAgent(Agent):
    name = "interoperability"

    def __init__(self, ledger):
        super().__init__(ledger)
        self.stats = Counter()

    def align(self, classes: list[dict]) -> list[dict]:
        by_id = {c["id"]: c for c in classes if not c["excluded"]}
        todo = [c for c in by_id.values() if c.get("candidates")]
        mappings, seen = [], set()
        shown = {c["id"]: set(range(1, len(c["candidates"]) + 1)) for c in todo}
        row = lambda c: {"id": c["id"], "label": c["label"], "parent": label_of(c["parent"], by_id),
                         "def": c.get("definition", "")[:160],
                         "candidates": [[n, x["label"], x["ontology"], x["definition"][:120],
                                         "=" if x.get("label_match") else x.get("score", "")]
                                        for n, x in enumerate(c["candidates"], 1) if n in shown[c["id"]]]}
        if tier(self.name) == "local":  # pass 1: keep only candidates about the same (or a broader) thing
            n_batches = -(-len(todo) // BATCH)
            log(f"mapping pass 1: screening candidates for {len(todo)} classes ({n_batches} call(s))")
            answered = {key(k.get("id")): k.get("candidates") for k in self.call_rows(
                [row(c) for c in todo], load_prompt("interoperability_filter"), "filter", "keep", "candidates", size=BATCH)}
            for c in todo:
                if c["id"] not in answered:
                    continue  # no answer for this class: show all candidates to pass 2
                keep = {int(n) for n in (targets(answered[c["id"]]) or []) if str(n).isdigit()}
                keep |= {n for n, x in enumerate(c["candidates"], 1) if x.get("label_match")}  # never screened out
                self.stats["candidates_screened_out"] += len(shown[c["id"]] - keep)
                shown[c["id"]] &= keep
            todo = [c for c in todo if shown[c["id"]]]
        n_batches = -(-len(todo) // BATCH)
        log(f"{'mapping pass 2: relation for' if tier(self.name) == 'local' else 'aligning'} {len(todo)} classes "
            f"({n_batches} call(s))")
        for i in range(0, len(todo), BATCH):
            out = self.call(compact([row(c) for c in todo[i:i + BATCH]]), item=f"align_{i // BATCH + 1}",
                            label=f"align {i // BATCH + 1}/{n_batches}", soft=True)
            for m in items(out, "mappings", "candidate"):
                c = by_id.get(key(m.get("id")))
                if not c:
                    continue
                rel = key(m.get("relation"))  # a list or dict here used to crash the stage (unhashable)
                rel = rel.lower() if rel else None
                try:
                    n = int(m.get("candidate"))
                except (TypeError, ValueError):
                    continue
                if rel not in RELATIONS or n not in shown[c["id"]]:
                    continue
                cand = c["candidates"][n - 1]
                chosen = rel
                if "qudt.org" in cand["iri"]:  # QUDT quantity kinds/units are individuals, not classes
                    rel = DOWNGRADE.get(rel, rel)
                if rel in ("exact", "equivalent") and not cand.get("label_match"):
                    rel = "close"  # meaning claimed identical but the names differ: keep only as a close match
                if (c["id"], cand["iri"]) not in seen and cand["iri"] != c["iri"]:
                    seen.add((c["id"], cand["iri"]))
                    mappings.append({"id": c["id"], "relation": rel, **cand, "source": "model",
                                     "confidence": 1.0 if cand.get("label_match") else cand.get("score"),
                                     **({"downgraded_from": chosen} if rel != chosen else {})})
        for c in todo:  # same name, and similar in meaning, but not chosen by the model
            for cand in c["candidates"]:
                if cand.get("label_match") and cand.get("score", 0) >= MAPPING["strong_similarity"] \
                        and (c["id"], cand["iri"]) not in seen:
                    seen.add((c["id"], cand["iri"]))
                    mappings.append({"id": c["id"], "relation": "exact", **cand, "source": "label_match",
                                     "confidence": 1.0})
        downgraded = sum(1 for m in mappings if "downgraded_from" in m)
        log(f"mappings: {len(mappings)} ({downgraded} downgraded to close for mismatched names, "
            f"{sum(1 for m in mappings if m['source'] == 'label_match')} added from label matches)")
        return mappings

    def tag_facets(self, classes: list[dict], properties: dict, mappings: list[dict]) -> dict:
        """MDS-Onto study stage(s) and MDSDom domain/subdomain for every class and local property.
        MDS-Onto's own facets on matched terms are passed as hints; invalid names are dropped; anything left
        untagged gets a stage from its concept type and the General domain."""
        f = upper.facets()
        stages = {s.lower(): s for s in f["study_stages"]}
        domains = {d.lower(): d for d in f["domains"]}
        live = {c["id"]: c for c in classes if not c["excluded"]}
        hints = defaultdict(set)
        for c in live.values():
            for x in c.get("candidates", []):
                if x.get("label_match") and x.get("mds"):
                    hints[c["id"]].add(" / ".join(x["mds"].values()))
        for m in mappings:
            if m.get("mds"):
                hints[m["id"]].add(" / ".join(m["mds"].values()))
        rows = [{"id": cid, "label": c["label"], "type": c.get("type", ""), "parent": label_of(c["parent"], live),
                 "def": c.get("definition", "")[:140], "mds": sorted(hints[cid])[:2]} for cid, c in live.items()]
        rows += [{"id": f"p:{name}", "label": name, "type": "relation", "parent": p.get("parent") or "",
                  "def": p.get("definition", "")[:140], "mds": []} for name, p in properties.items()]
        system = (load_prompt("facets") + "\n\nSTUDY STAGES\n"
                  + "\n".join(f"- {s}: {d}" for s, d in f["study_stages"].items()) + "\n\nDOMAINS\n"
                  + "\n".join(f"- {d}: {', '.join(subs) or '(no subdomains)'}" for d, subs in f["domains"].items()))
        stage_list = "\n\nSTUDY STAGES\n" + "\n".join(f"- {s}: {d}" for s, d in f["study_stages"].items())
        domain_list = "\n\nDOMAINS\n" + "\n".join(f"- {d}: {', '.join(subs) or '(no subdomains)'}"
                                                   for d, subs in f["domains"].items())
        if tier(self.name) == "local":  # separate closed-list calls for stage and for domain, merged per item
            prompts = [("stage", load_prompt("facets_stage") + stage_list), ("domain", load_prompt("facets_domain") + domain_list)]
        else:
            prompts = [("facets", system)]
        n_batches = -(-len(rows) // FACET_BATCH)
        log(f"tagging {len(rows)} classes/properties with study stage and domain "
            f"({n_batches * len(prompts)} call(s))")
        answers = defaultdict(dict)
        for name, prompt in prompts:
            for t in self.call_rows(rows, prompt, name, "tags", {"stage": "study_stage", "domain": "domain"}.get(name),
                                    size=FACET_BATCH):
                answers[key(t.get("id"))].update({k: v for k, v in t.items() if k != "id"})
        tags = {}
        for tid, t in answers.items():
            chosen = [stages[x.lower()] for x in targets(t.get("study_stage")) if x.lower() in stages][:2]
            dom = domains.get(str(t.get("domain", "")).strip().lower())
            if not chosen and not dom:
                continue
            sub = str(t.get("subdomain", "") or "").strip()
            sub = next((x for x in f["domains"][dom] if x.lower() == sub.lower()), "") if dom else ""
            tags[tid] = {"study_stage": chosen, "domain": dom or "General", "subdomain": sub,
                         "source": "model" if chosen and dom else "partial"}
        for cid, c in live.items():
            c["facets"] = tags.get(cid) or {"study_stage": [], "domain": "General", "subdomain": "",
                                            "source": "type_default"}
            c["facets"]["study_stage"] = c["facets"]["study_stage"] or [f["type_default_stage"].get(c.get("type"), "Data")]
        for name, p in properties.items():
            p["facets"] = tags.get(f"p:{name}") or {"study_stage": [], "domain": "General", "subdomain": "",
                                                    "source": "type_default"}
            p["facets"]["study_stage"] = p["facets"]["study_stage"] or ["Semantic Search"]
        facets = {cid: c["facets"] for cid, c in live.items()} | {f"p:{n}": p["facets"] for n, p in properties.items()}
        log(f"facets: {Counter(v['source'] for v in facets.values())}; "
            f"domains {dict(Counter(v['domain'] for v in facets.values()).most_common(4))}")
        return facets

    def run(self, classes: list[dict], properties: dict, papers: list[dict], run_id: str, domain: str) -> dict:
        mappings = self.align(classes)
        facets = self.tag_facets(classes, properties, mappings)
        log(f"mappings committed: {len(mappings)}")
        log("building OWL2 graph (classes, restrictions, provenance, BFO/CCO/RO imports)")
        graph = owl.build(classes, properties, mappings, papers, run_id, domain)
        log(f"serializing JSON-LD and Turtle ({len(graph):,} triples)")
        text = owl.serialize(graph)
        turtle = owl.serialize_turtle(graph)
        log("validating structure (round trip, declarations, BFO connection, cycles, labels)")
        validation = owl.validate(graph, text)
        log("valid" if validation["valid"] else f"{validation['n_issues']} structural issue(s); see ontology/validation.json")
        self.stats.update({f"failed_{k}": v for k, v in self.failures.items()})
        self.stats["row_coverage"] = {k: dict(v) for k, v in self.row_stats.items()}
        return {"mappings": mappings, "facets": facets, "checks": dict(self.stats), "jsonld": text, "turtle": turtle, "validation": validation,
                "metrics": owl.metrics(graph, classes, mappings, properties)}
