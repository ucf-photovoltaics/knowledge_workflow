"""Landing page and local authentication onboarding.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from pathlib import Path
from shiny import module, reactive, render, ui
from dpv_dashboard.auth import ENV, credentials, save_env
from dpv_dashboard import model


@module.ui
def home_ui():
    return ui.nav_panel("Home", ui.div(
        ui.output_ui("workspace"),
        ui.p("Start with the current workspace to explore saved findings. Use setup below when connecting research libraries or creating a new project.", class_="page-purpose"),
        ui.div(ui.p("UCF DATA-ENABLED PHOTOVOLTAICS", class_="eyebrow"),
               ui.h1("From literature to\nconnected knowledge."),
               ui.p("Build evidence-backed domain ontologies from your Zotero libraries. Follow every stage, inspect every connection, and keep the research behind each result.", class_="hero-copy"),
               ui.div(ui.input_action_button("begin", "Configure your workflow →", class_="btn-primary"),
                      ui.input_action_button("guide", "Getting started"), class_="button-row",
                      **({"style": "display:none"} if model.viewer() else {})),
               ui.p("Viewer mode: explore the saved ontologies, evidence and intermediate files. Choose a run or integration "
                    "under Existing outputs. Chat can answer from saved evidence, or with Gemini if you add your own key "
                    "under Visual Exploration → Chat (kept for your session only).", class_="hero-copy") if model.viewer() else None,
               ui.span("ZOTERO  /  EVIDENCE  /  ONTOLOGIES  /  DISCOVERY", class_="hero-caption"), class_="hero"),
        ui.div(ui.tags.details(ui.tags.summary("Connect libraries & create a project"), ui.layout_columns(
            ui.card(ui.card_header("01 / Connect your research"),
                    ui.p("Save your local .env and verify access to Zotero. Model credentials are passed only to dashboard-launched processes."),
                    ui.input_file("env", "Upload .env", accept=[".env", ".txt"], multiple=False),
                    ui.output_ui("auth")),
            ui.card(ui.card_header("02 / Create a project"),
                    ui.p("Projects group your domains, selections and attempts. Existing projects can be reopened from the workspace selector above."),
                    ui.input_text("name", "Project name", placeholder="Photovoltaic reliability study"),
                    ui.input_action_button("create", "Create project", class_="btn-primary")),
            ui.card(ui.card_header("03 / Follow the evidence"),
                    ui.p("Assign collections to domains, select the top-cited papers, and run automatically or one stage at a time."),
                    ui.tags.ul(ui.tags.li("Readable summaries and intermediate outputs"), ui.tags.li("Preserved stage attempts and provenance"),
                               ui.tags.li("Domain and integrated WebVOWL graphs")),
                    ui.output_ui("project_info")), col_widths=(4, 4, 4)), open=True),
               **({"style": "display:none"} if model.viewer() else {})),
        ui.div(ui.h3("One workspace. Nine transparent stages."),
               ui.p("Ingestion → Parsing → Extraction → Normalization → Placement → Enrichment → Interoperability → Integration → Reports"), class_="workflow-banner")), value="home")


@module.server
def home_server(input, output, session, context):
    auth_revision = reactive.Value(0)

    @render.ui
    def workspace():
        from dpv_dashboard import presentation, research
        context.tick()
        record, project = context.monitored(), context.project()
        if not record and not project:
            return None
        root = Path(record["path"]) if record else context.folder("extract")
        data = research.index(root)
        return ui.card(ui.card_header("Your current workspace"),
            ui.h4(presentation.run_label(root) if root else project["name"]),
            ui.p(f"{len(data.papers):,} readable paper records · {len(data.concepts):,} canonical/class records"),
            ui.p("Next: inspect evidence and review findings before accepting the results." if data.papers else "Next: configure the domain collections and paper selection."),
            ui.input_action_button("open_results", "Inspect current results"))

    @reactive.effect
    @reactive.event(input.open_results)
    def open_results():
        context.navigate("integrate" if context.monitored() and context.monitored()["kind"] == "integration" else "extract")

    @render.ui
    def auth():
        auth_revision.get()
        values = credentials()
        services = {"ZOTERO_API_KEY": "Zotero", "MDS_API_KEY": "MDS", "MATPORTAL_API_KEY": "MatPortal", "MATERIALS_PROJECT_API_KEY": "Materials Project"}
        names = [label for name, label in services.items() if values.get(name)]
        return ui.div(ui.span("Settings saved locally" if ENV.is_file() else "No settings saved", class_="status"),
                      ui.p("Configured: " + (", ".join(names) or "none") + ". Connection verification is separate."))

    @reactive.effect
    @reactive.event(input.env)
    def upload():
        try:
            context.ensure_idle()
            upload = input.env()
            if upload:
                save_env(Path(upload[0]["datapath"]))
                auth_revision.set(auth_revision.get() + 1)
                context.notice("Environment settings saved privately for local use. Use Discover libraries to verify Zotero access.")
        except Exception as exc:
            context.notice(str(exc), error=True)

    @reactive.effect
    @reactive.event(input.create)
    def create():
        try:
            context.ensure_idle()
            project = model.create_project(input.name())
            context.select_project(project["id"])
            context.notice("Project created. Assign collections to named domains on Zotero ingestion.")
            context.navigate("ingest")
        except Exception as exc:
            context.notice(str(exc), error=True)

    @reactive.effect
    @reactive.event(input.begin)
    def begin():
        context.navigate("ingest")

    @reactive.effect
    @reactive.event(input.guide)
    def guide():
        ui.modal_show(ui.modal(
            ui.tags.ol(ui.tags.li("Upload a local .env containing ZOTERO_API_KEY and any model/provider settings you use."),
                       ui.tags.li("Create a project, discover accessible libraries, and select collections. Descendant collections are included automatically."),
                       ui.tags.li("Assign collections to a domain. Its paper limit applies to the top-cited distinct papers with PDFs across that entire domain."),
                       ui.tags.li("Use Run workflow for automatic progression, or Run stage on each page. Restart creates a fresh attempt at that stage."),
                       ui.tags.li("Inspect evidence and review issues before accepting ontology results. Integration connects completed domain ontologies.")),
            title="Getting started", easy_close=True, footer=ui.modal_button("Ready")))

    @render.ui
    def project_info():
        context.tick()
        project = context.project()
        return ui.p(f"Current project: {project['name']} · {len(project['domains'])} domains" if project else "Create your first project to begin.")
