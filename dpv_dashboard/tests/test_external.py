"""Test external support for the Knowledge Workflow system.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from dpv_dashboard import model, external


def test_experiment_choices_follow_real_folders_and_sort_sizes(tmp_path):
    records = {name: {"path": str(tmp_path / "experiments" / group / name)} for name, group in
               (("unrelated-name", "pv-cost-chain-n10"), ("small", "pv-cost-chain-n2"), ("large", "pv-cost-chain-n50"))}
    assert list(external.experiments(records)) == ["experiments/pv-cost-chain-n2", "experiments/pv-cost-chain-n10", "experiments/pv-cost-chain-n50"]
    assert list(external.in_experiment(records, "experiments/pv-cost-chain-n10")) == ["unrelated-name"]
    assert external.in_experiment(records, "missing") == {}
    assert external.experiment({"path": str(tmp_path / "old-run")}) == "outputs"


def test_duplicate_run_names_in_different_experiments_are_preserved(tmp_path, monkeypatch):
    import os
    monkeypatch.setattr(model, "ROOT", tmp_path)
    parents = [tmp_path / "experiments" / group for group in ("one", "two", "three")]
    for parent in parents:
        model.write(parent / "same-run/run.json", {"id": "same-run"})
    monkeypatch.setenv("DPV_OUTPUT_DIRS", os.pathsep.join(str(path) for path in parents))
    found = external.discover()
    assert len(found) == 3
    assert {external.experiment(row) for row in found.values()} == {"experiments/one", "experiments/two", "experiments/three"}
    assert len(external.in_experiment(found, "experiments/two")) == 1


def test_pinned_run_keeps_startup_experiment(tmp_path, monkeypatch):
    monkeypatch.setattr(model, "ROOT", tmp_path)
    parent = tmp_path / "experiments/pv-cost-chain-n10"
    model.write(parent / "gemma/run.json", {"id": "gemma"})
    model.write(parent / "other/run.json", {"id": "other"})
    monkeypatch.setenv("DPV_OUTPUT_DIRS", str(parent))
    monkeypatch.setenv("DPV_DEFAULT_OUTPUT", "gemma")
    records = external.discover()
    first = next(iter(records.values()))
    assert next(iter(records)) == "gemma"
    assert external.experiment(first) == "experiments/pv-cost-chain-n10"


def test_linked_selectors_clear_old_run_during_experiment_switch(tmp_path):
    import ast
    from contextlib import nullcontext
    from pathlib import Path
    from types import SimpleNamespace
    from dpv_dashboard import presentation
    records = {"gemma": {"path": str(tmp_path / "experiments/pv-cost-chain-n10/gemma")},
               "other": {"path": str(tmp_path / "experiments/pv-cost-chain-n2/other")}}
    state = {"experiment": "", "run": ""}
    updates = {}
    namespace = {"external": external, "Path": Path, "presentation": presentation,
                 "external_choices": SimpleNamespace(get=lambda: records),
                 "experiment_folders": SimpleNamespace(get=lambda: ()),
                 "input": SimpleNamespace(experiment=lambda: state["experiment"], existing=lambda: state["run"]),
                 "model": SimpleNamespace(viewer=lambda: True), "reactive": SimpleNamespace(isolate=nullcontext),
                 "ui": SimpleNamespace(update_select=lambda name, **kwargs: updates.update({name: kwargs}))}
    tree = ast.parse((Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in {"experiment_choices", "selected_records", "run_choices", "monitored"}:
            node.decorator_list = []
            exec(compile(ast.Module(body=[node], type_ignores=[]), "app.py", "exec"), namespace)
    namespace["experiment_choices"]()
    assert updates["experiment"]["selected"] == "experiments/pv-cost-chain-n10"
    state.update(experiment="experiments/pv-cost-chain-n10", run="gemma")
    assert namespace["monitored"]()["path"] == records["gemma"]["path"]
    state["experiment"] = "experiments/pv-cost-chain-n2"
    assert namespace["monitored"]() is None  # browser still holds the old run value
    namespace["run_choices"]()
    assert list(updates["existing"]["choices"]) == ["other"]
    assert updates["existing"]["selected"] == "other"
    state["run"] = "other"
    assert namespace["monitored"]() == records["other"]


def test_empty_experiment_folders_remain_selectable(tmp_path, monkeypatch):
    monkeypatch.setattr(model, "ROOT", tmp_path)
    empty = tmp_path / "outputs/experiments/pv-cost-chain-n1"
    empty.mkdir(parents=True)
    model.write(tmp_path / "outputs/experiments/pv-cost-chain-n10/gemma/run.json", {"id": "gemma"})
    monkeypatch.setenv("DPV_OUTPUT_DIRS", str(tmp_path / "outputs/experiments/*"))
    records = external.discover()
    scopes = external.experiments(records, external.experiment_folders())
    assert list(scopes) == ["experiments/pv-cost-chain-n1", "experiments/pv-cost-chain-n10"]
    assert external.in_experiment(records, "experiments/pv-cost-chain-n1") == {}


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
