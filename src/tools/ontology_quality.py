"""Read-only aftermarket assessment of exported ontologies.

Run independently with python -m src.tools.ontology_quality INPUT.ttl.
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from uuid import uuid4

import rdflib
from rdflib.namespace import OWL, RDF, RDFS

from src.tools.progress import redact


def _execute(command, folder, name, timeout):
    start = time.monotonic()
    result = {"command": command, "status": "error"}
    try:
        proc = subprocess.run(command, cwd=folder, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8",
                                   "JAVA_TOOL_OPTIONS": os.environ.get("JAVA_TOOL_OPTIONS", "") + " -Dfile.encoding=UTF-8"})
        result.update(status="completed" if proc.returncode == 0 else "error", returncode=proc.returncode)
        output = proc.stdout + "\n" + proc.stderr
    except subprocess.TimeoutExpired:
        result["status"], output = "timeout", f"Exceeded {timeout} seconds"
    except OSError as exc:
        result["status"], output = "unavailable", str(exc)
    (folder / f"{name}.log").write_text(redact(output), encoding="utf-8")
    return {**result, "seconds": round(time.monotonic() - start, 3), "log": f"{name}.log"}


def _robot():
    tools = Path(__file__).resolve().parents[2] / "outputs" / "quality-tools"
    jar = os.environ.get("ROBOT_JAR")
    if not jar and not shutil.which("robot") and (tools / "robot.jar").is_file():
        jar = str(tools / "robot.jar")
    if jar:
        java = os.environ.get("JAVA_EXE") or shutil.which("java")
        if not java:
            java = next((str(p) for p in sorted(tools.glob("*/bin/java.exe"))), "java")
        return [java, "-jar", str(Path(jar).resolve())]
    executable = shutil.which("robot")
    return [executable] if executable else None


def assess(source, output=None, *, imports=None, questions=None, domain_prefixes=(), timeout=600, base_iri=None,
           search_term=None):
    """Assess a local Turtle artifact without modifying it; findings never discard it.

    imports maps ontology IRIs to local Turtle files. Unresolved imports are reported
    and prevent ROBOT checks rather than silently reasoning over an incomplete graph.
    """
    source = Path(source).resolve()
    if not source.is_file():
        raise ValueError(f"Ontology file does not exist: {source}")
    if timeout <= 0:
        raise ValueError("Quality-check timeout must be positive")
    if questions and not Path(questions).is_file():
        raise ValueError(f"Competency question file does not exist: {questions}")
    if questions and not domain_prefixes:
        raise ValueError("OntoCheck requires domain_prefixes with competency questions")
    root = Path(output).resolve() if output else source.parent / "quality" / source.stem
    root.mkdir(parents=True, exist_ok=True)
    # Each assessment gets its own folder so stale tool output cannot mask failures.
    folder = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8])
    folder.mkdir()
    summary = {"source": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "created": datetime.now(timezone.utc).isoformat(), "directory": str(folder),
               "checks": {}, "imports": [], "scope": "exported axioms and explicitly supplied local imports"}
    checks = summary["checks"]
    graph, pending, seen = rdflib.Graph(), [source], set()
    mapping = {str(k): Path(v).resolve() for k, v in (imports or {}).items()}
    unresolved = set()
    try:
        while pending:
            path = pending.pop()
            if path in seen:
                continue
            seen.add(path)
            part = rdflib.Graph().parse(path, format="turtle")
            summary["imports"].append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            for iri in part.objects(None, OWL.imports):
                if str(iri) in mapping:
                    pending.append(mapping[str(iri)])
                else:
                    unresolved.add(str(iri))
            for triple in part:
                graph.add(triple)
        checks["parse"] = {"status": "passed", "triples": len(graph)}
    except Exception as exc:
        checks["parse"] = {"status": "error", "message": redact(str(exc))}
    summary["unresolved_imports"] = sorted(unresolved)
    if checks["parse"]["status"] == "passed":
        graph.remove((None, OWL.imports, None))
        snapshot = folder / "assessment.ttl"
        graph.serialize(snapshot, format="turtle")
        summary["assessment_sha256"] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        robot = _robot()
        if robot and not unresolved:
            summary["robot_version"] = _execute(robot + ["--version"], folder, "robot-version", min(timeout, 30))
            summary["robot_version"]["value"] = (folder / "robot-version.log").read_text(encoding="utf-8").strip()
            profile = _execute(robot + ["validate-profile", "--profile", "DL", "--input", str(snapshot),
                                       "--output", str(folder / "owl-profile.txt")], folder, "owl-profile", timeout)
            checks["owl_profile"] = profile
            if profile["status"] == "completed":
                checks["hermit"] = _execute(robot + ["reason", "--reasoner", "hermit", "--input", str(snapshot),
                                                     "--output", str(folder / "reasoned.owl")], folder, "hermit", timeout)
            else:
                checks["hermit"] = {"status": "skipped", "message": "OWL 2 DL profile check did not pass"}
            resources = Path(__file__).resolve().parents[1] / "resources" / "quality"
            profile_path = folder / "robot-profile.tsv"
            profile_path.write_text((resources / "robot-profile.tsv").read_text(encoding="utf-8").strip() +
                                    "\nWARN\t" + (resources / "missing-definition.rq").as_uri() + "\n", encoding="utf-8")
            command = robot + ["report", "--input", str(snapshot), "--fail-on", "none",
                               "--profile", str(profile_path),
                               "--output", str(folder / "robot-report.tsv")]
            if base_iri:
                command += ["--base-iri", base_iri]
            checks["robot_report"] = _execute(command, folder, "robot-report", timeout)
            if checks["robot_report"]["status"] == "completed" and (folder / "robot-report.tsv").exists():
                with (folder / "robot-report.tsv").open(encoding="utf-8-sig") as stream:
                    checks["robot_report"]["findings"] = list(csv.DictReader(stream, delimiter="\t"))
            elif checks["robot_report"]["status"] == "completed":
                checks["robot_report"].update(status="error", message="ROBOT did not write its report")
        else:
            for name in ("owl_profile", "hermit", "robot_report"):
                checks[name] = {"status": "unavailable" if not robot else "skipped",
                                "message": "Install ROBOT/Java or set ROBOT_JAR" if not robot else "Unresolved local imports"}
        try:
            summary["ontocheck_version"] = metadata.version("OntoCheck")
        except metadata.PackageNotFoundError:
            summary["ontocheck_version"] = None
        if summary["ontocheck_version"]:
            labels = sorted(str(label) for cls in graph.subjects(RDF.type, OWL.Class)
                            for label in graph.objects(cls, RDFS.label)
                            if not base_iri or str(cls).startswith(base_iri))
            search_term = search_term or (labels[0] if labels else source.stem)
            worker = ("import json; from pathlib import Path; "
                      "from ontocheck.run_assessment import METRIC_DISPATCHER; "
                      "Path('ontocheck-requested.json').write_text(json.dumps(list(METRIC_DISPATCHER))); "
                      "from ontocheck.cli import main; main()")
            command = [sys.executable, "-c", worker, str(snapshot),
                       "--metrics", "all", "--log-file", str(folder / "ontocheck-metrics.log"),
                       "--csv-file", str(folder / "ontocheck.csv"), "--search-term", search_term]
            checks["ontocheck"] = _execute(command, folder, "ontocheck", timeout)
            checks["ontocheck"]["metrics"] = "all"
            checks["ontocheck"]["search_term"] = search_term
            if (folder / "ontocheck.csv").exists():
                with (folder / "ontocheck.csv").open(encoding="utf-8-sig") as stream:
                    checks["ontocheck"]["results"] = list(csv.DictReader(stream))
                rows = checks["ontocheck"]["results"]
                checks["ontocheck"]["metric_count"] = len(rows)
                requested = folder / "ontocheck-requested.json"
                if requested.exists():
                    expected = json.loads(requested.read_text(encoding="utf-8"))
                    checks["ontocheck"]["requested_metrics"] = expected
                    checks["ontocheck"]["missing_metrics"] = sorted(set(expected) - {r.get("Metric") for r in rows})
                    if checks["ontocheck"]["missing_metrics"]:
                        checks["ontocheck"].update(status="error", message="Some requested metrics have no result")
                if any(row.get("Status") != "Success" for row in rows) or not rows:
                    checks["ontocheck"].update(status="error", message="One or more metrics failed or were skipped; see results")
            elif checks["ontocheck"]["status"] == "completed":
                checks["ontocheck"].update(status="error", message="OntoCheck did not write its CSV")
        else:
            checks["ontocheck"] = {"status": "unavailable", "metrics": "all", "message": "Install requirements-quality.txt"}
        checks["competency_questions"] = {"status": checks["ontocheck"]["status"] if questions else "not_configured",
                                           "file": str(Path(questions).resolve()) if questions else None}
        if questions and summary["ontocheck_version"]:
            command = [sys.executable, "-c", "from ontocheck.cli import main; main()", str(snapshot),
                       "--questions", str(Path(questions).resolve()), "--domain-prefixes", *domain_prefixes,
                       "--log-file", str(folder / "competency-questions-metrics.log"),
                       "--csv-file", str(folder / "competency-questions.csv")]
            checks["competency_questions"] = _execute(command, folder, "competency-questions", timeout)
            if (folder / "competency-questions.csv").exists():
                with (folder / "competency-questions.csv").open(encoding="utf-8-sig") as stream:
                    checks["competency_questions"]["results"] = list(csv.DictReader(stream))
            elif checks["competency_questions"]["status"] == "completed":
                checks["competency_questions"].update(status="error", message="No competency-question results were written")
    statuses = [c["status"] for c in checks.values()]
    summary["status"] = "needs_review" if any(s in ("error", "timeout") for s in statuses) else (
        "incomplete" if any(s in ("unavailable", "skipped") for s in statuses) or unresolved else "completed")
    if checks.get("robot_report", {}).get("findings"):
        summary["status"] = "needs_review"
    summary["note"] = "Completed metrics are measurements, not proof of scientific correctness. See detailed reports."
    payload = json.dumps(summary, indent=2, ensure_ascii=False)
    (folder / "summary.json").write_text(payload, encoding="utf-8")
    (root / "summary.json").write_text(payload, encoding="utf-8")
    lines = ["# Ontology quality assessment", "", f"Source: `{source}`", "", f"Status: **{summary['status']}**", "",
             *[f"- {name}: {check['status']}" for name, check in checks.items()], "",
             f"Detailed reports: `{folder}`", "", summary["note"], "",
             "Scope: exported axioms and resolved local imports. MIREOT ancestor extracts may omit external constraints.",
             "OntoCheck accessibility metrics may contact public URLs declared in the ontology."]
    (root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--imports", type=Path, help="JSON map from ontology IRI to local Turtle path")
    parser.add_argument("--questions", type=Path)
    parser.add_argument("--domain-prefixes", nargs="*", default=[])
    parser.add_argument("--base-iri")
    parser.add_argument("--search-term", help="OntoCheck searchClass probe (default: first sorted local class label)")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    imports = json.loads(args.imports.read_text(encoding="utf-8")) if args.imports else None
    result = assess(args.input, args.output, imports=imports, questions=args.questions,
                    domain_prefixes=args.domain_prefixes, timeout=args.timeout, base_iri=args.base_iri,
                    search_term=args.search_term)
    print(f"Ontology quality: {result['status']}; reports in {result['directory']}")


if __name__ == "__main__":
    main()
