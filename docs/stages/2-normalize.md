# Stage 2: Normalize (`normalize`)

Joins the per-paper records into one corpus vocabulary without rewriting them. Agent: `src/agents/normalization.py`. Command: `python -m src.run normalize --run-id ID`.

## Steps

1. **Clean** model output shapes (lists or dicts where a string belongs) and normalise predicate names to snake case.
2. **Lexical groups.** Labels that match after case, punctuation and plural normalisation are grouped. Extracted synonym lists are not used to join concepts: transitive synonym chains were found to collapse distinct concepts.
3. **Semantic merge.** Label embeddings (`EMBED`, default `nomic-embed-text` on Ollama) nominate clusters at cosine >= 0.85 (at most 12 terms per cluster). The model reviews each cluster and merges only true synonyms, acronyms and variants (`prompts/normalization.md`); merges must stay inside one cluster. If the embedding service fails, the stage continues with lexical groups only and records the error.
4. **Canonical concepts.** The most frequent label wins; the others become alternative labels. Definitions, evidence, papers, figures and type votes are kept. Groups that end up with the same label (a name the model gave a merged cluster can equal the label of a group it did not review) are folded into one concept, so no two concepts share a name.
5. **Type conflicts.** Concepts the papers typed differently go to the model, which must choose one of the types the papers used.
6. **Edges.** Relations and causal claims are joined by (subject, predicate, object) and (cause, effect, polarity), with support (paper count), conditions and up to two evidence entries each (`paper`, `text`, `verified`, `status`). Measurements keep their property and entity, mapped to canonical ids.
7. **Contradictions.** Opposite polarity for the same cause and effect is flagged, never merged (`normalized/contradictions.json`).
8. **Importance.** Score = 0.35 paper frequency + 0.25 log mentions + 0.20 PageRank in the relation and causal graph + 0.10 causal degree + 0.10 figure links (each normalised); tiers core (top 10%), major (next 20%), minor.
9. **Causal order.** Topological rank in the merged causal graph, cycles reported.
10. **Corpus summary** (one model call) and `corpus_report.md`.

## Outputs

`normalized/{concepts,relations,causal,measurements,contradictions,causal_order,summary}.json`, `normalized/corpus_stats.json`, `corpus_report.md`.

## Checks and limits

- `semantic_merges`, `candidate_clusters`, `type_conflicts`, `types_settled_by_model`, `causal_contradictions`, `concepts_in_2plus_papers` and row coverage of the type pass are reported.
- Merging is deliberately conservative. A low share of concepts in two or more papers can mean the literature is diverse or that merges were missed; the run alone does not tell them apart.
