"""Scoped citations and crop fallbacks must not invent evidence or alter PDFs.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import hashlib
from pathlib import Path
import pymupdf
import pytest
from dpv_dashboard import media, model, research, catalog, highlight, external


@pytest.fixture
def source(tmp_path):
    pdf = tmp_path / "source.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=800)
        page.draw_rect(pymupdf.Rect(50, 100, 350, 300))
        page.insert_text((50, 330), "Figure 1. Solar cell efficiency.")
        page.insert_text((50, 400), "Solar cell efficiency increases.")
        doc.save(pdf)
    model.write(tmp_path / "papers/P1.json", {"key": "P1", "title": "Paper one", "pdf": str(pdf), "cache_hit": True,
        "concepts": [{"id": "c1", "label": "Solar cell"}],
        "relations": [{"s": "c1", "p": "is_a", "o": "c1", "evidence": "Solar cell efficiency increases.", "verified": True}],
        "figures": [{"id": "F1", "label": "Figure 1", "page": 1, "caption": "Solar cell efficiency.", "bbox": [50, 100, 350, 300]},
                    {"id": "F2", "label": "Figure 2", "page": 1, "caption": "Unfindable caption"}]})
    model.write(tmp_path / "normalized/concepts.json", [{"id": "k1", "label": "Solar cell", "papers": ["P1"]}])
    return research.index(tmp_path), pdf


def test_inline_citations_are_scoped_escaped_and_open_exact_claim(source):
    data, pdf = source
    row = {**data.claims("P1")[0], "root": str(data.root), "canonical_id": "k1"}
    html = str(media.chat_answer('<script>bad</script> [S1] [S99] https://example.org/source', [row]))
    assert "&lt;script&gt;" in html and '<script>' not in html
    assert 'data-paper="P1"' in html and 'data-claim="relation:1"' in html
    assert '[S99] (source unavailable)' in html
    assert 'href="https://example.org/source"' in html
    detail = str(media.paper_view(data, "P1", claim="relation:1"))
    assert "Cited evidence" in detail and "does not verify" in detail and "cached" in detail


def test_crop_dimensions_full_paper_collapsed_and_source_unchanged(source):
    data, pdf = source
    before = hashlib.sha256(pdf.read_bytes()).hexdigest()
    spec = highlight.focus(data, "P1", figure="F1")
    image = pymupdf.Pixmap(media.figure_image(pdf, catalog.fingerprint(pdf), spec))
    assert (image.width, image.height) == (600, 400)
    html = str(media.paper_view(data, "P1", figure="F1"))
    assert '?crop=1' in html and "Expand full paper at source page" in html
    assert '<details open' not in html and 'alt="Source page' not in html
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == before


def test_caption_missing_never_falls_back_to_a_full_page_crop(source):
    data, pdf = source
    figure = data.papers['P1']['figures'][1]
    url, note = media.figure_preview(data, 'P1', figure, pdf)
    assert url is None and "unavailable" in note
    with pytest.raises(ValueError, match="boundary unavailable"):
        media.figure_image(pdf, catalog.fingerprint(pdf), highlight.focus(data, 'P1', figure='F2'))


def test_explicit_references_and_safe_external_schemes(source):
    data, _ = source
    html = str(media.reference_text(data, 'c1 F1 k1 https://example.org/term', 'P1'))
    assert html.count('data-paper="P1"') == 3 and 'data-figure="F1"' in html
    assert 'href="https://example.org/term"' in html
    assert 'href=' not in str(media.external_reference('bad', 'javascript:alert(1)'))
    assert 'href=' not in str(media.external_reference('bad', 'https://user:pass@example.org'))
    assert 'data-figure=' not in str(media.reference_text(data, 'F1'))


def test_integration_progress_refers_to_source_domains(tmp_path):
    state = external.states(tmp_path, 'integration')
    assert state['integrate'] == 'completed'
    assert state['extract'] == 'see contributing domains'


def test_crop_rotates_recorded_coordinates_and_keeps_both_panels(tmp_path):
    pdf = tmp_path / 'rotated.pdf'
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=800)
        page.draw_rect(pymupdf.Rect(50, 100, 180, 250))
        page.draw_rect(pymupdf.Rect(220, 100, 350, 250))
        page.set_rotation(90)
        doc.save(pdf)
    spec = ('', (), (), 1, 'Figure 1', '', (50, 100, 350, 250))
    pix = pymupdf.Pixmap(media.figure_image(pdf, catalog.fingerprint(pdf), spec))
    assert (pix.width, pix.height) == (300, 600)
    assert min(pix.samples) < 100


def test_report_references_preserve_markdown_and_do_not_nest_links(source):
    data, _ = source
    html = str(media.linked_markdown(data, '## Evidence\n\nc1 F1 [source](https://example.org/paper)\n\n10.1000/example'))
    assert '<h2>' in html and 'data-figure=' not in html  # no paper scope for a bare F1
    assert html.count('href="https://example.org/paper"') == 1
    assert 'href="https://doi.org/10.1000/example"' in html
