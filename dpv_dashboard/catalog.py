"""Read-only artifact inventory. Files being written are never treated as completed work.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo
from dpv_dashboard import model

MAX_JSON = 64 * 1024 * 1024
REQUIRED = {
    "normalize": tuple(f"normalized/{name}.json" for name in
                       ("concepts", "relations", "causal", "measurements", "contradictions", "causal_order", "summary", "corpus_stats")),
    "ontology": ("ontology/classes.json",), "enrich": ("ontology/enriched.json", "ontology/properties.json"),
    "interop": ("ontology.ttl", "ontology.jsonld", "domain_layer.ttl", "ontology/mappings.json", "ontology/validation.json"),
    "integrate": ("integration.json", "mappings.json", "bridge_concepts.json", "validation.json"),
}


def restricted(path):
    name = path.name.lower()
    return name.startswith(".env") or name.endswith((".pem", ".key")) or any(p.lower() == "private" for p in path.parts)


def fingerprint(path):
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size
    except OSError:
        return None


@lru_cache(maxsize=96)
def _json(path, stamp):
    if stamp is None:
        return None, "missing"
    if stamp[1] > MAX_JSON:
        return None, "not inspected (file exceeds 64 MB)"
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        # Model transcripts remain downloadable, but need not occupy the research index.
        if Path(path).parent.name == "papers" and isinstance(value, dict):
            value.pop("raw_calls", None)
        return value, "readable"
    except (OSError, UnicodeError, ValueError):
        return None, "unreadable JSON (may be mid-write)"


def load(path, default=None):
    if restricted(path):
        return default
    value, status = _json(str(path), fingerprint(path))
    return default if value is None else value


def classify(relative, kind="run"):
    name = relative.name
    if "cache" in relative.parts:
        return "execution", "Reusable cache"
    if relative.parts[0] == "papers":
        return "extract", "Per-paper extraction and evidence"
    if relative.parts[0] == "extraction_review":
        return "extract", "Malformed concepts and dependent records withheld for review"
    if relative.parts[0] == "parsed":
        return "parse", "Parsed sections and extraction windows"
    if relative.parts[0] == "normalized":
        return "normalize", "Exact concept lineage" if name == "concept_lineage.json" else "Corpus vocabulary and claims"
    if relative.parts[0] in ("figures", "report") or relative.suffix in (".png", ".pdf", ".html"):
        return "reports", "Report, figure or supporting data"
    if name.startswith("ingestion"):
        return "ingest", "Domain paper selection"
    if name == "corpus_report.md":
        return "normalize", "Corpus interpretation"
    if kind == "integration" and (relative.suffix in (".ttl", ".jsonld") or name in
            ("integration.json", "mappings.json", "bridge_concepts.json", "candidates.json", "validation.json", "integration_report.md")):
        return "integrate", "Cross-domain ontology, mappings or review"
    if name in ("ontology.ttl", "ontology.jsonld", "domain_layer.ttl", "domain_layer.jsonld", "ontology_report.md"):
        return "interop", "Ontology export and literature layer"
    if relative.parts[0] == "ontology":
        if name == "classes.json":
            return "ontology", "Class placement and hierarchy"
        if name in ("enriched.json", "properties.json", "materials_project.json", "cross_domain_candidates.json"):
            return "enrich", "Definitions, restrictions and enrichment"
        if name in ("review_issues.json", "uncertain.json"):
            return "review", "Cross-stage review findings"
        return "interop", "Mappings, facets and validation"
    if relative.suffix in (".log", ".jsonl") or name in ("run.json", "dashboard.json", "job.json"):
        return "execution", "Manifest, progress or model-call audit"
    if relative.suffix == ".csv":
        return "reports", "Metrics or sweep outcomes"
    return "other", "Unclassified artifact (retained in inventory)"


def inventory(root, kind="run", superseded=False):
    if root is None or not root.is_dir():
        return []
    root = root.resolve()
    manifest = load(root / "run.json", {})
    completed = set(manifest.get("stages", {}))
    completion_times = {}
    for stage, info in manifest.get("stages", {}).items():
        try:
            completion_times[stage] = datetime.fromisoformat(info["completed"]).timestamp()
        except (KeyError, TypeError, ValueError):
            pass
    completed |= {s for s, value in load(root / "dashboard.json", {}).get("stages", {}).items()
                  if isinstance(value, dict) and value.get("status") == "completed"}
    if kind == "integration" and load(root / "integration.json"):
        completed.add("integrate")
    rows, actual = [], set()
    try:
        candidates = list(root.rglob("*"))
    except OSError:
        return [{"path": ".", "stage": "other", "availability": "unreadable directory", "completion": "unknown"}]
    for path in candidates:
        try:
            if not path.is_file() or not path.resolve().is_relative_to(root):
                continue
            relative = path.relative_to(root)
            stamp = fingerprint(path)
            if stamp is None:
                continue
            actual.add(relative.as_posix())
            stage, purpose = classify(relative, kind)
            availability = "present"
            if restricted(relative):
                availability = "restricted (contents withheld)"
            elif path.suffix == ".json":
                _, availability = _json(str(path), stamp)
            else:
                if stamp[1] == 0:
                    availability = "empty"
                try:
                    with path.open("rb") as handle:
                        handle.read(1)
                except OSError:
                    availability = "unreadable"
            completion = "recorded complete" if stage in completed else "partial / completion not recorded"
            if stage in ("execution", "review", "other", "reports"):
                completion = "saved artifact; not a stage completion signal"
            if ".tmp" in path.name or ".partial" in path.name:
                completion = "partial / temporary file"
            stale = False
            if stage in model.STAGES and stage in completion_times:
                stale = any(completion_times.get(prior, 0) > completion_times[stage]
                            for prior in model.STAGES[:model.STAGES.index(stage)])
            rows.append({"path": relative.as_posix(), "stage": stage, "purpose": purpose,
                         "availability": availability, "completion": completion,
                         "attempt": "superseded (recorded attempt history)" if superseded else
                                    "superseded (newer upstream completion)" if stale else "selected attempt",
                         "bytes": stamp[1], "updated": datetime.fromtimestamp(stamp[0] / 1e9, ZoneInfo("America/New_York")).isoformat(timespec="seconds")})
        except OSError:
            continue
    for stage, names in REQUIRED.items():
        if stage not in completed:
            continue
        for name in names:
            if name not in actual:
                rows.append({"path": name, "stage": stage, "purpose": "Expected output of a recorded completed stage",
                             "availability": "missing", "completion": "stage recorded complete; file unavailable", "bytes": 0})
    if kind == "integration":
        for name in load(root / "integration.json", {}).get("ontology", {}).get("files", []):
            if isinstance(name, str) and Path(name).name == name and name not in actual:
                rows.append({"path": name, "stage": "integrate", "purpose": "Export named by integration manifest",
                             "availability": "missing", "completion": "manifest references an unavailable export", "bytes": 0})
    if "normalize" in completed and "normalized/concept_lineage.json" not in actual:
        rows.append({"path": "normalized/concept_lineage.json", "stage": "normalize", "purpose": "Exact normalization lineage",
                     "availability": "unavailable (not recorded by this run)", "completion": "do not infer exact merge decisions", "bytes": 0})
    if kind == "run" and not any(p.startswith("parsed/") for p in actual) and not (root / "dashboard.json").exists():
        rows.append({"path": "parsed/*.json", "stage": "parse", "purpose": "Separate parsing windows",
                     "availability": "unavailable (not recorded by this pipeline)", "completion": "paper records may contain parsing statistics", "bytes": 0})
    if kind == "run":
        selected = manifest.get("corpus", {}).get("selection", {}).get("selected", [])
        for paper in selected:
            if not isinstance(paper, dict) or not paper.get("key"):
                continue
            name = f"papers/{paper['key']}.json"
            if name not in actual:
                rows.append({"path": name, "stage": "extract", "purpose": "Selected paper awaiting a saved extraction",
                             "availability": "missing" if "extract" in completed else "not yet available",
                             "completion": "selected paper; inspect failures and progress", "bytes": 0})
    return sorted(rows, key=lambda row: (row["stage"], row["path"]))


def accessible(root, relative):
    path = model.inside(root, relative)
    if restricted(path.relative_to(root)) or not path.is_file():
        raise ValueError("This artifact is unavailable or its contents are restricted.")
    try:
        with path.open("rb") as handle:
            handle.read(1)
    except OSError:
        raise ValueError("This artifact is not currently readable.") from None
    return path
