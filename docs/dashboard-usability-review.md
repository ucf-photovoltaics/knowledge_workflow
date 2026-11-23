# Dashboard usability review and proposed research experience

Reviewed 20 October 2026. This document records the original proposal. The three implementation phases were subsequently approved; the dashboard wrapper now includes the guidance, graph workspace and research tools described in the implementation notes in `dpv_dashboard/README.md`. Detailed recommendations below remain a design reference, not a claim that every future research interaction has been exhaustively tested.

## Review basis

Inspected the authenticated, read-only Cloud Run dashboard in a separate browser tab, including the navigation, Home, Evidence & provenance, All artifacts, nine stage screens, and the loaded default Gemma integrated WebVOWL view. Also inspected the Shiny page modules, context routing, record inspector, and styling. This was a usability review, not exhaustive functional testing of every record or every experiment. Some stage observations were of their initial loading state.

Compared interaction patterns against official documentation:

- [GraphDB visual exploration](https://graphdb.ontotext.com/documentation/11.3/explore-data-and-class-relationships.html): search for a resource, expand/focus its neighborhood, retain a resource inspector, and control graph presentation.
- [Obsidian graph view](https://help.obsidian.md/plugins/graph): global and local graphs, depth controls, filtering, and groups.
- [Obsidian backlinks](https://help.obsidian.md/plugins/backlinks): a persistent list of references with surrounding context.

These are interaction references, not recommendations to adopt their storage systems or assume their data has the same scientific meaning.

## Most consequential observations

1. The information architecture leads with pipeline stages and technical run names. A visiting scientist has to learn the production process before finding a result relevant to a research question.
2. Global experiment/run selectors, page source selectors, ontology selectors, graph focus, and the embedded viewer's own controls create several overlapping kinds of scope. Changes can be difficult to interpret.
3. During initial loading, the graph displayed “No graph available yet” and “Choose an available Turtle ontology.” A cached graph subsequently appeared. Loading and missing data need distinct states.
4. Opening Evidence & provenance at the integrated root displayed “No source mapping available.” Domain sources were selectable, but the screen did not offer a prominent next step. An integrated result should lead naturally into contributing evidence.
5. The loaded default graph reported 160 supplied nodes from 8,175 total, while WebVOWL rendered 52 nodes after its filters. This is disclosed, but beginners must reconcile several counts and filter systems.
6. In the observed viewport, headers, selectors, descriptions, legends, and coverage explanations occupied substantial space above the graph. The graph's useful working area starts too far down the page.
7. There are already valuable building blocks: per-stage purpose statements, compact technical columns, record inspectors, source links, evidence tracing, search, bounded graph views, and quality exclusions. The next iteration should connect these into coherent research tasks.

## Shared page design

Each page should answer four questions near its title:

- What happened here? One sentence explaining the transformation.
- Why is this useful? The scientific or review task enabled by these outputs.
- What am I looking at? Explicit experiment, model, domain/integration, and data coverage.
- What should I do next? One primary action, with alternatives available but secondary.

For pipeline pages, use a compact Input → Process → Output strip with an actual recorded example when available. Explain terms such as canonical concept, restriction, mapping, and integration in context. Keep raw identifiers available through technical details and copy actions.

Use separate states for loading, no results under current filters, output not recorded, unavailable source, and preparation failure. Each should offer an appropriate next action. Keep the previous valid view visible while a new selection loads, with a clear pending label; never label the previous view as the newly selected run.

Replace prominent raw folder names with readable labels, for example “PV cost chain · 10 papers per domain · Gemma 4 31B + ThinkOnto · Integrated.” Keep the exact folder identifier in Run details. Bucket experiment structure remains the source of grouping.

Group navigation around reader tasks: Explore research, Inspect evidence, Understand the workflow, and Download results. The nine stages remain available under an expandable workflow group. Visual Exploration can remain the landing page, and Quality review remains its last tab. Preserve a visible active state and keyboard navigation.

## Visual Exploration proposal

### Workspace

Use a compact scope/search header above a large graph. Provide a collapsible left panel for search results and filters, a central graph, and a persistent right inspector. Avoid a third permanent navigation column competing for graph width. Put technical coverage and diagnostics in a compact disclosure beneath the working area.

The graph must be usable at a normal laptop viewport without scrolling through several paragraphs first. Provide fit-to-view, reset, freeze layout, zoom, hide selection, and undo controls. Preserve positions of existing nodes during expansion. A table/list alternative should expose the same relationships for accessibility and precise review.

### Research tasks and entry points

Keep the requested Gemma overview at startup, but offer useful actions alongside it:

- Explore a concept: search a label or synonym and center a local neighborhood.
- Follow the literature: show claims and their supporting papers for that concept.
- Connect domains: inspect recorded links between reliability, device concepts, and economics.
- Inspect the ontology: examine hierarchy, restrictions, and external mappings.

Suggested questions must be grounded in available concepts, not imply that an unrecorded answer exists. A possible interaction example is searching “degradation rate” and following recorded links toward reliability or cost concepts; display an explicit absence when no such path is recorded.

### Distinguish what each graph means

Offer clearly named presets instead of requiring beginners to configure OWL-oriented checkboxes:

- Research findings: recorded literature claims with evidence inspection.
- Ontology structure: classes, hierarchy, restrictions, and mapping types.
- Cross-domain connections: recorded integration mappings and bridge members with both domain contexts.

Explain that ontology restrictions describe modeled constraints, while literature claims report findings under particular conditions. Keep these provenance types distinct if combined. Preserve the formal predicate and IRI behind a readable label. Do not make an unsupported restriction look like an experimentally established causal result.

WebVOWL can remain the ontology view. A research-oriented interaction layer or renderer should be assessed separately if its internal filtering and schema-oriented presentation prevent the desired workflow. Do not replace it before testing a small, representative interaction prototype.

### Local exploration

From any selected node, provide visible actions: Expand neighbors, Focus here, Show papers, Pin, Hide, and Copy IRI. Offer one-hop/two-hop depth and relation/domain filters. Show the number of hidden neighbors before expansion, and cap expansion in a stated, deterministic way. Centrality or link count must not be described as scientific importance.

Keep the existing double-click action that opens an evidence trace. Add a visible equivalent button so users can discover the action and operate it by keyboard or touch. A single click can populate the persistent inspector without leaving the graph.

### Concept inspector

Show the label, recorded definition and its source, synonyms, domain membership, and record type. Provide grouped Incoming relationships and Outgoing relationships, followed by Supporting papers, Related figures, Normalization history, Ontology placement, and Review findings. Distinguish direct recorded links from label-based reconstructed associations.

The backlinks pattern becomes a scientific “Where is this concept used?” panel: statements, papers, definitions, mappings, and figures connected to the current concept, each with enough context to judge relevance.

### Relationship inspector

Selecting an edge should immediately show a readable subject–relationship–object statement, relationship origin, source paper, complete recorded quote, conditions, and verification/review status. For a restriction without a recorded paper quote, say so and show the ontology source. For mappings, compare the two definitions side by side and display whether the mapping denotes equivalence, broader/narrower meaning, or another relation.

Where aggregation is supported, show distinct source papers, not simply extracted claim counts. Deduplicate the same paper across models and runs. Citation counts and model agreement are not evidence of scientific correctness. Use “Quote located in parsed text” for textual verification; reserve scientific acceptance for an actual recorded review decision. No recorded contradiction does not establish consensus.

### Reading the graph

Use a concise legend with domain color and a separate visual encoding for relationship origin, supported by text for accessibility. Keep labels readable and reveal long labels on selection/hover. De-emphasize generic hubs where useful, with a visible way to restore them.

Unify scope and rendering controls. Explain counts as: visible now, hidden by filters, loaded neighborhood, and complete selected scope. Provide one clear reset-filters action. Search must cover the full authorized scope even if most nodes are not currently rendered.

### Research queries and paths

Later, add a guided “How is A connected to B?” control with allowed relationship types and maximum path length. Return the path as a graph and readable steps, with evidence available for each edge. Structural paths, mapping chains, and causal claims must remain distinguishable. A path through the graph is not automatically a causal explanation.

Useful saved queries include supporting papers for a concept, links crossing domains, statements requiring review, and differences between two explicitly selected runs. Model comparisons must state shared-paper coverage and separate vocabulary changes from semantic agreement.

### Continuity and reuse

Add exploration Back/Forward, breadcrumbs, and reset-to-start. Returning from a paper trace should restore focus, filters, zoom, and expanded nodes. Later, allow named views and export of selected relationships, citations, and figures. Shared views must recheck access on opening and retain the run/bundle version. Exported figures should identify whether they show a filtered subset and include source/provenance information.

## Page-by-page recommendations

| Page | Research question it should answer | Proposed improvement |
|---|---|---|
| Home | What can I learn from this collection? | Give three actionable starting routes: explore a concept, read a finding's evidence, and inspect quality. Summarize selected corpus, domains, model, and coverage. Avoid setup-oriented text for read-only visitors. |
| Evidence & provenance | Why does this result exist? | Start from a selected finding and show quote → extracted record → canonical concept → ontology result. Use a persistent paper/evidence reader. For integrated results, expose contributing domains directly rather than a dead-end empty message. |
| All artifacts | Which output should I download for my task? | Add recommended downloads with plain-language descriptions: ontology, literature evidence, report, quality results. Keep the full technical inventory below. State format, scope, size, and intended use. |
| 1. Zotero ingestion | Which papers informed this result, and why these papers? | Explain inclusion/ranking rules, per-domain limits, duplicates, PDF availability, and exclusions. Link corpus choices to potential coverage gaps. Read-only wording should describe the saved selection. |
| 2. Parsing & chunking | Was the relevant source material read? | Show coverage by paper, section, table, and figure where recorded. Offer a source excerpt beside its parsed representation. Distinguish unread content from content that yielded no claim. |
| 3. Evidence extraction | What statements and measurements were extracted? | Show claim-first cards/table rows with subject, relation, object, conditions, quote, and paper. Add useful relation/material/outcome filters and explain quote verification. |
| 4. Corpus normalization | Which terms were merged, and was meaning preserved? | Show original terms → chosen term with paper context and recorded rationale. Explain canonical as “the shared name used in this run.” Make ambiguous merges and conflicting meanings easy to inspect. |
| 5. Ontology placement | Why is this concept in this category? | Provide a compact parent tree, definition comparison, recorded placement rationale, and source evidence. Separate classification rationale from scientific claims. |
| 6. Enrichment | What definitions or connections were added, and from where? | Show the additions to the existing concept, distinguish imported versus generated definitions, and expose source attribution and review flags beside the added material. |
| 7. Interoperability & export | Can this term be reused with external vocabularies? | Compare local and external meanings side by side. Explain mapping type and its implications. Offer downloads with short reuse instructions. Similar labels alone should not appear as confirmed equivalence. |
| 8. Cross-domain integration | What connects these domains, and what supports the connection? | Lead with concrete connection cards and a small graph. Put both concepts, definitions, mapping/bridge rationale, and domain evidence together. Group the large Explore menu into connections, source evidence, and review. |
| 9. Reports & figures | What are the results, limitations, and reusable outputs? | Lead with an abstract, corpus/methods description, coverage and quality summary, then annotated figures. Explain units, denominators, and what each plot supports. Offer citations and reproducible export details. |
| Chat | What can the saved evidence answer? | Separate evidence search from optional AI synthesis before requesting a key. Show answer scope, example questions, cited supporting passages, and links back to graph concepts. State when no supporting evidence was retrieved. |
| Quality review, last exploration tab | What has been checked, what failed, and what remains unknown? | Distinguish withheld malformed records from ontology quality checks. Group logical consistency, structural checks, metadata metrics, provenance gaps, and scientific review. Show individual/integrated target, input version, tool/version/time, denominators, and passed/failed/error/not-run status where recorded. Provide affected concepts and recommended review actions. Avoid a single unexplained quality score. |
| Documentation | How do I use and interpret the dashboard? | Separate a short researcher's guide, worked example, glossary, methods, and technical file reference. Add page-specific help links that open the relevant explanation. |

For stages belonging to contributing domains, keep the integrated context visible and offer explicit domain buttons or a domain selector. Do not force readers to discover that they must change a global run to inspect upstream data.

## Proposed implementation sequence

1. Clarity and navigation: readable run labels, consistent scope, distinct loading/empty/error states, page Input → Process → Output strips, relevant next actions, and useful integration/domain handoffs.
2. Graph usability: larger canvas, compact controls, presets, persistent concept/edge inspector, visible evidence action, unified filtering, local expansion, and exploration history. Reuse current caches and evidence joins where possible.
3. Research tools: typed path exploration, backlinks across evidence types, matched-run comparisons, saved views, and reproducible citation/figure exports. Assess new traversal/index needs before implementation.

Suggested acceptance tasks for a beginner:

- From the default view, locate a concept, read what one relationship means, and open its recorded quote and paper without losing graph position.
- Explain the difference between a literature claim and an ontology restriction after reading the page's own help.
- Inspect both sides of a cross-domain mapping and see which source records support it.
- Identify an unavailable source, an unexecuted check, and a failed check without confusing them with zero results.
- Download an ontology and its evidence with enough scope/version information to cite and reproduce the view.

Measure task completion, wrong-scope errors, backtracking, evidence-opening time, and user explanation accuracy. Do not judge success only by visual appearance or number of features.
