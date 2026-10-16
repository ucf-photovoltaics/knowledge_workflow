"""Stage-specific research tables and clickable paper/ontology provenance.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from urllib.parse import quote
from shiny import module, reactive, render, ui
from dpv_dashboard import catalog, research, integration, media
from dpv_dashboard import presentation, record_view
from dpv_dashboard.inspect import table

VIEWS = {
    "ingest": {"papers": "Selected papers"}, "parse": {"parsing": "Parsing statistics"},
    "extract": {"papers": "Papers", "claims": "Relations, causal claims & measurements"},
    "normalize": {"concepts": "Canonical vocabulary", "lineage": "Original → canonical lineage", "contradictions": "Contradictions"},
    "ontology": {"placements": "Evidence & placement decisions", "hierarchy": "Root-to-class hierarchy paths"},
    "enrich": {"definitions": "Definitions & source status", "restrictions": "Restrictions & evidence",
               "candidates": "External candidates", "materials_project": "Materials Project enrichments"},
    "interop": {"mappings": "Local ↔ external term comparison"},
    "integrate": {"mappings": "Cross-domain mappings", "bridges": "Bridge concept members", "candidates": "Reviewed & unresolved pairs",
        "sources": "Contributing domains & coverage", "source_papers": "Source papers & figures", "source_figures": "Source figures & captions", "source_evidence": "Source claims & evidence",
        "source_concepts": "Source canonical vocabulary", "source_lineage": "Source normalization lineage",
        "source_placements": "Source placement rationale", "source_definitions": "Source definitions",
        "source_restrictions": "Source restrictions", "source_external": "Source external mappings",
        "source_contradictions": "Source contradictions", "source_review": "Source review findings"},
    "reports": {},
}


@module.ui
def research_ui(stage):
    return ui.card(ui.card_header("Research results & provenance"),
        ui.output_ui("progress"),
        ui.input_select("domain_filter", "Contributing source", choices={"": "All contributing domains"}) if stage == "integrate" else None,
        ui.input_select("view", "Explore", choices={**VIEWS[stage], "review": "Review & validation findings"},
                        selected={"extract": "claims", "integrate": "bridges"}.get(stage)),
        ui.tags.details(ui.tags.summary("Display options"), ui.input_checkbox("technical", "Show identifiers and technical columns", False)),
        ui.input_checkbox("needs_review", "Only evidence needing quote review", False) if stage == "extract" else None,
        ui.input_select("side", "Integration source to inspect", choices={"a": "First concept", "b": "Second concept"}) if stage == "integrate" else None,
        ui.input_action_button("inspect", "Inspect selected row → evidence & provenance", class_="btn-primary"),
        ui.p("Select a row below to see its detail alongside the table, or open its full evidence trace.", class_="muted"),
        ui.layout_columns(ui.output_data_frame("results"), ui.output_ui("record"), col_widths=(8, 4)),
        ui.output_ui("connection") if stage == "integrate" else None)


@module.server
def research_server(input, output, session, stage, context):
    snapshot = reactive.Value(research.index(None))

    @reactive.effect
    def source_choices():
        if stage != "integrate":
            return
        data = snapshot.get()
        choices = {"": "All contributing domains", **{s["source_run"]: s["domain"] + " · " + s["source_run"] for s in integration.sources(data.root)}}
        with reactive.isolate():
            previous = input.domain_filter()
        ui.update_select("domain_filter", choices=choices, selected=previous if previous in choices else "")

    @reactive.effect
    def poll():
        context.tick()
        value = research.index(context.folder(stage))
        with reactive.isolate():
            previous = snapshot.get()
        if previous is not value:
            snapshot.set(value)

    @render.ui
    def progress():
        context.tick()
        data = snapshot.get()
        status, counts = data.progress(stage)
        return ui.div(ui.p("Progress: " + str(presentation.friendly(status))),
                      ui.h5("Inherited domain coverage") if stage == "integrate" else None,
                      ui.p(integration.summary(data.root)) if stage == "integrate" else None,
                      ui.h5("New integration decisions") if stage == "integrate" else None,
                      *(ui.span(f"{presentation.friendly(name)}: {value}", class_="status") for name, value in counts.items()), class_="research-counts")

    @render.data_frame
    def results():
        data = snapshot.get()
        if stage == "integrate" and (input.view() in integration.VIEWS or input.view() in ("sources", "source_review")):
            all_rows = integration.rows(data.root, input.view(), input.domain_filter())
            rows = all_rows[:10000]
            frames = []
            for source in integration.sources(data.root):
                selected = [r for r in rows if r.get("source_run") == source["source_run"]]
                if selected:
                    part = media.rich_table(research.index(source["root"]), selected)
                    part.attrs.clear()
                    frames.append(part)
            import pandas as pd
            frame = pd.concat(frames, ignore_index=True) if frames else table([])
            frame.attrs["dpv_raw_records"] = table([r for source in integration.sources(data.root) for r in rows if r.get("source_run") == source["source_run"]])
            return presentation.grid(frame, compact=not input.technical(), filters=True, selection_mode="row", height="440px", width="100%",
                                     summary=f"Showing {len(frame):,} of {len(all_rows):,} source records; complete files are available in All artifacts.")
        rows = data.review_rows(stage) if input.view() == "review" else data.stage_rows(stage, input.view())
        if stage == "extract" and input.view() == "claims" and input.needs_review():
            rows = [r for r in rows if r.get("verification") != "verified"]
        if stage == "integrate" and input.domain_filter():
            source = next((s for s in integration.sources(data.root) if s["source_run"] == input.domain_filter()), {})
            rows = [r for r in rows if input.domain_filter() in (r.get("a_run"), r.get("b_run")) or
                    source.get("domain") in (r.get("domain"), r.get("a_domain"), r.get("b_domain"))]
        return presentation.grid(media.rich_table(data, rows[:10000]), compact=not input.technical(), filters=True, selection_mode="row", height="440px", width="100%",
                                 summary=f"Showing up to {min(len(rows), 10000):,} of {len(rows):,} saved records. Complete source files are available in All artifacts.")

    @render.ui
    def record():
        selected = presentation.selected(results)
        data = snapshot.get()
        row = selected.iloc[0].to_dict() if not selected.empty else None
        if row and stage == "integrate" and row.get("source_run"):
            source = next((s for s in integration.sources(data.root) if s["source_run"] == row["source_run"]), None)
            if source and source["root"]:
                data = research.index(source["root"])
        return record_view.inspector(data, row)

    @render.ui
    def connection():
        if stage != "integrate":
            return None
        selected = presentation.selected(results)
        if selected.empty:
            return ui.p("Select a connection to compare its saved source records here.")
        row, data = selected.iloc[0].to_dict(), snapshot.get()
        panels = []
        members = [{"iri": row.get(s + "_iri"), "run": row.get(s + "_run"), "domain": row.get(s + "_domain"), "side": s.upper()} for s in ("a", "b")] if row.get("a_iri") else [{**row, "run": row.get("source_run"), "side": "member"}]
        if row.get("bridge_label"):
            members = [{**m, "run": m.get("run_id") or m.get("run"), "side": m.get("domain", "member")}
                       for b in data.bridges if b.get("label") == row["bridge_label"] for m in research.records(b.get("members"))]
        for member in members:
            match = integration.member(data.root, member.get("iri"), member.get("run"), member.get("domain"))
            if not match:
                panels.append(ui.div(ui.h4("Source " + str(member.get("side", "member"))), ui.p("No unique available source class record for this reference.")))
                continue
            source, record, cid = match
            concept = record.concepts[cid]
            links = record.by_canonical.get(cid, [])
            panels.append(ui.card(ui.h4(f"{source['domain']} · {record.label(cid)}"),
                media.reference(record, "Open supporting paper", cid), ui.p(concept.get("definition") or "Definition not recorded."),
                ui.p("Parent: ", media.reference_text(record, concept.get("parent") or "Not recorded")),
                ui.p("Placement method: " + str(presentation.friendly(concept.get("parent_source", "not recorded")))),
                ui.tags.details(ui.tags.summary("Placement evidence"),
                    *(ui.tags.blockquote(e.get("text", "Quote not recorded")) for e in research.records(concept.get("parent_evidence", [])))),
                ui.p("Definition source: " + str(presentation.friendly(concept.get("definition_source", "not recorded"))) + " / " + str(presentation.friendly(concept.get("definition_status", "not recorded")))),
                ui.p("Lineage: " + "; ".join(f"{k}: {v}" for k, v in Counter(r["lineage_status"] for r in links).items())),
                ui.tags.details(ui.tags.summary(f"Restrictions · {len(concept.get('restrictions', []))}"),
                    *(ui.p(str(presentation.friendly(r.get("p", "Relationship not recorded"))) + " → ", media.reference_text(record, r.get("o") or "Not recorded")) for r in research.records(concept.get("restrictions", [])))),
                ui.p("Needs review: " + ("; ".join(str(presentation.friendly(v)) for v in concept.get("review_flags", [])) or "No flags recorded")),
                *(ui.tags.blockquote(str(c.get("quote", ""))) for c in record.claims(canonical=cid)[:3])))
        return ui.div(*panels, class_="connection-columns")

    @reactive.effect
    @reactive.event(input.inspect)
    def inspect():
        selected = presentation.selected(results)
        if selected.empty:
            context.notice("Select a result row first.", error=True)
            return
        row, data = selected.iloc[0].to_dict(), snapshot.get()
        if stage == "integrate":
            if row.get("source_run"):
                source = next((s for s in integration.sources(data.root) if s["source_run"] == row["source_run"]), None)
                if source and source["root"]:
                    record = research.index(source["root"])
                    cid = row.get("canonical_id") or row.get("id")
                    key = row.get("paper")
                    context.inspect(source["root"], canonical=cid if cid in record.concepts else None,
                                    paper=key if key in record.papers else None)
                    return
            side = input.side()
            iri = row.get(side + "_iri") or row.get("iri")
            match = integration.member(data.root, iri, row.get(side + "_run"), row.get(side + "_domain"))
            if match:
                source, record, cid = match
                context.inspect(source["root"], canonical=cid)
                return
            context.notice("The selected integration member has no available source-run class record.", error=True)
            return
        cid = row.get("canonical_id") or row.get("id")
        paper = row.get("paper") or row.get("key")
        cid = cid if isinstance(cid, str) and cid in data.concepts else None
        paper = paper if isinstance(paper, str) and paper in data.papers else None
        if not cid and not paper:
            context.notice("This row has no recorded concept or paper link. Inspect its saved finding in the artifact browser.", error=True)
            return
        context.inspect(data.root, canonical=cid, paper=paper)


@module.ui
def provenance_ui():
    return ui.nav_panel("Evidence & provenance", ui.div(
        ui.p("RESEARCH TRACE", class_="eyebrow"), ui.h2("From ontology result to paper evidence"),
        ui.p("Trace a finding back to the literature. Choose a concept or paper, inspect its quotes and figures, and check whether its lineage was recorded or reconstructed.", class_="page-purpose"),
        ui.input_select("source", "Source run", choices={}),
        ui.input_checkbox("technical", "Show identifiers and technical columns", False),
        ui.layout_columns(ui.input_selectize("concept", "Canonical concept (blank shows the whole paper)", choices={}),
                          ui.input_selectize("paper", "Paper", choices={}), col_widths=(6, 6)),
        ui.output_ui("overview"),
        ui.navset_tab(
            ui.nav_panel("Paper & evidence", ui.output_ui("paper_info"),
                ui.input_select("verification", "Evidence filter", choices={"all": "All verification statuses", "verified": "Verified quotes", "review": "Needs review / not recorded"}),
                ui.output_data_frame("claims"), ui.output_ui("claim_detail")),
            ui.nav_panel("Original → canonical", ui.output_data_frame("lineage"),
                ui.p("Reconstructed links use a matching recorded label/alternative label and paper membership. They do not establish which merge the model approved.", class_="muted")),
            ui.nav_panel("Concepts & figures", ui.h4("Original paper concepts"), ui.output_data_frame("originals"),
                ui.h4("Figure captions and references"), ui.output_data_frame("figures")),
            ui.nav_panel("Ontology context", ui.h4("Canonical and class record"), ui.output_data_frame("ontology"),
                ui.h4("Restrictions, mappings & review"), ui.output_data_frame("connections")),
            ui.nav_panel("Contradictions", ui.output_data_frame("contradictions")), id="detail"), class_="stage-heading"), value="provenance")


@module.server
def provenance_server(input, output, session, context):
    snapshot = reactive.Value(research.index(None))
    source_focus = concept_focus = paper_focus = None
    concept_root = paper_root = None
    tab_focus = None

    @reactive.effect
    def requested_tab():
        nonlocal tab_focus
        focus = context.focused()
        if focus.get("request") != tab_focus and focus.get("tab"):
            ui.update_navset("detail", selected=focus["tab"])
            tab_focus = focus.get("request")

    @reactive.effect
    def sources():
        nonlocal source_focus
        options = {str(root): presentation.run_label(root) for root in context.roots()}
        focus = context.focused()
        with reactive.isolate():
            previous = input.source()
        desired = previous
        if focus.get("request") != source_focus and focus.get("root") in options:
            desired = focus["root"]
            source_focus = focus.get("request")
        ui.update_select("source", choices=options, selected=desired if desired in options else next(iter(options), ""))

    @reactive.effect
    def poll():
        context.tick()
        allowed = {str(root) for root in context.roots()}
        root = input.source()
        value = research.index(Path(root)) if root in allowed else research.index(None)
        with reactive.isolate():
            previous = snapshot.get()
        if value is not previous:
            snapshot.set(value)

    @reactive.effect
    def concepts():
        nonlocal concept_focus, concept_root
        data, focus = snapshot.get(), context.focused()
        options = {"": "All concepts / inspect paper"}
        options.update({cid: f"{c.get('label', cid)} · {cid}" for cid, c in data.concepts.items()})
        with reactive.isolate():
            previous = input.concept()
        desired = previous if concept_root == str(data.root) else ""
        if focus.get("root") == str(data.root) and focus.get("request") != concept_focus:
            desired = focus.get("canonical") or ""
            concept_focus = focus.get("request")
        concept_root = str(data.root)
        ui.update_selectize("concept", choices=options, selected=desired if desired in options else "")

    @reactive.effect
    def papers():
        nonlocal paper_focus, paper_root
        data, cid, focus = snapshot.get(), input.concept(), context.focused()
        supporting = {r["paper"] for r in data.by_canonical.get(cid, [])} if cid else set(data.papers)
        supporting |= set(data.concepts.get(cid, {}).get("papers", []))
        options = {"": "All supporting papers", **{key: f"{paper.get('title', key)[:110]} · {key}"
                   for key, paper in data.papers.items() if key in supporting}}
        with reactive.isolate():
            previous = input.paper()
        desired = previous if paper_root == str(data.root) else ""
        if (focus.get("root") == str(data.root) and focus.get("request") != paper_focus
                and (cid or "") == (focus.get("canonical") or "")):
            desired = focus.get("paper") or ""
            paper_focus = focus.get("request")
        paper_root = str(data.root)
        ui.update_selectize("paper", choices=options, selected=desired if desired in options else "")

    @render.ui
    def overview():
        data, cid = snapshot.get(), input.concept()
        if not data.root:
            return ui.p("Select an existing run or dashboard attempt to inspect its evidence.")
        rows = data.by_canonical.get(cid, []) if cid else data.lineage
        paper = input.paper()
        if paper:
            rows = [row for row in rows if row.get("paper") == paper]
        states = Counter(row["lineage_status"] for row in rows)
        note = "; ".join(f"{status}: {count}" for status, count in states.items()) or "No source mapping available"
        return ui.div(ui.p(note, class_="summary-paragraph"),
                      media.reference(data, data.label(cid), canonical=cid) if cid else None,
                      ui.p("Quote verification indicates a text match in the parsed paper, not that the quote establishes the claim.", class_="muted"))

    @render.ui
    def paper_info():
        data, key = snapshot.get(), input.paper()
        paper = data.papers.get(key)
        if not paper:
            return ui.p("Select a paper to see its metadata, original concepts and figures. The evidence table can span all supporting papers.")
        doi = paper.get("doi", "")
        return ui.div(ui.h4(paper.get("title", key)), ui.p(f"{key} · {paper.get('year', '')} · {paper.get('citations', 'unknown')} citations"),
                      media.reference(data, "Open paper PDF & figures", paper=key),
                      ui.p("Cached extraction reused; run completion does not mean this evidence was regenerated.", class_="muted") if paper.get("cache_hit") else None,
                      ui.tags.a("Open paper DOI", href="https://doi.org/" + quote(doi, safe="/"), target="_blank", rel="noopener noreferrer") if doi else ui.p("No DOI recorded."))

    @render.data_frame
    def claims():
        rows = snapshot.get().claims(input.paper() or None, input.concept() or None)
        status = input.verification()
        if status != "all":
            rows = [row for row in rows if (row["verification"] == "verified") == (status == "verified")]
        return presentation.grid(media.rich_table(snapshot.get(), rows), compact=not input.technical(), filters=True, selection_mode="row", height="440px", width="100%")

    @render.ui
    def claim_detail():
        selected = presentation.selected(claims)
        if selected.empty:
            return ui.p("Select an evidence row to read its complete quote and condition.", class_="muted")
        return record_view.inspector(snapshot.get(), selected.iloc[0].to_dict())

    @render.data_frame
    def lineage():
        data, cid, paper = snapshot.get(), input.concept(), input.paper()
        return presentation.grid(media.rich_table(data, [row for row in data.lineage if (not cid or row.get("canonical_id") == cid)
                                      and (not paper or row.get("paper") == paper)]), filters=True, height="440px", width="100%")

    @render.data_frame
    def originals():
        data, key, cid = snapshot.get(), input.paper(), input.concept()
        allowed = {(r["paper"], r["original_id"]) for r in data.by_canonical.get(cid, [])} if cid else None
        return presentation.grid(media.rich_table(data, [{"paper": paper, **row} for (paper, oid), row in data.originals.items()
                                      if (not key or paper == key) and (allowed is None or (paper, oid) in allowed)]), filters=True, height="350px", width="100%")

    @render.data_frame
    def figures():
        data, key, cid = snapshot.get(), input.paper(), input.concept()
        allowed = {(r["paper"], r["original_id"]) for r in data.by_canonical.get(cid, [])} if cid else None
        rows = []
        for paper, p in data.papers.items():
            if key and key != paper:
                continue
            for figure in research.records(p.get("figures", [])):
                if allowed is not None and not any((paper, c) in allowed for c in figure.get("concepts", [])):
                    continue
                rows.append({"paper": paper, **figure})
        return presentation.grid(media.rich_table(data, rows), filters=True, height="350px", width="100%")

    @render.data_frame
    def ontology():
        data, cid = snapshot.get(), input.concept()
        concept = data.concepts.get(cid, {})
        return presentation.grid(table(concept), filters=True, height="400px", width="100%")

    @render.data_frame
    def connections():
        data, cid = snapshot.get(), input.concept()
        concept = data.concepts.get(cid, {})
        rows = [{"kind": "restriction", **row, "target_label": data.label(row.get("o"))} for row in research.records(concept.get("restrictions", []))]
        rows += [{"kind": "mapping", **row} for row in data.mappings if row.get("id") == cid]
        rows += [{"kind": "review", **row} for row in data.review_rows(canonical=cid)] if cid else []
        return presentation.grid(table(rows), filters=True, height="400px", width="100%")

    @render.data_frame
    def contradictions():
        data, cid = snapshot.get(), input.concept()
        rows = data.stage_rows("normalize", "contradictions")
        if cid:
            rows = [r for r in rows if cid in (r.get("cause"), r.get("effect"))]
        return presentation.grid(table(rows), filters=True, height="400px", width="100%")


