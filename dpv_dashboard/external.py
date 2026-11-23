"""Read-only discovery of existing pipeline outputs; never adopts process ownership.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import glob
import os
import re
import time
from pathlib import Path
from dpv_dashboard import model

_KINDS = {}  # folder -> run / integration / sweep; a saved output keeps its kind, so it is read once, not every poll


def discover(root=None):
    """Runs in outputs/ plus any folders listed in DPV_OUTPUT_DIRS (e.g. a mounted Cloud Storage bucket). An entry
    may be a pattern: /app/hpc-outputs/experiments/* reads every experiment folder of the bucket layout.
    DPV_DEFAULT_OUTPUT names the folder listed first, which the dashboard opens with (else the newest)."""
    if root is None:
        entries = [p.strip() for p in os.environ.get("DPV_OUTPUT_DIRS", "").split(os.pathsep) if p.strip()]
        extra = [Path(m) for p in entries for m in (sorted(glob.glob(p)) if any(c in p for c in "*?[") else [p])]
        found = {}
        for folder in [model.ROOT / "outputs", *extra]:
            for identifier, record in discover(folder).items():
                if identifier in found and found[identifier]["path"] != record["path"]:
                    prior = found.pop(identifier)
                    found[prior["path"]] = prior
                    identifier = record["path"]
                elif any(Path(value["path"]).name == identifier and value["path"] != record["path"] for value in found.values()):
                    identifier = record["path"]
                found[identifier] = record
        found = dict(sorted(found.items(), key=lambda pair: pair[1]["modified"], reverse=True))
        pinned = os.environ.get("DPV_DEFAULT_OUTPUT", "").strip()
        return {pinned: found[pinned], **found} if pinned in found else found
    root = Path(root).resolve()
    found = {}
    if not root.is_dir():
        return found
    for folder in root.iterdir():
        if not folder.is_dir() or folder.name in ("cache", "dashboard") or not folder.resolve().is_relative_to(root):
            continue
        kind = _KINDS.get(str(folder))
        if kind is None:
            kind = next((kind for name, kind in (("run.json", "run"), ("integration.json", "integration"))
                         if model.read(folder / name)), None)
            if not kind and folder.name.startswith("sweep-") and (folder / "summary.csv").is_file():
                kind = "sweep"
        if kind:
            _KINDS[str(folder)] = kind
            found[folder.name] = {"path": str(folder), "kind": kind, "modified": folder.stat().st_mtime}
    return dict(sorted(found.items(), key=lambda pair: pair[1]["modified"], reverse=True))


def experiment(record):
    """Use the actual enclosing experiment directory, never infer it from a run name."""
    parent = Path(record["path"]).parent
    return "experiments/" + parent.name if parent.parent.name == "experiments" else "outputs"


def experiment_folders():
    """List configured experiment folders, including those without completed runs."""
    patterns = [str(model.ROOT / "outputs/experiments/*"),
                *[value.strip() for value in os.environ.get("DPV_OUTPUT_DIRS", "").split(os.pathsep) if value.strip()]]
    return tuple(sorted({Path(path) for pattern in patterns for path in glob.glob(pattern)
                         if Path(path).is_dir() and Path(path).parent.name == "experiments"}))


def experiments(records, folders=()):
    scopes = {experiment(record) for record in records.values()} | {"experiments/" + folder.name for folder in folders}
    ordered = sorted(scopes, key=lambda value: [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)])
    return {scope: scope.removeprefix("experiments/") if scope != "outputs" else "Other saved outputs" for scope in ordered}


def in_experiment(records, scope):
    return {key: record for key, record in records.items() if experiment(record) == scope}


def files(folder, stage, kind="run"):
    patterns = model.ARTIFACTS[stage]
    if stage == "ingest":
        patterns = ("run.json",)
    elif stage == "parse":
        patterns = ("papers/*.json", "compute_per_paper.csv")
    elif stage == "reports":
        patterns = ("figures/**/*.html", "figures/**/*.md", "figures/**/*.csv", "figures/**/*.png", "figures/**/*.pdf",
                    "report/**/*", "*report.md", "summary.csv", "compute*.csv")
    if kind != "run" and stage not in ("integrate", "reports"):
        return []
    if kind != "integration" and stage == "integrate":
        return []
    return sorted({p for pattern in patterns for p in folder.glob(pattern)
                   if p.is_file() and p.resolve().is_relative_to(folder.resolve())})


def log(folder):
    path = folder / "run.log"
    if not path.is_file():
        candidates = sorted(folder.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        path = candidates[0] if candidates else None
    if not path:
        return "No log file is available in this output folder."
    with path.open("rb") as handle:
        bom = handle.read(2)
        offset = max(0, path.stat().st_size - 24000)
        if bom in (b"\xff\xfe", b"\xfe\xff"):
            offset -= offset % 2
        handle.seek(offset)
        data = handle.read()
    encoding = ("utf-16-le" if bom == b"\xff\xfe" else "utf-16-be") if bom in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    return data.decode(encoding, errors="replace")


def states(folder, kind):
    manifest = model.read(folder / "run.json", {}) if kind == "run" else {}
    result = {s: "waiting" for s in model.STAGES}
    for stage in manifest.get("stages", {}):
        if stage in result:
            result[stage] = "completed"
    if "extract" in manifest.get("stages", {}):
        result.update(ingest="completed", parse="completed")
    else:
        result.update(ingest="not separately recorded", parse="not separately recorded")
    for error in manifest.get("errors", []):
        stage = error.get("stage")
        if stage in result and result[stage] != "completed":
            result[stage] = "failed"
    path = folder / "run.log"
    if path.is_file() and time.time() - path.stat().st_mtime < 180:
        observed = re.findall(r"\[(extract|normalize|ontology|enrich|interop|integrate)\]", log(folder))
        if observed and result.get(observed[-1]) != "completed":
            result[observed[-1]] = "active (recent log)"
    if kind == "integration":
        result["integrate"] = "completed"
        for stage in model.STAGES:
            if stage not in ("integrate", "reports"):
                result[stage] = "see contributing domains"
    if files(folder, "reports", kind):
        result["reports"] = "outputs available"
    return result


def summary(folder, stage, kind):
    if stage == "ingest":
        corpus = model.read(folder / "run.json", {}).get("corpus", {})
        selection = corpus.get("selection", {})
        return (f"This existing run selected {corpus.get('items', len(selection.get('selected', [])))} papers; "
                f"{corpus.get('processed', 0)} were processed and {len(corpus.get('failed', []))} failed. "
                "Selection metadata is in run.json. This run is monitored read-only.")
    if stage == "parse":
        records = [model.read(p, {}) for p in folder.glob("papers/*.json")]
        return (f"Saved paper records contain parsing statistics for {len(records)} papers: "
                f"{sum(p.get('parse_stats', {}).get('n_sections', 0) for p in records)} sections and "
                f"{sum(p.get('parse_stats', {}).get('n_figures', 0) for p in records)} figures. "
                "This pipeline version does not save separate parsing windows; the dashboard shows the available paper records.")
    if kind == "sweep":
        return "This existing sweep is monitored read-only. Its saved summary, reports and figures are available below; select individual domain runs to inspect their intermediate outputs."
    from dpv_dashboard.inspect import summary as standard
    return standard(folder, stage)
