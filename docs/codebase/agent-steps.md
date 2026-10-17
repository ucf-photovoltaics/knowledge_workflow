# Agent operational step reference

Author: Brent Thompson <brent.thompson@ucf.edu>

Start from `LiteratureToOntologyWorkflow` in the RDF graph. Examples are templates, statically checked against entry points but never executed during documentation generation. Resolve every uppercase binding before execution. Use only one execution mode per run.

## preflight: Check environment and sources

Verify collection names, model and embeddings, accessible PDFs and ontology services. This command makes provider/network checks; it is not a no-network validator.

Prerequisites: store

Implementations:
- `src/run.py:check`

Inputs:
- `configured collection; credentials in local environment`

Outputs:
- `preflight observations in terminal`

cli prerequisites: store

cli argument vector:
```json
["uv", "run", "--with-requirements", "requirements.txt", "python", "-m", "src.run", "check", "--collection", "COLLECTION"]
```

Completion: Read every printed check and require the final ready message with no [FAIL] lines. src.run.check catches check failures and does not guarantee a nonzero exit code; exit status alone is insufficient.

Recovery: Resolve each failed source/model/provider/store check, then rerun check and inspect its printed outcome. Exit code alone is insufficient; this command does not create a per-run completion record.

Effects: Calls real chat, embedding and portal services and downloads/ranks collection PDFs into shared cache. Full preflight includes ontology-store readiness; build the store first if missing.

Required saved products: 

Conditions:
- Use human-authorized input sources, runtime and output scope. An ontology template is not a grant of permission.
- CLI reads root environment/.env; wrapper reads dashboard private settings. Check required provider/model availability without exposing values.
- Establish that no running job uses shared assets before store writes; do not infer process ownership from logs.

## store: Prepare ontology store

Build once before placement. This writes the shared store, downloads sources and may embed terms; do not rebuild or upgrade it during active runs.

Prerequisites: 

Implementations:
- `src/run.py:ontologies`
- `src/tools/ontostore.py:build`
- `src/tools/ontostore.py:require`

Inputs:
- `configured ontology sources`

Outputs:
- `configured ONTOLOGY_STORE (default outputs/cache/ontology_store/)`

cli prerequisites: 

cli argument vector:
```json
["uv", "run", "--with-requirements", "requirements.txt", "python", "-m", "src.run", "ontologies", "build"]
```

Completion: Confirm the configured ontology-store DB and manifest exist and inspect ontologies status; build/require implementations define readiness. Do not rebuild an already-valid active store.

Recovery: Inspect the configured store status, DB and manifest first. Repair/build only if readiness is missing and no active job uses shared assets; do not rebuild an already-valid store. A build is not a per-domain stage restart.

Effects: Downloads ontology sources, writes the configured shared ontology store and may call embedding providers. Establish exclusive safe write scope before building.

Required saved products: 

Conditions:
- Use human-authorized input sources, runtime and output scope. An ontology template is not a grant of permission.
- CLI reads root environment/.env; wrapper reads dashboard private settings. Check required provider/model availability without exposing values.
- Establish that no running job uses shared assets before store writes; do not infer process ownership from logs.

## ingest: Select literature across collections

Select personal/group libraries permitted by the key; expand descendants, deduplicate DOI/membership, rank citations across the entire domain, and skip unavailable PDFs. Missing citation counts rank last.

Prerequisites: preflight

Implementations:
- `dpv_dashboard/worker.py:ingest`
- `dpv_dashboard/zotero.py:Libraries.expand`
- `dpv_dashboard/zotero.py:deduplicate`
- `src/run.py:select_papers`

Inputs:
- `project.json domains[].collections and domains[].limit`

Outputs:
- `ingestion.json`
- `ingestion.partial.json`
- `outputs/dashboard/cache/pdfs/`

wrapper prerequisites: 

wrapper argument vector:
```json
["outputs/dashboard/.venv/Scripts/python.exe", "-m", "dpv_dashboard.worker", "PROJECT_ID", "stage", "--domain", "DOMAIN_ID", "--stage", "ingest"]
```

Completion: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: CLI single-stage commands reattempt that stage in the same run; all --run-id skips recorded completion. Dashboard stage skips completed stages; restart creates a new attempt and preserves upstream/history. Inspect failures and do not mix these semantics.

Effects: Writes output artifacts; may call models/providers and shared read caches. Do not execute a command template without resolving scope and credentials.

Required saved products: `ingestion.json`

Conditions:
- Use human-authorized input sources, runtime and output scope. An ontology template is not a grant of permission.
- CLI reads root environment/.env; wrapper reads dashboard private settings. Check required provider/model availability without exposing values.
- CLI COLLECTION must exist in src.config.COLLECTIONS. Wrapper PROJECT_ID and DOMAIN_ID must exist with real accessible collection selections. Do not substitute one mode for another.

## parse: Parse PDFs and prepare text windows

Retain captions and source pages, remove recurring headers/reference sections, save PDF hashes and chunk windows. Chunk windows are temporary inputs, not separate paper ontologies.

Prerequisites: ingest

Implementations:
- `dpv_dashboard/worker.py:parse`
- `src/tools/pdf_parse.py:parse`
- `src/agents/extraction.py:ExtractionAgent._chunks`

Inputs:
- `ingestion.json`
- `selected accessible PDFs`

Outputs:
- `parsed/*.json`

wrapper prerequisites: ingest

wrapper argument vector:
```json
["outputs/dashboard/.venv/Scripts/python.exe", "-m", "dpv_dashboard.worker", "PROJECT_ID", "stage", "--domain", "DOMAIN_ID", "--stage", "parse"]
```

Completion: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: CLI single-stage commands reattempt that stage in the same run; all --run-id skips recorded completion. Dashboard stage skips completed stages; restart creates a new attempt and preserves upstream/history. Inspect failures and do not mix these semantics.

Effects: Writes output artifacts; may call models/providers and shared read caches. Do not execute a command template without resolving scope and credentials.

Required saved products: `parsed/*.json`

Conditions:
- Use human-authorized input sources, runtime and output scope. An ontology template is not a grant of permission.
- CLI reads root environment/.env; wrapper reads dashboard private settings. Check required provider/model availability without exposing values.
- CLI COLLECTION must exist in src.config.COLLECTIONS. Wrapper PROJECT_ID and DOMAIN_ID must exist with real accessible collection selections. Do not substitute one mode for another.

## extract: Extract evidence-backed paper records

One reconciled record per paper: concepts, relations, causal claims, measurements, quotes, figures and verification. CLI extract combines ingestion, parsing and extraction; do not invoke it separately for the first two UI steps.

Prerequisites: parse

Implementations:
- `src/run.py:extract`
- `src/agents/extraction.py:ExtractionAgent.run`

Inputs:
- `ingestion.json`
- `parsed/*.json`

Outputs:
- `papers/*.json`
- `compute_per_paper.csv`
- `ontology/uncertain.json`

cli prerequisites: preflight

cli argument vector:
```json
["uv", "run", "--with-requirements", "requirements.txt", "python", "-m", "src.run", "extract", "--collection", "COLLECTION", "--run-id", "RUN_ID", "--limit", "15", "--no-figures"]
```

wrapper prerequisites: parse

wrapper argument vector:
```json
["outputs/dashboard/.venv/Scripts/python.exe", "-m", "dpv_dashboard.worker", "PROJECT_ID", "stage", "--domain", "DOMAIN_ID", "--stage", "extract"]
```

Completion: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: CLI single-stage commands reattempt that stage in the same run; all --run-id skips recorded completion. Dashboard stage skips completed stages; restart creates a new attempt and preserves upstream/history. Inspect failures and do not mix these semantics.

Effects: Writes output artifacts; may call models/providers and shared read caches. Do not execute a command template without resolving scope and credentials.

Required saved products: `papers/*.json`

Conditions:
- Use human-authorized input sources, runtime and output scope. An ontology template is not a grant of permission.
- CLI reads root environment/.env; wrapper reads dashboard private settings. Check required provider/model availability without exposing values.
- CLI COLLECTION must exist in src.config.COLLECTIONS. Wrapper PROJECT_ID and DOMAIN_ID must exist with real accessible collection selections. Do not substitute one mode for another.

## normalize: Consolidate vocabulary across papers

Canonicalize terms and reviewed aliases, merge claims and rank importance. New runs persist exact paper-local original-to-canonical identities and per-label sources. Older runs without the sidecar retain reconstructed or ambiguous dashboard links.

Prerequisites: extract

Implementations:
- `src/run.py:normalize`
- `src/agents/normalization.py:NormalizationAgent.run`

Inputs:
- `papers/*.json`

Outputs:
- `normalized/concepts.json`
- `normalized/relations.json`
- `normalized/causal.json`
- `normalized/measurements.json`
- `normalized/contradictions.json`
- `normalized/corpus_stats.json`
- `corpus_report.md`
- `normalized/concept_lineage.json`

cli prerequisites: extract

cli argument vector:
```json
["uv", "run", "--with-requirements", "requirements.txt", "python", "-m", "src.run", "normalize", "--run-id", "RUN_ID", "--no-figures"]
```

wrapper prerequisites: extract

wrapper argument vector:
```json
["outputs/dashboard/.venv/Scripts/python.exe", "-m", "dpv_dashboard.worker", "PROJECT_ID", "stage", "--domain", "DOMAIN_ID", "--stage", "normalize"]
```

Completion: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: CLI single-stage commands reattempt that stage in the same run; all --run-id skips recorded completion. Dashboard stage skips completed stages; restart creates a new attempt and preserves upstream/history. Inspect failures and do not mix these semantics.

Effects: Writes output artifacts; may call models/providers and shared read caches. Do not execute a command template without resolving scope and credentials.

Required saved products: `normalized/concepts.json`, `normalized/relations.json`, `normalized/causal.json`, `normalized/measurements.json`, `normalized/contradictions.json`, `normalized/causal_order.json`, `normalized/summary.json`, `normalized/corpus_stats.json`

Conditions:
- Use human-authorized input sources, runtime and output scope. An ontology template is not a grant of permission.
- CLI reads root environment/.env; wrapper reads dashboard private settings. Check required provider/model availability without exposing values.
- CLI COLLECTION must exist in src.config.COLLECTIONS. Wrapper PROJECT_ID and DOMAIN_ID must exist with real accessible collection selections. Do not substitute one mode for another.

## ontology: Place canonical concepts

Place under BFO/CCO or suitable existing/corpus parents, assign stable domain IRIs, check cycles/categories. Distinguish excluded concepts, default parents and review flags from reviewed placements.

Prerequisites: normalize, store

Implementations:
- `src/run.py:ontology`
- `src/agents/ontology.py:OntologyAgent.run`

Inputs:
- `normalized/concepts.json`
- `normalized/relations.json`

Outputs:
- `ontology/classes.json`
- `ontology/review_issues.json`

cli prerequisites: normalize, store

cli argument vector:
```json
["uv", "run", "--with-requirements", "requirements.txt", "python", "-m", "src.run", "ontology", "--run-id", "RUN_ID", "--no-figures"]
```

wrapper prerequisites: normalize

wrapper argument vector:
```json
["outputs/dashboard/.venv/Scripts/python.exe", "-m", "dpv_dashboard.worker", "PROJECT_ID", "stage", "--domain", "DOMAIN_ID", "--stage", "ontology"]
```

Completion: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: CLI single-stage commands reattempt that stage in the same run; all --run-id skips recorded completion. Dashboard stage skips completed stages; restart creates a new attempt and preserves upstream/history. Inspect failures and do not mix these semantics.

Effects: Writes output artifacts; may call models/providers and shared read caches. Do not execute a command template without resolving scope and credentials.

Required saved products: `ontology/classes.json`

Conditions:
- Use human-authorized input sources, runtime and output scope. An ontology template is not a grant of permission.
- CLI reads root environment/.env; wrapper reads dashboard private settings. Check required provider/model availability without exposing values.
- CLI COLLECTION must exist in src.config.COLLECTIONS. Wrapper PROJECT_ID and DOMAIN_ID must exist with real accessible collection selections. Do not substitute one mode for another.
- Read the current src.tools.ontostore availability/require contract. A full CLI preflight requires the store. Wrapper uses the prebuilt shared store; do not rebuild it during active runs.

## enrich: Add definitions and formal relationships

Preserve definition sources/status, evidence restrictions, disjointness and rejected candidates. Generated or draft definitions are not authoritative; external candidates are not accepted mappings.

Prerequisites: ontology

Implementations:
- `src/run.py:enrich`
- `src/agents/enrichment.py:EnrichmentAgent.run`

Inputs:
- `ontology/classes.json`
- `normalized/relations.json`
- `normalized/causal.json`

Outputs:
- `ontology/enriched.json`
- `ontology/properties.json`
- `ontology/materials_project.json`
- `ontology/review_issues.json`
- `ontology/cross_domain_candidates.json`

cli prerequisites: ontology

cli argument vector:
```json
["uv", "run", "--with-requirements", "requirements.txt", "python", "-m", "src.run", "enrich", "--run-id", "RUN_ID", "--no-figures"]
```

wrapper prerequisites: ontology

wrapper argument vector:
```json
["outputs/dashboard/.venv/Scripts/python.exe", "-m", "dpv_dashboard.worker", "PROJECT_ID", "stage", "--domain", "DOMAIN_ID", "--stage", "enrich"]
```

Completion: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: CLI single-stage commands reattempt that stage in the same run; all --run-id skips recorded completion. Dashboard stage skips completed stages; restart creates a new attempt and preserves upstream/history. Inspect failures and do not mix these semantics.

Effects: Writes output artifacts; may call models/providers and shared read caches. Do not execute a command template without resolving scope and credentials.

Required saved products: `ontology/enriched.json`, `ontology/properties.json`

Conditions:
- Use human-authorized input sources, runtime and output scope. An ontology template is not a grant of permission.
- CLI reads root environment/.env; wrapper reads dashboard private settings. Check required provider/model availability without exposing values.
- CLI COLLECTION must exist in src.config.COLLECTIONS. Wrapper PROJECT_ID and DOMAIN_ID must exist with real accessible collection selections. Do not substitute one mode for another.
- Read the current src.tools.ontostore availability/require contract. A full CLI preflight requires the store. Wrapper uses the prebuilt shared store; do not rebuild it during active runs.

## interop: Map, export and validate domain layers

Export formal OWL classes separately from literature claims. Quote matches and structural validity do not establish semantic correctness. Review mapping category compatibility, confidence and evidence.

Prerequisites: enrich

Implementations:
- `src/run.py:interop`
- `src/agents/interoperability.py:InteroperabilityAgent.run`
- `src/tools/bottomup.py:build`
- `src/tools/owl.py:validate`

Inputs:
- `ontology/enriched.json`
- `ontology/properties.json`
- `papers/*.json`
- `normalized/*.json`

Outputs:
- `ontology.ttl`
- `ontology.jsonld`
- `domain_layer.ttl`
- `domain_layer.jsonld`
- `ontology/mappings.json`
- `ontology/imported_definitions.json`
- `ontology/facets.json`
- `ontology/validation.json`
- `ontology/metrics.json`
- `ontology_report.md`

cli prerequisites: enrich

cli argument vector:
```json
["uv", "run", "--with-requirements", "requirements.txt", "python", "-m", "src.run", "interop", "--run-id", "RUN_ID", "--no-figures"]
```

wrapper prerequisites: enrich

wrapper argument vector:
```json
["outputs/dashboard/.venv/Scripts/python.exe", "-m", "dpv_dashboard.worker", "PROJECT_ID", "stage", "--domain", "DOMAIN_ID", "--stage", "interop"]
```

Completion: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: CLI single-stage commands reattempt that stage in the same run; all --run-id skips recorded completion. Dashboard stage skips completed stages; restart creates a new attempt and preserves upstream/history. Inspect failures and do not mix these semantics.

Effects: Writes output artifacts; may call models/providers and shared read caches. Do not execute a command template without resolving scope and credentials.

Required saved products: `ontology.ttl`, `ontology.jsonld`, `domain_layer.ttl`, `domain_layer.jsonld`, `ontology/mappings.json`, `ontology/validation.json`

Conditions:
- Use human-authorized input sources, runtime and output scope. An ontology template is not a grant of permission.
- CLI reads root environment/.env; wrapper reads dashboard private settings. Check required provider/model availability without exposing values.
- CLI COLLECTION must exist in src.config.COLLECTIONS. Wrapper PROJECT_ID and DOMAIN_ID must exist with real accessible collection selections. Do not substitute one mode for another.
- Read the current src.tools.ontostore availability/require contract. A full CLI preflight requires the store. Wrapper uses the prebuilt shared store; do not rebuild it during active runs.

## integrate: Integrate completed domain ontologies

Use explicit selected runs from distinct domains; default latest-run selection can mix historical runs. Master imports formal graphs; merged output unions them. Claims remain separate source-domain layers. At least two successful distinct domains are required.

Prerequisites: interop

Implementations:
- `src/run.py:integrate`
- `src/agents/integration.py:IntegrationAgent.run`
- `src/tools/integration.py:select_runs`
- `src/tools/integration.py:build_master`
- `src/tools/integration.py:merge`
- `src/tools/integration.py:validate`

Inputs:
- `at least two explicit completed domain runs with ontology.ttl, run.json and ontology/enriched.json`

Outputs:
- `integration.json`
- `mappings.json`
- `bridge_concepts.json`
- `candidates.json`
- `validation.json`
- `integration_report.md`
- `<domains>.ttl`
- `<domains>.jsonld`
- `<domains>_merged.ttl`

cli prerequisites: interop

cli argument vector:
```json
["uv", "run", "--with-requirements", "requirements.txt", "python", "-m", "src.run", "integrate", "--runs", "DOMAIN_A_RUN_ID", "DOMAIN_B_RUN_ID", "--run-id", "INTEGRATION_RUN_ID", "--no-figures"]
```

wrapper prerequisites: interop

wrapper argument vector:
```json
["outputs/dashboard/.venv/Scripts/python.exe", "-m", "dpv_dashboard.worker", "PROJECT_ID", "stage", "--stage", "integrate"]
```

Completion: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: CLI single-stage commands reattempt that stage in the same run; all --run-id skips recorded completion. Dashboard stage skips completed stages; restart creates a new attempt and preserves upstream/history. Inspect failures and do not mix these semantics.

Effects: Writes output artifacts; may call models/providers and shared read caches. Do not execute a command template without resolving scope and credentials.

Required saved products: `integration.json`, `mappings.json`, `bridge_concepts.json`, `candidates.json`, `validation.json`

Conditions:
- Use human-authorized input sources, runtime and output scope. An ontology template is not a grant of permission.
- CLI reads root environment/.env; wrapper reads dashboard private settings. Check required provider/model availability without exposing values.
- CLI COLLECTION must exist in src.config.COLLECTIONS. Wrapper PROJECT_ID and DOMAIN_ID must exist with real accessible collection selections. Do not substitute one mode for another.
- Select at least two distinct-domain run IDs with recorded interop, formal ontology and enriched classes; inspect failed papers and validation independently.

## reports: Produce reports and figures

Reports can run after one domain interop; integration is optional, not a prerequisite. Plot failures/skips must be read from index.md/report messages; successful command completion does not mean every plot exists.

Prerequisites: interop

Implementations:
- `src/figures.py:build`
- `src/figures.py:main`

Inputs:
- `explicit completed run IDs and optional integration inputs`

Outputs:
- `report.html`
- `report.md`
- `index.md`
- `*.png`
- `*.pdf`
- `*.csv`

cli prerequisites: interop

cli argument vector:
```json
["uv", "run", "--with-requirements", "requirements.txt", "python", "-m", "src.figures", "--runs", "RUN_ID", "--out", "outputs/review-RUN_ID", "--title", "Domain literature review"]
```

wrapper prerequisites: interop

wrapper argument vector:
```json
["outputs/dashboard/.venv/Scripts/python.exe", "-m", "dpv_dashboard.worker", "PROJECT_ID", "stage", "--stage", "reports"]
```

Completion: Confirm expected artifacts are parseable and inspect the saved stage/error records. Review content; file presence alone is not completion.

Recovery: CLI single-stage commands reattempt that stage in the same run; all --run-id skips recorded completion. Dashboard stage skips completed stages; restart creates a new attempt and preserves upstream/history. Inspect failures and do not mix these semantics.

Effects: Writes output artifacts; may call models/providers and shared read caches. Do not execute a command template without resolving scope and credentials.

Required saved products: `report.html`, `report.md`, `index.md`

Conditions:
- Use human-authorized input sources, runtime and output scope. An ontology template is not a grant of permission.
- CLI reads root environment/.env; wrapper reads dashboard private settings. Check required provider/model availability without exposing values.
- CLI COLLECTION must exist in src.config.COLLECTIONS. Wrapper PROJECT_ID and DOMAIN_ID must exist with real accessible collection selections. Do not substitute one mode for another.
- Select the exact intended completed run IDs; reports do not require integration.

