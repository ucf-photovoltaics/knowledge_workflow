# SWJ paper — interview notes

Working notes for the Semantic Web Journal paper. Overleaf project: 2026-Thompson-SWJ-Knowledge-Workflow (the .tex sections live there, not in this repository). Code: this repository, current pipeline (2026-10-15). Stage details: `docs/stages/`.

---

## Claim and scope

- Goal: draft ontologies per photovoltaic subdomain (techno-economic analysis, reliability/durability, Si-PERC, Si-TOPCon), built independently from each subdomain's literature, then connected.
- The pipeline offloads initial ontology construction so a domain expert starts from a populated, evidence-traceable draft. Not claiming completeness or expert-level ontologies.
- Intended use: a shared triple store the group queries; bridge concepts tell a researcher entering a subdomain which terms mean the same thing.
- Provider-agnostic: any tool-using model behind an OpenAI-compatible endpoint. Development and the first results use a small local model; the same corpora and code are then rerun on larger open-weight models on HPC to validate and compare the local results (see "Models and compute").

## Architecture the paper describes (sections 03, 04)

Local tier (the configuration used for every run so far): each stage is split into narrow single-task calls, each with its own prompt and JSON schema, in a fixed Python order.

1. Extract (per paper): selection by citation count (OpenCitations, then OpenAlex, then Crossref), PyMuPDF parsing with short sections packed, four passes (concepts, causal claims, relations, measurements as property + entity), quotes ≤20 words checked against the text (verified / unverified / unevidenced), one re-ask for missing quotes. Cached per paper.
2. Normalize (corpus): lexical groups (same wording and plurals), embedding clusters (nomic-embed-text, cosine ≥0.85) settled by the model, type conflicts settled among the types the papers used, contradictions flagged, importance (PageRank tiers), causal order.
3. Ontology: same-name MDS-Onto / PMDCO classes used as parents; BFO category taken from the extraction type, the model only marks "not a class" (since 2026-10-14; the model's own category choices were worse about half the time); parent chosen from the concept's ontology-store candidates (CCO, then BFO) inside that category or from corpus concepts; lexical heads; deterministic cycle and exclusion repair; domain-scoped hashed IRIs.
4. Enrich: mapping candidates from a local ontology store (Oxigraph + trigram + embedding search over BFO, CCO, RO, QUDT, PMDCO, IOF, MDS-Onto) plus MDS-Onto portal and MatPortal searches, with 1–2 hop propagation through existing mappings; Materials Project properties as annotations on material classes; causal edges become restrictions deterministically (local polarity, RO and CCO property); other relations get store properties by exact name or tie-break, the rest chosen by the model with domain/range checks; unevidenced relations never become axioms. Definitions (status supported / draft evidence / none; model knowledge only on profiles that allow it, never on the local or HPC runs), synonyms, disjointness among siblings (same parent) only: each class is shown the next 12 siblings by label, so every pair is asked once; a pair the papers call is-a is dropped.
5. Interop: candidate screening, then mapping relation; exact/equivalent kept only when labels match (otherwise downgraded to close); definitions imported from exact matches for classes without a supported one; MDS-Onto study stage and domain/subdomain in one call; OWL 2 + literature layer (JSON-LD, Turtle); structural validation.
6. Integrate (after all domains of a size): label / synonym / shared-IRI / embedding candidates, model decision, equivalence only for same-label same-category pairs that never join two classes of one domain, SKOS otherwise; master ontology imports domain ontologies unchanged; bridge concepts.

Cross-cutting mechanics:
- Row coverage: rows a model answer leaves out are re-sent in smaller batches (half, then a quarter) and counted per pass; rows still missing fall back to defaults and are listed for review.
- Batch sizes (local): category 25, parent 8, definitions 8, synonyms 10, restrictions 8, disjointness 8, screening 8, stage + domain 8.
- Answers reused across corpus sizes: a row whose content is identical to one answered before (same revision, model, prompt, evidence, support counts, parent, siblings, candidates) takes the earlier answer, so tea-n10 asks the model only about what changed since tea-n5. Any change to what the model sees means a fresh answer. Every run lists each answer and whether it was reused (`rows.jsonl`). Parent placement never reuses (its prompt lists the corpus concepts, which change with every size).
- Concurrency: requests run in parallel up to a worker limit; an overload halves the limit for the rest of the run.

## Models and compute

- Development and first results: `kw-qwen3.5-9b-32k` (Qwen 3.5 9B, 32k context, thinking off, output capped at 8k tokens) on Ollama, on a laptop GPU, two requests at a time. Embeddings: `nomic-embed-text` on Ollama. Temperature: provider default (not pinned).
- Validation / comparison: the same corpora, code and revision on the university HPC through Slurm (`scripts/slurm-sweep.sh`), with vLLM serving Mistral Small 4 (119B) and gpt-oss-120b; Ollama on CPU keeps the same embedding model and cache. The script sizes itself to whatever GPUs the job gets (as many model copies as fit, workers scaled to them, the domains of a size side by side).
- The local sweep is the baseline the HPC runs are compared against, so it has to be rerun on the same revision as the HPC runs.
- Local cost, revision 2026-10-14 (2 workers): about 1,600–1,900 tokens per final class at every size; wall time per domain run 14–32 min at n5, 37–74 min at n10, 76–108 min at n20.

## Results so far (local model only; nothing from HPC yet)

Sweep `20261014-154503`, revision `2026-10-14-category-from-type`. Cumulative sizes: each size adds the next five most-cited papers. Not the final revision; listed to see what the numbers look like before the final sweep.

| run | final classes | at category root | no definition | external mapping | disjoint axioms | valid |
|---|---|---|---|---|---|---|
| tea n5 / n10 / n20 / n25 | 217 / 661 / 1,234 / 1,567 | 40 / 39 / 36 / 33 % | 88 / 89 / 85 / 84 % | 15 / 15 / 13 / 11 % | 1,019 / 2,323 / 4,216 / 8,104 | yes |
| reliability n5 / n10 / n20 | 573 / 1,271 / 1,865 | 24 / 31 / 33 % | 83 / 83 / 83 % | 12 / 16 / 14 % | 2,213 / 3,847 / 7,869 | yes |
| si-topcon n5 / n10 / n15 / n20 | 458 / 716 / 911 / 1,286 | 27 / 29 / 30 / 28 % | 86 / 87 / 87 / 84 % | 14 / 13 / 17 / 16 % | 1,266 / 2,484 / 2,273 / 4,036 | yes |

- Every completed domain run and integration passed structural validation with 0 issues.
- Evidence verified (quote found in the paper): relations 40–47 %, causal claims 62–73 %, measurements 67–75 %.
- Definitions: 1–5 % supported by a paper definition, 5–8 % drafted from evidence, 1–4 % imported from an exact match; the rest have none (the local and HPC runs may not write definitions from model knowledge).
- Classes left on their BFO category root dropped from 51–77 % (earlier revisions) to 24–40 %.
- Concepts in two or more papers: 0.3–6 % of canonical concepts; the corpora overlap little within a domain at these sizes.
- reliability-n15 failed: the model returned invalid JSON twice for one synonym-cluster batch in normalization, which has no soft fallback. integration-n15 therefore has two domains.

| integration | domains | candidates | mappings | bridge concepts (3 domains) |
|---|---|---|---|---|
| n5 | 3 | 31 | 25 | 5 (2) |
| n10 | 3 | 130 | 94 | 16 (4) |
| n15 | 2 (tea, si-topcon) | 27 | 18 | 7 (0) |
| n20 | 3 | 298 | 226 | 29 (7) |

- Bridge concepts in all three domains at n20: ambient temperature, device, material, modules, series resistance, solar cell, VOC.
- Visible defects for the failure-modes section: value-bearing labels still become classes ("degradation rate (lower than threshold)", "climate zone (desert)"); near-duplicates survive normalization ("modules" / "PV modules"); very generic classes (device, material) become bridges; disjoint axioms grow faster than classes (tea n20 → n25: +27 % classes, +92 % disjoint axioms), so disjointness needs expert review before it is trusted.

Current pipeline, sweep `20261015-150628` (running, sizes 5–25):
- n5 (all three domains) and integration-n5 done, all valid; tea-n10 done in 32.5 min vs 36.6 min on the previous revision.
- Rows reused in tea-n10 from tea-n5: category 245/739, synonyms 85/237, definitions 103/655, screening 95/614, stage + domain 93/661, disjointness 1/564, parent 0/642.
- First-call answer rate, tea-n5: definitions 87 % (85 % before, batches of 15), disjointness 86 % (81 %), stage + domain in one call 83 % (82 % stage, 87 % domain as separate calls). One run each, not a controlled comparison.
- Not yet run: `scripts/run-checks.ps1` (reused vs fresh answers, one-call vs two-call facets, first-call rates against a baseline). Until it runs, the paper cannot claim that reuse leaves results unchanged.

## Validity and error checking (section 08, "Failure modes found during development")

Found by inspecting run artifacts on earlier revisions; each now has a check:

- Answers wrapped in a copy of the schema were read as empty and counted as successes (12/27 parent calls, 22/22 disjointness, 5/5 restrictions, 22/24 mapping screens in one reliability run). Now unwrapped.
- Partial answers: category for ~74% of concepts, parent for ~48%; 20 of 90 integration pairs answered. 51–77% of classes ended on a BFO category root. Now retried in smaller batches and reported per pass.
- Model category choices overrode a correct extraction type about half the time (e.g. LCOE filed under function). Now the category comes from the type; the model only marks non-classes.
- Leaked model ids as terms: 1.9–3.0% of concepts; 15 of 27 cross-domain candidates. Now blocked, stripped, skipped.
- Type drift: 50–79 type strings, 8–11% untyped. Now mapped to the enum.
- Evidence: 24% empty quotes (20 TEA papers); ligatures and ellipses failed the check (59.0% → 65.1% verified after normalizing). Now re-asked, flagged unevidenced, normalized.
- Values on the wrong concept: 66–77% on devices/materials. Now property + entity.
- Sparse source definitions: 18 of 529 classes. Now status per definition, never pooled.
- Integration picked older runs from different code. Now each input run and revision is listed and mixed revisions are noted.
- A restarting local model server failed runs after ~15 s; now waited out for up to 15 min. Model merge labels returned as non-text crashed normalization; now read as text.
- Still open: one invalid-JSON answer in normalization stops the whole run (reliability-n15).
- Not catchable by any of these: a well-formed wrong answer. That is what CQs, judging and the human calibration subset are for.

## Paper status (2026-10-15)

- Drafted (2026-10-04) to the pipeline as it was then: abstract, 01, 02, 03, 04, 04b, 05, 08, 10. Skeletons: 06 results, 07 discussion, 09 conclusion.
- Out of date since then, to revise in Overleaf: 03/04 (category from the extraction type, ontology store and portals, answer reuse across sizes, one-call facets, disjointness once per pair, batch sizes, concurrency), 05 (local 9B model for development and first results, HPC with Mistral Small 4 and gpt-oss-120b for validation, sweep sizes 5–25), 08 (new failure modes above).
- 06 results waits for the final-revision sweep; no numbers from earlier revisions in Results.
- New section 03b Embeddings (2026-10-16), drafted as `paper/swj/03b-embeddings.tex` to paste into Overleaf after 03: model and embedded text, ontology store index, every embedding comparison by stage, the parent-retrieval revision (2026-10-16-embedding-parents) and limits. Motivating numbers are development observations (revision 2026-10-15, n25); effect numbers are `% TODO` until runs on the new revision.
- New section 03c Automation (2026-10-16), `paper/swj/03c-automation.tex` with `automation.bib`, after 03b: corpus acquisition, the six agents (model calls vs deterministic code), external services, unattended operation (retries, row coverage, reuse, sweeps, auto-resume, Slurm), records for review, and what remains for the scientist. Motivated by SWJ work: Li/Garijo/Poveda-Villalon LLM ontology engineering review and Tsaneva et al. LLM ontology evaluation (both submissions under major revision; check status before citing), Chaves-Fraga et al. KG construction editorial (SW 17(3), 2026), KG generation from text editorial (accepted). Reviewer time per item is `% TODO` until the expert calibration runs.
- "At category root" in the tables above counts only fallbacks (680 of 2,199 in reliability-n25, 31%); classes whose direct parent is any bare BFO category, including the model choosing the root, are 1,652 (75%). Say which one a number means.

## Open decisions (`% DECIDE:` in the .tex)

1. Title and system name: proposed "Knowledge Workflow: Evidence-Traceable Domain Ontologies from Photovoltaics Literature, Built per Subdomain and Connected".
2. Corpus selection: curated 30–50 paper sets vs the code's citation-ranked top N of each collection (72–233 items). Sweeps so far cover tea, reliability and si-topcon; Si-PERC has not been run.
3. Sampling: temperature is unpinned for every agent; pin before reported runs?
4. External conformance tools (OOPS!, OWL 2 DL profile) or structural validation only.
5. Judging tasks (currently five) and which model judges.
6. Run variance: now measurable (`KW_FRESH=1`; `scripts/run-checks.ps1` compares two fresh runs), not yet measured.
7. Existential restrictions as an open item for expert review.
8. LoRA adapter: in a reported run, or future work.
9. Section 04b: keep, shorten into Implementation, or move to supplementary material.
10. Statements: funding, conflicts (MDS-Onto co-authorship), ORCIDs, data archive.
11. Answer reuse across corpus sizes: describe as part of the method once the reuse check supports it, or report sizes run independently.
12. HPC comparison: which measures (class overlap, BFO placement, mappings, bridge concepts, compute), and whether either HPC model is treated as the reference or both are compared to the local run.
13. Disjointness: thousands of sibling disjoint axioms per domain; keep all, limit, or leave for expert review only.

## Runs to report

- Local, final revision: tea, reliability, si-topcon at 5, 10, 15, 20, 25 papers, each size followed by `integrate` (sweep `20261015-150628`, stops at n25).
- HPC: the same sizes and corpora with Mistral Small 4 and gpt-oss-120b, same revision, then the comparison with the local runs.
- Report only runs and integrations whose inputs share one revision and profile.

## Questions for the next interview session

- Why the earlier implementation was replaced rather than extended (for 04b, in your words).
- Is the literature layer a contribution you want to claim, or supporting infrastructure?
- What the HPC models are for in the paper: validation of the local results, the reported configuration, or both?
- Which bridge concepts would you expect between each pair of subdomains? (Write down before seeing the integration output.)
- Who authors the competency questions for each subdomain, and when?
- Why stop the sweep at 25 papers per domain (time, GPU, or enough for the claim)?
