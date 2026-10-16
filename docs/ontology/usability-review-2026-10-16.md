# Operational ontology usability review

Author: Brent Thompson <brent.thompson@ucf.edu>

## Review objective

Enable an agent to enter from one documentation node, discover relevant code and contracts, bind a
mode-consistent plan, inspect each saved result and recover deliberately. Preserve the distinction
between prescriptions, execution processes, execution records and scientific acceptance.

## Gaps found and addressed

| Finding | Change and practical consequence |
|---|---|
| Source inventory existed without a common connected entry. | CodebaseDocumentation reaches every file and its callables; internal imports and resolved static references add navigation. Dynamic calls remain explicitly syntactic observations. |
| Identical artifact patterns were separate nodes per step. | Shared ArtifactSpecification nodes now connect production and consumption. Required products are separate from optional or descriptive artifacts. |
| Conceptual steps could be mistaken for runnable commands. | Each invocation has mode-specific dependencies, coverage and conditions. CLI extraction covers ingestion/parsing too; wrapper extraction does not. |
| Agent instructions placed full preflight before store preparation. | A missing store must be prepared first. Existing readiness is checked before a conditional build, protecting active shared assets. |
| Preflight success was easy to infer from exit status. | Source inspection of src.run.check found caught failures without guaranteed nonzero status. Completion requires printed checks and final ready outcome. |
| Prompt/schema rules were outside the graph. | Step resources embed their actual text and fingerprints, with configuration-to-source links where statically identifiable. |
| Documentation could remain trusted after contract changes. | Freshness checks now include guide, workflow contract, SHACL, prompt/schema content and all inventoried source; CLI also rejects changed code coverage. |
| No operational comparison with actual saved runs. | Read-only observations distinguish recorded completion, product readability, partial failures and review needs, and carry artifact hashes/PROV derivations. |
| Reports could be incorrectly sought only in a domain root. | The graph records alternative relative artifact locations. The observer finds reports in figures/ and distinguishes available outputs from recorded completion. |
| External alignment was mostly subclass links. | Pinned BFO/CCO/PROV labels, definitions and named ancestor chains enrich navigation; local terms have definitions. No speculative equivalences were introduced. |

The contract source is [workflow.json](../codebase/workflow.json). The implementation references and
completion rules are generated into [agent-steps.md](../codebase/agent-steps.md). The main
[agent guide](../codebase/agent-guide.md) is embedded in the ontology as prescriptive content.

## Verification and evidence

Current outcomes are recorded in [validation.json](validation.json), [enrichment.json](enrichment.json)
and the [verification record](../codebase/verification.md). Fixture tests live in
`tests/test_codebase_ontology.py`; regeneration, validation, planning and observation are isolated from
the pipeline runtime. Negative cases cover missing/unreadable products, partial extraction, later
failures, missing bindings, path traversal, mode cycles, disconnected source nodes and stale contracts.
Read-only checks of the existing n15 domain and integration runs exercise real artifact formats and
recorded source-domain links. No new literature/model run is launched as part of this review.

CCO information-content modeling follows its [official explanation](https://commoncoreontology.github.io/cco-webpage/information/).
Provenance follows [PROV-O](https://www.w3.org/TR/prov-o/): a specification/record is an entity and an
actual occurrence is an activity. Local information-processing occurrences are aligned with the CCO
act class; records are never activities. Import closure is pinned, hashed and checked offline.

## Limits retained deliberately

The plan helper is not another pipeline executor. An agent uses the returned argument lists through
its authorized tools only after establishing conditions and reviewing results. Store state, provider
availability, process ownership, full scientific review and every possible provider configuration are
not established by static ontology validation. The observer checks structure/readability, recorded
failures and selected freshness signals, not full schema validity or logical entailment of paper claims.
Unrecorded artifact edits can still make downstream results stale. Refresh observations before acting.

OWL-RL and named disjointness checks are bounded consistency checks, not complete OWL2DL classification
or institutional BFO/CCO certification. No complete DL reasoner was available. The namespace remains a
proposal, not a published institutional identifier. Source files and saved manifests remain inspectable
evidence behind the versioned ontology rather than being displaced by unsupported assertions.
