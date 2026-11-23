"""Integrated results expose upstream domain data without changing global scope."""
import ast
from pathlib import Path
from types import SimpleNamespace
from shiny import ui
from dpv_dashboard import presentation


def callback(name, namespace):
    source = Path(__file__).parents[1] / "pages/stage.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    function.decorator_list = []
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[name]


def test_domain_selector_bootstraps_without_reading_its_unbound_input(tmp_path):
    domains = [tmp_path / "tea-run", tmp_path / "reliability-run"]
    # No input object exists until this UI is rendered. Reading it would deadlock startup.
    html = str(callback("domain_scope", {"sources": lambda: domains, "ui": ui, "presentation": presentation})())
    assert "Inspect contributing domain" in html and "domain_source" in html
    assert "integrated run stays selected" in html and "tea-run" in html


def test_domain_handoff_accepts_only_contributing_roots(tmp_path):
    integration = tmp_path / "integrated"
    domains = [tmp_path / "tea", tmp_path / "reliability"]
    selected = str(domains[1])
    namespace = {"sources": lambda: domains, "input": SimpleNamespace(domain_source=lambda: selected),
                 "original_context": SimpleNamespace(folder=lambda stage: integration)}
    resolve = callback("source_folder", namespace)
    assert resolve("extract") == domains[1]
    selected = str(tmp_path / "private")
    assert resolve("extract") == domains[0]
    assert namespace["original_context"].folder("extract") == integration
