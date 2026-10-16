"""Visual Exploration workspace: ontology graph, scoped search and grounded chat.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import asyncio
from pathlib import Path
from shiny import module, reactive, render, ui
from dpv_dashboard import catalog, exploration, media, research, chat_settings, visual_graph
from dpv_dashboard.auth import credentials
from dpv_dashboard import presentation
from dpv_dashboard.inspect import table
from dpv_dashboard.viewer import viewer, convert


@module.ui
def exploration_ui():
    return ui.nav_panel("Visual Exploration", ui.div(
        ui.p("CONNECTED RESEARCH", class_="eyebrow"), ui.h2("Visual Exploration"),
        ui.p("Explore a research topic, follow its evidence, or ask a question about the selected results. Search finds concepts and papers; WebVOWL reveals connections; Chat cites saved sources.", class_="page-purpose"),
        ui.layout_sidebar(ui.sidebar(
            ui.input_select("source", "Run / integration scope", choices={}),
            ui.input_text("query", "Search concepts, papers, evidence or IRIs"),
            ui.input_action_button("search", "Search", class_="btn-primary"),
            ui.div(
            ui.input_select("ontology", "Ontology", choices={}),
            ui.div(ui.input_checkbox("literature", "Include literature claims", True),
            ui.input_checkbox("hierarchy", "Show class hierarchy", False),
            ui.input_checkbox("mappings", "Show cross-ontology mappings", True),
            ui.input_checkbox("disjoint", "Show disjointness", False), class_="graph-controls"),
            ui.div(ui.input_select("focus", "Graph focus", choices={"": "Full ontology"}),
            ui.input_action_button("inspect", "Inspect focused concept provenance"), class_="graph-controls"), class_="graph-only-controls"), width=320),
            ui.navset_tab(
                ui.nav_panel("WebVOWL", ui.output_ui("graph_summary"), ui.output_ui("graph"), ui.output_ui("edge_detail")),
                ui.nav_panel("Search results", ui.p("Search for a topic using the search box. Select a result to read its evidence or focus it in the graph."),
                    ui.input_action_button("use_result", "Focus selected result in graph"), ui.output_ui("coverage"), ui.output_data_frame("results"), ui.output_ui("result_detail")),
                ui.nav_panel("Quality review", ui.p("These saved records are withheld from search and chat. Originals remain unchanged in All artifacts."),
                    ui.output_data_frame("excluded_results")),
                ui.nav_panel("Chat", ui.p("Ask about the selected research. Answers include links to supporting papers. Your workflow model is selected automatically; you can choose another saved model below."),
                    ui.input_text_area("message", "Your research question", rows=3, width="100%"),
                    ui.div(ui.input_action_button("send", "Send", class_="btn-primary"), ui.input_action_button("clear", "Clear chat"), class_="button-row"),
                    ui.tags.details(ui.tags.summary("Answer style & model"),
                        ui.input_select("mode", "Answer style", choices={"saved": "Find supporting evidence", "model": "AI answer with citations"}),
                        ui.input_password("session_key", "Gemini API key for this session (optional, never saved)", width="100%"),
                        ui.input_select("model", "Chat model", choices={}), ui.output_ui("model_info")),
                    ui.output_ui("history")), id="tabs")),
        class_="stage-heading"), value="explore")


@module.server
def exploration_server(input, output, session, context):
    files = reactive.Value({})
    signature = reactive.Value(None)
    graph_files = reactive.Value(((), []))
    hits = reactive.Value([])
    excluded = reactive.Value([])
    chat_history = reactive.Value([])
    busy = reactive.Value(False)
    chat_revision = reactive.Value(0)
    target_seen = None
    scope_seen = None

    def keys():
        """Saved credentials plus a Gemini key entered for this browser session only (held in memory, never written)."""
        key = (input.session_key() or "").strip()
        return {**credentials(), **({"GEMINI_API_KEY": key} if key else {})}

    @reactive.calc
    def available_models():
        context.tick()
        return chat_settings.choices(root(), context.project(), keys())

    @reactive.effect
    def model_choices():
        options = available_models()
        with reactive.isolate():
            previous = input.model()
        running = [k for k, v in options.items() if not v.get("offline")]
        default = previous if previous in running else "workflow" if "workflow" in running else next(iter(running), next(iter(options), ""))
        ui.update_select("model", choices={k: v["label"] for k, v in options.items()}, selected=default)

    @render.ui
    def model_info():
        option = available_models().get(input.model())
        if not option:
            return ui.p("Enter a Gemini API key above, or connect a model provider on Home, to enable AI answers. Evidence search remains available.")
        try:
            chat_settings.connection(option, keys())
            message = ("Uses the API key you entered for this session." if option.get("key_name") == "GEMINI_API_KEY" and (input.session_key() or "").strip()
                       else "Uses your saved model connection. No additional chat setup is needed.")
        except ValueError as exc:
            message = str(exc)
        return ui.div(ui.p(message),
            ui.tags.details(ui.tags.summary("Model details"), ui.p("Model identifier: " + option["model"]),
                            ui.p("Provider: " + chat_settings.PROVIDERS.get(option["profile"], "Saved connection"))))

    @reactive.effect
    def choices():
        nonlocal target_seen
        context.tick()
        choices = {str(p): presentation.run_label(p) for p in context.roots()}
        target = context.visual_target()
        with reactive.isolate():
            previous = input.source()
        if target.get("request") != target_seen and target.get("root") in choices:
            previous = target["root"]
        ui.update_select("source", choices=choices, selected=previous if previous in choices else next(iter(choices), ""))

    @reactive.calc
    def root():
        return next((p for p in context.roots() if str(p) == input.source()), None)

    @reactive.effect
    def ontologies():
        nonlocal target_seen
        context.tick()
        base = root()
        values = {}
        if base:
            for p in sorted(base.rglob("*.ttl")):
                try:
                    path = catalog.accessible(base, str(p.relative_to(base)))
                    if path:
                        label = presentation.ontology_label(p)
                        if label in values.values():
                            label += " · " + p.stem.replace("_", " ")
                        values[str(path)] = label
                except ValueError:
                    continue
        with reactive.isolate():
            previous, prior = input.ontology(), files.get()
        target = context.visual_target()
        if target.get("request") != target_seen and str(base) == target.get("root"):
            previous = target.get("file", "")
            target_seen = target.get("request")
        if values != prior:
            files.set(values)
        default = next((p for p in values if Path(p).name.endswith("_merged.ttl")), next((p for p in values if Path(p).name == "ontology.ttl"), next(iter(values), "")))
        ui.update_select("ontology", choices=values, selected=previous if previous in values else default)

    @reactive.calc
    def path():
        value = input.ontology()
        return Path(value) if value in files.get() else None

    @reactive.effect
    def poll():
        context.tick()
        selected = path()
        value = (str(selected), catalog.fingerprint(selected)) if selected else None
        with reactive.isolate():
            previous = signature.get()
        if value != previous:
            signature.set(value)
        graph_value = visual_graph.files(root(), selected, input.literature())
        with reactive.isolate():
            previous_graph = graph_files.get()
        if graph_value != previous_graph:
            graph_files.set(graph_value)

    @reactive.calc
    def rdf():
        value = signature.get()
        if not value:
            return None
        try:
            return exploration.graph(*value)
        except Exception:
            return None

    @reactive.effect
    def scope_reset():
        nonlocal scope_seen
        current = (str(root()), signature.get())
        if current == scope_seen:
            return
        scope_seen = current
        hits.set([])
        excluded.set([])
        chat_history.set([])
        with reactive.isolate():
            chat_revision.set(chat_revision.get() + 1)
        busy.set(False)
        model_chat.cancel()
        ui.update_select("focus", choices={"": "Full ontology"}, selected="")

    @render.ui
    def graph():
        payload = graph_payload()
        if payload is None:
            return ui.p("Choose an available Turtle ontology to explore its graph.")
        return viewer(None, session.ns("vowl"), payload=payload)

    @reactive.calc
    def graph_payload():
        entries, missing = graph_files.get()
        if not entries:
            return None
        combined, origins, loaded, failed = visual_graph.assemble(entries)
        focused = exploration.neighborhood(combined, input.focus(), show_disjoint=input.disjoint(), as_graph=True)
        return convert(focused, show_disjoint=input.disjoint(), show_hierarchy=input.hierarchy(), show_mappings=input.mappings(), origins=origins, show_literature=input.literature())

    @render.ui
    def graph_summary():
        payload = graph_payload()
        if payload is None:
            return ui.p("No graph available yet.")
        from collections import Counter
        counts = Counter(e["kind"] for e in payload["_dpv"]["edges"].values())
        entries, missing = graph_files.get()
        _, _, loaded, failed = visual_graph.assemble(entries)
        return ui.div(ui.p("Relationships supplied to viewer: " + "; ".join(f"{k}: {v}" for k,v in counts.items())),
            ui.div(*(ui.span(presentation.run_label(Path(run)), style=f"background:{color};padding:4px 8px;margin:4px;display:inline-block") for run, color in payload["_dpv"]["domain_colors"].items()),
                   ui.span("Gray: shared, external or unassigned nodes", class_="muted")),
            ui.p("Literature claims are reported findings; ontology restrictions describe class constraints. Quote matching does not prove a claim."),
            ui.tags.details(ui.tags.summary("Graph sources & coverage"), *(ui.p(f"{v['run']} / {v['file']} · {v['layer']}") for v in loaded),
                *(ui.p(v) for v in [*missing, *failed]), ui.p(f"Malformed concept nodes withheld: {payload['_dpv']['withheld_nodes']}")))

    @render.ui
    def edge_detail():
        event, payload = input.edge(), graph_payload()
        if not isinstance(event, dict) or not payload or event.get("token") != payload["_dpv"]["token"]:
            return ui.p("Click a relationship label in the graph to see its provenance and supporting quotes.")
        edge = payload["_dpv"]["edges"].get(event.get("id"))
        if not edge:
            return None
        contents = [ui.h4(f"{edge['subject_name']} — {edge['relation']} — {edge['object_name']}"), ui.p(edge["kind"])]
        for origin in edge["sources"]:
            contents.append(ui.p(f"Source: {presentation.run_label(Path(origin['run']))} / {origin['file']}"))
        for claim in edge["claims"]:
            contents += [ui.tags.blockquote(quote) for quote in claim["quotes"]]
            if not claim["quotes"]:
                contents.append(ui.p("No supporting quote recorded for this claim."))
            contents.append(ui.p("At least one supporting quote matched source text" if "true" in claim["verification"] else "Quote verification not recorded or not matched"))
            contents.append(ui.p("Conditions: " + "; ".join(claim["conditions"])) if claim["conditions"] else None)
            for citation in claim["papers"]:
                matches = []
                source_names = {s["run"] for s in edge["sources"]}
                for source in research.source_roots(root()):
                    if source.name not in source_names:
                        continue
                    data = research.index(source)
                    for key, paper in data.papers.items():
                        if citation == "zotero:" + key or paper.get("doi") and citation == "https://doi.org/" + paper["doi"]:
                            matches.append(media.reference(data, "Open paper: " + paper.get("title", key), paper=key))
                contents += matches or [ui.p("Recorded paper source: ", media.external_reference(citation, citation))]
        if not edge["claims"]:
            contents.append(ui.p("No paper-level claim evidence was recorded for this displayed ontology edge."))
        return ui.card(*contents)

    @reactive.effect
    @reactive.event(input.search)
    def search():
        try:
            withheld = []
            rows = exploration.search(exploration.documents(root(), path(), withheld), input.query())
            excluded.set(withheld)
            hits.set(rows)
            choices = {"": "Full ontology", **{h["iri"]: h["label"] for h in rows if h.get("iri")}}
            ui.update_select("focus", choices=choices, selected="")
            ui.update_navset("tabs", selected="Search results")
        except ValueError as exc:
            context.notice(str(exc), error=True)

    @render.data_frame
    def results():
        return presentation.grid(table([{"actions": actions(r), "result_id": i, "label": r.get("label"), "kind": r.get("kind"),
            "source_run": r.get("source_run"), "verification": r.get("verification", "Not applicable")} for i, r in enumerate(hits.get())]),
                               filters=True, selection_mode="row", height="440px", width="100%")

    def actions(row):
        resolved = exploration.resolve_source(row, context.roots())
        if not resolved:
            return ui.span("Source evidence/provenance unavailable", class_="muted")
        attrs = {"data-root": str(resolved["root"]), "data-canonical": resolved["canonical"] or "", "data-paper": resolved["paper"] or ""}
        links = [ui.tags.button("View provenance", type="button", class_="btn btn-sm btn-outline-secondary research-nav",
                    **attrs, **{"data-tab": "Original → canonical"})]
        if resolved["has_evidence"]:
            links.insert(0, ui.tags.button("View evidence", type="button", class_="btn btn-sm btn-outline-primary research-nav",
                         **attrs, **{"data-tab": "Paper & evidence"}))
        else:
            links.append(ui.span("No linked paper available", class_="muted"))
        if resolved["open_paper"]:
            links.append(ui.tags.button("Open paper", type="button", class_="btn btn-sm btn-outline-secondary research-open",
                **{**attrs, "data-paper": resolved["open_paper"]}))
        return ui.div(*links, class_="search-actions")

    @render.ui
    def coverage():
        return ui.p(f"{len(hits.get())} matches. {len(excluded.get())} records withheld for quality review; see Quality review.")

    @render.data_frame
    def excluded_results():
        return presentation.grid(table(excluded.get()), filters=True, height="440px", width="100%")

    @reactive.calc
    def selected():
        rows = presentation.selected(results)
        if rows.empty:
            return None
        number = int(rows.iloc[0]["result_id"])
        values = hits.get()
        return values[number] if 0 <= number < len(values) else None

    @render.ui
    def result_detail():
        row = selected()
        if not row:
            return ui.p("Select a search result to read its saved detail and open supporting papers.")
        data = research.index(Path(row["root"]))
        return ui.div(actions(row), ui.p(media.reference_text(data, row.get("text", "")[:2400], row.get("paper"))),
                      ui.tags.details(ui.tags.summary("Source identifiers"), ui.p(media.external_reference(row.get("iri", ""), row.get("iri", ""))),
                                      ui.p("Source run: " + row["source_run"]), ui.p("Concept: " + str(row.get("canonical_id", "")))))

    @reactive.effect
    @reactive.event(input.use_result)
    def use_result():
        row = selected()
        if not row or not row.get("iri"):
            context.notice("Select a concept or ontology term with a recorded IRI.")
            return
        ui.update_select("focus", selected=row["iri"])
        ui.update_navset("tabs", selected="WebVOWL")

    @reactive.effect
    @reactive.event(input.inspect)
    def inspect():
        for source in research.source_roots(root()):
            data = research.index(source)
            cid = data.iri_ids.get(input.focus())
            if cid:
                context.inspect(source, canonical=cid)
                return
        context.notice("Choose a focused class with an available source concept record.")

    @render.ui
    def history():
        return ui.div(*(ui.card(ui.strong(h["question"]), media.chat_answer(h["answer"], h["sources"]),
            *(ui.div(ui.tags.small(f"[S{i}] {presentation.run_label(Path(r['root']))} · {r.get('label', '')} "),
                     media.cited_reference(r, "Open cited evidence"))
              for i, r in enumerate(h["sources"], 1))) for h in chat_history.get()),
            ui.p("Answer in progress…") if busy.get() else None)

    @reactive.effect
    @reactive.event(input.send)
    def send():
        if busy.get():
            return
        question = input.message().strip()
        if not question or len(question) > 1000:
            context.notice("Enter a question of 1–1,000 characters.", error=True)
            return
        scope = (str(root()), signature.get())
        busy.set(True)
        try:
            withheld = []
            rows = exploration.search(exploration.documents(root(), path(), withheld), question, 12)
            excluded.set(withheld)
            if input.mode() == "model" and rows:
                settings, name = chat_settings.connection(available_models().get(input.model()), keys())
                model_chat.invoke(question, rows, settings, name, scope, chat_revision.get())
                return
            else:
                answer = exploration.evidence_answer(question, rows)
            if (str(root()), signature.get()) == scope:
                chat_history.set([*chat_history.get(), {"question": question, "answer": answer, "sources": rows[:6]}][-12:])
                ui.update_text_area("message", value="")
        except ValueError as exc:
            context.notice(str(exc), error=True)
        except Exception:
            context.notice("The configured chat provider could not return an answer. Check its dashboard settings and availability.", error=True)
        finally:
            if input.mode() != "model" or model_chat.status() != "running":
                busy.set(False)

    @reactive.extended_task
    async def model_chat(question, rows, settings, name, scope, revision):
        try:
            answer = await asyncio.to_thread(exploration.model_answer, question, rows, settings, name)
            return {"answer": "AI answer — check the linked sources.\n\n" + answer,
                    "question": question, "sources": rows, "scope": scope, "revision": revision}
        except ValueError as exc:
            return {"error": str(exc), "scope": scope, "revision": revision}
        except Exception:
            return {"error": "The configured chat provider could not return an answer. Check its dashboard settings and availability.",
                    "scope": scope, "revision": revision}

    @reactive.effect
    def receive_model():
        result = model_chat.result()
        busy.set(False)
        if result["scope"] != (str(root()), signature.get()) or result["revision"] != chat_revision.get():
            return
        if result.get("error"):
            context.notice(result["error"], error=True)
            return
        with reactive.isolate():
            previous = chat_history.get()
        chat_history.set([*previous, result][-12:])
        ui.update_text_area("message", value="")

    @reactive.effect
    @reactive.event(input.clear)
    def clear():
        chat_history.set([])
        chat_revision.set(chat_revision.get() + 1)
        model_chat.cancel()
        busy.set(False)
