# Worked operational tasks

Author: Brent Thompson <brent.thompson@ucf.edu>

Each recipe traces inputs to their producers, binds callable arguments, follows source operations and
explains returns, persistence, checks and recovery. The ontology embeds and fingerprints these guides.
They describe the implemented behavior; they do not claim successful live execution or scientific acceptance.

| Stage | Worked task | Key boundary |
|---|---|---|
| Setup | [Preflight](preflight.md) | Printed readiness, real provider probes, no per-run completion |
| Shared resources | [Ontology store](store.md) | Conditional shared build; exclusive ownership required |
| 1 | [Zotero ingestion](ingest.md) | Collections across libraries → one ranked domain corpus |
| 2 | [PDF parsing](parse.md) | Selected PDFs → sections, captions, hashes and windows |
| 3 | [Evidence extraction](extract.md) | Parsed context → one saved paper graph with verification |
| 4 | [Normalization](../normalization-walkthrough.md) | Paper graphs → canonical vocabulary and claims |
| 5 | [Ontology placement](ontology.md) | Canonical IDs → parents, exclusions and stable IRIs |
| 6 | [Enrichment](enrich.md) | Placed classes + claims → classes/properties tuple |
| 7 | [Interoperability](interop.md) | Enriched records → formal ontology and separate literature layer |
| 8 | [Integration](integrate.md) | Explicit domain runs → master imports, formal union and bridges |
| 9 | [Reports and figures](reports.md) | Selected saved results → review package with visible skips |

CLI extraction combines stages1–3. Dashboard mode saves them separately. Choose invocation mode before
following conceptual stage order. Direct agent calls bypass orchestration: prefer the documented CLI
or wrapper so settings, ledger, checkpoints and stage records stay consistent.

In WebVOWL, select a stage and open its **Worked example**. The **Input & return contract** explains the
call boundary, **Data bindings** traces artifacts, **Operations** links implementation functions, and
**Checks & review** states each check's phase. The initial graph remains focused; connected records
and code lookup reveal further detail on demand.

Implementation graphs initially show the operation sequence. Select an operation to open its linked
function, formal arguments and source, rather than displaying all function nodes on top of the plan.
