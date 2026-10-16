# Researcher workflow review

Date: 15 October 2026. Application: UCF DPV Knowledge Workflow, local dashboard on port 8056.

## Main finding

The dashboard provides useful inspection tools, particularly the focused scientific graph, saved quotes, source figures and visible lineage caveats. A researcher still has to assemble the literature review outside the application. Topic discovery, evidence assessment, cross-paper comparison and review writing lack a shared, persistent research context.

The next improvements should follow the researcher's question through the application. Adding more artifact tables would have less value than fixing search coverage, repairing evidence-navigation dead ends, and providing a place to collect and compare selected findings.

## Method and limits

This was a read-only, single-operator cognitive walkthrough using an actual saved corpus, followed by source inspection to explain observed behavior. It was not a usability study with recruited researchers. Ease and clarity judgments below are heuristic assessments; no user success rates or measured task-completion times are claimed.

The walkthrough deliberately used `integration-n5-20261015-150628`, a reproducible completed integration containing three domain runs: Tea, Reliability and Si-TOPCon. These contain 15 paper records with 15 distinct known DOIs; the TOPCon source contains five papers. This is a selected corpus, not a complete search of the literature. A five-paper, citation-ranked sample can support orientation and exploratory synthesis but cannot establish comprehensive systematic-review coverage.

I used topic search, result inspection, evidence/provenance navigation, lineage, contradictions, graph focus, graph-edge evidence, source-paper access, caption search, figure inspection and the local saved-evidence chat mode. I inspected saved outputs to distinguish missing data from missing presentation. No external model, Zotero discovery, pipeline execution, dependency changes or dashboard restarts were performed during this review. No application code or existing run outputs were changed.

Companion walkthrough: [Literature-review user story](literature-review-user-story-2026-10-15.md).

## Anticipated researcher workflows

| Researcher's goal | Questions the interface should answer | Needed working output |
|---|---|---|
| Orient to a domain | What is covered, by which papers and dates? What was excluded? | Corpus scope and coverage summary |
| Learn the vocabulary | Which terms describe the same topic, and which remain distinct? | A selected topic family with visible synonym/lineage uncertainty |
| Investigate a mechanism | What affects this outcome, under what conditions? | Named relationships, study conditions and source passages |
| Evaluate a finding | Does the passage actually support this claim? Is this measured, simulated or anticipated? | A claim-level assessment with source page and figure |
| Compare studies | Do the studies examine comparable devices, methods and conditions? | A comparison matrix based on distinct papers |
| Investigate disagreements | Is this a genuine conflict, a condition difference, or an extraction error? | Explainable disagreements and unresolved cases |
| Connect domains | Why is a bridge relevant to my question? | Mapping rationale and contextual evidence from both domains |
| Write a review | Which findings support each section, and what remains uncertain? | A saved evidence collection, outline and cited export |
| Return later | What did I search, select, reject and conclude? | A persistent review workspace tied to a corpus snapshot |

These workflows share concepts and sources, but their tasks differ from running the nine pipeline stages. The stages remain valuable for examining how the results were produced.

## Ease and clarity assessment

| Task | Ease | Clarity | Observed reason |
|---|---|---|---|
| Establish the selected corpus | Moderate | Moderate | Run labels and read-only context help; selection limits, topic coverage and completeness require further investigation. |
| Find a topic | Difficult to assess exhaustively | Low | Search caps results without showing the full count; IRI namespace matches and duplicate representations inflate the result set. |
| Follow a selected result to evidence | Mixed | Mixed | TOPCon evidence navigation worked. Wafer-thickness provenance reached a page with no mappings despite an unresolved original-concept candidate and available paper claims. |
| Explore a focused graph | Good after selecting a concept | Moderate | A 12-node supplied neighborhood exposed relevant claims; some relations still displayed opaque RO identifiers. |
| Inspect a claim's source | Mixed | Moderate | Saved quotes and source names help. The direct graph paper action did not open a dialog on two attempts in this session; the gallery route worked. The cause of that interaction failure was not established. |
| Inspect source figures | Good through the gallery | Moderate | Caption search found the relevant figure. Full source pages and crop/box limitations remain important to interpret. |
| Compare independent studies | Difficult | Low | Tables provide records but no study-level evidence matrix or independent-support summary for a topic. |
| Compare meanings across domains | Good for opening both records | Moderate | Photovoltaic modules opened Reliability and Tea side by side, but one definition was a draft and the other absent. Shared mapping did not establish a shared empirical finding. |
| Interpret an empty disagreement view | Difficult | Low | The Contradictions tab was blank, without a scoped explanation or a statement of what had been checked. |
| Assemble and retain a review | Unavailable as a dedicated workflow | Low | No evidence basket, inclusion/exclusion decisions, section outline or persistent review notes were found in UI/source inspection. |
| Export the chosen review evidence | Requires manual assembly | Moderate | Existing artifact/report downloads preserve results but do not create a question-specific evidence dossier. |

Positive observations should be retained: top-stage navigation is direct; the original topic query survived a return from provenance within the same scope; compact tables preserve identifiers in technical details; reconstructed lineage is explicitly labeled; scientific graph edges can expose their actual saved quotes; figure galleries have useful caption search; original outputs remain accessible.

## Reproducible findings

### F1. Search does not reveal its actual coverage

In this corpus, read-only evaluation of the same search implementation found:

| Query | Matching records before the cap | Returned to the dashboard |
|---|---:|---:|
| TOPCon | 878 | 100 |
| recombination | 105 | 100 |
| wafer thickness | 189 | 100 |

The browser displayed `100 matches`, rather than `Showing 100 of 878 matching records`. The returned subset is subsequently filtered by the table, so a table filter cannot recover matching claims that were already omitted by the retrieval cap.

For TOPCon, 812 of the 878 matches matched only the IRI field, not the record's label or indexed text. The `si-topcon` namespace caused broad domain membership to behave like a topical text match. These records may belong to a relevant domain, but the matching reason is not disclosed.

The first 100 TOPCon records contained 71 concepts, 17 ontology terms, one paper, eight relations and three causal claims. Seventeen IRI-bearing entries duplicated an IRI already represented in that subset. These are duplicate search presentations, not evidence that the original ontology should be merged or deduplicated.

**Change:** expose total/displayed/unique-paper counts, provide result-type and domain facets before pagination, combine equivalent presentations only when their scoped identity is known, and make identifier matching explicit. Show why each result matched.

### F2. Search drops important scientific terms and uses broad matching

`Si recombination` produced the same ordered results as `recombination`. In a multiword query the implementation discards tokens of two characters or fewer, affecting common scientific terms such as Si, PV and FF. The search scores any matching query tokens; it does not implement an all-terms constraint or quoted phrase behavior.

Pressing Enter after typing TOPCon did not launch search; the Search button did. During a rapid query replacement and button submission, the text box showed `wafer thickness` while the old TOPCon results remained until another submission. This rapid interaction is a reproducible observation, not a measured human error rate.

**Change:** support Enter, clearly distinguish the submitted query from unsent text, show a loading state, retain meaningful scientific symbols/abbreviations, and offer explicit all-terms/phrase behavior. Introduce domain-specific aliases only with visible provenance and an expansion control.

### F3. An ambiguity becomes an evidence dead end

The graph showed `wafer thickness W → increases → efficiency` with a saved quote and source paper. Following the focused concept to provenance selected canonical `k230`, but the page said `No source mapping available` and showed an empty lineage table.

Saved source inspection explains the gap: original concept `EL4JUC4H/c4`, labeled `wafer thickness W`, has two candidate canonical matches, `k230` and `k339`. The older run records no exact normalization map. The dashboard correctly avoids inventing a unique merge, but it does not expose this ambiguity from the selected canonical result.

**Change:** distinguish exact, reconstructed, ambiguous and unavailable paths. Show unresolved candidate original records in a separate section with candidate concepts, source-paper access and an explicit non-authoritative status. Do not relabel candidate evidence as a confirmed lineage join.

### F4. Text matching is insufficient for scientific acceptance

The TOPCon concept evidence table included unsupported relationships and text-matched relationships whose quote required interpretation. In the wafer-thickness source, causal claim 4 displays `efficiency → decreases → resistivity`, while the saved passage describes efficiency decreasing as resistivity increases. That direction appears inconsistent with the source and needs semantic review, even though its quote matched.

Other source records assign `5 Ω cm` as a value for wafer thickness. They are unverified and should invite a unit/property check rather than be treated as a thickness measurement.

**Change:** distinguish quote found, interpretation assessed, and study independence. Provide a dashboard-side disposition such as candidate, usable with caveat, needs semantic review, or rejected, with a reason. Preserve the generated record. Add visible checks for missing conditions, units and apparent direction mismatches. Pipeline-level semantic checks would require a separate, approved change after protecting active runs.

### F5. Conditions appear only after additional navigation

The graph's thickness/efficiency claim contained a matched passage reporting 24.9% at 150 µm and 25.3% at 400 µm, but no condition text in its displayed claim panel. The paper's Figure 5 caption identifies the thickness comparison as 5 Ω cm n-type FZ Si and distinguishes experimental data from simulation assumptions. Figure 8 explicitly discusses simulated efficiency.

**Change:** display claim, quote, study conditions, measured/simulated/expected status and relevant figure together. Where these fields have not been recorded, say so and show linked source context; do not infer them silently from nearby records.

### F6. Source opening and highlighting do not consistently preserve the selected claim

The focused graph edge opened the correct evidence panel in one click. Its Open paper action did not open a modal on two attempts during this walkthrough; a hover page preview was requested. No Shiny output error appeared, and the interaction's root cause was not established. A direct figure-gallery button on the paper's lineage records did open the inspector.

The graph paper reference carries the paper identity but not the specific claim or its quote. The workaround through the first available lineage row opened the right paper with focus on a different concept (`p-type/n-type Si solar cells`). This is valid context for that row but loses the original investigative focus.

Figure 5 opened its correct source page and reported `caption text match`; it had no separately saved figure image. A researcher needs an explanation that this locates a caption, rather than a guarantee that the entire plot has been boxed.

**Change:** provide distinct reliable actions for preview, open source passage, and inspect figure. Pass scoped claim/quote/page identity through every link. Keep the selected topic and claim visible inside the viewer. Make recorded versus estimated figure bounds and caption-only matches explicit.

### F7. Empty contradictions and opaque relations weaken interpretation

The TOPCon run has zero saved contradiction records. The Contradictions tab showed an empty table without explanatory text. This cannot establish that the studies agree. Some graph edges also displayed labels such as `RO 0019000`, which are not useful research language without a definition.

**Change:** say `No contradictions are recorded for this selection; this does not establish agreement`. Disclose the scope and limitations of contradiction detection. Resolve relationship labels from available property records, retain their IRIs in details, and explicitly label unresolved names.

### F8. Local evidence chat does not yet perform a useful review synthesis

In saved-evidence mode, I asked: `What does the saved evidence say about wafer thickness and efficiency?`

The answer's six references all pointed to the same paper. Most were concept descriptions, and the substantive thickness/efficiency claim already found through the graph did not appear. An unverified extracted relation appeared with an opaque figure-method identifier. Six references therefore did not represent six independent studies or a balanced review of the question.

**Change:** rank actual supporting passages separately from concept records, show verification and source type, group by distinct study and distinguish direct evidence from contextual records. Make scope explicit: current question, selected topic, selected papers or full corpus. AI synthesis should be optional and should expose each statement's supporting sources; the external-model mode was not exercised in this review.

### F9. No review assembly workflow is available

The researcher can inspect and download artifacts but cannot collect a selected claim, preserve a rejection rationale, organize findings into review sections, or export just that selected evidence with citations and run provenance. Source and record navigation do not provide a persistent back trail for the investigation.

**Change:** add a review workspace stored separately from pipeline outputs. It should retain the research question, corpus snapshot, selected concepts and papers, screening decisions, evidence cards, caveats and outline. Export the selected collection as an evidence table and cited draft notes, with bibliography and source provenance.

### F10. Cross-domain comparison opens records but needs interpretive guardrails

Selecting the photovoltaic-modules mapping opened Reliability's `photovoltaic modules` and Tea's `module` side by side. This is a useful existing comparison. Reliability showed an AI-generated draft definition and several source quotes; Tea had no recorded definition. The panels still exposed a raw model identifier and parent IRI. The Reliability panel also said no review flags were recorded while identifying its definition as a draft.

**Change:** lead with the mapping's meaning, direction, method and review status; separate the status of the mapping from that of each definition and supporting claim. A shared class or external parent is a navigation bridge, not evidence of a cross-domain causal finding. Keep both source meanings visible and explain missing definitions before suggesting equivalence or consensus.

## Walkthrough evidence

- [Figure 5 inspection screenshot](/C:/Users/brent/dev/knowledge_workflow/outputs/dashboard/researcher-story-figure5.png) records the caption, source identity and caption-localization status.
- Saved artifacts inspected include `papers/EL4JUC4H.json`, `normalized/concepts.json`, the source ontology/literature layers, and integration mappings. The source claim direction and ambiguous k230/k339 case can be reproduced from these outputs.
- The search totals were computed by invoking the existing read-only search on the same indexed documents with a larger result limit, then comparing it with the default limit of 100. No search algorithm changes were made.

## Prioritized improvements

| Priority | Improvement | Researcher acceptance check |
|---|---|---|
| P0 | Search coverage and scientific query handling | TOPCon shows returned/total counts and match reasons; Si is preserved; facets operate on all matches; Enter submits; old results cannot masquerade as a new query. |
| P0 | Resolve evidence-navigation dead ends transparently | The k230 example exposes its two candidate mappings and gives access to the original paper/claim without asserting a merge. |
| P0 | Reliable claim-to-source navigation | Opening the selected thickness claim reaches its relevant source passage or explicitly reports that localization is unavailable; preview hover cannot block the action. |
| P1 | Evidence cards with conditions and assessment | The thickness finding and Figure 5 can be inspected together; expected >25.5% efficiency potential cannot be mistaken for an observed result; the apparent reversed causal record can be marked for review. |
| P1 | Persistent review workspace | Selected findings, caveats and screening reasons survive navigation and reopening; run outputs remain unchanged. |
| P1 | Study comparison and independent support | One paper contributing six records counts as one study; measured/simulated status, conditions, methods and units are visible side by side, with unknown fields explicit. |
| P1 | Review-specific export | Export includes only selected evidence, human-readable claims, citations, page/figure references, decisions and corpus/run provenance. |
| P2 | Topic families and meaningful cross-domain context | A researcher can include several related TOPCon concepts in a question without asserting ontology equivalence; bridge comparisons expose the actual mapping rationale and scope. |
| P2 | Consistent labels, empty states and navigation history | Technical columns obey the visibility control in lineage views; unresolved property names are explained; empty results distinguish no records, unresolved links, filters and unavailable data. |

## Recommended implementation sequence

1. **Make discovery and evidence tracing dependable.** Fix retrieval semantics and counts, expose ambiguous candidates, and preserve claim identity through source links. Verify with the actual TOPCon and wafer-thickness cases plus fixtures for repeated IDs and ambiguous aliases.
2. **Build the review workspace.** Add a persistent research question and selected topic set, an evidence basket with dispositions, a source-aware return trail, and a distinct-study comparison matrix. Store human review notes in dashboard-owned sidecars rather than modifying generated paper or ontology artifacts.
3. **Support review writing and export.** Organize evidence cards into outline sections and export a review dossier, citation data and limitations. Scope optional chat to the selected dossier and clearly distinguish retrieval from synthesis.

Do not replace the existing stage pages. Keep them as the detailed production/provenance views, while offering a question-driven route through them.

## Completion criterion for the next iteration

A researcher should be able to reopen a saved research question, discover relevant studies with visible coverage limits, collect a supported finding and an unresolved counterexample, inspect their source passages and figures, compare conditions across distinct papers, and export a cited evidence dossier with caveats. The scoped unresolved-lineage example must remain navigable without inventing provenance.

The next verification should repeat this story with representative researchers and record task success, wrong-scope mistakes, recovery from ambiguous provenance and time spent assembling evidence. This review supplies hypotheses and concrete regression cases, not those future usability results.
