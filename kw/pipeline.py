# -*- coding: utf-8 -*-
"""
The pipeline - the single ordered runner. Implements the spec exactly:

    INPUT(mode) -> CONCEPTS -> MINE(LLM + REBEL) -> CONSOLIDATE
                -> ONTOLOGY -> JSON-LD -> DIAGRAM -> LoRA

Ordering invariants enforced here: JSON-LD, diagram, and LoRA run only AFTER the
ontology is built. REBEL runs together with the LLM during mining.
"""
from __future__ import annotations

import os
import glob

import pandas as pd

from kw import (config, zotero, extract, rebel, store, tagger, drawio,
                ontology, validate, lora, relations, merge)


def run(collection_id: str,
        concepts_csv: str | None = None,
        outputs_dir: str | None = None,
        emit_diagram: bool = True,
        do_lora: bool = True,
        limit: int | None = None,
        do_rebel: bool = True) -> dict:
    outputs_dir = outputs_dir or config.OUTPUTS_DIR

    # --- Step 0: input -----------------------------------------------------
    coll_map        = zotero.get_collection_map()
    id_to_name      = {v: k for k, v in coll_map.items()}
    collection_name = id_to_name.get(collection_id, collection_id)
    domain          = collection_name.lower().replace(' ', '_')
    slug            = store.collection_slug(collection_name)
    mode            = 'supervised' if concepts_csv else 'unsupervised'
    print(f'\n[{mode}] collection "{collection_name}" ({collection_id}) | model {config.MODEL}')

    papers = zotero.get_collection_with_text(collection_id, limit=limit)
    print(f'Loaded {len(papers)} papers.' + (f' (limited to {limit})' if limit else ''))
    no_text = [p['title'] for p in papers.values() if not p.get('full_text')]
    if no_text:
        print(f'[input] {len(no_text)} paper(s) had no extractable PDF text (abstract only).')
    if config.LORA_ADAPTER_PATH:
        print(f'[lora] extraction adapter configured: {config.LORA_ADAPTER_PATH}')

    out_dir  = os.path.join(outputs_dir, slug)
    os.makedirs(out_dir, exist_ok=True)
    prefix   = store.make_filename(collection_name)
    ckpt_dir = os.path.join(out_dir, '.checkpoints') if config.USE_CHECKPOINT else None

    # --- Step 1: concepts --------------------------------------------------
    if concepts_csv:                                   # supervised - skip extraction
        concept_list  = store.load_concept_list(concepts_csv)
        concept_table = None
        print(f'[concepts] supervised: {len(concept_list)} from {concepts_csv}')
    else:                                              # unsupervised - from abstracts
        print('[concepts] Step 1: extracting from abstracts...')
        concept_table = extract.build_concept_table(papers)
        concept_list  = extract.normalize_concept_list(concept_table.all_canonicals)
        print(f'[concepts] normalized to {len(concept_list)}')

    # --- Step 2: mine (LLM + REBEL together) -------------------------------
    print('[mine] Step 2: full-text mining (LLM) + REBEL triples...')
    schema_rows = extract.build_schema_rows(papers, concept_list, domain,
                                            checkpoint_dir=ckpt_dir)
    triples     = rebel.extract_corpus(papers) if do_rebel else []   # safe no-op if absent

    # --- Step 3: consolidate - normalize predicates + resolve entities -----
    merge_stats = None
    rel_cov     = None
    if triples:
        relations.normalize_triples(triples)           # T3.2 predicate -> mds vocab
        rel_cov = relations.coverage(triples)
        if config.MERGE_REBEL:
            merge.resolve(triples, concept_list)        # T3.1 entity resolution
            merge_stats = merge.stats(triples)
    extra = ''
    if triples and merge_stats:
        extra = f' (rel-vocab {rel_cov}, resolved {merge_stats["resolution_rate"]})'
    print(f'[mine] {len(schema_rows)} schema rows, {len(triples)} REBEL triples{extra}')

    # --- persist mined data (the CSV handoff the emitter consumes) ---------
    if concept_table and concept_table.rows:
        store.save_concepts_csv(concept_table, os.path.join(out_dir, f'concepts_{prefix}'))
    schema_path = os.path.join(out_dir, f'schema_{prefix}')
    store.save_schema_csv(schema_rows, concept_list, schema_path)

    # REBEL triples become part of the GraphDB repo (relations as stated in the text)
    triples_files = None
    if triples:
        triples_files = rebel.save_triples(triples, out_dir, prefix, ns=config.MDS_NS)
        print(f'[mine] REBEL triples -> {triples_files["jsonld"]}')

    # --- Step 4 -> 5: ONTOLOGY then JSON-LD (ordered) ----------------------
    print('[ontology] Step 4: OWL 2 TTL, then Step 5: JSON-LD (GraphDB repo)...')
    ontology.process_schema_file(schema_path=schema_path, outdir=outputs_dir, ttl_map={})
    ttls = sorted(glob.glob(os.path.join(out_dir, '*_onto.ttl')), key=os.path.getmtime)
    ttl_path = ttls[-1] if ttls else None

    # --- validation gate ---------------------------------------------------
    report = None
    if ttl_path:
        report = validate.evaluate(ttl_path)
        print(f'[validate] {"PASS" if report["passed"] else "CHECK"} - '
              f'alignment {report["alignment_ratio"]}, {report["classes"]} classes')

    # --- Step 5b: DIAGRAM (cemento draw.io) --------------------------------
    diagram_path = enriched_path = None
    if emit_diagram:
        print('[diagram] tagging concepts + building cemento draw.io...')
        cdf = pd.DataFrame({'concept': concept_list})
        cdf = tagger.tag_concepts(cdf)
        enriched_path = os.path.join(out_dir, f'enriched_{prefix}')
        cdf.to_csv(enriched_path, index=False)
        mx = drawio.build_drawio_xml(cdf, page_title=collection_name)
        drawio.add_template_pages(mx)                  # embed MDS-Onto + Cemento palettes
        diagram_path = os.path.join(out_dir, 'diagram_' + prefix.replace('.csv', '.drawio'))
        with open(diagram_path, 'w', encoding='utf-8') as fh:
            fh.write(drawio.serialize_drawio(mx))
        print(f'[diagram] {diagram_path}')

    # --- Step 6: LoRA (only after the ontology) ----------------------------
    lora_result = None
    if do_lora and ttl_path:
        print('[lora] Step 6: fine-tune on final ontology terms...')
        lora_result = lora.finetune(concept_list, ttl_path,
                                    schema_path=schema_path, papers=papers)

    print(f'\nDone - GraphDB repo + diagram in {out_dir}')
    return {
        'collection': collection_name, 'mode': mode, 'out_dir': out_dir,
        'concepts': concept_list, 'schema_path': schema_path,
        'n_triples': len(triples), 'rebel_triples': triples_files,
        'ttl': ttl_path, 'all_jsonld': os.path.join(out_dir, 'all.jsonld'),
        'enriched': enriched_path, 'diagram': diagram_path,
        'validation': report, 'lora': lora_result,
        'relation_coverage': rel_cov, 'merge_stats': merge_stats,
        'lora_adapter': config.LORA_ADAPTER_PATH or None,
    }
