"""Ontology agent: place canonical concepts under CCO/BFO classes from the ontology store (or a same-name MDS-Onto or
PMDCO class), or under each other, and assign IRIs."""
import re
import hashlib
from urllib.parse import quote
from collections import Counter

from src.agents.base import Agent, key, load_prompt
from src.config import ONTOLOGY_SEARCH, tier
from src.tools import lexical, ontology_review, ontostore, retrieval, upper
from src.tools.progress import log
from src.tools.owl import base, bfo_category, lineage

BATCH = 60
SPLIT_BATCH = 25       # local tier: smaller batches, so a small model answers every row
PARENT_CONCEPTS = 150  # local parent pass: the most important corpus concepts of the category offered as parents
OBO = "http://purl.obolibrary.org/obo/"
CATEGORIES = {  # local tier, pass 1 choices -> BFO root
    "material entity": f"{OBO}BFO_0000040", "site": f"{OBO}BFO_0000029", "quality": f"{OBO}BFO_0000019",
    "disposition": f"{OBO}BFO_0000016", "function": f"{OBO}BFO_0000034", "role": f"{OBO}BFO_0000023",
    "process": f"{OBO}BFO_0000015", "process profile": f"{OBO}BFO_0000144", "information": f"{OBO}BFO_0000031",
}


def slug(label: str) -> str:
    s = "".join(w[0].upper() + w[1:] for w in re.findall(r"[A-Za-z0-9]+", label)) or "Concept"
    return "C" + s if s[0].isdigit() else s


class OntologyAgent(Agent):
    name = "ontology"

    def run(self, concepts: list[dict], relations: list[dict], domain: str) -> list[dict]:
        if not domain or not domain.strip():
            raise ValueError("Ontology generation requires a nonempty domain")
        context = ontology_review.context(concepts, relations)
        menu_lc = {k.lower(): v for k, v in upper.class_menu().items()}  # type defaults only; not shown to the model
        self.roots = {upper.describe(root).get("label", cat).lower(): root for cat, root in CATEGORIES.items()}
        self.stats = {"tier": tier(self.name)}
        self.by_id = {c["id"]: c for c in concepts}

        names = self._name_matches(concepts, menu_lc)
        rest = [c for c in concepts if c["id"] not in names]
        self.cands = {}
        rows_of = lambda cs: [{"id": c["id"], "label": c["label"], "type": c["type"], "alt": c["alt_labels"][:3],
                               "source_definitions": c["definitions"][:2], "relations": context[c["id"]][:8],
                               **({"candidates": [f"U:{x['label']} - {x['definition'][:90]}" for x in self.cands[c["id"]]]}
                                  if c["id"] in self.cands else {})} for c in cs]
        if tier(self.name) == "local":
            picks = self._pick_split(rest, menu_lc, rows_of)
        else:
            picks = self._pick_combined(rest, menu_lc, rows_of)
        picks.update(names)
        self.stats["parent_candidates_mean"] = round(sum(map(len, self.cands.values())) / max(len(self.cands), 1), 1)
        self.stats["parent_candidates_by_ontology"] = dict(Counter(
            (ontostore.term(x["iri"]) or {}).get("ontology", "BFO") for v in self.cands.values() for x in v))

        used, classes = set(), []
        for c in concepts:
            pick = picks.get(c["id"], {})
            parent = pick.get("parent") or ""
            entry = {**c, "excluded": bool(pick.get("exclude")), "parent_source": pick.get("source", "llm")}
            if pick.get("default"):
                entry["parent_source"] = "category_default"
            if pick.get("flags"):
                entry["review_flags"] = [*c.get("review_flags", []), *pick["flags"]]
            if parent in self.by_id and parent != c["id"] or parent.startswith("http"):
                entry["parent"] = parent
            else:
                entry["parent"], entry["parent_source"] = self._default(c, menu_lc), "type_default"
            identity = c["label"] + "\0" + c["type"]
            name = slug(c["label"]) + "_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
            if name in used:
                raise ValueError(f"Duplicate concept identity or identifier collision: {c['label']}")
            used.add(name)
            entry["iri"] = base() + quote(domain, safe="") + "/class/" + name
            classes.append(entry)
        self._repair(classes, menu_lc)
        ontology_review.paper_parents(classes, relations)
        self._lexical_heads(classes)
        for c in classes:
            if c["parent_source"] not in ("category_default", "type_default", "cycle_break"):
                c["review_flags"] = [f for f in c.get("review_flags", []) if f != "unresolved_placement"]
        self.stats["paper_is_a"] = sum(c["parent_source"] == "paper_is_a" for c in classes)
        self.stats["name_matches"] = sum(c["parent_source"] == "name_match" for c in classes)
        self.stats["unresolved_placements"] = sum("unresolved_placement" in c.get("review_flags", []) for c in classes)
        self.stats["category_conflicts"] = sum("paper_parent_category_conflict" in c.get("review_flags", []) for c in classes)
        self.stats["row_coverage"] = {k: dict(v) for k, v in self.row_stats.items()}
        log(f"placement sources: {dict(Counter(c['parent_source'] for c in classes))}; "
            f"{self.stats['unresolved_placements']} unresolved; {sum(c['excluded'] for c in classes)} excluded")
        return classes

    def _name_matches(self, concepts: list[dict], menu_lc: dict) -> dict:
        """A concept whose label names an MDS-Onto or PMDCO class (any of its labels, normalised) is placed under
        that class alone; its route to CCO/BFO is that ontology's own. Used only when the route reaches BFO."""
        order = ONTOLOGY_SEARCH["name_match_ontologies"]
        out, unaligned = {}, 0
        for c in concepts:
            hits = sorted(ontostore.exact(c["label"], kinds=("class",), ontologies=order),
                          key=lambda x: order.index(x["ontology"]))
            hit = next((x for x in hits if ontostore.reaches_bfo(x["iri"])), None)
            unaligned += bool(hits) and hit is None
            if hit:
                roots = {self._root(hit["iri"]), self._root(self._default(c, menu_lc))}
                flags = ["name_match_category_conflict"] if None not in roots and len(roots) > 1 else []
                out[c["id"]] = {"parent": hit["iri"], "source": "name_match", "flags": flags}
        self.stats["name_matches_not_reaching_bfo"] = unaligned
        log(f"name matches: {len(out)} concept(s) placed under a same-name {' or '.join(order)} class"
            + (f"; {unaligned} match(es) skipped (no route to BFO)" if unaligned else ""))
        return out

    def _root(self, iri: str) -> str | None:
        """The BFO category root (of CATEGORIES) above an external class."""
        chain = [iri, *upper.ancestors(iri)]
        return next((r for r in CATEGORIES.values() if r in chain), None)

    def _candidates(self, concepts: list[dict], menu_lc: dict, cats: dict | None = None):
        """Parent candidates per concept from the ontology store: CCO classes first, then BFO, found by label,
        synonyms and lexical head (exact and trigram) and by embedding; then the type default and, on the local
        tier, the root of the concept's BFO category. With cats, only candidates inside that category."""
        order = ONTOLOGY_SEARCH["parent_ontologies"]
        k = ONTOLOGY_SEARCH["parents_per_class"]
        texts = {c["id"]: f"{c['label']}: {(c['definitions'][0]['text'] if c['definitions'] else '')[:200]}"
                 for c in concepts}
        vectors = dict(zip(texts, retrieval.embed(list(texts.values()), self.ledger, self.name))) \
            if ontostore.has_vectors() and texts else {}
        for c in concepts:
            queries = [c["label"], *c["alt_labels"][:2], lexical.head_query(c["label"]) or ""]
            found = ontostore.search(queries, vectors.get(c["id"]), kinds=("class",), ontologies=order, k=k * 3,
                                     nearest=3)
            root = CATEGORIES.get(cats[c["id"]]) if cats else None
            if root:
                found = [x for x in found if root in [x["iri"], *upper.ancestors(x["iri"])]]
            found.sort(key=lambda x: (order.index(x["ontology"]), -x["score"]))
            extra = [self._default(c, menu_lc)] + ([root] if root else [])
            if root and root not in [self._default(c, menu_lc), *upper.ancestors(self._default(c, menu_lc))]:
                extra = [root]  # the type default sits in another category
            found = found[:k] + [{"iri": i, **upper.describe(i)} for i in extra if i not in {x["iri"] for x in found[:k]}]
            self.cands[c["id"]] = [{"iri": x["iri"], "label": x.get("label", ""), "definition": x.get("definition", "")}
                                   for x in found]

    def _resolve(self, cid: str, answer) -> str | None:
        """A model answer as a parent: a corpus id, one of the concept's candidates, or a BFO category root."""
        a = key(answer) or ""
        if a in self.by_id:
            return a
        label = (a[2:] if a.startswith("U:") else a).split(" - ")[0].strip().lower()
        hit = next((x["iri"] for x in self.cands.get(cid, []) if x["label"].lower() == label), None)
        return hit or self.roots.get(label)

    def _pick_combined(self, concepts: list[dict], menu_lc: dict, rows_of) -> dict:
        """Frontier tier: one call per batch chooses the parent (a candidate, a BFO category or a corpus concept)
        and exclusion."""
        self._candidates(concepts, menu_lc)
        index = "\n".join(f"{c['id']}: {c['label']} - " + (c["definitions"][0]["text"][:160] if c["definitions"] else "")
                          for c in concepts)
        system = (f"{self.system}\n\nBFO CATEGORIES\n" + "\n".join(f"U:{lab}" for lab in self.roots)
                  + f"\n\nCORPUS CONCEPTS\n{index}")  # stable across batches -> cached
        log(f"placing {len(concepts):,} concepts under store candidates or each other ({-(-len(concepts) // BATCH)} call(s))")
        picks = {}
        for r in self.call_rows(rows_of(concepts), system, "hierarchy", "classes", "parent", size=BATCH):
            cid = key(r.get("id"))
            if cid in self.by_id:
                picks[cid] = {"parent": self._resolve(cid, r.get("parent")), "exclude": bool(r.get("exclude"))}
        return picks

    def _pick_split(self, concepts: list[dict], menu_lc: dict, rows_of) -> dict:
        """Local tier: pass 1 picks a BFO category (or 'not a class'); pass 2 picks the parent from that concept's
        store candidates inside the category and the corpus concepts in it. Pass 2 may override a wrong category
        with another root."""
        cat_prompt = load_prompt("ontology_category") + "\n\nCATEGORIES\n" + "\n".join(
            [f"- {c}" for c in CATEGORIES] + ["- not a class"])
        cats, n_batches = {}, -(-len(concepts) // SPLIT_BATCH)
        log(f"ontology pass 1: BFO category for {len(concepts):,} concepts ({n_batches} call(s))")
        for r in self.call_rows(rows_of(concepts), cat_prompt, "category", "classes", "category",
                                size=SPLIT_BATCH):
            cat = str(r.get("category", "")).strip().lower()
            if cat in CATEGORIES or cat == "not a class":
                cats[key(r.get("id"))] = cat
        for c in concepts:  # no answer: category of the type's default parent
            if c["id"] not in cats:
                default = [self._default(c, menu_lc)] + upper.ancestors(self._default(c, menu_lc))
                cats[c["id"]] = next((k for k, root in CATEGORIES.items() if root in default), "material entity")
                self.stats["category_default"] = self.stats.get("category_default", 0) + 1
        picks = {cid: {"parent": "", "exclude": True} for cid, cat in cats.items() if cat == "not a class"}
        kept = [c for c in concepts if cats[c["id"]] != "not a class"]
        log(f"parent candidates from the ontology store for {len(kept):,} concepts")
        self._candidates(kept, menu_lc, cats)
        root_labels = {k: upper.describe(root).get("label", k) for k, root in CATEGORIES.items()}
        for cat, root in CATEGORIES.items():
            members = [c for c in kept if cats[c["id"]] == cat]
            if not members:
                continue
            same = sorted(members, key=lambda c: -c.get("score", 0))[:PARENT_CONCEPTS]
            system = (load_prompt("ontology_parent") + f"\n\nCATEGORY\n{cat} (U:{root_labels[cat]})"
                      + "\n\nOTHER CATEGORIES\n" + ", ".join(f"U:{l}" for k, l in root_labels.items() if k != cat)
                      + "\n\nCORPUS CONCEPTS\n" + "\n".join(f"{c['id']}: {c['label']} - "
                          + (c["definitions"][0]["text"][:160] if c["definitions"] else "") for c in same))
            n = -(-len(members) // SPLIT_BATCH)
            log(f"ontology pass 2: parents for {len(members)} {cat} concept(s) ({n} call(s))")
            for r in self.call_rows(rows_of(members), system, f"parent_{cat}", "classes", "parent",
                                    size=SPLIT_BATCH, label=f"parent {cat}", stat="parent"):
                cid = key(r.get("id"))
                if not cid or cid not in self.by_id:
                    continue
                parent = self._resolve(cid, r.get("parent"))
                if parent in self.by_id and cats.get(parent) != cat:  # local parent from another category
                    self.stats["category_mismatch"] = self.stats.get("category_mismatch", 0) + 1
                    parent = root
                if parent and parent not in self.by_id and root not in [parent] + upper.ancestors(parent):
                    self.stats["category_override"] = self.stats.get("category_override", 0) + 1
                if parent:
                    picks[cid] = {"parent": parent, "exclude": False}
            for c in members:  # no usable answer: the category's root
                picks.setdefault(c["id"], {"parent": root, "exclude": False, "default": True})
        self.stats["categories"] = dict(Counter(cats.values()))
        return picks

    @staticmethod
    def _default(c: dict, menu_lc: dict) -> str:
        label = upper.menus()["type_defaults"].get(c["type"], "entity")
        return menu_lc.get(label.lower(), upper.ENTITY)

    @staticmethod
    def _lexical_heads(classes: list[dict]):
        """Where the model attached a concept straight to BFO/CCO, nest it under its obvious lexical head
        instead - only if the head is kept, falls in the same BFO category, and no cycle results."""
        live = {c["id"]: c for c in classes if not c["excluded"]}
        moved = 0
        for child_id, head_id in lexical.heads(list(live.values())).items():
            c, head = live[child_id], live.get(head_id)
            if head is None or c["parent"] in live or c["parent_source"] == "name_match" \
                    or child_id in lineage(head_id, live):
                continue
            if bfo_category(child_id, live) != bfo_category(head_id, live):
                continue
            c["parent"], c["parent_source"] = head_id, "lexical_head"
            moved += 1
        log(f"lexical heads: {moved} concept(s) nested under a more general corpus concept")

    def _repair(self, classes: list[dict], menu_lc: dict):
        """Break is-a cycles, then route children of excluded concepts to the nearest kept ancestor."""
        by_id = {c["id"]: c for c in classes}
        for c in classes:
            seen, p = {c["id"]}, c["parent"]
            while p in by_id:
                if p in seen:
                    c["parent"], c["parent_source"] = self._default(c, menu_lc), "cycle_break"
                    break
                seen.add(p)
                p = by_id[p]["parent"]
        for c in classes:
            p = c["parent"]
            while p in by_id and by_id[p]["excluded"]:
                p = by_id[p]["parent"]
            c["parent"] = p
