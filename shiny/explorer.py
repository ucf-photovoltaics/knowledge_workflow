"""
MDS-Onto Knowledge Dashboard (Shiny host).

Thin host around kw.graphview: the sidebar handles data ingestion (pick one or
more output collections, upload .jsonld, or point at a folder) and the main area
embeds the full-bleed interactive graph app (graph + floating Details and
Data/Plot panels). All graph interactivity lives client-side in the embedded app.
"""
from shiny import App, ui, render, reactive
import pathlib
import sys
import os
import glob
import html as _html

# --- Make kw importable regardless of CWD -----------------------------------
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from kw import graphview as gv


# --- Collection discovery ---------------------------------------------------
def _discover_collections():
    """Return {label: folder_path} for every output folder holding an all.jsonld,
    most-recently-modified first."""
    found = []
    for base in ("outputs", "outputs_test"):
        for p in glob.glob(str(PROJECT_ROOT / base / "*" / "all.jsonld")):
            folder = os.path.dirname(p)
            found.append((os.path.getmtime(p), f"{base}/{os.path.basename(folder)}", folder))
    found.sort(reverse=True)
    return {label: folder for _, label, folder in found}


_COLLECTIONS = _discover_collections()
_DEFAULT = [next(iter(_COLLECTIONS))] if _COLLECTIONS else []


# --- UI ---------------------------------------------------------------------
app_ui = ui.page_fillable(
    ui.navset_card_underline(
        ui.nav_panel(
            "Graph Explorer",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.h5("Data Source"),
                    ui.input_selectize(
                        "collections", "Collections (combine multiple):",
                        choices=list(_COLLECTIONS.keys()),
                        selected=_DEFAULT, multiple=True,
                    ),
                    ui.input_action_button("reload", "Rebuild graph", class_="btn-primary btn-sm"),
                    ui.hr(),
                    ui.input_file("ontology_upload", "Add .jsonld file(s)",
                                  multiple=True, accept=[".jsonld"]),
                    ui.input_text("local_folder_path", "Or add a folder path:",
                                  placeholder="e.g. outputs/my_collection"),
                    ui.input_action_button("load_folder", "Add folder", class_="btn-sm"),
                    ui.hr(),
                    ui.output_ui("source_status"),
                    width=300,
                ),
                ui.output_ui("graph_app"),
            ),
        ),
        ui.nav_panel(
            "Export Workflows",
            ui.markdown("### Export Pathways"),
            ui.markdown("Prepare the current graph and data state for publication "
                        "or GraphDB import."),
        ),
        title="MDS-Onto Knowledge Dashboard",
    ),
    title="MDS-Onto Knowledge Dashboard",
)


# --- Server -----------------------------------------------------------------
def server(input, output, session):
    extra_jsonld = reactive.Value([])      # uploaded loose .jsonld paths
    extra_folders = reactive.Value([])     # folders added by path
    status = reactive.Value(
        f"Loaded: {_DEFAULT[0]}" if _DEFAULT else "No output folders found.")

    @reactive.Effect
    @reactive.event(input.ontology_upload)
    def _on_upload():
        info = input.ontology_upload()
        if not info:
            return
        paths = [f["datapath"] for f in info if f["name"].lower().endswith(".jsonld")]
        if paths:
            extra_jsonld.set(extra_jsonld() + paths)
            status.set(f"Added {len(paths)} uploaded file(s).")
        else:
            status.set("Upload .jsonld files (.ttl not yet supported).")

    @reactive.Effect
    @reactive.event(input.load_folder)
    def _on_folder():
        raw = (input.local_folder_path() or "").strip()
        if not raw:
            return
        folder = pathlib.Path(raw)
        if not folder.is_absolute():
            folder = PROJECT_ROOT / folder
        if folder.is_dir():
            extra_folders.set(extra_folders() + [str(folder)])
            status.set(f"Added folder: {folder.name}")
        else:
            status.set("Invalid directory path.")

    @reactive.Calc
    @reactive.event(input.collections, input.reload, input.ontology_upload,
                    input.load_folder, ignore_none=False)
    def merged_graph():
        # Gather data files from selected collections + added folders + uploads.
        jsonld, rebel, csvs, enriched = [], [], [], []
        folders = [_COLLECTIONS[c] for c in (input.collections() or []) if c in _COLLECTIONS]
        folders += extra_folders()
        for f in folders:
            d = gv._discover(f)
            jsonld += d["jsonld"]; rebel += d["rebel"]; csvs += d["csv"]
            enriched += d.get("enriched", [])
        jsonld += extra_jsonld()
        if not jsonld:
            return None
        return gv.build_merged_graph(jsonld, rebel_paths=rebel, csv_paths=csvs,
                                     enriched_paths=enriched)

    @render.ui
    def source_status():
        G = merged_graph()
        if G is not None:
            from collections import Counter
            c = Counter(d["ntype"] for _, d in G.nodes(data=True))
            summary = ", ".join(f"{v} {k}" for k, v in c.most_common())
            extra = (f"<br><small>{G.number_of_nodes()} nodes &middot; "
                     f"{G.number_of_edges()} edges<br>{_html.escape(summary)}</small>")
        else:
            extra = ""
        return ui.HTML(f"<small><b>Status:</b> {_html.escape(status())}</small>{extra}")

    @render.ui
    def graph_app():
        G = merged_graph()
        if G is None:
            return ui.HTML(
                "<div style='padding:40px;color:gray'><i>No graph loaded - pick a "
                "collection or upload a .jsonld file.</i></div>")
        srcdoc = _html.escape(gv.render_app_html(G, height="86vh"), quote=True)
        return ui.HTML(
            f'<iframe srcdoc="{srcdoc}" style="width:100%; height:88vh; '
            f'border:none; display:block;"></iframe>')


app = App(app_ui, server)
