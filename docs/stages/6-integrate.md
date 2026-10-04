# Stage 6: Cross-domain integration (`integrate`)

Runs after the domain runs. Maps the domain ontologies of one run set to each other in a master ontology, without changing any of them. Agent: `src/agents/integration.py`; graph, validation and report `tools/integration.py`. Command:

```powershell
python -m src.run integrate --collections tea reliability si-topcon [--runs ID ...] [--outputs DIR] [--run-id NAME]
```

## Inputs

One run per domain that completed `interop`. By default the newest such run per collection in `INTEGRATION["collections"]`, preferring the current workflow revision; a domain with no completed run is left out and noted; runs from different revisions are noted. Pass `--collections` to limit the set, `--runs` to name runs.

## Steps

1. **Load** each run's `enriched.json` (live classes, BFO category, parent label, definition) and `ontology.ttl` (its ontology IRI and labels). Labels that are leaked model ids or only parentheses are skipped.
2. **Candidates** (deterministic): same normalised label (`label`) or label-synonym match (`synonym`) across two domains; a class IRI two domains already share (`shared_iri`, runs from before domain-scoped IRIs); mutual nearest neighbours by label embedding at cosine >= `min_similarity` (default 0.80). Ordered label > synonym > embedding, capped at `max_model_pairs` (default 1,500); the rest are listed unreviewed.
3. **Decision.** The model labels each pair equivalent, exact, close, broader, narrower or none (`prompts/integration.md`), seeing both labels, domains, BFO kinds, parents and definitions. Rows left out are retried once.
4. **Checks.**
   - `owl:equivalentClass` only for same-label pairs in the same BFO category, and never when the equivalence cluster would hold two classes of one domain; otherwise exact (names match) or close.
   - Exact requires a label or synonym match, else close.
   - Unanswered same-label, same-category pairs are added as exact (`label_match`).
   - Broader and narrower become `skos:narrowMatch` and `skos:broadMatch`; no cross-domain `rdfs:subClassOf` is asserted.
5. **Bridge concepts.** Connected components of equivalent, exact and shared-IRI mappings that span two or more domains.

## Outputs

`outputs/integration-<id>/`: `master.ttl`/`master.jsonld` (owl:imports of each domain ontology plus the mapping axioms, each with source, candidate kind, confidence, similarity and any downgrade), `master_merged.ttl` (domain graphs plus master), `mappings.json`, `candidates.json`, `bridge_concepts.json`, `validation.json`, `integration.json`, `integration_report.md`, `ledger.jsonl`, `calls.jsonl`. One row per integration in `outputs/eval_integrations.csv`.

## Checks and limits

- Validation: JSON-LD round trip, mapped classes declared in their domain ontology, no within-domain mappings, no equivalence cluster joining two classes of one domain, no subclass cycle once equivalent classes are identified.
- Mapping correctness is not established by these checks; mappings are candidates for expert confirmation.
- Integrating runs that were not produced together (an older run picked because the newest failed) mixes code versions; the report lists each input run and revision so this is visible.
