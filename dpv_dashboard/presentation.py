"""Readable display labels; source keys and artifacts remain unchanged.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import json
import re
from shiny import render, ui

STAGES = {"ingest": "Zotero ingestion", "parse": "PDF parsing", "extract": "Evidence extraction", "normalize": "Normalization",
          "ontology": "Ontology placement", "enrich": "Enrichment", "interop": "Interoperability", "integrate": "Integration",
          "reports": "Reports & figures", "review": "Review findings", "execution": "Run activity", "other": "Other files"}
HEADINGS = {"canonical_id": "Canonical concept ID", "original_id": "Original concept ID", "id": "Record ID", "key": "Paper ID",
            "result_id": "Result", "iri": "Ontology identifier", "parent_id_or_iri": "Parent identifier",
            "a_label": "First concept", "b_label": "Second concept", "a_domain": "First domain", "b_domain": "Second domain",
            "a_run": "First source run", "b_run": "Second source run", "a_iri": "First ontology identifier", "b_iri": "Second ontology identifier",
            "lineage_status": "Mapping provenance", "match_basis": "How the link was established", "bytes": "Size in bytes",
            "type": "Concept type", "kind": "Record type", "s": "Subject", "p": "Relationship", "o": "Object"}
TERMS = {"type_default": "Default placement by concept type", "name_match": "Matching class name",
         "malformed_label": "Concept label is missing or invalid", "label_too_long": "Concept label exceeds the length limit",
         "label_word_limit": "Concept label contains too many words", "repeated_label_text": "Concept label contains looping text",
         "malformed_alias": "An alternative label is invalid", "extraction_quarantined": "Record withheld for quality review",
         "excluded_source_record": "Source record was excluded",
         "name_match_category_conflict": "Name match conflicts with concept category", "unsupported_definition": "Definition needs supporting evidence",
         "candidate_screened_out": "Candidate excluded during review", "model_generated": "AI-generated", "generated": "AI-generated",
         "unresolved_parent_answer": "Parent class needs review", "restriction_dropped": "Proposed restriction omitted",
         "unresolved_relation_end": "Relationship endpoint unresolved", "unanswered_row": "No model answer recorded",
         "mapping_downgraded": "Mapping reduced during review", "name_match_no_bfo_route": "Upper-ontology placement unresolved",
         "disjointness_dropped": "Disjointness proposal omitted", "model_only": "AI-generated without independent support",
         "imported": "Imported from an ontology", "supported": "Supported by paper evidence",
         "none": "Not provided", "not_recorded": "Not recorded", "completed_with_warnings": "Completed with review findings",
         "completed_with_deterministic_fallback": "Completed using a rule-based fallback", "unverified": "Quote not verified",
         "unevidenced": "Supporting quote missing", "verified": "Quote matched source text", "recorded": "Recorded mapping",
         "running": "In progress", "waiting": "Waiting", "completed": "Completed", "failed": "Needs attention",
         "pending": "Pending", "reconstructed": "Reconstructed link", "ambiguous": "Unresolved link"}
TERMS.update({"draft_evidence": "Draft definition awaiting evidence review", "category_default": "Fallback to concept category",
              "lexical_head": "Placement using the term's head word", "paper_is_a": "Placement from a paper's class relationship",
              "llm": "AI-proposed placement", "unresolved_placement": "Placement needs review",
              "definition_category_conflict": "Definition conflicts with concept category", "model": "Model assessment"})
ENUM_FIELDS = {"stage", "status", "definition_status", "placement_source", "kind", "review_flags", "flags", "verification", "decision", "evidence_status", "predicate", "relation", "method"}


def heading(key):
    if key in {"reduction", "text_reduction"}:
        return "Text removed (%)"
    if key == "parse_s":
        return "Parsing time (seconds)"
    if key in HEADINGS:
        return HEADINGS[key]
    words = str(key).replace("_", " ").strip().split()
    acronyms = {"id", "iri", "pdf", "doi", "bfo", "cco", "rdf", "csv", "ttl", "json"}
    return " ".join(w.upper() if w.lower() in acronyms else w.capitalize() if i == 0 else w for i, w in enumerate(words)) or "Unnamed field"


def friendly(value):
    if not isinstance(value, str):
        return value
    return TERMS.get(value, STAGES.get(value, value.replace("_", " ") if re.fullmatch(r"[a-z][a-z0-9_]+", value) else value))


def prose(text):
    return re.sub(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b", lambda m: TERMS.get(m[0], m[0]), str(text))


def grid(frame, compact=False, **kwargs):
    original = frame.attrs.get("dpv_raw_records", frame).copy()
    if compact:
        technical = {"id", "canonical_id", "original_id", "subject_id", "object_id", "iri", "target_iri", "parent_id_or_iri",
                     "a_iri", "b_iri", "a_run", "b_run", "source_run", "scores", "source_definitions", "parent_evidence"}
        if any(c in frame for c in ("title", "label", "subject")):
            technical |= {"paper", "key", "paper_id"}
        keep = [c for c in frame.columns if c not in technical]
        if keep:
            frame = frame[keep]
    shown = frame.copy()
    for column in shown.columns:
        if column in {"reduction", "text_reduction"}:
            shown[column] = shown[column].map(lambda v: round(v * 100, 1) if isinstance(v, (float, int)) else v)
        if column in {"excluded", "verified", "reviewed", "cycle_detected", "property_missing"}:
            shown[column] = shown[column].map(lambda v: "Yes" if v is True else "No" if v is False else v)
        if column in ENUM_FIELDS:
            def value(raw):
                if not isinstance(raw, str):
                    return raw
                if raw.startswith("["):
                    try:
                        items = json.loads(raw)
                        if isinstance(items, list) and all(isinstance(i, str) for i in items):
                            return "; ".join(str(friendly(i)) for i in items) or "None"
                    except (ValueError, TypeError):
                        pass
                return friendly(raw)
            shown[column] = shown[column].map(value)
        if column == "field":
            shown[column] = shown[column].map(lambda v: heading(v) if isinstance(v, str) else v)
        if column in {"alt_labels", "alternative_labels", "papers", "synonyms"}:
            def labels(raw):
                try:
                    items = json.loads(raw) if isinstance(raw, str) and raw.startswith("[") else raw
                    if compact and column in {"alt_labels", "alternative_labels", "synonyms"} and isinstance(items, list) and len(items) > 2:
                        return ui.tags.details(ui.tags.summary(f"{len(items)} alternative labels"), ui.p("; ".join(str(i) for i in items)))
                    return "; ".join(str(i) for i in items) if isinstance(items, list) else raw
                except (ValueError, TypeError):
                    return raw
            shown[column] = shown[column].map(labels)
    labels = {}
    for column in shown.columns:
        name = heading(column)
        if name in labels:
            name += " (additional)"
        labels[name] = column
    shown.columns = list(labels)
    shown.attrs["dpv_source_columns"] = labels
    shown.attrs["dpv_source_records"] = original
    return render.DataGrid(shown, **kwargs)


def selected(renderer):
    original = renderer.data()
    values = renderer.data_view(selected=True)
    source = original.attrs.get("dpv_source_records")
    if source is not None:
        return source.loc[values.index].copy()
    return values.rename(columns=original.attrs.get("dpv_source_columns", {}))


def run_label(path):
    name = path.name
    match = re.fullmatch(r"(.+)-n(\d+)-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", name)
    if not match:
        return name.replace("_", " ")
    title, count, year, month, day, hour, minute, second = match.groups()
    size = f"{count} per domain" if title == "integration" else f"{count} papers"
    return f"{title.replace('-', ' ').title()} · {size} · {year}-{month}-{day} {hour}:{minute}:{second}"


def ontology_label(path):
    name = path.name
    if name == "ontology.ttl":
        return "Domain ontology"
    if name == "domain_layer.ttl":
        return "Literature claims"
    if name.endswith("_merged.ttl"):
        return "Merged domain ontologies"
    return "Integrated ontology" if "_" in path.stem else path.stem.replace("-", " ").title()


def stage_step(stage, number, status, style=None):
    if stage not in STAGES or stage in {"review", "execution", "other"}:
        raise ValueError("Choose one of the nine workflow stages.")
    return ui.tags.button(ui.span(f"{number:02d}"), ui.span(STAGES[stage]), ui.tags.small(friendly(status)),
        type="button", class_=f"pipeline-step {style or status}",
        **{"data-stage": stage, "aria-label": f"Open {STAGES[stage]} details. Status: {friendly(status)}"})


def growth_note():
    return ui.div(ui.strong("How to read Concept growth"),
        ui.p(ui.span(style="display:inline-block;width:28px;border-top:3px solid #526854;margin-right:8px;vertical-align:middle", **{"aria-hidden": "true"}), "Solid line: distinct canonical concepts accumulated in citation order."),
        ui.p(ui.span(style="display:inline-block;width:28px;height:14px;background:#dce7dc;margin-right:8px;vertical-align:middle", **{"aria-hidden": "true"}), "Shaded band: the 5th–95th percentile of concept counts when the same papers are repeatedly shuffled into random orders—the middle 90% of those results at each paper count."),
        ui.p("A wider band means paper order changes how quickly concepts accumulate. A line above the band finds concepts faster than most random orders; below it, slower. All orders reach the same final total when every paper is included."),
        ui.p("The shading shows paper-order variability, not uncertainty about concept correctness or a statistical confidence interval. A line inside the band does not prove order has no effect. Each domain's line and band use the same color."),
        class_="growth-explanation", style="padding:16px;border-left:4px solid #ffc904;background:#f5f6f1;color:#202720;line-height:1.6;margin:16px 0")


def report_html(text, asset_url=None):
    """Add a dashboard-only interpretation; never rewrite saved reports or images."""
    def explain(match):
        figure = match[0]
        if "concept_growth.csv" not in figure and "Concept growth and saturation" not in figure:
            return figure
        figure = figure.replace("so a line inside the band means the order of papers does not matter.",
                                "a line inside the band is consistent with the variation caused by changing paper order.")
        return figure.replace("</figcaption>", "</figcaption>" + str(growth_note()), 1)
    text = re.sub(r"<figure\b[^>]*>.*?</figure>", explain, text, flags=re.S)
    if asset_url:
        from html import escape, unescape
        def image(match):
            url = asset_url(unescape(match[2]))
            return match[1] + escape(url, quote=True) + match[3] if url else match[0]
        text = re.sub(r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'])', image, text, flags=re.I)
    style = """<style>
    body{font:15px/1.65 'Segoe UI',sans-serif!important;color:#20291f!important;background:#fff!important;
      max-width:none!important;margin:0!important;padding:18px 22px!important}
    h1{font-size:26px;line-height:1.25;border-left:5px solid #ffc904;padding-left:14px;margin:0 0 18px}
    h2{font-size:21px;margin:26px 0 12px!important;border-bottom:2px solid #e4e8de;padding-bottom:8px}
    h3{font-size:17px;margin:18px 0 8px}nav{background:#f4f6ef!important;border-left:4px solid #ffc904;padding:12px 18px}
    table{width:100%;font-size:13px;border-collapse:collapse}th{background:#eef2e8;font-weight:600}
    th,td{padding:9px 12px!important;border-bottom:1px solid #dde3d6!important;color:#20291f}
    tr:nth-child(even){background:#f8faf5}figure{margin:18px 0!important;padding:12px;border:1px solid #e4e8de;border-radius:8px}
    figcaption{font-style:normal!important;font-size:13px}.note{background:#fff6d5!important;color:#20291f}
    a{color:#715500}img{display:block;max-width:100%;height:auto;margin:auto}
    </style>"""
    return text.replace("</head>", style + "</head>", 1) if "</head>" in text else style + text
