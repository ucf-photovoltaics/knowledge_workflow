# -*- coding: utf-8 -*-
"""
publish.py — push a finished ontology + JSON-LD to GitHub, then load into GraphDB.

Final step of a run. Only publishes artifacts that PASS structural_metrics.

Usage:
    python scripts/publish.py outputs/gaas/gaas_onto.ttl outputs/gaas/gaas_instances.jsonld

Env:
    GRAPHDB_URL        e.g. http://localhost:7200
    GRAPHDB_REPO       target repository / sandbox id
    GIT_REMOTE         (optional) remote name, default "origin"
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from kw.validate import evaluate


def git_push(paths: list[str]) -> None:
    """Commit the artifacts and push to the configured remote."""
    remote = os.getenv("GIT_REMOTE", "origin")
    subprocess.run(["git", "add", *paths], check=True)
    subprocess.run(["git", "commit", "-m", f"Add ontology artifacts: {', '.join(paths)}"], check=True)
    subprocess.run(["git", "push", remote, "HEAD"], check=True)


def graphdb_load(ttl_path: str) -> None:
    """Load the .ttl into a GraphDB repository via its REST API.

    TODO: POST the file to {GRAPHDB_URL}/repositories/{repo}/statements with
    Content-Type: text/turtle. Use requests; handle auth if the sandbox needs it.
    """
    url = os.getenv("GRAPHDB_URL", "http://localhost:7200")
    repo = os.getenv("GRAPHDB_REPO", "sandbox")
    endpoint = f"{url}/repositories/{repo}/statements"
    print(f"TODO: POST {ttl_path} -> {endpoint} (text/turtle)")


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: python scripts/publish.py <ontology.ttl> <instances.jsonld>")
        sys.exit(1)
    ttl, jsonld = sys.argv[1], sys.argv[2]

    # Gate: never publish an ontology that fails structural evaluation.
    rep = evaluate(ttl)
    if not rep["passed"]:
        print("BLOCKED — ontology failed structural metrics:")
        for k, v in rep.items():
            print(f"  {k}: {v}")
        sys.exit(2)

    git_push([ttl, jsonld])
    graphdb_load(ttl)
    print("Published.")


if __name__ == "__main__":
    main()
