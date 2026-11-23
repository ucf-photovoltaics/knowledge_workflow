"""Hidden pages must not read the remote output mount during graph startup."""
import ast
from pathlib import Path
from types import SimpleNamespace
import pytest


@pytest.mark.parametrize("filename,names", [
    ("stage.py", {"baselines", "poll_artifacts", "choices"}),
    ("inventory.py", {"poll"}),
    ("research.py", {"poll"}),
    ("exploration.py", {"poll", "request_graph"}),
])
def test_inactive_pages_do_not_poll(filename, names):
    source = Path(__file__).parents[1] / "pages" / filename
    tree = ast.parse(source.read_text(encoding="utf-8"))
    callbacks = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name in names]
    assert callbacks
    for callback in callbacks:
        callback.decorator_list = []
        # A hidden-page callback must return without reading any other context or state.
        namespace = {"context": SimpleNamespace(active=lambda page: False), "stage": "integrate"}
        exec(compile(ast.Module(body=[callback], type_ignores=[]), str(source), "exec"), namespace)
        assert namespace[callback.name]() is None
