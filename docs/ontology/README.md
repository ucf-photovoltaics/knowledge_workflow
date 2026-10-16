# Operational codebase ontology

Author: Brent Thompson <brent.thompson@ucf.edu>

Entry graph: [knowledge-workflow.ttl](knowledge-workflow.ttl), with equivalent
[JSON-LD](knowledge-workflow.jsonld). Start at `kw:CodebaseDocumentation`, then follow
`kw:documentsWorkflow` or `kw:hasCodeUnit`. The workflow entry remains `kw:LiteratureToOntologyWorkflow`.
The proposed namespace is `https://w3id.org/ucf-dpv/knowledge-workflow/codebase#`; it has not been registered
or published. No institutional hosting/endorsement is implied.

## What an agent can navigate

Workflow → steps → prerequisites, function implementations, source paths/signatures/lines/hashes,
input/output artifact specifications, configuration names, CLI/wrapper invocation argument vectors,
required parameter bindings, completion checks, recovery rules and side effects. All first-party code
files and Python callables are represented. Syntactic callTargetText is deliberately not claimed to be
a resolved dynamic call graph. See [agent guide](../codebase/agent-guide.md) and [step reference](../codebase/agent-steps.md).

The codebase root connects every inventoried source file and callable, including dashboard and helper
code. Internal imports and conservatively resolved calls connect modules. Shared artifact specifications
connect steps through their inputs/outputs. Step resources embed the actual extraction/normalization/
placement/enrichment/interoperability/integration prompts and schemas with hashes. Configuration nodes
link to source definitions where statically identifiable; no credential values are included.

Select `kw:hasInvocation` by `kw:executionMode`, then follow `kw:requiresStepForMode`, `kw:requiresCondition`,
`kw:requiresBinding` and `kw:coversStep`. These distinguish a single CLI extraction command covering
ingest/parse/extract from the dashboard's three separate operations. Conceptual `kw:requiresCompletionOf`
is not a substitute for these mode-specific requirements. Required products use `kw:requiredOutput`;
`kw:artifactLocations` lists relative locations (for example, reports at the selected root or `figures/`).

The graph is a source-linked operational reference, not a magical executor. A new agent still needs an
authorized runtime, real input selections, credentials, available models and the implementation. The
examples were source-checked; no live literature run was performed to certify every execution path.

## BFO/CCO alignment

The pinned snapshots in imports/lock.json include BFO2020 and CCO merged version2026-08-13, copied read-only
from the repository's existing ontology cache, plus official PROV-O. Their original authorship/licenses
are retained. SHA256 hashes pin the exact files; ontology/version IRIs are recorded in the lock.

- WorkflowSpecification and StepSpecification subclass CCO Plan (ont00000974).
- CodeUnitSpecification, InvocationSpecification, ArtifactSpecification, ConfigurationSpecification and
  ParameterSpecification subclass CCO Prescriptive Information Content Entity (ont00000965).
- ExecutionProcess subclasses CCO Act of Information Processing (ont00000366) and PROV Activity.
- ExecutionRecord and ArtifactRecord subclass CCO Information Content Entity (ont00000958) and PROV Entity.
- CodebaseSnapshot and RuntimeObservation subclass CCO Descriptive Information Content Entity (ont00000853)
  and PROV Entity. ResourceSpecification and EnvironmentConditionSpecification are prescriptive content.
- Workflow/step plans additionally subclass PROV Plan. Imported labels, definitions and named ancestor
  chains enrich these external links; see [enrichment counts](enrichment.json). SKOS definitions explain
  local concepts. No guessed `owl:equivalentClass`, `owl:sameAs` or unverified vocabulary mapping is added.

Code nodes represent code **contents/specifications**, not physical disks or material file bearers.
Expected artifact patterns are specifications, not assertions that files were generated. ExecutionRecord
describes an ExecutionProcess; records are not processes. These classes are available for actual provenance;
documentation generation creates no fictitious execution instances.
Plan dependencies are local specification relations, not BFO temporal precedence between processes.
No blanket equivalence between BFO/CCO and PROV top-level classes is asserted. No IAO duplication is
needed because CCO supplies the selected information-content hierarchy.

Authoritative modeling references: [CCO information](https://commoncoreontology.github.io/cco-webpage/information/),
[BFO2020](https://github.com/BFO-ontology/BFO-2020), [PROV-O](https://www.w3.org/TR/prov-o/).

## Offline loading and validation

The main graph imports pinned version IRIs. For offline use, resolve those exact IRIs to the files listed
in imports/lock.json or load the three snapshots plus the main graph explicitly. The validator does the
latter and rejects unresolved transitive imports. Do not let an editor silently fetch a different release.

`scripts/validate-codebase-ontology.py` checks SHACL step/code/invocation contracts, source freshness,
real function links, prerequisite cycles, template argument structure, snapshot hashes and external
class existence. It materializes OWL-RL over the import closure and checks named disjointness conflicts.
It also checks reachability from the documentation root, shared artifact flow, mode-specific dependency
cycles, invocation coverage/conditions, newly added or removed code, and prompt/schema/guide/contract
fingerprints. Fixture tests exercise successful and rejected navigation/planning cases.
Results: validation.json and shacl-report.txt. Tool environment: rdflib7.6.0, pyshacl0.40.1, owlrl7.6.2.

This establishes alignment and consistency **within those checks**, not full OWL2DL classification,
formal BFO/CCO certification, scientific correctness, provider availability or successful execution of
every command. A complete DL reasoner was unavailable in this environment; that limitation is recorded.
Imported terms may use constructs beyond OWL-RL. Revalidate after changing source or contracts.

Regeneration commands are in [codebase README](../codebase/README.md). SHACL definitions are in shapes.ttl.

## Source of truth and agent use

The default reviewer now opens an **information journey**, with fixed reading order and explicit
data transformations. InformationStateSpecification nodes represent paper records, canonical
vocabulary, placed/enriched classes, formal exports, literature claims and integrated results.
InformationTransformationSpecification nodes link these representations to actual stage functions
and explain preservation, additions, omissions and provenance gaps. States align with CCO
prescriptive information content; transformation plans align with CCO Plan. They are not asserted
as real domain materials or executed processes. Integration is an optional reporting input.

**Follow a real concept · n15** is a separate, fingerprinted observation package. It exposes saved
canonical-ID/IRI joins, source papers/quotes, formal/merged class membership and reconstructed merge
candidates without promoting inference to recorded provenance. See the
[journey guide](../codebase/data-journey.md) and [information-flow query](information-flow.rq).

Every project-owned RDF node now has an English `skos:definition` annotation. Definitions do not
reclassify workflow records as `skos:Concept`. Source-reviewed behavior is distinguished from structural
identity descriptions; missing type annotations and uncurated helper behavior remain explicit gaps.
Formal argument nodes retain names, kinds, required/default values and source type expressions.

All11 stages have source-reviewed operational recipes, input/return contracts, data bindings, operation
sequences, worked examples, recovery and limitations. Start with the nine-operation
[Normalization example](../codebase/normalization-walkthrough.md), then use the
[remaining stage walkthroughs](../codebase/stages/README.md). Read-only checks cover paper contracts,
selected-corpus coverage, canonical endpoints, placement/enrichment identity preservation, restriction
targets, mapping/source provenance, export round trips and report packages. Check rules explicitly
state before/after phase and any execution-mode restriction. Setup checks remain runtime-only.
These documentation-layer checks do not alter pipeline validation policy. Follow `evaluatedBy` from
a check to its evaluator. Structural-only helper descriptions remain honest gaps; a detailed stage
recipe does not certify every internal callable or scientific decision.

Exact saved-export comparisons are limited to12,000 triples per graph and40 distinct blank-node
identifiers across the pair. Larger exports are parsed and fingerprinted, but equality remains
unverified and is returned as a review finding. This prevents expensive canonicalization from
stalling routine navigation; it does not silently promote readability to graph equivalence.

The focused [WebVOWL reviewer](viewer/index.html) source is exported by
`scripts/export-codebase-webvowl.py` using the existing dashboard Python environment. It defaults to
a small stage data-flow view, with implementation and bounded code neighborhoods available separately.
Source snapshots, explicit definitions and bidirectional artifact links support review without opening
the entire record graph. The standalone preview remains at localhost8058; the pipeline/dashboard are
not modified by its export.
Its maintained reviewer bridge coalesces delayed graph framing when stages change; the dashboard's
original WebVOWL bridge and third-party assets retain their own behavior.

The graph is a versioned specification of the implemented workflow, not a live status database.
`scripts/ontology_agent.py plan` reads its trusted invocation nodes and emits bound argument vectors
with prerequisites and completion/recovery guidance. It does not execute them. `inspect` reads a selected
saved run and emits JSON or RDF observations with time, artifact hashes, recorded status and blockers.
Observations remain separate from the specification graph and never assert fabricated process instances.
Actual run manifests/products remain authoritative for recorded execution. Scientific acceptance still
requires evidence and review checks; a readable output or recorded completion is not acceptance.

See the [agent guide examples](../codebase/agent-guide.md#machine-readable-planning-and-saved-run-observations)
and [usability audit](usability-review-2026-10-16.md). The preflight has a documented exit-status trap:
require its printed `ready` outcome without failed checks. Store preparation is conditional and must
not rewrite shared assets used by active jobs. Revalidate source fingerprints before trusting the graph.
