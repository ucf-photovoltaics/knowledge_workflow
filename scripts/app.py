"""
app.py  —  Shiny for Python UI for Knowledge Workflow V3 + V4
──────────────────────────────────────────────────────────────
Run with:
    uv run shiny run app.py --reload

Required in .env:
    ZOTERO_API_KEY=your_key_here
    ANTHROPIC_API_KEY=your_key_here

Optional in .env:
    ZOTERO_LIBRARY_ID=2189702         (defaults to 2189702 if not set)
"""

from __future__ import annotations

import asyncio
import glob
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from io import BytesIO
from typing import Any

import anthropic
import instructor
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field, create_model
from pypdf import PdfReader
from pyzotero import Zotero
from shiny import App, Inputs, Outputs, Session, reactive, render, ui

load_dotenv()

# ── Environment config ────────────────────────────────────────────────────────

ZOTERO_API_KEY    = os.environ.get("ZOTERO_API_KEY",    "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ZOTERO_LIBRARY_ID = os.environ.get("ZOTERO_LIBRARY_ID", "2189702")
DEFAULT_LIBRARY_TYPE = "group"
MODEL             = "claude-sonnet-4-6"
RATE_LIMIT_DELAY  = 0.5

# Directory where this file (and V4 script) lives
_HERE = os.path.dirname(os.path.abspath(__file__))

# ── Fixed universal fields (V3 extraction) ────────────────────────────────────

_FIXED_FIELDS: dict[str, tuple] = {
    "author": (
        str,
        Field(description='Last name of the first author. "Not Specified" if not explicitly stated.'),
    ),
    "institution": (
        str,
        Field(description='Institution of the first author. "Not Specified" if not explicitly stated.'),
    ),
    "country": (
        str,
        Field(description='Country of that institution. "Not Specified" if not explicitly stated.'),
    ),
    "doi": (
        str,
        Field(description='Full DOI URL (https://doi.org/10.xxxx/...). "Not Specified" if not explicitly stated.'),
    ),
}

_SCHEMA_SKIP_COLS = {"domain", "doi", "title", "paper"}

# ── Dynamic model helpers (V3) ────────────────────────────────────────────────

def _slug(concept: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", concept.lower().strip()).strip("_")
    return s or "concept"


def build_extraction_model(concepts: list[str]) -> type[BaseModel]:
    fields: dict[str, Any] = dict(_FIXED_FIELDS)
    for concept in concepts:
        slug = _slug(concept)
        if slug in fields:
            slug = f"{slug}_val"
        fields[slug] = (
            str,
            Field(
                description=(
                    f'For "{concept}": the exact term, value, or measurement this paper '
                    f'reports. "Not Specified" if not explicitly stated.'
                )
            ),
        )
    return create_model("PaperExtraction", **fields)


def build_system_prompt(concepts: list[str]) -> str:
    concept_lines = "\n".join(
        f'  - {c}: exact term/value this paper reports. "Not Specified" if absent.'
        for c in concepts
    )
    return (
        "Act as an expert materials scientist and researcher. Extract specific "
        "parameters from the provided research article into a structured format.\n\n"
        "Crucial: Do not infer, guess, or calculate missing information. "
        'If a value is not explicitly stated, output exactly "Not Specified".\n\n'
        "Always extract these universal fields:\n"
        "  - author: Last name of the first author.\n"
        "  - institution: Name of the institution of the first author.\n"
        "  - country: Country where that institution is located.\n"
        "  - doi: Full DOI URL formatted as https://doi.org/10.xxxx/...\n"
        + (
            "\nAlso extract these domain-specific concepts:\n" + concept_lines
            if concepts else ""
        )
    )


def model_to_row(instance: BaseModel, title: str, concepts: list[str]) -> dict:
    data    = instance.model_dump()
    doi_val = data.get("doi", "Not Specified") or "Not Specified"
    if doi_val != "Not Specified" and not doi_val.startswith("http"):
        doi_val = f"https://doi.org/{doi_val}"
    row: dict = {
        "Title":       title,
        "Author":      data.get("author",      "Not Specified"),
        "Institution": data.get("institution", "Not Specified"),
        "Country":     data.get("country",     "Not Specified"),
        "DOI":         doi_val,
    }
    for concept in concepts:
        row[concept] = data.get(_slug(concept), "Not Specified")
    return row


def col_headers(concepts: list[str]) -> list[str]:
    return ["Title", "Author", "Institution", "Country", "DOI"] + concepts


def load_concepts_from_csv(path: str, column: str = "concept") -> list[str]:
    df = pd.read_csv(path)
    if column not in df.columns:
        return [c for c in df.columns if c.lower() not in _SCHEMA_SKIP_COLS]
    return df[column].dropna().str.strip().str.lower().tolist()


# ── Shared Zotero / Anthropic clients ─────────────────────────────────────────

def _make_zot() -> Zotero:
    if not ZOTERO_API_KEY:
        raise ValueError("ZOTERO_API_KEY not found in environment / .env file.")
    return Zotero(ZOTERO_LIBRARY_ID, DEFAULT_LIBRARY_TYPE, ZOTERO_API_KEY)


def _make_claude() -> instructor.Instructor:
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not found in environment / .env file.")
    return instructor.from_anthropic(anthropic.Anthropic(api_key=ANTHROPIC_API_KEY))


def get_collection_map(zot: Zotero) -> dict[str, str]:
    return {c["data"]["name"]: c["key"] for c in zot.collections()}


# ── Paper-fetching helpers ─────────────────────────────────────────────────────

def _pdf_text(zot: Zotero, item_key: str) -> str:
    for child in zot.children(item_key):
        if child["data"].get("contentType") == "application/pdf":
            try:
                reader = PdfReader(BytesIO(zot.file(child["key"])))
                return "".join(p.extract_text() or "" for p in reader.pages)
            except Exception:
                pass
    return ""


def _fetch_papers(zot: Zotero, collection_id: str, log) -> dict:
    all_items = zot.everything(zot.collection_items(collection_id))
    valid = [
        i for i in all_items
        if i["data"].get("itemType") not in ("attachment", "note")
        and i["data"].get("title")
    ]
    papers: dict = {}
    for idx, item in enumerate(valid, 1):
        data  = item["data"]
        title = data["title"]
        log(f"[{idx}/{len(valid)}] Fetching PDF: {title[:65]}…")
        papers[title.lower()] = {
            "key":       item["key"],
            "title":     title,
            "doi":       data.get("DOI"),
            "abstract":  data.get("abstractNote"),
            "date":      data.get("date"),
            "authors":   data.get("creators", []),
            "full_text": _pdf_text(zot, item["key"]),
        }
    return papers


# ── V3 extraction pipeline ─────────────────────────────────────────────────────

def _build_context(paper: dict) -> str:
    parts = [f"Title: {paper['title']}"]
    doi_meta = paper.get("doi", "")
    if doi_meta:
        if not doi_meta.startswith("http"):
            doi_meta = f"https://doi.org/{doi_meta}"
        parts.append(f"DOI (from metadata): {doi_meta}")
    names = "; ".join(
        a.get("lastName", "") for a in paper.get("authors", []) if a.get("lastName")
    )
    if names:
        parts.append(f"Authors (from metadata): {names}")
    opening = (paper.get("full_text") or "")[:2000]
    if opening:
        parts.append(f"\n[Article opening — may contain affiliations]:\n{opening}")
    abstract = paper.get("abstract") or ""
    if abstract:
        parts.append(f"\n[Abstract]:\n{abstract}")
    return "\n".join(parts)


def _extract_paper_data(
    client: instructor.Instructor,
    paper: dict,
    model_class: type[BaseModel],
    system_prompt: str,
    concepts: list[str],
) -> dict:
    result = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": _build_context(paper)}],
        response_model=model_class,
    )
    return model_to_row(result, paper["title"], concepts)


def _make_filename(collection_name: str, version: int = 3) -> str:
    date = datetime.now().strftime("%Y%m%d")
    name = collection_name.replace(" ", "_").lower()
    return f"extraction_{name}-Brent_Thompson-v{version}-{date}.csv"


def _run_pipeline(
    collection_name: str,
    collection_id:   str,
    concepts:        list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Full synchronous V3 pipeline. Returns (df, logs)."""
    logs: list[str] = []
    def log(msg: str) -> None:
        logs.append(msg)

    log(f"Connecting to Zotero library {ZOTERO_LIBRARY_ID}…")
    zot    = _make_zot()
    client = _make_claude()

    papers = _fetch_papers(zot, collection_id, log)
    log(f"Loaded {len(papers)} paper(s) from '{collection_name}'.")

    missing = [p["title"] for p in papers.values() if not p["full_text"]]
    if missing:
        preview = ", ".join(missing[:3]) + ("…" if len(missing) > 3 else "")
        log(f"⚠  {len(missing)} paper(s) without PDF text: {preview}")

    if concepts:
        log(f"\nConcepts ({len(concepts)}): {', '.join(concepts[:5])}"
            + (f" … +{len(concepts)-5} more" if len(concepts) > 5 else ""))
    else:
        log("\nNo concepts loaded — extracting base metadata only.")

    model_class   = build_extraction_model(concepts)
    system_prompt = build_system_prompt(concepts)

    all_papers = list(papers.values())
    total = len(all_papers)
    log(f"Extracting parameters from {total} paper(s) using {MODEL}…")

    rows: list[dict] = []
    for i, paper in enumerate(all_papers, 1):
        log(f"  [{i}/{total}] {paper['title'][:65]}")
        rows.append(_extract_paper_data(client, paper, model_class, system_prompt, concepts))
        if i < total:
            time.sleep(RATE_LIMIT_DELAY)

    headers = col_headers(concepts)
    df = pd.DataFrame(rows, columns=headers) if rows else pd.DataFrame(columns=headers)
    log(f"✓ Done — {len(df)} row(s)  ×  {len(df.columns)} columns.")
    return df, logs


# ── V4 schema generation (subprocess) ────────────────────────────────────────

def _run_v4_subprocess(collection_name: str) -> tuple[list[str], list[str]]:
    """
    Run knowledge_workflow_V4.py as a subprocess with the given collection name.
    Returns (concepts, logs).
    """
    script = os.path.join(_HERE, "knowledge_workflow_V4.py")
    cmd    = [sys.executable, "-m", "uv", "run", "python", script,
              "--collection", collection_name]
    # Prefer uv if available, fall back to current interpreter directly
    try:
        result = subprocess.run(
            ["uv", "run", "python", script, "--collection", collection_name],
            capture_output=True,
            text=True,
            cwd=_HERE,
        )
    except FileNotFoundError:
        result = subprocess.run(
            [sys.executable, script, "--collection", collection_name],
            capture_output=True,
            text=True,
            cwd=_HERE,
        )

    logs = result.stdout.splitlines()
    if result.returncode != 0:
        err_lines = result.stderr.splitlines()[-20:]   # last 20 lines of stderr
        logs += [""] + ["❌ V4 stderr:"] + err_lines
        raise RuntimeError(f"knowledge_workflow_V4.py exited with code {result.returncode}")

    # Find the schema CSV that V4 just wrote
    name_slug = collection_name.replace(" ", "_").lower()
    pattern   = os.path.join(_HERE, f"schema_{name_slug}*.csv")
    found     = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if not found:
        raise FileNotFoundError(
            f"V4 ran successfully but no schema CSV found matching: schema_{name_slug}*.csv"
        )
    schema_path = found[0]
    logs.append(f"✓ Schema CSV: {os.path.basename(schema_path)}")

    concepts = load_concepts_from_csv(schema_path)
    logs.append(f"✓ Loaded {len(concepts)} concept column(s) from schema.")
    return concepts, logs


# ── UI ────────────────────────────────────────────────────────────────────────

_WRAP_CSS = ui.tags.style("""
    /* DataGrid: wrap text in Title and Institution columns */
    .shiny-data-grid table td:nth-child(1),
    .shiny-data-grid table td:nth-child(3) {
        white-space: normal !important;
        word-break: break-word;
        min-width: 180px;
        max-width: 280px;
    }
    /* Collection listbox: compact style */
    #collection_pick {
        border: 1px solid #dee2e6;
        border-radius: 4px;
        font-size: 0.85rem;
    }
""")


def _key_badge(found: bool, name: str):
    if found:
        return ui.tags.span(f"✓ {name} found", class_="text-success small d-block")
    return ui.tags.span(f"✗ {name} missing — add to .env", class_="text-danger small d-block")


_zotero_badge    = _key_badge(bool(ZOTERO_API_KEY),    "ZOTERO_API_KEY")
_anthropic_badge = _key_badge(bool(ANTHROPIC_API_KEY), "ANTHROPIC_API_KEY")

app_ui = ui.page_sidebar(
    ui.sidebar(
        # ── API Key Status ────────────────────────────────────────────────────
        ui.h6("API Keys"),
        _zotero_badge,
        _anthropic_badge,
        ui.hr(),
        # ── Collection search ─────────────────────────────────────────────────
        ui.h6("Collection"),
        ui.input_text(
            "collection_query", None,
            placeholder="Search collections…",
            width="100%",
        ),
        ui.output_ui("collection_matches"),
        ui.hr(),
        # ── Domain Concepts ───────────────────────────────────────────────────
        ui.h6("Domain Concepts"),
        ui.input_file(
            "schema_csv", "Load custom schema table",
            accept=[".csv"],
            button_label="Browse…",
            multiple=False,
            placeholder="No file selected",
        ),
        ui.tags.small("— or —", class_="text-muted d-block text-center my-1"),
        ui.input_action_button(
            "v4_btn", "Generate Schema (V4)",
            class_="btn-outline-info btn-sm w-100",
        ),
        ui.tags.small(
            "Runs knowledge_workflow_V4.py on the selected collection.",
            class_="text-muted d-block mt-1",
        ),
        ui.output_ui("concepts_preview"),
        ui.hr(),
        # ── Run ───────────────────────────────────────────────────────────────
        ui.input_action_button("run_btn", "▶  Run Pipeline", class_="btn-success w-100"),
        ui.output_ui("status_badge"),
        width=310,
    ),

    _WRAP_CSS,

    ui.card(
        ui.card_header("Progress Log"),
        ui.output_text_verbatim("log_out", placeholder=True),
        style="max-height:200px; overflow-y:auto;",
    ),

    ui.card(
        ui.card_header(
            ui.row(
                ui.column(6, ui.h6("Extracted Parameters", class_="mb-0 mt-1")),
                ui.column(6,
                    ui.download_button(
                        "dl_results", "⬇  Download CSV",
                        class_="btn-sm btn-outline-secondary float-end",
                    ),
                ),
            )
        ),
        ui.output_data_frame("results_tbl"),
    ),

    title="Knowledge Workflow V3",
    fillable=True,
)


# ── Server ────────────────────────────────────────────────────────────────────

def server(input: Inputs, output: Outputs, session: Session) -> None:

    collections:          reactive.Value[dict[str, str]] = reactive.Value({})
    collections_loading:  reactive.Value[bool]           = reactive.Value(False)
    collections_error:    reactive.Value[str]            = reactive.Value("")
    selected_collection:  reactive.Value[str]            = reactive.Value("")
    loaded_concepts:      reactive.Value[list[str]]      = reactive.Value([])
    log_lines:            reactive.Value[list[str]]      = reactive.Value(["Waiting to run…"])
    results:              reactive.Value[tuple | None]   = reactive.Value(None)
    is_running:           reactive.Value[bool]           = reactive.Value(False)
    v4_is_running:        reactive.Value[bool]           = reactive.Value(False)
    current_collection:   reactive.Value[str]            = reactive.Value("")
    run_start_time:       reactive.Value[float]          = reactive.Value(0.0)
    last_heartbeat:       reactive.Value[float]          = reactive.Value(0.0)

    # ── Auto-load collections on startup ──────────────────────────────────────

    @reactive.extended_task
    async def _load_collections_task():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: get_collection_map(_make_zot())
        )

    if ZOTERO_API_KEY:
        collections_loading.set(True)
        _load_collections_task()

    @reactive.effect
    def _watch_collection_load() -> None:
        status = _load_collections_task.status()
        if status == "success":
            collections.set(_load_collections_task.result())
            collections_loading.set(False)
            collections_error.set("")
        elif status == "error":
            collections_loading.set(False)
            collections_error.set(str(_load_collections_task.error()))

    # ── Collection search UI ──────────────────────────────────────────────────

    @render.ui
    def collection_matches():
        # Status states
        if collections_loading():
            return ui.tags.small("⟳ Loading collections…", class_="text-muted d-block mt-1")
        err = collections_error()
        if err:
            return ui.tags.small(f"⚠ {err[:80]}", class_="text-danger d-block mt-1")
        cmap = collections()
        if not cmap:
            if not ZOTERO_API_KEY:
                return ui.tags.small("✗ Add ZOTERO_API_KEY to .env", class_="text-danger d-block mt-1")
            return ui.tags.small("No collections found.", class_="text-warning d-block mt-1")

        sel   = selected_collection()
        query = (input.collection_query() or "").strip().lower()

        # Show confirmed selection (search box is empty after picking)
        if sel and not query:
            return ui.div(
                ui.tags.small("Selected:", class_="text-muted d-block"),
                ui.tags.strong(sel, class_="d-block text-success"),
                ui.input_action_button(
                    "clear_collection_btn", "✕ Change",
                    class_="btn btn-link btn-sm p-0 text-secondary",
                ),
                class_="mt-1",
            )

        if not query:
            return ui.tags.small(
                f"{len(cmap)} collections available — type to search",
                class_="text-muted d-block mt-1",
            )

        matches = sorted(k for k in cmap if query in k.lower())
        if not matches:
            return ui.tags.small("No matches.", class_="text-muted d-block mt-1")

        return ui.div(
            ui.input_select(
                "collection_pick", None,
                choices=matches,
                size=min(len(matches), 6),
                selectize=False,
                width="100%",
            ),
            ui.tags.small(
                f"{len(matches)} match(es) — click to select",
                class_="text-muted d-block",
            ),
        )

    @reactive.effect
    @reactive.event(input.collection_pick)
    def _pick_collection() -> None:
        val = input.collection_pick()
        if val:
            selected_collection.set(val)
            ui.update_text("collection_query", value="")

    @reactive.effect
    @reactive.event(input.clear_collection_btn)
    def _clear_collection() -> None:
        selected_collection.set("")

    # ── Schema CSV upload → concept list ──────────────────────────────────────

    @reactive.effect
    @reactive.event(input.schema_csv)
    def _load_schema() -> None:
        file_info = input.schema_csv()
        if not file_info:
            loaded_concepts.set([])
            return
        try:
            path     = file_info[0]["datapath"]
            concepts = load_concepts_from_csv(path)
            loaded_concepts.set(concepts)
            ui.notification_show(
                f"Loaded {len(concepts)} concepts from schema CSV.", type="message", duration=3
            )
        except Exception as exc:
            ui.notification_show(f"Error reading schema CSV: {exc}", type="error", duration=6)
            loaded_concepts.set([])

    @render.ui
    def concepts_preview():
        if v4_is_running():
            return ui.tags.span(
                "⟳ V4 running…", class_="badge bg-info text-dark d-block mt-1"
            )
        concepts = loaded_concepts()
        if not concepts:
            return ui.tags.small(
                "No concepts loaded — pipeline will extract base metadata only "
                "(Title, Author, Institution, Country, DOI).",
                class_="text-muted d-block mt-1",
            )
        preview = ", ".join(concepts[:5]) + (f" … +{len(concepts)-5} more" if len(concepts) > 5 else "")
        return ui.div(
            ui.tags.small(f"{len(concepts)} concepts loaded:", class_="text-muted d-block mt-1"),
            ui.tags.small(preview, class_="text-info"),
        )

    # ── V4 schema generation (subprocess) ─────────────────────────────────────

    @reactive.extended_task
    async def _v4_task(collection_name):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, _run_v4_subprocess, collection_name,
        )

    @reactive.effect
    @reactive.event(input.v4_btn)
    def _start_v4() -> None:
        if not ANTHROPIC_API_KEY:
            ui.notification_show("ANTHROPIC_API_KEY missing from .env", type="error", duration=8)
            return
        col_name = selected_collection()
        if not col_name:
            ui.notification_show("Select a collection first.", type="warning")
            return
        if is_running() or v4_is_running():
            ui.notification_show("A pipeline is already running.", type="warning")
            return
        log_lines.set([f"[V4] Running knowledge_workflow_V4.py for '{col_name}'…",
                        "(output will appear when V4 finishes)"])
        v4_is_running.set(True)
        run_start_time.set(time.time())
        last_heartbeat.set(time.time())
        _v4_task(col_name)

    @reactive.effect
    def _watch_v4_task() -> None:
        status = _v4_task.status()
        if status == "success":
            concepts, logs = _v4_task.result()
            loaded_concepts.set(concepts)
            log_lines.set(logs)
            v4_is_running.set(False)
            ui.notification_show(
                f"V4 complete — {len(concepts)} concept column(s) ready. Click ▶ Run Pipeline.",
                type="message", duration=6,
            )
        elif status == "error":
            log_lines.set([f"❌ V4 Error: {_v4_task.error()}"])
            v4_is_running.set(False)

    # ── V3 background task ────────────────────────────────────────────────────

    @reactive.extended_task
    async def _pipeline(collection_name, collection_id, concepts):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, _run_pipeline, collection_name, collection_id, concepts,
        )

    # ── Run button ────────────────────────────────────────────────────────────

    @reactive.effect
    @reactive.event(input.run_btn)
    def _start_run() -> None:
        missing = [k for k, v in [("ZOTERO_API_KEY", ZOTERO_API_KEY),
                                   ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY)] if not v]
        if missing:
            ui.notification_show(f"Missing from .env: {', '.join(missing)}", type="error", duration=8)
            return
        cmap = collections()
        if not cmap:
            ui.notification_show(
                "Collections still loading — try again in a moment." if collections_loading()
                else "No collections available. Check ZOTERO_API_KEY in .env.",
                type="warning",
            )
            return
        col_name = selected_collection()
        if not col_name or col_name not in cmap:
            ui.notification_show("Select a collection first.", type="warning")
            return
        if is_running() or v4_is_running():
            ui.notification_show("A pipeline is already running.", type="warning")
            return
        concepts = loaded_concepts()   # [] → base metadata only
        current_collection.set(col_name)
        log_lines.set([f"Starting pipeline for '{col_name}' with {len(concepts)} concept(s)…"])
        results.set(None)
        is_running.set(True)
        run_start_time.set(time.time())
        last_heartbeat.set(time.time())
        _pipeline(col_name, cmap[col_name], concepts)

    # ── Collect V3 results ────────────────────────────────────────────────────

    @reactive.effect
    def _watch_task() -> None:
        status = _pipeline.status()
        if status == "success":
            df, logs = _pipeline.result()
            results.set((df, current_collection()))
            log_lines.set(logs)
            is_running.set(False)
        elif status == "error":
            log_lines.set([f"❌ Error: {_pipeline.error()}"])
            is_running.set(False)

    # ── Heartbeat (separate effect — never mutates state inside a render) ──────

    @reactive.effect
    def _heartbeat() -> None:
        if not (is_running() or v4_is_running()):
            return
        reactive.invalidate_later(5)
        now     = time.time()
        elapsed = int(now - run_start_time())
        if elapsed < 30:
            return
        if now - last_heartbeat() < 30:
            return
        label        = "[V4]" if v4_is_running() else "[V3]"
        mins, secs   = divmod(elapsed, 60)
        hb_msg       = (f"⟳ {label} Still running… {mins}m {secs:02d}s elapsed"
                        if mins else f"⟳ {label} Still running… {secs}s elapsed")
        lines = log_lines()
        if lines and lines[-1].startswith("⟳"):
            log_lines.set(lines[:-1] + [hb_msg])
        else:
            log_lines.set(lines + [hb_msg])
        last_heartbeat.set(now)

    # ── Status badge ──────────────────────────────────────────────────────────

    @render.ui
    def status_badge():
        if v4_is_running():
            return ui.div(
                ui.tags.span("⟳ V4 running…", class_="badge bg-info text-dark"),
                class_="text-center mt-2",
            )
        if is_running():
            return ui.div(
                ui.tags.span("⟳ Running…", class_="badge bg-warning text-dark"),
                class_="text-center mt-2",
            )
        r = results()
        if r is not None:
            return ui.div(
                ui.tags.span(f"✓ {len(r[0])} row(s) extracted", class_="badge bg-success"),
                class_="text-center mt-2",
            )
        return ui.div()

    # ── Progress log (read-only render) ───────────────────────────────────────

    @render.text
    def log_out():
        return "\n".join(log_lines())

    # ── Results table ─────────────────────────────────────────────────────────

    @render.data_frame
    def results_tbl():
        r = results()
        if r:
            return render.DataGrid(r[0], filters=True, height="500px")
        return render.DataGrid(pd.DataFrame(columns=col_headers([])))

    # ── CSV download ──────────────────────────────────────────────────────────

    @render.download(
        filename=lambda: _make_filename(results()[1] if results() else "collection")
    )
    def dl_results():
        r = results()
        if r:
            yield r[0].to_csv(index=False)


# ── Entry point ───────────────────────────────────────────────────────────────

app = App(app_ui, server)
