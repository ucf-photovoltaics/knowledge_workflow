# -*- coding: utf-8 -*-
"""
Orchestrator agent.

Coordinates the full two-pipeline knowledge workflow:

  Pipeline A — Extraction  (V5 logic)
    1. fetch_papers       — pull papers + PDFs from Zotero
    2. extract_concepts   — Phase 1: per-paper concept extraction
    3. normalize          — deduplicate raw concept labels
    4. build_schema       — Phase 2: wide-format schema population
    5. save_extraction    — write concepts_*.csv + schema_*.csv

  Pipeline B — Enrichment  (V6 logic)
    6. tag_concepts       — assign MDS-Onto study stage + supply chain level
    7. build_diagram      — generate draw.io concept-map with library pages
    8. save_enrichment    — write enriched_*.csv + diagram_*.drawio

run_extraction(collection_id)  — run Pipeline A only
run_enrichment(csv_path)       — run Pipeline B on an existing concepts CSV
run_full(collection_id)        — run A then B end-to-end
"""

import os
import time
import pandas as pd
from datetime import datetime

from src.config import (
    MODEL, RATE_LIMIT_DELAY,
    USE_CSV_CONCEPTS, CONCEPTS_CSV_PATH, CONCEPTS_COLUMN,
    TOP_N_PER_PAPER, OUTPUTS_DIR, SCHEMAS_DIR,
)

# Agents
from src.agents.extractor     import build_concept_table
from src.agents.normalizer    import normalize_concept_list
from src.agents.schema_builder import build_schema_rows
from src.agents.tagger         import tag_concepts

# Tools
from src.tools.zotero_client  import get_collection_map, get_collection_with_text
from src.tools.csv_writer     import (
    make_filename, find_latest_file, collection_slug,
    save_concepts_csv, save_schema_csv, load_concepts,
)
from src.tools.drawio_builder import (
    build_drawio_xml, add_template_pages, serialize_drawio,
)


# ---------------------------------------------------------------------------
# Pipeline A — Extraction
# ---------------------------------------------------------------------------

def run_extraction(collection_id: str) -> dict:
    """
    Run the full extraction pipeline (Phase 1 + normalization + Phase 2).

    Returns a result dict with keys:
        collection_name, domain, papers, normalized_concepts,
        concept_table, schema_rows,
        concepts_file (path), schema_file (path)
    """
    print(f'\nModel: {MODEL}')

    # 1. Resolve collection name
    coll_map  = get_collection_map()
    id_to_name = {v: k for k, v in coll_map.items()}
    collection_name = id_to_name.get(collection_id, collection_id)
    domain          = collection_name.lower().replace(' ', '_')
    print(f'\nCollection: "{collection_name}" (id: {collection_id})')

    # 2. Fetch papers
    papers = get_collection_with_text(collection_id)
    print(f'Loaded {len(papers)} papers.')

    missing_pdf = [p['title'] for p in papers.values() if not p['full_text']]
    if missing_pdf:
        print(f'\n{len(missing_pdf)} papers without PDF (will use abstract for Phase 2):')
        for t in missing_pdf:
            print(f'  - {t}')

    # 3. Concept list: extract fresh or load from existing CSV
    if USE_CSV_CONCEPTS and CONCEPTS_CSV_PATH:
        print(f'\n[Concepts] Loading from CSV: {CONCEPTS_CSV_PATH}')
        df_reuse = pd.read_csv(CONCEPTS_CSV_PATH)
        normalized_concepts = (
            df_reuse[CONCEPTS_COLUMN].dropna().str.strip().str.lower().tolist()
        )
        print(f'  Loaded {len(normalized_concepts)} concepts.')
        concept_table = None
    else:
        # Phase 1
        print(f'\n[Phase 1] Extracting concepts ({TOP_N_PER_PAPER}/paper)…')
        concept_table = build_concept_table(papers, top_n=TOP_N_PER_PAPER)
        all_canonicals = concept_table.all_canonicals
        print(f'  {len(concept_table.rows)} concept-paper pairs extracted.')
        print(f'  {len(set(all_canonicals))} unique raw labels.')

        # Normalization
        print(f'\n[Normalization] Normalizing concept list…')
        time.sleep(RATE_LIMIT_DELAY)
        normalized_concepts = normalize_concept_list(all_canonicals)
        print(f'  Normalized to {len(normalized_concepts)} concepts.')
        for c in normalized_concepts[:10]:
            print(f'    - {c}')
        if len(normalized_concepts) > 10:
            print(f'    … and {len(normalized_concepts) - 10} more')

    # 4. Phase 2 — schema population
    print(f'\n[Phase 2] Building schema ({len(normalized_concepts)} columns)…')
    schema_rows = build_schema_rows(papers, normalized_concepts, domain)

    # 5. Save outputs
    slug    = collection_slug(collection_name)
    out_dir = os.path.join(OUTPUTS_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)
    prefix  = make_filename(collection_name)

    concepts_file = ''
    if concept_table and concept_table.rows:
        concepts_file = os.path.join(out_dir, f'concepts_{prefix}')
        save_concepts_csv(concept_table, concepts_file)
        print(f'\nSaved: {concepts_file}')

    schema_file = os.path.join(out_dir, f'schema_{prefix}')
    save_schema_csv(schema_rows, normalized_concepts, schema_file)
    print(f'Saved: {schema_file}')

    # Copy schema to schemas/<collection>/ for reuse
    schema_dir  = os.path.join(SCHEMAS_DIR, slug)
    os.makedirs(schema_dir, exist_ok=True)
    schema_copy = os.path.join(schema_dir, f'schema_{prefix}')
    save_schema_csv(schema_rows, normalized_concepts, schema_copy)
    print(f'Saved: {schema_copy}')

    return {
        'collection_name':    collection_name,
        'domain':             domain,
        'papers':             papers,
        'normalized_concepts': normalized_concepts,
        'concept_table':      concept_table,
        'schema_rows':        schema_rows,
        'concepts_file':      concepts_file,
        'schema_file':        schema_file,
    }


# ---------------------------------------------------------------------------
# Pipeline B — Enrichment
# ---------------------------------------------------------------------------

def run_enrichment(csv_path: str) -> dict:
    """
    Run the enrichment pipeline on an existing concepts_*.csv file.

    Returns a result dict with keys:
        csv_out (path), drawio_out (path)
    """
    date_stamp = datetime.now().strftime('%Y%m%d')
    stem       = os.path.splitext(os.path.basename(csv_path))[0]
    slug       = os.path.basename(os.path.dirname(os.path.abspath(csv_path)))
    out_dir    = os.path.join(OUTPUTS_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)

    # 6. Load + tag
    print(f'\n[Enrichment] {os.path.basename(csv_path)}')
    df = load_concepts(csv_path)
    print(f'  Concepts : {len(df)}')
    print(f'  Tagging  : mds:studyStage + mds:supplyChainLevel…')
    df = tag_concepts(df)

    # Save enriched CSV
    csv_out = os.path.join(out_dir, f'enriched_{stem}-v7-{date_stamp}.csv')
    df.to_csv(csv_out, index=False)
    print(f'  CSV      : {csv_out}')

    # 7. Build draw.io diagram
    page_title = slug.replace('_', ' ').replace('-', ' ').title()
    mxfile_el  = build_drawio_xml(df, page_title=page_title)
    add_template_pages(mxfile_el)
    xml = serialize_drawio(mxfile_el)

    drawio_out = os.path.join(out_dir, f'diagram_{stem}-v7-{date_stamp}.drawio')
    with open(drawio_out, 'w', encoding='utf-8') as fh:
        fh.write(xml)
    print(f'  draw.io  : {drawio_out}')

    return {'csv_out': csv_out, 'drawio_out': drawio_out}


# ---------------------------------------------------------------------------
# Full pipeline — A then B
# ---------------------------------------------------------------------------

def run_full(collection_id: str) -> dict:
    """
    Run extraction (Pipeline A) followed immediately by enrichment (Pipeline B).
    Returns the combined result dict from both pipelines.
    """
    result_a = run_extraction(collection_id)
    concepts_file = result_a.get('concepts_file', '')

    if concepts_file and os.path.isfile(concepts_file):
        result_b = run_enrichment(concepts_file)
        return {**result_a, **result_b}

    print('\n[warn] No concepts CSV produced — skipping enrichment step.')
    return result_a
