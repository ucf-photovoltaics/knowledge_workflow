# -*- coding: utf-8 -*-
"""
Knowledge Workflow — CLI entry point.

Usage
-----
  # Run the full pipeline (extraction + enrichment) for the default collection:
  python main.py

  # Extraction only:
  python main.py --extract

  # Enrichment only (on an existing concepts CSV):
  python main.py --enrich outputs/my_collection/concepts_*.csv

  # Override collection at runtime:
  python main.py --collection VWMCLGL5

  # List available Zotero collections and exit:
  python main.py --list-collections

Environment variables (or .env file):
  COLLECTION_ID      Zotero collection key to process
  LLM_MODEL          Model name  (default: claude-sonnet-4-6)
  LLM_BASE_URL       OpenAI-compatible base URL
  LLM_API_KEY        API key
  ZOTERO_API_KEY     Zotero API key
  ZOTERO_LIBRARY_ID  Zotero library ID
"""

import argparse
import glob
import os
import sys

from src.config import COLLECTION_ID, OUTPUTS_DIR, MODEL, LLM_BASE_URL
from src.tools.zotero_client import get_collection_map
from src.agents.orchestrator import run_extraction, run_enrichment, run_full


def _list_collections() -> None:
    print('Fetching Zotero collections…\n')
    coll_map = get_collection_map()
    if not coll_map:
        print('No collections found.')
        return
    max_len = max(len(k) for k in coll_map)
    for name, key in sorted(coll_map.items()):
        print(f'  {name:<{max_len}}  {key}')


def _find_concept_csvs(pattern: str | None = None) -> list[str]:
    p = pattern or os.path.join(OUTPUTS_DIR, '**', 'concepts_*.csv')
    return sorted(glob.glob(p, recursive=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Knowledge Workflow — multi-agent literature extraction & enrichment.'
    )
    parser.add_argument(
        '--collection', '-c',
        default=COLLECTION_ID,
        help='Zotero collection ID to process (overrides COLLECTION_ID env var).',
    )
    parser.add_argument(
        '--extract',
        action='store_true',
        help='Run extraction pipeline (Phase 1 + normalization + Phase 2) only.',
    )
    parser.add_argument(
        '--enrich',
        nargs='?',
        const='',       # --enrich with no argument → discover all concepts_*.csv
        metavar='CSV',
        help=(
            'Run enrichment pipeline on a concepts CSV. '
            'Omit the path to process all concepts_*.csv files found under outputs/.'
        ),
    )
    parser.add_argument(
        '--list-collections',
        action='store_true',
        help='List available Zotero collections and exit.',
    )
    args = parser.parse_args()

    print(f'Provider : {LLM_BASE_URL}')
    print(f'Model    : {MODEL}')

    if args.list_collections:
        _list_collections()
        return

    if args.enrich is not None:
        # Enrichment-only mode
        if args.enrich:
            csv_files = [args.enrich]
        else:
            csv_files = _find_concept_csvs()
            if not csv_files:
                print(
                    f'\nNo concepts_*.csv files found under "{OUTPUTS_DIR}".\n'
                    f'Run extraction first, or pass a specific CSV path with --enrich <path>.'
                )
                sys.exit(1)

        print(f'\nFound {len(csv_files)} concepts file(s) to enrich:\n')
        for p in csv_files:
            print(f'  {p}')

        results = []
        for idx, csv_path in enumerate(csv_files, 1):
            print(f'\n[{idx}/{len(csv_files)}] {os.path.basename(csv_path)}')
            try:
                result = run_enrichment(csv_path)
                results.append(result)
            except Exception as exc:
                print(f'  ERROR: {exc}')

        print('\n' + '=' * 60)
        print(f'Done — {len(results)}/{len(csv_files)} files processed\n')
        for r in results:
            print(f'  {r["drawio_out"]}')
            print(f'  {r["csv_out"]}')
        return

    if args.extract:
        # Extraction-only mode
        result = run_extraction(args.collection)
        _print_extraction_summary(result)
        return

    # Default: run full pipeline
    result = run_full(args.collection)
    _print_extraction_summary(result)
    if 'drawio_out' in result:
        print(f'\nDiagram  : {result["drawio_out"]}')
        print('Open .drawio files in draw.io → File → Open from → This Device')


def _print_extraction_summary(result: dict) -> None:
    concept_table = result.get('concept_table')
    schema_rows   = result.get('schema_rows', [])
    concepts      = result.get('normalized_concepts', [])

    if concept_table and not concept_table.rows:
        pass
    elif concept_table:
        print(f'\n--- Concept extraction preview (top 20 rows) ---')
        import pandas as pd
        rows = [
            {'paper': r.paper[:50], 'canonical': r.canonical,
             'paper_term': r.paper_term, 'relevance': r.relevance}
            for r in concept_table.rows[:20]
        ]
        print(pd.DataFrame(rows).to_string(index=False))

    print(f'\n--- Schema preview ---')
    print(f'Papers  : {len(schema_rows)}')
    print(f'Concepts: {len(concepts)}')
    if concepts:
        print(f'\nAll concept columns ({len(concepts)}):')
        for c in concepts:
            print(f'  {c}')


if __name__ == '__main__':
    main()
