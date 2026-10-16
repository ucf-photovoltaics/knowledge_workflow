"""Test external support for the Knowledge Workflow system.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from dpv_dashboard import model, external


def test_discovery_ignores_dashboard_and_finds_original_outputs(tmp_path):
    model.write(tmp_path / "reliability/run.json", {"stages": {"extract": {}}})
    model.write(tmp_path / "dashboard/run.json", {"stages": {}})
    model.write(tmp_path / "integration-old/integration.json", {"stats": {}})
    (tmp_path / "sweep-old").mkdir()
    (tmp_path / "sweep-old/summary.csv").write_text("run_id,status\n")
    found = external.discover(tmp_path)
    assert set(found) == {"reliability", "integration-old", "sweep-old"}
    assert found["reliability"]["kind"] == "run"


def test_external_status_and_available_intermediates(tmp_path):
    model.write(tmp_path / "run.json", {"stages": {"extract": {}, "normalize": {}, "ontology": {}}})
    model.write(tmp_path / "papers/paper.json", {"parse_stats": {"n_sections": 5, "n_figures": 2}})
    (tmp_path / "run.log").write_text("14:00:00 [enrich] definitions 7/30\n")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    states = external.states(tmp_path, "run")
    assert states["extract"] == "completed"
    assert states["parse"] == "completed"
    assert states["enrich"] == "active (recent log)"
    assert external.files(tmp_path, "ingest") == [tmp_path / "run.json"]
    assert external.files(tmp_path, "parse") == [tmp_path / "papers/paper.json"]
    assert "5 sections" in external.summary(tmp_path, "parse", "run")
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_integration_and_sweep_artifacts(tmp_path):
    model.write(tmp_path / "integration.json", {"stats": {}})
    (tmp_path / "tea_reliability_merged.ttl").write_text("# ontology")
    (tmp_path / "report").mkdir()
    (tmp_path / "report/report.html").write_text("report")
    assert tmp_path / "tea_reliability_merged.ttl" in external.files(tmp_path, "integrate", "integration")
    assert tmp_path / "report/report.html" in external.files(tmp_path, "reports", "sweep")
    assert external.files(tmp_path, "extract", "integration") == []
