"""One report with every figure, grouped by pipeline stage, each with a short paragraph computed from the numbers it
plots; plus the sweep summary (one row per run and per integration). Written by src.figures.build:

  report.md            figures linked as PNG files beside it
  report.html          self-contained (figures embedded), for sharing
  sweep_summary.csv    one row per run, then one per integration"""
import base64
import csv
import html
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from src import figures as F

GROUPS = [  # (title, what the group answers, [(figure, heading)])
    ("Corpus and extraction", "What the papers yielded: how much text was kept, what each paper gave, how well the "
     "extracted claims are backed by quotes, and how the knowledge grows as papers are added.",
     [("parsing", "Parsing and extraction effort"), ("per_paper_yield", "Yield per paper"),
      ("extraction_checks", "Extraction checks"), ("evidence_status", "Evidence behind extracted claims"),
      ("knowledge_growth", "Knowledge growth"), ("concept_growth", "Concept growth and saturation")]),
    ("Normalization", "How mentions in separate papers were joined into one vocabulary, and what that vocabulary "
     "contains.",
     [("normalization", "From occurrences to canonical concepts"), ("concept_support", "Support across papers"),
      ("concept_types", "Concept types"), ("causal_polarity", "Causal polarity"),
      ("relation_predicates", "Relation predicates")]),
    ("Ontology placement and structure", "Where each class was placed under CCO/BFO, how the model's answers were "
     "read, and the shape of the resulting hierarchy.",
     [("placement_sources", "Where parents came from"), ("parent_answers", "How parent answers were read"),
      ("bfo_categories", "BFO categories"), ("hierarchy_depth", "Hierarchy depth"),
      ("review_flags", "Review flags")]),
    ("Enrichment", "What the ontology states about each class beyond its parent: definitions and axioms, against "
     "everything the literature layer keeps.",
     [("definitions_status", "Definitions"), ("restriction_sources", "Restrictions"),
      ("layer_vs_ontology", "Literature layer against ontology")]),
    ("Interoperability", "How classes connect to external ontologies, and the MDS-Onto facets they carry.",
     [("external_mappings", "External mappings"), ("mapping_targets", "Mapping targets"),
      ("mapping_methods", "Mapping predicates and methods"), ("study_stages", "MDS-Onto study stages")]),
    ("Ontology store", "What every stage drew from the local ontology store (and the MDS-Onto and MatPortal "
     "portals): candidates, propagation through the store's own mappings, and the terms finally imported.",
     [("store_candidates", "Candidates by ontology"), ("store_sources", "Candidate sources and portal hits"),
      ("store_propagation", "Propagation through mappings"), ("store_imports", "Imported terms and labels")]),
    ("Model reliability and compute", "How often the local model answered every row it was sent, and what each "
     "stage cost.",
     [("row_coverage", "Row coverage per pass"), ("compute_by_stage", "Tokens and time per stage")]),
    ("Uncertain items", "Everything otherwise only counted, listed item by item in each run's "
     "ontology/uncertain.json for expert review.",
     [("uncertain_items", "Uncertain and dropped items")]),
    ("Scaling and cross-domain integration", "How results change with corpus size, and how the domain ontologies "
     "link to each other.",
     [("scaling_runs", "Runs of increasing size"), ("integration_series", "Integration as the corpus grows"),
      ("integration", "Latest integration")]),
]

READ = {  # how to read each figure (fixed); the numbers sentence follows
    "parsing": "Left, each dot is a paper: characters in the PDF against characters kept after references and running "
               "headers are removed (on the dashed line nothing was removed). Right, concepts extracted against the "
               "number of sections sent to the model.",
    "per_paper_yield": "Boxes show the spread over papers of concepts, relations, causal claims and reported values "
                       "extracted from each paper.",
    "extraction_checks": "Per-paper rates of the checks run during extraction: quotes re-asked and filled, concepts "
                         "first introduced by a later pass, and reported values without a property.",
    "evidence_status": "A claim is verified when its quote is found in the paper text, unverified when a quote was given "
                       "but not found, and unevidenced when no usable quote came back after one re-ask; unevidenced "
                       "claims never become axioms.",
    "knowledge_growth": "Cumulative distinct items as papers are added in citation order; a flattening line means new "
                        "papers mostly repeat what is already known.",
    "concept_growth": "Distinct canonical concepts as papers are added in citation order; the band is the 5-95% range "
                      "over random paper orders, so a line inside the band means the order of papers does not matter.",
    "normalization": "Left, the funnel from concept occurrences in single papers to lexical groups and canonical concepts. "
                     "Right, the decisions taken on the way: look-alike clusters found by embeddings, merges the model "
                     "accepted, type conflicts and causal contradictions.",
    "concept_support": "Share of canonical concepts found in one, two or more papers; concepts in several papers are "
                       "the better-supported core of the domain.",
    "concept_types": "Share of canonical concepts by the type assigned during extraction and normalization.",
    "causal_polarity": "Share of normalized causal claims by polarity (increases, decreases, and so on).",
    "relation_predicates": "Share of each domain's extracted relations by predicate.",
    "placement_sources": "Each class gets one parent. Model choice: the model picked a store candidate, corpus concept or "
                         "BFO root; paper is-a: the papers state the parent; lexical head: the class is nested under its "
                         "head noun; same-name: an MDS-Onto/PMDCO class of the same name; category root: the model's "
                         "answer could not be used, so the class sits directly under its BFO category.",
    "parent_answers": "How each parent answer of the local model was read: a candidate, corpus concept or BFO root "
                      "offered to it, a CCO/BFO class named exactly (inside the chosen category), or a close spelling "
                      "of an offered parent. Unresolved answers are kept in uncertain.json with the model's text.",
    "bfo_categories": "Share of the ontology's classes by top-level BFO category, from each class's ancestors.",
    "hierarchy_depth": "Left, levels from each class up to BFO entity; right, how many corpus classes sit above a class "
                       "(0: the class hangs directly from CCO/BFO).",
    "review_flags": "Share of classes flagged for expert review, by reason.",
    "definitions_status": "Definitions by status as a share of classes: supported by a paper definition, drafted from "
                          "evidence, generated by the model, imported from an exact or equivalent external match, or none.",
    "restriction_sources": "Restrictions by source: causal claims expressed with local, RO or CCO properties, and "
                           "relations formalized from the extracted predicate or chosen by the model.",
    "layer_vs_ontology": "Left, what the literature layer keeps (every claim the papers state); right, what the ontology "
                         "asserts as universal axioms. The gap is by design: only evidenced, general statements become "
                         "axioms.",
    "external_mappings": "Share of classes by their strongest external mapping; the empty remainder of each bar is "
                         "unmapped.",
    "mapping_targets": "External mappings by target ontology (counts).",
    "mapping_methods": "Left, mappings by the predicate written into the ontology; right, whether the model chose them or "
                       "they were added from same-name label matches, and how many were downgraded to a weaker relation.",
    "study_stages": "Classes by the first MDS-Onto study stage assigned.",
    "store_candidates": "Share of candidates by source ontology at each step that searches the store: parents for "
                        "placement (CCO first, then BFO), terms for mappings, and properties for restrictions.",
    "store_sources": "Left, where each mapping candidate was found (store search, a portal, or both; propagated: reached "
                     "through the store's own mappings). Right, portal search hits per class.",
    "store_propagation": "Candidates reached through one or two hops of the store's own mappings, and the mappings "
                         "committed directly or through a hop.",
    "store_imports": "Left, external terms declared in the ontology because a class maps or attaches to them; right, "
                     "class labels by origin (preferred label, paper synonyms, labels from external matches).",
    "row_coverage": "For each model pass, the share of rows answered on the first call, recovered by the retry in "
                    "smaller batches, and still missing (missing rows fall back to defaults and are listed in "
                    "uncertain.json).",
    "compute_by_stage": "Tokens and wall time per stage; extractions reused from the cache cost no tokens.",
    "uncertain_items": "Items each run lists in ontology/uncertain.json, by stage and kind (log scale above 10).",
    "scaling_runs": "Separate runs of increasing size per domain: canonical concepts, ontology classes and the share of "
                    "concepts found in two or more papers.",
    "integration_series": "The newest cross-domain integration at each corpus size: mappings and bridge concepts, and the "
                          "share of each domain's classes that map to another domain.",
    "integration": "The latest integration: mappings per domain pair, mappings by relation, and bridge concepts.",
}


# ---------------------------------------------------------------- number helpers

def n(x) -> str:
    x = F.num(x)
    return f"{x:,.0f}" if abs(x) >= 10 or x == int(x) else f"{x:.1f}"


def pc(a, b=1.0) -> str:
    b = F.num(b)
    return f"{F.num(a) / b:.0%}" if b else "n/a"


def L(d) -> str:
    return F.label(d)


def by_domain(t: list[dict]) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for r in t:
        if r.get("domain"):
            out[r["domain"]].append(r)
    return dict(out)


def counts(r: dict, skip=("domain", "run_id", "total", "classes", "papers", "concepts")) -> Counter:
    return Counter({k: F.num(v) for k, v in r.items() if k not in skip and isinstance(v, (int, float))})


def top(r: dict, k: int = 2, skip=("domain", "run_id", "total", "classes")) -> str:
    c = counts(r, skip)
    tot = sum(c.values())
    return ", ".join(f"{name.replace('_', ' ')} {pc(v, tot)}" for name, v in c.most_common(k) if v) or "none"


def each(t, fn) -> str:
    return "; ".join(fn(d, rs) for d, rs in by_domain(t).items()) + "."


# ---------------------------------------------------------------- one numbers sentence per figure

def _growth(t):
    c = "canonical_concepts_citation_order"

    def one(d, rs):
        last, prev = rs[-1], (rs[-2] if len(rs) > 1 else None)
        added = F.num(last[c]) - (F.num(prev[c]) if prev else 0)
        inside = F.num(last["random_order_p5"]) <= F.num(last[c]) <= F.num(last["random_order_p95"])
        return (f"{L(d)} reaches {n(last[c])} concepts after {n(last['papers'])} papers and the last paper still added "
                f"{n(added)} ({pc(added, last[c])}){'' if inside else ', outside the random-order band'}")
    return "Here " + each(t, one) + " A last paper that still adds a sizeable share means the domain vocabulary has " \
        "not saturated at this corpus size."


def _knowledge(t):
    last = {}
    for r in t:
        last[(r["domain"], r["panel"])] = r
    names = dict(F.KINDS)
    doms = list(dict.fromkeys(r["domain"] for r in t))
    parts = []
    for d in doms:
        ps = [f"{n(last[(d, k)]['cumulative'])} {names[k].lower()}" for k in names if (d, k) in last]
        papers = max(F.num(r["papers"]) for r in t if r["domain"] == d)
        parts.append(f"{L(d)} after {n(papers)} papers: {', '.join(ps)}")
    return "; ".join(parts) + "."


def _scaling(t):
    def one(d, rs):
        cc = sorted([r for r in rs if r["panel"] == "canonical_concepts"], key=lambda r: r["papers"])
        sh = sorted([r for r in rs if r["panel"].startswith("share")], key=lambda r: r["papers"])
        if len(cc) < 2:
            return f"{L(d)}: one size only"
        a, b = cc[0], cc[-1]
        per = (F.num(b["mean"]) - F.num(a["mean"])) / max(F.num(b["papers"]) - F.num(a["papers"]), 1)
        s = f"{L(d)} grows from {n(a['mean'])} to {n(b['mean'])} concepts between {n(a['papers'])} and " \
            f"{n(b['papers'])} papers (about {n(per)} per added paper)"
        return s + (f", with {pc(sh[-1]['mean'])} of concepts in two or more papers at the largest size" if sh else "")
    return "In this sweep " + each(t, one)


def _yield(t):
    from statistics import median

    def one(d, rs):
        con = [F.num(r["count"]) for r in rs if r["panel"] == "concepts"]
        rel = [F.num(r["count"]) for r in rs if r["panel"] == "relations"]
        return (f"{L(d)} gives a median of {n(median(con))} concepts (range {n(min(con))}-{n(max(con))}) and "
                f"{n(median(rel)) if rel else 0} relations per paper")
    return "Per paper, " + each(t, one) + " A wide range usually reflects paper length and how much of it is method " \
        "rather than results."


def _parsing(t):
    def one(d, rs):
        raw, kept = sum(F.num(r["chars_raw"]) for r in rs), sum(F.num(r["chars_kept"]) for r in rs)
        ch, co = sum(F.num(r["chunks"]) for r in rs), sum(F.num(r["concepts"]) for r in rs)
        return f"{L(d)} keeps {pc(kept, raw)} of {n(raw / 1e3)}k characters and yields {n(co / max(ch, 1))} concepts " \
               f"per section sent"
    return each(t, one)


def _checks(t):
    def one(r):
        c = counts(r)
        return f"{L(r['domain'])} " + ", ".join(f"{k.lower()} {n(v)}" for k, v in c.most_common(3))
    return "Per paper: " + "; ".join(one(r) for r in t) + ". Many concepts added by later passes, or many values " \
        "without a property, point to something the first extraction pass missed."


def _evidence(t):
    def one(d, rs):
        items = sum(F.num(r["items"]) for r in rs)
        worst = min(rs, key=lambda r: F.num(r["verified"]) / max(F.num(r["items"]), 1))
        return (f"{L(d)} has {pc(sum(F.num(r['verified']) for r in rs), items)} of {n(items)} claims verified and "
                f"{pc(sum(F.num(r['unevidenced']) for r in rs), items)} unevidenced (weakest: {worst['kind']}, "
                f"{pc(worst['verified'], worst['items'])} verified)")
    return each(t, one)


def _normalization(t):
    def one(r):
        return (f"{L(r['domain'])} joins {n(r['Occurrences'])} occurrences into {n(r['Canonical concepts'])} concepts "
                f"({n(F.num(r['Occurrences']) / max(F.num(r['Canonical concepts']), 1))} per concept); the model accepted "
                f"{n(r['Merges accepted'])} merges from {n(r['Look-alike clusters'])} look-alike clusters and settled "
                f"{n(r['Types settled'])} of {n(r['Type conflicts'])} type conflicts")
    return "; ".join(one(r) for r in t) + "."


def _support(t):
    def one(r):
        c = F.num(r["concepts"])
        three = sum(F.num(r.get(b, 0)) for b in ("3", "4", "5+"))
        return f"{L(r['domain'])}: {pc(r.get('1', 0), c)} of {n(c)} concepts appear in one paper only, {pc(three, c)} in three or more"
    return "; ".join(one(r) for r in t) + ". Single-paper concepts are expected to fall as the corpus grows."


def _shares(t, what="categories"):
    return "Largest " + what + ": " + "; ".join(f"{L(r['domain'])} {top(r, 2)}" for r in t) + "."


def _hierarchy(t):
    return "; ".join(f"{L(r['domain'])}: {n(r['classes'])} classes, mean {F.num(r['mean_depth_to_bfo']):.1f} levels to BFO "
                     f"(max {n(r['max_depth_to_bfo'])}), {pc(r['classes_with_local_parent'], r['classes'])} under another "
                     f"corpus class" for r in t) + ". A low share under corpus classes means a flat ontology hanging " \
        "directly from CCO/BFO."


def _placement(t):
    def one(r):
        tot = F.num(r["total"])
        return (f"{L(r['domain'])}: {pc(r.get('llm', 0), tot)} model choice, {pc(r.get('category_default', 0), tot)} "
                f"category root, {pc(r.get('type_default', 0), tot)} type default, "
                f"{pc(F.num(r.get('paper_is_a', 0)) + F.num(r.get('name_match', 0)) + F.num(r.get('lexical_head', 0)), tot)} "
                f"from the papers, a same name or the head noun")
    return "; ".join(one(r) for r in t) + ". Category-root classes are in the right BFO category but shallow; " \
        "the next figure and uncertain.json show why their answers could not be used."


def _parent_answers(t):
    def one(r):
        tot = F.num(r["total"])
        bad = F.num(r.get("unresolved", 0)) + F.num(r.get("no_answer", 0))
        return (f"{L(r['domain'])}: {pc(tot - bad, tot)} of {n(tot)} answers usable ({pc(r.get('candidate', 0), tot)} a "
                f"store candidate, {pc(r.get('root', 0), tot)} a bare BFO root), {pc(r.get('unresolved', 0), tot)} unresolved")
    unresolved = any(F.num(r.get("unresolved", 0)) for r in t)
    return "; ".join(one(r) for r in t) + "." + (" Unresolved answers are mostly labels the model wrote itself rather "
                                                 "than chose from what it was offered." if unresolved else "")


def _flags(t):
    return "Most common: " + "; ".join(f"{L(r['domain'])} " + ", ".join(
        f"{k} ({pc(v)} of classes)" for k, v in counts(r).most_common(2)) for r in t) + "."


def _coverage(t):
    tot = {r["pass"]: F.num(r["answered_first"]) + F.num(r["recovered"]) + F.num(r["missing"]) for r in t}
    allrows = sum(tot.values())
    worst = sorted(t, key=lambda r: -F.num(r["missing"]) / max(tot[r["pass"]], 1))[:3]
    return (f"Over all passes {pc(sum(F.num(r['recovered']) for r in t), allrows)} of {n(allrows)} rows needed the retry "
            f"and {pc(sum(F.num(r['missing']) for r in t), allrows)} were still missing. Most missing: "
            + ", ".join(f"{r['pass'].replace('_', ' ')} {pc(r['missing'], tot[r['pass']])}" for r in worst) + ".")


def _definitions(t):
    def one(r):
        tot = F.num(r["total"])
        have = sum(F.num(r.get(k, 0)) for k in ("supported", "draft_evidence", "model_generated", "imported"))
        return (f"{L(r['domain'])}: {pc(have, tot)} of classes have a definition ({pc(r.get('supported', 0), tot)} "
                f"supported by a paper, {pc(r.get('imported', 0), tot)} imported), {pc(r.get('none', 0), tot)} none")
    return "; ".join(one(r) for r in t) + "."


def _restrictions(t):
    def one(r):
        c = counts(r)
        tot = sum(c.values())
        causal = sum(v for k, v in c.items() if k.startswith("Causal"))
        return f"{L(r['domain'])}: {n(tot)} restrictions, {pc(causal, tot)} from causal claims"
    return "; ".join(one(r) for r in t) + "."


def _layer(t):
    def one(r):
        claims = F.num(r.get("Relation claims", 0)) + F.num(r.get("Causal claims", 0))
        axioms = F.num(r.get("Relation restrictions", 0)) + F.num(r.get("Causal restrictions", 0))
        return (f"{L(r['domain'])}: {n(claims)} relation and causal claims in the layer against {n(axioms)} restrictions "
                f"in the ontology ({pc(axioms, claims)}), plus {n(r.get('Reported values', 0))} reported values kept "
                f"only in the layer")
    return "; ".join(one(r) for r in t) + "."


def _mappings(t):
    def one(r):
        c = counts(r, ("domain", "run_id", "classes", "unmapped"))
        best = c.most_common(1)[0][0] if sum(c.values()) else "none"
        return f"{L(r['domain'])}: {pc(sum(c.values()), r['classes'])} of {n(r['classes'])} classes mapped (most often {best})"
    return "; ".join(one(r) for r in t) + "."


def _methods(t):
    def one(r):
        preds = Counter({k: F.num(v) for k, v in r.items() if ":" in k})
        tot = sum(preds.values())
        return (f"{L(r['domain'])}: {n(tot)} mappings, {pc(preds.get('skos:closeMatch', 0), tot)} close matches, "
                f"{n(r.get('method_label_match', 0))} added from label matches, {n(r.get('downgraded', 0))} downgraded")
    return "; ".join(one(r) for r in t) + ". Close matches dominate when the names differ, because exact and equivalent " \
        "need the labels (or a synonym) to match."


def _store_candidates(t):
    def one(r):
        c = counts(r, ("panel", "domain", "total"))
        tot = sum(c.values())
        if r["panel"].startswith("parent"):
            return f"{L(r['domain'])} parents {pc(c.get('CCO', 0), tot)} CCO / {pc(c.get('BFO', 0), tot)} BFO"
        return f"{L(r['domain'])} {r['panel'].split('_')[0]} {top(r, 2, ('panel', 'domain', 'total'))}"
    return "; ".join(one(r) for r in t) + "."


def _store_sources(t):
    def one(r):
        src = {k[7:]: F.num(v) for k, v in r.items() if k.startswith("source_")}
        tot = sum(src.values())
        portal = sum(v for k, v in src.items() if "portal" in k.lower() or "matportal" in k.lower())
        hits = {k[5:]: F.num(v) for k, v in r.items() if k.startswith("hits_")}
        return (f"{L(r['domain'])}: {pc(src.get('store', 0), tot)} of {n(tot)} candidates from the store alone, "
                f"{pc(portal, tot)} involving a portal; "
                + ", ".join(f"{k.replace('_', ' ')} {n(v / max(F.num(r['classes']), 1))} hits per class" for k, v in hits.items()))
    return "; ".join(one(r) for r in t) + ". Portal hits outside the store become facet hints only."


def _propagation(t):
    def one(r):
        ch = sum(F.num(v) for k, v in r.items() if k.startswith("candidates_hop_") and not k.endswith("_0"))
        mt = sum(F.num(v) for k, v in r.items() if k.startswith("mappings_hop_"))
        mh = sum(F.num(v) for k, v in r.items() if k.startswith("mappings_hop_") and not k.endswith("_0"))
        return f"{L(r['domain'])}: {n(ch)} candidates via hops, {n(mh)} of {n(mt)} mappings committed through one"
    return "; ".join(one(r) for r in t) + "."


def _imports(t):
    def one(r):
        imp = Counter({k[9:]: F.num(v) for k, v in r.items() if k.startswith("imported_")})
        paper = sum(F.num(v) for k, v in r.items() if k.startswith("labels_paper"))
        ext = sum(F.num(v) for k, v in r.items() if k.startswith("labels_external"))
        return (f"{L(r['domain'])}: {n(sum(imp.values()))} imported terms (most from "
                f"{imp.most_common(1)[0][0] if imp else 'none'}), {n(paper)} paper synonyms and {n(ext)} external labels")
    return "; ".join(one(r) for r in t) + "."


def _uncertain(t):
    def one(r):
        c = counts(r)
        return f"{L(r['domain'])}: {n(sum(c.values()))} items, most {', '.join(f'{k} ({n(v)})' for k, v in c.most_common(2))}"
    return "; ".join(one(r) for r in t) + ". Each item names the class, the model's answer or the term, and why it " \
        "was dropped or left uncertain."


def _compute(t):
    def one(r):
        tok = sum(F.num(v) for k, v in r.items() if k.endswith("_tokens"))
        wall = {k[:-7]: F.num(v) for k, v in r.items() if k.endswith("_wall_s")}
        big = max(wall, key=wall.get) if wall else "?"
        return (f"{L(r['domain'])} ({n(r.get('papers'))} papers): {n(tok / 1e3)}k tokens and {n(sum(wall.values()) / 60)} "
                f"minutes, {pc(wall.get(big, 0), sum(wall.values()))} of it in {big}")
    return "; ".join(one(r) for r in t) + "."


def _integration(t):
    pairs = [r for r in t if "a" in r]
    rels = [r for r in t if "relation" in r]
    if not pairs:
        return ""
    tot = sum(F.num(r["mappings"]) for r in pairs)
    best = max(pairs, key=lambda r: F.num(r["mappings"]))
    rel = max(rels, key=lambda r: F.num(r["count"])) if rels else None
    return (f"{n(tot)} mappings in {pairs[0]['integration']}; the most connected pair is {L(best['a'])}-{L(best['b'])} "
            f"({n(best['mappings'])})" + (f", and the most common relation is {rel['relation']} ({n(rel['count'])})" if rel else "")
            + ".")


def _integration_series(t):
    a, b = t[0], t[-1]
    return (f"From {n(a['papers_per_domain'])} to {n(b['papers_per_domain'])} papers per domain, mappings go from "
            f"{n(a['mappings'])} to {n(b['mappings'])} and bridge concepts from {n(a['bridge_concepts'])} to "
            f"{n(b['bridge_concepts'])}.")


NOTES = {"concept_growth": _growth, "knowledge_growth": _knowledge, "scaling_runs": _scaling,
         "per_paper_yield": _yield, "parsing": _parsing, "extraction_checks": _checks, "evidence_status": _evidence,
         "normalization": _normalization, "concept_support": _support,
         "concept_types": lambda t: _shares(t, "types"), "causal_polarity": lambda t: _shares(t, "polarities"),
         "relation_predicates": lambda t: _shares(t, "predicates"), "bfo_categories": lambda t: _shares(t, "categories"),
         "study_stages": lambda t: _shares(t, "stages"), "mapping_targets": lambda t: _shares(t, "targets"),
         "hierarchy_depth": _hierarchy, "placement_sources": _placement, "parent_answers": _parent_answers,
         "review_flags": _flags, "row_coverage": _coverage, "definitions_status": _definitions,
         "restriction_sources": _restrictions, "layer_vs_ontology": _layer, "external_mappings": _mappings,
         "mapping_methods": _methods, "store_candidates": _store_candidates, "store_sources": _store_sources,
         "store_propagation": _propagation, "store_imports": _imports, "uncertain_items": _uncertain,
         "compute_by_stage": _compute, "integration": _integration, "integration_series": _integration_series}


def paragraph(name: str, table: list[dict]) -> str:
    """How to read the figure, then what its numbers say. A numbers sentence that fails is left out."""
    try:
        numbers = NOTES[name](table) if name in NOTES and table else ""
    except Exception as e:  # noqa: BLE001 - a missing column must not cost the report
        numbers = ""
        print(f"  note for {name} skipped ({type(e).__name__}: {e})")
    return " ".join(x for x in (READ.get(name, ""), numbers) if x)


# ---------------------------------------------------------------- sweep summary

RUN_COLS = [("collection", "Domain"), ("papers_processed", "Papers"), ("stages", "Stages"), ("canonical_concepts", "Concepts"),
            ("final_classes", "Classes"), ("placement_llm", "Placed by model"), ("placement_category_default", "Category root"),
            ("mappings_total", "Mappings"), ("restrictions", "Restrictions"), ("validation_valid", "Valid"),
            ("uncertain_total", "Uncertain items"), ("total_tokens", "Tokens"), ("total_wall_s", "Wall (min)"),
            ("run_id", "Run")]
INT_COLS = [("domains", "Domains"), ("papers_per_domain", "Papers/domain"), ("classes_total", "Classes"),
            ("mappings_total", "Mappings"), ("bridge_concepts", "Bridge concepts"), ("validation_valid", "Valid"),
            ("run_id", "Integration")]


def sweep(rows: list[dict], outputs: Path, revision: str, run_ids) -> tuple[list[dict], list[dict]]:
    runs = []
    for r in sorted(rows, key=lambda r: (F.num(r.get("papers_processed")), list(F.DOMAINS).index(r["collection"])
                                         if r.get("collection") in F.DOMAINS else 99, r.get("created", ""))):
        row = {k: r.get(k, "") for k, _ in RUN_COLS}
        row["stages"] = f"{len([x for x in (r.get('stages_completed') or '').split('+') if x])}/5"
        mt = sum(F.num(v) for k, v in r.items() if k.startswith("mappings_predicate_"))
        row["mappings_total"] = int(mt) if mt else r.get("mappings_total", "")
        row["restrictions"] = int(sum(F.num(r.get(f"axioms_restriction_{k}")) for k in ("causal", "relation"))) or ""
        row["total_wall_s"] = round(F.num(r.get("total_wall_s")) / 60, 1) if r.get("total_wall_s") else ""
        runs.append(row)
    papers = {r["run_id"]: F.num(r.get("papers_processed")) for r in F._csv(outputs / "eval_runs.csv")
              if r.get("row_type") == "run"}
    ints = [r for r in F._csv(outputs / "eval_integrations.csv") if r.get("row_type") == "integration"]
    ints = [r for r in ints if (set(filter(None, r.get("input_runs", "").split("+"))) <= set(run_ids) if run_ids
                                else r.get("workflow_revision") == revision)]
    out_ints = []
    for r in sorted(ints, key=lambda r: r.get("created", "")):
        per = sorted({int(papers.get(k, 0)) for k in r.get("input_runs", "").split("+") if k})
        out_ints.append({**{k: r.get(k, "") for k, _ in INT_COLS},
                         "papers_per_domain": "/".join(map(str, per)), "domains": r.get("domains", "").replace("+", ", ")})
    return runs, out_ints


def _write_csv(path: Path, runs, ints):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row_type"] + [k for k, _ in RUN_COLS])
        w.writerows([["run"] + [r[k] for k, _ in RUN_COLS] for r in runs])
        if ints:
            w.writerow([])
            w.writerow(["row_type"] + [k for k, _ in INT_COLS])
            w.writerows([["integration"] + [r[k] for k, _ in INT_COLS] for r in ints])


def _cell(k, v):
    if k == "collection":
        return L(v)
    if k in ("total_tokens",) and v not in ("", None):
        return f"{F.num(v) / 1e3:,.0f}k"
    return str(v) if v not in (None, "") else "-"


# ---------------------------------------------------------------- writers

def sections(out) -> list[tuple[str, str, list[tuple[str, str, str, str, str]]]]:
    """Groups with the figures that exist: (group, intro, [(name, heading, title, source, paragraph)])."""
    made = {name: (title, source) for name, title, source in out.index}
    placed, result = set(), []
    for group, intro, figs in GROUPS:
        items = [(nm, h, *made[nm], paragraph(nm, out.tables.get(nm, []))) for nm, h in figs if nm in made]
        placed |= {nm for nm, _ in figs}
        if items:
            result.append((group, intro, items))
    rest = [(nm, nm.replace("_", " ").capitalize(), t, s, paragraph(nm, out.tables.get(nm, [])))
            for nm, (t, s) in made.items() if nm not in placed]
    if rest:
        result.append(("Other figures", "", rest))
    return result


def write(out, rows: list[dict], outputs: Path, revision: str, run_ids, notes: list[str], title: str | None = None):
    runs, ints = sweep(rows, outputs, revision, run_ids)
    _write_csv(out.folder / "sweep_summary.csv", runs, ints)
    secs = sections(out)
    title = title or f"Pipeline report: revision {revision}"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    domains = ", ".join(dict.fromkeys(L(r.get("collection")) for r in rows)) or "none"
    lead = (f"{len(rows)} run(s) ({domains}) and {len(ints)} integration(s). Generated {stamp}. Each figure is also in "
            "this folder as PDF (for LaTeX), PNG and CSV (the plotted numbers).")

    md = [f"# {title}", "", lead, *[f"\n> Note: {x}" for x in notes], "", "## Contents", ""]
    md += [f"{i}. [{g}](#{g.lower().replace(' ', '-')})" for i, (g, _, _) in enumerate(secs, 1)]
    md += ["", "## Sweep summary", "", "| " + " | ".join(h for _, h in RUN_COLS) + " |",
           "|" + "---|" * len(RUN_COLS)]
    md += ["| " + " | ".join(_cell(k, r[k]) for k, _ in RUN_COLS) + " |" for r in runs]
    if ints:
        md += ["", "| " + " | ".join(h for _, h in INT_COLS) + " |", "|" + "---|" * len(INT_COLS)]
        md += ["| " + " | ".join(_cell(k, r[k]) for k, _ in INT_COLS) + " |" for r in ints]
    for g, intro, items in secs:
        md += ["", f"## {g}", "", intro]
        for nm, h, t, s, para in items:
            md += ["", f"### {h}", "", f"![{t}]({nm}.png)", "", f"*{t}.*", "", para, "",
                   f"<sub>Data: {s}. Files: `{nm}.pdf`, `{nm}.png`, `{nm}.csv`.</sub>"]
    if out.skipped:
        md += ["", "## Figures not drawn", "", *[f"- `{nm}`: {why}" for nm, why in out.skipped]]
    (out.folder / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    e = html.escape
    img = lambda nm: base64.b64encode((out.folder / f"{nm}.png").read_bytes()).decode()
    table = lambda cols, data: ("<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for _, h in cols) + "</tr></thead><tbody>"
                                + "".join("<tr>" + "".join(f"<td>{e(_cell(k, r[k]))}</td>" for k, _ in cols) + "</tr>"
                                          for r in data) + "</tbody></table>")
    body = [f"<h1>{e(title)}</h1>", f"<p class=lead>{e(lead)}</p>", *[f"<p class=note>Note: {e(x)}</p>" for x in notes],
            "<nav><b>Contents</b><ol>" + "".join(f"<li><a href='#g{i}'>{e(g)}</a></li>" for i, (g, _, _) in enumerate(secs, 1))
            + "</ol></nav>", "<h2>Sweep summary</h2>", "<div class=scroll>" + table(RUN_COLS, runs) + "</div>"]
    if ints:
        body.append("<div class=scroll>" + table(INT_COLS, ints) + "</div>")
    for i, (g, intro, items) in enumerate(secs, 1):
        body += [f"<section id='g{i}'><h2>{i}. {e(g)}</h2>", f"<p class=intro>{e(intro)}</p>"]
        for nm, h, t, s, para in items:
            body.append(f"<figure><h3>{e(h)}</h3><img alt='{e(t)}' src='data:image/png;base64,{img(nm)}'>"
                        f"<figcaption>{e(t)}.</figcaption><p>{e(para)}</p><p class=src>Data: {e(s)}. Files: {nm}.pdf, "
                        f"{nm}.png, {nm}.csv.</p></figure>")
        body.append("</section>")
    if out.skipped:
        body += ["<h2>Figures not drawn</h2><ul>"] + [f"<li><code>{e(nm)}</code>: {e(w)}</li>" for nm, w in out.skipped] + ["</ul>"]
    css = ("body{font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif;color:#1b1b19;background:#fff;max-width:980px;"
           "margin:0 auto;padding:24px 16px}h1{font-size:26px}h2{margin-top:44px;border-bottom:1px solid #e6e5e0;padding-bottom:6px}"
           "h3{margin:0 0 8px;font-size:17px}figure{margin:26px 0;padding:0}img{max-width:100%;height:auto;border:1px solid #eee}"
           "figcaption{font-style:italic;color:#52514e;margin:6px 0}.src{font-size:12px;color:#77756f}.lead,.intro{color:#3a3936}"
           ".note{background:#fff7e0;padding:6px 10px}.scroll{overflow-x:auto}table{border-collapse:collapse;font-size:13px;"
           "margin:10px 0}th,td{border-bottom:1px solid #e6e5e0;padding:4px 8px;text-align:left;white-space:nowrap}"
           "nav{background:#f6f6f3;padding:10px 16px;border-radius:6px}"
           "@media (prefers-color-scheme: dark){body{background:#161615;color:#e8e6e1}img{background:#fff}"
           "nav{background:#232321}.note{background:#3a3220}th,td{border-color:#333}}")
    page = (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,"
            f"initial-scale=1'><title>{e(title)}</title><style>{css}</style></head><body>{''.join(body)}</body></html>")
    (out.folder / "report.html").write_text(page, encoding="utf-8")
    print(f"  report.md, report.html, sweep_summary.csv ({sum(len(x[2]) for x in secs)} figures in {len(secs)} groups)")
