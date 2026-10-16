"""Stage controls and figure explanations remain display-only.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import pytest
from html import unescape
from dpv_dashboard import model, presentation


def test_all_stage_controls_are_named_native_buttons():
    for number, stage in enumerate(model.STAGES, 1):
        html = str(presentation.stage_step(stage, number, "waiting"))
        assert '<button' in html and 'type="button"' in html
        assert f'data-stage="{stage}"' in html
        assert f'Open {presentation.STAGES[stage]}' in unescape(html)
        assert 'Status: Waiting' in html
    with pytest.raises(ValueError):
        presentation.stage_step("other", 1, "waiting")


def test_growth_explanation_states_order_variability_not_confidence():
    html = str(presentation.growth_note())
    assert "5th–95th percentile" in html and "middle 90%" in html
    assert "same papers" in html and "same final total" in html
    assert "not uncertainty about concept correctness" in html
    assert "does not prove order has no effect" in html


def test_report_preview_explains_only_growth_without_altering_source():
    other = '<figure><figcaption>Concept support</figcaption><p>concept_support.csv</p></figure>'
    growth = '<figure><figcaption>Original 200-order caption</figcaption><p>so a line inside the band means the order of papers does not matter.</p><p>concept_growth.csv</p></figure>'
    original = growth + other
    rendered = presentation.report_html(original)
    assert "Original 200-order caption" in rendered
    assert "How to read Concept growth" in rendered
    assert "means the order of papers does not matter" not in rendered
    assert other in rendered
    assert original == growth + other
