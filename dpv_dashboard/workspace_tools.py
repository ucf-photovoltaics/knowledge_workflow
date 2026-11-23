"""Research inspector, typed paths, matched comparisons and versioned exports."""
import asyncio
import json
from pathlib import Path
from shiny import reactive, render, ui
from dpv_dashboard import research, research_tools, presentation, media, catalog, visual_graph
from dpv_dashboard.viewer import viewer


def controls():
    return ui.tags.details(ui.tags.summary("Research tools · paths, comparisons & exports"),
        ui.p("Load the complete selected graph to search paths and backlinks beyond the visible neighborhood. Graph paths do not establish causation."),
        ui.input_action_button("load_tools", "Load full-scope research tools"), ui.output_ui("tools_status"),
        ui.input_selectize("path_start", "From concept", choices={}), ui.input_selectize("path_end", "To concept", choices={}),
        ui.input_checkbox_group("path_kinds", "Allowed relationship origins", choices={}),
        ui.input_numeric("path_hops", "Maximum path length", 3, min=1, max=6),
        ui.input_select("path_direction", "Direction", {"outgoing": "Follow recorded arrow direction", "either": "Either direction · association exploration"}),
        ui.input_action_button("find_path", "Find a recorded path"), ui.output_ui("path_result"),
        ui.hr(), ui.input_select("compare_run", "Compare another contributing run", choices={}),
        ui.input_action_button("compare_runs", "Compare shared-paper vocabulary"), ui.output_ui("comparison_result"),
        ui.hr(), ui.p("Exports include the current graph subset, source fingerprints and evidence. No model key is included."),
        ui.download_button("graph_json", "Graph + provenance JSON"), ui.download_button("graph_csv", "Relationships + evidence CSV"),
        ui.download_button("graph_bib", "Recorded citations BibTeX"),
        ui.tags.button("Export graph SVG", type="button", class_="btn btn-default workspace-action", **{"data-action": "export"}))


def graph_controls():
    return ui.div(ui.input_select("depth", "Neighborhood", {"0": "Overview / all available depth", "1": "One hop from focused concept", "2": "Two hops from focused concept"}),
        ui.input_select("relation_filter", "Relationship", {"": "All recorded relationships"}),
        ui.input_select("domain_filter", "Domain source", {"": "All contributing domains"}),
        ui.input_text("view_name", "Name this research view", value="My research view"),
        ui.input_select("saved_view", "Saved views in this browser", {"": "Choose a saved view"}),
        ui.div(*(ui.tags.button(label, type="button", class_="btn btn-sm btn-outline-secondary workspace-action", **{"data-action": action})
                 for action, label in (("back", "Back"), ("forward", "Forward"), ("fit", "Fit graph"), ("freeze", "Freeze layout"),
                                       ("pin", "Pin selected"), ("hide", "Hide selected"), ("undo", "Undo hide"), ("reset", "Reset view"),
                                       ("save", "Save view"), ("restore", "Restore saved view"))), class_="workspace-toolbar"),
        ui.p("Saved views stay in this browser and reopen only in the same source scope. Double-click a node to open its evidence trace.", class_="muted"))


def edge_card(edge, root):
    contents = [ui.h4(f"{edge['subject_name']} → {edge['relation']} → {edge['object_name']}"), ui.span(edge["kind"], class_="status")]
    contents.extend(ui.p("Source: " + presentation.run_label(Path(s["run"])) + " / " + s["file"]) for s in edge["sources"])
    papers = {p for c in edge["claims"] for p in c["papers"]}
    contents.append(ui.p(f"{len(papers)} distinct recorded citation identifiers (not a scientific confidence score)."))
    for claim in edge["claims"]:
        contents.extend(ui.tags.blockquote(q) for q in claim["quotes"])
        contents.append(ui.p("Quote located in parsed text" if "true" in claim["verification"] else "Text match not recorded or not confirmed"))
        if claim["conditions"]:
            contents.append(ui.p("Reported conditions: " + "; ".join(claim["conditions"])))
    if not edge["claims"]:
        contents.append(ui.p("No paper-level claim evidence recorded for this edge. This may describe an ontology constraint or a mapping."))
    # Resolve recorded citations against allowed contributing sources; do not invent paper joins.
    for source in research.source_roots(root):
        data = research.index(source)
        for key, paper in data.papers.items():
            if "zotero:" + key in papers or paper.get("doi") and "https://doi.org/" + paper["doi"] in papers:
                contents.append(media.reference(data, paper.get("title", key), paper=key))
    contents.extend(media.external_reference(p, p) for p in sorted(papers) if p.startswith(("http://", "https://")))
    contents.append(ui.p("A text match does not establish scientific validity. Inspect the paper context and recorded conditions.", class_="muted"))
    return ui.div(*contents)


def server(input, output, session, context, root, path, graph_files, graph_payload):
    full = reactive.Value(None)
    full_scope = reactive.Value(None)
    selection = reactive.Value(None)
    path_steps = reactive.Value(None)
    comparison = reactive.Value(None)

    def scope():
        entries, _ = research_tools.files(root(), path(), True)
        return (str(root()), str(path()), research_tools.fingerprint(entries))

    def current_full():
        payload = full.get()
        if payload is None:
            return None
        return payload if full_scope.get() == scope() else None

    def comparison_roots():
        return [p for p in context.comparison_roots() if root() and p.parent == root().parent
                and p != root() and ((p / "run.json").is_file() or (p / "integration.json").is_file())]

    @reactive.extended_task
    async def load_projection(entries, stamp):
        try:
            payload, *_ = await asyncio.to_thread(visual_graph.projection, entries, True, True, True, True)
            return {"payload": payload, "scope": stamp}
        except Exception:
            return {"error": "Full graph unavailable. Check source coverage and retry.", "scope": stamp}

    @reactive.effect
    @reactive.event(input.load_tools)
    def request_tools():
        if root() is None or path() is None:
            context.notice("Choose a saved ontology first.")
            return
        entries, _ = research_tools.files(root(), path(), True)
        load_projection.invoke(entries, scope())

    @reactive.effect
    def receive_tools():
        result = load_projection.result()
        if result["scope"] != scope():
            return
        if result.get("error"):
            context.notice(result["error"], error=True)
            return
        full.set(result["payload"])
        full_scope.set(result["scope"])
        attrs = result["payload"]["classAttribute"]
        choices = {r["iri"]: r["label"].get("en", r["iri"]) for r in attrs}
        ui.update_selectize("path_start", choices=choices, server=True)
        ui.update_selectize("path_end", choices=choices, server=True)
        kinds = sorted({e["kind"] for e in result["payload"]["_dpv"]["edges"].values()})
        ui.update_checkbox_group("path_kinds", choices=kinds, selected=[k for k in kinds if k == "Literature claim"] or kinds[:1])

    @render.ui
    def tools_status():
        payload = current_full()
        if payload:
            return ui.p(f"Full scope ready: {len(payload['class']):,} concepts. Filters in the graph do not limit path search.")
        return ui.p("Preparing full scope…" if load_projection.status() == "running" else "Full-scope tools have not been loaded for this ontology.")

    @reactive.effect
    def tool_choices():
        payload = graph_payload()
        if payload:
            kinds = sorted({e["relation"] for e in payload["_dpv"]["edges"].values()})
            with reactive.isolate():
                selected = input.relation_filter()
            # Preserve the selected relation when a filter removes all other relation choices.
            if selected and selected not in kinds:
                kinds.append(selected)
            ui.update_select("relation_filter", choices={"": "All relationships", **{k: k for k in kinds}}, selected=selected or "")
            with reactive.isolate():
                domain = input.domain_filter()
            domains = payload["_dpv"]["domain_colors"]
            ui.update_select("domain_filter", choices={"": "All contributing domains", **{k: presentation.run_label(Path(k)) for k in domains}}, selected=domain if domain in domains else "")
        choices = {str(p): presentation.run_label(p) for p in comparison_roots()}
        with reactive.isolate():
            comparison_choice = input.compare_run()
        ui.update_select("compare_run", choices={"": "Choose a run in this experiment", **choices}, selected=comparison_choice if comparison_choice in choices else "")

    def selected_graph_item(event):
        payload = graph_payload()
        candidates = [p for p in (payload, current_full()) if p]
        if isinstance(event, dict) and any(event.get("token") == p["_dpv"]["token"] for p in candidates):
            selection.set(event)

    @reactive.effect
    @reactive.event(input.selection)
    def selected_node():
        selected_graph_item(input.selection())

    @reactive.effect
    @reactive.event(input.edge)
    def selected_edge():
        selected_graph_item(input.edge())

    @render.ui
    def inspector():
        payload, event = graph_payload(), selection.get()
        whole = current_full()
        if event and whole and event.get("token") == whole["_dpv"]["token"]:
            payload = whole
        if not payload or not event or event.get("token") != payload["_dpv"]["token"]:
            return ui.div(ui.h4("Inspect a concept or relationship"), ui.p("Click a node to read its meaning and connections. Click an arrow label to read its origin and evidence."),
                          ui.p("Double-click a node for its complete evidence trace."), class_="inspector-empty")
        if event.get("id") in payload["_dpv"]["edges"]:
            return edge_card(payload["_dpv"]["edges"][event["id"]], root())
        iri = event.get("iri")
        node = next((n for n in payload["classAttribute"] if n["iri"] == iri), None)
        if node is None:
            return ui.p("Choose a concept from the current graph.")
        contents = [ui.h4(node["label"].get("en", iri)), ui.tags.code(iri),
                    ui.div(ui.tags.button("Focus here · one hop", type="button", class_="btn btn-primary inspector-focus", **{"data-iri": iri}),
                           ui.tags.button("Expand neighbors · two hops", type="button", class_="btn btn-default inspector-focus", **{"data-iri": iri, "data-depth": "2"}),
                           ui.tags.button("Copy IRI", type="button", class_="btn btn-default copy-iri", **{"data-iri": iri}), class_="button-row")]
        for source in research.source_roots(root()):
            data = research.index(source)
            cid = data.iri_ids.get(iri)
            if not cid:
                continue
            concept = data.concepts[cid]
            contents.extend([ui.h5(presentation.run_label(source)), ui.p(concept.get("definition") or "Definition not recorded."),
                ui.p("Definition source/status: " + str(presentation.friendly(concept.get("definition_status", "not_recorded")))),
                ui.p("Also called: " + "; ".join(str(x) for x in concept.get("alt_labels", []))),
                ui.p("Review: " + "; ".join(str(presentation.friendly(x)) for x in concept.get("review_flags", [])) if concept.get("review_flags") else "No review flags recorded; this is not an acceptance decision."),
                media.reference(data, "Open evidence, normalization & ontology context", canonical=cid)])
            papers = {r["paper"] for r in data.by_canonical.get(cid, [])} | set(concept.get("papers", []))
            identities = {research_tools.paper_identity(data.papers[k], k): k for k in papers if k in data.papers}
            contents.append(ui.h5(f"Supporting papers in this domain ({len(identities)})"))
            contents.extend(media.reference(data, data.papers[k].get("title", k), paper=k) for k in list(identities.values())[:20])
            if len(identities) > 20:
                contents.append(ui.p("First 20 papers shown. Open the complete evidence trace for the source records.", class_="muted"))
            lineage = data.by_canonical.get(cid, [])
            contents.append(ui.tags.details(ui.tags.summary("Original terms & lineage"), *(ui.p(str(r.get("original_label", "")) + " → " + data.label(cid) + " · " + r.get("lineage_status", "not recorded")) for r in lineage[:30])))
        all_payload = current_full() or payload
        edges = all_payload["_dpv"]["edges"]
        contents.append(ui.h5("Where is this concept used?"))
        contents.append(ui.p(("Full-scope connections. " if current_full() else "Connections in the loaded graph only; load full-scope tools to inspect all backlinks. ") + "The first 60 relationships in each direction are listed below.", class_="muted"))
        for label, key in (("Outgoing relationships", "subject"), ("Incoming relationships", "object")):
            related = [e for e in edges.values() if e.get(key) == iri]
            contents.append(ui.tags.details(ui.tags.summary(f"{label} ({len(related)})"), *(ui.div(
                ui.p(f"{e['subject_name']} → {e['relation']} → {e['object_name']} · {e['kind']}"),
                ui.tags.button("Read relationship evidence", type="button", class_="btn btn-sm workspace-edge",
                    **{"data-edge": key, "data-token": all_payload["_dpv"]["token"]}))
                for key, e in list((k, e) for k, e in edges.items() if e.get({"Outgoing relationships": "subject", "Incoming relationships": "object"}[label]) == iri)[:60])))
        return ui.div(*contents)

    @reactive.effect
    @reactive.event(input.find_path)
    def find_path():
        payload = current_full()
        if not payload:
            context.notice("Load full-scope research tools first.")
            return
        try:
            steps = research_tools.path(payload, input.path_start(), input.path_end(), input.path_kinds(), int(input.path_hops()), input.path_direction())
            path_steps.set({"scope": scope(), "steps": steps, "payload": payload})
        except (ValueError, TypeError) as exc:
            context.notice(str(exc), error=True)

    @render.ui
    def path_result():
        result = path_steps.get()
        if not result or result["scope"] != scope():
            return None
        if result["steps"] is None:
            return ui.p("No path recorded under these direction, relationship and length limits. This does not show that no scientific connection exists.")
        if not result["steps"]:
            return ui.p("Both endpoints are the same concept; no relationship was traversed.")
        edges = result["payload"]["_dpv"]["edges"]
        ids = {s["edge"] for s in result["steps"]}
        nodes = {n for e in result["payload"]["propertyAttribute"] if e["id"] in ids for n in (e["domain"], e["range"])}
        path_payload = research_tools.subset(result["payload"], nodes, ids)
        return ui.div(ui.p("A recorded connection path, not a causal conclusion."),
            viewer(None, session.ns("path_vowl"), payload=path_payload), *(ui.tags.details(
            ui.tags.summary(f"Step {i}: " + ("traversed against arrow · " if step["reverse"] else "") + edges[step["edge"]]["kind"]),
            edge_card(edges[step["edge"]], root()), open=True) for i, step in enumerate(result["steps"], 1)))

    @reactive.extended_task
    async def compare_task(left, right, stamp):
        return {"result": await asyncio.to_thread(research_tools.compare, left, right), "scope": stamp}

    @reactive.effect
    @reactive.event(input.compare_runs)
    def compare_runs():
        chosen = next((p for p in comparison_roots() if str(p) == input.compare_run()), None)
        if chosen is None or root() is None or chosen == root():
            context.notice("Select another available source run.")
            return
        compare_task.invoke(root(), chosen, scope())

    @reactive.effect
    def compared():
        value = compare_task.result()
        if value["scope"] == scope():
            comparison.set(value)

    @render.ui
    def comparison_result():
        value = comparison.get()
        if not value or value["scope"] != scope():
            return None
        row = value["result"]
        return ui.div(ui.p(f"Shared papers: {row['shared_papers']} · current corpus: {row['left_papers']} · comparison corpus: {row['right_papers']}"),
            ui.p(f"Shared papers with recorded, resolvable lineage on both sides: {row['shared_papers_with_lineage']}. Missing lineage does not establish that a concept was absent."),
            ui.p(row["method"]), *(ui.tags.details(ui.tags.summary(f"{label}: {len(row[key])}"), ui.p("; ".join(row[key][:200])))
            for label, key in (("Shared labels", "shared_labels"), ("Current run only", "left_only_labels"), ("Comparison only", "right_only_labels"))))

    for format, mime in (("json", "application/json"), ("csv", "text/csv"), ("bib", "application/x-bibtex")):
        def register(kind, content_type):
            @output(id="graph_" + kind)
            @render.download_button(filename=lambda: "research-view." + kind, media_type=content_type, label="Download " + kind.upper())
            def download():
                payload = graph_payload()
                if payload is None:
                    raise ValueError("Wait for a graph before exporting.")
                papers = {}
                if kind == "bib":
                    for source in research.source_roots(root()):
                        for key, paper in research.index(source).papers.items():
                            papers["zotero:" + key] = paper
                            if paper.get("doi"):
                                papers["https://doi.org/" + paper["doi"]] = paper
                yield research_tools.export(payload, graph_files.get()[0], root().name, kind, papers)
        register(format, mime)

    @render.ui
    def quality_summary():
        reports = [{**row, "domain": presentation.run_label(source)} for source in context.roots() for row in research_tools.saved_checks(source)]
        return ui.div(ui.h4("Ontology checks"), ui.p("Assessments are shown only when saved. Missing reports mean not recorded, not passed. Historical input hashes let you check whether a report applies to the current ontology."),
            *(ui.tags.details(ui.tags.summary(f"{r['domain']} · {r['target']} · {r['check']} · {r['status']}"),
                ui.p("Assessed: " + r["assessed"]), ui.p("Tool: " + str(r["tool_version"])), ui.p("Input SHA256: " + r["input_sha256"]),
                ui.p(r["message"]), ui.p("Report: " + r["report"]), ui.pre(json.dumps(r["results"], ensure_ascii=False, indent=2))) for r in reports),
            ui.p("No saved ontology-check summaries found in this scope. Open All artifacts to inspect available quality files.") if not reports else None,
            ui.h4("Withheld search records"), ui.p("Malformed records below are excluded from search and chat. This is separate from logical consistency, metadata metrics and scientific review."))
