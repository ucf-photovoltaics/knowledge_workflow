# Post-generation ontology quality

Every domain `interop` export now runs assessment after writing `ontology.ttl`.
Every `integrate` run assesses its master plus the selected domain graphs, loaded
through an explicit local import map. Original ontologies are never rewritten.
The existing structural validation remains separate.

## Checks and reports

- RDF parsing and input SHA-256 hashes.
- ROBOT OWL 2 DL profile validation, then HermiT consistency and satisfiability.
- ROBOT editorial report scoped to generated IRIs: labels, duplicate labels,
  annotation whitespace and invalid entity IRIs. Definitions accept either
  `skos:definition` or `IAO:0000115`, matching this pipeline's exports.
- **Every metric registered by OntoCheck 0.1.3**, including its MDS design metric.
  The wrapper requests `--metrics all` and checks each CSV row for failure or
  skipped execution. `searchClass` uses an explicitly supplied search term, or
  the first sorted local class label (recorded in the summary).
- Optional OntoCheck competency-question vocabulary recall/precision. These
  measure term coverage/utilization; they do not assert correct query answers.

Results live in `<run>/quality/summary.json` and `report.md`, with timestamped
assessment subfolders retaining input snapshots, versions, CSV/TSV results,
tool logs, a reasoned ontology when successful, and detailed profiles.
`completed` means the configured tools completed; it is not a quality score.
`needs_review` flags reported ROBOT findings, tool errors or timeouts.
`incomplete` flags unavailable tools or unresolved imports. OntoCheck's scores
are retained without imposing arbitrary acceptance thresholds. A metric can
complete and report poor quality; inspect the scores and detailed metric log.
Some upstream metrics print details but return no numeric value; their CSV
score is blank and their detailed output is in `ontocheck.log`.

Generation keeps its artifacts regardless of quality findings. Report-writing
failures still raise an error. The domain stage stats and integration manifest
include the quality status. Each external command has a default 600-second
timeout; later checks continue after a tool fails or times out.

## Setup

`requirements.txt` includes pinned OntoCheck. For assessment alone, use
`requirements-quality.txt` plus `rdflib` (installed by OntoCheck).

Install Java and [ROBOT](https://robot.obolibrary.org/) on PATH, or set
`ROBOT_JAR` to the absolute JAR path and optionally `JAVA_EXE` to Java's executable.
This checkout also discovers portable tools under `outputs/quality-tools/`:
`robot.jar` and a Java runtime at `*/bin/java.exe`. Portable ROBOT 1.9.11 and Java
17 were downloaded there for validation; those ignored files are not committed.
Missing tools are reported explicitly, never counted as passing.

OntoCheck includes URL accessibility checks that may make network requests and
spelling checks that need NLTK resources. Full assessment can be slower than
structural validation. Its upstream metric errors remain visible in the summary.

## Existing ontology

```powershell
uv run --with-requirements requirements-quality.txt python -m src.tools.ontology_quality outputs/MY-RUN/ontology.ttl --base-iri https://example.org/my-ontology/
```

For a master with imports, supply `--imports local-imports.json`. The JSON object
maps each imported ontology IRI to an absolute local Turtle path. No HTTP imports
are fetched by the wrapper. Missing imports block reasoning and leave a record of
the incomplete scope. OntoCheck still measures the available exported graph.

For competency questions add `--questions questions.json --domain-prefixes kw`.
For a particular class-search probe add `--search-term "Solar cell"`.
Set `--output DIR` or `--timeout SECONDS` as needed.

Pipeline equivalents are `--quality-questions`, `--quality-domain-prefixes`,
`--quality-search-term` and `--quality-timeout`, for `interop`, `all` or `integrate`.
Without a question file, competency questions are explicitly `not_configured`.
Normal resume skips completed stages; use the standalone assessment command to
check existing exports without rerunning model stages.

## Scope and limitations

Domain exports contain MIREOT-style external term/ancestor extracts. Reasoning
checks the axioms actually present, plus supplied local imports. It does not prove
consistency with all axioms of full BFO, CCO or other source ontologies. The local
assessment snapshot removes resolved import declarations after assembling their
graphs so generated ontology IRIs are never fetched from the network by ROBOT.
Input files retain all imports. A successful reasoner run does not verify factual
support from papers, completeness, or correct mappings.

## Focused validation

```powershell
uv run --with rdflib --with pytest --with-requirements requirements-quality.txt python -m pytest tests/test_ontology_quality.py -q
```

Set `ROBOT_JAR` (and make Java available) to enable the real contradiction,
unsatisfiable-class, import-closure and coherent-ontology tests. Set `QUALITY_LIVE=1`
to enable the real OntoCheck test that compares returned metrics against its
installed dispatcher. Tool-independent tests cover missing tools, malformed RDF,
timeouts, per-metric errors, input preservation, and separate assessment histories.
