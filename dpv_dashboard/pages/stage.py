"""Reusable stage-page module with readable summaries and scoped artifact inspection.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
import pandas as pd
from shiny import module, reactive, render, ui
from dpv_dashboard import model, external, research, media, catalog
from dpv_dashboard.auth import redact
from dpv_dashboard import presentation, record_view
from dpv_dashboard.inspect import summary, table
from dpv_dashboard.pages.research import research_ui, research_server

PURPOSES = {
    "ingest": "Choose the literature that informs each domain. Review the selected papers and configure libraries, collections and paper limits.",
    "parse": "Check whether papers and figures were read successfully. Inspect parsing coverage and open source papers to investigate gaps.",
    "extract": "Explore what the literature reports. Select an evidence row to inspect its claim, supporting quote and source paper.",
    "normalize": "Understand how terminology was consolidated. Trace original terms to canonical concepts and inspect ambiguous links or contradictions.",
    "ontology": "See where concepts fit in the ontology. Compare parent concepts, placement rationale and decisions needing review.",
    "enrich": "See what meaning and connections were added. Inspect definition sources, restrictions and review findings before accepting them.",
    "interop": "Compare your vocabulary with external ontologies. Read local and external meanings together before accepting a mapping.",
    "integrate": "Discover connections between domains. Explore bridge concepts, compare connected terms and follow their original evidence.",
    "reports": "Understand the overall findings. Read the report, browse key figures and download the results you need.",
}


@module.ui
def stage_ui(stage, lead=None):
    index = model.STAGES.index(stage)
    return ui.nav_panel(f"{index + 1}. {model.TITLES[index]}",
        ui.div(ui.p(f"STAGE {index + 1:02d}", class_="eyebrow"), ui.h2(model.TITLES[index]),
               ui.p(PURPOSES[stage], class_="page-purpose"),
               ui.output_ui("overview"), class_="stage-heading"),
        lead if lead is not None else None,
        ui.output_ui("status"),
        ui.div(ui.tags.details(ui.tags.summary("Run controls"),
            ui.p("Run or restart this stage in a dashboard project. Saved external runs are read-only."),
            ui.div(ui.input_action_button("run", "Run stage", class_="btn-primary"), ui.input_action_button("restart", "Restart stage"), class_="button-row")),
            **({"style": "display:none"} if model.viewer() else {})),
        research_ui("research", stage) if stage != "reports" else None,
        ui.output_ui("report_library") if stage == "reports" else None,
        ui.card(ui.card_header("Report & findings"), ui.output_ui("visual"), fill=False, class_="report-summary") if stage == "reports" else None,
        ui.tags.details(ui.tags.summary("What needs attention"), ui.output_ui("notes"), open=True),
        ui.tags.details(ui.tags.summary("Compare result counts with another saved run"),
            ui.input_select("baseline", "Comparison baseline", choices={"": "Choose a saved baseline"}), ui.output_ui("comparison")),
        ui.tags.details(ui.tags.summary("Files & technical details"),
        research_ui("research", stage) if stage == "reports" else None,
        ui.layout_columns(
            ui.card(ui.card_header("Intermediate files"), ui.input_select("file", "Artifact", choices={}),
                    ui.input_select("section", "Table section", choices={}), ui.download_button("download", "Download selected file")),
            ui.card(ui.card_header("Artifact preview"), ui.input_checkbox("artifact_technical", "Show technical artifact columns", False),
                    ui.output_ui("visual") if stage != "reports" else None, ui.output_data_frame("results")), col_widths=(4, 8)),
        ui.accordion(ui.accordion_panel("Raw artifact preview", ui.output_code("raw")), open=False)), value=stage)


@module.server
def stage_server(input, output, session, stage, context):
    research_server("research", stage, context)
    baseline_choices = reactive.Value({})

    @reactive.effect
    def baselines():
        import re
        context.tick()
        root = context.folder(stage)
        scope = lambda p: re.sub(r"-n\d+-\d{8}-\d{6}$", "", p.name)
        choices = {str(p): presentation.run_label(p) for p in context.comparison_roots() if root and p != root and scope(p) == scope(root)}
        with reactive.isolate():
            previous, selected = baseline_choices.get(), input.baseline()
        if choices != previous:
            baseline_choices.set(choices)
            ui.update_select("baseline", choices={"": "Choose a saved baseline", **choices}, selected=selected if selected in choices else "")

    @render.ui
    def comparison():
        selected = input.baseline()
        if selected not in baseline_choices.get():
            return ui.p("Select a baseline explicitly. Comparisons use saved counts and exact vocabulary labels; they do not infer semantic equivalence.")
        return record_view.compare(research.index(context.folder(stage)), research.index(Path(selected)), stage)
    @reactive.calc
    def folder():
        return context.folder(stage)

    signature = reactive.Value(None)

    @reactive.effect
    def poll_artifacts():
        context.tick()
        root = folder()
        value = [(str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in context.files(root, stage)]
        with reactive.isolate():
            previous = signature.get()
        if value != previous:
            signature.set(value)

    @reactive.effect
    def choices():
        signature.get()
        root = folder()
        options = {str(p.relative_to(root)): str(p.relative_to(root)) for p in context.files(root, stage)} if root else {}
        selected = input.file()
        preferred = {"normalize": "corpus_report.md", "ontology": "ontology/classes.json", "enrich": "ontology/enriched.json",
                     "interop": "ontology_report.md", "integrate": "integration_report.md", "reports": "report.html"}.get(stage, "")
        if stage == "reports":
            preferred = next((key for suffix in ("report.html", "report.md") for key in options
                              if key.replace("\\", "/").endswith(suffix)), preferred)
        preferred = next((key for key in options if key.replace("\\", "/") == preferred.replace("\\", "/")),
                         next((key for key in options if stage == "extract" and key.replace("\\", "/").startswith("papers/")), next(iter(options), "")))
        ui.update_select("file", choices=options, selected=selected if selected in options else preferred)

    @reactive.calc
    def selected_file():
        signature.get()
        root, relative = folder(), input.file()
        if not root or not relative:
            return None
        path = model.inside(root, relative)
        if path not in context.files(root, stage):
            return None
        return path

    @reactive.calc
    def document():
        path = selected_file()
        return model.read(path) if path and path.suffix == ".json" else None

    @reactive.effect
    def sections():
        data = document()
        options = {"__root__": "Overview"}
        if isinstance(data, dict):
            options.update({k: k.replace("_", " ").title() for k, v in data.items() if isinstance(v, (dict, list))})
        previous = input.section()
        preferred = next((k for k in ("papers", "concepts", "sections", "mappings") if k in options), "__root__")
        ui.update_select("section", choices=options, selected=previous if previous in options and previous != "__root__" else preferred)

    @render.ui
    def overview():
        context.tick()
        record = context.monitored()
        if record and record["kind"] == "sweep":
            return ui.p(external.summary(folder(), stage, record["kind"]), class_="summary-paragraph")
        return ui.p(presentation.prose(research.index(folder()).narrative(stage)), class_="summary-paragraph")

    @render.ui
    def status():
        context.tick()
        root = folder()
        record = context.monitored()
        if record:
            status = external.states(root, record["kind"])[stage]
            return ui.div(ui.span(status.title(), class_="status"), ui.span("Read-only · " + root.name, class_="muted"))
        state = model.read(root / "dashboard.json", {}) if root else {}
        status = state.get("stages", {}).get(stage, {}).get("status", "waiting")
        project = context.project()
        if stage in ("integrate", "reports") and project:
            state = model.read(model.project_path(project["id"]) / "dashboard.json", {})
            status = state.get("stages", {}).get(stage, {}).get("status", "waiting")
        if stage == "integrate" and root:
            status = "outdated" if project.get("integration_stale") else "completed"
        if stage == "reports" and root and (root / "report.html").is_file():
            status = "outdated" if project.get("report_stale") else "completed"
        if state.get("stages", {}).get(stage, {}).get("status") in ("running", "failed", "cancelled", "interrupted"):
            status = state["stages"][stage]["status"]
        return ui.div(ui.span(status.title(), class_=f"status status-{status}"),
                      ui.span(root.name if root else "No attempt yet", class_="muted"), class_="button-row")

    @render.ui
    def notes():
        context.tick()
        root = folder()
        data = research.index(root)
        findings = ([{"id": r.get("subject_id"), "paper": r.get("paper"), "flags": [r.get("verification", "not_recorded")]}
                     for r in data.claims() if r.get("verification") != "verified"] if stage == "extract" else data.review_rows(stage))
        return ui.div(record_view.priorities(findings),
                      ui.input_action_button("review", "Inspect review findings"),
                      ui.p("Restart creates a new stage attempt. Previous outputs remain available in attempt history."))

    @reactive.effect
    @reactive.event(input.review)
    def review():
        scope = session.make_scope("research")
        ui.update_select("view", selected="claims" if stage == "extract" else "review", session=scope)
        if stage == "extract":
            ui.update_checkbox("needs_review", value=True, session=scope)

    @render.ui
    def report_library():
        if stage != "reports":
            return None
        root = folder()
        if root is None:
            return ui.p("Select a run to browse its reports and figures.")
        files = [p for p in root.rglob("*") if p.is_file() and p.resolve().is_relative_to(root.resolve())
                 and not catalog.restricted(p) and p.suffix.lower() in (".md", ".html", ".png", ".jpg", ".jpeg")
                 and "cache" not in p.relative_to(root).parts]
        cards = []
        for path in sorted(files, key=lambda p: (p.suffix.lower() not in (".png", ".jpg", ".jpeg"), str(p)))[:100]:
            relative = path.relative_to(root).as_posix()
            url = media.register(path)
            cards.append(ui.card(ui.h5(path.stem.replace("_", " ")),
                ui.tags.img(src=url, alt=path.stem, loading="lazy", class_="report-thumbnail") if path.suffix.lower() in (".png", ".jpg", ".jpeg") else ui.p("Saved report"),
                ui.p("Shading: 5th–95th percentile across random paper orders. Open Preview for the full explanation.") if path.stem == "concept_growth" else None,
                ui.p(relative, class_="muted"), ui.tags.button("Preview", type="button", class_="report-open btn btn-outline-primary",
                    **{"data-input": session.ns("report_file"), "data-file": relative}),
                ui.tags.a("Download", href=url, download=path.name, class_="ms-3")))
        return ui.card(ui.card_header("Figures & report downloads"), ui.p(f"{len(files)} reports and images; showing {min(len(files), 100)}. Preview a figure here, or read the report below. All artifacts retains the complete inventory."),
                       ui.div(*cards, class_="report-library") if cards else ui.p("No report documents or images saved yet. Metrics and intermediate outputs remain available below."), fill=False, class_="report-figure-library")

    def report_document(path):
        """Resolve report image paths against its own folder, within the selected run."""
        from urllib.parse import unquote, urlsplit
        def asset_url(value):
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc or not parsed.path:
                return None
            try:
                relative = (path.parent / unquote(parsed.path)).resolve().relative_to(folder().resolve())
                image = catalog.accessible(folder(), relative.as_posix())
                return media.register(image) if image.suffix.lower() in (".png", ".jpg", ".jpeg") else None
            except (ValueError, OSError):
                return None
        return presentation.report_html(path.read_text(encoding="utf-8", errors="replace"), asset_url)

    @reactive.effect
    @reactive.event(input.report_file)
    def preview_report():
        root, relative = folder(), input.report_file()
        if stage != "reports" or root is None or not isinstance(relative, str):
            return
        try:
            path = catalog.accessible(root, relative)
        except ValueError:
            return
        if path.stat().st_size > 10 * 1024 * 1024:
            context.notice("This report exceeds the 10 MB preview limit. Download it from the report library.")
            return
        suffix = path.suffix.lower()
        content = (media.linked_markdown(research.index(folder()), path.read_text(encoding="utf-8", errors="replace")) if suffix == ".md" else
                   ui.tags.iframe(srcdoc=report_document(path), sandbox="", class_="report-frame", title=path.name) if suffix == ".html" else
                   ui.tags.img(src=media.register(path), alt=path.stem, class_="figure-preview") if suffix in (".png", ".jpg", ".jpeg") else None)
        if content is not None:
            if path.stem == "concept_growth":
                content = ui.div(content, presentation.growth_note(), class_="growth-figure-preview")
            ui.modal_show(ui.modal(content, title=path.stem.replace("_", " "), size="xl", easy_close=True))

    @render.data_frame
    def results():
        path = selected_file()
        if not path:
            return presentation.grid(pd.DataFrame(), filters=True)
        try:
            if path.suffix == ".csv":
                frame = pd.read_csv(path, nrows=10000)
                frame = media.rich_table(research.index(folder()), frame.to_dict("records"))
            elif path.suffix == ".json":
                value = document()
                section = input.section()
                if isinstance(value, dict) and section != "__root__":
                    value = value.get(section, value)
                values = value[:10000] if isinstance(value, list) else value
                if isinstance(values, list) and all(isinstance(r, dict) for r in values):
                    if path.parent.name == "papers":
                        values = [{"paper": path.stem, **r} for r in values]
                    frame = media.rich_table(research.index(folder()), values)
                else:
                    frame = table(value)
            elif path.suffix == ".ttl":
                from rdflib import Graph, RDF, RDFS, OWL
                graph = Graph().parse(path, format="turtle")
                frame = media.rich_table(research.index(folder()), [{"label": str(graph.value(c, RDFS.label) or c), "iri": str(c)} for c in graph.subjects(RDF.type, OWL.Class)])
            else:
                frame = pd.DataFrame()
            return presentation.grid(frame.head(10000), compact=not input.artifact_technical(), filters=True, height="480px")
        except Exception:
            return presentation.grid(pd.DataFrame([{"message": "Table preview unavailable; inspect or download the artifact."}]))

    @render.ui
    def visual():
        path = selected_file()
        if not path:
            return ui.p("Saved outputs will appear here.", class_="empty-state")
        if path.suffix == ".ttl":
            return ui.div(ui.p("Explore this ontology with WebVOWL, search and chat on Visual Exploration."),
                          ui.input_action_button("explore", "Open Visual Exploration", class_="btn-primary"))
        if path.suffix == ".png":
            return ui.div(ui.tags.img(src="data:image/png;base64," + base64.b64encode(path.read_bytes()).decode(), class_="figure-preview", alt=path.stem),
                          presentation.growth_note() if path.stem == "concept_growth" else None,
                          class_="growth-figure-preview" if path.stem == "concept_growth" else "")
        if path.suffix == ".html":
            return ui.tags.iframe(srcdoc=report_document(path), sandbox="", title=path.name, class_="report-frame")
        if path.suffix == ".md":
            return ui.div(media.linked_markdown(research.index(folder()), path.read_text(encoding="utf-8")), class_="report-markdown")
        return ui.tags.span()

    @reactive.effect
    @reactive.event(input.explore)
    def explore():
        context.explore(folder(), selected_file())

    @render.code
    def raw():
        path = selected_file()
        if not path:
            return "No artifact selected."
        if path.suffix in (".png", ".pdf"):
            return "Binary artifact; use Download selected file."
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return redact(handle.read(50000))

    @render.download_button(filename=lambda: selected_file().name if selected_file() else "artifact.txt")
    def download():
        path = selected_file()
        if not path:
            raise ValueError("Select a saved artifact first.")
        return str(path)

    @reactive.effect
    @reactive.event(input.run)
    def launch():
        context.launch("stage", stage)

    @reactive.effect
    @reactive.event(input.restart)
    def restart():
        context.launch("restart", stage)
