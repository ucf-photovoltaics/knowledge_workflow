"""Complete per-run file inventory with explicit availability and bounded previews.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from pathlib import Path
from shiny import module, reactive, render, ui
from dpv_dashboard import catalog
from dpv_dashboard import presentation
from dpv_dashboard.inspect import table
from dpv_dashboard.auth import redact


@module.ui
def inventory_ui():
    return ui.nav_panel("All artifacts", ui.div(ui.p("OUTPUT COVERAGE", class_="eyebrow"), ui.h2("Complete artifact inventory"),
        ui.p("Find and download every saved output. Filter by stage, select a file, then open its preview or download it.", class_="page-purpose"),
        ui.input_select("source", "Run or report folder", choices={}),
        ui.input_select("stage", "Stage", choices={"all": "All stages", **{s: presentation.STAGES[s] for s in
                        ("ingest", "parse", "extract", "normalize", "ontology", "enrich", "interop", "integrate", "reports", "review", "execution", "other")}}),
        ui.output_ui("overview"),
        ui.p("Select a row, then open its preview. The opened artifact stays selected when new files arrive. Missing/unavailable rows explain coverage gaps; no placeholder files are created.", class_="muted"),
        ui.div(ui.input_action_button("open_artifact", "Open selected artifact"), ui.download_button("download", "Download selected artifact"), class_="button-row"),
        ui.output_data_frame("inventory"), ui.output_ui("selected_info"),
        ui.output_code("preview"), class_="stage-heading"), value="inventory")


@module.server
def inventory_server(input, output, session, context):
    listing = reactive.Value([])
    chosen = reactive.Value(None)

    @reactive.effect
    def roots():
        choices = {str(p): presentation.run_label(p) for p in context.roots()}
        with reactive.isolate():
            previous = input.source()
        ui.update_select("source", choices=choices, selected=previous if previous in choices else next(iter(choices), ""))

    @reactive.calc
    def folder():
        value = input.source()
        return Path(value) if value in {str(p) for p in context.roots()} else None

    @reactive.effect
    def poll():
        context.tick()
        root = folder()
        kind = "integration" if root and (root / "integration.json").is_file() else "run"
        values = [{**row, "source_run": str(root)} for row in catalog.inventory(root, kind, context.superseded(root))]
        with reactive.isolate():
            previous = listing.get()
        if values != previous:
            listing.set(values)

    @render.data_frame
    def inventory():
        stage = input.stage()
        values = [r for r in listing.get() if stage == "all" or r["stage"] == stage]
        return presentation.grid(table(values), compact=True, filters=True, selection_mode="row", height="500px", width="100%")

    @render.ui
    def overview():
        rows = listing.get()
        problematic = sum(r["availability"].startswith(("missing", "unreadable", "unavailable", "empty")) for r in rows)
        return ui.p(f"{len(rows)} inventory entries; {problematic} missing, unavailable, empty or unreadable. Completion is taken from saved manifests; superseded status is used only when recorded attempt history establishes it.", class_="summary-paragraph")

    @reactive.effect
    @reactive.event(input.open_artifact)
    def choose():
        with reactive.isolate():
            data = presentation.selected(inventory)
            root = folder()
        if data.empty or root is None:
            return
        row = data.iloc[0]
        if row.get("source_run") != str(root):
            return
        value = (str(root), row.get("path"))
        with reactive.isolate():
            previous = chosen.get()
        if value != previous:
            chosen.set(value)

    @reactive.calc
    def selected():
        value = chosen.get()
        if not value or value[0] != str(folder()):
            return None
        relative = value[1]
        if relative not in {r["path"] for r in listing.get()}:
            return None
        try:
            return catalog.accessible(folder(), relative)
        except ValueError:
            return None

    @render.ui
    def selected_info():
        path = selected()
        return ui.div(ui.p("Selected artifact: " + str(path.relative_to(folder())) if path else "Select an available, unrestricted file to preview or download."),
                      ui.tags.details(ui.tags.summary("Source location"), ui.tags.code(str(folder()))))

    @render.code
    def preview():
        path = selected()
        if not path:
            return "Unavailable rows and credential files cannot be downloaded."
        if path.suffix.lower() not in (".json", ".jsonl", ".log", ".txt", ".md", ".csv", ".ttl", ".jsonld", ".html", ".xml"):
            return "Binary or unsupported text format. Download the original artifact for inspection."
        try:
            with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
                return redact(handle.read(40000))
        except OSError:
            return "This file became unavailable while being read. Refresh the inventory."

    @render.download_button(filename=lambda: selected().name if selected() else "artifact.txt")
    def download():
        path = selected()
        if path is None:
            raise ValueError("Select an available, unrestricted artifact.")
        return str(path)
