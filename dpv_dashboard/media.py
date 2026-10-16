"""Explicitly registered local research media; no client-supplied filesystem paths.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from collections import OrderedDict
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import re
from urllib.parse import urlsplit
from starlette.responses import FileResponse, Response
from starlette.routing import Route
from shiny import ui
from dpv_dashboard import catalog, model, research, highlight, quality

_files = OrderedDict()
_secret = uuid4().hex


def local_file(data, value, suffixes):
    if not data.root or not isinstance(value, str) or not value:
        return None
    path = Path(value)
    path = (path if path.is_absolute() else data.root / path).resolve()
    allowed = [data.root.resolve(), (model.ROOT / "outputs/cache/pdfs").resolve()]
    if not any(path.is_relative_to(base) for base in allowed) or catalog.restricted(path) or path.suffix.lower() not in suffixes:
        return None
    return path if path.is_file() else None


def register(path, spec=None):
    stamp = catalog.fingerprint(path)
    token = sha256((_secret + str(path) + str(stamp) + str(spec)).encode()).hexdigest()
    _files[token] = (path, stamp, spec)
    _files.move_to_end(token)
    while len(_files) > 512:
        _files.popitem(last=False)
    return "/research-media/" + token


async def serve(request):
    value = _files.get(request.path_params["token"])
    if not value or catalog.fingerprint(value[0]) != value[1]:
        return Response("Preview expired or unavailable. Reopen the reference.", status_code=404)
    if request.query_params.get("annotated") and value[2]:
        try:
            from starlette.concurrency import run_in_threadpool
            content = await run_in_threadpool(highlight.pdf_copy, *value)
            return Response(content, media_type="application/pdf", headers={"Cache-Control": "private, no-store"})
        except (ValueError, RuntimeError, ImportError):
            return Response("Annotated PDF unavailable. Open the original source PDF.", status_code=404)
    if request.query_params.get("crop"):
        try:
            from starlette.concurrency import run_in_threadpool
            content = await run_in_threadpool(figure_image, *value)
            return Response(content, media_type="image/png", headers={"Cache-Control": "private, no-store"})
        except (ValueError, RuntimeError, ImportError):
            return Response("Figure crop unavailable. Expand the full paper.", status_code=404)
    if request.query_params.get("page") or request.query_params.get("focus"):
        try:
            from starlette.concurrency import run_in_threadpool
            if request.query_params.get("focus") and value[2]:
                _, page, _ = await run_in_threadpool(highlight.locate, *value)
            else:
                page = int(request.query_params.get("page", "1"))
            if page < 1 or value[0].suffix.lower() != ".pdf":
                raise ValueError("Invalid PDF page")
            from starlette.concurrency import run_in_threadpool
            content = await run_in_threadpool(page_image, value[0], value[1], page, value[2])
            return Response(content, media_type="image/png", headers={"Cache-Control": "private, no-store"})
        except (ValueError, RuntimeError, ImportError):
            return Response("Source page preview unavailable. Open the PDF instead.", status_code=404)
    return FileResponse(value[0], headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@lru_cache(maxsize=16)
def page_image(path, stamp, page, spec=None):
    if not isinstance(page, int) or page < 1:
        raise ValueError("A positive source page is required")
    import pymupdf
    with pymupdf.open(path) as document:
        if page > len(document):
            raise ValueError("Page outside document")
        if spec:
            boxes, _, _ = highlight.locate(path, stamp, spec)
            highlight.annotate(document, [b for b in boxes if b[0] == page])
        source = document[page - 1]
        scale = min(1.5, 1600 / max(source.rect.width, source.rect.height))
        return source.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")


route = Route("/research-media/{token}", serve)


@lru_cache(maxsize=32)
def figure_image(path, stamp, spec):
    """Render only a located figure region; caption-only matches are never crops."""
    if not spec or Path(path).suffix.lower() != ".pdf":
        raise ValueError("A PDF figure reference is required")
    import pymupdf
    boxes, _, _ = highlight.locate(path, stamp, spec)
    regions = [b for b in boxes if "figure" in b[2]]
    if not regions:
        raise ValueError("Figure boundary unavailable")
    page, bounds, _ = regions[0]
    with pymupdf.open(path) as document:
        source = document[page - 1]
        clip = pymupdf.Rect(bounds) & (source.rect * source.derotation_matrix)
        if clip.is_empty or clip.width < 2 or clip.height < 2:
            raise ValueError("Figure boundary is empty")
        # Convert unrotated layout coordinates to the rendered page orientation.
        clip = clip * source.rotation_matrix
        scale = min(2, 1800 / max(clip.width, clip.height))
        return source.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False).tobytes("png")


def figure_preview(data, key, figure, pdf):
    image = local_file(data, figure.get("image_path") or figure.get("image"), {".png", ".jpg", ".jpeg", ".webp"})
    if image:
        return register(image), "Saved figure image"
    if pdf and pdf.stat().st_size <= 64 * 1024 * 1024:
        spec = highlight.focus(data, key, figure=figure.get("id"))
        try:
            boxes, _, _ = highlight.locate(pdf, catalog.fingerprint(pdf), spec)
            if any("figure" in b[2] for b in boxes):
                return register(pdf, spec) + "?crop=1", "Recorded figure crop" if any(b[2].startswith("recorded") for b in boxes) else "Estimated figure crop · check against the full paper"
        except (ValueError, RuntimeError, OSError, ImportError):
            pass
    return None, "Figure crop unavailable · expand the full paper to inspect the source page"


def paper_view(data, key, figure=None, canonical=None, gallery=False, claim=None):
    paper = data.papers.get(key, {})
    if not paper:
        return ui.p("Source paper record unavailable.")
    fig = next((f for f in research.records(paper.get("figures")) if f.get("id") == figure), None) if figure else None
    pdf = local_file(data, paper.get("pdf"), {".pdf"})
    contents = [ui.h4(paper.get("title", key)), ui.p(f"Source: {data.root.name} · Paper: {key}")]
    if paper.get("cache_hit"):
        contents.append(ui.p("Reused cached paper extraction; this run did not regenerate the paper evidence.", class_="muted"))
    if claim:
        selected = next((row for row in data.claims(key) if f"{row.get('kind')}:{row.get('claim_number')}" == claim), None)
        if selected:
            contents += [ui.h5("Cited evidence"), ui.p(" · ".join(str(selected.get(k) or "") for k in ("subject", "predicate", "object", "value", "unit"))),
                         ui.tags.blockquote(selected.get("quote") or "Supporting quote not recorded."),
                         ui.p("Quote match: " + str(selected.get("verification", "not recorded")) + ". A source-text match does not verify the value, causal direction or interpretation.")]
        else:
            contents.append(ui.p("The cited claim record is unavailable; the source paper remains accessible."))
    if figure and not fig:
        contents.append(ui.p("This figure reference has no saved figure record."))
    if fig:
        contents += [ui.h5(fig.get("label", figure)), ui.p(fig.get("caption", "Caption unavailable."))]
        image_url, crop_note = figure_preview(data, key, fig, pdf)
        contents += [ui.p(crop_note), ui.tags.img(src=image_url, style="max-width:100%", alt=fig.get("caption", "Figure crop")) if image_url else None]
    if pdf:
        spec = highlight.focus(data, key, canonical, figure) if canonical or figure else None
        if spec and pdf.stat().st_size > 64 * 1024 * 1024:
            contents.append(ui.p("PDF exceeds the 64 MB focus-preview limit; original viewing is available."))
            spec = None
        url = register(pdf, spec)
        page = fig.get("page") if fig else None
        if spec:
            try:
                _, page, note = highlight.locate(pdf, catalog.fingerprint(pdf), spec)
            except (ValueError, RuntimeError, OSError):
                note = "Focus could not be located in this PDF. Original viewing remains available."
                spec = None
                url = register(pdf)
            contents.append(ui.p(note, class_="focus-status"))
        fragment = f"#page={page}" if isinstance(page, int) and page > 0 else ""
        if fragment and not fig:
            contents += [ui.p("Focused source page preview; blue boxes locate text, red boxes mark figure regions:" if spec else "Source page preview (the full page, including the figure):"),
                         ui.tags.img(src=url + f"?page={page}", alt=f"Source page {page}", style="max-width:100%")]
        if not fig:
            figures = research.records(paper.get("figures"))
            cards = []
            for f in figures[:100]:
                image_url, crop_note = figure_preview(data, key, f, pdf)
                cards.append(ui.div(ui.strong(f.get("label", f.get("id", "Figure"))),
                    ui.tags.img(src=image_url, alt="Figure crop", loading="lazy", class_="report-thumbnail") if image_url else None,
                    ui.p(crop_note, class_="muted"),
                    ui.p(f.get("caption") or "Caption not recorded"),
                    ui.tags.button("Inspect figure", type="button", class_="btn btn-outline-primary research-open",
                                   **{"data-root": str(data.root), "data-paper": key, "data-canonical": canonical or "", "data-figure": f.get("id", "")}), class_="figure-card"))
            contents.append(ui.tags.details(ui.tags.summary(f"Figure gallery · {len(figures)} saved figures"), ui.p("Showing up to 100 figures; all figure records remain in the paper artifact."),
                ui.tags.input(type="search", placeholder="Search figure captions", class_="figure-filter form-control", **{"aria-label": "Search figure captions"}),
                ui.div(*cards, class_="report-library"), open=gallery))
        full_paper = [ui.tags.a("Open original source PDF", href=register(pdf) + fragment, target="_blank", rel="noopener"),
                     ui.tags.a("Open boxed PDF copy", href=url + "?annotated=1" + fragment, target="_blank", rel="noopener", class_="ms-3") if spec else None,
                     ui.tags.iframe(src=url + ("?annotated=1" if spec else "") + fragment, title="Source paper PDF", style="width:100%;height:65vh;border:1px solid #ddd")]
        contents.append(ui.tags.details(ui.tags.summary("Expand full paper at source page"), *full_paper))
    else:
        contents.append(ui.p("Local source PDF unavailable within the run or pipeline PDF cache."))
    return ui.div(*contents)


def reference(data, label, canonical=None, paper=None, figure=None, claim=None, direct=False):
    cid = canonical if canonical in data.concepts else None
    papers = [paper] if paper in data.papers else (sorted(set(data.concepts.get(cid, {}).get("papers", [])) |
              {r["paper"] for r in data.by_canonical.get(cid, [])}) if cid else [])
    valid = [key for key in papers if key in data.papers]
    if not valid:
        if cid:
            return ui.tags.button(quality.bounded(str(label), 160), type="button", class_="research-nav research-ref",
                **{"data-root": str(data.root), "data-canonical": cid, "data-paper": "", "data-tab": "Concept lineage"})
        return ui.tags.span(quality.bounded(str(label), 160), title="Supporting paper record unavailable. Full saved label remains in technical details.")
    if direct:
        return ui.tags.button(quality.bounded(str(label), 160), type="button", class_="research-open research-ref",
            **{"data-root": str(data.root), "data-paper": valid[0], "data-canonical": cid or "", "data-figure": figure or "", "data-claim": claim or ""})
    preview = []
    for key in valid[:3]:
        record = data.papers[key]
        claims = data.claims(key, cid) if cid else data.claims(key)
        quote = str(claims[0].get("quote", ""))[:350] if claims else "No linked claim recorded."
        statuses = sorted({r["lineage_status"] for r in data.by_canonical.get(cid, []) if r.get("paper") == key})
        pdf = local_file(data, record.get("pdf"), {".pdf"})
        spec = highlight.focus(data, key, cid, figure) if cid or figure else None
        if pdf and pdf.stat().st_size > 64 * 1024 * 1024:
            spec = None
        preview.append(ui.div(ui.strong(record.get("title", key)), ui.p(quote), ui.tags.small("; ".join(statuses)),
            ui.tags.img(**{"data-preview-src": register(pdf, spec) + ("?focus=1" if spec else "?page=1")}, alt="Focused source paper preview" if spec else "First page of source paper", style="width:100%;max-height:240px;object-fit:contain") if pdf else ui.p("Local PDF unavailable."),
            ui.p("Figures: " + ", ".join(str(f.get("label", f.get("id", ""))) for f in research.records(record.get("figures"))) or "No figures recorded."),
            ui.tags.button("Open paper & figures", type="button", class_="btn btn-sm btn-outline-primary research-open",
                           **{"data-root": str(data.root), "data-paper": key, "data-canonical": cid or "", "data-figure": figure or ""})))
    return ui.tags.span(ui.tags.button(quality.bounded(str(label), 160), type="button", class_="research-ref research-open",
        **{"data-root": str(data.root), "data-paper": valid[0], "data-canonical": cid or "", "data-figure": figure or ""}),
        ui.tags.span(*preview, class_="research-popover", role="tooltip"), class_="research-reference", tabindex="0")


def external_reference(label, value):
    """Link only explicit web IRIs, keeping arbitrary paths and schemes inert."""
    if not isinstance(value, str):
        return str(label or "")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError:
        return str(label or value)
    if parsed.scheme not in ("http", "https") or not hostname or parsed.username or parsed.password:
        return str(label or value)
    return ui.tags.a(quality.bounded(str(label or value), 160), href=value, target="_blank", rel="noopener noreferrer")


def reference_text(data, value, paper=None):
    """Resolve explicit identifiers in narratives without guessing unscoped paper IDs."""
    text = str(value)
    pattern = r"https?://[^\s<>\"']+|\b10\.\d{4,9}/[^\s<>\"']+|\b[A-Za-z][\w-]*-\d{8}-\d{6}\b|\b(?:k\d+|c\d+|F\d+|Fig(?:ure)?\.?\s*\d+|[A-Z0-9]{8})\b"
    runs = {root.name: root for root in research.source_roots(data.root)} if data.root else {}
    if data.root:
        runs[data.root.name] = data.root
    parts, start = [], 0
    for match in re.finditer(pattern, text):
        parts.append(text[start:match.start()])
        token = match[0]
        target = token
        if token in runs:
            target = ui.tags.button(token, type="button", class_="research-nav research-ref",
                **{"data-root": str(runs[token]), "data-canonical": "", "data-paper": "", "data-tab": "Paper & evidence"})
        elif token in getattr(data, "iri_ids", {}):
            cid = data.iri_ids[token]
            target = reference(data, data.label(cid), canonical=cid, direct=True)
        elif token.startswith(("http://", "https://")):
            target = external_reference(token, token)
        elif token.startswith("10."):
            from urllib.parse import quote
            target = external_reference(token, "https://doi.org/" + quote(token, safe="/"))
        elif token in data.papers:
            target = reference(data, data.papers[token].get("title", token), paper=token, direct=True)
        elif token.startswith("k") and token in data.concepts:
            target = reference(data, data.label(token), canonical=token, direct=True)
        elif (paper, token) in getattr(data, "originals", {}):
            original = data.originals[(paper, token)]
            target = reference(data, original.get("label", token), paper=paper, direct=True)
        else:
            number = re.search(r"\d+$", token)
            figure = "F" + number[0] if number and not token.startswith(("k", "c")) else None
            record = data.papers.get(paper, {})
            if figure and any(f.get("id") == figure for f in research.records(record.get("figures"))):
                target = reference(data, token, paper=paper, figure=figure, direct=True)
        parts.append(target)
        start = match.end()
    parts.append(text[start:])
    return ui.span(*parts, style="white-space:pre-wrap")


def linked_markdown(data, text):
    """Link resolved references in rendered report text without nesting links."""
    from html.parser import HTMLParser
    from html import escape
    class References(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts, self.skip = [], 0

        def handle_starttag(self, tag, attrs):
            self.parts.append(self.get_starttag_text())
            if tag in ('a', 'script', 'style'):
                self.skip += 1

        def handle_startendtag(self, tag, attrs):
            self.parts.append(self.get_starttag_text())

        def handle_endtag(self, tag):
            self.parts.append(f'</{tag}>')
            if tag in ('a', 'script', 'style'):
                self.skip = max(0, self.skip - 1)

        def handle_data(self, value):
            self.parts.append(escape(value) if self.skip else str(reference_text(data, value)))

    parser = References()
    parser.feed(str(ui.markdown(text)))
    return ui.HTML(''.join(parser.parts))


def cited_reference(row, label):
    root = row.get("root")
    if not root:
        return ui.span(label, title="Source run unavailable")
    data = research.index(Path(root))
    claim = f"{row['kind']}:{row['claim_number']}" if row.get("kind") in ("relation", "causal", "measurement") and row.get("claim_number") is not None else None
    return reference(data, label, row.get("canonical_id"), row.get("paper"), row.get("figure"), claim=claim, direct=True)


def chat_answer(answer, sources):
    """Keep model text escaped; only citations in this response's source list resolve."""
    roots = {row.get("root") for row in sources if row.get("root")}
    data = research.index(Path(next(iter(roots)))) if len(roots) == 1 else research.index(None)
    papers = {row.get("paper") for row in sources}
    paper = next(iter(papers)) if len(roots) == 1 and len(papers) == 1 else None
    parts, start = [], 0
    for match in re.finditer(r"\[S(\d+)\]", str(answer)):
        parts.append(reference_text(data, str(answer)[start:match.start()], paper))
        number = int(match[1])
        parts.append(cited_reference(sources[number - 1], match[0]) if 1 <= number <= len(sources) else
                     ui.span(match[0] + " (source unavailable)", class_="muted"))
        start = match.end()
    parts.append(reference_text(data, str(answer)[start:], paper))
    return ui.div(*parts, class_="chat-answer", style="white-space:pre-wrap")


def rich_table(data, values):
    """Render references as escaped Shiny tags, retaining raw IDs in separate columns."""
    from dpv_dashboard.inspect import table
    frame = table(values).astype(object)
    indexed = None
    if data.integration:
        from dpv_dashboard import integration
        indexed = [(s, research.index(s["root"])) for s in integration.sources(data.root) if s["root"]]
    for number, row in enumerate(values):
        cid = row.get("canonical_id") or row.get("id")
        if cid not in data.concepts and row.get("iri") in data.iri_ids:
            cid = data.iri_ids[row["iri"]]
        paper = row.get("paper") or row.get("key") or row.get("paper_id")
        if paper in data.papers and "title" not in frame and not row.get("label") and not row.get("kind"):
            frame["title"] = None
        if paper in data.papers and "title" in frame and not row.get("title"):
            frame.at[number, "title"] = reference(data, data.papers[paper].get("title", paper), paper=paper)
        for field in ("papers", "supporting_papers"):
            keys = row.get(field)
            if field not in frame or not isinstance(keys, list):
                continue
            buttons = [ui.tags.button(data.papers[key].get("title", key), type="button", class_="research-nav research-ref",
                       **{"data-root": str(data.root), "data-paper": key, "data-canonical": cid if cid in data.concepts else "", "data-tab": "Paper & evidence"})
                       for key in keys if isinstance(key, str) and key in data.papers]
            frame.at[number, field] = ui.tags.details(ui.tags.summary(f"{len(keys)} supporting papers"), *[ui.div(button) for button in buttons]) if buttons else "Source paper records unavailable"
        for field in ("s", "o", "cause", "effect", "concept", "entity", "parent"):
            raw = row.get(field)
            if not isinstance(raw, str) or field not in frame:
                continue
            original = data.originals.get((paper, raw), {})
            named = original.get("label") or (data.label(raw) if raw in data.concepts else None)
            if named:
                frame.at[number, field] = reference(data, named, canonical=raw if raw in data.concepts else None, paper=paper)
            elif raw.startswith(("http://", "https://")):
                frame.at[number, field] = external_reference(raw, raw)
        for field in ("iri", "a_iri", "b_iri", "source_iri", "external_iri", "definition_source", "source"):
            if field in frame and isinstance(row.get(field), str) and row[field].startswith(("https://", "http://")):
                frame.at[number, field] = external_reference(row[field], row[field])
        if "external_label" in frame and row.get("external_label"):
            frame.at[number, "external_label"] = external_reference(row["external_label"], row.get("external_iri"))
        if "quote" in frame and paper in data.papers and row.get("quote"):
            token = f"{row.get('kind')}:{row.get('claim_number')}" if row.get("claim_number") is not None else None
            frame.at[number, "quote"] = reference(data, row["quote"], paper=paper, claim=token, direct=True)
        figure = row.get("id") if paper and any(f.get("id") == row.get("id") for f in research.records(data.papers.get(paper, {}).get("figures"))) else None
        for column in ("label", "local_label", "title", "original_label", "caption", "subject", "object"):
            if column in frame.columns and row.get(column):
                target = cid
                if column in ("subject", "object"):
                    oid = row.get(column + "_id")
                    links = [r for r in data.lineage if r.get("paper") == paper and r.get("original_id") == oid and
                             (r["lineage_status"] == "recorded" or r["lineage_status"].startswith("reconstructed"))]
                    target = links[0].get("canonical_id") if len(links) == 1 else None
                frame.at[number, column] = reference(data, row[column], target, paper, figure)
        if data.integration:
            from dpv_dashboard import integration
            for side in ("a", "b", ""):
                column = side + "_label" if side else "label"
                if column not in frame.columns or not row.get(column):
                    continue
                match = integration.member(data.root, row.get(side + "_iri") if side else row.get("iri"),
                    row.get(side + "_run") if side else None, row.get(side + "_domain") if side else row.get("domain"), indexed=indexed)
                if match:
                    _, source, target = match
                    frame.at[number, column] = reference(source, row[column], target)
        # Always expose saved figure references for this paper, including caption-only records.
        if paper in data.papers:
            import re
            mentioned = str(row.get("quote", "")) + " " + str(row.get("figures", ""))
            figures = research.records(data.papers[paper].get("figures"))
            if figure:
                figures = [f for f in figures if f.get("id") == figure]
            if row.get("kind") in ("relation", "causal", "measurement"):
                figures = [f for f in figures if re.search(r"\b(?:fig(?:ure)?s?\.?\s*|F)" + re.escape(str(f.get("id", ""))[1:]) + r"\b", mentioned, re.I)]
            elif row.get("label") and not figure:
                declared = row.get("figures", [])
                declared = declared if isinstance(declared, list) else []
                figures = [f for f in figures if f.get("id") in declared or row.get("id") in f.get("concepts", [])]
            links = [reference(data, f.get("label", f.get("id", "Figure")), paper=paper, figure=f.get("id"))
                     for f in figures[:3] if f.get("id")]
            if "figure_links" not in frame:
                frame["figure_links"] = None
            gallery = ui.tags.button(f"Open figure gallery ({len(figures)} figures)", type="button", class_="research-open btn btn-sm btn-outline-primary",
                **{"data-root": str(data.root), "data-paper": paper, "data-canonical": cid or "", "data-figure": "", "data-gallery": "true"})
            frame.at[number, "figure_links"] = gallery if len(figures) > 3 else ui.div(*links) if links else "No figure link recorded for this row"
    frame.attrs["dpv_raw_records"] = table(values)
    return frame
