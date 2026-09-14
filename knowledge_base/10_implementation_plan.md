# 10 — Implementation Plan (toward a defensible SMSE submission)

Goal: move `kw/` from a working prototype with several stubbed/aspirational pieces to
an artifact whose paper claims are all backed by running code and measured numbers,
suitable for the Semantic Web Journal *Semantic Materials Science and Engineering*
special issue.

The plan is organized into five workstreams. Each task carries an ID, the files it
touches, an acceptance criterion (how you know it's done), and a rough size
(**S** ≈ half-day, **M** ≈ 1–3 days, **L** ≈ a week+). A phased sequence and a
"minimum defensible submission" cut are at the end.

> Framing rule: every task is tied to a **paper claim it backs**. If a task doesn't
> back a claim or unblock a number, it's out of scope for the submission.

---

## Implementation status (current pass)

Code-level tasks are **implemented and opt-in** (off by default, so the working run
is unchanged unless enabled). Evaluation tasks that require live experiments ship as
**runnable harnesses** — the code is done; producing the numbers is a run you trigger.

| Task | Status | Where |
|------|--------|-------|
| T1.1 reasoner | done (opt-in `RUN_REASONER`, owlready2/HermiT) | `kw/validate.py` |
| T1.2 OOPS! | done (opt-in `RUN_OOPS`, REST) | `kw/validate.py` |
| T1.3 SHACL | done (opt-in `RUN_SHACL`, pyshacl) | `kw/validate.py`, `kw/shapes/mds_shapes.ttl` |
| T1.4 BFO/CCO parents | done | `kw/ontology.py` |
| T1.5 LoRA loop hook | done (config `LORA_ADAPTER_PATH` + Ollama Modelfile) | `kw/lora.py`, `kw/pipeline.py` |
| T1.6 confidence | done (REBEL beam-score confidence) | `kw/rebel.py` |
| T2.1 multi-domain metrics | harness | `eval/run_all.py` |
| T2.2 REBEL ablation | harness (live) | `eval/ablation_rebel.py` (+ `do_rebel` flag) |
| T2.3 learning-loop ablation | needs live training run | depends on T1.5; protocol documented |
| T2.4 spot-check + kappa | harness | `eval/spot_check.py` |
| T2.5 baseline vs NeOn-GPT | external run | documented; not code |
| T3.1 entity resolution | done (opt-in `MERGE_REBEL`) | `kw/merge.py` |
| T3.2 predicate vocab | done | `kw/relations.py` |
| T3.3 chunking | done (opt-in `CHUNK_FULL_TEXT`) | `kw/extract.py` |
| T4.1 checkpointing | done (`USE_CHECKPOINT`) | `kw/extract.py`, `kw/pipeline.py` |
| T4.2 retry/backoff + PDF surfacing | done | `kw/llm.py`, `kw/pipeline.py` |
| T4.3 async | deferred (risks determinism; revisit after numbers) | — |
| T4.4 pinned repro | done (offline reproduce script) | `scripts/reproduce.py` |
| T5.1 patent source | done (drop-in adapter) | `kw/sources/patents.py` |

---

## WS1 — Claims ↔ code parity (highest priority)

These are places where the paper currently asserts something the code only stubs or
skips. Reviewers will check; close the gap or soften the claim.

### T1.1 — Wire a real reasoner into the validation gate — **M**
- **Backs:** "logical consistency … passes a DL reasoner with no unsatisfiable classes."
- **Today:** `kw/validate.py:run_reasoner()` returns `True` unconditionally.
- **Do:** shell out to ROBOT (`robot reason --reasoner ELK` / `report`) or call
  `owlready2` + HermiT; parse the result into `{consistent: bool, unsatisfiable: [..]}`.
  Keep the current function signature so `evaluate()` is unchanged.
- **Accept:** running the gate on a deliberately broken TTL (e.g. a class made
  `owl:disjointWith` its own parent) returns `consistent=False`; the GaAs reference
  returns `consistent=True`.

### T1.2 — Wire OOPS! pitfall scanning — **M**
- **Backs:** "an ontology-pitfall scan (OOPS!) reports no critical pitfalls."
- **Today:** `kw/validate.py:run_oops()` returns `[]`.
- **Do:** POST the TTL to the OOPS! REST API (`oops-ws`), parse pitfalls, filter to
  `Critical`/`Important`. Cache responses to avoid hammering the service; degrade to a
  logged warning (not a hard fail) if the service is unreachable, mirroring the REBEL
  no-op pattern.
- **Accept:** report lists pitfall codes (e.g. P08 missing annotations) with severities;
  the gate's `passed` flag flips when a critical pitfall is present.

### T1.3 — Define and check SHACL shapes — **M**
- **Backs:** "structural constraints can be expressed in SHACL."
- **Today:** SHACL is mentioned but no shapes file exists.
- **Do:** author `kw/shapes/mds_shapes.ttl` (e.g. every `SchemaRecord` must have a DOI;
  every concept property must have an `rdfs:label` and a `skos:broader`); validate with
  `pyshacl` in a new `validate.run_shacl(ttl_path)`; fold the result into `evaluate()`.
- **Accept:** a JSON-LD instance missing a required field is reported as a SHACL
  violation; a clean run passes.

### T1.4 — Add BFO/CCO parents to the grounding layer — **M**
- **Backs:** "interoperable with BFO, CCO, and MDS-Onto"; the alignment ratio.
- **Today:** `kw/ontology.py:_CLASS_PARENTS` tops out at `mds:Concept`; no BFO/CCO IRIs
  are ever emitted, so "BFO/CCO interoperability" is currently aspirational.
- **Do:** add a small mapping table from each of the eight MDS branches to a BFO (and,
  where apt, CCO) parent — e.g. `Measurement ⊑ bfo:Quality` (BFO_0000019),
  `Process ⊑ bfo:Process` (BFO_0000015), `Material ⊑ bfo:MaterialEntity`
  (BFO_0000040), `Device ⊑ cco:Artifact`. Emit those `rdfs:subClassOf` triples in
  `build_collection_ontology`. Update `validate.UPPER_PREFIXES` already includes BFO/CCO,
  so the alignment ratio will rise automatically.
- **Accept:** the emitted TTL contains BFO/CCO IRIs; `alignment_ratio` on a fresh run
  counts BFO/CCO parents, not just MDS.

### T1.5 — Close the LoRA learning loop in code — **M**
- **Backs:** "successive runs reuse prior ontologies to ingest new material more accurately";
  "using the trained LoRA adapter directly within the extraction agents."
- **Today:** `kw/lora.py` trains and saves an adapter but nothing ever loads it back;
  `config._make_model()` always builds the base model.
- **Do:** add `LORA_ADAPTER_PATH` to `config`; when set, load base + adapter (PEFT) for the
  extraction/mining agents. Record the active adapter version in each run's provenance.
- **Accept:** a run with `LORA_ADAPTER_PATH` set logs "extractor using adapter
  lora-<stamp>"; the adapter measurably changes extraction output vs. base (feeds T2.3).

### T1.6 — Replace hardcoded confidence with a real signal — **M**
- **Backs:** "each assertion carries provenance … and confidence"; the trust/guardrail story.
- **Today:** `kw/models.py:Provenance.confidence` is always `1.0`.
- **Do:** for LLM assertions, derive confidence from token logprobs (if the provider
  exposes them) or from 2-sample self-consistency (agree → high, disagree → low). For
  REBEL, use the beam score. Persist it on every `Triple`/cell.
- **Accept:** confidence varies across assertions; low-confidence cells are flagged in the
  JSON-LD and can be filtered in GraphDB.

---

## WS2 — Quantitative evaluation (unblocks the Evaluation section)

The paper currently reports one reference run (GaAs 7/7). A journal will want numbers
across the corpus plus at least one ablation and a sanity check against ground truth.

### T2.1 — Multi-domain structural metrics table — **M**
- **Backs:** the Evaluation section's central results table (currently absent).
- **Do:** run the full pipeline over every domain in the corpus (GaAs, CdTe/CdSeTe,
  perovskite, TEM semiconductors, copper metallization, electron-microscopy corrosion);
  collect per-domain `{classes, alignment_ratio, reasoner_consistent, oops_critical,
  shacl_violations, #concepts, #triples, #papers}` into one CSV/LaTeX table via a new
  `eval/run_all.py`.
- **Accept:** a reproducible table of ≥6 domains drops straight into the paper.

### T2.2 — Ablation: LLM-only vs. LLM+REBEL — **M**
- **Backs:** contribution #2 (the dual extraction stage).
- **Do:** run each domain with REBEL on and off; report added relational triples, added
  graph connectivity (e.g. # connected components, # cross-concept edges), and any change
  in alignment. This isolates REBEL's contribution.
- **Accept:** a table/plot showing what REBEL adds that the per-concept LLM pass misses.

### T2.3 — Ablation: learning loop (run N vs. N+1) — **L**
- **Backs:** the compounding-improvement / closed-loop claim (the special issue's
  "closed-loop optimization" wording). Depends on **T1.5**.
- **Do:** train the adapter on domain A, then extract domain B with and without it;
  measure schema fill-rate, concept precision against the supervised list, and
  validation metrics. Honest negative results are still publishable — the machinery and
  protocol are the contribution.
- **Accept:** a head-to-head showing whether the adapter helps, hurts, or is neutral, with
  the measurement protocol documented.

### T2.4 — Gold-standard spot-check with inter-annotator agreement — **M**
- **Backs:** turning "structural soundness ≠ domain correctness" from a caveat into a
  measured bound.
- **Do:** sample ~50–100 extracted (concept, value, quote) cells and ~50 REBEL triples;
  have two domain readers label correct/incorrect; report precision and Cohen's κ. Reuse
  the draw.io diagram as the review surface.
- **Accept:** reported precision + κ for both the LLM extraction and the REBEL triples.

### T2.5 — Baseline comparison vs. NeOn-GPT (or SPIRES) — **L**
- **Backs:** "closest prior pipeline" — reviewers will ask why Kweave is better.
- **Do:** run NeOn-GPT (or OntoGPT/SPIRES) on one shared domain; compare alignment,
  pitfalls, consistency, and #grounded classes. Frame as complementary where fair.
- **Accept:** one apples-to-apples comparison table on a single domain.

---

## WS3 — Graph quality (raises the ceiling of the output)

### T3.1 — Entity resolution at the merge step — **L**
- **Backs:** Step 3 "Consolidate … one node per real thing"; the merge limitation.
- **Today:** REBEL triples land in a separate `rebel_triples.jsonld`, disconnected from the
  concept nodes — two outputs, not one graph.
- **Do:** implement `kw/merge.py`: link REBEL subjects/objects to concept/`SchemaRecord`
  URIs by normalized string match first, then embedding similarity (cosine over
  sentence-transformer vectors) with a threshold; emit `owl:sameAs`/shared-URI links.
- **Accept:** REBEL triples reference concept URIs; the combined graph has materially fewer
  disconnected components (measure before/after).

### T3.2 — Normalize REBEL predicates to a relation vocabulary — **M**
- **Backs:** queryability of the relational layer.
- **Today:** REBEL emits free-text predicates straight into JSON-LD.
- **Do:** map surface predicates to a small controlled set of `mds:` object properties
  (e.g. "is deposited on" → `mds:depositedOn`) via a lookup + embedding fallback; keep the
  raw predicate as an annotation for provenance.
- **Accept:** triples use a bounded predicate vocabulary; unmapped predicates are logged.

### T3.3 — Chunk long full texts instead of truncating — **M**
- **Backs:** extraction completeness; removes a silent failure mode.
- **Today:** `FULL_TEXT_MAX_CHARS=80000` hard-truncates; the tail of long papers is dropped.
- **Do:** window the text, mine per chunk, and aggregate per concept (prefer the
  highest-confidence non-empty value); de-duplicate quotes.
- **Accept:** for a paper > 80k chars, values are recovered from sections beyond the cutoff.

---

## WS4 — Robustness & reproducibility (credibility of the artifact)

### T4.1 — Per-paper checkpointing + resume — **M**
- **Backs:** the reproducibility claim; makes multi-domain runs (WS2) feasible.
- **Today:** `kw/pipeline.py` is serial with no checkpointing; a late error reprocesses
  everything.
- **Do:** persist each paper's mined result as it completes; on restart, skip papers
  already done. A simple per-paper JSON cache keyed by Zotero item key suffices.
- **Accept:** killing a run mid-corpus and restarting resumes without re-mining.

### T4.2 — Retry/backoff and surfaced PDF failures — **S**
- **Today:** LLM calls use `retries=2` with no backoff; `zotero.get_pdf_text` already logs
  but failures aren't summarized.
- **Do:** wrap provider calls in exponential backoff; collect skipped/failed PDFs into a
  per-run report.
- **Accept:** a transient 429 no longer aborts the run; the run summary lists any skipped
  papers.

### T4.3 — Optional async/parallel mining — **M**
- **Backs:** the runtime numbers cited in Discussion.
- **Do:** parallelize Step 2 across papers with a bounded worker pool (respecting
  `RATE_LIMIT_DELAY`); keep determinism by sorting outputs before emission.
- **Accept:** wall-clock for a 50-paper mine drops materially; outputs identical to serial.

### T4.4 — Pin REBEL revision and ship a reproducibility artifact — **S**
- **Today:** `REBEL_REVISION='main'` (not pinned) in `kw/rebel.py`.
- **Do:** pin to a commit hash; assemble a repro bundle — seeds, model IDs, pinned REBEL
  hash, a small sample corpus, and the GaAs gold ontology — with a one-command run script.
- **Accept:** a fresh clone reproduces the GaAs reference metrics.

---

## WS5 — Stretch: broaden the extraction source

### T5.1 — Patent source adapter — **L**
- **Backs:** the special issue's explicit mention of **patents**; widens contribution #1.
- **Today:** `kw/zotero.py` is the only source; everything downstream consumes the uniform
  corpus dict `{title: {key, title, doi, abstract, date, authors, full_text}}`.
- **Do:** add `kw/sources/patents.py` that yields the same contract from a patent source
  (e.g. Google Patents / USPTO bulk / Lens.org export). No downstream changes needed if the
  contract is honored.
- **Accept:** one patent-derived collection runs end-to-end and produces a validated
  ontology + JSON-LD.

---

## Phased sequence (dependencies honored)

**Phase 0 — Parity quick wins (make claims true):** T1.4 (BFO/CCO), T4.4 (pin + repro),
T4.2 (retry). These are small and immediately strengthen the paper.

**Phase 1 — Validation gate is real:** T1.1 (reasoner), T1.2 (OOPS!), T1.3 (SHACL).
Unblocks every metric in WS2.

**Phase 2 — Numbers for the paper:** T4.1 (checkpoint) → T2.1 (multi-domain table) →
T2.2 (REBEL ablation) → T2.4 (spot-check + κ). This is the core of a publishable
Evaluation section.

**Phase 3 — Depth and differentiation:** T3.1 (entity resolution), T3.2 (predicate
vocab), T1.5 + T2.3 (close and measure the learning loop), T2.5 (baseline vs. NeOn-GPT).

**Phase 4 — Polish / stretch:** T1.6 (real confidence), T3.3 (chunking), T4.3 (async),
T5.1 (patents).

---

## Minimum defensible submission

If time is tight, the smallest cut that makes the paper's claims honest and gives
reviewers numbers:

- **T1.1 + T1.2 + T1.4** — the validation gate actually validates, and BFO/CCO grounding is real.
- **T2.1 + T2.2 + T2.4** — a multi-domain metrics table, the REBEL ablation, and a small expert spot-check with κ.
- **T4.1 + T4.4** — checkpointing so the runs above are feasible, and a reproducibility bundle.

Everything else (entity resolution, the measured learning loop, baseline comparison,
patents) strengthens the work and can be staged as "in progress" or future work without
undermining the central claims.

---

## Claim → task traceability

| Paper claim | Backed by |
|---|---|
| Validation gate (reasoner + OOPS! + alignment) | T1.1, T1.2, T1.4, T2.1 |
| SHACL structural constraints | T1.3 |
| BFO/CCO/MDS interoperability | T1.4, T2.1 |
| Dual LLM + REBEL extraction | T2.2, T3.1, T3.2 |
| LoRA learning loop / closed loop | T1.5, T2.3 |
| Provenance + confidence / trust | T1.6, T2.4 |
| Reproducible by construction | T4.1, T4.2, T4.4 |
| Automated extraction (incl. patents) | T5.1 |
