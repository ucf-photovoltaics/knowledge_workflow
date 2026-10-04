"""Enrichment agent: definitions, synonyms, restrictions, disjointness, local property domain/range,
and candidate external terms from the MDS-Onto Open Portal.

Causal edges become restrictions deterministically: each keeps its local polarity property and also gets the
best-fitting RO property and CCO property for the cause/effect BFO categories (resources/upper/menus.json
causal_rules), with RO 'causally related to' as the fallback. The LLM only handles definitions, labels,
non-causal restrictions (BFO, CCO and RO properties side by side) and disjointness. Every restriction must
trace back to an extracted relation.
"""
import hashlib
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from src.agents.base import Agent, compact, items, key, load_prompt, targets
from src.config import (AGENT_PROFILES, CACHE, CANDIDATES_PER_PORTAL, EMBED, LLM_PROFILE, MAPPING, MATPORTAL,
                        MDS_ONTOLOGIES, MODEL_DEFINITION_PROFILES, secret, tier)
from src.tools import lexical, matportal, mds_portal, retrieval, upper
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

        log(f"mapping candidates: {' and '.join(p for p, _, _ in self._portals())} + local BFO/CCO "
            f"for {len(live):,} classes")
        self._candidates(live)
        log(f"candidates kept for {sum(1 for c in live if c['candidates'])} classes; "
            f"{sum(1 for c in live if any(x['label_match'] for x in c['candidates']))} with a label match")
        self._causal(by_id, causal)
        log(f"causal restrictions added (local + RO + CCO): {sum(len(c['restrictions']) for c in live):,}")

        pmenu = upper.property_menu()
        system = self.system + rule + "\n\nPROPERTIES\n" + "\n".join(self._prop_line(lab, iri) for lab, iri in pmenu.items())
        rels = defaultdict(list)
        for r in relations:  # unevidenced relations never become axioms
            if r["p"] != "is_a" and r["s"] in by_id and r["o"] in by_id and _evidenced(r):
                rels[r["s"]].append(r)
            elif r["p"] != "is_a" and r["s"] in by_id and r["o"] in by_id:
                self.dropped["unevidenced"] += 1
        self._predicate_restrictions(by_id, rels)  # verified RO/BFO/CCO predicates: no model call needed
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

        pmenu_lc = {k.lower(): v for k, v in pmenu.items()}
        rel_text = lambda c: [f"{r['p']}: {by_id[r['o']]['label']} ({r['o']}) x{r['support']}"
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
                ("restrictions", load_prompt("enrichment_restrictions") + "\n\nPROPERTIES\n"
                 + "\n".join(self._prop_line(lab, iri) for lab, iri in pmenu.items()), BATCH,
                 [c for c in live if rels[c["id"]]],
                 lambda c: {"id": c["id"], "label": c["label"], "parent": label_of(c["parent"], by_id),
                            "relations": rel_text(c)}),
                ("disjointness", load_prompt("enrichment_disjoint"), BATCH, [c for c in live if sibs(c)],
                 lambda c: {"id": c["id"], "label": c["label"], "parent": label_of(c["parent"], by_id),
                            "siblings": sibs(c)}),
            ]
            for name, prompt, size, todo, row in passes:
                log(f"enrichment {name}: {len(todo)} classes ({-(-len(todo) // size)} call(s))")
                answers = self.call_rows([row(c) for c in todo], prompt, name, "classes", PASS_FIELD[name], size=size)
                self._apply({"classes": answers}, by_id, pmenu_lc, rels)
        else:
            n_batches = -(-len(live) // BATCH)
            log(f"definitions, synonyms, restrictions and disjointness for {len(live):,} classes ({n_batches} call(s))")
            rows = [{"id": c["id"], "label": c["label"], "parent": label_of(c["parent"], by_id),
                     "alt": c["alt_labels"][:8], "defs": [d["text"][:200] for d in c["definitions"][:2]],
                     "evidence": quotes[c["id"]], "relations": rel_text(c), "siblings": sibs(c)} for c in live]
            self._apply({"classes": self.call_rows(rows, system, "enrich", "classes", size=BATCH)}, by_id, pmenu_lc, rels)
        for c in live:
            if c["definition_status"] in ("none", "unreviewed"):
                c.setdefault("review_flags", []).append("unsupported_definition")
        # check: a disjoint pair the papers call "is a" of one another is dropped
        isa = {(r["s"], r["o"]) for r in relations if r["p"] == "is_a"}
        for c in live:
            kept = [d for d in c["disjoint_with"] if (c["id"], d) not in isa and (d, c["id"]) not in isa]
            self.dropped["disjoint_vs_is_a"] += len(c["disjoint_with"]) - len(kept)
            c["disjoint_with"] = kept
        self.stats = {"restrictions_dropped": dict(self.dropped), "failed_calls": dict(self.failures),
                      "restrictions_from_predicate": self.from_predicate,
                      "definitions_by_status": dict(Counter(c["definition_status"] for c in live)),
                      "row_coverage": {k: dict(v) for k, v in self.row_stats.items()},
                      "unsupported_definitions": sum(c["definition_status"] in ("none", "unreviewed") for c in live),
                      "definition_category_conflicts": sum("definition_category_conflict" in c.get("review_flags", []) for c in live)}
        log(f"restrictions dropped: {dict(self.dropped) or 'none'}")
        return classes, self._local_properties(live, by_id)

    @staticmethod
    def _prop_line(label: str, iri: str) -> str:
        m = upper.describe(iri)
        dom = upper.describe(m["domain"]).get("label", "any") if m.get("domain") else "any"
        rng = upper.describe(m["range"]).get("label", "any") if m.get("range") else "any"
        return f"P:{label} (domain: {dom}; range: {rng}) - {m.get('definition', '')[:80]}"

    @staticmethod
    def _portals() -> list[tuple]:
        """(name, search function, ontology filter) for each portal in use."""
        portals = [("MDS-Onto portal", mds_portal.search, MDS_ONTOLOGIES)]
        if MATPORTAL["enabled"] and secret("MATPORTAL_API_KEY"):
            portals.append(("MatPortal", matportal.search, MATPORTAL["ontologies"]))
        return portals

    def _candidates(self, live: list[dict]):
        """Mapping candidates per class:
        1. portal searches with cleaned queries: an exact-label search, the full label, its general term, and the
           spelled-out synonym when the label is an abbreviation (BFO/CCO hits dropped: those are matched locally);
        2. local BFO/CCO classes with the same label, plus the nearest ones by embedding;
        3. re-rank by embedding similarity to the class, keep label matches and anything above min_similarity."""
        failed = set()

        def fetch(portal: str, search, onts, query: str, exact: bool) -> list[dict]:
            folder = CACHE / ("mds" if portal == "MDS-Onto portal" else "matportal")
            path = folder / (hashlib.sha256(f"{onts}|{exact}|{query}".encode()).hexdigest()[:20] + ".json")
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
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(res), encoding="utf-8")
            return res

        def queries(c: dict) -> list[tuple[str, bool]]:
            q = lexical.clean_query(c["label"])
            out = [(q, True), (q, False)]
            if lexical.head_query(c["label"]):
                out.append((lexical.head_query(c["label"]), False))
            if len(q) <= 6 or q.isupper():  # abbreviation: also search the spelled-out synonym
                out += [(lexical.clean_query(a), False) for a in c["alt_labels"] if len(a) > 6][:1]
            return [(q, exact) for q, exact in dict.fromkeys(out) if q.strip()]  # a symbol-only label cleans to ""

        jobs = [(c["id"], portal, search, onts, q, exact)
                for c in live for portal, search, onts in self._portals() for q, exact in queries(c)]
        with ThreadPoolExecutor(8) as ex:
            results = list(ex.map(lambda j: fetch(j[1], j[2], j[3], j[4], j[5]), jobs))
        found = {c["id"]: {} for c in live}
        for (cid, portal, *_rest), res in zip(jobs, results):
            for r in res:
                if "commoncoreontologies.org" in r["ID"] or "/obo/BFO_" in r["ID"]:
                    continue
                found[cid].setdefault(r["ID"], {"iri": r["ID"], "label": r["Label"], "ontology": r["Ontology"],
                                                 "definition": "" if r["Definition"] == "N/A" else r["Definition"],
                                                 "portal": portal,
                                                 "mds": {k: r[f"MDS_{v}"] for k, v in (("stage", "StudyStage"),
                                                         ("domain", "Domain"), ("subdomain", "SubDomain"))
                                                         if r.get(f"MDS_{v}") not in (None, "", "N/A")}})
        by_label = {}
        for iri, t in upper.terms()["classes"].items():
            by_label.setdefault(lexical.match_key(t["label"]), iri)

        def local(iri: str) -> dict:
            t = upper.describe(iri)
            return {"iri": iri, "label": t["label"], "ontology": t["source"].upper(),
                    "definition": t.get("definition", ""), "portal": "local"}

        texts = {c["id"]: f"{c['label']}: {(c['definitions'][0]['text'] if c['definitions'] else '')[:200]}" for c in live}
        near = {}
        if retrieval.enabled():
            ids = list(texts)
            near = dict(zip(ids, retrieval.nearest_upper([texts[i] for i in ids], MAPPING["local_upper_top"],
                                                          self.ledger)))
        key_of = lambda x: f"{x['label']}: {x['definition'][:200]}"
        for c in live:
            cands = found[c["id"]]
            names = {lexical.match_key(n) for n in [c["label"], *c["alt_labels"]]}
            for n in names:
                if n in by_label:
                    cands.setdefault(by_label[n], local(by_label[n]))
            for iri, _ in near.get(c["id"], []):
                cands.setdefault(iri, local(iri))
            for x in cands.values():
                x["label_match"] = lexical.match_key(x["label"]) in names
        if retrieval.enabled():  # one batched embedding pass for every class and candidate
            batch = list(dict.fromkeys([*texts.values(), *(key_of(x) for c in live for x in found[c["id"]].values())]))
            log(f"embedding {len(batch):,} class and candidate texts for re-ranking ({EMBED['model']})")
            retrieval.embed(batch, self.ledger)
        for c in live:
            ranked = list(found[c["id"]].values())
            if retrieval.enabled() and ranked:
                for x in ranked:
                    x["score"] = round(retrieval.similarity(texts[c["id"]], key_of(x)), 3)
                ranked = [x for x in ranked if x["label_match"] or x["score"] >= MAPPING["min_similarity"]]
            ranked.sort(key=lambda x: (not x["label_match"], -x.get("score", 0)))
            c["candidates"] = ranked[:MAPPING["candidates_total"]]

    @classmethod
    def _causal(cls, by_id: dict, causal: list[dict]):
        polarity = upper.menus()["causal_polarity"]
        for r in causal:
            c, o = by_id.get(r["cause"]), by_id.get(r["effect"])
            if not c or not o:
                continue
            claim = {"o": o["id"], "kind": "causal", "polarity": r["polarity"], "support": r["support"],
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

    def _apply(self, out: dict, by_id: dict, pmenu_lc: dict, rels: dict, value_key: str | None = None):
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
                p = pmenu_lc.get(str(x.get("p", "")).removeprefix("P:").strip().lower())
                for target in targets(x.get("o")) or [None]:
                    o = by_id.get(target)
                    src = next((e for e in rels[c["id"]] if o and e["o"] == o["id"]), None)
                    if not p or not o or o["id"] == c["id"]:
                        self.dropped["invalid"] += 1
                    elif not src:
                        self.dropped["ungrounded"] += 1
                    elif not self._fits(p, c, o, by_id):
                        self.dropped["domain_range"] += 1
                    elif not any(e["p"] == p and e["o"] == o["id"] for e in c["restrictions"]):
                        c["restrictions"].append({"p": p, "o": o["id"], "kind": "relation", "support": src["support"],
                                                  "papers": src["papers"], "evidence": src["evidence"]})
            for d in targets(r.get("disjoint_with")):
                o = by_id.get(d)
                if o and o["id"] != c["id"] and o["parent"] == c["parent"] \
                        and d not in c["disjoint_with"] and c["id"] not in o["disjoint_with"]:
                    c["disjoint_with"].append(d)

    def _predicate_restrictions(self, by_id: dict, rels: dict):
        """A relation whose extracted predicate an RO/BFO/CCO property formalizes, with verified evidence, becomes a
        restriction with the first property of its group whose domain and range fit. Those relations leave rels;
        the rest (related_to, unverified, or no fitting property) go to the model pass."""
        self.from_predicate = 0
        for cid, edges in rels.items():
            c, rest = by_id[cid], []
            for r in edges:
                o, group = by_id.get(r["o"]), upper.relation_group(r["p"])
                fits = None
                if o and group and any(e.get("verified") is True for e in r.get("evidence", [])):
                    props, s_cat, o_cat = group
                    if (not s_cat or s_cat in lineage(cid, by_id)) and (not o_cat or o_cat in lineage(o["id"], by_id)):
                        fits = next((i for i in map(upper.property_iri, props) if i and self._fits(i, c, o, by_id)), None)
                if not fits:
                    rest.append(r)
                    continue
                if not any(e["p"] == fits and e["o"] == o["id"] for e in c["restrictions"]):
                    c["restrictions"].append({"p": fits, "o": o["id"], "kind": "relation", "source": "extracted_predicate",
                                              "support": r["support"], "papers": r["papers"], "evidence": r["evidence"]})
                    self.from_predicate += 1
            edges[:] = rest

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
