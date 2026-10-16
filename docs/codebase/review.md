# Codebase review findings

Author: Brent Thompson <brent.thompson@ucf.edu>

Scope: static inventory of every first-party code file, detailed review of orchestration, stage I/O,
resume/restart, evidence checks, dashboard joins/media and existing regression coverage. This is not
line-by-line scientific adjudication, penetration testing or a live provider/GPU evaluation. No behavioral
pipeline fixes are bundled with the documentation/header work.

| Priority | Finding and source | Consequence / recommended follow-up |
|---|---|---|
| High | extraction._finalize checks quote word trigrams, not numeric/causal entailment; see extraction.py evidence verification block and the n15 audit | Clearly separate quote match from assertion validity; add future assertion-component checks with regression fixtures. |
| High | src.run.extract returns failed-paper counts; main records the returned stage result. Dashboard worker.perform additionally rejects failed counts. | CLI completed extraction can be partial. Agents must inspect corpus.failed before advancing; consider a consistent future policy. |
| High | src.run.normalize saves no exact concept_lineage.json; dashboard research reconstructs older links | Preserve explicit merge lineage and original labels in a separately reviewed future pipeline change; do not fabricate provenance now. |
| Medium | CLI all skips stage keys in run.json; single-stage calls operate in the same run directory | Earlier-stage reattempts can leave downstream artifacts logically stale. Prefer new IDs or documented invalidation; dashboard has separate attempt semantics. |
| Medium | Jobs.running/process ownership is local to one server instance | Separate servers are not a distributed job lock. Avoid controlling one project from multiple instances; persistent per-project locking is a possible future improvement. |
| Medium | ontology_review.correspondences scans other run outputs for candidate matches | Historical cross-domain candidates are advisory and must not be confused with the explicitly selected integration inputs. |
| Medium | Figure focus uses geometric estimates where recorded bounds are absent | A locatable crop is not a scientifically annotated focus region. Preserve estimated/unavailable labels and source access. |
| Medium | src.figures.build catches per-figure failures and continues | Check index/skipped reports; a completed report command does not guarantee every figure exists. |
| Documentation | Mixed CLI/UI stage granularity, credential locations and restart behavior | Addressed in operational ontology contracts and agent guide; callable links and source digests are checked at generation/validation. |

The detailed artifact audit remains in dpv_dashboard/reviews/n15-reference-and-data-audit-2026-10-16.md.
Future behavior changes should have separate approval, focused fixtures and isolated run verification.
