"""Asynchronous Zotero browsing and domain configuration module.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from shiny import module, reactive, render, ui
from dpv_dashboard.auth import credentials
from dpv_dashboard.zotero import Libraries
from dpv_dashboard import model
from dpv_dashboard.inspect import table

EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dpv-zotero")


@module.ui
def browse_ui():
    return ui.div(ui.layout_columns(
        ui.card(ui.card_header("Browse Zotero"),
                ui.input_action_button("discover", "Discover libraries", class_="btn-primary"),
                ui.input_selectize("libraries", "Personal and group libraries", choices={}, multiple=True),
                ui.input_action_button("load", "Load collections"),
                ui.input_selectize("collections", "Collections to assign (includes subcollections)", choices={}, multiple=True),
                ui.input_action_button("preview", "Preview selected collections"), ui.output_ui("browse_status")),
        ui.card(ui.card_header("Build a domain"),
                ui.input_text("domain", "Domain name", placeholder="Reliability and degradation"),
                ui.input_numeric("limit", "Top-cited papers across this domain", 30, min=1, max=10000),
                ui.input_select("profile", "Model connection", choices={"ollama": "Local Ollama", "ollama-lora": "Local Ollama · fine-tuned", "vllm": "Local vLLM",
                    "gemini": "Google Gemini", "gemini-lite": "Google Gemini · lightweight", "deepseek": "DeepSeek", "groq": "Groq", "anthropic": "Anthropic"}),
                ui.input_numeric("workers", "Paper / batch workers", 2, min=1, max=8),
                ui.input_action_button("add", "Add domain to project", class_="btn-primary"),
                ui.p("Duplicates with the same DOI are combined. Citation ranking and PDF acquisition happen when ingestion runs.", class_="muted")), col_widths=(6, 6)),
        ui.card(ui.card_header("Project domains"), ui.output_data_frame("domains")),
        ui.accordion(ui.accordion_panel("Zotero paper preview", ui.output_data_frame("preview_table")), open=False))


@module.server
def browse_server(input, output, session, context):
    libraries = reactive.Value({})
    collections = reactive.Value({})
    preview_rows = reactive.Value([])
    task = reactive.Value(None)
    message = reactive.Value("Discover libraries to verify the saved API key and browse its accessible libraries.")

    def submit(kind, function):
        if task.get():
            raise ValueError("A Zotero request is running. Wait for it to finish.")
        task.set((kind, EXECUTOR.submit(function)))
        message.set("Contacting Zotero…")

    def api():
        return Libraries(credentials().get("ZOTERO_API_KEY", ""))

    @reactive.effect
    def poll():
        pending = task.get()
        if not pending:
            return
        reactive.invalidate_later(0.5)
        kind, future = pending
        if not future.done():
            return
        task.set(None)
        try:
            rows = future.result()
            if kind == "libraries":
                values = {f"{r['type']}:{r['id']}": r for r in rows}
                libraries.set(values)
                collections.set({})
                ui.update_selectize("libraries", choices={k: f"{v['name']} ({v['type']})" for k, v in values.items()}, selected=[])
                ui.update_selectize("collections", choices={}, selected=[])
                message.set(f"Zotero access verified. {len(rows)} accessible libraries found.")
            elif kind == "collections":
                values = {f"{r['library']['type']}:{r['library']['id']}:{r['key']}": r for r in rows}
                collections.set(values)
                ui.update_selectize("collections", choices={k: f"{v['library']['name']} / {v['name']}" for k, v in values.items()}, selected=[])
                message.set(f"Loaded {len(rows)} collections. Select collections across any of these libraries.")
            else:
                preview_rows.set(rows)
                message.set(f"Preview contains {len(rows)} item memberships including subcollections; ingestion will deduplicate and rank them.")
        except Exception as exc:
            message.set(str(exc))

    @reactive.effect
    @reactive.event(input.discover)
    def discover():
        try:
            submit("libraries", lambda: api().libraries())
        except Exception as exc:
            context.notice(str(exc), error=True)

    @reactive.effect
    @reactive.event(input.load)
    def load():
        try:
            selected = [libraries.get()[k] for k in input.libraries() if k in libraries.get()]
            if not selected:
                raise ValueError("Select at least one library.")
            def fetch():
                client = api()
                return [c for library in selected for c in client.collections(library)]
            submit("collections", fetch)
        except Exception as exc:
            context.notice(str(exc), error=True)

    @reactive.effect
    @reactive.event(input.preview)
    def preview():
        try:
            selected = [collections.get()[k] for k in input.collections() if k in collections.get()]
            if not selected:
                raise ValueError("Select collections to preview.")
            def fetch():
                client = api()
                result = []
                for collection in client.expand(selected):
                    for row in client.pages(client.prefix(collection["library"]) + f"/collections/{collection['key']}/items/top"):
                        data = row["data"]
                        if data.get("itemType") not in ("attachment", "note", "annotation"):
                            result.append({"title": data.get("title", ""), "doi": data.get("DOI", ""),
                                           "year": data.get("date", ""), "library": collection["library"]["name"], "collection": collection["name"]})
                return result
            submit("preview", fetch)
        except Exception as exc:
            context.notice(str(exc), error=True)

    @reactive.effect
    @reactive.event(input.add)
    def add():
        try:
            context.ensure_idle()
            project = context.require_project()
            selected = [collections.get()[k] for k in input.collections() if k in collections.get()]
            model.add_domain(project, input.domain(), input.limit(), selected)
            project["profile"], project["workers"] = input.profile(), int(input.workers())
            model.save_project(project)
            context.refresh()
            context.notice("Domain saved. Its paper limit includes all selected collections and descendants.")
        except Exception as exc:
            context.notice(str(exc), error=True)

    @render.ui
    def browse_status():
        return ui.p(message.get(), role="status", class_="browse-message")

    @render.data_frame
    def domains():
        context.tick()
        project = context.project()
        return render.DataGrid(table([{"domain": d["name"], "paper limit": d["limit"],
                                      "collections": [c["library"]["name"] + " / " + c["name"] for c in d["collections"]],
                                      "attempts": len(d["history"])} for d in project["domains"]] if project else []), filters=True)

    @render.data_frame
    def preview_table():
        return render.DataGrid(table(preview_rows.get()), filters=True)
