"""Build LoRA training data from a suite of ontologies, in the pipeline's own prompt and JSON formats.

Each example hides something an expert-built ontology already states and asks for it back, using the exact
system prompt and output schema of the local-tier pass that makes that call (PIPELINE_TIER local):
  category / parent                  - BFO category, then parent (U:<upper class> or corpus id)  -> ontology agent
  definitions / synonyms / disjointness - the enrichment passes                                  -> enrichment agent
  filter / align                     - screen look-alike candidates, then choose the mapping relation -> interoperability
  restrict  - turn paper-style relations into BFO/CCO/RO properties whose domain and range fit, or drop them
              (the local-tier restrictions pass; built from property definitions, domains and ranges)
  extract   - (optional) section -> concepts/relations/causal/measurements/figures: the exact per-section calls of
              an earlier (e.g. frontier-model) run on a collection NOT in LORA["exclude_collections"] -> extraction agent
Splits are by ontology branch (source + nearest curated upper class), so test branches never appear in training.
"""
import hashlib
import json
import random
import re
import zipfile
from collections import Counter, defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import rdflib
import requests
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from src.agents.base import compact, load_prompt
from src.agents.enrichment import EnrichmentAgent
from src.agents.ontology import CATEGORIES
from src.config import CACHE, LORA, OUTPUTS, RESOURCES
from src.tools import upper
from src.tools.owl import BFO_CATEGORIES
from src.tools.progress import log

OUT = OUTPUTS / "lora"
DEF_PROPS = [SKOS.definition, rdflib.URIRef("http://purl.obolibrary.org/obo/IAO_0000115"),
             rdflib.URIRef("https://spec.industrialontologies.org/ontology/annotation/naturalLanguageDefinition"),
             rdflib.URIRef("http://qudt.org/schema/qudt/plainTextDescription")]
QUANTITY_KIND = rdflib.URIRef("http://qudt.org/schema/qudt/QuantityKind")
OWNER = (("purl.obolibrary.org/obo/BFO_", "BFO"), ("commoncoreontologies.org", "CCO"), ("w3id.org/pmd", "PMDCO"),
         ("industrialontologies.org", "IOF"), ("cwrusdle.bitbucket.io", "MDS-ONTO"), ("qudt.org", "QUDT"))
TYPE_OF = {"material entity": "material", "quality": "property", "relational quality": "property",
           "disposition": "property", "function": "property", "role": "property", "site": "condition",
           "immaterial entity": "condition", "generically dependent continuant": "information",
           "process": "process", "process boundary": "process", "process profile": "process",
           "temporal region": "condition", "spatial region": "condition", "spatiotemporal region": "condition"}
MATERIAL_ARTIFACT = "https://www.commoncoreontologies.org/ont00000995"
GENUS = re.compile(r"^(an?|the)\s+[^.]{0,80}?\s+(that|which|in which|whose|where)\s+", re.I)


def _owner(iri: str) -> str | None:
    return next((name for frag, name in OWNER if frag in iri), None)


def _text(g, s, props, langs=("en", "en-us", None)):
    for p in props:
        for lang in langs:
            for o in g.objects(s, p):
                if isinstance(o, rdflib.Literal) and (o.language or None) == lang and str(o).strip():
                    return re.sub(r"\s+", " ", str(o)).strip()
    return ""


def _all_text(g, s, p):
    return sorted({str(o).strip() for o in g.objects(s, p)
                   if isinstance(o, rdflib.Literal) and (o.language or "en").lower().startswith("en") and str(o).strip()})


def _fetch(name: str, loc: str, folder: Path) -> tuple[rdflib.Graph, Path]:
    ext = ".ttl" if loc.lower().endswith(".ttl") else ".owl"
    path = Path(loc) if Path(loc).exists() else folder / f"{name}{ext}"
    if not path.exists():
        log(f"downloading {name}")
        r = requests.get(loc, timeout=180)
        r.raise_for_status()
        path.write_bytes(r.content)
    return rdflib.Graph().parse(path, format="turtle" if ext == ".ttl" else "xml"), path


def load_suite() -> tuple[rdflib.Graph, list[dict]]:
    """Download (cached) and parse every ontology in LORA['ontologies'] into one graph."""
    g, sources = rdflib.Graph(), []
    folder = CACHE / "ontologies"
    folder.mkdir(parents=True, exist_ok=True)
    for name, loc in LORA["ontologies"].items():
        try:
            part, path = _fetch(name, loc, folder)
        except Exception as e:
            log(f"skipping {name}: {type(e).__name__}: {e}")
            continue
        onto = next(part.subjects(RDF.type, OWL.Ontology), None)
        sources.append({"name": name, "location": loc, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "triples": len(part), "ontology_iri": str(onto) if onto else None,
                        "version": str(part.value(onto, OWL.versionIRI) or part.value(onto, OWL.versionInfo) or "")
                        if onto else ""})
        g += part
        log(f"{name}: {len(part):,} triples")
    return g, sources


def collect_terms(g: rdflib.Graph) -> dict[str, dict]:
    labels = [RDFS.label, SKOS.prefLabel]
    subjects = {s for s in g.subjects(RDF.type, OWL.Class) if isinstance(s, rdflib.URIRef)}
    subjects |= {s for s in g.subjects(RDF.type, QUANTITY_KIND) if isinstance(s, rdflib.URIRef)}
    terms = {}
    for s in subjects:
        iri, label = str(s), _text(g, s, labels)
        if not label or not _owner(iri):
            continue
        restrictions, mappings = [], []
        for o in g.objects(s, RDFS.subClassOf):
            if isinstance(o, rdflib.BNode):
                p, t = g.value(o, OWL.onProperty), g.value(o, OWL.someValuesFrom)
                if isinstance(p, rdflib.URIRef) and isinstance(t, rdflib.URIRef):
                    restrictions.append((str(p), str(t)))
        for pred, rel in ((OWL.equivalentClass, "equivalent"), (SKOS.exactMatch, "exact"), (SKOS.closeMatch, "close")):
            mappings += [(str(o), rel) for o in g.objects(s, pred) if isinstance(o, rdflib.URIRef)]
        terms[iri] = {
            "iri": iri, "label": label, "source": _owner(iri), "definition": _text(g, s, DEF_PROPS),
            "alts": [a for a in _all_text(g, s, SKOS.altLabel) if a.lower() != label.lower()],
            "parents": [str(o) for o in g.objects(s, RDFS.subClassOf) if isinstance(o, rdflib.URIRef)],
            "restrictions": restrictions, "mappings": mappings,
            "disjoint": [str(o) for o in g.objects(s, OWL.disjointWith) if isinstance(o, rdflib.URIRef)],
            "individual": (s, RDF.type, QUANTITY_KIND) in g,
        }
    for t in terms.values():
        t["ancestors"] = _ancestors(t["iri"], terms)
        t["type"] = next((TYPE_OF[BFO_CATEGORIES[a]] for a in t["ancestors"] if a in BFO_CATEGORIES), "")
        if MATERIAL_ARTIFACT in t["ancestors"]:
            t["type"] = "device"
    return terms


def _ancestors(iri: str, terms: dict) -> list[str]:
    out, queue = [], list(terms[iri]["parents"])
    while queue:
        p = queue.pop(0)
        if p not in out and p != iri:
            out.append(p)
            queue += terms[p]["parents"] if p in terms else upper.describe(p).get("parents", [])
    return out


def _split(key: str) -> str:
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16) % 20
    return "test" if h < 2 else "val" if h == 2 else "train"


def _chunks(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _example(task, key, system, user, answer, meta=None) -> dict:
    return {"task": task, "split": _split(key), "group": key,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user},
                         {"role": "assistant", "content": compact(answer)}], "meta": meta or {}}


def _category(t: dict) -> str | None:
    """The local-tier BFO category of a term: the nearest CATEGORIES root among its ancestors."""
    roots = {root: cat for cat, root in CATEGORIES.items()}
    return next((roots[a] for a in [t["iri"], *t["ancestors"]] if a in roots), None)


def hierarchy_examples(terms: dict, rng: random.Random, repeat: int) -> list[dict]:
    """The ontology agent's two local passes, as the pipeline sends them:
      category - pick the BFO category of each concept (ontology_category)
      parent   - pick the parent among that category's upper classes and the corpus concepts in it (ontology_parent)"""
    menu = upper.class_menu()
    menu_iri = {iri: lab for lab, iri in menu.items()}
    cat_system = load_prompt("ontology_category") + "\n\nCATEGORIES\n" + "\n".join(
        [f"- {c}" for c in CATEGORIES] + ["- not a class"])
    root_labels = {k: upper.describe(root).get("label", k) for k, root in CATEGORIES.items()}
    sub_menus = {cat: {lab: iri for lab, iri in menu.items() if root in [iri] + upper.ancestors(iri)}
                 for cat, root in CATEGORIES.items()}
    groups = defaultdict(list)
    for t in terms.values():
        if t["iri"] in menu_iri or t["individual"] or t["source"] == "QUDT" or not _category(t):
            continue
        branch = next((menu_iri[a] for a in t["ancestors"] if a in menu_iri), None)
        if branch:
            groups[f"{t['source']}|{branch}"].append(t)
    by_cat = defaultdict(list)
    for t in terms.values():
        if t["iri"] not in menu_iri and not t["individual"] and _category(t):
            by_cat[(t["source"], _category(t))].append(t)
    row = lambda t, ids: {"id": ids[t["iri"]], "label": t["label"], "type": t["type"], "alt": t["alts"][:3],
                          "def": GENUS.sub("", t["definition"])[:160] if rng.random() < 0.5 else ""}
    out = []
    for key, members in sorted(groups.items()):
        if repeat and _split(key) != "train":
            continue
        rng.shuffle(members)
        for chunk in _chunks(members, LORA["hierarchy_batch"]):
            ids = {t["iri"]: f"k{n}" for n, t in enumerate(chunk, 1)}
            out.append(_example("category", key, cat_system, compact([row(t, ids) for t in chunk]),
                                {"classes": [{"id": ids[t["iri"]], "category": _category(t)} for t in chunk]},
                                {"source": chunk[0]["source"]}))
            for cat in sorted({_category(t) for t in chunk}):
                same = [t for t in chunk if _category(t) == cat]
                index = {t["iri"]: t for t in same}
                for t in same:  # nearest local ancestor, so local parents are choosable
                    near = next((a for a in t["ancestors"] if a in terms and a not in menu_iri), None)
                    if near and _category(terms[near]) == cat:
                        index.setdefault(near, terms[near])
                pool = by_cat[(same[0]["source"], cat)]
                for t in rng.sample(pool, min(15, len(pool))):
                    index.setdefault(t["iri"], t)
                order = list(index)
                rng.shuffle(order)
                pids = {iri: f"k{n}" for n, iri in enumerate(order, 1)}
                sub = sub_menus[cat]
                system = (load_prompt("ontology_parent") + f"\n\nCATEGORY\n{cat} (U:{root_labels[cat]})\n\nUPPER CLASSES\n"
                          + "\n".join(f"U:{lab} - {upper.describe(iri).get('definition', '')[:90]}" for lab, iri in sub.items())
                          + "\n\nOTHER CATEGORIES\n" + ", ".join(f"U:{l}" for k, l in root_labels.items() if k != cat)
                          + "\n\nCORPUS CONCEPTS\n" + "\n".join(f"{pids[i]}: {index[i]['label']}" for i in order))
                sub_iris = {iri: lab for lab, iri in sub.items()}
                answer, acceptable = [], {}
                for t in same:
                    refs = [pids[a] if a in pids else f"U:{sub_iris[a]}" for a in t["ancestors"]
                            if a in pids or a in sub_iris] or [f"U:{root_labels[cat]}"]
                    answer.append({"id": pids[t["iri"]], "parent": refs[0]})
                    acceptable[pids[t["iri"]]] = refs
                out.append(_example("parent", key, system, compact([row(t, pids) for t in same]),
                                    {"classes": answer}, {"acceptable": acceptable, "source": same[0]["source"]}))
    return out


def enrich_examples(terms: dict, rng: random.Random, repeat: int) -> list[dict]:
    """The enrichment agent's local passes, as the pipeline sends them: definitions, synonyms (true alt labels
    among sibling decoys) and disjointness among siblings. Restrictions are the separate restrict task."""
    prompts = {n: load_prompt(f"enrichment_{n}") for n in ("definitions", "synonyms", "disjoint")}
    children = defaultdict(list)
    for t in terms.values():
        if t["parents"] and not t["individual"]:
            children[t["parents"][0]].append(t)
    out = []
    for parent, kids in sorted(children.items()):
        key = f"{kids[0]['source']}|{parent}"
        if repeat and _split(key) != "train":
            continue
        defined = [t for t in kids if t["definition"]]
        rng.shuffle(defined)
        parent_label = terms[parent]["label"] if parent in terms else upper.describe(parent).get("label", "")
        if not parent_label:
            continue
        for chunk in _chunks(defined, LORA["enrich_batch"]):
            ids = {}
            ref = lambda iri: ids.setdefault(iri, f"k{len(ids) + 1}")
            for t in chunk:
                ref(t["iri"])
            in_chunk = {t["iri"] for t in chunk}
            sibling_pool = [k for k in kids if k["iri"] not in in_chunk]
            defs, syns, disj = [], [], []
            for t in chunk:
                related = [f"related_to: {terms[x]['label'] if x in terms else upper.describe(x).get('label', '')} ({ref(x)}) x1"
                           for _, x in t["restrictions"] if x in terms or upper.describe(x)][:4]
                defs.append(({"id": ids[t["iri"]], "label": t["label"], "parent": parent_label, "defs": [],
                              "relations": related}, {"id": ids[t["iri"]], "definition": t["definition"]}))
                decoys = [x["label"] for x in rng.sample(sibling_pool, min(2, len(sibling_pool)))]
                if t["alts"] or decoys:
                    alts = t["alts"] + decoys
                    rng.shuffle(alts)
                    syns.append(({"id": ids[t["iri"]], "label": t["label"], "alt": alts[:8]},
                                 {"id": ids[t["iri"]], "alt_labels": t["alts"]}))
                sibs = [k for k in kids if k["iri"] != t["iri"]][:12]
                if sibs:
                    sib_ids = {s["iri"] for s in sibs}
                    disj.append(({"id": ids[t["iri"]], "label": t["label"], "parent": parent_label,
                                  "siblings": [f"{ref(s['iri'])}: {s['label']}" for s in sibs]},
                                 {"id": ids[t["iri"]], "disjoint_with": [ids[d] for d in t["disjoint"] if d in sib_ids]}))
            for task, pairs, prompt in (("definitions", defs, "definitions"), ("synonyms", syns, "synonyms"),
                                        ("disjointness", disj, "disjoint")):
                if pairs:
                    out.append(_example(task, key, prompts[prompt], compact([r for r, _ in pairs]),
                                        {"classes": [a for _, a in pairs]}, {"source": chunk[0]["source"]}))
    return out


BFO = "http://purl.obolibrary.org/obo/BFO_"
CONTINUANT, OCCURRENT, IC, SDC = BFO + "0000002", BFO + "0000003", BFO + "0000004", BFO + "0000020"
MATERIAL, PROCESS = BFO + "0000040", BFO + "0000015"
# Paper-style relation phrases -> menu properties that formalize them, most specific first, and the subject/object
# categories the relation needs where the properties leave domain or range open. Gold = first property that fits.
RELATION_GROUPS = [
    (["part_of", "is_part_of", "component_of", "belongs_to"], ["BFO:continuant part of", "BFO:occurrent part of"], None, None),
    (["has_part", "contains", "consists_of", "includes"], ["BFO:has continuant part", "BFO:has occurrent part"], None, None),
    (["has_property", "has_quality", "characterized_by", "exhibits"], ["RO:has quality", "RO:has characteristic"], IC, None),
    (["has_disposition", "susceptible_to", "prone_to"], ["RO:has disposition"], None, None),
    (["has_function", "functions_as", "serves_to"], ["RO:has function"], None, None),
    (["has_role", "acts_as", "plays_role_of"], ["RO:has role"], None, None),
    (["capable_of", "can_perform"], ["RO:capable of"], None, None),
    (["has_input", "consumes", "takes_as_input"], ["CCO:has input", "RO:has input"], None, CONTINUANT),
    (["has_output", "produces", "yields", "generates"], ["CCO:has output", "RO:has output"], PROCESS, CONTINUANT),
    (["input_of", "used_in", "consumed_by"], ["CCO:is input of", "RO:input of"], CONTINUANT, PROCESS),
    (["output_of", "produced_by", "result_of"], ["CCO:is output of", "RO:output of"], CONTINUANT, PROCESS),
    (["participates_in", "involved_in", "takes_part_in"], ["RO:participates in", "BFO:participates in"], None, None),
    (["has_participant", "involves"], ["RO:has participant", "BFO:has participant"], None, None),
    (["located_in", "found_in", "positioned_in"], ["RO:located in"], None, None),
    (["adjacent_to", "next_to", "in_contact_with"], ["RO:adjacent to"], None, None),
    (["connected_to", "attached_to", "bonded_to"], ["RO:connected to"], IC, IC),
    (["composed_primarily_of", "mainly_made_of"], ["RO:composed primarily of"], None, None),
    (["derived_from", "made_from", "obtained_from"], ["RO:derives from"], MATERIAL, MATERIAL),
    (["transformation_of", "converted_from"], ["RO:transformation of"], MATERIAL, MATERIAL),
    (["measured_by", "quantified_by"], ["CCO:is measured by"], None, None),
    (["measures", "is_measurement_of"], ["CCO:is a measurement of"], None, None),
    (["describes", "is_about", "reports_on"], ["CCO:is about"], None, None),
    (["precedes", "followed_by", "comes_before"], ["BFO:precedes"], None, None),
    (["occurs_in", "takes_place_in"], ["BFO:occurs in"], OCCURRENT, IC),
    (["regulates", "controls", "tunes"], ["RO:regulates characteristic"], None, SDC),
    (["realizes", "manifests"], ["BFO:realizes"], None, None),
]


def restrict_examples(rng: random.Random) -> list[dict]:
    """Relations as the restrictions pass sees them ("phrase: target (id) xN"); the answer keeps the ones a menu
    property formalizes with a fitting domain and range (the first fitting property of the phrase's group) and drops
    the rest: the same phrase between the wrong kinds of entity, and vague relations to unrelated classes."""
    pmenu = upper.property_menu()
    system = load_prompt("enrichment_restrictions") + "\n\nPROPERTIES\n" + "\n".join(
        EnrichmentAgent._prop_line(k, iri) for k, iri in pmenu.items())
    classes = upper.terms()["classes"]
    pool = [i for i, c in classes.items() if c.get("label") and c.get("parents")]
    line = {i: {i, *upper.ancestors(i)} for i in pool}

    def ok(req, iri):
        return not req or req == upper.ENTITY or req in line[iri]

    def fits(key, need_s, need_o, s, o):
        meta = upper.describe(pmenu[key])
        return ok(need_s, s) and ok(need_o, o) and ok(meta.get("domain"), s) and ok(meta.get("range"), o)

    groups = [(ph, [k for k in props if k in pmenu], ns, no) for ph, props, ns, no in RELATION_GROUPS]
    groups = [g for g in groups if g[1]]
    by_subject = {"train": defaultdict(list), "val": defaultdict(list), "test": defaultdict(list)}
    target = {"train": LORA["restrict_examples"] * LORA["restrict_batch"] * 2}  # relations; ~2 per subject row
    target["val"] = target["test"] = max(LORA["restrict_batch"] * 4, target["train"] // 10)
    ends = {}  # (property, need_s, need_o) -> (subjects, objects) that fit it

    def fitting(key, ns, no):
        if (key, ns, no) not in ends:
            meta = upper.describe(pmenu[key])
            ends[(key, ns, no)] = ([i for i in pool if ok(ns, i) and ok(meta.get("domain"), i)],
                                   [i for i in pool if ok(no, i) and ok(meta.get("range"), i)])
        return ends[(key, ns, no)]

    made, tries = Counter(), 0
    while any(made[k] < n for k, n in target.items()) and tries < 400_000:
        tries += 1
        phrases, props, ns, no = rng.choice(groups)
        kind = rng.random()
        if kind < 0.55:  # a relation one of the group's properties formalizes
            subjects, objects = fitting(rng.choice(props), ns, no)
            if not subjects or not objects:
                continue
            s, o = rng.choice(subjects), rng.choice(objects)
        else:
            s, o = rng.choice(pool), rng.choice(pool)
        good = [k for k in props if fits(k, ns, no, s, o)]
        if s == o or (kind < 0.8 and bool(good) != (kind < 0.55)):
            continue
        if kind < 0.8:  # kept with its first fitting property, or the right words between the wrong kinds of entity
            phrase, gold = rng.choice(phrases), good
        else:  # a vague relation: nothing to formalize
            phrase, gold = rng.choice(["related_to", "associated_with", "compared_with", "studied_with"]), []
        split = _split(f"restrict|{s}")
        if made[split] >= target[split] or len(by_subject[split][s]) >= 3 \
                or any(o == x for _, x, _ in by_subject[split][s]):
            continue
        by_subject[split][s].append((phrase, o, gold))
        made[split] += 1
    out = []
    for split, subjects in by_subject.items():
        items = list(subjects.items())
        rng.shuffle(items)
        for chunk in _chunks(items, LORA["restrict_batch"]):
            ids = {}
            ref = lambda iri: ids.setdefault(iri, f"k{len(ids) + 1}")
            rows, answer, acceptable = [], [], {}
            for s, rels in chunk:
                sid = ref(s)
                rows.append({"id": sid, "label": classes[s]["label"],
                             "parent": classes.get(classes[s]["parents"][0], {}).get("label", ""),
                             "relations": [f"{ph}: {classes[o]['label']} ({ref(o)}) x{rng.randint(1, 3)}"
                                           for ph, o, _ in rels]})
                answer.append({"id": sid, "restrictions": [{"p": f"P:{gold[0]}", "o": ids[o]}
                                                           for _, o, gold in rels if gold]})
                acceptable.update({f"{sid}|{ids[o]}": [f"P:{k}" for k in gold] for _, o, gold in rels})
            out.append({**_example("restrict", f"restrict|{chunk[0][0]}", system, compact(rows), {"classes": answer},
                                   {"acceptable": acceptable, "source": "BFO/CCO/RO properties"}), "split": split})
    return out


def align_examples(terms: dict, rng: random.Random) -> list[dict]:
    pool = list(terms.values())
    token_index = defaultdict(set)
    for n, t in enumerate(pool):
        for w in re.findall(r"[a-z]{4,}", t["label"].lower()):
            token_index[w].add(n)

    def lookalikes(t, exclude, k):
        hits = set().union(*(token_index[w] for w in re.findall(r"[a-z]{4,}", t["label"].lower()))) or set()
        cands = [pool[i] for i in hits if pool[i]["source"] != t["source"] and pool[i]["iri"] not in exclude]
        cands.sort(key=lambda c: -SequenceMatcher(None, t["label"].lower(), c["label"].lower()).ratio())
        extra = [c for c in rng.sample(pool, 20) if c["source"] != t["source"] and c["iri"] not in exclude]
        return list({c["iri"]: c for c in cands[:k] + extra}.values())[:k]

    items = []
    for t in pool:
        if t["individual"]:
            continue
        gold = [(x, rel) for x, rel in t["mappings"] if x in terms and terms[x]["source"] != t["source"]]
        gold += [(p, "subclass") for p in t["parents"] if p in terms and terms[p]["source"] != t["source"]]
        gold = [(x, "exact" if terms[x]["individual"] and r == "equivalent" else
                 "close" if terms[x]["individual"] and r == "subclass" else r) for x, r in gold][:2]
        if gold or rng.random() < 0.15:
            items.append((t, gold))
    groups = defaultdict(list)
    for t, gold in items:
        branch = next((a for a in t["ancestors"] if a in upper.terms()["classes"]), "none")
        groups[f"{t['source']}|{branch}"].append((t, gold))
    out = []
    system, filter_system = load_prompt("interoperability"), load_prompt("interoperability_filter")
    for key, members in sorted(groups.items()):
        rng.shuffle(members)
        for chunk in _chunks(members, LORA["align_batch"]):
            rows, answer, keep = [], [], []
            for n, (t, gold) in enumerate(chunk, 1):
                gold_iris = {x for x, _ in gold}
                cands = [terms[x] for x in gold_iris] + lookalikes(t, gold_iris | {t["iri"]}, 5 - len(gold_iris))
                rng.shuffle(cands)
                cid = f"k{n}"
                parent = terms[t["parents"][0]]["label"] if t["parents"] and t["parents"][0] in terms else ""
                # 5th field as the pipeline shows it: "=" for a name match, else a similarity (here lexical, 0-1)
                match = lambda c: "=" if c["label"].lower() == t["label"].lower() else \
                    round(SequenceMatcher(None, t["label"].lower(), c["label"].lower()).ratio(), 2)
                rows.append({"id": cid, "label": t["label"], "parent": parent, "def": t["definition"][:160],
                             "candidates": [[i, c["label"], c["source"], c["definition"][:120], match(c)]
                                            for i, c in enumerate(cands, 1)]})
                kept = []
                for i, c in enumerate(cands, 1):
                    rel = next((r for x, r in gold if x == c["iri"]), None)
                    if rel:
                        answer.append({"id": cid, "candidate": i, "relation": rel})
                        kept.append(i)
                keep.append({"id": cid, "candidates": kept})
            meta = {"source": chunk[0][0]["source"]}
            out.append(_example("filter", key, filter_system, compact(rows), {"keep": keep}, meta))
            out.append(_example("align", key, system, compact(rows), {"mappings": answer}, meta))
    return out


def extract_examples(run_ids: list[str]) -> list[dict]:
    out, system = [], load_prompt("extraction")
    for run_id in run_ids:
        manifest = json.loads((OUTPUTS / run_id / "run.json").read_text(encoding="utf-8"))
        name = manifest.get("collection", {}).get("name")
        if name in LORA["exclude_collections"]:
            log(f"not distilling {run_id}: '{name}' is an evaluation collection")
            continue
        for path in sorted((OUTPUTS / run_id / "papers").glob("*.json")):
            p = json.loads(path.read_text(encoding="utf-8"))
            # one example per section call, exactly as the teacher model saw and answered it
            for n, call in enumerate(p.get("raw_calls", [])):
                if len(call["input"]) <= LORA["max_distill_chars"]:
                    prompt = load_prompt(call.get("prompt", "extraction"))
                    out.append(_example(f"extract:{call.get('pass', 'combined')}", f"paper|{p['key']}", prompt,
                                        call["input"], call["output"],
                                        {"source": f"run:{run_id}", "section": n,
                                         "teacher": manifest["config"].get("model_extraction")}))
    return out


def build(distill_runs: list[str] | None = None) -> dict:
    rng = random.Random(LORA["seed"])
    g, sources = load_suite()
    terms = collect_terms(g)
    log(f"{len(terms):,} labelled terms: {dict(Counter(t['source'] for t in terms.values()))}")
    examples = []
    for r in range(LORA["repeats"]):
        examples += hierarchy_examples(terms, rng, r) + enrich_examples(terms, rng, r)
        log(f"batching pass {r + 1}/{LORA['repeats']}: {len(examples):,} examples so far")
    examples += align_examples(terms, rng) + restrict_examples(rng)
    if distill_runs:
        examples += extract_examples(distill_runs)
    data = OUT / "data"
    data.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "test"):
        rows = [e for e in examples if e["split"] == split]
        rng.shuffle(rows)
        with (data / f"{split}.jsonl").open("w", encoding="utf-8") as f:
            f.writelines(json.dumps(e, ensure_ascii=False) + "\n" for e in rows)
    card = {"built": date.today().isoformat(), "config": LORA, "sources": sources, "distilled_runs": distill_runs or [],
            "counts": {f"{t}/{s}": n for (t, s), n in sorted(Counter((e["task"], e["split"]) for e in examples).items())},
            "by_source": dict(Counter(e["meta"].get("source", "") for e in examples)),
            "test_groups": sorted({e["group"] for e in examples if e["split"] == "test"})}
    (data / "dataset_card.json").write_text(json.dumps(card, indent=1), encoding="utf-8")
    bundle = OUT / "kw_lora_upload.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("train.jsonl", "val.jsonl", "test.jsonl", "dataset_card.json"):
            z.write(data / f, f"data/{f}")
        z.write(RESOURCES / "lora" / "finetune_colab.ipynb", "finetune_colab.ipynb")
    log(f"examples: {card['counts']}")
    log(f"upload bundle: {bundle}")
    return card
