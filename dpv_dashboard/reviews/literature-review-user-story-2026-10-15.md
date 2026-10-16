# Literature-review user story and completed walkthrough

## User story

As a photovoltaics researcher preparing a literature-review section, I want to investigate how TOPCon contacts relate to recombination and efficiency, compare the effects of wafer thickness and resistivity, and retain the supporting passages and figures, so that my review distinguishes study-specific observations, simulation results, proposed potential and unresolved claims.

The desired output is a small, auditable evidence dossier and a review outline, rather than a list of ontology terms.

## Research question and scope

**Question:** What evidence in the selected corpus connects TOPCon/passivated contacts, wafer thickness, resistivity, recombination and efficiency, and under which conditions should those findings be interpreted?

**Starting corpus:** `integration-n5-20261015-150628`, containing three domain runs and 15 distinct known paper DOIs. The TOPCon source run contains five selected papers. This is an exploratory review of a bounded citation-ranked selection, not a systematic review of all relevant literature.

**Primary paper followed:** *n-Type Si solar cells with passivating electron contact: Identifying sources for efficiency limitations by wafer thickness and resistivity variation* (2017), paper key `EL4JUC4H`, [DOI](https://doi.org/10.1016/j.solmat.2017.05.042).

Related titles discovered in the same TOPCon corpus include *Efficient carrier-selective p- and n-contacts for Si solar cells* and *Tunnel oxide passivated contacts as an alternative to partial rear contacts*. Their presence identifies candidates for comparison; it does not mean their full findings were validated in this walkthrough.

## Walkthrough performed in the dashboard

| Step | Researcher's action | Actual result | Ease/clarity and implication |
|---|---|---|---|
| 1 | Select the completed integration run | Run/domain scope and read-only status were visible. | Helpful. A review-specific scope summary should also state selection limits, dates and distinct-study coverage. |
| 2 | Open Visual Exploration and search TOPCon | Enter did not submit. Search returned a table labeled 100 matches. Read-only source evaluation found 878 matching records, 812 matching only through the IRI field. | The user cannot judge retrieval completeness or why broad results are included. |
| 3 | Select TOPCon (Tunnel Oxide Passivated Contact) and View evidence | Correctly reached its source-run concept and five claim records from two papers, with quote statuses and review caveats. | A useful path, but this single canonical concept does not represent the entire five-paper topic. |
| 4 | Inspect Original → canonical | Two links were explicitly marked reconstructed. | Honest provenance. The unchecked technical-columns control still left IDs visible in this lineage view. |
| 5 | Open Contradictions | The table was empty. Saved data contains no contradiction records. | There is no explanation distinguishing no recorded contradictions from agreement or incomplete analysis. |
| 6 | Return to exploration and search wafer thickness | Previous TOPCon query/results survived the first return. The mechanism query required resubmission during a rapid query-change interaction. | State retention helps, but submitted-query/loading feedback is needed. |
| 7 | Select wafer thickness W and focus it in the graph | The supplied neighborhood contained 12 nodes and 20 relationships, including literature claims and ontology restrictions. | Useful topic narrowing. Several other relationship labels remained opaque RO identifiers. |
| 8 | Click the increases → efficiency literature edge | One click opened the saved quantitative quote, its source file and paper reference. | This was the clearest path from a concept to an actual finding. |
| 9 | Try Open paper from that edge | No modal opened on two attempts; a hover page preview was requested. No Shiny output error appeared. | A source-verification action must be reliable. This observation needs a focused interaction regression; its cause was not established here. |
| 10 | Inspect the focused concept's provenance | Canonical k230 was selected but the lineage view said No source mapping available. | Saved inspection found original c4 ambiguously matched to k230/k339. The ambiguity is hidden from the selected concept's page. |
| 11 | Clear the canonical filter and select the full source paper | The researcher could widen to paper-level records. The select menu truncates the long title before the distinguishing thickness/resistivity wording. | A workaround requiring knowledge of how the filters interact; an explicit Show all evidence from this paper action would be clearer. |
| 12 | Open the paper's 11-figure gallery through a lineage row | The correct paper opened. Its initial highlighted concept came from the selected lineage row rather than the original thickness question. | Source identity was retained; investigative focus was lost. |
| 13 | Search figure captions for wafer thickness and inspect Figure 5 | Caption search narrowed the gallery to Figures 5 and 6. Figure 5 opened source page 4, identifying 5 Ω cm n-type FZ Si and distinguishing data from simulation assumptions. The viewer reported caption text match and no separately saved figure image. | Useful study context. The UI should state exactly what was localized or boxed and retain the originating claim beside the figure. |
| 14 | Ask saved-evidence chat about thickness and efficiency | Six references were returned, all from the same paper, mostly concept descriptions. The quantitative claim already found in the graph did not appear. No external model was used. | Reference count is not independent support. Evidence assistance should prioritize source passages and explain record type/verification. |
| 15 | Open Integration and compare the photovoltaic-modules mapping | Reliability's photovoltaic modules and Tea's module opened side by side, with a draft definition in one and no definition in the other. | Helpful navigation, but this is a vocabulary bridge, not independent support for a scientific finding. |
| 16 | Open Reports and look for a way to collect findings and produce the review section | Existing file/report downloads are available, but no question-specific evidence basket, screening notes, comparison matrix or cited review export was found. | The story reaches an in-app assembly boundary. The dossier below was assembled manually for this review. |

The walkthrough was completed through the available routes, including recording where the desired workflow could not be finished in the app. It does not claim that a publication-ready multi-paper review was completed.

## Evidence dossier assembled from the walkthrough

These are candidates for a review, not automatic scientific acceptance. The source identity is the TOPCon run, paper `EL4JUC4H`; record numbers are scoped to this paper and record type.

| Candidate | Saved source record/context | Interpretation for the review | Disposition |
|---|---|---|---|
| Thickness-dependent efficiency in this study | Causal claim 3 quotes 24.9% at 150 µm and 25.3% at 400 µm. Figure 5's caption identifies the thickness comparison as 5 Ω cm n-type FZ Si and describes simulation assumptions. | Report as a study-specific finding with its device/material conditions. Do not generalize it to all TOPCon cells. | Candidate for inclusion after passage-level verification and comparison with other papers. |
| Resistivity and recombination-related FF loss | Causal claim 2 quotes SRH recombination in the c-Si bulk as a source of significant FF reduction for high-resistivity Si. | A mechanism-level explanation requiring its resistivity range, measurement/simulation context and comparison study. | Include as a source-bound interpretation with caveat, pending full contextual review. |
| Efficiency potential above 25.5% | Measurement record 25 states an expected potential conditional on avoiding recombination-active bulk impurities and obtaining high parallel resistance. | Expected potential must remain distinct from an observed efficiency measurement. | Keep in a potential/limitations section; do not count as demonstrated performance. |
| Apparent reversed causal direction | Causal claim 4 displays efficiency decreases resistivity; its quote describes efficiency decreasing with increasing resistivity. | Quote matching has not validated the direction of the represented claim. | Exclude from the working synthesis until reviewed; retain the source and rejection reason. |
| Property/unit mismatch | Unverified measurement records associate a 5 Ω cm value with wafer thickness. | The unit/property association needs correction or reinterpretation from source context. | Hold for review; do not use as a thickness measurement. |

These entries come from **one independent paper**, even though they are several records and figures. Additional papers must be examined before describing agreement, disagreement or domain-wide trends.

## Example provisional review note

Within the inspected 2017 study, the saved thickness-dependent efficiency result is tied to the tested cell structure and material conditions. The retrieved passage reports 24.9% for 150 µm cells and 25.3% for 400 µm cells; Figure 5 identifies a 5 Ω cm n-type FZ Si thickness comparison and separates the data from simulation assumptions. The same paper discusses resistivity-dependent recombination losses and an expected efficiency potential under additional improvements. These are distinct kinds of findings, and the projected potential should not be presented as an observed measurement. This one study does not establish a general thickness recommendation or cross-study consensus.

This note illustrates a properly qualified review paragraph. It still needs full passage verification, comparison with the other selected papers, and appropriate bibliography before publication.

## Proposed review outline

1. Scope, search terms, selection limits and devices/materials included.
2. TOPCon/contact structures and terminology, including unresolved aliases.
3. Experimental evidence for thickness and resistivity effects.
4. Recombination mechanisms, measurements and simulation assumptions.
5. Comparability across studies: substrates, thickness ranges, resistivity, contact architecture, processing and efficiency conditions.
6. Conflicting or unresolved evidence, including extraction and normalization uncertainty.
7. Demonstrated performance versus modeled or anticipated potential.
8. Remaining research gaps and limits of this selected corpus.

## Acceptance criteria for a complete in-app user story

- The researcher can save the question and pin the corpus snapshot, selection rules and inclusion/exclusion criteria.
- A topic search retains Si/PV/FF and other meaningful scientific terms, discloses total and displayed counts, and explains expanded/identifier matches.
- Search facets operate on the complete matching set. Known identical scoped concept/ontology presentations do not consume separate positions without explanation.
- The researcher can collect multiple related concepts into a topic without asserting ontology equivalence.
- A selected claim opens the correct source paper and passage or states why exact localization is unavailable; the claim remains visible next to the PDF/figure.
- Ambiguous original-to-canonical candidates remain inspectable and are not silently promoted to exact provenance.
- Evidence cards separate quote matching, semantic review, measured/simulated/expected status and independent study support. Unknown conditions remain explicit.
- A comparison matrix includes at least three selected independent papers when the corpus supports that selection. Record counts and repeated citations do not inflate study counts.
- An empty disagreement view states its selection scope and detection limits.
- The researcher can retain a rejected or unresolved claim with a reason alongside accepted candidates, without modifying the original pipeline outputs.
- Selected evidence can be arranged into an outline and exported with source passages, page/figure references, citations, review dispositions and run provenance.
- Reopening the review restores its question, selections, notes and navigation context. Optional chat is scoped visibly to the review collection and distinguishes retrieval from synthesis.

## Practical next build

First repair search accuracy/coverage and ambiguous provenance navigation. Next add a persistent review workspace with evidence cards and study comparison. Then provide an outline-based review export and optional collection-scoped synthesis. Re-run this exact story and add observation sessions with representative researchers before calling the workflow easy to use.

Detailed findings: [Researcher workflow review](researcher-workflow-review-2026-10-15.md).
