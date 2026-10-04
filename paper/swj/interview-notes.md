# SWJ paper — interview notes

Working notes for the Semantic Web Journal paper. Overleaf project: 2026-Thompson-SWJ-Knowledge-Workflow. Code: this repository, workflow revision `2026-10-04-coverage-evidence-ro-v1`. Stage details: `docs/stages/`.

---

## Claim and scope

- Goal: draft ontologies per photovoltaic subdomain (techno-economic analysis, reliability/durability, Si-PERC, Si-TOPCon), built independently from each subdomain's literature, then connected.
- The pipeline offloads initial ontology construction so a domain expert starts from a populated, evidence-traceable draft. Not claiming completeness or expert-level ontologies.
- Intended use: a shared triple store the group queries; bridge concepts tell a researcher entering a subdomain which terms mean the same thing.
- Provider-agnostic: develop on local Ollama, re-run the same corpora on a frontier model for final results.

## Architecture the paper describes (sections 03, 04)

1. Extract (per paper): selection by citation count, PyMuPDF parsing, concepts / RO-BFO-CCO relations with explicit is-a / causal claims / measurements (property + entity), quotes ≤20 words, one re-ask for missing quotes, status verified / unverified / unevidenced.
2. Normalize (corpus): lexical groups, embedding clusters reviewed by the model, type conflicts, contradictions flagged, importance.
3. Ontology: BFO/CCO placement, verified paper is-a priority, lexical heads, deterministic repair, domain-scoped hashed IRIs.
4. Enrich: definitions with status (supported / draft evidence / model generated on Gemini only), restrictions from verified RO predicates or the model with domain/range checks, unevidenced relations never axioms, disjointness, mapping candidates.
5. Interop: MDS-Onto and related mappings, MDS facets, OWL + literature layer export, structural validation.
6. Integrate (after all domains): label / synonym / shared-IRI / embedding candidates, model decision, equivalence only for same-label same-category pairs that never join two classes of one domain, SKOS otherwise; master ontology imports domain ontologies unchanged; bridge concepts.

Fixed stage order in Python; each agent has its own prompt and JSON schema. Rows the model skips are retried once and counted per pass.

## Validity and error checking (section 08, "Failure modes found during development")

Found by inspecting run artifacts on earlier revisions; each now has a check:

- Answers wrapped in a copy of the schema were read as empty and counted as successes (12/27 parent calls, 22/22 disjointness, 5/5 restrictions, 22/24 mapping screens in one reliability run). Now unwrapped.
- Partial answers: category for ~74% of concepts, parent for ~48%; 20 of 90 integration pairs answered. 51–77% of classes ended on a BFO category root. Now retried once and reported per pass.
- Leaked model ids as terms: 1.9–3.0% of concepts; 15 of 27 cross-domain candidates. Now blocked, stripped, skipped.
- Type drift: 50–79 type strings, 8–11% untyped. Now mapped to the enum.
- Evidence: 24% empty quotes (20 TEA papers); ligatures and ellipses failed the check (59.0% → 65.1% verified after normalizing). Now re-asked, flagged unevidenced, normalized.
- Values on the wrong concept: 66–77% on devices/materials. Now property + entity.
- Sparse source definitions: 18 of 529 classes. Now status per definition, never pooled.
- Integration picked older runs from different code. Now each input run and revision is listed and mixed revisions are noted.
- Not catchable by any of these: a well-formed wrong answer. That is what CQs, judging and the human calibration subset are for.

## Paper status (2026-10-04)

- Drafted to the current pipeline: abstract, 01, 02, 03, 04, 04b (only place earlier versions appear), 05, 08, 10.
- Skeletons waiting for runs under the current revision: 06 results, 07 discussion, 09 conclusion. No numbers from earlier revisions in Results.
- Compiles clean; abstract ~180 words before the results sentence (limit 200).

## Open decisions (`% DECIDE:` in the .tex)

1. Title and system name: proposed "Knowledge Workflow: Evidence-Traceable Domain Ontologies from Photovoltaics Literature, Built per Subdomain and Connected".
2. Corpus selection: curated 30–50 paper sets vs the code's citation-ranked top 50 of each collection (72–233 items).
3. Sampling: temperature is unpinned for every agent; pin before reported runs?
4. External conformance tools (OOPS!, OWL 2 DL profile) or structural validation only.
5. Judging tasks (currently five) and which model judges.
6. Run variance: measure with the cache bypassed, or state it is unmeasured.
7. Existential restrictions as an open item for expert review.
8. LoRA adapter: in a reported run, or future work.
9. Section 04b: keep, shorten into Implementation, or move to supplementary material.
10. Statements: funding, conflicts (MDS-Onto co-authorship), ORCIDs, data archive.

## Runs to report

- Next: tea, reliability, si-topcon at 5, 10 and 15 papers, each followed by `integrate` (`integration-n5-*`, `-n10-*`, `-n15-*`). Then full corpora, then the frontier-model rerun.
- Report only runs and integrations whose inputs share one revision and profile.

## Questions for the next interview session

- Why the earlier implementation was replaced rather than extended (for 04b, in your words).
- Is the literature layer a contribution you want to claim, or supporting infrastructure?
- What the hybrid local / Gemini split is for: development only, or the reported configuration?
- Which bridge concepts would you expect between each pair of subdomains? (Write down before seeing the integration output.)
- Who authors the competency questions for each subdomain, and when?
