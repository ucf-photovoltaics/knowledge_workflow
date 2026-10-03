# Implementation Plan — Zotero → Concepts → CCO/BFO Ontology

Agentic pipeline: Zotero collection → per-paper concept extraction → corpus normalization and report → BFO/CCO ontology → enrichment → interoperability → OWL2 JSON-LD and report. Must be token efficient and must report compute per paper and publication metadata per run.

## Layout
```
src/
  agents/      extraction, normalization, ontology, enrichment, interoperability (+ shared base)
  tools/       zotero, pdf_parse, llm (chat + embeddings), ledger, upper (BFO/CCO), owl (build/validate/metrics),
               reports, mds_portal (+ mds_onto_open_api.py, vendored unchanged)
  resources/   prompts/, schemas/, upper/ (bfo_cco.json = BFO 2020 + CCO terms + RO properties, menus.json = curated classes/properties/causal rules)
  config.py, run.py
outputs/
  cache/       PDFs, per-paper extraction cache (content-hash keyed)
  <run_id>/    papers/, ledger.jsonl, compute_per_paper.csv, reports, ontology.jsonld, run.json
.env           API keys only (all other settings in src/config.py)
```

## Decisions
- **LLM runtime:** provider-agnostic. Named profiles in `src/config.py` (ollama, gemini, deepseek, groq, anthropic), switched with `LLM_PROFILE`. `openai` covers any OpenAI-compatible endpoint; `anthropic` uses the Messages API with the system prompt cached. Optional model override per agent (`AGENT_MODELS`).
- **Zotero:** web API via pyzotero, with named focus collections that can span group libraries. A PDF is taken from the zotero.org download, the local Zotero storage folder, or the linked-file path, in that order, and cached in `outputs/cache/pdfs`.
- **PDF parsing:** PyMuPDF. Deterministic, no LLM.
- **Corpus selection:** each collection is cut to its `TOP_N_BY_CITATIONS` (50) most-cited papers that have a PDF. Citation counts come from the OpenCitations Index (open CC0 data, no key needed). A DOI it has no positive count for falls back to OpenAlex, then Crossref, and each count records its source. Counts are cached with their fetch date (`outputs/cache/citations.json`) so the selection stays frozen, and `run.json` records the selected keys, their counts and sources, and the papers passed over for having no PDF.
- **Figures:** captions plus citing sentences, text only (no vision).
- **Output format:** OWL2 as RDF, serialized as JSON-LD.
- **Reasoner:** none for now. Validation is structural only.

## Stages and agents
0. **Ingest** (tools, no LLM)
   - Fetch the collection's metadata (key, title, DOI, year, authors) and download the PDFs.
   - Parse each PDF into sections.
   - Drop references, acknowledgements, funding and declarations, plus repeated page headers and footers.
   - Pull out figure captions, and the sentences that cite each figure (`Fig. N`).
   - Record the character reduction as evidence of token savings.
1. **Extraction agent** (once per section)
   - One call per section. Short sections are merged forward; long ones are split at sentence ends.
   - Passes follow the pipeline tier (the profile's `tier`, override `PIPELINE_TIER`; `EXTRACTION_PASSES`). **Local:** four narrow calls per section. Concepts come first; then causal, relations and measurements, each given the section's numbered concept list (plus up to 40 earlier concepts) and allowed to add `new_concepts`. **Frontier:** one combined call.
   - Evidence check: each relation, causal claim and measurement is marked `verified` when at least 80% of its quote's word 3-grams appear in the paper. The share per type is in `eval_runs.csv`.
   - Each call sees only the figures that section cites, plus the labels already found earlier in the paper, which the model reuses.
   - The prompt is recall-oriented and faithful: materials, device parts, equipment, process steps, process parameters, measured properties, mechanisms/defects, methods, conditions. Causal claims are the priority: parameter→property, stressor→degradation, mechanism chains split into links.
   - Returns concepts, relations, causal edges, **measurements** (value, unit, condition, verbatim evidence) and figure links.
   - Every call's exact input and output is saved (`raw_calls`), so frontier-model runs can later become LoRA training data for the local model (`lora-data --distill`).
   - Mention counts and sections are computed deterministically.
2. **Normalization agent** (whole corpus)
   - Embeddings cluster synonyms, and the LLM only settles the ambiguous clusters.
   - Assigns canonical labels, keeping the rest as altLabels.
   - Importance score: paper frequency, total mentions, centrality in the relation graph, causal in/out degree.
   - Causal order: rank each concept in the merged causal graph (topological rank, with cycles reported).
   - Output: **corpus report** (concepts ranked by importance, causal chains, figure coverage).
3. **Ontology agent**
   - Input: the canonical concept list.
   - Places each concept under a curated BFO/CCO class (`resources/upper/menus.json`) or under another corpus concept (true is-a).
   - The upper-class menu and the concept index sit in the system prompt, so every batch reuses the same cached prefix.
   - Lexical heads: when the model attached a concept straight to BFO/CCO, it goes under its obvious lexical head instead ("rear AlOx passivation layer" → "passivation layer"). This applies only for the same type, a specific head and no negating or prepositional modifier, within the same BFO category, and never if it creates a cycle.
   - Deterministic repair: an invalid pick falls back to a default parent for the concept's type, is-a cycles are broken, and children of excluded concepts move up to the nearest kept ancestor. Each class gets an IRI (`ONTOLOGY_IRI` + CamelCase label).
4. **Enrichment agent**
   - The LLM writes definitions (genus + differentia), filters alt labels, picks non-causal restrictions from a menu of BFO, CCO and RO (OBO Relations Ontology) properties listed side by side (`SOURCE:label`), and proposes disjoint siblings.
   - Causal edges become restrictions deterministically, in layers so no claim is lost:
     - Local polarity property, always: influences > increases, decreases, causes, enables, prevents. `influences` is a subproperty of RO `causally related to`, with skos:closeMatch to CCO `affects`, `is cause of` or `inhibits`.
     - RO property picked from the BFO categories of the cause and effect (`causal_rules` in menus.json):
       - process → process: `causally upstream of`, with its positive or negative effect variant;
       - process → quality: `positively regulates characteristic`, `negatively regulates characteristic` or `regulates characteristic`;
       - continuant → continuant: `causally influences`;
       - anything else: `causally related to`.
     - CCO property when its process domain fits: `is cause of`, `inhibits`, `affects`.
     - Polarity is also kept as an axiom annotation.
   - Compliance checks: every restriction must trace back to an extracted relation, and the subject and target must fall under the property's BFO/CCO domain and range. Disjointness is allowed only between siblings.
   - Domain and range of the local properties = the most specific common ancestor of the classes that use them.
   - Candidate external terms, retrieved and then filtered:
     - portal searches with cleaned queries (an exact-label search, the full label, its general term, the spelled-out synonym for abbreviations) on the MDS-Onto portal and MatPortal, with BFO/CCO hits dropped;
     - local BFO/CCO classes with the same label, plus the nearest by embedding;
     - re-ranking by embedding similarity (`MAPPING` in src/config.py): label matches and candidates at or above `min_similarity` are kept, top `candidates_total`.
     - Each candidate carries `label_match`, `score`, its portal, and MDS-Onto's own study stage/domain when present.
5. **Interoperability agent**
   - The LLM commits mappings from the numbered candidates: equivalentClass, subClassOf, skos:exactMatch or skos:closeMatch. QUDT targets are downgraded to skos, since QUDT quantity kinds and units are individuals.
   - Mapping checks: exact/equivalent are kept only for label (or synonym) matches, otherwise downgraded to close; label-matched candidates the model skipped are added when similarity ≥ `strong_similarity`. Every mapping records a confidence and its source (model or label match).
   - MDS facets: every class and local property is tagged with `mds:hasStudyStage` (1–2 of the 13 study stages), `mds:hasDomain` and `mds:hasSubDomain` (MDSDom list in `resources/upper/mds_facets.json`). MDS-Onto's own facets on matched terms are passed as hints; untagged items default by concept type to the General domain. The tags are also copied into the bottom-up layer.
   - Imports only the BFO/CCO terms the ontology uses, plus their full ancestor chains (MIREOT style), from the cached `bfo_cco.json`.
   - Provenance: dcterms:source (DOI) on classes, and axiom annotations on each restriction (support, evidence quote, condition, sources).
   - Structural validation: the JSON-LD parses, every IRI resolves, there are no dangling parents or undeclared terms.
   - Emits `ontology.jsonld` and `ontology.ttl` (the same graph) and the **ontology report**. One ontology per domain run: the ontology IRI is `<ONTOLOGY_IRI><domain>`, and class IRIs share `<ONTOLOGY_IRI>` so identical concepts align across domains.

## Bottom-up literature layer (alongside the BFO/CCO ontology)
- `domain_layer.ttl` / `.jsonld` per run is a SKOS concept scheme built only from the corpus:
  - hierarchy (`skos:broader`) from extracted is_a relations plus obvious lexical heads;
  - every extracted relation and causal claim as a link plus a `kw:Claim` node with support, evidence, condition and sources, kept even when it isn't universally true;
  - every reported value as `kw:ReportedValue`;
  - `kw:ontologyClass` linking each concept to its BFO/CCO class.
- The BFO/CCO ontology is unchanged. Metrics appear in `eval_runs.csv` as `domain_layer_*`.

## LoRA adapter for the local model
- **Base model:** Qwen 3.5 9B on an A100/L4 (bf16 LoRA, about 22 GB); on a T4 the notebook trains the 2B in float32, since Qwen 3.5 cannot train in float16 and Unsloth advises against 4-bit QLoRA for it. The result is a 4-bit GGUF served locally by Ollama.
- **Training data:** `python -m src.run lora-data` builds it from the ontology suite in `LORA` (src/config.py: BFO, CCO and QUDT, with RO through the property menu). Each example uses the pipeline's own prompts and JSON schemas:
  - **category**, **parent** (ontology agent, local passes): BFO category, then the hidden parent among that category's upper classes and corpus concepts;
  - **definitions**, **synonyms**, **disjointness** (enrichment agent, local passes): gold definition, true alt labels among sibling decoys, disjoint siblings;
  - **filter**, **align** (interoperability agent, local passes): screen look-alike candidates from other ontologies, then choose the mapping relation, including no-match cases;
  - **restrict** (enrichment restrictions pass): paper-style relations between BFO/CCO classes mapped to the first menu property (BFO, CCO or RO) whose domain and range fit, with the same phrases between ill-fitting classes and vague relations as drop cases (`LORA["restrict_examples"]`);
  - **extract** (optional): `--distill RUN_ID`, runs on non-evaluation collections only.
- **Splits:** by branch (source + nearest curated upper class), so test branches are unseen. The four SWJ collections are never distilled. `dataset_card.json` records ontology file hashes and versions.
- **Training:** locally on a bf16 GPU with `src/resources/lora/train_local.py` in WSL2 (setup: `LOCAL_TRAINING.md`), or in Colab with `src/resources/lora/finetune_colab.ipynb` (uploaded inside `outputs/lora/kw_lora_upload.zip`).
- **Deploy:** `src/resources/ollama/Modelfile.lora` → `kw-qwen3.5-9b-lora-32k`, used via the `ollama-lora` profile.
- **Evaluation:** `python -m src.run lora-eval --model <name>` scores base vs adapter on the held-out split: JSON validity, parent exact/ancestor accuracy, definition similarity, restriction/synonym/disjoint/mapping P/R/F1, relation accuracy. Results go to `outputs/lora/eval_summary.csv`. The end-to-end effect shows in `eval_runs.csv`.

## Pipeline tier: split calls for local models
`tier()` = `PIPELINE_TIER` or the profile's `tier`. On the **frontier** tier each stage keeps one combined call. On the **local** tier each stage is split into single-task calls:

| Stage | Local passes | Minimal checks |
|---|---|---|
| Extraction | concepts → causal, relations, measurements (numbered concept list; `new_concepts` allowed) | evidence verified; new concepts per pass; measurements on non-property concepts; pairs that are both a relation and a causal claim |
| Normalization | synonyms; **type conflicts** (only for concepts the papers typed differently, choosing among the types they used); summary | **causal contradictions** (opposite polarity for the same cause and effect): flagged, never merged (`normalized/contradictions.json`, corpus report) |
| Ontology | BFO category (or not a class) → parent from that category's upper classes and corpus concepts | override to another category root allowed and counted; local parent from another category is replaced by the category root; missing answers fall back to the category root |
| Enrichment | definitions; synonyms; restrictions; disjointness | disjoint pairs the papers call is-a are dropped |
| Interoperability | candidate screen → mapping relation; study stage; domain/subdomain | name-matched candidates can't be screened out; partial facet answers are kept and defaulted |

All split calls are *soft*: a call that fails to return JSON twice is skipped and counted, and the run continues. Check counts appear in `eval_runs.csv` (`extraction_check_*`, `ontology_category_*`, `*_failed_*`, `interop_check_*`, `type_conflicts`, `causal_contradictions`).

## Token efficiency
- Parsing, section filtering, header dedup and mention counting are deterministic.
- Captions are truncated, and there is one call per paper unless the paper exceeds the limit.
- The system prompt and schema are fixed per agent so providers can cache them (explicit `cache_control` on Anthropic).
- Extraction results are cached by hash of (text + prompt + model), so a re-run of an unchanged paper costs 0 tokens.
- Embeddings deduplicate concepts before any LLM call.
- Output is JSON only, with compact keys and evidence quotes of 20 words or fewer.

## Reporting
- **Per call** (`ledger.jsonl`): agent, item, model, input, cached and output tokens, latency, cost (if prices are set), attempt, cache hit.
- **Per paper** (`compute_per_paper.csv`): calls, tokens, cost, LLM latency, parse time, text reduction, concept, relation, causal and figure counts.
- **Per run** (`run.json`): run id, timestamps, git commit, provider and models, Zotero library and collection, corpus hash, papers processed or skipped (no PDF), totals per stage.
- **Ontology metrics:** classes, object properties, axioms, hierarchy depth and breadth, definition coverage, imported terms by source (CCO, BFO, QUDT, IOF, PMDCO, MDS), mapping counts by type, share of classes linked to evidence (DOI, figure).
- **Across runs** (`outputs/eval_runs.csv`): one row per run, rebuilt after every stage. It covers run settings, corpus selection and citations, PDF sources and text reduction, concepts extracted, normalization and joins (lexical groups, embedding clusters, merges, compression ratio, concepts shared by 2+ papers, tiers, types, causal graph), final ontology metrics and validation, calls, tokens, latency, cost and wall time per agent and in total, tokens per paper and per final class, and the top 25 concepts.

## Build order
All five stages are built (not yet run). Next: Brent tests on 3–5 papers (`python -m src.run all --limit 5`), then on a full corpus.

## Open items
- Focus collection keys in `COLLECTIONS` (src/config.py): find them with `python -m src.run collections --library <id>`, then check each one with `python -m src.run check --collection <name>`.
- Portal acronyms for `MDS_ONTOLOGIES`. They are unverified: the portal was unreachable from the build environment.
- The MDS-Onto code falls back to a hardcoded demo API key when `MDS_API_KEY` is blank.
- Encoding causal claims as existential restrictions ("every A influences some B") is strong. Experts should review it, or it could move to annotations only.
- Refreshing BFO/CCO/RO: `python -c "from src.tools.upper import build; build()"`.
