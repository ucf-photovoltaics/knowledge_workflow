"""Matched paper comparisons preserve missing data and frozen citation provenance."""
import csv
import json

import pytest

from scripts.compare_models import compare_papers


def test_matched_papers_rank_citations_and_expose_missing_data(tmp_path):
    models = [{"sweep": name, "label": name} for name in ("a", "b")]
    found = {}
    for model in models:
        folder = tmp_path / model["sweep"]
        (folder / "papers").mkdir(parents=True)
        (folder / "run.json").write_text(json.dumps({"collection": {"name": "domain"}}))
        found[model["sweep"]] = {10: {"domains": [folder]}}
        paper = {"key": "shared", "title": "Paper <title>", "doi": "10/example",
                 "citations": 9 if model["sweep"] == "a" else 10,
                 "concepts": [{}], "relations": [{}],
                 "verification": {"relations": {"items": 1, "verified": 0}}}
        (folder / "papers" / "shared.json").write_text(json.dumps(paper))
        if model["sweep"] == "a":
            for key, count in [("unknown", None), ("highest", 20)]:
                (folder / "papers" / f"{key}.json").write_text(
                    json.dumps({"key": key, "title": key, "citations": count}))
    compare_papers(tmp_path, models, found, 10, tmp_path, 1)
    with (tmp_path / "paper_metrics.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert [r["paper_key"] for r in rows] == ["highest", "highest", "shared", "shared", "unknown", "unknown"]
    assert rows[1]["present"] == "False" and rows[1]["concepts"] == ""
    assert rows[2]["citation_conflict"] == "True"
    assert rows[2]["relations_evidence_found"] == "0.0"
    assert rows[2]["causal_evidence_found"] == ""
    report = (tmp_path / "paper_comparison.md").read_text(encoding="utf-8")
    assert "1 papers shared by all 2 models" in report
    assert "### 1. highest" in report and "### 2." not in report
    assert "<table>" in (tmp_path / "paper_comparison.html").read_text(encoding="utf-8")


def test_top_papers_must_be_positive(tmp_path):
    with pytest.raises(ValueError, match="at least 1"):
        compare_papers(tmp_path, [], {}, 10, tmp_path, 0)
