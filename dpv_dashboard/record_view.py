"""Shared, read-only record inspector and bounded research summaries.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import json
import re
import math
from collections import Counter
from shiny import ui
from dpv_dashboard import media, presentation, research, quality


def value(raw):
    if raw is None:
        return "Not recorded"
    if isinstance(raw, (dict, list)):
        return json.dumps(raw, ensure_ascii=False, indent=2)
    return str(raw) if str(raw) else "Not recorded"


def inspector(data, row):
    if not row:
        return ui.p("Select a row to inspect its meaning, evidence, provenance and review findings.", class_="empty-state")
    row = {key: None if isinstance(raw, float) and math.isnan(raw) else raw for key, raw in row.items()}
    cid = row.get("canonical_id") or row.get("id")
    paper = row.get("paper") or row.get("key") or row.get("paper_id")
    title = row.get("label") or row.get("local_label") or row.get("title") or row.get("original_label") or data.papers.get(paper, {}).get("title") or "Selected record"
    if row.get("subject"):
        title = f"{row['subject']} → {presentation.friendly(row.get('predicate', row.get('p', 'related to')))} → {row.get('object', '')}"
    flags = quality.label_issues(str(title))
    if re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", str(title), re.I):
        flags.append("Identifier-like label; inspect the original extraction")
    concept = data.concepts.get(cid, {})
    links = data.by_canonical.get(cid, [])
    trace = [ui.div(ui.p(f"{link.get('original_label', link.get('original_id', 'Original term unavailable'))} → {data.label(cid)}"),
                    ui.p("Link: " + str(presentation.friendly(link.get("lineage_status", "not_recorded"))), class_="muted"),
                    media.reference(data, "Source paper", canonical=cid, paper=link.get("paper"))) for link in links[:20]]
    aliases = concept.get("alt_labels", [])
    alias_notes = []
    for alias in aliases if isinstance(aliases, list) else []:
        if not isinstance(alias, str):
            alias_notes.append("Non-text alternative label needs review")
            continue
        if quality.label_issues(alias) or re.match(r"^F\d+\s*:", alias):
            alias_notes.append("Potential caption or malformed alternative label: " + quality.bounded(alias))
        matching = [data.label(key) for key, other in data.concepts.items() if key != cid and isinstance(other.get("label"), str)
                    and other["label"].strip().casefold() == alias.strip().casefold()]
        if matching:
            alias_notes.append("Alternative label also names another canonical concept: " + quality.bounded(alias))
    details = [ui.tags.details(ui.tags.summary(presentation.heading(k)), media.reference_text(data, value(v), paper)) for k, v in row.items()]
    evidence = row.get("quote") or row.get("parent_evidence")
    lineage = row.get("lineage_status")
    return ui.card(ui.card_header("Record inspector"), ui.h4(quality.bounded(str(title), 240)),
        ui.p("This label needs quality review: " + "; ".join(flags), class_="review-alert") if flags else None,
        ui.h5("Evidence"), ui.tags.blockquote(value(evidence)) if evidence else ui.p("No supporting quote is recorded in this row."),
        ui.p("Quote status: " + str(presentation.friendly(row.get("verification", "not_recorded")))),
        ui.p("Quote matching identifies text in the source; it does not independently validate the claim.", class_="muted"),
        ui.h5("Provenance"), ui.p("Source: " + (presentation.run_label(data.root) if data.root else "Not recorded")),
        ui.p("Class → canonical concept → original term → paper → page/figure. Only saved links or explicitly marked reconstructed links are available.", class_="trace-breadcrumb"),
        ui.p("Mapping: " + str(presentation.friendly(lineage))) if lineage else None,
        media.reference(data, "Open source paper and figures", canonical=cid, paper=paper),
        ui.tags.details(ui.tags.summary(f"Original terms and supporting papers · {len(links)} links"), *trace,
                        ui.p("Showing up to 20 links. The Evidence & provenance page contains the complete trace.")) if links else None,
        ui.tags.details(ui.tags.summary("Meaning and ontology context"),
            ui.p("Definition: " + value(row.get("definition") or row.get("local_definition") or concept.get("definition"))),
            ui.p("Parent: ", media.reference_text(data, concept.get("parent"), paper)) if concept.get("parent") else ui.p("Parent not recorded"),
            ui.p("Alternative labels: " + value(concept.get("alt_labels"))),
            ui.p("Placement: " + str(presentation.friendly(concept.get("parent_source", "not_recorded"))))),
        ui.div(ui.div(ui.h5("Local meaning"), ui.p(value(row.get("local_label"))), ui.p(value(row.get("local_definition")))),
               ui.div(ui.h5("External meaning"), ui.p(media.external_reference(value(row.get("external_label")), row.get("external_iri"))), ui.p(value(row.get("external_definition")))), class_="connection-columns") if row.get("external_label") else None,
        ui.p("Confidence is a saved model assessment or matching score, not a calibrated probability of correctness.", class_="muted") if row.get("confidence") is not None else None,
        ui.h5("Review"), ui.p(value(row.get("review_flags") or row.get("flags") or "No review flags recorded in this row")),
        *(ui.p(note, class_="review-alert") for note in alias_notes[:10]),
        ui.tags.details(ui.tags.summary("All fields, identifiers and technical metadata"), *details), class_="record-inspector")


def priorities(rows):
    """Count findings separately from affected concepts; do not invent severity."""
    issues = Counter()
    concepts = set()
    for row in rows:
        identity = row.get("canonical_id") or row.get("id") or row.get("iri")
        if identity:
            concepts.add((str(row.get("source_run", "")), str(row.get("paper", "")), str(identity)))
        flags = row.get("review_flags") or row.get("flags") or row.get("issue") or row.get("kind") or "Unclassified finding"
        if isinstance(flags, str):
            try:
                flags = json.loads(flags) if flags.startswith("[") else [flags]
            except ValueError:
                flags = [flags]
        for flag in flags if isinstance(flags, list) else [flags]:
            issues[str(presentation.friendly(str(flag)))] += 1
    return ui.div(ui.p(f"{len(rows):,} saved finding records affecting {len(concepts):,} identified concepts. Findings can repeat across sources; counts are not severity scores."),
        *(ui.p(f"{name}: {count:,}") for name, count in issues.most_common(5)), class_="review-priorities")


def compare(current, baseline, stage):
    """Compare saved counts only; labels never establish identity across runs."""
    from numbers import Real
    _, now = current.progress(stage)
    _, before = baseline.progress(stage)
    counts = [ui.p(f"{presentation.friendly(key)}: {before[key]:,} → {number:,} ({number - before[key]:+,})")
              for key, number in now.items() if isinstance(number, Real) and isinstance(before.get(key), Real)]
    def vocabulary(data):
        records = data.originals.values() if stage == "extract" else data.concepts.values()
        return {r["label"].strip() for r in records if isinstance(r.get("label"), str) and r["label"].strip()}
    names, old = vocabulary(current), vocabulary(baseline)
    return ui.div(ui.p("Baseline: " + presentation.run_label(baseline.root)), *counts,
        ui.p(f"Exact vocabulary labels: {len(names - old):,} added; {len(old - names):,} no longer present; {len(names & old):,} shared.") if stage in ("extract", "normalize", "ontology", "enrich") else None,
        ui.p("Counts reflect saved artifacts and may differ with corpus size, model or configuration. Label differences do not establish new concepts, deletions, or merge decisions.", class_="muted"))
