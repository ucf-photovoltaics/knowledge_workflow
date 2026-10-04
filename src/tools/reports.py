"""Run reports: per-paper compute CSV, corpus report, ontology report (Markdown + JSON stats)."""
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import median

from src.agents.normalization import TIERS, WEIGHTS

TOKENS = ("calls", "input_tokens", "cached_tokens", "output_tokens", "latency_s")


def _table(headers: list, rows: list) -> str:
    lines = ["| " + " | ".join(map(str, headers)) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(x).replace("|", "/").replace("\n", " ") for x in r) + " |" for r in rows]
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict]):
    if rows:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def paper_compute(papers: list[dict], ledger_by_item: dict) -> list[dict]:
    """Compute per paper. `extraction_*` = what extracting the paper cost (kept across cache reuse);
    `run_*` = what this run actually spent on it (0 on a cache hit)."""
    rows = []
    for p in papers:
        ps, c, run = p["parse_stats"], p.get("compute", {}), ledger_by_item.get(p["key"], {})
        rows.append({
            "key": p["key"], "title": p["title"][:120], "year": p.get("year", ""), "doi": p.get("doi", ""),
            "citations": p.get("citations"), "pages": ps["pages"], "chars_raw": ps["chars_raw"], "chars_kept": ps["chars_kept"],
            "text_reduction": ps["reduction"], "parse_s": ps["parse_s"], "chunks": p.get("n_chunks", 0),
            "model": c.get("model", ""), "cache_hit": p.get("cache_hit", False),
            **{f"extraction_{k}": c.get(k, 0) for k in TOKENS},
            "extraction_total_tokens": c.get("input_tokens", 0) + c.get("output_tokens", 0),
            "run_input_tokens": run.get("input_tokens", 0), "run_output_tokens": run.get("output_tokens", 0),
            "run_cost_usd": run.get("cost_usd", 0),
            "concepts": len(p["concepts"]), "relations": len(p["relations"]), "causal": len(p["causal"]),
            "figures": len(p["figures"]), "figures_linked": sum(1 for f in p["figures"] if f["concepts"]),
        })
    return rows


def corpus_report(path: Path, run_id: str, norm: dict, papers: list[dict]) -> dict:
    concepts, causal, order, st = norm["concepts"], norm["causal"], norm["causal_order"], norm["stats"]
    label = {c["id"]: c["label"] for c in concepts}
    n_figs = sum(len(p["figures"]) for p in papers)
    stats = {
        "papers": len(papers), "concept_occurrences": st["concept_occurrences"],
        "mean_concepts_per_paper": round(st["concept_occurrences"] / max(len(papers), 1), 1),
        "lexical_groups": st["lexical_groups"], "candidate_clusters": st.get("candidate_clusters", 0),
        "semantic_merges": st.get("semantic_merges", 0), "canonical_concepts": len(concepts),
        "embedding_error": st.get("embedding_error"),
        "concepts_in_2plus_papers": sum(1 for c in concepts if c["n_papers"] > 1),
        "relations": len(norm["relations"]), "causal_edges": len(causal),
        "reported_values": len(norm.get("measurements", [])),
        "type_conflicts": st.get("type_conflicts", 0), "types_settled_by_model": st.get("types_settled_by_model", 0),
        "causal_contradictions": st.get("causal_contradictions", 0), "row_coverage": st.get("row_coverage", {}),
        "measurements_property_missing": sum(1 for m in norm.get("measurements", []) if m.get("property_missing")),
        "measurements_with_entity": sum(1 for m in norm.get("measurements", []) if m.get("entity")),
        "tiers": dict(Counter(c["tier"] for c in concepts)), "types": dict(Counter(c["type"] for c in concepts).most_common()),
        "figures": n_figs, "figures_linked": sum(1 for p in papers for f in p["figures"] if f["concepts"]),
        "concepts_with_figures": sum(1 for c in concepts if c["figures"]),
        "causal_graph": {k: order[k] for k in ("n_nodes", "n_edges", "max_rank")} | {"cycles": len(order["cycles"])},
    }
    s = norm["summary"]
    md = [f"# Corpus Report - run {run_id}", "", "## Summary", "", s.get("summary", ""), "", "## Themes", ""]
    md += [f"- **{t.get('theme', '')}**: {', '.join(t.get('concepts', []))}" for t in s.get("themes", [])]
    md += ["", "## Corpus statistics", "", _table(["metric", "value"], [
        ["papers", stats["papers"]], ["concept occurrences (per-paper)", stats["concept_occurrences"]],
        ["mean concepts per paper", stats["mean_concepts_per_paper"]], ["lexical groups", stats["lexical_groups"]],
        ["embedding candidate clusters", stats["candidate_clusters"]], ["semantic merges", stats["semantic_merges"]],
        ["canonical concepts", stats["canonical_concepts"]], ["concepts in 2+ papers", stats["concepts_in_2plus_papers"]],
        ["distinct relations", stats["relations"]], ["distinct causal edges", stats["causal_edges"]],
        ["figures (captions)", stats["figures"]], ["figures linked to concepts", stats["figures_linked"]]])]
    md += ["", "## Concept importance (top 50)", "", _table(
        ["rank", "concept", "tier", "type", "papers", "mentions", "causal in/out", "figures", "score"],
        [[c["rank"], c["label"], c["tier"], c["type"], c["n_papers"], c["mentions"],
          f"{c['causal_in']}/{c['causal_out']}", len(c["figures"]), c["score"]] for c in concepts[:50]])]
    md += ["", "Tiers: " + ", ".join(f"{t} {stats['tiers'].get(t, 0)}" for _, t in TIERS),
           "", "Types: " + ", ".join(f"{k or 'unset'} {v}" for k, v in stats["types"].items())]
    md += ["", "## Causal structure", "",
           f"{order['n_nodes']} concepts, {order['n_edges']} cause->effect pairs, deepest causal rank {order['max_rank']}, "
           f"{len(order['cycles'])} feedback cycles.", "", "Longest causal chains:", ""]
    md += [f"{i}. " + " -> ".join(ch) for i, ch in enumerate(order["chains"], 1)]
    if order["cycles"]:
        md += ["", "Cycles (mutual causation reported across papers):", ""] + [f"- {' <-> '.join(c)}" for c in order["cycles"]]
    md += ["", "## Best-supported causal claims", "", _table(
        ["cause", "polarity", "effect", "papers", "evidence"],
        [[label[r["cause"]], r["polarity"], label[r["effect"]], r["support"], (r["evidence"] or [{"text": ""}])[0]["text"]]
         for r in causal[:25]])]
    if norm.get("contradictions"):
        md += ["", "## Contradicting causal claims", "",
               "Same cause and effect reported with opposite polarity; conditions often explain the difference.", ""]
        md += [f"- {label[c['cause']]} -> {label[c['effect']]}: " + "; ".join(
            f"{x['polarity']} ({len(x['papers'])} paper(s){', ' + '; '.join(x['conditions']) if x['conditions'] else ''})"
            for x in c["claims"]) for c in norm["contradictions"]]
    md += ["", "## Figures", "", _table(["concept", "figures"],
           [[c["label"], len(c["figures"])] for c in sorted(concepts, key=lambda c: -len(c["figures"]))[:15] if c["figures"]])]
    md += ["", "## Scoring method", "",
           "score = " + " + ".join(f"{w} x {k}" for k, w in WEIGHTS.items()) + ", each component scaled to [0, 1] by its "
           "corpus maximum. papers = number of papers; mentions = log(1 + mentions); centrality = PageRank over "
           "relation and causal edges; causal = causal in-degree + out-degree; figures = figure links. Tiers by rank: "
           "core = top 10%, major = next 20%, minor = rest. Causal rank = longest cause->effect path depth after "
           "collapsing cycles."]
    path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return stats


def ontology_report(path: Path, run_id: str, m: dict, v: dict, classes: list[dict], by_agent: dict, manifest: dict):
    ax, h, cov = m["axioms"], m["hierarchy"], m["coverage"]
    md = [f"# Ontology Report - run {run_id}", "", "## Headline", "", _table(["metric", "value"], [
        ["classes (local)", m["classes"]],
        ["imported classes (BFO / CCO / external)", f"{m['imported_classes']['BFO']} / {m['imported_classes']['CCO']} / {m['imported_classes']['external']}"],
        ["object properties by source", ", ".join(f"{k} {n}" for k, n in m["object_properties"].items())],
        ["causal restrictions by source", ", ".join(f"{k} {n}" for k, n in m["causal_restrictions_by_source"].items())],
        ["logical axioms", sum(ax[k] for k in ("subclass_named", "subclass_restriction", "equivalent_class", "disjoint_with", "domain", "range", "subproperty"))],
        ["annotation assertions", m["annotation_assertions"]], ["triples", m["triples"]],
        ["structural validation", "pass" if v["valid"] else f"{v['n_issues']} issues"]])]
    flags = Counter(f for c in classes if not c.get("excluded") for f in set(c.get("review_flags", [])))
    md += ["", "## Workflow revision and review", "", manifest.get("config", {}).get("workflow_revision", "legacy"),
           "", _table(["review flag", "classes"], sorted(flags.items())),
           "", "Review details: ontology/review_issues.json. Cross-domain candidates: ontology/cross_domain_candidates.json."]
    md += ["", "## Upper-level placement (BFO category)", "", _table(["category", "classes"], list(m["bfo_categories"].items()))]
    md += ["", "## Hierarchy", "", _table(["metric", "value"], [
        ["max depth to BFO entity", h["max_depth_to_bfo_entity"]], ["mean depth to BFO entity", h["mean_depth_to_bfo_entity"]],
        ["max local depth", h["max_local_depth"]], ["local roots (parent is BFO/CCO)", h["local_roots"]],
        ["leaves", h["leaves"]], ["placement source", ", ".join(f"{k} {n}" for k, n in h["placement"].items())]])]
    md += ["", "## Axioms", "", _table(["type", "count"], list(ax.items()))]
    md += ["", "## Coverage", "", _table(["annotation", "share of classes"], list(cov.items()))]
    md += ["", "## Interoperability", "", _table(["relation", "mappings"], list(m["mappings"]["by_relation"].items())),
           "", _table(["ontology", "mappings"], list(m["mappings"]["by_ontology"].items())),
           "", f"Classes with portal candidates: {m['mappings']['classes_with_candidates']}. "
               f"Local causal properties used: {m['local_properties_used']}."]
    md += ["", "## Validation (structural, no reasoner)", "", f"JSON-LD round trip: {'ok' if v['jsonld_roundtrip'] else 'FAILED'}. "
           f"Issues: {v['n_issues']}.", ""] + [f"- {i}" for i in v["issues"][:50]]
    excluded = [c["label"] for c in classes if c["excluded"]]
    md += ["", f"## Excluded concepts ({len(excluded)})", "", ", ".join(excluded) or "none"]
    md += ["", "## Compute by agent", "", _table(
        ["agent", "calls", "input tokens", "cached", "output tokens", "latency s", "cost USD"],
        [[a, s["calls"], s["input_tokens"], s["cached_tokens"], s["output_tokens"], s["latency_s"], s["cost_usd"]]
         for a, s in by_agent.items()])]
    md += ["", "## Reproducibility", "", _table(["field", "value"], [
        ["run id", run_id], ["git commit", manifest.get("git_commit")], ["corpus hash", manifest.get("corpus", {}).get("hash")],
        *[[k, val] for k, val in manifest.get("config", {}).items()]])]
    path.write_text("\n".join(md) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Cross-run evaluation table: one row per run in outputs/eval_runs.csv, rebuilt after every stage.
# ---------------------------------------------------------------------------
STAGE_AGENT = {"extract": "extraction", "normalize": "normalization", "ontology": "ontology",
               "enrich": "enrichment", "interop": "interoperability"}
AGENT_FIELDS = ("calls", "cache_hits", "input_tokens", "cached_tokens", "output_tokens", "latency_s", "cost_usd")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _flat(prefix: str, d: dict) -> dict:
    return {f"{prefix}_{str(k).replace(' ', '_')}": v for k, v in (d or {}).items()}


def _coverage(*sources) -> dict:
    """Row coverage per model pass (sent, recovered by the retry, still missing) as flat columns."""
    out = {}
    for src in sources:
        for name, s in (src or {}).items():
            out.update({f"{name}_rows": s.get("rows"), f"{name}_rows_recovered": s.get("recovered"),
                        f"{name}_rows_missing_after_retry": s.get("missing")})
    return out


def _unevidenced(papers: list[dict], kind: str):
    items = sum(p.get("verification", {}).get(kind, {}).get("items", 0) for p in papers)
    n = sum(p.get("verification", {}).get(kind, {}).get("unevidenced", 0) for p in papers)
    return round(n / items, 3) if items and any("unevidenced" in p.get("verification", {}).get(kind, {}) for p in papers) else None


def _share(papers: list[dict], kind: str):
    """Share of a paper set's extracted items whose evidence quote was found in the paper text."""
    items = sum(p.get("verification", {}).get(kind, {}).get("items", 0) for p in papers)
    return sum(p.get("verification", {}).get(kind, {}).get("verified", 0) for p in papers) / items if items else None


def eval_row(run_dir: Path, m: dict) -> dict:
    """Everything worth comparing across runs, as one flat row. Missing stages leave blanks."""
    cfg, coll, corpus, stages = m.get("config", {}), m.get("collection", {}), m.get("corpus", {}), m.get("stages", {})
    sel, by_agent = corpus.get("selection", {}), m.get("compute", {}).get("by_agent", {})
    papers = [_load(p) for p in sorted((run_dir / "papers").glob("*.json"))]
    cs = _load(run_dir / "normalized" / "corpus_stats.json")
    concepts = _load(run_dir / "normalized" / "concepts.json") or []
    om, val = _load(run_dir / "ontology" / "metrics.json"), _load(run_dir / "ontology" / "validation.json")
    layer = _load(run_dir / "ontology" / "domain_layer_metrics.json")
    ex, on, en = stages.get("extract", {}), stages.get("ontology", {}), stages.get("enrich", {})
    ps = [p["parse_stats"] for p in papers]
    cites = sorted(s["citations"] for s in sel.get("selected", []) if s.get("citations") is not None)
    occ = sum(len(p["concepts"]) for p in papers)
    canonical = cs.get("canonical_concepts")
    raw, kept = sum(x["chars_raw"] for x in ps), sum(x["chars_kept"] for x in ps)
    checks = Counter()
    for p in papers:
        for k, v in p.get("checks", {}).items():
            for kk, vv in (v.items() if isinstance(v, dict) else [("", v)]):
                checks[f"{k}_{kk}".rstrip("_")] += vv
    extraction_original = sum(p.get("compute", {}).get("input_tokens", 0) + p.get("compute", {}).get("output_tokens", 0)
                              for p in papers)

    row = {
        # run identity and settings
        "run_id": m.get("run_id"), "collection": coll.get("name"), "library_id": coll.get("library_id"),
        "collection_key": coll.get("collection_key"), "created": m.get("created"),
        "stages_completed": "+".join(s for s in STAGE_AGENT if s in stages),
        "last_completed": max((s["completed"] for s in stages.values()), default=""),
        "git_commit": m.get("git_commit"),
        "row_type": "run", "workflow_revision": cfg.get("workflow_revision", ""),
        "ontology_unresolved_placements": on.get("unresolved_placements"),
        "ontology_category_conflicts": on.get("category_conflicts"),
        "enrichment_unsupported_definitions": en.get("unsupported_definitions"),
        "enrichment_definition_category_conflicts": en.get("definition_category_conflicts"),
        **{k: cfg.get(k) for k in ("llm_profile", "llm_provider", "model_extraction", "model_normalization",
                                   "model_ontology", "model_enrichment", "model_interoperability", "embed_model",
                                   "temperature", "max_input_chars", "max_output_tokens", "mds_ontologies")},
        # corpus selection
        "top_n_by_citations": sel.get("top_n"), "items_in_collection": sel.get("items_in_collection"),
        "items_without_doi": sel.get("items_without_doi"), "items_without_citation_count": sel.get("items_without_count"),
        "papers_selected": len(sel.get("selected", [])), "papers_passed_over_no_pdf": len(sel.get("skipped_no_pdf", [])),
        "papers_processed": corpus.get("processed"), "papers_failed": len(corpus.get("failed", [])),
        "citations_min": cites[0] if cites else None, "citations_median": median(cites) if cites else None,
        "citations_max": cites[-1] if cites else None, **_flat("citation_source", sel.get("citation_sources")),
        **_flat("pdf_source", corpus.get("pdf_sources")),
        "pages": sum(x["pages"] for x in ps), "chars_raw": raw, "chars_kept": kept,
        "text_reduction": round(1 - kept / raw, 3) if raw else None,
        "extraction_chunks": sum(p.get("n_chunks", 0) for p in papers), "corpus_hash": corpus.get("hash"),
        # concepts tracked (per paper, before normalization)
        "concept_occurrences": occ, "concepts_per_paper_mean": round(occ / len(papers), 1) if papers else None,
        "concept_mentions": sum(c.get("mentions", 0) for p in papers for c in p["concepts"]),
        "relations_extracted": sum(len(p["relations"]) for p in papers),
        "causal_extracted": sum(len(p["causal"]) for p in papers),
        "measurements_extracted": sum(len(p.get("measurements", [])) for p in papers),
        "pipeline_tier": cfg.get("pipeline_tier") or cfg.get("extraction_tier"),
        **{f"{k}_evidence_verified_share": round(v, 3) if (v := _share(papers, k)) is not None else None
           for k in ("relations", "causal", "measurements")},
        **{f"{k}_unevidenced_share": _unevidenced(papers, k) for k in ("relations", "causal", "measurements")},
        "measurements_property_missing": cs.get("measurements_property_missing"),
        "measurements_with_entity": cs.get("measurements_with_entity"),
        "extraction_calls_per_paper": round(sum(len(p.get("raw_calls", [])) for p in papers) / len(papers), 1)
        if papers else None,
        "figures": sum(len(p["figures"]) for p in papers),
        "figures_linked": sum(1 for p in papers for f in p["figures"] if f.get("concepts")),
        # normalized and joined across papers
        "lexical_groups": cs.get("lexical_groups"), "embedding_candidate_clusters": cs.get("candidate_clusters"),
        **_flat("extraction_check", checks),
        "semantic_merges": cs.get("semantic_merges"), "canonical_concepts": canonical,
        "type_conflicts": cs.get("type_conflicts"), "types_settled_by_model": cs.get("types_settled_by_model"),
        "causal_contradictions": cs.get("causal_contradictions"),
        "embedding_error": cs.get("embedding_error"),
        "compression_ratio": round(occ / canonical, 2) if canonical else None,
        "concepts_in_2plus_papers": cs.get("concepts_in_2plus_papers"),
        "share_concepts_2plus_papers": round(cs["concepts_in_2plus_papers"] / canonical, 3) if canonical else None,
        "distinct_relations": cs.get("relations"), "distinct_causal_edges": cs.get("causal_edges"),
        "concepts_with_figures": cs.get("concepts_with_figures"),
        **_flat("causal_graph", cs.get("causal_graph")), **_flat("tier", cs.get("tiers")), **_flat("type", cs.get("types")),
        # final ontology
        "final_classes": om.get("classes"), "concepts_excluded": on.get("excluded"),
        "classes_with_local_parent": on.get("local_parent"), **_flat("placement", on.get("placement")),
        **_flat("bfo_category_pass", on.get("categories")),
        **{f"ontology_{k}": on.get(k) for k in ("category_override", "category_mismatch", "category_default")},
        **_flat("ontology_failed", on.get("failed_calls")), **_flat("enrichment_failed", en.get("failed_calls")),
        **_flat("interop_check", {k: v for k, v in (stages.get("interop", {}).get("checks") or {}).items()
                                  if k != "row_coverage"}),
        **_coverage(cs.get("row_coverage"), on.get("row_coverage"), en.get("row_coverage"),
                    (stages.get("interop", {}).get("checks") or {}).get("row_coverage")),
        **_flat("definitions", en.get("definitions_by_status")),
        "restrictions_from_predicate": en.get("restrictions_from_predicate"),
        **_flat("imported_classes", om.get("imported_classes")), **_flat("object_properties", om.get("object_properties")),
        **_flat("axioms", om.get("axioms")), **_flat("causal_restrictions", om.get("causal_restrictions_by_source")),
        **_flat("restrictions_dropped", en.get("restrictions_dropped")),
        "definitions_llm": en.get("definitions_llm"), "disjoint_pairs": en.get("disjoint_pairs"),
        **_flat("hierarchy", {k: v for k, v in om.get("hierarchy", {}).items() if k != "placement"}),
        **_flat("bfo", om.get("bfo_categories")), **_flat("coverage", om.get("coverage")),
        **_flat("study_stage", om.get("facets", {}).get("study_stage")),
        **_flat("mds_domain", om.get("facets", {}).get("domain")),
        "facets_with_subdomain": om.get("facets", {}).get("with_subdomain"),
        **_flat("facets_source", om.get("facets", {}).get("source")),
        **_flat("mappings", om.get("mappings", {}).get("by_relation")),
        **_flat("mappings_to", om.get("mappings", {}).get("by_ontology")),
        "classes_with_portal_candidates": om.get("mappings", {}).get("classes_with_candidates"),
        **_flat("mappings", {k: v for k, v in om.get("mappings", {}).items()
                             if k not in ("by_relation", "by_ontology", "classes_with_candidates")}),
        "triples": om.get("triples"), "annotation_assertions": om.get("annotation_assertions"),
        "validation_valid": val.get("valid"), "validation_issues": val.get("n_issues"),
        # bottom-up literature layer
        **_flat("domain_layer", {k: v for k, v in layer.items() if k != "predicates"}),
    }
    # compute and time per agent
    for stage, agent in STAGE_AGENT.items():
        a = by_agent.get(agent, {})
        row.update({f"{agent}_{f}": a.get(f) for f in AGENT_FIELDS})
        row[f"{agent}_wall_s"] = stages.get(stage, {}).get("wall_s")
    tot = {f: round(sum((by_agent.get(a, {}).get(f) or 0) for a in by_agent), 6) for f in AGENT_FIELDS}
    row.update({f"total_{f}": v for f, v in tot.items()})
    row["total_tokens"] = tot["input_tokens"] + tot["output_tokens"]
    row["total_wall_s"] = round(sum(s.get("wall_s", 0) for s in stages.values()), 2)
    row["extraction_tokens_per_paper"] = round(extraction_original / len(papers)) if papers else None
    row["tokens_per_final_class"] = round(row["total_tokens"] / om["classes"]) if om.get("classes") else None
    row["top_concepts"] = "; ".join(c["label"] for c in concepts[:25])
    return row


def upsert_eval(path: Path, row: dict):
    """Replace this run's row (or append it). New columns are added at the end; old rows keep blanks."""
    rows = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r.get("run_id") != row["run_id"]]
    rows.append(row)
    columns = list(dict.fromkeys(k for r in rows for k in r))
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=columns, restval="")
            w.writeheader()
            w.writerows(rows)
    except PermissionError:  # usually open in Excel
        print(f"[eval] could not write {path} (is it open in Excel?); the run itself is unaffected")


def revision_event(path: Path, revision: str, created: str, description: str = ""):
    """One non-metric event when this revision first starts a new run."""
    event_id = "workflow-change:" + revision
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            if any(r.get("run_id") == event_id for r in csv.DictReader(f)):
                return
    upsert_eval(path, {"run_id": event_id, "row_type": "workflow_change", "workflow_revision": revision,
                      "created": created, "change_description": description})
