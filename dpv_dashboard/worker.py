"""Child-process adapter. Imports existing pipeline functions without editing source files.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from dpv_dashboard import model
from dpv_dashboard.auth import credentials, redact


def bootstrap(project, fresh_cache=None):
    # Configure constants before dependent pipeline modules import them. Process-local only.
    os.environ.update(credentials())
    os.environ["LLM_PROFILE"] = project["profile"]
    from src import config
    config.OUTPUTS = model.project_path(project["id"]) / "runs"
    config.CACHE = fresh_cache or model.DATA / "cache"
    config.CACHE.mkdir(parents=True, exist_ok=True)
    # ONTOLOGY_STORE deliberately retains the existing read-only store location.
    from src import run
    run.workers.configure(project["workers"])
    return run


def ingest(run, domain, folder):
    from pyzotero.zotero import Zotero
    from dpv_dashboard.zotero import Libraries, deduplicate
    key = os.environ.get("ZOTERO_API_KEY", "")
    library_api = Libraries(key)
    expanded = library_api.expand(domain["collections"])
    clients, papers = {}, []
    for collection in expanded:
        library = collection["library"]
        identity = (library["type"], library["id"])
        client = clients.setdefault(identity, Zotero(library["id"], library["type"], key))
        print(f"Reading {library['name']} / {collection['name']}", flush=True)
        for item in client.everything(client.collection_items_top(collection["key"])):
            data = item["data"]
            if data["itemType"] in ("attachment", "note", "annotation"):
                continue
            doi = data.get("DOI", "") or next((line.split(":", 1)[1].strip()
                for line in data.get("extra", "").splitlines() if line.lower().startswith("doi:")), "")
            source = {"library": library, "item_key": item["key"], "collection": collection["key"]}
            papers.append({"key": f"{library['type']}-{library['id']}-{item['key']}",
                "title": data.get("title", ""), "doi": doi, "year": item.get("meta", {}).get("parsedDate", "")[:4],
                "authors": [c.get("lastName") or c.get("name", "") for c in data.get("creators", [])],
                "sources": [source], "pdf": None, "pdf_source": None})
    unique = deduplicate(papers)
    print(f"Ranking {len(unique)} distinct papers across {len(expanded)} collections by citations", flush=True)
    counts = run.citations.counts([p["doi"] for p in unique if p["doi"]])
    for paper in unique:
        count = counts.get(run.citations.norm(paper["doi"]), {})
        paper.update(citations=count.get("count"), citations_source=count.get("source"), citations_fetched=count.get("fetched"))
    ranked = sorted(unique, key=lambda p: (p["citations"] is None, -(p["citations"] or 0), p["key"]))
    chosen, skipped = [], []
    pdfs = model.DATA / "cache" / "pdfs"
    pdfs.mkdir(parents=True, exist_ok=True)
    for paper in ranked:
        if len(chosen) >= domain["limit"]:
            break
        print(f"Finding PDF {len(chosen) + 1}/{domain['limit']}: {paper['title'][:90]}", flush=True)
        for source in paper["sources"]:
            library = source["library"]
            client = clients[(library["type"], library["id"])]
            path = pdfs / f"{library['type']}-{library['id']}-{source['item_key']}.pdf"
            origin = "cache" if path.is_file() else run.zotero._fetch_pdf(client, source["item_key"], path)
            if origin:
                paper.update(pdf=str(path), pdf_source=origin)
                break
        (chosen if paper["pdf"] else skipped).append(paper)
        model.write(folder / "ingestion.partial.json", {"selected": chosen, "skipped_no_pdf": skipped})
    if not chosen:
        raise ValueError("No papers with available PDFs were found in this domain.")
    selection = {"ranked_by": "citations across domain; missing counts last", "top_n": domain["limit"],
        "items_in_collection": len(unique), "items_without_doi": sum(not p["doi"] for p in unique),
        "items_without_count": sum(p["citations"] is None for p in unique), "selected": chosen,
        "skipped_no_pdf": skipped, "expanded_collections": expanded, "duplicate_memberships": len(papers) - len(unique)}
    model.write(folder / "ingestion.json", {"papers": chosen, "selection": selection})


def parse(run, folder):
    from src.agents.extraction import ExtractionAgent
    data = model.read(folder / "ingestion.json")
    if not data:
        raise ValueError("Complete ingestion first.")
    # _chunks uses only profile settings, not the model or network.
    chunker = object.__new__(ExtractionAgent)
    from src.config import profile_for
    chunker.profile = profile_for("extraction")
    for index, paper in enumerate(data["papers"], 1):
        print(f"Parsing {index}/{len(data['papers'])}: {paper['title'][:90]}", flush=True)
        destination = folder / "parsed" / f"{paper['key']}.json"
        digest = hashlib.sha256(Path(paper["pdf"]).read_bytes()).hexdigest()
        existing = model.read(destination)
        if existing and existing.get("pdf_hash") == digest:
            continue
        parsed = run.pdf_parse.parse(paper["pdf"])
        chunks = chunker._chunks({**paper, **parsed})
        model.write(destination, {**parsed, "key": paper["key"], "title": paper["title"], "pdf_hash": digest, "chunks": chunks})


def perform(project, domain, stage, restart=False):
    folder = model.run_dir(project, domain)
    state = model.read(folder / "dashboard.json", {}) if folder else {}
    if restart or folder is None:
        folder = model.new_attempt(project, domain, stage)
    elif state.get("stages", {}).get(stage, {}).get("status") == "completed":
        return
    earlier = model.STAGES[:model.STAGES.index(stage)]
    current = model.read(folder / "dashboard.json", {})
    if any(current.get("stages", {}).get(s, {}).get("status") != "completed" for s in earlier):
        raise ValueError("Complete all preceding domain stages first.")
    model.stage_state(folder, stage, "running")
    model.write(model.project_path(project["id"]) / "active.json", {"domain": domain["id"], "stage": stage, "folder": str(folder)})
    try:
        run = bootstrap(project, folder / "cache" if restart else None)
        run.configure_logging(folder, folder.name)
        run.set_stage(stage)
        if stage == "ingest":
            ingest(run, domain, folder)
        elif stage == "parse":
            parse(run, folder)
        else:
            run.config.COLLECTIONS[domain["id"]] = {"library_id": "dashboard", "collection_key": "DOMAIN"}
            pipeline_run = run.Run(folder.name, domain["id"])
            args = SimpleNamespace(limit=domain["limit"], workers=project["workers"])
            if stage == "extract":
                data = model.read(folder / "ingestion.json")
                run.select_papers = lambda *a, **kw: (data["papers"], data["selection"])
                original = run.pdf_parse.parse
                def saved_parse(path):
                    paper = next(p for p in data["papers"] if p["pdf"] == path)
                    return model.read(folder / "parsed" / f"{paper['key']}.json") or original(path)
                run.pdf_parse.parse = saved_parse
            started = time.perf_counter()
            stats = run.STAGES[stage](pipeline_run, args)
            pipeline_run.record(stage, stats, time.perf_counter() - started)
            if stage == "extract" and stats.get("failed"):
                raise ValueError(f"Extraction was partial: {stats['failed']} paper(s) failed. Inspect logs and resume.")
        model.stage_state(folder, stage, "completed")
    except BaseException:
        model.stage_state(folder, stage, "failed")
        raise


def integrate(project):
    if len(project["domains"]) < 2:
        raise ValueError("Integration requires at least two domains.")
    for domain in project["domains"]:
        folder = model.run_dir(project, domain)
        state = model.read(folder / "dashboard.json", {}) if folder else {}
        if state.get("stages", {}).get("interop", {}).get("status") != "completed":
            raise ValueError("Complete interoperability for every selected domain before integration.")
    run = bootstrap(project)
    identifier = "integration-" + uuid4().hex[:12]
    run.integrate(SimpleNamespace(outputs=str(model.project_path(project["id"]) / "runs"),
        collections=None, runs=[d["run"] for d in project["domains"]], run_id=identifier, no_figures=True))
    project["integration"] = identifier
    project["integration_stale"] = False
    save = model.load_project(project["id"])
    save.update(integration=identifier, integration_stale=False)
    save.setdefault("integration_history", []).append(identifier)
    save["report_stale"] = True
    model.save_project(save)


def reports(project):
    bootstrap(project)
    from src import figures
    run_ids = [d["run"] for d in project["domains"] if d.get("run") and
               model.read(model.run_dir(project, d) / "dashboard.json", {}).get("stages", {}).get("interop", {}).get("status") == "completed"]
    if not run_ids:
        raise ValueError("Complete interoperability for at least one domain before generating reports.")
    identifier = "report-" + uuid4().hex[:12]
    figures.build(outputs=model.project_path(project["id"]) / "runs", run_ids=run_ids,
                  out_dir=model.project_path(project["id"]) / identifier, title=project["name"])
    current = model.load_project(project["id"])
    current["report_stale"] = False
    current["report"] = identifier
    current.setdefault("report_history", []).append(identifier)
    model.save_project(current)


def global_stage(project, stage):
    root = model.project_path(project["id"])
    model.stage_state(root, stage, "running")
    model.write(root / "active.json", {"stage": stage, "folder": str(root)})
    try:
        (integrate if stage == "integrate" else reports)(project)
        model.stage_state(root, stage, "completed")
    except BaseException:
        model.stage_state(root, stage, "failed")
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("action", choices=("all", "resume", "stage", "restart"))
    parser.add_argument("--domain")
    parser.add_argument("--stage", choices=model.STAGES, default="ingest")
    args = parser.parse_args()
    project = model.load_project(args.project)
    if not project["domains"]:
        raise ValueError("Add at least one domain first.")
    if args.action in ("all", "resume"):
        # New interpreter per stage prevents process-local adapters leaking between domains.
        import subprocess
        for domain in project["domains"]:
            for stage in model.STAGES[:7]:
                subprocess.run([sys.executable, "-u", "-m", "dpv_dashboard.worker", project["id"],
                                "stage", "--domain", domain["id"], "--stage", stage], check=True)
        project = model.load_project(project["id"])
        if len(project["domains"]) > 1 and (not project.get("integration") or project.get("integration_stale")):
            global_stage(project, "integrate")
            project = model.load_project(project["id"])
        global_stage(project, "reports")
    elif args.stage == "integrate":
        global_stage(project, "integrate")
    elif args.stage == "reports":
        global_stage(project, "reports")
    else:
        domain = next((d for d in project["domains"] if d["id"] == args.domain), None)
        if not domain:
            raise ValueError("Select a domain.")
        perform(project, domain, args.stage, args.action == "restart")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        print(redact(traceback.format_exc()), file=sys.stderr, flush=True)
        sys.exit(1)
