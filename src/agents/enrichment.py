"""Enrichment agent: definitions, synonyms, restrictions, disjointness, local property domain/range, and the
external candidate terms for interop, all from the ontology store (src/tools/ontostore.py) plus the MDS-Onto
portal and MatPortal searches.

Causal edges become restrictions deterministically: each keeps its local polarity property and also gets the
best-fitting RO property and CCO property for the cause/effect BFO categories (resources/upper/menus.json
causal_rules), with RO 'causally related to' as the fallback. Other relations get object-property candidates
from the store (predicate phrase and quote; domain and range must fit): an exact name match, or a tie that
upper.RELATION_GROUPS breaks, is used directly; the rest go to the model with their numbered candidates. The
paper's predicate phrase, quote, support and papers stay on every restriction. Every restriction must trace back
to an extracted relation.
"""
import hashlib
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from src.agents.base import Agent, items, key, load_prompt, targets
from src.config import (AGENT_PROFILES, CACHE, CANDIDATES_PER_PORTAL, LLM_PROFILE, MATPORTAL, MDS_ONTOLOGIES,
                        MODEL_DEFINITION_PROFILES, ONTOLOGY_SEARCH, secret, tier)
from src.tools import files, lexical, matportal, mds_portal, ontostore, retrieval, upper
from src.tools.owl import label_of, lineage
from src.tools.progress import log

BATCH = 25
PASS_FIELD = {"definitions": "definition", "synonyms": "alt_labels", "restrictions": "restrictions",
              "disjointness": "disjoint_with"}  # the answer field each local pass fills (reads {"k1": value} replies)
MAX_RELATIONS = 8
MAX_SIBLINGS = 12
BASIS = {"source_definition": "supported", "evidence": "draft_evidence", "model_knowledge": "model_generated"}
DEFINITION_RULE = {
    True: "basis=model_knowledge is allowed: when the source definitions and evidence are not enough, write a standard "
          "definition of the concept from general domain knowledge and return basis=model_knowledge.",
    False: "Never use outside knowledge. When neither the source definitions nor the evidence support a definition, "
           "return an empty definition and basis=none."}
CATEGORY = {"process": "http://purl.obolibrary.org/obo/BFO_0000015",
            "specifically dependent continuant": "http://purl.obolibrary.org/obo/BFO_0000020",
            "continuant": "http://purl.obolibrary.org/obo/BFO_0000002"}


def _public(iri: str) -> bool:
    """A term IRI others can resolve: http(s) on a public host (portals also return private-network IRIs)."""
    host = urlparse(iri).hostname or ""
    return urlparse(iri).scheme in ("http", "https") and "." in host and not (
        host == "localhost" or host.startswith(("127.", "10.", "192.168.", "169.254.")) or
        re.match(r"172\.(1[6-9]|2\d|3[01])\.", host))


def _same_term(r: dict) -> dict | None:
    """A portal hit from an ontology in the store but under another IRI (e.g. an older CCO release): the store's
    term of that ontology with the same label."""
    name = str(r.get("Ontology", "")).lower()
    hits = [t for t in ontostore.exact(r.get("Label", ""))
            if t["ontology"].lower() == name or t["ontology"].lower().startswith(name + "-")]
    return hits[0] if len(hits) == 1 else None


class EnrichmentAgent(Agent):
    name = "enrichment"

    def run(self, classes: list[dict], relations: list[dict], causal: list[dict]) -> tuple[list[dict], dict]:
        live = [c for c in classes if not c["excluded"]]
        by_id = {c["id"]: c for c in live}
        self.dropped = Counter()
        profile = AGENT_PROFILES.get(self.name, LLM_PROFILE)
        self.model_definitions = profile in MODEL_DEFINITION_PROFILES
        self.definition_source = f"{profile}:{self.model}"
        rule = "\n\n" + DEFINITION_RULE[self.model_definitions]
        for c in live:
            c["definition"], c["definition_source"] = "", ""
            c["definition_status"] = "unreviewed"
            c["restrictions"], c["disjoint_with"] = [], []

        log(f"mapping candidates: ontology store + MDS-Onto portal + MatPortal (all their ontologies) for {len(live):,} classes")
        self._candidates(live)
        log(f"candidates kept for {sum(1 for c in live if c['candidates'])} classes; "
            f"{sum(1 for c in live if any(x['label_match'] for x in c['candidates']))} with a label match; "
            f"{sum(1 for c in live for x in c['candidates'] if x.get('hop'))} propagated through mappings")
        self._causal(by_id, causal)
        log(f"causal restrictions added (local + RO + CCO): {sum(len(c['restrictions']) for c in live):,}")

        system = self.system + rule
        rels = defaultdict(list)
        for r in relations:  # unevidenced relations never become axioms
            if r["p"] != "is_a" and r["s"] in by_id and r["o"] in by_id and _evidenced(r):
                rels[r["s"]].append(r)
            elif r["p"] != "is_a" and r["s"] in by_id and r["o"] in by_id:
                self.dropped["unevidenced"] += 1
                self.doubt("restriction_dropped", reason="unevidenced", id=r["s"], label=by_id[r["s"]]["label"],
                           p=r["p"], o=r["o"], target=by_id[r["o"]]["label"], support=r.get("support"))
        self._property_candidates(by_id, rels)
        self._predicate_restrictions(by_id, rels)  # exact store names or RELATION_GROUPS tie-breaks: no model call
        log(f"restrictions from extracted predicates: {self.from_predicate}; "
            f"{sum(len(v) for v in rels.values())} relations left for the model")
        quotes = defaultdict(list)  # evidence each class takes part in, for definitions
        for r in relations + causal:
            ends = (r.get("s"), r.get("o")) if "s" in r else (r.get("cause"), r.get("effect"))
            for e in r.get("evidence", []):
                if e.get("text") and e.get("status") != "unevidenced":
                    for cid in ends:
                        if cid in by_id and len(quotes[cid]) < 3 and e["text"] not in quotes[cid]:
                            quotes[cid].append(e["text"][:200])
        children = defaultdict(list)
        for c in live:
            children[c["parent"]].append(c["id"])

        rel_text = lambda c: [f"{r['p']}: {by_id[r['o']]['label']} ({r['o']}) x{r['support']}"
                              for r in rels[c["id"]][:MAX_RELATIONS]]
        rel_rows = lambda c: [{"o": r["o"], "target": by_id[r["o"]]["label"], "paper": f"{r['p']} x{r['support']}",
                               "properties": [self._prop_line(x) for x in self.pcands.get(self._rkey(c["id"], r), [])]}
                              for r in rels[c["id"]][:MAX_RELATIONS]]
        sibs = lambda c: [f"{s}: {by_id[s]['label']}" for s in children[c["parent"]] if s != c["id"]][:MAX_SIBLINGS]
        if tier(self.name) == "local":
            passes = [  # (name, prompt, batch, which classes, row)
                ("definitions", load_prompt("enrichment_definitions") + rule, BATCH, live,
                 lambda c: {"id": c["id"], "label": c["label"], "parent": label_of(c["parent"], by_id),
                            "defs": [d["text"][:200] for d in c["definitions"][:2]], "relations": rel_text(c)[:4],
                            "evidence": quotes[c["id"]]}),
                ("synonyms", load_prompt("enrichment_synonyms"), 50, [c for c in live if c["alt_labels"]],
                 lambda c: {"id": c["id"], "label": c["label"], "alt": c["alt_labels"][:8]}),
                ("restrictions", load_prompt("enrichment_restrictions"), BATCH,
                 [c for c in live if any(self.pcands.get(self._rkey(c["id"], r)) for r in rels[c["id"]])],
                 lambda c: {"id": c["id"], "label": c["label"], "parent": label_of(c["parent"], by_id),
                            "relations": rel_rows(c)}),
                ("disjointness", load_prompt("enrichment_disjoint"), BATCH, [c for c in live if sibs(c)],
                 lambda c: {"id": c["id"], "label": c["label"], "parent": label_of(c["parent"], by_id),
                            "siblings": sibs(c)}),
            ]
            for name, prompt, size, todo, row in passes:
                log(f"enrichment {name}: {len(todo)} classes ({-(-len(todo) // size)} call(s))")
                answers = self.call_rows([row(c) for c in todo], prompt, name, "classes", PASS_FIELD[name], size=size)
                self._apply({"classes": answers}, by_id, rels)
        else:
            n_batches = -(-len(live) // BATCH)
            log(f"definitions, synonyms, restrictions and disjointness for {len(live):,} classes ({n_batches} call(s))")
            rows = [{"id": c["id"], "label": c["label"], "parent": label_of(c["parent"], by_id),
                     "alt": c["alt_labels"][:8], "defs": [d["text"][:200] for d in c["definitions"][:2]],
                     "evidence": quotes[c["id"]], "relations": rel_rows(c), "siblings": sibs(c)} for c in live]
            self._apply({"classes": self.call_rows(rows, system, "enrich", "classes", size=BATCH)}, by_id, rels)
        for c in live:
            if c["definition_status"] in ("none", "unreviewed"):
                c.setdefault("review_flags", []).append("unsupported_definition")
        # check: a disjoint pair the papers call "is a" of one another is dropped
        isa = {(r["s"], r["o"]) for r in relations if r["p"] == "is_a"}
        for c in live:
            kept = [d for d in c["disjoint_with"] if (c["id"], d) not in isa and (d, c["id"]) not in isa]
            for d in set(c["disjoint_with"]) - set(kept):
                self.doubt("disjointness_dropped", reason="papers state is_a", id=c["id"], label=c["label"], o=d,
                           target=by_id.get(d, {}).get("label"))
            self.dropped["disjoint_vs_is_a"] += len(c["disjoint_with"]) - len(kept)
            c["disjoint_with"] = kept
        self.stats = {"restrictions_dropped": dict(self.dropped), "failed_calls": dict(self.failures),
                      "restrictions_from_predicate": self.from_predicate,
                      "candidates": self.candidate_stats, "property_candidates": self.property_stats,
                      "definitions_by_status": dict(Counter(c["definition_status"] for c in live)),
                      "row_coverage": {k: dict(v) for k, v in self.row_stats.items()},
                      "unsupported_definitions": sum(c["definition_status"] in ("none", "unreviewed") for c in live),
                      "definition_category_conflicts": sum("definition_category_conflict" in c.get("review_flags", []) for c in live)}
        log(f"restrictions dropped: {dict(self.dropped) or 'none'}")
        return classes, self._local_properties(live, by_id)

    @staticmethod
    def _prop_line(x: dict) -> str:
        """A property candidate as shown to the model: P:<ONTOLOGY>:<label> (domain; range) - definition."""
        dom = upper.describe(x["domain"]).get("label", "any") if x.get("domain") else "any"
        rng = upper.describe(x["range"]).get("label", "any") if x.get("range") else "any"
        return f"P:{x['ontology']}:{x['label']} (domain: {dom}; range: {rng}) - {x['definition'][:80]}"

    @staticmethod
    def _rkey(cid: str, r: dict) -> tuple:
        return cid, r["o"], r["p"]

    def _property_candidates(self, by_id: dict, rels: dict):
        """Object-property candidates per extracted relation from the store: the predicate phrase (exact and
        trigram) and the embedding of phrase plus quote, kept only when the property's domain and range fit the two
        classes."""
        k = ONTOLOGY_SEARCH["properties_per_relation"]
        todo = [(cid, r) for cid, edges in rels.items() for r in edges]
        phrase = lambda r: r["p"].replace("_", " ")
        texts = {self._rkey(cid, r): f"{phrase(r)}: {next((e['text'] for e in r.get('evidence', []) if e.get('text')), '')[:200]}"
                 for cid, r in todo}
        vectors = dict(zip(texts, retrieval.embed(list(texts.values()), self.ledger))) \
            if ontostore.has_vectors() and texts else {}
        self.pcands, unfit = {}, 0
        for cid, r in todo:
            o = by_id[r["o"]]
            found = ontostore.search([phrase(r)], vectors.get(self._rkey(cid, r)), kinds=("object property",), k=k * 4)
            fit = [{**x, **{f: upper.describe(x["iri"]).get(f) for f in ("domain", "range")}}
                   for x in found if self._fits(x["iri"], by_id[cid], o, by_id)]
            unfit += len(found) - len(fit)
            self.pcands[self._rkey(cid, r)] = fit[:k]
        n = len(todo) or 1
        self.property_stats = {"relations": len(todo), "with_candidates": sum(1 for v in self.pcands.values() if v),
                               "mean_candidates": round(sum(map(len, self.pcands.values())) / n, 2),
                               "dropped_domain_range": unfit,
                               "by_ontology": dict(Counter(x["ontology"] for v in self.pcands.values() for x in v))}
        log(f"property candidates: {self.property_stats['with_candidates']}/{len(todo)} relations have a fitting "
            f"store property ({unfit} dropped for domain/range)")

    def _candidates(self, live: list[dict]):
        """Mapping candidates per class:
        1. the ontology store, over every ontology in it: label, synonyms and lexical head (exact and trigram)
           and the class's embedding (label + first source definition);
        2. the MDS-Onto portal and MatPortal searches over every ontology each portal hosts, with cleaned
           queries (exact label, full label, general term, spelled-out synonym of an abbreviation); a hit for a
           term in the store (also under another IRI of the same ontology, matched by label) joins the pool with
           the store's record, flagged with the portal(s) that found it; a hit outside the store (public IRI only)
           is a candidate too, scored on its label, up to portal_per_class per class;
        3. ranked label matches first, then score: the store's best candidates_per_class, then the portal-only
           ones; then terms one and two mapping hops away from a label-matched or strong store candidate, with
           confidence decaying per hop and the path recorded."""
        portals = [("MDS-Onto portal", mds_portal.search, MDS_ONTOLOGIES, "mds")]
        if MATPORTAL["enabled"] and secret("MATPORTAL_API_KEY"):
            portals.append(("MatPortal", matportal.search, MATPORTAL["ontologies"], "matportal"))
        failed = set()

        def fetch(portal: str, search, onts, folder: str, query: str, exact: bool) -> list[dict]:
            path = CACHE / folder / (hashlib.sha256(f"{onts}|{exact}|{query}".encode()).hexdigest()[:20] + ".json")
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
            try:
                res = search(query, ontologies=onts, max_results=CANDIDATES_PER_PORTAL, exact=exact)
            except Exception as e:
                if portal not in failed:
                    failed.add(portal)
                    err = re.sub(r"apikey=[^&\s]+", "apikey=***", str(e))
                    log(f"  {portal}: a search failed ({type(e).__name__}: {err}); other searches continue")
                return []
            if res:  # never cache failures
                files.atomic_write(path, json.dumps(res))
            return res

        def queries(c: dict) -> list[tuple[str, bool]]:
            q = lexical.clean_query(c["label"])
            out = [(q, True), (q, False)]
            if lexical.head_query(c["label"]):
                out.append((lexical.head_query(c["label"]), False))
            if len(q) <= 6 or q.isupper():  # abbreviation: also search the spelled-out synonym
                out += [(lexical.clean_query(a), False) for a in c["alt_labels"] if len(a) > 6][:1]
            return [(q, exact) for q, exact in dict.fromkeys(out) if q.strip()]  # a symbol-only label cleans to ""

        jobs = [(c["id"], portal, q, exact) for c in live for portal in portals for q, exact in queries(c)]
        with ThreadPoolExecutor(8) as ex:
            results = list(ex.map(lambda j: fetch(*j[1], j[2], j[3]), jobs))

        def from_store(t: dict, source: str, **extra) -> dict:
            return {"iri": t["iri"], "label": t["label"], "ontology": t["ontology"], "kind": t["kind"],
                    "definition": t["definition"], "labels": [x if isinstance(x, str) else x["text"] for x in t["labels"]],
                    "portal": source, **extra}

        k = ONTOLOGY_SEARCH["candidates_per_class"]
        texts = {c["id"]: f"{c['label']}: {(c['definitions'][0]['text'] if c['definitions'] else '')[:200]}" for c in live}
        vectors = dict(zip(texts, retrieval.embed(list(texts.values()), self.ledger))) \
            if ontostore.has_vectors() and texts else {}
        found = {c["id"]: {} for c in live}
        for c in live:
            qs = [c["label"], *c["alt_labels"][:3], lexical.head_query(c["label"]) or ""]
            for x in ontostore.search(qs, vectors.get(c["id"]), k=k * 2):
                found[c["id"]][x["iri"]] = {**from_store(x, "store"), **{f: x[f] for f in ("score", "exact", "fuzzy", "cosine", "methods")}}
        hits, off_store, by_label = Counter(), Counter(), Counter()
        lexical_texts = {c["id"]: [c["label"], *c["alt_labels"][:3]] for c in live}
        for (cid, (portal, *_p), *_rest), res in zip(jobs, results):
            for r in res:
                hits[portal] += 1
                mds = {k_: r[f"MDS_{v}"] for k_, v in (("stage", "StudyStage"), ("domain", "Domain"),
                                                      ("subdomain", "SubDomain")) if r.get(f"MDS_{v}") not in (None, "", "N/A")}
                t = ontostore.term(r["ID"]) or _same_term(r)  # a store ontology under another IRI (version): by label
                iri = t["iri"] if t else r["ID"]
                x = found[cid].get(iri)
                if x:  # already found by the store or the other portal
                    x["mds"] = x.get("mds") or mds
                    if portal not in x["portal"]:
                        x["portal"] += f"+{portal}"
                    continue
                if t:
                    by_label[portal] += t["iri"] != r["ID"]
                    found[cid][iri] = {**from_store(t, portal, mds=mds),
                                       **ontostore.score(t["iri"], lexical_texts[cid], vectors.get(cid))}
                elif _public(r["ID"]):  # outside the store: a candidate in its own right, scored below
                    off_store[f"{portal}: {r['Ontology']}"] += 1
                    found[cid][iri] = {"iri": iri, "label": r["Label"], "ontology": r["Ontology"], "kind": "",
                                       "labels": [r["Label"]], "definition": "" if r["Definition"] == "N/A" else r["Definition"],
                                       "portal": portal, "mds": mds, "in_store": False}
        # terms outside the store: the store's own signals and fused score (label + embedding of label: definition)
        outside = [(cid, x) for cid in found for x in found[cid].values() if x.get("in_store") is False]
        texts_out = [ontostore.external_text(x["label"], x["definition"]) for _, x in outside]
        term_vecs = dict(zip(texts_out, retrieval.embed(texts_out, self.ledger))) if vectors and texts_out else {}
        for (cid, x), text in zip(outside, texts_out):
            x.update(ontostore.score_external(x["label"], x["definition"],
                                              lexical_texts[cid],
                                              vectors.get(cid), term_vecs.get(text)))
        decay, cap, strong = ONTOLOGY_SEARCH["hop_decay"], ONTOLOGY_SEARCH["propagated_per_class"], ONTOLOGY_SEARCH["min_cosine"]
        for c in live:
            names = {lexical.match_key(n) for n in [c["label"], *c["alt_labels"]]}
            ranked = list(found[c["id"]].values())
            for x in ranked:
                x["label_match"] = any(lexical.match_key(n) in names for n in x["labels"] or [x["label"]])
            c["portal_only"] = [x for x in ranked if x.get("in_store") is False and x["label_match"]]  # facet hints
            outside = [x for x in ranked if x.get("in_store") is False and (  # stricter: no store curation behind them
                x["label_match"] or x.get("score", 0) >= ONTOLOGY_SEARCH["portal_min_score"])]
            ranked = [x for x in ranked if x.get("in_store", True) and (x["label_match"]
                      or x.get("score", 0) >= ONTOLOGY_SEARCH["min_score"])]
            ranked.sort(key=lambda x: (not x["label_match"], -x.get("score", 0)))
            outside.sort(key=lambda x: (not x["label_match"], -x.get("score", 0)))
            kept = ranked[:k] + outside[:ONTOLOGY_SEARCH["portal_per_class"]]  # store terms, then portal-only terms
            have, extra = {x["iri"] for x in kept} | {c["iri"]}, []
            for x in kept:
                if x.get("in_store") is False or not (x["label_match"] or x.get("score", 0) >= strong):
                    continue
                base_score = 1.0 if x["label_match"] else x["score"]
                for hop in ontostore.propagate(x["iri"]):
                    if hop["iri"] in have or len(extra) >= cap:
                        continue
                    have.add(hop["iri"])
                    t = ontostore.term(hop["iri"])
                    extra.append({**from_store(t, "propagated"), "score": round(base_score * decay ** hop["hop"], 3),
                                  "hop": hop["hop"], "path": hop["path"], "via": hop["relations"],
                                  "label_match": any(lexical.match_key(n["text"]) in names for n in t["labels"])})
            c["candidates"] = kept + extra
        per = [len(c["candidates"]) for c in live] or [0]
        self.candidate_stats = {
            "classes_with_candidates": sum(1 for c in live if c["candidates"]),
            "mean_per_class": round(sum(per) / len(per), 2),
            "by_source": dict(Counter(x["portal"] + (" (outside store)" if x.get("in_store") is False else "")
                                      for c in live for x in c["candidates"])),
            "outside_store": sum(1 for c in live for x in c["candidates"] if x.get("in_store") is False),
            "portal_resolved_by_label": dict(by_label),
            "by_ontology": dict(Counter(x["ontology"] for c in live for x in c["candidates"])),
            "propagated_by_hop": dict(Counter(str(x["hop"]) for c in live for x in c["candidates"] if x.get("hop"))),
            "portal_hits": dict(hits), "portal_hits_off_store": dict(off_store.most_common(25))}

    @classmethod
    def _causal(cls, by_id: dict, causal: list[dict]):
        polarity = upper.menus()["causal_polarity"]
        for r in causal:
            c, o = by_id.get(r["cause"]), by_id.get(r["effect"])
            if not c or not o:
                continue
            claim = {"o": o["id"], "kind": "causal", "polarity": r["polarity"], "phrase": r["polarity"], "support": r["support"],
                     "papers": r["papers"], "evidence": r["evidence"], "conditions": r.get("conditions", [])}
            for p in ["local:" + polarity.get(r["polarity"], "influences"), *cls._standard_causal(c, o, r["polarity"], by_id)]:
                if not any(x["p"] == p and x["o"] == o["id"] for x in c["restrictions"]):
                    c["restrictions"].append({"p": p, **claim})

    @classmethod
    def _standard_causal(cls, c: dict, o: dict, polarity: str, by_id: dict) -> list[str]:
        """First fitting RO and CCO causal property for this cause/effect pair; RO fallback if no RO rule fits."""
        menus, chosen = upper.menus(), {}

        def is_a(cid, category):
            return category == "entity" or CATEGORY[category] in lineage(cid, by_id)

        for rule in menus["causal_rules"]:
            key = rule["map"].get(polarity) or rule["map"].get("*")
            source = key.split(":", 1)[0] if key else None
            if not key or source in chosen or not (is_a(c["id"], rule["cause"]) and is_a(o["id"], rule["effect"])):
                continue
            iri = upper.property_iri(key)
            if iri and cls._fits(iri, c, o, by_id):
                chosen[source] = iri
        chosen.setdefault("RO", upper.property_iri(menus["causal_fallback"]))
        return list(chosen.values())

    def _apply(self, out: dict, by_id: dict, rels: dict, value_key: str | None = None):
        for r in items(out, "classes", value_key):
            c = by_id.get(key(r.get("id")))
            if not c:
                continue
            if "definition" in r:
                text = r["definition"].strip() if isinstance(r.get("definition"), str) else ""
                basis = str(r.get("basis") or "").strip().lower()
                if not basis and r.get("definition_supported") is True:  # answer in the previous shape
                    basis = "source_definition"
                status = BASIS.get(basis) if text else None
                if status == "model_generated" and not self.model_definitions:
                    status = None  # outside knowledge is only allowed on the profiles that permit it
                if status:
                    c["definition"], c["definition_status"], c["definition_source"] = text, status, self.definition_source
                else:
                    c["definition"], c["definition_status"], c["definition_source"] = "", "none", ""
                if r.get("category_conflict") is True:
                    c.setdefault("review_flags", []).append("definition_category_conflict")
            if isinstance(r.get("alt_labels"), list):
                given = {a.lower(): a for a in c["alt_labels"]}
                c["alt_labels"] = [given[a.lower()] for a in r["alt_labels"] if isinstance(a, str) and a.lower() in given]
            for x in items(r, "restrictions"):
                answer = str(x.get("p", "")).split(" (")[0].removeprefix("P:").strip().lower()
                for target in targets(x.get("o")) or [None]:
                    o = by_id.get(target)
                    src = next((e for e in rels[c["id"]] if o and e["o"] == o["id"]), None)
                    p = self._answer_property(c["id"], src, answer) if src else None
                    reason = ("invalid" if not o or o["id"] == c["id"] else "ungrounded" if not src
                              else "not_a_candidate" if not p else "domain_range" if not self._fits(p, c, o, by_id) else "")
                    if reason:
                        self.dropped[reason] += 1
                        self.doubt("restriction_dropped", reason=reason, id=c["id"], label=c["label"],
                                   answer=str(x.get("p", ""))[:120], o=target, target=(o or {}).get("label"),
                                   property=p)
                    elif not any(e["p"] == p and e["o"] == o["id"] for e in c["restrictions"]):
                        c["restrictions"].append({"p": p, "o": o["id"], "kind": "relation", "source": "model",
                                                  "phrase": src["p"], "support": src["support"],
                                                  "papers": src["papers"], "evidence": src["evidence"]})
            for d in targets(r.get("disjoint_with")):
                o = by_id.get(d)
                if o and o["id"] != c["id"] and o["parent"] == c["parent"] \
                        and d not in c["disjoint_with"] and c["id"] not in o["disjoint_with"]:
                    c["disjoint_with"].append(d)

    def _predicate_restrictions(self, by_id: dict, rels: dict):
        """A relation with verified evidence becomes a restriction without a model call when the store settles the
        property: one fitting candidate carries the predicate's name exactly, or the top candidates tie (within
        tie_margin) and RELATION_GROUPS names one of them. Several exact names are also a tie for RELATION_GROUPS.
        Those relations leave rels; the rest go to the model with their candidates."""
        self.from_predicate = 0
        for cid, edges in rels.items():
            c, rest = by_id[cid], []
            for r in edges:
                o = by_id.get(r["o"])
                fits = self._store_choice(cid, r, by_id) if o and any(
                    e.get("verified") is True for e in r.get("evidence", [])) else None
                if not fits:
                    rest.append(r)
                    continue
                if not any(e["p"] == fits and e["o"] == o["id"] for e in c["restrictions"]):
                    c["restrictions"].append({"p": fits, "o": o["id"], "kind": "relation", "source": "extracted_predicate",
                                              "phrase": r["p"], "support": r["support"], "papers": r["papers"],
                                              "evidence": r["evidence"]})
                    self.from_predicate += 1
            edges[:] = rest

    def _store_choice(self, cid: str, r: dict, by_id: dict) -> str | None:
        cands = self.pcands.get(self._rkey(cid, r)) or []
        if not cands:
            return None
        group, preferred = upper.relation_group(r["p"]), []
        if group:
            props, s_cat, o_cat = group
            if (not s_cat or s_cat in lineage(cid, by_id)) and (not o_cat or o_cat in lineage(r["o"], by_id)):
                preferred = [i for i in map(upper.property_iri, props) if i]
        exact = [x for x in cands if x["exact"]]
        tied = exact or [x for x in cands if x["score"] >= cands[0]["score"] - ONTOLOGY_SEARCH["tie_margin"]]
        pick = next((i for i in preferred if i in {x["iri"] for x in tied}), None)
        return pick or (exact[0]["iri"] if exact else None)

    def _answer_property(self, cid: str, rel: dict, answer: str) -> str | None:
        """The IRI of the candidate the model named for this relation ("ONTOLOGY:label" or just the label)."""
        for x in self.pcands.get(self._rkey(cid, rel), []):
            if answer in (f"{x['ontology']}:{x['label']}".lower(), x["label"].lower()):
                return x["iri"]
        return None

    @staticmethod
    def _fits(p_iri: str, c: dict, o: dict, by_id: dict) -> bool:
        """BFO/CCO compliance: subject and target must fall under the property's declared domain and range."""
        meta = upper.describe(p_iri)
        for end, cls in (("domain", c), ("range", o)):
            req = meta.get(end)
            if req and req != upper.ENTITY and req not in lineage(cls["id"], by_id):
                return False
        return True

    @staticmethod
    def _local_properties(live: list[dict], by_id: dict) -> dict:
        local = upper.menus()["local_properties"]
        uses = defaultdict(lambda: ([], []))
        for c in live:
            for r in c["restrictions"]:
                if r["p"].startswith("local:"):
                    uses[r["p"][6:]][0].append(c["id"])
                    uses[r["p"][6:]][1].append(r["o"])
        props = {name: {**local[name], "domain": _lca(s, by_id), "range": _lca(o, by_id), "uses": len(s)}
                 for name, (s, o) in uses.items()}
        if props and "influences" not in props:
            props["influences"] = {**local["influences"], "domain": None, "range": None, "uses": 0}
        return props


def _lca(ids: list[str], by_id: dict):
    """Most specific common ancestor (local or upper); None when it is only BFO entity."""
    chains = [[i] + lineage(i, by_id) for i in dict.fromkeys(ids)]
    if not chains:
        return None
    common = next((a for a in chains[0] if all(a in ch for ch in chains[1:])), None)
    return None if common in (None, upper.ENTITY) else common


def _evidenced(r: dict) -> bool:
    """A joined relation with at least one usable quote (older runs carry no evidence status)."""
    return any(e.get("text") and e.get("status") != "unevidenced" and len(str(e["text"]).split()) >= 3
               for e in r.get("evidence", []))
