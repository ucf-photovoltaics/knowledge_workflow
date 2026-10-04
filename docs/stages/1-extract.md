# Stage 1: Extract (`extract`)

Turns each selected paper into a per-paper record of concepts, relations, causal claims, measurements and figure links, each relation, claim and measurement with a verbatim quote. Ingestion and PDF parsing run inside this stage. Agent: `src/agents/extraction.py`. Command: `python -m src.run extract --collection NAME [--limit N]` (or `all`).

## Inputs

- A named collection in `COLLECTIONS` (`src/config.py`): Zotero group library id and collection key.
- `TOP_N_BY_CITATIONS` (default 50) and `--limit N` (first N of the selection).

## Steps

1. **Select papers** (`run.select_papers`, `tools/zotero.py`, `tools/citations.py`). List the collection, look up citation counts (OpenCitations, then OpenAlex, then Crossref for a DOI with no positive count), rank, and keep the top N that have a PDF. A PDF comes from the zotero.org attachment, the local Zotero storage folder or a linked-file path, in that order, and is cached in `outputs/cache/pdfs`. Counts are cached with their fetch date (`outputs/cache/citations.json`) so the selection stays frozen. Papers without a PDF are passed over and listed.
2. **Parse** (`tools/pdf_parse.py`, no model). PyMuPDF text blocks; running headers and footers (identical short blocks on 3+ pages) and page numbers removed; hyphenated line breaks joined. Text is split at recognised headings; references, acknowledgements, funding, author contributions and declarations are dropped. Figure captions are kept with up to 3 sentences that cite each figure. The character reduction is recorded per paper.
3. **Chunk.** One chunk per section; sections under 1,500 characters merge forward, long ones split at sentence ends to fit the profile's `max_input_chars`. Each call also gets up to 80 labels already found in the paper (reuse them) and the captions of figures the section cites.
4. **Extract.**
   - Frontier tier: one combined call per chunk (`prompts/extraction.md`).
   - Local tier: four calls per chunk. `concepts` first; then `causal`, `relations` and `measurements`, each given the numbered concept list (plus up to 40 earlier concepts) and allowed to add `new_concepts`.
   - Relations use `is_a` plus RO/BFO/CCO-grounded predicates (part_of, has_part, composed_primarily_of, derived_from, transformation_of, has_quality, has_disposition, has_function, has_role, capable_of, has_input, has_output, input_of, output_of, participates_in, has_participant, located_in, occurs_in, adjacent_to, connected_to, precedes, measured_by, measures, is_about, regulates, realizes, correlated_with) and `related_to` as the last resort. The prompt asks explicitly for "is a", "type of", "such as" and "including" statements as `is_a`.
   - Measurements name the `property` (property, parameter or quantity) and, if the text names one, the `entity` it was measured on.
5. **Re-ask missing quotes.** Relations, causal claims and measurements whose quote has fewer than 3 words go back once, with the section text, to `prompts/extraction_evidence.md`, which returns a verbatim quote or an empty string.
6. **Merge** the chunk answers into one paper record. Ends given as phrases are resolved by label, synonym or the longest contained label; short unresolved phrases become new concepts, but unknown ids (`n14`, `c7-c8`, `f3`) never do. Leaked id prefixes are stripped from labels (`n1 (Auger recombination)` -> `Auger recombination`). Free-text types are mapped onto the 12-type enum; a later occurrence fills an empty type. A measurement attached to a non-property concept with no entity is moved to `entity` and flagged `property_missing`.
7. **Finalize.** Mention counts and sections per concept are computed by pattern matching, not by the model. Each item gets `evidence_status`:
   - `verified`: at least 80% of the quote's word 3-grams appear in the parsed paper (NFKC-normalised; quotes with "..." are checked per segment);
   - `unverified`: a quote that fails that check;
   - `unevidenced`: no usable quote after the re-ask.

## Outputs

- `papers/<zotero key>.json`: concepts, relations, causal, measurements, figures, verification counts, checks, `raw_calls` (exact model input and output, reusable as training data), compute.
- `compute_per_paper.csv`; `run.json` corpus block (selection, PDF sources, failures, corpus hash).
- Cache: `outputs/cache/extraction/<key>-<hash>.json`, keyed by model, tier, prompts, extraction code version and paper text. Re-running an unchanged paper costs no tokens.

## Checks and what they do not establish

- The 3-gram check says a quote is in the paper. It does not say the quote supports the extracted claim.
- `unevidenced` items stay in the record; downstream they never become axioms.
- `extraction_check_measurements_on_non_property`, `..._measurements_property_missing`, `..._pairs_both_relation_and_causal`, `..._new_concepts_by_pass_*` and `..._evidence_asked/filled` are counted per run.
- A paper whose extraction fails is skipped and listed in `run.json`; the run continues. A Gemini quota stop ends the run without marking the stage complete.

## Lessons behind the checks

- Small local models write their own reference ids where a label belongs; without the id guard these became concepts and later produced false cross-domain matches.
- About a quarter of quotes came back empty in local-tier runs; that is why missing quotes are re-asked and flagged rather than counted as unverified.
- Ligatures and quotes abridged with "..." failed the overlap check although they were faithful; the check now normalises both.
- Values were attached to the device rather than the property (a conductivity on "battery"); the schema now separates them.
