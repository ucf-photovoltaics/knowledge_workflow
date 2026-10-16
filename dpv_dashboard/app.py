"""UCF DPV Knowledge Workflow standalone Shiny application.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from types import SimpleNamespace
from pathlib import Path
from datetime import datetime
import json
from uuid import uuid4
import asyncio
from shiny import App, reactive, render, ui
from dpv_dashboard import model, external, research, media, presentation
from dpv_dashboard.auth import ENV, redact
from dpv_dashboard.jobs import JOBS
from dpv_dashboard.pages.home import home_ui, home_server
from dpv_dashboard.pages.browse import browse_ui, browse_server
from dpv_dashboard.pages.stage import stage_ui, stage_server
from dpv_dashboard.pages.research import provenance_ui, provenance_server
from dpv_dashboard.pages.inventory import inventory_ui, inventory_server
from dpv_dashboard.pages.exploration import exploration_ui, exploration_server

WWW = model.ROOT / "dpv_dashboard" / "www"
DOCUMENTATION = model.ROOT / "outputs/development/codebase-docs/webvowl"

app_ui = ui.page_fluid(
    ui.tags.link(rel="stylesheet", href=f"dashboard.css?v={(WWW / 'dashboard.css').stat().st_mtime_ns}"),
    ui.tags.script(src=f"dashboard.js?v={(WWW / 'dashboard.js').stat().st_mtime_ns}"),
    ui.tags.header(ui.div(ui.tags.img(src="ucf-knight.jpg", alt="UCF Knighthead", class_="brand-logo"),
                         ui.div(ui.span("UCF DPV", class_="brand-name"), ui.span("Knowledge Workflow", class_="brand-subtitle")), class_="brand"),
                   ui.div(ui.tags.a("Documentation", href="documentation/library.html", class_="documentation-button"),
                          ui.span("DATA-ENABLED PHOTOVOLTAICS", class_="header-caption"), ui.output_ui("authentication"), class_="header-right"), class_="app-header"),
    ui.div(ui.div(ui.input_select("project", "PROJECT", choices={"": "Create a project on Home"}),
                  ui.input_select("domain", "DOMAIN", choices={}),
                  ui.input_select("attempt", "ATTEMPT", choices={"latest": "Latest attempt"}), class_="workspace-selectors",
                  **({"style": "display:none"} if model.viewer() else {})),
           ui.div(ui.div(ui.input_action_button("automatic", "Run workflow", class_="btn-primary"),
                         ui.input_action_button("resume", "Resume"), ui.input_action_button("cancel", "Cancel"), class_="button-row workflow-actions",
                         **({"style": "display:none"} if model.viewer() else {})),
                  ui.div(ui.input_select("existing", "EXISTING OUTPUTS · READ-ONLY MONITOR", choices={"": "Dashboard project"}), class_="output-selector"),
                  ui.output_ui("latest_integration"), class_="output-toolbar"), class_="workspace-bar"),
    ui.output_ui("pipeline_status"),
    ui.output_ui("view_context"),
    ui.tags.details(ui.tags.summary("Run details"), ui.output_ui("monitor_notice")),
    ui.navset_pill_list(home_ui("home"), provenance_ui("provenance"), inventory_ui("inventory"),
        *(stage_ui(stage, stage, (ui.div(browse_ui("browse"), style="display:none") if model.viewer() else browse_ui("browse"))
                   if stage == "ingest" else None) for stage in model.STAGES),
        exploration_ui("exploration"),
        id="pages", selected="home", widths=(2, 10)),
    ui.accordion(ui.accordion_panel("Execution log & job status", ui.output_ui("job_status"), ui.output_code("logs")), open=False),
    ui.tags.footer("UCF Data-Enabled Photovoltaics · Evidence, provenance, and connected research", class_="app-footer"),
    title="UCF DPV Knowledge Workflow")


def server(input, output, session):
    revision = reactive.Value(0)
    external_choices = reactive.Value({})
    discovery_started = False

    @reactive.effect
    def discover_outputs():
        nonlocal discovery_started
        reactive.invalidate_later(5)
        records = external.discover()
        with reactive.isolate():
            previous = external_choices.get()
            selected = input.existing()
        if records != previous or not discovery_started:
            external_choices.set(records)
            choices = {} if model.viewer() else {"": "Dashboard project (enable execution controls)"}
            choices.update({k: presentation.run_label(Path(v["path"])) for k, v in records.items()})
            if not discovery_started:
                selected = next(iter(records), "")
            ui.update_select("existing", choices=choices, selected=selected if selected in choices else "")
        discovery_started = True

    def monitored():
        return external_choices.get().get(input.existing())

    @render.ui
    def latest_integration():
        candidates = []
        for identifier, record in external_choices.get().items():
            if record["kind"] != "integration":
                continue
            manifest = model.read(Path(record["path"]) / "integration.json", {})
            try:
                created = datetime.fromisoformat(manifest.get("created", "")).timestamp()
            except (TypeError, ValueError, OverflowError):
                created = record["modified"]
            candidates.append((created, identifier, manifest))
        if not candidates:
            return ui.p("No completed integration outputs found yet.", class_="muted")
        _, identifier, manifest = max(candidates, key=lambda item: (item[0], item[1]))
        domains = " + ".join(str(row.get("domain", "")) for row in manifest.get("inputs", []))
        action = ("$('#existing').val(" + json.dumps(identifier) + ").trigger('change');"
                  "document.querySelector('a[data-value=\"integrate\"]').click();")
        return ui.div(ui.div(ui.tags.strong("Latest integration"), ui.p(presentation.run_label(Path(identifier)), class_="muted"),
                             ui.p(domains or "Saved cross-domain ontology", class_="muted")),
                      ui.tags.button("View latest integration", type="button", onclick=action,
                                     class_="btn btn-primary", id="view_latest_integration"),
                      class_="latest-integration-summary")

    def stage_files(root, stage):
        record = monitored()
        return external.files(root, stage, record["kind"]) if record and root else model.artifact_files(root, stage)

    @reactive.calc
    def tick():
        reactive.invalidate_later(2)
        revision.get()
        return model.now()

    def refresh():
        revision.set(revision.get() + 1)

    project_value = reactive.Value(None)

    @reactive.effect
    def poll_project():
        tick()
        identifier = input.project()
        value = model.load_project(identifier) if identifier else None
        with reactive.isolate():
            previous = project_value.get()
        if value != previous:
            project_value.set(value)

    @reactive.calc
    def project():
        return project_value.get()

    def require_project():
        if monitored():
            raise ValueError("Existing outputs are read-only. Select Dashboard project in Existing outputs to launch or configure jobs.")
        current = project()
        if not current:
            raise ValueError("Create or select a project first.")
        return current

    def notice(message, error=False):
        ui.notification_show(redact(message), type="error" if error else "message", duration=8)

    def ensure_idle():
        if JOBS.running():
            raise ValueError("A dashboard job is running. Wait or cancel before changing configuration.")

    def select_project(identifier):
        ui.update_select("existing", selected="", session=session)
        choices = {p["id"]: p["name"] for p in model.projects()}
        ui.update_select("project", choices=choices, selected=identifier, session=session)
        # Updating the selector itself invalidates the project; avoid a second update
        # racing it back to the previous selection in project_choices.

    @reactive.effect
    def project_choices():
        revision.get()
        choices = {"": "Select or create a project", **{p["id"]: p["name"] for p in model.projects()}}
        with reactive.isolate():
            selected = input.project()
        ui.update_select("project", choices=choices, selected=selected if selected in choices else "")

    @reactive.effect
    def domain_choices():
        current = project()
        choices = {d["id"]: d["name"] for d in current["domains"]} if current else {}
        with reactive.isolate():
            selected = input.domain()
        ui.update_select("domain", choices=choices, selected=selected if selected in choices else next(iter(choices), ""))

    def domain():
        current = project()
        return next((d for d in current["domains"] if d["id"] == input.domain()), None) if current else None

    @reactive.effect
    def attempts():
        current = project()
        selected = domain()
        choices = {"latest": "Latest attempt"}
        page = input.pages()
        if current and page in ("integrate", "reports"):
            key = "integration_history" if page == "integrate" else "report_history"
            choices.update({r: f"Saved attempt {i + 1} / {r}" for i, r in enumerate(current.get(key, []))})
        elif selected:
            choices.update({r: f"Saved attempt {i + 1} / {r}" for i, r in enumerate(selected["history"])})
        with reactive.isolate():
            previous = input.attempt()
        ui.update_select("attempt", choices=choices, selected=previous if previous in choices else "latest")

    def folder(stage):
        record = monitored()
        if record:
            return Path(record["path"])
        current = project()
        if not current:
            return None
        root = model.project_path(current["id"])
        if stage == "integrate":
            attempt = input.attempt()
            identifier = attempt if attempt in current.get("integration_history", []) else current.get("integration")
            return root / "runs" / identifier if identifier else None
        if stage == "reports":
            attempt = input.attempt()
            identifier = attempt if attempt in current.get("report_history", []) else current.get("report")
            return root / identifier if identifier else None
        selected = domain()
        if not selected:
            return None
        attempt = input.attempt()
        if attempt and attempt != "latest" and attempt in selected["history"]:
            return root / "runs" / attempt
        return model.run_dir(current, selected)

    def launch(action, stage=None):
        try:
            current = require_project()
            if input.attempt() != "latest":
                raise ValueError("Switch to Latest attempt before running a stage.")
            JOBS.start(current, action, input.domain(), stage)
            refresh()
            notice("Dashboard job started. Follow its progress in the stage pages and execution log.")
        except Exception as exc:
            notice(str(exc), error=True)

    focused = reactive.Value({})
    visual_target = reactive.Value({})

    def open_exploration(root, path=None):
        if root not in roots():
            notice("The graph source is unavailable in this workspace.", error=True)
            return
        visual_target.set({"root": str(root), "file": str(path) if path else "", "request": uuid4().hex})
        ui.update_navset("pages", selected="explore", session=session)

    def roots():
        record = monitored()
        if record:
            root = Path(record["path"])
            return list(dict.fromkeys([root, *research.source_roots(root)]))
        current = project()
        if not current:
            return []
        candidates = [folder("extract")]
        candidates += [model.run_dir(current, d) for d in current["domains"]]
        candidates += [folder(s) for s in ("integrate", "reports")]
        project_root = model.project_path(current["id"])
        history_runs = [name for d in current["domains"] for name in d["history"]] + current.get("integration_history", [])
        candidates += [model.inside(project_root / "runs", name) for name in history_runs
                       if isinstance(name, str) and Path(name).name == name and name not in (".", "..")]
        candidates += [model.inside(project_root, name) for name in current.get("report_history", [])
                       if isinstance(name, str) and Path(name).name == name and name not in (".", "..")]
        return list(dict.fromkeys(p for p in candidates if p and p.is_dir()))

    def superseded(root):
        current = project()
        if root is None or monitored() or not current:
            return False
        for d in current["domains"]:
            if root.name in d["history"]:
                return root.name != d.get("run")
        return ((root.name in current.get("integration_history", []) and root.name != current.get("integration")) or
                (root.name in current.get("report_history", []) and root.name != current.get("report")))

    def inspect_source(root, canonical=None, paper=None, tab=None):
        if root not in roots():
            notice("The requested source run is unavailable in this workspace.", error=True)
            return
        data = research.index(root)
        if canonical and canonical not in data.concepts or paper and paper not in data.papers:
            notice("The requested concept or paper is not recorded in this run.", error=True)
            return
        focused.set({"root": str(root), "canonical": canonical, "paper": paper, "tab": tab, "request": uuid4().hex})
        ui.update_navset("pages", selected="provenance", session=session)

    context = SimpleNamespace(tick=tick, refresh=refresh, project=project, require_project=require_project,
        select_project=select_project, navigate=lambda page: ui.update_navset("pages", selected=page, session=session),
        notice=notice, ensure_idle=ensure_idle, folder=folder, launch=launch, monitored=monitored, files=stage_files,
        roots=roots, superseded=superseded, focused=focused.get, inspect=inspect_source,
        comparison_roots=lambda: [Path(record["path"]) for record in external_choices.get().values()],
        visual_target=visual_target.get, explore=open_exploration)
    home_server("home", context)
    browse_server("browse", context)
    provenance_server("provenance", context)
    inventory_server("inventory", context)
    exploration_server("exploration", context)
    for stage in model.STAGES:
        stage_server(stage, stage, context)

    @reactive.effect
    @reactive.event(input.research_navigate)
    def research_navigation():
        event = input.research_navigate()
        if not isinstance(event, dict):
            return
        root = next((r for r in roots() if str(r) == event.get("root")), None)
        if root is None:
            return
        cid, paper = event.get("canonical"), event.get("paper")
        if not isinstance(cid, str) or not isinstance(paper, str):
            return
        tab = event.get("tab") if event.get("tab") in ("Paper & evidence", "Original → canonical") else None
        inspect_source(root, cid or None, paper or None, tab)

    @reactive.effect
    @reactive.event(input.research_open)
    async def open_research_reference():
        event = input.research_open()
        if not isinstance(event, dict):
            return
        root = next((p for p in roots() if str(p) == event.get("root")), None)
        if root is None:
            notice("This reference is outside the selected workspace.", error=True)
            return
        data, key = research.index(root), event.get("paper")
        if not isinstance(key, str) or key not in data.papers:
            notice("The paper record is unavailable.", error=True)
            return
        figure = event.get("figure") if isinstance(event.get("figure"), str) else None
        canonical = event.get("canonical") if isinstance(event.get("canonical"), str) else None
        claim = event.get("claim") if isinstance(event.get("claim"), str) else None
        content = await asyncio.to_thread(media.paper_view, data, key, figure, canonical, event.get("gallery") is True, claim)
        ui.modal_show(ui.modal(content,
                              title="Paper & figure inspector", size="xl", easy_close=True))

    @reactive.effect
    @reactive.event(input.provenance_graph)
    def graph_provenance():
        event = input.provenance_graph()
        if not isinstance(event, dict) or not isinstance(event.get("iri"), str):
            return
        for root in roots():
            data = research.index(root)
            cid = data.iri_ids.get(event["iri"])
            if cid:
                inspect_source(root, canonical=cid)
                return
        notice("This graph node has no recorded local concept in the available source runs.")

    @render.ui
    def authentication():
        tick()
        if model.viewer():
            return ui.span("VIEWER · READ-ONLY", class_="header-caption")
        return ui.input_action_link("authenticate", "Settings saved · Reauthenticate" if ENV.is_file() else "Authenticate .env")

    @reactive.effect
    @reactive.event(input.authenticate)
    def authenticate():
        ui.update_navset("pages", selected="home")
        notice("Upload your .env on Home to save or replace local authentication settings.")

    @render.ui
    def pipeline_status():
        tick()
        record = monitored()
        if record:
            states = external.states(Path(record["path"]), record["kind"])
            return ui.div(*(presentation.stage_step(s, i + 1, states[s],
                                  'completed' if states[s] == 'completed' else 'running' if states[s].startswith('active') else 'waiting')
                            for i, s in enumerate(model.STAGES)), class_="pipeline-strip")
        current, selected = project(), domain()
        root = model.run_dir(current, selected) if current and selected else None
        state = model.read(root / "dashboard.json", {}) if root else {}
        global_state = model.read(model.project_path(current["id"]) / "dashboard.json", {}) if current else {}
        items = []
        for i, stage in enumerate(model.STAGES):
            status = state.get("stages", {}).get(stage, {}).get("status", "waiting")
            if stage in ("integrate", "reports"):
                status = global_state.get("stages", {}).get(stage, {}).get("status", "waiting")
            if current and stage == "integrate" and current.get("integration"):
                status = "outdated" if current.get("integration_stale") else "completed"
            if current and stage == "reports" and current.get("report"):
                status = "outdated" if current.get("report_stale") else "completed"
            if stage in ("integrate", "reports") and global_state.get("stages", {}).get(stage, {}).get("status") in ("running", "failed", "cancelled", "interrupted"):
                status = global_state["stages"][stage]["status"]
            items.append(presentation.stage_step(stage, i + 1, status))
        return ui.div(*items, class_="pipeline-strip")

    @render.ui
    def job_status():
        tick()
        if monitored():
            return ui.p("Read-only external run · Recent log activity indicates progress, not verified process ownership.")
        current = project()
        job = model.read(model.project_path(current["id"]) / "job.json", {}) if current else {}
        return ui.p(f"{job.get('status', 'idle').title()} · {job.get('action', 'No job launched')} · {job.get('stage') or 'workflow'}")

    @render.code
    def logs():
        tick()
        record = monitored()
        if record:
            return redact(external.log(Path(record["path"])))
        current = project()
        return JOBS.log(current) if current else "Select a project to inspect its execution log."

    @render.ui
    def view_context():
        record = monitored()
        current = project()
        title = presentation.run_label(Path(record["path"])) if record else (current["name"] if current else "No project selected")
        return ui.div(ui.strong(title), ui.span("Viewing saved results · execution disabled" if record else "Project workspace"),
                      ui.p("Source-specific selectors on evidence and exploration pages identify the contributing domain being inspected."),
                      class_="view-context", **{"data-readonly": "true" if record else "false"})

    @render.ui
    def monitor_notice():
        record = monitored()
        return ui.p("Run identifier: " + input.existing()) if record else ui.p("Select a saved output to inspect its run identifier.")

    @reactive.effect
    @reactive.event(input.automatic)
    def automatic():
        launch("all")

    @reactive.effect
    @reactive.event(input.resume)
    def resume():
        launch("resume")

    @reactive.effect
    @reactive.event(input.cancel)
    def cancel():
        try:
            JOBS.cancel(require_project()["id"])
            refresh()
            notice("Cancellation requested. Saved outputs are retained.")
        except Exception as exc:
            notice(str(exc), error=True)


app = App(app_ui, server, static_assets={"/": WWW, **({"/documentation": DOCUMENTATION} if DOCUMENTATION.is_dir() else {})})
app.starlette_app.router.routes.insert(0, media.route)
