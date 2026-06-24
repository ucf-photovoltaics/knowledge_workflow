# Project Instructions — Knowledge-Workflow Ontology Extension

Use these as the project's operating instructions (e.g., Claude project instructions
or a CONTRIBUTING-style guide for the pipeline). Goal: every run turns curated domain
papers into a committee-ready OWL 2 ontology + JSON-LD, grounded in MDS-Onto/CCO/BFO.

> The contract below is implemented in the `kw/` package. Where it refers to "existing
> agents", those are now the `kw/extract.py`, `kw/tagger.py`, `kw/ontology.py`, and
> `kw/pipeline.py` modules. See [ARCHITECTURE.md](ARCHITECTURE.md) for the module map.

## Pipeline contract
1. **Ingest.** Pull the Zotero collection. Use **abstracts** to sketch scope and pick
   salient papers; use **full text** for extraction.
2. **Extract in parallel.**
   - LLM agents (`kw/extract.py`: discovery, normalization, schema mining; `kw/tagger.py`)
     produce concepts, terms, and the schema.
   - **REBEL** runs alongside and emits flat S-P-O triples *as stated in the paper*.
3. **Merge by entity resolution.** Reconcile REBEL triples with LLM concepts so a thing
   named in prose and in a relation becomes **one node / one URI**. Never blind-union.
4. **Ground.** Map every class/relation to MDS-Onto (`mds:`), then CCO/BFO where MDS
   lacks a parent. Record the alignment. Extend beyond MDS-Onto when the domain needs it.
5. **Emit.** Write `{domain}_onto.ttl` (OWL 2 DL) and `{domain}_instances.jsonld` from
   the same raw extraction.
6. **Validate (gate).** Run a reasoner (HermiT/ELK) for consistency, OOPS! for pitfalls,
   and compute % of classes aligned to BFO/CCO/MDS. A run is not "done" until these pass.
7. **Publish.** Push ontology + JSON-LD to the GitHub repo; load into the GraphDB sandbox.

## Hard rules
- **Reproducibility.** Pin model name + version and the random seed; log the routing
  decision and tool calls for every run.
- **Provenance.** Every asserted triple records its source paper + text span, the tool
  that produced it, and a confidence. Low-confidence items go to a review queue, not the graph.
- **Standards.** Output must be valid OWL 2 DL and interoperable with BFO/CCO/MDS-Onto.
  Namespaces: `bfo:` `http://purl.obolibrary.org/obo/BFO_`, `mds:`
  `https://cwrusdle.bitbucket.io/mds#`, plus `cco:` for the Common Core Ontologies.
- **Structure vs meaning.** SHACL/OOPS! check structure; the OWL reasoner checks logical
  consistency. Both are required and are not substitutes for each other.

## LoRA learning loop (stretch)
- Train on `(paper text → ontology-grounded structure)` pairs seeded from MDS-Onto and
  prior pipeline runs.
- Pin the **LoRA adapter hash** and the **base-model version** per run.
- Purpose: over successive runs, reuse known terms/ontologies to ingest new domains faster.
- If training data is thin before the deadline, ship the design + a small POC and treat
  full training as future work.

## Definition of done (per run)
A domain ontology that (a) loads in Protégé/GraphDB, (b) passes the reasoner with no
unsatisfiable classes, (c) clears OOPS! critical pitfalls, (d) hits the alignment target
to BFO/CCO/MDS, and (e) is pushed to GitHub with its JSON-LD instances.
