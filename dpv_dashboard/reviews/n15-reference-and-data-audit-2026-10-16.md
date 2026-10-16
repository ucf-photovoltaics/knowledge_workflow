# N15 reference, figure and pipeline audit

Scope: completed sweep family `20261015-150628`, tea/reliability/si-topcon n15 and their integration. Read-only inspection on 2026-10-16. No application, pipeline, dependency, source PDF or run-result changes. Generated analysis lives in `outputs/development/n15-audit-2026-10-16/`.

## Evidence and limits

Inventoried 543 files (144 per domain, 111 integration). Parsed every JSON, JSONL, CSV, Turtle and JSON-LD in these run directories; no parse failures. Examined all 45 paper records and their saved extraction, normalization, placement, enrichment, mapping, review, metric and integration records. Checked all 480 figures with the existing PDF locator. Readability is not semantic correctness. Images/report PDFs were inventoried, not exhaustively visually reviewed; CSV readability does not establish chart arithmetic. Raw model-call JSON was parsed, not independently adjudicated response by response. This is not a full scientific expert review of all 45 source papers.

All 45 paper records report cache hits. Extraction problems are present in this run's inputs but may originate in earlier cached extraction, rather than the October 15 execution. Each domain has 15 distinct saved DOI values and all 45 referenced local PDFs exist. This does not independently establish Zotero selection completeness, current citation ranking, collection membership or absence of cross-domain duplicate papers.

Machine-readable evidence: `audit.json`, `inventory.csv`, `supplement.json`, `figure-coverage.json` in the analysis directory. `audit.py` reproduces the primary structured-file scan. Figure/lineage supplements were generated separately using existing dashboard readers. No saved source was rewritten.

## Stage findings

| Stage | Observed finding | Interpretation and recommended action |
|---|---|---|
| Ingestion | 15 records/domain, PDFs present; all records cached | Show cached extraction origin/date separately from current stage completion. Do not imply the new run regenerated evidence. Fresh citation ranking and subcollection selection require a separate ingestion check. |
| Parsing | All 480 figures have captions and in-range PDF pages; none has a saved bounding box or image field. Three papers have one detected section. | Valid page numbers do not prove correct figure identity. Single-section parsing is a review signal, not an automatic failure. Save caption/layout coordinates and crop provenance in future parsing. |
| Extraction | 57 labels longer than 240 characters: tea25, reliability12, si-topcon20. Maximum lengths 14,316 / 15,272 / 17,513. | Length threshold is a triage heuristic; examples contain concatenated narrative/table text. Quarantine malformed records before normalization and preserve raw output with reasons. |
| Evidence | Of 1,592 extracted relations, 840 unevidenced and97 unverified; 655 quote-verified. Of902 causal claims,207 unevidenced and90 unverified;605 quote-verified. | Missing evidence propagates. Show quote-match status separately from assertion correctness, direction and scope. Unsupported claims should not be promoted silently as established scientific relations. |
| Measurements | 336 of1,058 normalized measurements marked property_missing (tea127/reliability119/si-topcon90). | Property/entity/value/unit roles need validation; retain incomplete records as review items. Do not treat every value as a comparable quantitative observation. |
| Normalization | 3,988 canonical concepts from4,282 occurrences. No recorded concept_lineage.json in any domain. Dashboard reconstructs3,971 unique label+paper links;311 are ambiguous (123/132/56). | Unique reconstruction is a useful navigation aid, not a recorded merge decision. Never select an arbitrary canonical target for the311 ambiguous originals. Preserve original terms as scoped alternative labels only after a supported merge. |
| Placement | 1,124 category-default placements marked unresolved;470 concepts excluded from formal class export. | A fallback parent is not a reviewed scientific classification. Distinguish formal classes3,518 from all canonical concepts3,988. Exclusion does not mean loss from the literature layer. |
| Enrichment | 3,126 records flagged unsupported_definition;702 definition_category_conflict flags. Definition status supported123, draft_evidence244, none3,126, unreviewed25, not recorded470. Restrictions1,820 total. | Flag counts overlap; not all are separate bad concepts. These are sparse or unresolved definitions, not completed authoritative descriptions. Display sources/status beside definitions and separate supported/imported/generated/draft. Restrictions require semantic checking, not just syntactic validation. |
| Interoperability | 646 saved domain mappings;17 equivalent,156 exact,219 close,95 narrower,68 broader,91 related. | Related candidates are not synonym assertions. Inspect local/external definitions and category compatibility before accepting equivalence; distinguish rejected candidates from selected mappings. |
| Export/validation | All three formal ontologies report valid/0issues and roundtrip success. | These checks establish structural conditions, not evidence entailment, sensible units, label quality, correct synonyms or scientific truth. Keep quality review separate from validation success. |
| Integration | 226 candidates reviewed;173 mappings;23 equivalent/54exact/60close/18broader/18narrower;26 bridges. | Generic device/material/property bridges and broad clusters such as converter/inverter need scope review. Same labels need not identify the same scientific concept. Exact control mapping has function vs material-entity categories and confidence1.0: review priority, not automatic proof of error. |
| Reports/progress | Complete structured artifacts coexist with evidence/placement/definition review gaps. Integration top bar shows contributing upstream stages Waiting while integration Completed. | Show contributing-domain completion separately from stages not executed by the integration job. Completion means artifacts saved, not scientific quality approved. Figures/report tables need consistency checks before stronger claims. |

### Concrete assertion-verification defect

`outputs/si-topcon-n15-20261015-150628/papers/2KH8BXKM.json` includes a measurement value `<70%` paired with evidence `implied FF (iFF) of 85%.`, marked verified. Other verified records contain `<150 h (lifetime implied by Jsc loss context)` or `<40 h (lifetime implied by Jsc loss context)` with qualitative evidence that does not give those numeric values. These are recorded extraction mismatches, regardless of whether a value might be supported elsewhere in the PDF.

The causal path is visible in `src/agents/extraction.py`: verification compares quote word trigrams with the source text. It does not check that the quote supports the structured measurement value or causal direction. The mismatched `<70%` record survives in normalized measurements. The UI must say "Quote matched source text" rather than imply the entire assertion was verified. Pipeline follow-up should validate assertion components, units and direction independently and preserve flagged records for review.

### Propagation and normalization examples

All57 oversized labels persist in normalized concepts;48 remain non-excluded enrichment records (tea19/reliability10/si-topcon19). Early malformed-label handling is therefore needed in the pipeline, while bounded display/chat filtering is still necessary for older runs.

Si-topcon canonical `passivated contact` has aliases including `induced emitter` and `n+/n back surface field junctions`, type phenomenon despite device votes2 vs phenomenon1, and placement under BFO function. This is a semantic/type review case, not proven synonymy. Reliability photovoltaic-modules aliases include a figure-caption fragment. Preserve original labels but do not equate every label/figure phrase without a recorded, reviewable decision.

There are830 normalized relation records with empty evidence lists (tea297/reliability363/si-topcon170). Merging reduces total row counts, so do not directly compare these denominators to extraction counts or label deduplication as missing data without tracing the merge.

### Integration retention check

Merged Turtle contains96,821 triples. URI/literal-only source comparison checked tea17,559, reliability31,847, si-topcon17,001 triples. Tea/si-topcon exact matches all present. Five reliability exact comparisons differ only by additional carriage returns in literal values; removing carriage returns makes corresponding text equal. This is a text-serialization fidelity issue, not evidence that integration dropped concepts. Blank-node graph isomorphism was not exhaustively checked. Formal integration unions ontology.ttl graphs; the separate domain_layer claims require their own provenance-aware viewer loading.

## Reference coverage and viewer behavior

Code review covered shared `media.reference`, `media.rich_table`, paper/figure routing, research and stage pages, graph provenance, search and chat. Browser verified the n15 integrated Visual Exploration chat in "Find supporting evidence" mode without invoking an LLM. Inline[S1]–[S6] are plain text. Separate Open cited paper buttons open a source preview; Open paper & figures then opens the correct scoped source paper inspector. This is clickable but requires two actions and the inline citation itself is not actionable.

| Reference surface | Current gap | Target behavior |
|---|---|---|
| Chat inline citations | Plain text inside answer; model output has no validated citation-link rendering | Parse supported source markers safely into buttons bound to the saved response source list; unknown markers explicitly unavailable. Escape generated text; no arbitrary HTML. |
| Chat claim sources | Generic paper opener, incomplete claim context; first result can be a concept summary | Open cited claim, quote, verification and paper/figure context directly; keep source run, paper and original/canonical IDs scoped. |
| Concept/paper tables | Shared rich-table paths cover many cells, not every narrative/plain metadata field | Shared reference renderer for labels, supporting papers, figures and provenance throughout stages, search, integration and inspectors. |
| Ambiguous lineage |311 originals cannot resolve uniquely | Show candidate chooser and reason, never a fabricated unique link. |
| External terms/DOIs | Technical metadata may remain plain text | Human-readable labels with safe external links, separate from local evidence actions. |
| Figure mentions | Some plain-text descriptions and >3-reference gallery shortcuts | Click resolves exact source paper+figure; ambiguous Figure1 references need a paper chooser. |
| Artifact/report content | Preformatted previews are not uniformly link-aware | Link known local references to safe artifact/evidence targets; preserve raw download. Do not turn arbitrary filesystem paths into unrestricted file access. |

This is not a claim that every rendered cell and every possible model answer was browser-tested. Implement a reference coverage matrix and fixtures before asserting dashboard-wide coverage.

## Crop-first design feasibility

Existing locator over all480 records:407 estimated regions,65 caption-only,8 unlocated. By domain: tea178/10/1, reliability157/39/4, si-topcon72/16/3. These are algorithm outputs, not407 visually confirmed correct crops. Sampled9 figure locations across3 PDFs, including raster/vector paths. One si-topcon Figure1 crop was visually checked and retains plot/axes/labels/legend. Geometry evidence: `figure-coverage.json` and `supplement.json`; preview `estimated-figure-crop.png`.

Use saved images or recorded bounds first when available, otherwise PDF raster/vector layout estimates with an "Estimated crop" label. Render the figure crop and caption initially. Expand full-paper view on request at the source page, retaining concept/figure focus. For73 caption-only/unlocated cases, explicitly show crop unavailable plus source-page/full-paper action; never silently call a full-page thumbnail a figure crop. Do not draw invented internal focus boxes in a plot when no region-level evidence exists.

## Proposed implementation plan — awaiting approval

1. Add one shared, safe reference-resolution/rendering path using run+paper+concept+claim+figure identity. Apply across stage results, evidence/provenance, search, graph detail, reports and integration. Handle unresolved/ambiguous references visibly.
2. Render chat source markers as direct evidence actions, retaining exact cited claim context and safe external links. Cover evidence mode and model mode; bound labels and exclude flagged malformed retrieval records.
3. Add bounded PDF crop rendering using existing locator, render crop+caption first in gallery and inspector, and add Expand full paper at source page. Keep source PDFs unchanged and label estimated/unavailable crops.
4. Add honest quality/provenance indicators: quote match vs assertion support, reconstructed lineage, cache origin, review priorities, and contributing-domain progress for integration.
5. Verify scoped joins, malformed/unresolved citations, duplicate figure IDs across papers/domains, missing PDFs, rotated/vector/multipanel crops, crop fallback and safe URLs with fixtures. Browser-check n15 stage/search/chat/integration navigation and crop-to-full-paper transitions. Save a diff. Restart only enhanced dashboard8056 if needed after approval; preserve running pipeline and8055.

Pipeline changes are separate follow-up proposals: malformed-label quarantine before normalization; component-level measurement/causal validation; exact recorded merge lineage and alias decisions; figure coordinates at parse time; category-aware mapping review; text line-ending fidelity. Implement them in isolation for future runs after an approved plan, not by editing the currently running pipeline or rewriting these outputs.
