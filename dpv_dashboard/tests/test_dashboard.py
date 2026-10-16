"""Offline regression coverage for the wrapper's domain and attempt semantics.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from types import SimpleNamespace
from pathlib import Path
import json
import pytest
from dpv_dashboard import model
from dpv_dashboard.zotero import Libraries, deduplicate
from dpv_dashboard.viewer import convert


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(model, "DATA", tmp_path)
    monkeypatch.setenv("DPV_DASHBOARD_HOME", str(tmp_path))
    project = model.create_project("PV research")
    sources = [{"library": {"id": "1", "type": "group", "name": "PV"}, "key": "ABCDEFGH", "name": "Cells"}]
    model.add_domain(project, "Cell reliability", 2, sources)
    return project, project["domains"][0]


def test_restart_preserves_upstream_and_invalidates_downstream(workspace):
    project, domain = workspace
    old = model.new_attempt(project, domain, "ingest")
    for stage in model.STAGES[:7]:
        model.stage_state(old, stage, "completed")
    model.write(old / "ingestion.json", {"papers": []})
    model.write(old / "parsed/a.json", {"sections": []})
    model.write(old / "papers/a.json", {"concepts": []})
    model.write(old / "normalized/concepts.json", [{"label": "old result"}])
    model.write(old / "ontology/classes.json", [])
    model.write(old / "run.json", {"run_id": old.name, "stages": {s: {} for s in model.STAGES[:7]}})
    project["integration"] = "integration-old"
    new = model.new_attempt(project, domain, "normalize")
    assert (new / "papers/a.json").is_file()
    assert not (new / "normalized/concepts.json").exists()
    assert not (new / "ontology/classes.json").exists()
    assert (old / "normalized/concepts.json").is_file()
    assert project["integration_stale"] and project["report_stale"]
    assert set(model.read(new / "run.json")["stages"]) == {"ingest", "parse", "extract"}


def test_stage_requires_completed_inputs(workspace):
    project, domain = workspace
    with pytest.raises(ValueError, match="preceding"):
        model.new_attempt(project, domain, "normalize")


def test_recursive_expansion_deduplicates_overlapping_roots(monkeypatch):
    library = {"id": "123", "type": "group", "name": "PV"}
    rows = [{"library": library, "key": key, "parent": parent, "name": key}
            for key, parent in [("AAAAAAAA", ""), ("BBBBBBBB", "AAAAAAAA"), ("CCCCCCCC", "BBBBBBBB")]]
    monkeypatch.setattr(Libraries, "collections", lambda *args: rows)
    assert len(Libraries("fixture").expand(rows[:2])) == 3


def test_doi_duplicates_keep_attachment_alternatives():
    papers = [{"key": "group-1-AAA", "doi": "https://doi.org/10.1/TEST", "sources": [{"library": 1}]},
              {"key": "user-2-BBB", "doi": "10.1/test", "sources": [{"library": 2}]}]
    result = deduplicate(papers)
    assert len(result) == 1 and len(result[0]["sources"]) == 2


def test_domain_ranking_across_groups_not_per_collection(workspace, monkeypatch):
    from dpv_dashboard.worker import ingest
    from pyzotero import zotero
    project, domain = workspace
    folder = model.new_attempt(project, domain, "ingest")
    domain["collections"] = [
        {"key": "AAAAAAAA", "name": "A", "library": {"type": "group", "id": "1", "name": "Group A"}},
        {"key": "BBBBBBBB", "name": "B", "library": {"type": "user", "id": "2", "name": "Personal"}}]
    monkeypatch.setenv("ZOTERO_API_KEY", "offline-fixture")
    monkeypatch.setattr(Libraries, "expand", lambda self, selected: selected)
    class Client:
        def __init__(self, identifier, *args):
            self.id = identifier
        def everything(self, result):
            return result
        def collection_items_top(self, key):
            return [{"key": f"PAPER00{n}", "data": {"itemType": "journalArticle", "title": f"Paper {n}", "DOI": f"10.1/{n}"}}
                    for n in ([1, 2] if self.id == "1" else [3, 4])]
    monkeypatch.setattr(zotero, "Zotero", Client)
    count = {"10.1/1": {"count": 5}, "10.1/2": {"count": 8}, "10.1/3": {"count": 30}, "10.1/4": {"count": 20}}
    def pdf(client, key, destination):
        destination.write_bytes(b"fixture pdf")
        return "fixture"
    run = SimpleNamespace(citations=SimpleNamespace(counts=lambda dois: count, norm=lambda doi: doi),
                          zotero=SimpleNamespace(_fetch_pdf=pdf))
    ingest(run, domain, folder)
    selected = model.read(folder / "ingestion.json")["papers"]
    assert [p["citations"] for p in selected] == [30, 20]
    assert all(p["key"].startswith("user-2-") for p in selected)


def test_personal_and_restricted_group_discovery(monkeypatch):
    api = Libraries("fixture")
    monkeypatch.setattr(api, "get", lambda path, params=None: {"userID": 9, "access": {
        "user": {"library": True}, "groups": {"1": {"library": True}}}} if path == "/keys/current" else {})
    monkeypatch.setattr(api, "pages", lambda path: [{"id": 1, "data": {"name": "Allowed"}}, {"id": 2, "data": {"name": "Denied"}}])
    assert [(r["type"], r["id"]) for r in api.libraries()] == [("user", "9"), ("group", "1")]


def test_webvowl_keeps_mapping_and_restriction_iris():
    text = '''@prefix ex: <https://example.org/> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
    ex:Cell a owl:Class; rdfs:label "Solar cell"; skos:exactMatch ex:Device;
      rdfs:subClassOf [a owl:Restriction; owl:onProperty ex:hasPart; owl:someValuesFrom ex:Layer] .'''
    result = convert(text)
    assert {r["iri"] for r in result["classAttribute"]} == {"https://example.org/Cell", "https://example.org/Device", "https://example.org/Layer"}
    assert len(result["property"]) == 2


def test_paths_cannot_escape_workspace(tmp_path):
    with pytest.raises(ValueError):
        model.inside(tmp_path, "../private.env")


def test_subprocess_bootstrap_isolates_pipeline_outputs(workspace):
    # A fresh process proves configuration is applied before dependent imports.
    import subprocess
    import sys
    project, domain = workspace
    code = '''from dpv_dashboard.worker import bootstrap
from dpv_dashboard import model
import json
project = json.loads(__import__('sys').argv[1])
run = bootstrap(project)
from src.agents import extraction
print(json.dumps({'outputs':str(run.OUTPUTS),'cache':str(extraction.CACHE),'store':str(run.ontostore.DB)}))'''
    completed = subprocess.run([sys.executable, "-c", code, json.dumps(project)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert str(model.DATA) in result["outputs"] and str(model.DATA) in result["cache"]
    assert "ontology_store" in result["store"]


def test_parser_saves_existing_chunker_windows_without_model(workspace):
    import pymupdf
    from src.tools import pdf_parse
    from dpv_dashboard.worker import parse
    project, domain = workspace
    folder = model.new_attempt(project, domain, "ingest")
    pdf = model.DATA / "paper.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Introduction\nSolar cell reliability depends on passivation quality.")
    doc.save(pdf)
    doc.close()
    model.write(folder / "ingestion.json", {"papers": [{"key": "fixture", "pdf": str(pdf), "title": "Solar cells"}]})
    parse(SimpleNamespace(pdf_parse=pdf_parse), folder)
    result = model.read(folder / "parsed/fixture.json")
    assert result["chunks"] and "Solar cell reliability" in result["chunks"][0]
    assert result["pdf_hash"]


def test_supervised_worker_failure_is_durable_without_network(workspace):
    import time
    from dpv_dashboard.jobs import Jobs
    project, domain = workspace
    jobs = Jobs()
    jobs.start(project, "stage", domain["id"], "normalize")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        state = model.read(model.project_path(project["id"]) / "job.json", {})
        if state.get("status") == "failed":
            break
        time.sleep(0.05)
    assert state["status"] == "failed"
    assert "Complete the preceding stages" in jobs.log(project)


def test_report_attempts_are_preserved(workspace, monkeypatch):
    from dpv_dashboard import worker
    from src import figures
    project, domain = workspace
    folder = model.new_attempt(project, domain, "ingest")
    model.stage_state(folder, "interop", "completed")
    monkeypatch.setattr(worker, "bootstrap", lambda project: None)
    def build(**kwargs):
        out = kwargs["out_dir"]
        out.mkdir()
        (out / "report.html").write_text("fixture report")
        return out
    monkeypatch.setattr(figures, "build", build)
    worker.global_stage(project, "reports")
    first = model.load_project(project["id"])["report"]
    worker.global_stage(model.load_project(project["id"]), "reports")
    current = model.load_project(project["id"])
    assert first != current["report"]
    assert (model.project_path(project["id"]) / first / "report.html").is_file()
    assert len(current["report_history"]) == 2


def test_restart_filters_downstream_compute(workspace):
    project, domain = workspace
    folder = model.new_attempt(project, domain, "ingest")
    for stage in ("ingest", "parse", "extract"):
        model.stage_state(folder, stage, "completed")
    (folder / "ledger.jsonl").write_text(json.dumps({"agent": "extraction"}) + "\n" + json.dumps({"agent": "enrichment"}) + "\n")
    new = model.new_attempt(project, domain, "normalize")
    assert (new / "ledger.jsonl").read_text().strip() == json.dumps({"agent": "extraction"})


def test_cancel_stops_only_supervised_test_process(workspace, monkeypatch):
    import subprocess
    import sys
    import time
    from dpv_dashboard import jobs as job_module
    project, domain = workspace
    real_popen = subprocess.Popen
    def sleeping_process(command, **kwargs):
        return real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
    monkeypatch.setattr(job_module.subprocess, "Popen", sleeping_process)
    jobs = job_module.Jobs()
    jobs.start(project, "stage", domain["id"], "ingest")
    # Restore Popen before taskkill/subprocess.run creates its own process.
    monkeypatch.setattr(job_module.subprocess, "Popen", real_popen)
    assert jobs.running()
    jobs.cancel(project["id"])
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state = model.read(model.project_path(project["id"]) / "job.json", {})
        if state.get("status") == "cancelled":
            break
        time.sleep(0.05)
    assert state["status"] == "cancelled"
    assert jobs.process.poll() is not None
