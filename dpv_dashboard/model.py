"""Project persistence and immutable stage-attempt snapshots, without pipeline imports.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("DPV_DASHBOARD_HOME", ROOT / "outputs" / "dashboard")).resolve()


def viewer():
    """Viewer mode (DPV_VIEWER=1 or --viewer): saved results only; no projects, jobs or saved settings."""
    return os.environ.get("DPV_VIEWER", "").strip().lower() in ("1", "true", "yes", "on")


def require_editor():
    if viewer():
        raise ValueError("This dashboard is in viewer mode: saved results can be explored, not changed or run.")
STAGES = ("ingest", "parse", "extract", "normalize", "ontology", "enrich", "interop", "integrate", "reports")
TITLES = ("Zotero ingestion", "Parsing & chunking", "Evidence extraction", "Corpus normalization",
          "Ontology placement", "Enrichment", "Interoperability & export", "Cross-domain integration", "Reports & figures")
ARTIFACTS = {
    "ingest": ("ingestion.json",), "parse": ("parsed/*.json",),
    "extract": ("papers/*.json", "compute_per_paper.csv"),
    "normalize": ("normalized/*.json", "corpus_report.md"),
    "ontology": ("ontology/classes.json", "ontology/review_issues.json", "ontology/uncertain.json"),
    "enrich": ("ontology/enriched.json", "ontology/properties.json", "ontology/materials_project.json",
               "ontology/review_issues.json", "ontology/cross_domain_candidates.json"),
    "interop": ("ontology.ttl", "ontology.jsonld", "domain_layer.*", "ontology/mappings.json",
                "ontology/imported_definitions.json", "ontology/facets.json", "ontology/validation.json",
                "ontology/metrics.json", "ontology/domain_layer_metrics.json"),
    "integrate": ("*.ttl", "*.jsonld", "mappings.json", "bridge_concepts.json", "validation.json", "integration_report.md"),
    "reports": ("**/*.png", "**/*.pdf", "**/*.csv", "*.md", "*.html"),
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    # Windows briefly denies replacement while a polling reader holds the target.
    for attempt in range(50):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(0.02)


def slug(name):
    result = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]
    if not result:
        raise ValueError("Use a domain name containing letters or numbers.")
    return result


def inside(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("File must belong to the selected workspace.")
    return target


def project_path(identifier):
    if not re.fullmatch(r"[a-f0-9]{32}", identifier or ""):
        raise ValueError("Select a valid project.")
    return DATA / "projects" / identifier


def projects():
    if viewer():
        return []
    return sorted((p for f in (DATA / "projects").glob("*/project.json") if (p := read(f))),
                  key=lambda p: p["created"], reverse=True)


def create_project(name):
    if not name.strip():
        raise ValueError("Enter a project name.")
    project = {"id": uuid4().hex, "name": name.strip(), "created": now(), "domains": [],
               "profile": "ollama", "workers": 2, "integration": None, "integration_stale": False, "report_stale": False}
    save_project(project)
    return project


def load_project(identifier):
    project = read(project_path(identifier) / "project.json")
    if not project:
        raise ValueError("Project not found.")
    return project


def save_project(project):
    require_editor()
    write(project_path(project["id"]) / "project.json", project)


def add_domain(project, name, limit, collections):
    key = slug(name)
    if any(d["id"] == key for d in project["domains"]):
        raise ValueError("That domain already exists. Use a different name.")
    if not collections or int(limit) < 1:
        raise ValueError("Select collections and a positive paper limit.")
    project["domains"].append({"id": key, "name": name.strip(), "limit": int(limit),
                               "collections": collections, "run": None, "history": []})
    save_project(project)


def run_dir(project, domain):
    return project_path(project["id"]) / "runs" / domain["run"] if domain.get("run") else None


def new_attempt(project, domain, stage):
    """Copy only upstream products. Previous attempts are never changed or deleted."""
    if stage not in STAGES[:7]:
        raise ValueError("Not a domain stage.")
    old = run_dir(project, domain)
    previous = read(old / "dashboard.json", {}) if old else {}
    upstream = STAGES[:STAGES.index(stage)]
    if upstream and any(previous.get("stages", {}).get(s, {}).get("status") != "completed" for s in upstream):
        raise ValueError("Complete the preceding stages first.")
    identifier = f"{domain['id']}-{uuid4().hex[:12]}"
    folder = project_path(project["id"]) / "runs" / identifier
    folder.mkdir(parents=True)
    if old:
        for earlier in upstream:
            for pattern in ARTIFACTS[earlier]:
                for source in old.glob(pattern):
                    if source.is_file():
                        destination = folder / source.relative_to(old)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, destination)
        # Retain only upstream compute provenance, not invalidated downstream calls.
        agents = {"extract": "extraction", "normalize": "normalization", "ontology": "ontology",
                  "enrich": "enrichment", "interop": "interoperability"}
        for name in ("ledger.jsonl", "calls.jsonl"):
            if (old / name).is_file():
                lines = []
                for line in (old / name).read_text(encoding="utf-8").splitlines():
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if row.get("agent") in {agents[s] for s in upstream if s in agents}:
                        lines.append(line)
                (folder / name).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        manifest = read(old / "run.json")
        if manifest:
            manifest.update(run_id=identifier, created=now())
            manifest["stages"] = {k: v for k, v in manifest.get("stages", {}).items() if k in upstream}
            manifest.pop("errors", None)
            if "extract" not in upstream:
                manifest.pop("corpus", None)
            write(folder / "run.json", manifest)
    state = {"run_id": identifier, "parent": domain.get("run"), "created": now(), "stages": {
        s: previous["stages"][s] for s in upstream}}
    write(folder / "dashboard.json", state)
    domain["run"] = identifier
    domain["history"].append(identifier)
    if project.get("integration"):
        project["integration_stale"] = True
    project["report_stale"] = True
    save_project(project)
    return folder


def stage_state(folder, stage, status, **extra):
    state = read(folder / "dashboard.json", {"stages": {}})
    state["stages"][stage] = {"status": status, "updated": now(), **extra}
    write(folder / "dashboard.json", state)


def artifact_files(folder, stage):
    if not folder:
        return []
    return sorted({p for pattern in ARTIFACTS[stage] for p in folder.glob(pattern)
                   if p.is_file() and p.resolve().is_relative_to(folder.resolve())})
