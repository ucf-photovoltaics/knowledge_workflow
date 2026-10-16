"""Display compaction must preserve source identity through filtering and sorting.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import pandas as pd
from pathlib import Path
from types import SimpleNamespace
from dpv_dashboard import presentation, record_view


def test_compact_selection_preserves_hidden_identity_and_raw_status():
    source = pd.DataFrame([{"canonical_id": "k1", "label": "First", "source_run": "one", "verification": "verified"},
                           {"canonical_id": "k1", "label": "Second", "source_run": "two", "verification": "unverified"}])
    shown = presentation.grid(source, compact=True).data
    assert "Canonical concept ID" not in shown and "Source run" not in shown
    class Renderer:
        def data(self): return shown
        def data_view(self, selected): return shown.iloc[[1, 0]]
    restored = presentation.selected(Renderer())
    assert restored["source_run"].tolist() == ["two", "one"]
    assert restored["verification"].tolist() == ["unverified", "verified"]
    assert source.iloc[0]["verification"] == "verified"


def test_rich_display_can_restore_plain_record_without_html_tags():
    source = pd.DataFrame([{"canonical_id": "k1", "label": "Solar cell"}])
    decorated = pd.DataFrame([{"canonical_id": "k1", "label": "<button>Solar cell</button>"}])
    decorated.attrs["dpv_raw_records"] = source
    shown = presentation.grid(decorated, compact=True).data
    class Renderer:
        def data(self): return shown
        def data_view(self, selected): return shown.iloc[[0]]
    assert presentation.selected(Renderer()).iloc[0]["label"] == "Solar cell"


def test_inspector_escapes_evidence_and_explains_missing_provenance():
    data = SimpleNamespace(root=Path("fixture-run"), concepts={}, papers={}, by_canonical={}, label=lambda x: x)
    output = str(record_view.inspector(data, {"label": "<script>bad</script>", "quote": "<img src=x>", "lineage_status": "reconstructed"}))
    assert "&lt;script&gt;" in output and "&lt;img src=x&gt;" in output
    assert "Reconstructed link" in output and "does not independently validate" in output
    assert "Not recorded" in output


def test_review_summary_distinguishes_repeated_findings_from_concepts():
    output = str(record_view.priorities([{"id": "k1", "flags": '["unsupported_definition"]'},
                                        {"id": "k1", "flags": ["unsupported_definition"]}]))
    assert "2 saved finding records" in output and "1 identified concepts" in output
    assert "Definition needs supporting evidence: 2" in output


def test_run_comparison_uses_counts_and_literal_labels_without_equivalence():
    current = SimpleNamespace(root=Path("current"), progress=lambda stage: ("completed", {"claims": 12, "unknown": "not recorded"}),
                              concepts={"k1": {"label": "Cell"}, "k2": {"label": "Layer"}})
    baseline = SimpleNamespace(root=Path("baseline"), progress=lambda stage: ("completed", {"claims": 10, "unknown": 2}),
                               concepts={"k1": {"label": "Cell"}, "k3": {"label": "Contact"}})
    output = str(record_view.compare(current, baseline, "normalize"))
    assert "10 → 12 (+2)" in output
    assert "1 added; 1 no longer present; 1 shared" in output
    assert "do not establish new concepts" in output
