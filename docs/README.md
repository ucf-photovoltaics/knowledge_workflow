# Knowledge Workflow documentation

Author: Brent Thompson <brent.thompson@ucf.edu>

## Start here

The main dashboard's **Documentation** header button opens a searchable library of these guides,
with a **Dashboard** return button on each page. The library is served by the dashboard at
`http://127.0.0.1:8056/documentation/library.html`; it follows a custom dashboard port automatically.
Choose **Information journey & WebVOWL** to explore the interactive operational ontology.

- [Architecture and ownership](architecture.md)
- [Dashboard user guide](../dpv_dashboard/README.md)
- [Codebase documentation and regeneration](codebase/README.md)
- [Agent step-by-step operating guide](codebase/agent-guide.md)
- [Operational ontology and validation](ontology/README.md)
- [Ontology usability and source-of-truth audit](ontology/usability-review-2026-10-16.md)
- [Source module/callable inventory](codebase/modules.md)
- [Review findings and follow-up work](codebase/review.md)

## Pipeline contracts

1. [Extraction, ingestion and parsing](stages/1-extract.md)
2. [Normalization](stages/2-normalize.md)
3. [Ontology placement](stages/3-ontology.md)
4. [Enrichment](stages/4-enrich.md)
5. [Interoperability and export](stages/5-interop.md)
6. [Cross-domain integration](stages/6-integrate.md)
7. [Reporting and compute provenance](stages/7-reporting.md)

[Ontology store preparation](ontology-store.md) is a prerequisite for placement and downstream knowledge lookup.

The operational ontology contains specifications and templates, not a record of imaginary executions.
Use explicit run/project/domain IDs, inspect evidence and review flags, and preserve active jobs.
