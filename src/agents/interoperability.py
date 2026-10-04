"""Interoperability agent: commit mappings from classes to external terms (ontology store and MDS-Onto portal
candidates), import definitions of matched terms, then assemble, validate (structurally, no reasoner) and emit the
ontology as OWL2 JSON-LD and Turtle.

Mapping checks: every target must be in the ontology store and not deprecated. exact/equivalent are kept only
when the labels (or a synonym) actually match - otherwise they are downgraded to close. owl:equivalentClass needs
a BFO-aligned class target in the same BFO category (otherwise skos:exactMatch); broader adds rdfs:subClassOf
only when the target's category is the class's own or above it (otherwise skos:broadMatch alone). Individuals
(QUDT quantity kinds and units) get SKOS only. Label-matched candidates the model skipped are added when their
similarity is high; propagated candidates are only ever asserted by the model. Every mapping carries its method,
scores, confidence, target ontology, hop count and path."""
from collections import Counter, defaultdict

from src.agents.base import Agent, compact, items, key, load_prompt, targets
from src.config import MAPPING, tier
from src.tools import ontostore, owl, upper
from src.tools.owl import label_of, lineage
from src.tools.progress import log

BATCH = 20
FACET_BATCH = 40
RELATIONS = {"equivalent", "exact", "close", "broader", "narrower", "related"}
ALIASES = {"subclass": "broader", "broad": "broader", "narrow": "narrower"}  # earlier answer shapes


class InteroperabilityAgent(Agent):
    name = "interoperability"

    def __init__(self, ledger):
        super().__init__(ledger)
        self.stats = Counter(dropped_not_in_store=0, dropped_deprecated=0)

    def align(self, classes: list[dict]) -> list[dict]:
        by_id = {c["id"]: c for c in classes if not c["excluded"]}
        todo = [c for c in by_id.values() if c.get("candidates")]
        mappings, seen = [], set()
        shown = {c["id"]: set(range(1, len(c["candidates"]) + 1)) for c in todo}
        row = lambda c: {"id": c["id"], "label": c["label"], "parent": label_of(c["parent"], by_id),
                         "def": c.get("definition", "")[:160],
                         "candidates": [[n, x["label"], x["ontology"], x["definition"][:120],
                                         "=" if x.get("label_match") else x.get("score", ""),
                                         *([f"via {x['hop']} hop(s)"] if x.get("hop") else [])]
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
            batch = {c["id"]: c for c in todo[i:i + BATCH]}
            out = self.call(compact([row(c) for c in batch.values()]), item=f"align_{i // BATCH + 1}",
                            label=f"align {i // BATCH + 1}/{n_batches}", soft=True)
            for m in items(out, "mappings", "candidate"):
                c = batch.get(key(m.get("id")))  # only accept classes actually shown in this call
                if not c:
                    continue
                rel = key(m.get("relation"))  # a list or dict here used to crash the stage (unhashable)
                rel = ALIASES.get(rel.lower(), rel.lower()) if rel else None
                try:
                    n = int(m.get("candidate"))
                except (TypeError, ValueError):
                    continue
                if rel not in RELATIONS or n not in shown[c["id"]]:
                    continue
                if (c["id"], c["candidates"][n - 1]["iri"]) not in seen:
                    self._commit(c, c["candidates"][n - 1], rel, "model", by_id, mappings, seen)
        for c in todo:  # same name, and similar in meaning, but not chosen by the model (never propagated ones)
            for cand in c["candidates"]:
                if cand.get("label_match") and not cand.get("hop") and (c["id"], cand["iri"]) not in seen \
                        and (cand.get("cosine") or cand.get("score") or 0) >= MAPPING["strong_similarity"]:
                    self._commit(c, cand, "exact", "label_match", by_id, mappings, seen)
        downgraded = sum(1 for m in mappings if "downgraded_from" in m)
        log(f"mappings: {len(mappings)} ({downgraded} downgraded, "
            f"{sum(1 for m in mappings if m['method'] == 'label_match')} added from label matches, "
            f"{sum(1 for m in mappings if m.get('hop'))} through propagated candidates); "
            f"dropped: {self.stats['dropped_not_in_store']} not in the store, {self.stats['dropped_deprecated']} deprecated")
        return mappings

    def _commit(self, c: dict, cand: dict, rel: str, method: str, by_id: dict, mappings: list, seen: set):
        """Checks one chosen mapping against the store and BFO categories, then records it."""
        t = ontostore.term(cand["iri"])
        if cand["iri"] == c["iri"]:
            return
        if t is None:
            self.stats["dropped_not_in_store"] += 1
            return
        if t["deprecated"]:
            self.stats["dropped_deprecated"] += 1
            return
        chosen = rel
        if rel in ("exact", "equivalent") and not cand.get("label_match"):
            rel = "close"  # meaning claimed identical but the names differ: keep only as a close match
        if rel == "equivalent" and not owl.category_fit(lineage(c["id"], by_id), t["iri"], same=True, kind=t["kind"]):
            rel = "exact"  # not a BFO-aligned class of the same category: SKOS only
        axiom = rel == "broader" and owl.category_fit(lineage(c["id"], by_id), t["iri"], same=False, kind=t["kind"])
        seen.add((c["id"], cand["iri"]))
        mappings.append({"id": c["id"], "relation": rel, "iri": t["iri"], "label": t["label"], "ontology": t["ontology"],
                         "kind": t["kind"], "definition": t["definition"], "labels": [x["text"] for x in t["labels"]],
                         "method": method, "source": method, "portal": cand.get("portal"), "mds": cand.get("mds", {}),
                         "label_match": bool(cand.get("label_match")), "subclass_axiom": axiom,
                         "scores": {k: cand.get(k) for k in ("score", "fuzzy", "cosine") if cand.get(k) is not None},
                         "confidence": 1.0 if cand.get("label_match") and not cand.get("hop") else cand.get("score"),
                         "hop": cand.get("hop", 0), "path": cand.get("path", []), "via": cand.get("via", []),
                         **({"downgraded_from": chosen} if rel != chosen else {})})

    def import_definitions(self, classes: list[dict], mappings: list[dict]) -> list[dict]:
        """A class without a paper-supported definition takes the definition of its exact or equivalent match
        (equivalent first, then confidence), with status imported and the term's IRI as source."""
        live = {c["id"]: c for c in classes if not c["excluded"]}
        best = {}
        for m in sorted(mappings, key=lambda m: (m["relation"] != "equivalent", -(m.get("confidence") or 0))):
            if m["relation"] in ("exact", "equivalent") and m.get("definition") and m["id"] in live:
                best.setdefault(m["id"], m)
        imported = []
        for cid, m in best.items():
            c = live[cid]
            if c.get("definition_status") == "supported":
                continue
            imported.append({"id": cid, "iri": c["iri"], "source": m["iri"], "ontology": m["ontology"],
                             "replaced": {"text": c.get("definition", ""), "status": c.get("definition_status", "")}})
            c["definition"], c["definition_status"], c["definition_source"] = m["definition"], "imported", m["iri"]
            c["review_flags"] = [f for f in c.get("review_flags", []) if f != "unsupported_definition"]
        self.stats["definitions_imported"] = len(imported)
        log(f"definitions imported from matched terms: {len(imported)}")
        return imported

    def mapping_issues(self, graph, classes: list[dict], mappings: list[dict]) -> list[str]:
        """Checks the structural validator cannot make: mapped IRIs exist in the store and are not deprecated;
        owl:sameAs only between individuals; no subclass or equivalence into another BFO category."""
        live = {c["id"]: c for c in classes if not c["excluded"]}
        issues = []
        for m in mappings:
            t = ontostore.term(m["iri"])
            if t is None:
                issues.append(f"mapped IRI not in the ontology store: {m['iri']}")
            elif t["deprecated"]:
                issues.append(f"mapping to a deprecated term: {m['iri']}")
            elif (m["relation"] == "equivalent" or m.get("subclass_axiom")) and m["id"] in live and not owl.category_fit(
                    lineage(m["id"], live), m["iri"], same=m["relation"] == "equivalent", kind=t["kind"]):
                issues.append(f"{m['relation']} axiom into another BFO category: {live[m['id']]['iri']} -> {m['iri']}")
        issues += owl.same_as_issues(graph)
        return issues

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
            for x in c.get("candidates", []) + c.get("portal_only", []):  # portal_only: hits not in the store
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
        imported = self.import_definitions(classes, mappings)
        facets = self.tag_facets(classes, properties, mappings)
        log(f"mappings committed: {len(mappings)}")
        log("building OWL2 graph (classes, labels, restrictions, mappings, provenance, imports from the store)")
        graph = owl.build(classes, properties, mappings, papers, run_id, domain)
        log(f"serializing JSON-LD and Turtle ({len(graph):,} triples)")
        text = owl.serialize(graph)
        turtle = owl.serialize_turtle(graph)
        log("validating structure (round trip, declarations, BFO connection, cycles, labels, mapping checks)")
        validation = owl.validate(graph, text, self.mapping_issues(graph, classes, mappings))
        log("valid" if validation["valid"] else f"{validation['n_issues']} structural issue(s); see ontology/validation.json")
        self.stats.update({f"failed_{k}": v for k, v in self.failures.items()})
        self.stats["row_coverage"] = {k: dict(v) for k, v in self.row_stats.items()}
        return {"mappings": mappings, "facets": facets, "checks": dict(self.stats), "jsonld": text, "turtle": turtle,
                "validation": validation, "imported_definitions": imported,
                "metrics": owl.metrics(graph, classes, mappings, properties)}
