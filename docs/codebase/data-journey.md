# Information and concept journeys

Author: Brent Thompson <brent.thompson@ucf.edu>

The default standalone reviewer at http://127.0.0.1:8058/ follows information representations through
the pipeline. Cards use a stable reading order, left to right and then down; each handoff opens the
retained, added and omitted information, the provenance limitation and the responsible functions.
Stage-file and implementation neighborhoods remain available in WebVOWL.

## Information flow is part of the ontology

`data-flow.json` is the curated source. `scripts/data_journey.py:enrich_journey` embeds the complete
definition in RDF and creates explicit, connected InformationStateSpecification and
InformationTransformationSpecification nodes. States link to existing artifact specifications;
transformations link to their input/output states, implementing stages and actual code functions.
State field lists describe the information boundary. Source hashes protect the recipe against drift.

Start from CodebaseDocumentation → documentsWorkflow → hasInformationState / hasInformationTransformation.
Follow transformsInputState and producesInformationState to discover how information changes, then
transformationImplementation to source arguments and implementation. `guide --step normalize` includes
the stage's information_transformations as well as its callable contracts and worked instructions.
The [information-flow query](../ontology/information-flow.rq) returns these connections directly.

Information states are prescriptions of data structure, aligned with CCO Prescriptive Information
Content Entity. Transformations are CCO Plans. Both are information content, not the real scientific
materials, physical files or executed processes. New nodes have SKOS definitions and SHACL shapes.
No execution or scientific truth is asserted by drawing the flow.

The literature-claims branch is explicit: canonical concepts and saved paper claims feed a separate
SKOS/evidence RDF layer. This does not imply every extracted relation becomes an OWL axiom. Master
integration imports and merges source **formal** ontologies; it does not automatically union their
literature layers. Reporting can run without integration; optionalInputState records that distinction.

## Follow a real saved concept

Choose **Follow a real concept · n15**. Filter the concept selector, then inspect its paper-local
records, canonical vocabulary, placement, enrichment, formal export and integration connections.
The current exported example is si-topcon-n15-20261015-150628 and its explicitly recorded n15 integration.
All1,006 canonical concepts are selectable. This is an export-time snapshot, not a live run monitor.

The default example, **tunnel oxide layer**, has four recorded supporting papers and five label-based
original-record candidates. The snapshot records its declaration in both domain and merged formal
graphs and one cross-domain mapping. Click paper/quote links to open an escaped scientific snapshot;
publication DOI links are available there. Figure links open caption/page records. This documentation
snapshot does not include PDF/image assets or claim image localization.

The original-to-canonical merge map was not saved in this run. Dashed candidate connections are
reconstructed from normalized labels/alternate labels and recorded paper membership. They are not
asserted as exact merge decisions. Ambiguous aliases retain all candidate canonical targets.
If a saved normalized/concept_lineage.json is present, recognized paper/original_id/canonical_id rows
are checked against source identities and labels; missing rows are not filled with inferred merges.
Duplicate or changed-label mappings remain review findings.

Later joins use recorded canonical IDs and class IRIs. Formal and merged membership are observed
from explicit OWL class declarations; they do not prove complete graph equivalence. A class can be
carried into the integration without any cross-domain mapping. Definition imports and facets are
read from interoperability sidecars because enriched.json is not rewritten after those decisions.
Reports are aggregate products; the trace does not invent a per-concept report record.

## Snapshot safeguards and regeneration

The exporter reads a bounded source snapshot, checks SHA256 fingerprints again before publishing,
and writes generated preview artifacts only. Scientific source previews whitelist paper fields;
raw model calls, credentials, provider configuration and local PDF paths are excluded. Rendered
scientific text is escaped. Original run files, pipeline code, stores and dependencies are untouched.

From the repository root, using the existing isolated environments:

```powershell
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/document-codebase.py
outputs/dashboard/.venv/Scripts/python.exe scripts/export-codebase-webvowl.py
outputs/development/codebase-docs/.venv/Scripts/python.exe -m pytest tests/test_data_journey.py tests/test_operational_contracts.py tests/test_codebase_ontology.py -q
outputs/development/codebase-docs/.venv/Scripts/python.exe scripts/validate-codebase-ontology.py
```

Open **Documentation → Information journey & WebVOWL** from the dashboard. The optional standalone
static server on8058 also serves updated files without restarting the pipeline dashboard.
Reload the browser after export. `concept-journey.json` records snapshot time and source fingerprints;
individual traces and whitelisted HTML source previews remain separate from the ontology specification.
Missing n15 data produces an explicit unavailable example rather than fabricated observations.
