"""Evidence/term text matches and conservative figure regions in disposable PDF copies.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from functools import lru_cache
from dpv_dashboard import research


def focus(data, paper, canonical=None, figure=None):
    record = data.papers.get(paper, {})
    fig = next((f for f in research.records(record.get("figures")) if f.get("id") == figure), {})
    concept = data.concepts.get(canonical, {})
    lineage = [r for r in data.by_canonical.get(canonical, []) if r.get("paper") == paper and
               (r["lineage_status"] == "recorded" or r["lineage_status"].startswith("reconstructed"))]
    terms = [r.get("original_label") for r in lineage] + [concept.get("label"), *concept.get("alt_labels", [])]
    terms = tuple(dict.fromkeys(t.strip() for t in terms if isinstance(t, str) and 2 <= len(t.strip()) <= 180))[:24]
    quotes = tuple(dict.fromkeys(c["quote"].strip() for c in data.claims(paper, canonical) if canonical and
                                isinstance(c.get("quote"), str) and 15 <= len(c["quote"].strip()) <= 3000))[:8]
    bbox = fig.get("bbox")
    bbox = tuple(bbox) if isinstance(bbox, (list, tuple)) and len(bbox) == 4 and all(isinstance(v, (float, int)) for v in bbox) else ()
    return (concept.get("label", ""), terms, quotes, fig.get("page") if isinstance(fig.get("page"), int) else 0,
            str(fig.get("label") or figure or ""), str(fig.get("caption", ""))[:1000], bbox)


@lru_cache(maxsize=48)
def locate(path, stamp, spec):
    import pymupdf
    label, terms, quotes, figure_page, figure_label, caption, saved_box = spec
    boxes, notes = [], []
    with pymupdf.open(path) as doc:
        if len(doc) > 1000:
            return (), 1, "Document exceeds the 1,000-page preview limit."
        if figure_label:
            if not 1 <= figure_page <= len(doc):
                return (), 1, "Figure page not recorded or outside this PDF; figure not located."
            page = doc[figure_page - 1]
            bounds = page.rect * page.derotation_matrix
            if saved_box:
                rect = pymupdf.Rect(saved_box) & bounds
                if not rect.is_empty and not rect.is_infinite:
                    boxes.append((figure_page, tuple(rect), "recorded figure boundary"))
            hits = page.search_for(" ".join(caption.split()[:12])) if caption else []
            if not hits:
                hits = page.search_for(figure_label)
            if hits:
                cap = pymupdf.Rect(hits[0])
                for hit in hits[1:]:
                    if abs(hit.y0 - cap.y1) < 25:
                        cap |= hit
                # Expand a matched phrase to its caption block, avoiding adjacent body text.
                for block in page.get_text("blocks"):
                    rect = pymupdf.Rect(block[:4])
                    if rect.intersects(cap) and rect.height < 100 and caption[:35].casefold() in " ".join(block[4].split()).casefold():
                        cap |= rect
                boxes.append((figure_page, tuple(cap), "caption text match"))
                if not boxes[0][2].startswith("recorded"):
                    candidates = [pymupdf.Rect(i["bbox"]) for i in page.get_image_info()]
                    candidates = [r for r in candidates if r.width > 50 and r.height > 40 and r.get_area() < bounds.get_area() * .85
                                  and r.x0 < cap.x1 and r.x1 > cap.x0 and -10 <= cap.y0 - r.y1 <= 220]
                    if candidates:
                        nearest = min(candidates, key=lambda r: abs(cap.y0 - r.y1))
                        boxes.append((figure_page, tuple(nearest), "estimated figure image region"))
                    else:
                        # Plot frames/panel rectangles are stronger anchors than individual strokes.
                        anchors = [pymupdf.Rect(d["rect"]) for d in page.get_drawings()]
                        anchors = [r for r in anchors if r.width > 70 and r.height > 35 and r.get_area() < bounds.get_area() * .8
                                   and r.x0 < cap.x1 and r.x1 > cap.x0 and 0 <= cap.y0 - r.y1 <= 220]
                        if anchors:
                            region = pymupdf.Rect(min(anchors, key=lambda r: cap.y0 - r.y1))
                            for _ in range(8):
                                prior = tuple(region)
                                expanded = region + (-80, -80, 80, 80)
                                for r in anchors:
                                    if expanded.intersects(r):
                                        region |= r
                                if prior == tuple(region):
                                    break
                            region = (region + (-12, -12, 12, 12)) & pymupdf.Rect(0, 0, bounds.width, cap.y0 - 2)
                            boxes.append((figure_page, tuple(region), "estimated vector figure region"))
            notes.append("; ".join(dict.fromkeys(b[2] for b in boxes)) or "Figure and caption not located on the recorded page.")
            return tuple(boxes), figure_page, "; ".join(notes)
        if not terms and not quotes:
            return (), 1, "No concept focus selected; original paper view."
        evidence_pages = []
        for number, page in enumerate(doc, 1):
            for phrase in quotes:
                hits = page.search_for(phrase)
                if hits:
                    evidence_pages.append(number)
                boxes.extend((number, tuple(r), "evidence quote text match") for r in hits[:12])
            for term in terms:
                boxes.extend((number, tuple(r), "concept term text match") for r in page.search_for(term)[:20])
            if len(boxes) >= 300:
                boxes = boxes[:300]
                notes.append("Preview limited to 300 boxes.")
                break
        first = evidence_pages[0] if evidence_pages else boxes[0][0] if boxes else 1
        notes.insert(0, f"{len(boxes)} text-match boxes for {label}; these locate text, not scientific support." if boxes else
                     f"Concept {label} not located by its saved terms or evidence quotes. No box was inferred.")
    return tuple(boxes), first, " ".join(notes)


def annotate(document, boxes):
    import pymupdf
    for number, coordinates, kind in boxes:
        page = document[number - 1]
        rect = pymupdf.Rect(coordinates) & (page.rect * page.derotation_matrix)
        if rect.is_empty:
            continue
        annotation = page.add_rect_annot(rect)
        annotation.set_colors(stroke=(.85, .12, .12) if "figure" in kind else (.05, .35, .85))
        annotation.set_border(width=1.5)
        annotation.set_info(title="UCF DPV focus", content=kind)
        annotation.update()


@lru_cache(maxsize=6)
def pdf_copy(path, stamp, spec):
    import pymupdf
    boxes, _, _ = locate(path, stamp, spec)
    with pymupdf.open(path) as doc:
        annotate(doc, boxes)
        return doc.tobytes(garbage=3, deflate=True)
