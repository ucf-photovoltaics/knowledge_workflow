"""Ontology agent: place canonical concepts under BFO/CCO classes or under each other, and assign IRIs."""
import re
import hashlib
from urllib.parse import quote
from collections import Counter

from src.agents.base import Agent, compact, items, key, load_prompt
from src.config import tier
from src.tools import lexical, upper, ontology_review
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
        menu = upper.class_menu()
        menu_lc = {k.lower(): v for k, v in menu.items()}
        menu_text = "\n".join(f"U:{lab} - {upper.describe(iri).get('definition', '')[:90]}" for lab, iri in menu.items())
        index = "\n".join(f"{c['id']}: {c['label']} - "
                          + (c["definitions"][0]["text"][:160] if c["definitions"] else "") for c in concepts)
        system = f"{self.system}\n\nUPPER CLASSES\n{menu_text}\n\nCORPUS CONCEPTS\n{index}"  # stable across batches -> cached

        self.stats = {"tier": tier(self.name)}
        rows_of = lambda cs: [{"id": c["id"], "label": c["label"], "type": c["type"], "alt": c["alt_labels"][:3],
                               "source_definitions": c["definitions"][:2], "relations": context[c["id"]][:8]} for c in cs]
        if tier(self.name) == "local":
            picks = self._pick_split(concepts, menu, menu_lc, rows_of)
        else:
            picks = self._pick_combined(concepts, system, menu, rows_of)

        ids, used, classes = {c["id"] for c in concepts}, set(), []
        for c in concepts:
            pick = picks.get(c["id"], {})
            parent = key(pick.get("parent")) or ""
            entry = {**c, "excluded": bool(pick.get("exclude")),
                     "parent_source": "category_default" if pick.get("default") else "llm"}
            if parent.startswith("U:") and parent[2:].strip().lower() in menu_lc:
                entry["parent"] = menu_lc[parent[2:].strip().lower()]
            elif parent in ids and parent != c["id"]:
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
        self.stats["unresolved_placements"] = sum("unresolved_placement" in c.get("review_flags", []) for c in classes)
        self.stats["category_conflicts"] = sum("paper_parent_category_conflict" in c.get("review_flags", []) for c in classes)
        self.stats["row_coverage"] = {k: dict(v) for k, v in self.row_stats.items()}
        placed = sum(1 for c in classes if c["parent_source"] == "llm")
        log(f"placement sources: {dict(Counter(c['parent_source'] for c in classes))}; "
            f"{self.stats['unresolved_placements']} unresolved; {sum(c['excluded'] for c in classes)} excluded")
        return classes

    def _pick_combined(self, concepts: list[dict], system: str, menu: dict, rows_of) -> dict:
        """Frontier tier: one call per batch chooses parent (upper class or corpus concept) and exclusion."""
        n_batches = -(-len(concepts) // BATCH)
        log(f"placing {len(concepts):,} concepts under {len(menu)} BFO/CCO classes or each other ({n_batches} call(s))")
        answers = self.call_rows(rows_of(concepts), system, "hierarchy", "classes", "parent", size=BATCH)
        return {key(r.get("id")): r for r in answers}

    def _pick_split(self, concepts: list[dict], menu: dict, menu_lc: dict, rows_of) -> dict:
        """Local tier: pass 1 picks a BFO category (or 'not a class'); pass 2 picks the parent from the upper classes
        of that category and the corpus concepts in it. Pass 2 may override a wrong category with another root."""
        cat_prompt = load_prompt("ontology_category") + "\n\nCATEGORIES\n" + "\n".join(
            [f"- {c}" for c in CATEGORIES] + ["- not a class"])
        cats, n_batches = {}, -(-len(concepts) // SPLIT_BATCH)
        log(f"ontology pass 1: BFO category for {len(concepts):,} concepts ({n_batches} call(s))")
        for r in self.call_rows(rows_of(concepts), cat_prompt, "category", "classes", "category", size=SPLIT_BATCH):
            cat = str(r.get("category", "")).strip().lower()
            if cat in CATEGORIES or cat == "not a class":
                cats[key(r.get("id"))] = cat
        for c in concepts:  # no answer: category of the type's default parent
            if c["id"] not in cats:
                default = [self._default(c, menu_lc)] + upper.ancestors(self._default(c, menu_lc))
                cats[c["id"]] = next((k for k, root in CATEGORIES.items() if root in default), "material entity")
                self.stats["category_default"] = self.stats.get("category_default", 0) + 1
        picks = {cid: {"parent": "", "exclude": True} for cid, cat in cats.items() if cat == "not a class"}
        root_labels = {k: upper.describe(root).get("label", k) for k, root in CATEGORIES.items()}
        by_id = {c["id"]: c for c in concepts}
        for cat, root in CATEGORIES.items():
            members = [c for c in concepts if cats[c["id"]] == cat]
            if not members:
                continue
            sub_menu = {lab: iri for lab, iri in menu.items() if root in [iri] + upper.ancestors(iri)}
            same = sorted(members, key=lambda c: -c.get("score", 0))[:PARENT_CONCEPTS]
            system = (load_prompt("ontology_parent") + f"\n\nCATEGORY\n{cat} (U:{root_labels[cat]})\n\nUPPER CLASSES\n"
                      + "\n".join(f"U:{lab} - {upper.describe(iri).get('definition', '')[:90]}" for lab, iri in sub_menu.items())
                      + "\n\nOTHER CATEGORIES\n" + ", ".join(f"U:{l}" for k, l in root_labels.items() if k != cat)
                      + "\n\nCORPUS CONCEPTS\n" + "\n".join(f"{c['id']}: {c['label']} - "
                          + (c["definitions"][0]["text"][:160] if c["definitions"] else "") for c in same))
            n = -(-len(members) // SPLIT_BATCH)
            log(f"ontology pass 2: parents for {len(members)} {cat} concept(s) ({n} call(s), {len(sub_menu)} upper classes)")
            for r in self.call_rows(rows_of(members), system, f"parent_{cat}", "classes", "parent",
                                    size=SPLIT_BATCH, label=f"parent {cat}", stat="parent"):
                cid, parent = key(r.get("id")), key(r.get("parent")) or ""
                if not cid or cid not in by_id:
                    continue
                if parent in by_id and cats.get(parent) != cat:  # local parent from another category
                    self.stats["category_mismatch"] = self.stats.get("category_mismatch", 0) + 1
                    parent = f"U:{root_labels[cat]}"
                target = menu_lc.get(parent[2:].strip().lower()) if parent.startswith("U:") else None
                if target and root not in [target] + upper.ancestors(target):
                    self.stats["category_override"] = self.stats.get("category_override", 0) + 1
                picks[cid] = {"parent": parent, "exclude": False}
            for c in members:  # no usable answer: the category's root
                picks.setdefault(c["id"], {"parent": f"U:{root_labels[cat]}", "exclude": False, "default": True})
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
            if head is None or c["parent"] in live or child_id in lineage(head_id, live):
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
