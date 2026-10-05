"""Pipeline entry point.

  python -m src.run collections --library ID   list a group library's collections and keys
  python -m src.run portal                     list MDS-Onto portal and MatPortal ontology acronyms
  python -m src.run ontologies build|status|search TEXT   local ontology store (Oxigraph + label/embedding index)
  python -m src.run lora-data [--distill RUN_ID ...]   build LoRA training data + Colab upload bundle
  python -m src.run lora-eval --model NAME [--limit N]  score a model on the held-out LoRA test split
  python -m src.run check --collection NAME    preflight: keys, model, embeddings, Zotero PDFs, parser, portal
  python -m src.run all --collection NAME [--limit N]   every stage in a new run
  python -m src.run all --run-id ID            resume a run: only the stages it has not completed
  python -m src.run extract --collection NAME [--limit N]
  python -m src.run normalize --run-id ID      later stages continue an existing run
  (stages: extract, normalize, ontology, enrich, interop; collections are named in src/config.py)
  python -m src.run integrate [--runs ID ...] [--collections NAME ...] [--outputs DIR]
      cross-domain stage after the domain runs: master ontology named after its domains (tea_reliability_si-topcon.ttl)
      mapping their ontologies; outputs/integration-*/
"""
import argparse
import csv
import difflib
import hashlib
import json
import subprocess
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.agents.base import parse_json
from src.agents.enrichment import EnrichmentAgent
from src.agents.extraction import ExtractionAgent
from src.agents.integration import IntegrationAgent
from src.agents.interoperability import InteroperabilityAgent
from src.agents.normalization import NormalizationAgent
from src.agents.ontology import OntologyAgent
from src import config
from src.config import CACHE, OUTPUTS, ROOT, model_for
from src.tools import (bottomup, citations, integration, llm, matportal, mds_portal, ontostore, owl, pdf_parse, reports,
                       zotero, ontology_review)
from src.tools.ledger import Ledger
from src.tools.progress import log, set_stage

AGENTS = ("extraction", "normalization", "ontology", "enrichment", "interoperability")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None
    except OSError:
        return None


def _config() -> dict:
    """Run settings for the manifest. Never includes keys."""
    models = {}
    for a in AGENTS:
        try:
            models[f"model_{a}"] = model_for(a)
        except RuntimeError:
            models[f"model_{a}"] = None
    llm = config.LLM
    return {"llm_profile": config.LLM_PROFILE, "llm_provider": llm["provider"], "llm_base_url": llm["base_url"],
            **models, "temperature": config.TEMPERATURE, "max_output_tokens": config.MAX_OUTPUT_TOKENS,
            "max_input_chars": llm["max_input_chars"], "request_options": llm.get("request"),
            "agent_profiles": {a: {"profile": config.AGENT_PROFILES.get(a, config.LLM_PROFILE),
                                   "provider": config.profile_for(a)["provider"],
                                   "base_url": config.profile_for(a)["base_url"], "tier": config.tier(a),
                                   "max_input_chars": config.profile_for(a)["max_input_chars"]} for a in AGENTS},
            "pipeline_tier": config.tier(), "extraction_passes": config.EXTRACTION_PASSES[config.tier("extraction")], "embed_model": config.EMBED["model"],
            "embed_base_url": config.EMBED["base_url"], "mds_ontologies": config.MDS_ONTOLOGIES or "all",
            "matportal": (config.MATPORTAL["ontologies"] or "all") if config.MATPORTAL["enabled"] else "off",
            "ontology_search": config.ONTOLOGY_SEARCH,
            "workflow_revision": config.WORKFLOW_REVISION, "ontology_iri": config.ONTOLOGY_IRI, "prices_usd_per_m": config.PRICES}


class Run:
    def __init__(self, run_id: str, collection: str):
        self.id, self.dir = run_id, OUTPUTS / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ledger = Ledger(self.dir / "ledger.jsonl")
        path = self.dir / "run.json"
        self.manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
            "run_id": run_id, "created": _now(), "git_commit": _git(), "config": _config(),
            "collection": {"name": collection, **config.COLLECTIONS[collection]}, "stages": {}}
        if not path.exists():
            reports.revision_event(OUTPUTS / "eval_runs.csv", config.WORKFLOW_REVISION, _now(), config.WORKFLOW_REVISION_NOTE)

    def read(self, name: str):
        return json.loads((self.dir / name).read_text(encoding="utf-8"))

    def write(self, name: str, obj):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False)
        path.write_text(text, encoding="utf-8", errors="replace")  # a stray unencodable character never loses a run

    def papers(self) -> list[dict]:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self.dir / "papers").glob("*.json"))]

    def fail(self, stage: str, exc: BaseException):
        """Keep the error with the run (error.log, run.json "errors") and in the central outputs/errors.csv."""
        tb = "".join(traceback.format_exception(exc))
        where = traceback.extract_tb(exc.__traceback__)[-1] if exc.__traceback__ else None
        error = {"stage": stage, "time": _now(), "error": f"{type(exc).__name__}: {exc}"[:500],
                 "where": f"{Path(where.filename).name}:{where.lineno} in {where.name}" if where else ""}
        with (self.dir / "error.log").open("a", encoding="utf-8") as f:
            f.write(f"==== {error['time']} stage {stage}\n{tb}\n")
        self.manifest.setdefault("errors", []).append(error)
        self.write("run.json", self.manifest)
        path = OUTPUTS / "errors.csv"
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["time", "run_id", "collection", "stage", "error", "where"])
            if new:
                w.writeheader()
            w.writerow({"run_id": self.id, "collection": self.manifest["collection"]["name"], **error})
        log(f"stage {stage} failed: {error['error']} ({error['where']}); traceback in {self.dir / 'error.log'}")

    def record(self, stage: str, stats: dict, seconds: float):
        agent = reports.STAGE_AGENT[stage]
        if stage in ("ontology", "enrich", "interop"):
            self.manifest["ontology_store"] = ontostore.summary()
        profile = config.profile_for(agent)
        self.manifest["stages"][stage] = {"completed": _now(), "wall_s": round(seconds, 2), **stats,
                                          "llm_profile": config.AGENT_PROFILES.get(agent, config.LLM_PROFILE),
                                          "model": model_for(agent), "tier": config.tier(agent),
                                          "base_url": profile["base_url"]}
        by_agent = self.ledger.summary("agent")
        total = {k: round(sum(s[k] for s in by_agent.values()), 6) for k in
                 ("calls", "cache_hits", "input_tokens", "cached_tokens", "output_tokens", "latency_s", "cost_usd")}
        self.manifest["compute"] = {"total": total, "by_agent": by_agent}
        self.write("run.json", self.manifest)
        reports.write_csv(self.dir / "compute_per_agent.csv", [{"agent": a, **s} for a, s in by_agent.items()])
        reports.upsert_eval(OUTPUTS / "eval_runs.csv", reports.eval_row(self.dir, self.manifest))


def select_papers(coll: dict, top_n: int | None) -> tuple[list[dict], dict]:
    """Rank a collection by OpenAlex citation count and keep the top N that have a PDF.
    Papers without a DOI or without a count rank last, in Zotero order."""
    log(f"listing Zotero collection {coll['collection_key']} (library {coll['library_id']})")
    items = zotero.list_items(coll["library_id"], coll["collection_key"])
    log(f"{len(items)} items; looking up citation counts for {sum(1 for p in items if p['doi'])} DOIs")
    found = citations.counts([p["doi"] for p in items])
    for p in items:
        c = found.get(citations.norm(p["doi"])) if p["doi"] else None
        p["citations"], p["citations_source"], p["citations_fetched"] = \
            (c["count"], c.get("source"), c["fetched"]) if c else (None, None, None)
    ranked = sorted(items, key=lambda p: -1 if p["citations"] is None else -p["citations"])
    log(f"ranked by citations; getting PDFs for the top {top_n or 'all'}")
    chosen, no_pdf = [], []
    for p in ranked:
        if top_n and len(chosen) >= top_n:
            break
        zotero.attach_pdf(p, CACHE / "pdfs", coll["library_id"])
        (chosen if p["pdf"] else no_pdf).append(p)
        if p["pdf_source"] != "cache":
            log(f"  {p['key']}: {'PDF from ' + p['pdf_source'] if p['pdf'] else 'no PDF, passed over'}")
    return chosen, {
        "ranked_by": "citation count: OpenCitations Index, else OpenAlex, else Crossref", "top_n": top_n,
        "citation_sources": dict(Counter(p["citations_source"] or "none" for p in items)), "items_in_collection": len(items),
        "items_without_doi": sum(1 for p in items if not p["doi"]),
        "items_without_count": sum(1 for p in items if p["citations"] is None),
        "skipped_no_pdf": [{"key": p["key"], "title": p["title"], "citations": p["citations"]} for p in no_pdf],
        "selected": [{"key": p["key"], "doi": p["doi"], "citations": p["citations"],
                      "source": p["citations_source"], "fetched": p["citations_fetched"]} for p in chosen],
    }


def _uncertain(run: Run, stage: str, items: list[dict]):
    """Keep this stage's uncertain items in ontology/uncertain.json; a failure here never fails the run."""
    try:
        data = reports.write_uncertain(run.dir, run.id, stage, items, _now())
        log(f"uncertain items ({stage}): {len(items)} written to {reports.UNCERTAIN} ({data['total']} in all)")
    except Exception as e:
        log(f"uncertain.json not updated ({type(e).__name__}: {e})")


def extract(run: Run, args) -> dict:
    coll = run.manifest["collection"]
    if not coll["collection_key"]:
        raise SystemExit(f"No collection key for '{coll['name']}' in src/config.py COLLECTIONS")
    papers, selection = select_papers(coll, config.TOP_N_BY_CITATIONS)
    papers = papers[: args.limit or None]
    log(f"{len(papers)} papers to extract (top {config.TOP_N_BY_CITATIONS} of {selection['items_in_collection']} by "
        f"citations{f', limited to {args.limit}' if args.limit else ''}; "
        f"{len(selection['skipped_no_pdf'])} passed over for no PDF)")
    agent = ExtractionAgent(run.ledger)
    done, failed, digests = [], [], []
    for n, p in enumerate(papers, 1):
        log(f"paper {n}/{len(papers)} {p['key']} ({p['citations'] if p['citations'] is not None else '?'} citations, "
            f"PDF from {p['pdf_source']}): {p['title'][:70]}")
        try:
            parsed = pdf_parse.parse(p["pdf"])
            st = parsed["parse_stats"]
            log(f"  parsed {st['pages']} pages: {st['n_sections']} sections, {st['n_figures']} figures, "
                f"kept {st['chars_kept']:,} of {st['chars_raw']:,} chars")
            result = agent.run({**p, **parsed})
        except llm.gemini_quota.GeminiRequestStopped:
            raise  # quota exhaustion must not skip papers or mark extraction complete
        except Exception as e:  # keep going; the failure is reported in run.json
            failed.append({"key": p["key"], "title": p["title"], "error": f"{type(e).__name__}: {e}"[:300]})
            log(f"  FAILED: {failed[-1]['error']}")
            continue
        record = {**p, "parse_stats": parsed["parse_stats"], **result}
        run.write(f"papers/{p['key']}.json", record)
        done.append(record)
        with open(p["pdf"], "rb") as f:
            digests.append(p["key"] + hashlib.sha256(f.read()).hexdigest())
        log(f"  -> {len(result['concepts'])} concepts, {len(result['relations'])} relations, "
            f"{len(result['causal'])} causal, {sum(1 for f in result['figures'] if f['concepts'])}/{len(result['figures'])} "
            f"figures linked" + (f"; ends resolved from phrases: {result['resolution']}" if result.get("resolution") else ""))
    reports.write_csv(run.dir / "compute_per_paper.csv", reports.paper_compute(done, run.ledger.summary("item")))
    _uncertain(run, "extract", [{"kind": "unresolved_relation_end", "paper": p["key"], **u}
                                for p in done for u in p.get("unresolved_ends", [])]
               + agent.doubts)
    run.manifest["corpus"] = {"items": len(papers), "processed": len(done), "failed": failed, "selection": selection,
                              "pdf_sources": dict(Counter(p["pdf_source"] or "missing" for p in papers)),
                              "hash": hashlib.sha256("".join(sorted(digests)).encode()).hexdigest()}
    return {"papers": len(done), "skipped_no_pdf": len(selection["skipped_no_pdf"]), "failed": len(failed),
            "concepts": sum(len(p["concepts"]) for p in done), "relations": sum(len(p["relations"]) for p in done),
            "causal": sum(len(p["causal"]) for p in done), "figures": sum(len(p["figures"]) for p in done),
            "cache_hits": sum(1 for p in done if p.get("cache_hit"))}


def normalize(run: Run, args) -> dict:
    papers = run.papers()
    agent = NormalizationAgent(run.ledger)
    norm = agent.run(papers)
    _uncertain(run, "normalize", agent.doubts)
    for name in ("concepts", "relations", "causal", "measurements", "contradictions", "causal_order", "summary"):
        run.write(f"normalized/{name}.json", norm[name])
    stats = reports.corpus_report(run.dir / "corpus_report.md", run.id, norm, papers)
    run.write("normalized/corpus_stats.json", stats)
    log(f"wrote corpus_report.md and normalized/ ({stats['canonical_concepts']} concepts)")
    return stats


def ontology(run: Run, args) -> dict:
    ontostore.require()
    agent = OntologyAgent(run.ledger)
    classes = agent.run(run.read("normalized/concepts.json"), run.read("normalized/relations.json"),
                        run.manifest["collection"]["name"])
    run.write("ontology/classes.json", classes)
    run.write("ontology/review_issues.json", ontology_review.issues(classes))
    log("wrote ontology/classes.json and ontology/review_issues.json")
    _uncertain(run, "ontology", agent.doubts)
    live = [c for c in classes if not c["excluded"]]
    return {"classes": len(live), "excluded": len(classes) - len(live),
            "local_parent": sum(1 for c in live if c["parent"].startswith("k")),
            "placement": {s: sum(1 for c in live if c["parent_source"] == s)
                          for s in ("llm", "name_match", "paper_is_a", "lexical_head", "category_default", "type_default",
                                    "cycle_break")},
            **{k: v for k, v in agent.stats.items() if k != "tier"}, "failed_calls": dict(agent.failures)}


def enrich(run: Run, args) -> dict:
    ontostore.require()
    agent = EnrichmentAgent(run.ledger)
    classes, properties = agent.run(run.read("ontology/classes.json"), run.read("normalized/relations.json"),
                                    run.read("normalized/causal.json"))
    run.write("ontology/enriched.json", classes)
    run.write("ontology/properties.json", properties)
    run.write("ontology/review_issues.json", ontology_review.issues(classes))
    run.write("ontology/cross_domain_candidates.json", ontology_review.correspondences(
        OUTPUTS, run.id, run.manifest["collection"]["name"], classes))
    log("wrote ontology/enriched.json and ontology/properties.json")
    _uncertain(run, "enrich", agent.doubts)
    live = [c for c in classes if not c["excluded"]]
    return {"definitions_llm": sum(1 for c in live if c["definition"]),
            "restrictions": sum(len(c["restrictions"]) for c in live),
            "disjoint_pairs": sum(len(c["disjoint_with"]) for c in live),
            "classes_with_candidates": sum(1 for c in live if c.get("candidates")), **agent.stats}


def interop(run: Run, args) -> dict:
    ontostore.require()
    classes = run.read("ontology/enriched.json")
    agent = InteroperabilityAgent(run.ledger)
    out = agent.run(classes, run.read("ontology/properties.json"), run.papers(), run.id,
                    run.manifest["collection"]["name"])
    run.write("ontology.jsonld", out["jsonld"])
    run.write("ontology.ttl", out["turtle"])
    norm = {n: (run.read(f"normalized/{n}.json") if (run.dir / "normalized" / f"{n}.json").exists() else [])
            for n in ("concepts", "relations", "causal", "measurements")}
    layer, layer_metrics = bottomup.build(run.manifest["collection"]["name"], norm, classes, run.papers())
    run.write("domain_layer.ttl", owl.serialize_turtle(layer))
    run.write("domain_layer.jsonld", owl.serialize(layer))
    run.write("ontology/domain_layer_metrics.json", layer_metrics)
    log(f"wrote domain_layer.ttl/.jsonld (bottom-up): {layer_metrics['concepts']} concepts, "
        f"{layer_metrics.get('broader_is_a', 0)} is-a + {layer_metrics.get('broader_lexical', 0)} lexical broader links, "
        f"{layer_metrics['relation_links']} relations, {layer_metrics['causal_links']} causal, "
        f"{layer_metrics['reported_values']} reported values")
    run.write("ontology/mappings.json", out["mappings"])
    run.write("ontology/imported_definitions.json", out["imported_definitions"])
    run.write("ontology/facets.json", out["facets"])
    run.write("ontology/validation.json", out["validation"])
    run.write("ontology/metrics.json", out["metrics"])
    _uncertain(run, "interop", agent.doubts)
    run.record("interop", {}, 0)  # refresh compute totals before the report reads them
    reports.ontology_report(run.dir / "ontology_report.md", run.id, out["metrics"], out["validation"], classes,
                            run.manifest["compute"]["by_agent"], run.manifest)
    log(f"wrote ontology.jsonld, ontology.ttl and ontology_report.md ({out['metrics']['classes']} classes)")
    return {"classes": out["metrics"]["classes"], "mappings": len(out["mappings"]),
            "valid": out["validation"]["valid"], "issues": out["validation"]["n_issues"], "checks": out["checks"]}


def _require(ok, message: str):
    if not ok:
        raise RuntimeError(message)


def check(args):
    """Preflight for one collection. Also downloads the collection's PDFs into the cache."""
    coll = config.COLLECTIONS[args.collection]
    print(f"profile {config.LLM_PROFILE} ({config.LLM['model']}), collection '{args.collection}'")
    state = {}

    def keys():
        need = [k for k in (config.LLM["api_key_env"], config.EMBED["api_key_env"] if config.EMBED["model"] else None,
                            "ZOTERO_API_KEY") if k]
        need = list(dict.fromkeys(need))
        missing = [k for k in need if not config.secret(k)]
        _require(not missing, f"blank in .env: {', '.join(missing)}")
        return ", ".join(need) + " set"

    def model():
        text, u = llm.chat("Reply with JSON only.", 'Return {"ok": true}', model_for("extraction"), max_tokens=2000, profile=config.profile_for("extraction"))
        _require(parse_json(text) is not None, f"no JSON in reply: {text[:120]!r}")
        return f"{model_for('extraction')} replied in {u.latency_s}s ({u.input_tokens} in / {u.output_tokens} out)"

    def embeddings():
        if not config.EMBED["model"]:
            return "off (lexical merging only)"
        vectors, _ = llm.embed(["open-circuit voltage"])
        return f"{config.EMBED['model']}, dim {len(vectors[0])}"

    def corpus():
        _require(coll["collection_key"], f"no collection key for '{args.collection}' in src/config.py COLLECTIONS")
        state["papers"], sel = select_papers(coll, config.TOP_N_BY_CITATIONS)
        _require(state["papers"], "no PDFs available for any selected item")
        cites = [p["citations"] for p in state["papers"] if p["citations"] is not None]
        sources = Counter(p["pdf_source"] for p in state["papers"])
        return (f"{len(state['papers'])} selected of {sel['items_in_collection']} "
                f"(citations {min(cites, default=0)}-{max(cites, default=0)}; {sel['items_without_doi']} without DOI, "
                f"{len(sel['skipped_no_pdf'])} passed over for no PDF); PDFs: "
                + ", ".join(f"{k} {n}" for k, n in sources.items()))

    def parser():
        paper = next((p for p in state.get("papers", []) if p["pdf"]), None)
        _require(paper, "skipped: no PDF from the zotero step")
        st = pdf_parse.parse(paper["pdf"])["parse_stats"]
        return (f"{paper['key']}: {st['pages']} pages, {st['n_sections']} sections, {st['n_figures']} figures, "
                f"{st['reduction']:.0%} text dropped")

    def portal():
        known = mds_portal.list_ontologies()
        _, unknown = mds_portal.check_acronyms(config.MDS_ONTOLOGIES)
        hints = {u: difflib.get_close_matches(u.upper(), known, n=3, cutoff=0.4) for u in unknown}
        _require(not unknown, "unknown acronyms in MDS_ONTOLOGIES: " + "; ".join(
            f"{u} (did you mean {', '.join(h) or 'nothing close'}?)" for u, h in hints.items()))
        hits = mds_portal.search("solar cell", ontologies=config.MDS_ONTOLOGIES, max_results=5)
        _require(hits, "no results (portal unreachable or key rejected)")
        return f"{len(known)} ontologies on portal; {len(hits)} hits from {sorted({h['Ontology'] for h in hits})}"

    def matportal_check():
        if not config.MATPORTAL["enabled"]:
            return "off (MATPORTAL['enabled'] = False)"
        _require(config.secret("MATPORTAL_API_KEY"), "MATPORTAL_API_KEY is blank in .env")
        _, unknown = matportal.check_acronyms(config.MATPORTAL["ontologies"])
        _require(not unknown, f"unknown acronyms in MATPORTAL['ontologies']: {', '.join(unknown)}")
        hits = matportal.search("solar cell", ontologies=config.MATPORTAL["ontologies"], max_results=5)
        _require(hits, "no results (key rejected or portal unreachable)")
        return f"{len(matportal.list_ontologies())} ontologies on MatPortal; {len(hits)} hits from {sorted({h['Ontology'] for h in hits})}"

    def store():
        st = ontostore.status()
        _require(st["built"], "; ".join(st["problems"]))
        _require(not st["problems"], "; ".join(st["problems"]))
        return (f"{st['terms']:,} terms built {st['built']} ({', '.join(f'{k} {v}' for k, v in st['versions'].items())}); "
                f"embeddings {st['embed_model'] or 'off'}" + "".join(f"; note: {n}" for n in st["notes"]))

    failed = 0
    for label, fn in (("keys", keys), ("model", model), ("embeddings", embeddings), ("zotero + citations", corpus),
                      ("pdf parser", parser), ("mds portal", portal), ("matportal", matportal_check),
                      ("ontology store", store)):
        t0 = time.perf_counter()
        try:
            status, detail = "ok", fn()
        except Exception as e:
            status, detail, failed = "FAIL", f"{type(e).__name__}: {e}"[:300], failed + 1
        print(f"[{status:>4}] {label}: {detail} ({time.perf_counter() - t0:.1f}s)")
    print("ready" if not failed else f"{failed} check(s) failed")


def collections(args):
    library = args.library or config.COLLECTIONS[config.DEFAULT_COLLECTION]["library_id"]
    for c in sorted(zotero.list_collections(library), key=lambda c: c["name"].lower()):
        print(f"{c['key']}  {c['items']:>4}  {c['name']}" + (f"  (inside {c['parent']})" if c["parent"] else ""))


def lora_data(args):
    from src.tools import lora_data as ld
    ld.build(args.distill)


def lora_eval(args):
    from src.tools import lora_eval as le
    le.run(args.model or model_for("extraction"), args.limit)


def portal(args):
    print("== MDS-Onto portal (MDS_ONTOLOGIES) ==")
    for acronym, name in sorted(mds_portal.list_ontologies().items()):
        print(f"{acronym:<20} {name}")
    if config.MATPORTAL["enabled"] and config.secret("MATPORTAL_API_KEY"):
        print("\n== MatPortal (MATPORTAL['ontologies']) ==")
        for acronym, name in sorted(matportal.list_ontologies().items()):
            print(f"{acronym:<20} {name}")


def ontologies(args):
    """build: download missing ontology files, load them into Oxigraph, index labels, embed every term.
    status: is the store current (files, embedding model, newer MDS-Onto submission). search TEXT: try a query."""
    action = args.action or "status"
    if action == "build":
        ontostore.build()
    elif action == "status":
        print(json.dumps(ontostore.status(), indent=1))
    elif action == "search":
        text = " ".join(args.query)
        vector = llm.embed([text])[0][0] if config.EMBED["model"] else None
        for c in ontostore.search([text], vector, k=args.limit or 10):
            print(f"{c['score']:.2f}  {c['ontology']:<10} {c['kind']:<19} {c['label'][:50]:<50} {c['iri']}"
                  f"  [{', '.join(c['methods']) or 'fused'}]")
    else:
        raise SystemExit("ontologies: build, status or search TEXT")


def integrate(args):
    """Cross-domain stage: map the domain ontologies of completed runs to each other in one master ontology.
    Reads the domain runs; never rewrites them."""
    outputs = Path(args.outputs).resolve() if args.outputs else OUTPUTS
    selected, notes = integration.select_runs(outputs, args.collections, args.runs)
    for n in notes:
        log(n)
    if len(selected) < 2:
        raise SystemExit(f"integration needs completed runs for at least two domains in {outputs}; found {len(selected)}")
    name = integration.master_name([s["domain"] for s in selected])
    iid = args.run_id or f"integration-{name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out = outputs / iid
    out.mkdir(parents=True, exist_ok=True)
    write = lambda name, obj: (out / name).write_text(
        obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    t0 = time.perf_counter()
    try:
        domains, graphs = {}, {}
        for s in selected:
            domains[s["domain"]], g, iri = integration.load_domain(s)
            graphs[s["domain"]] = {"graph": g, "iri": iri}
            log(f"{s['domain']}: {s['run_id']} ({len(domains[s['domain']])} classes, revision {s['revision'] or 'none'})")
        agent = IntegrationAgent(Ledger(out / "ledger.jsonl"))
        result = agent.run(domains)
        master = integration.build_master(selected, graphs, result["mappings"], iid)
        text = owl.serialize(master)
        validation = integration.validate(master, text, graphs, result["mappings"])
        merged = integration.merge(master, graphs)
        write(f"{name}.jsonld", text)
        write(f"{name}.ttl", owl.serialize_turtle(master))
        write(f"{name}_merged.ttl", owl.serialize_turtle(merged))
        write("candidates.json", integration.public_candidates(result["candidates"]))
        write("mappings.json", result["mappings"])
        write("bridge_concepts.json", result["clusters"])
        write("validation.json", validation)
        by_agent = agent.ledger.summary("agent")
        compute = {k: round(sum(s.get(k, 0) or 0 for s in by_agent.values()), 6)
                   for k in ("calls", "input_tokens", "cached_tokens", "output_tokens", "latency_s")}
        compute["wall_s"] = round(time.perf_counter() - t0, 2)
        row = integration.report(out / "integration_report.md", iid, selected, domains, result, validation, compute,
                                 notes, len(merged))
        write("integration.json", {
            "integration_id": iid, "created": _now(), "git_commit": _git(), "config": _config(),
            "integration": {**config.INTEGRATION, "llm_profile": config.AGENT_PROFILES.get("integration", config.LLM_PROFILE),
                            "model": model_for("integration"), "tier": config.tier("integration"),
                            "embedding_error": getattr(agent, "embedding_error", None)},
            "inputs": [{k: s[k] for k in ("run_id", "domain", "revision", "profile", "created")} | {"ontology_iri": graphs[s["domain"]]["iri"]}
                       for s in selected],
            "ontology": {"name": name, "iri": f"{owl.base()}{name}",
                         "files": [f"{name}.ttl", f"{name}.jsonld", f"{name}_merged.ttl"]},
            "notes": notes, "stats": result["stats"], "validation": {k: validation[k] for k in ("valid", "n_issues")},
            "compute": compute})
        reports.upsert_eval(outputs / "eval_integrations.csv", row)
    except BaseException:
        (out / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    log(f"finished; {len(result['mappings'])} mappings, {len(result['clusters'])} bridge concepts; outputs in {out}; "
        f"summary row in {outputs / 'eval_integrations.csv'}")


STAGES = {"extract": extract, "normalize": normalize, "ontology": ontology, "enrich": enrich, "interop": interop}


def main():
    ap = argparse.ArgumentParser(description="Zotero -> concepts -> BFO/CCO ontology pipeline")
    ap.add_argument("stage", choices=[*STAGES, "all", "check", "collections", "portal", "lora-data", "lora-eval", "integrate",
                                      "ontologies"])
    ap.add_argument("action", nargs="?", help="ontologies: build, status or search")
    ap.add_argument("query", nargs="*", help="ontologies search: the text to search for")
    ap.add_argument("--collection", default=config.DEFAULT_COLLECTION, choices=list(config.COLLECTIONS),
                    help="named collection from src/config.py COLLECTIONS")
    ap.add_argument("--library", help="group library id (for 'collections')")
    ap.add_argument("--run-id", help="continue an existing run in outputs/<run-id>")
    ap.add_argument("--limit", type=int, help="process only the first N papers (or N test examples for lora-eval)")
    ap.add_argument("--distill", nargs="*", default=[], help="lora-data: run ids whose extractions become training data")
    ap.add_argument("--model", help="lora-eval: model name on the active profile (default: its model)")
    ap.add_argument("--runs", nargs="*", help="integrate: one completed run id per domain (default: latest per collection)")
    ap.add_argument("--collections", nargs="*", help="integrate: collections to include (default: INTEGRATION in config)")
    ap.add_argument("--outputs", help="integrate: outputs folder holding the runs (default: this checkout's outputs)")
    args = ap.parse_args()
    utilities = {"check": check, "collections": collections, "portal": portal, "lora-data": lora_data, "lora-eval": lora_eval,
                 "integrate": integrate, "ontologies": ontologies}
    if args.stage in utilities:
        set_stage(args.stage)
        return utilities[args.stage](args)
    run = Run(args.run_id or f"{args.collection}-{datetime.now().strftime('%Y%m%d-%H%M%S')}", args.collection)
    names = list(STAGES) if args.stage == "all" else [args.stage]
    if args.stage == "all" and args.run_id:  # resume: skip the stages this run already completed
        names = [n for n in names if n not in run.manifest["stages"]]
    log(f"run {run.id}: collection '{run.manifest['collection']['name']}', profile {config.LLM_PROFILE}, "
        f"stages {' -> '.join(names)}")
    for i, name in enumerate(names, 1):
        agent = reports.STAGE_AGENT[name]
        set_stage(name)
        print(f"\n==== stage {i}/{len(names)}: {name} ({agent} agent, {config.AGENT_PROFILES.get(agent, config.LLM_PROFILE)}, {model_for(agent)}) ====", flush=True)
        t0 = time.perf_counter()
        before = run.ledger.summary("agent").get(agent, {})
        try:
            run.record(name, STAGES[name](run, args), time.perf_counter() - t0)
        except BaseException as e:  # includes Ctrl+C, so interrupted runs are listed too
            run.fail(name, e)
            raise
        after = run.manifest["compute"]["by_agent"].get(agent, {})
        spent = {k: after.get(k, 0) - before.get(k, 0) for k in ("calls", "input_tokens", "output_tokens")}
        log(f"done in {time.perf_counter() - t0:.1f}s: {spent['calls']} model calls, "
            f"{spent['input_tokens']:,} in / {spent['output_tokens']:,} out")
    set_stage("run")
    log(f"finished; outputs in {run.dir}; summary row in {OUTPUTS / 'eval_runs.csv'}")


if __name__ == "__main__":
    main()
