"""Deterministic PDF → sections + figure captions/mentions. Drops back matter and repeated headers/footers."""
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
MENTION = re.compile(r"\bfig(?:ure)?s?\.?\s*(\d+)(?:\s*(?:and|,|–|-)\s*(\d+))?", re.I)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
MAX_MENTIONS = 3


SURROGATES = re.compile(r"[\ud800-\udfff]")  # broken math/symbol glyphs from some PDFs; not encodable as UTF-8


def _clean(text: str) -> str:
    text = SURROGATES.sub("", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def parse(pdf_path: str) -> dict:
    t0 = time.perf_counter()
    doc = pymupdf.open(pdf_path)
    blocks = [(p.number + 1, _clean(b[4])) for p in doc for b in p.get_text("blocks") if b[6] == 0]
    raw_chars = sum(len(t) for _, t in blocks)

    # Running headers/footers: identical short blocks on 3+ pages.
    counts = Counter(t for _, t in blocks if len(t) < 150)
    repeated = {t for t, n in counts.items() if n >= 3}

    sections, figures = [], {}
    current, dropping = {"heading": "Front matter", "text": []}, False
    for page, text in blocks:
        if not text or text in repeated or re.fullmatch(r"\d{1,4}", text):
            continue
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
        "parse_stats": {"pages": doc.page_count, "chars_raw": raw_chars, "chars_kept": kept,
                        "reduction": round(1 - kept / raw_chars, 3) if raw_chars else 0,
                        "n_sections": len(sections), "n_figures": len(figures),
                        "parse_s": round(time.perf_counter() - t0, 3)},
    }
