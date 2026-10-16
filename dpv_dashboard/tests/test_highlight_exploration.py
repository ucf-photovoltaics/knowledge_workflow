"""Disposable PDF boxes, provenance scope and offline exploration behavior.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import hashlib
import json
from pathlib import Path
import pymupdf
import pytest
from dpv_dashboard import catalog, exploration, highlight, media, model, research


@pytest.fixture
def focused_run(tmp_path):
    path = tmp_path / "source.pdf"
    with pymupdf.open() as image_doc:
        p = image_doc.new_page(width=200, height=100)
        p.draw_rect(pymupdf.Rect(10, 10, 190, 90), color=(0, 0, 1), fill=(.8, .9, 1))
        image = p.get_pixmap().tobytes("png")
    with pymupdf.open() as doc:
        doc.new_page().insert_text((50, 50), "Unrelated first page")
        p = doc.new_page()
        p.insert_text((50, 50), "Solar cell efficiency increases with illumination.")
        p.insert_image(pymupdf.Rect(50, 100, 250, 200), stream=image)
        p.insert_text((50, 220), "Figure 1. Solar cell response under illumination.")
        doc.save(path)
    model.write(tmp_path / "run.json", {})
    model.write(tmp_path / "papers/P1.json", {"key": "P1", "title": "Solar cells", "pdf": str(path),
        "concepts": [{"id": "c1", "label": "Solar cell"}], "relations": [{"s": "c1", "o": "c1", "p": "affects",
        "evidence": "Solar cell efficiency increases with illumination.", "verified": True}],
        "figures": [{"id": "F1", "label": "Figure 1", "page": 2, "caption": "Solar cell response under illumination."}]})
    model.write(tmp_path / "normalized/concepts.json", [{"id": "k1", "label": "Solar cell", "papers": ["P1"]}])
    return research.index(tmp_path), path


def test_concept_focus_preserved_and_original_pdf_unchanged(focused_run):
    data, path = focused_run
    original = hashlib.sha256(path.read_bytes()).hexdigest()
    spec = highlight.focus(data, "P1", "k1")
    boxes, page, note = highlight.locate(path, catalog.fingerprint(path), spec)
    assert page == 2 and boxes
    assert {b[2] for b in boxes} == {"concept term text match", "evidence quote text match"}
    assert "not scientific support" in note
    with pymupdf.open(stream=highlight.pdf_copy(path, catalog.fingerprint(path), spec), filetype="pdf") as doc:
        assert len(list(doc[1].annots())) == len(boxes)
        for annotation in doc[1].annots():
            assert not annotation.rect.is_empty and doc[1].rect.contains(annotation.rect)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original
    assert media.page_image(path, catalog.fingerprint(path), 2, spec).startswith(b"\x89PNG")


def test_figure_boxes_caption_and_conservative_image_region(focused_run):
    data, path = focused_run
    spec = highlight.focus(data, "P1", figure="F1")
    boxes, page, note = highlight.locate(path, catalog.fingerprint(path), spec)
    assert page == 2
    assert {b[2] for b in boxes} == {"caption text match", "estimated figure image region"}
    assert "estimated" in note
    html = str(media.paper_view(data, "P1", "F1"))
    assert "annotated=1#page=2" in html and "caption text match" in html


def test_unlocated_focus_is_not_inferred(focused_run):
    data, path = focused_run
    spec = ("Missing", ("quuxneverappears",), (), 0, "", "", ())
    boxes, page, note = highlight.locate(path, catalog.fingerprint(path), spec)
    assert boxes == () and "not located" in note
    figure = ("", (), (), 99, "Figure 99", "", ())
    assert highlight.locate(path, catalog.fingerprint(path), figure)[0] == ()


def test_scoped_search_and_graph_neighborhood(tmp_path):
    path = tmp_path / "ontology.ttl"
    path.write_text('@prefix owl: <http://www.w3.org/2002/07/owl#> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . <urn:a> a owl:Class; rdfs:label "Solar cell"; rdfs:subClassOf <urn:b> . <urn:b> a owl:Class . <urn:c> a owl:Class .', encoding="utf-8")
    rdf = exploration.graph(str(path), catalog.fingerprint(path))
    result = exploration.neighborhood(rdf, "urn:a")
    assert "urn:c" not in result and "urn:b" in result
    rows = [{"label": "Solar cell", "text": "efficiency", "source_run": "A", "canonical_id": "k1"},
            {"label": "Silicon", "text": "material", "source_run": "B", "canonical_id": "k1"}]
    assert exploration.search(rows, "What is solar cell efficiency?")[0]["source_run"] == "A"
    assert exploration.search(rows, "notpresent") == []
    assert "No matching saved evidence" in exploration.evidence_answer("x", [])
    with pytest.raises(ValueError):
        exploration.search(rows, "x" * 1001)


def test_model_chat_uses_bounded_cited_context_only_on_explicit_call(monkeypatch):
    seen = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b'{"choices":[{"message":{"content":"Saved evidence [S1]"}}]}'
    def transport(request, timeout):
        seen.append(json.loads(request.data))
        return Response()
    monkeypatch.setattr(exploration.urllib.request, "urlopen", transport)
    hits = [{"label": "Solar cell", "text": "Evidence", "source_run": "A"}]
    assert "[S1]" in exploration.evidence_answer("solar", hits) and seen == []
    assert "[S1]" in exploration.model_answer("solar", hits, {"DPV_CHAT_BASE_URL": "http://localhost:1234/v1"}, "fixture-model")
    assert seen[0]["model"] == "fixture-model"
    assert json.loads(seen[0]["messages"][1]["content"])["records"][0]["citation"] == "S1"


def test_vector_panel_region_is_explicitly_estimated(tmp_path):
    path = tmp_path / "vector.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.draw_rect(pymupdf.Rect(50, 100, 220, 210))
        page.draw_rect(pymupdf.Rect(250, 100, 420, 210))
        page.insert_text((50, 240), "Figure 1. Comparison of two solar cell panels.")
        doc.save(path)
    spec = ("", (), (), 1, "Figure 1", "Comparison of two solar cell panels.", ())
    boxes, _, note = highlight.locate(path, catalog.fingerprint(path), spec)
    region = next(pymupdf.Rect(b[1]) for b in boxes if b[2] == "estimated vector figure region")
    assert region.contains(pymupdf.Rect(50, 100, 420, 210))
    assert "estimated" in note


def test_rotated_pdf_retains_focus_coordinates(tmp_path):
    path = tmp_path / "rotated.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=300, height=800)
        page.insert_text((40, 700), "Solar cell")
        page.set_rotation(90)
        doc.save(path)
    spec = ("Solar cell", ("Solar cell",), (), 0, "", "", ())
    with pymupdf.open(stream=highlight.pdf_copy(path, catalog.fingerprint(path), spec), filetype="pdf") as doc:
        page = doc[0]  # PyMuPDF annotation handles require their owning page to stay alive.
        annotations = list(page.annots())
        assert len(annotations) == 1
        assert annotations[0].rect.y0 > 650
