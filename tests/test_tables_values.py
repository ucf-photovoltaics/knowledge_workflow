"""Tables in parsed sections, list-shaped answer rows, and the basis of reported values (revision 2026-10-20)."""
import pymupdf

from src.agents.extraction import ExtractionAgent, named, row_fields
from src.tools import pdf_parse


def table_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Results", fontsize=12)
    page.insert_text((72, 100), "The cells below were measured under standard test conditions.", fontsize=10)
    page.insert_text((72, 140), "Table 1. Cell efficiencies", fontsize=10)
    rows = [["Cell", "Efficiency (%)"], ["TOPCon", "0.505"], ["PERC", "23.1"]]
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            box = pymupdf.Rect(72 + 150 * c, 150 + 24 * r, 222 + 150 * c, 174 + 24 * r)
            page.draw_rect(box, width=0.8)
            page.insert_text((box.x0 + 4, box.y0 + 16), text, fontsize=10)
    doc.save(path)


def test_table_is_written_into_its_section_once(tmp_path):
    table_pdf(tmp_path / "t.pdf")
    parsed = pdf_parse.parse(str(tmp_path / "t.pdf"))
    text = " ".join(s["text"] for s in parsed["sections"])
    assert parsed["tables"] == [{"id": "T1", "page": 1, "caption": "Cell efficiencies", "rows": 3}]
    assert "TABLE T1: Cell efficiencies\n| Cell | Efficiency (%) |\n| TOPCon | 0.505 |\n| PERC | 23.1 |" in text
    assert text.count("TOPCon") == 1 and parsed["parse_stats"]["n_tables"] == 1


def test_rows_returned_as_lists_are_read_in_schema_order():
    fields = row_fields(["extraction_measurements"])
    assert fields["measurements"][:6] == ["property", "entity", "value", "unit", "condition", "evidence"]
    answer = {"measurements": [["c19", "c2", "0.031", "$/kWh", "peak period", "Price per kWh at the peak period 0.031"],
                               ["c1"]]}
    out = named(answer, fields)
    assert out["measurements"][0]["value"] == "0.031" and "basis" not in out["measurements"][0]
    assert out["measurements"][1] == ["c1"]             # too short to read safely: left for the quality filter
    assert isinstance(answer["measurements"][0], list)  # the raw answer is kept as returned


def test_basis_is_kept_and_unknown_bases_dropped():
    part = {"concepts": [{"id": "c1", "label": "efficiency", "type": "property"},
                         {"id": "c2", "label": "TOPCon cell", "type": "device"}],
            "measurements": [{"property": "c1", "entity": "c2", "value": "25.4", "unit": "%", "basis": "Measured"},
                             {"property": "c1", "entity": "c2", "value": "26", "unit": "%", "basis": "guess"}]}
    merged = ExtractionAgent._merge([part])
    assert [m["basis"] for m in merged["measurements"]] == ["measured", ""]
