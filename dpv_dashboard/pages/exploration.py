"""Visual Exploration workspace: ontology graph, scoped search and grounded chat.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import asyncio
from pathlib import Path
from shiny import module, reactive, render, ui
from dpv_dashboard import catalog, exploration, media, research, chat_settings, visual_graph
from dpv_dashboard.auth import credentials
from dpv_dashboard import presentation, research_tools, workspace_tools
from dpv_dashboard.inspect import table
from dpv_dashboard.viewer import viewer


@module.ui
def exploration_ui():
    return ui.nav_panel("Visual Exploration", ui.div(
        ui.p("CONNECTED RESEARCH", class_="eyebrow"), ui.h2("Visual Exploration"),
        ui.p("Explore a research topic, follow its evidence, or ask a question about the selected results. Search finds concepts and papers; WebVOWL reveals connections; Chat cites saved sources.", class_="page-purpose"),
        ui.div(ui.div(
            ui.input_select("source", "Run / integration scope", choices={}),
            ui.input_select("preset", "View purpose", research_tools.PRESETS, selected="overview"),
            ui.input_text("query", "Search concepts, papers, evidence or IRIs"),
            ui.input_action_button("search", "Search", class_="btn-primary"),
            ui.tags.details(ui.tags.summary("Graph settings & research tools"),
            workspace_tools.graph_controls(),
            ui.input_select("ontology", "Ontology", choices={}),
            ui.input_select("graph_size", "Graph size", choices={"160": "Overview · up to 160 nodes", "400": "Expanded · up to 400 nodes", "0": "Full graph · may be slow"}, selected="160"),
            ui.div(ui.input_checkbox("literature", "Include literature claims", True),
            ui.input_checkbox("hierarchy", "Show class hierarchy", False),
            ui.input_checkbox("mappings", "Show cross-ontology mappings", True),
            ui.input_checkbox("disjoint", "Show disjointness", False), class_="graph-controls"),
            ui.div(ui.input_select("focus", "Graph focus", choices={"": "Whole scope"}),
            ui.input_action_button("inspect", "Open focused concept evidence"), class_="graph-controls"),
            workspace_tools.controls(), class_="graph-only-controls"), class_="exploration-controls"),
            ui.navset_tab(
                ui.nav_panel("Graph", ui.output_ui("graph_summary"),
                    ui.div(ui.div(ui.output_ui("graph"), class_="graph-canvas"),
                           ui.tags.aside(ui.output_ui("inspector"), class_="graph-inspector", **{"aria-label": "Selected concept or relationship"}), class_="graph-workspace"),
                    ui.tags.details(ui.tags.summary("Relationships as a table"), ui.output_data_frame("relationship_list")), value="WebVOWL"),
                ui.nav_panel("Search results", ui.p("Search for a topic using the search box. Select a result to read its evidence or focus it in the graph."),
                    ui.input_action_button("use_result", "Focus selected result in graph"), ui.output_ui("coverage"), ui.output_data_frame("results"), ui.output_ui("result_detail")),
                ui.nav_panel("Chat", ui.p("Ask about the selected research. Answers include links to supporting papers. Your workflow model is selected automatically; you can choose another saved model below."),
                    ui.input_select("mode", "How would you like to answer?", choices={"saved": "Find supporting evidence · no API key needed", "model": "AI answer with citations · optional Gemini key"}),
                    ui.tags.details(ui.tags.summary("Optional AI connection"), ui.input_password("session_key", "Your Gemini API key (this session only)", width="100%"),
                    ui.p(ui.tags.a("Get a Gemini API key in Google AI Studio", href="https://aistudio.google.com/apikey", target="_blank", rel="noopener noreferrer")),
                    ui.p("Your key is held in this session and is not saved. AI answers send your question and selected research evidence to Google using your key.")),
                    ui.p("Try: Which saved findings mention degradation rate? What evidence supports the selected concept?"),
                    ui.input_text_area("message", "Your research question", rows=3, width="100%"),
                    ui.div(ui.input_action_button("send", "Send", class_="btn-primary"), ui.input_action_button("clear", "Clear chat"), class_="button-row"),
                    ui.tags.details(ui.tags.summary("Answer style & model"),
                        ui.input_select("model", "Chat model", choices={}), ui.output_ui("model_info")),
                    ui.output_ui("history")),
                ui.nav_panel("Quality review", ui.output_ui("quality_summary"),
                    ui.output_data_frame("excluded_results")), id="tabs", selected="WebVOWL")),
        class_="stage-heading"), value="explore")


@module.server
def exploration_server(input, output, session, context):
    files = reactive.Value({})
    signature = reactive.Value(None)
    graph_files = reactive.Value(((), []))
    prepared = reactive.Value(None)
    preparation_error = reactive.Value("")
    hits = reactive.Value([])
    excluded = reactive.Value([])
    chat_history = reactive.Value([])
    busy = reactive.Value(False)
    chat_revision = reactive.Value(0)
    target_seen = None
    scope_seen = None
    selection_seen = None
    session_key_seen = False
    hidden_nodes = reactive.Value(())
    ontology_scope = reactive.Value(None)

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
        nonlocal session_key_seen
        if not context.active("explore"):
            return
        options = available_models()
        with reactive.isolate():
            previous = input.model()
        running = [k for k, v in options.items() if not v.get("offline")]
        session_gemini = bool((input.session_key() or "").strip()) and "gemini" in running
        default = "gemini" if session_gemini and not session_key_seen else previous if previous in running else "workflow" if "workflow" in running else next(iter(running), next(iter(options), ""))
        session_key_seen = session_gemini
        ui.update_select("model", choices={k: v["label"] for k, v in options.items()}, selected=default)

    @reactive.effect
    @reactive.event(input.session_key)
    def session_chat():
        if (input.session_key() or "").strip():
            ui.update_select("mode", selected="model")

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
        nonlocal target_seen, selection_seen
        context.tick()
        choices = {str(p): presentation.run_label(p) for p in context.roots()}
        target = context.visual_target()
        with reactive.isolate():
            previous = input.source()
        selected_scope = str(context.folder("extract"))
        if selected_scope != selection_seen:
            previous = selected_scope
            selection_seen = selected_scope
        if target.get("request") != target_seen and target.get("root") in choices:
            previous = target["root"]
        ui.update_select("source", choices=choices, selected=previous if previous in choices else next(iter(choices), ""))

    @reactive.calc
    def root():
        return next((p for p in context.roots() if str(p) == input.source()), None)

    @reactive.effect
    def ontologies():
        nonlocal target_seen
        if not context.active("explore"):
            return
        context.tick()
        base = root()
        values = {}
        if base:
            for p in sorted(base.rglob("*.ttl")):
                try:
                    path = research_tools.available(base, p)
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
        integrated = next((p for p in values if not Path(p).name.endswith("_merged.ttl") and str(Path(p).with_name(Path(p).stem + "_merged.ttl")) in values), None)
        default = integrated or next((p for p in values if Path(p).name == "ontology.ttl"), next(iter(values), ""))
        ui.update_select("ontology", choices=values, selected=previous if previous in values else default)
        ontology_scope.set(str(base))

    @reactive.calc
    def path():
        value = input.ontology()
        base = root()
        return Path(value) if base and value in files.get() and Path(value).is_relative_to(base) else None

    @reactive.effect
    def poll():
        if not context.active("explore"):
            return
        context.tick()
        selected = path()
        value = (str(selected), catalog.fingerprint(selected)) if selected else None
        with reactive.isolate():
            previous = signature.get()
        if value != previous:
            signature.set(value)
        graph_value = research_tools.files(root(), selected, input.literature())
        with reactive.isolate():
            previous_graph = graph_files.get()
        if graph_value != previous_graph:
            graph_files.set(graph_value)

    @reactive.effect
    def scope_reset():
        nonlocal scope_seen
        current = (str(root()), signature.get())
        if current == scope_seen:
            return
        scope_seen = current
        hidden_nodes.set(())
        prepared.set(None)
        hits.set([])
        excluded.set([])
        chat_history.set([])
        with reactive.isolate():
            chat_revision.set(chat_revision.get() + 1)
        busy.set(False)
        model_chat.cancel()
        ui.update_select("focus", choices={"": "Whole scope"}, selected="")

    @render.ui
    def graph():
        payload = graph_payload()
        if payload is None:
            if preparation_error.get():
                return ui.p(preparation_error.get(), class_="text-warning")
            loading = root() is None or ontology_scope.get() != str(root()) or path() is not None
            return ui.p("Loading the selected research scope… The graph will appear here. You can use the other tabs while it loads." if loading else "No readable ontology was recorded in this scope. Choose another run or inspect All artifacts.", role="status")
        return viewer(None, session.ns("vowl"), payload=payload)

    @reactive.calc
    def graph_request():
        entries, missing = graph_files.get()
        selected = path()
        if not entries or selected is None or entries[0][0] != str(selected.resolve()):
            return None
        return ((entries, input.focus(), int(input.graph_size()), input.disjoint(), input.hierarchy(), input.mappings(), input.literature()),
                input.preset() or "overview", int(input.depth() or 0), input.relation_filter() or "", input.domain_filter() or "", hidden_nodes.get())

    @reactive.extended_task
    async def prepare_graph(request):
        try:
            payload = await asyncio.to_thread(research_tools.prepare, request)
            return {"request": request, "payload": payload}
        except ValueError as exc:
            return {"request": request, "error": str(exc)}
        except Exception:
            return {"request": request, "error": "Graph preparation failed. Try another ontology or a smaller view."}

    requested = reactive.Value(None)

    @reactive.effect
    def request_graph():
        # Parsing holds the interpreter; prepare graphs only while this page is open, so other pages stay responsive.
        if not context.active("explore"):
            return
        request = graph_request()
        with reactive.isolate():
            if request == requested.get():
                return
        requested.set(request)
        preparation_error.set("")
        prepare_graph.cancel()
        if request:
            prepare_graph.invoke(request)

    @reactive.effect
    def receive_graph():
        result = prepare_graph.result()
        if result["request"] != graph_request():
            return
        if result.get("error"):
            preparation_error.set(result["error"])
            context.notice(result["error"], error=True)
        else:
            payload = result["payload"]
            payload["_dpv"]["scope"] = str(root()) + "/" + path().name
            payload["_dpv"]["source_signature"] = research_tools.fingerprint(research_tools.files(root(), path(), True)[0])
            prepared.set(payload)

    @reactive.calc
    def graph_payload():
        return prepared.get()

    workspace_tools.server(input, output, session, context, root, path, graph_files, graph_payload)

    @reactive.effect
    @reactive.event(input.preset)
    def preset_settings():
        selected = input.preset()
        if selected == "ontology":
            ui.update_checkbox("literature", value=False)
            ui.update_checkbox("hierarchy", value=True)
        elif selected in ("findings", "connections", "overview"):
            ui.update_checkbox("literature", value=True)
            ui.update_checkbox("hierarchy", value=False)
        ui.update_checkbox("mappings", value=selected != "findings")

    @reactive.effect
    @reactive.event(input.workspace_focus)
    def workspace_focus():
        payload = graph_payload()
        event = input.workspace_focus()
        iri = event.get("iri") if isinstance(event, dict) else event
        if not payload or iri not in {r["iri"] for r in payload["classAttribute"]}:
            return
        ui.update_select("focus", choices={"": "Whole scope", **{r["iri"]: r["label"].get("en", r["iri"]) for r in payload["classAttribute"]}}, selected=iri)
        ui.update_select("depth", selected="2" if isinstance(event, dict) and event.get("depth") == "2" else "1")

    @reactive.effect
    @reactive.event(input.hidden_nodes)
    def update_hidden():
        values = input.hidden_nodes()
        if isinstance(values, list) and len(values) <= 1000 and all(isinstance(v, str) and len(v) < 4000 for v in values):
            hidden_nodes.set(tuple(values))

    @render.data_frame
    def relationship_list():
        payload = graph_payload()
        return presentation.grid(table([{"subject": e["subject_name"], "relation": e["relation"], "object": e["object_name"],
             "origin": e["kind"], "recorded_citations": len({p for c in e["claims"] for p in c["papers"]})}
             for e in payload["_dpv"]["edges"].values()] if payload else []), filters=True, height="350px")

    @render.ui
    def graph_summary():
        payload = graph_payload()
        if payload is None:
            return ui.p("No ontology available in this saved scope." if root() and ontology_scope.get() == str(root()) and not files.get() else "Preparing selected scope…", class_="muted", role="status")
        from collections import Counter
        counts = Counter(e["kind"] for e in payload["_dpv"]["edges"].values())
        entries, missing = graph_files.get()
        coverage = payload["_dpv"]["coverage"]
        loaded, failed = coverage["loaded"], coverage["failed"]
        return ui.div(ui.strong(presentation.run_label(root()) if root() else "Select a scope"),
            ui.p("Updating graph settings… showing the previous view until preparation completes.", role="status") if prepare_graph.status() == "running" else None,
            ui.p("Some graph sources are unavailable. Open Graph sources & coverage for details.", class_="text-warning") if missing or failed else None,
            ui.p(f"Loaded view: {len(payload['class'])} concepts · {len(payload['property'])} relationships. Search covers the complete authorized scope.", class_="muted"),
            ui.div(*(ui.span({"tea": "Techno-economic analysis", "si-topcon": "Silicon TOPCon", "reliability": "Reliability"}.get(run.split("-n", 1)[0], run.split("-n", 1)[0].replace("-", " ").title()),
                            title=presentation.run_label(Path(run)), style=f"background:{color};padding:4px 8px;margin:4px;display:inline-block") for run, color in payload["_dpv"]["domain_colors"].items()),
                   ui.span("Gray: shared, external or unassigned nodes", class_="muted")),
            ui.tags.details(ui.tags.summary("What this graph means · sources & coverage"),
                ui.p("Literature claims report findings; ontology restrictions describe modeled constraints; mappings connect vocabularies. A graph path does not establish causation."),
                ui.p(f"Selected projection before size limits: {coverage['total_nodes']} nodes / {coverage['total_edges']} relationships."),
                ui.p("Relationship origins: " + "; ".join(f"{k}: {v}" for k,v in counts.items())),
                *(ui.p(f"{v['run']} / {v['file']} · {v['layer']}") for v in loaded),
                *(ui.p(v) for v in [*missing, *failed]), ui.p(f"Malformed concept nodes withheld: {payload['_dpv']['withheld_nodes']}")), class_="graph-summary")

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
            choices = {"": "Whole scope", **{h["iri"]: h["label"] for h in rows if h.get("iri")}}
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
    @reactive.event(input.node)
    def node_evidence():
        event, payload = input.node(), graph_payload()
        if not isinstance(event, dict) or not payload or event.get("token") != payload["_dpv"]["token"]:
            return
        iri = event.get("iri")
        if not isinstance(iri, str) or not any(row.get("iri") == iri for row in payload["classAttribute"]):
            return
        resolved = exploration.resolve_source({"root": str(root()), "iri": iri}, context.roots())
        if resolved:
            context.inspect(resolved["root"], canonical=resolved["canonical"], paper=resolved["open_paper"], tab="Paper & evidence")
        else:
            context.notice("This node has no unique recorded concept in the displayed source runs. Inspect Graph sources & coverage for its sources.")

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
