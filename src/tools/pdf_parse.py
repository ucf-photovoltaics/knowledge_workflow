"""Deterministic PDF → sections + figure captions/mentions + tables. Drops back matter and repeated headers/footers.

Tables (PyMuPDF find_tables) are written into their section as rows under their caption, "TABLE n: caption" then
"| cell | cell |" lines, so the model reads each value with its row and column; the text blocks inside a table are
dropped so nothing is read twice. Cell text is read by position (clip, sorted), which keeps decimals intact.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import re
import time
from collections import Counter

import pymupdf

SECTION_WORDS = (r"abstract|introduction|background|literature review|related work|theory|methods?|methodology|"
                 r"materials and methods|experimental(?: methods| details| section)?|experiments?|model|"
                 r"results(?: and discussion)?|discussion|analysis|conclusions?|summary|outlook|appendix")
BACK_MATTER = (r"references|bibliography|acknowledge?ments?|author contributions?|credit authorship.*|"
               r"conflicts? of interest|declaration of competing interest|competing interests?|funding|"
               r"data availability.*|supplementary (?:material|information)")
HEADING = re.compile(rf"^(?:(?:\d+(?:\.\d+)*|[IVX]+)\.?\s+)?({SECTION_WORDS}|{BACK_MATTER})\s*:?$", re.I)
NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+([A-Z][^.]{2,80})$")
DROP = re.compile(rf"^(?:(?:\d+(?:\.\d+)*|[IVX]+)\.?\s+)?(?:{BACK_MATTER})\s*:?$", re.I)
CAPTION = re.compile(r"^(?:fig(?:ure)?\.?)\s*(\d+)\s*[.:|\-–—]\s*", re.I)
TABLE_CAPTION = re.compile(r"^tab(?:le)?\.?\s*(\d+|[IVX]+)\b\s*[.:|\-–—]?\s*", re.I)
MENTION = re.compile(r"\bfig(?:ure)?s?\.?\s*(\d+)(?:\s*(?:and|,|–|-)\s*(\d+))?", re.I)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
MAX_MENTIONS = 3
CELL_CHARS = 120      # longer cells are cut
PROSE_CELL = 60       # mean characters per cell above which a detected "table" is a text box (abstract, info panel);
                      # real tables in a 12-paper sample averaged 4-40, article-info and text boxes 88-248


SURROGATES = re.compile(r"[\ud800-\udfff]")  # broken math/symbol glyphs from some PDFs; not encodable as UTF-8


def _clean(text: str) -> str:
    text = SURROGATES.sub("", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def _tables(page) -> list[tuple[pymupdf.Rect, list[list[str]]]]:
    """(area, rows) of the real tables on a page: at least 2 x 2 cells, not a text box."""
    out = []
    for tab in page.find_tables().tables:
        rows = [[_clean(page.get_text("text", clip=pymupdf.Rect(c), sort=True)) if c else "" for c in row.cells]
                for row in tab.rows]
        cells = [c for row in rows for c in row if c]
        if len(rows) >= 2 and max(map(len, rows)) >= 2 and cells and sum(map(len, cells)) / len(cells) <= PROSE_CELL:
            out.append((pymupdf.Rect(tab.bbox), [[c[:CELL_CHARS].replace("|", "/") for c in row] for row in rows]))
    return out


def _table_text(tid: str, caption: str, rows: list[list[str]]) -> str:
    lines = [f"TABLE {tid}: {caption}".rstrip(": ")] + ["| " + " | ".join(row) + " |" for row in rows if any(row)]
    return "\n" + "\n".join(lines) + "\n"


def parse(pdf_path: str) -> dict:
    t0 = time.perf_counter()
    doc = pymupdf.open(pdf_path)
    blocks, tables = [], []  # blocks: (page, text, table index or None)
    for p in doc:
        found = _tables(p)
        placed = set()
        for b in p.get_text("blocks"):
            if b[6] != 0:
                continue
            area = pymupdf.Rect(b[:4])
            inside = next((i for i, (r, _) in enumerate(found) if abs(area & r) > 0.5 * abs(area)), None)
            if inside is None:
                blocks.append((p.number + 1, _clean(b[4]), None))
            elif inside not in placed:  # the table goes where its first block was
                placed.add(inside)
                blocks.append((p.number + 1, "", len(tables)))
                tables.append({"page": p.number + 1, "rows": found[inside][1], "caption": ""})
        for i in set(range(len(found))) - placed:
            blocks.append((p.number + 1, "", len(tables)))
            tables.append({"page": p.number + 1, "rows": found[i][1], "caption": ""})
    raw_chars = sum(len(t) for _, t, _ in blocks)

    # Running headers/footers: identical short blocks on 3+ pages.
    counts = Counter(t for _, t, _ in blocks if t and len(t) < 150)
    repeated = {t for t, n in counts.items() if n >= 3}

    sections, figures = [], {}
    current, dropping, caption = {"heading": "Front matter", "text": []}, False, None
    for page, text, table in blocks:
        if table is not None:
            tab = tables[table]
            tab["id"] = f"T{caption[0]}" if caption and caption[1] == page else f"T-p{page}-{table + 1}"  # untitled
            tab["caption"] = caption[2] if caption and caption[1] == page else ""
            caption = None
            if not dropping:
                current["text"].append(_table_text(tab["id"], tab["caption"], tab["rows"]))
            continue
        if not text or text in repeated or re.fullmatch(r"\d{1,4}", text):
            continue
        tcap = TABLE_CAPTION.match(text)
        if tcap and len(text) > 12:  # kept for the table that follows on this page, and in the text if none does
            caption = (tcap.group(1), page, text[tcap.end():])
        cap = CAPTION.match(text)
        if cap and len(text) > 20:
            n = cap.group(1)
            figures.setdefault(n, {"id": f"F{n}", "label": f"Figure {n}", "page": page,
                                   "caption": text[cap.end():], "mentions": []})
            continue
        if len(text) <= 90 and (HEADING.match(text) or NUMBERED_HEADING.match(text)):
            dropping = bool(DROP.match(text))
            if current["text"]:
                sections.append(current)
            current = {"heading": text, "text": []}
            continue
        if not dropping:
            current["text"].append(text)
    if current["text"]:
        sections.append(current)
    sections = [{"heading": s["heading"], "text": " ".join(s["text"])} for s in sections if not DROP.match(s["heading"])]

    # Citing sentences per figure (deterministic, capped).
    for s in sections:
        for sent in SENTENCE.split(s["text"]):
            for m in MENTION.finditer(sent):
                for n in filter(None, m.groups()):
                    fig = figures.get(n)
                    if fig and len(fig["mentions"]) < MAX_MENTIONS and sent[:300] not in fig["mentions"]:
                        fig["mentions"].append(sent[:300])

    kept = sum(len(s["text"]) for s in sections)
    return {
        "sections": sections,
        "figures": sorted(figures.values(), key=lambda f: int(f["id"][1:])),
        "tables": [{k: tab[k] for k in ("id", "page", "caption")} | {"rows": len(tab["rows"])}
                   for tab in tables if "id" in tab],
        "parse_stats": {"pages": doc.page_count, "chars_raw": raw_chars, "chars_kept": kept,
                        "reduction": round(1 - kept / raw_chars, 3) if raw_chars else 0,
                        "n_sections": len(sections), "n_figures": len(figures),
                        "n_tables": sum("id" in tab for tab in tables),
                        "parse_s": round(time.perf_counter() - t0, 3)},
    }
