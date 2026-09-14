# -*- coding: utf-8 -*-
"""
CLI
  python -m kw --list-collections
  python -m kw run -c <collection_id>                       # unsupervised, both outputs
  python -m kw run -c <id> --concepts list.csv              # supervised
  python -m kw run -c <id> --no-diagram --no-lora           # ontology/JSON-LD only

Tuning dials (override config defaults):
  python -m kw run -c <id> --limit 20                       # cap papers processed
  python -m kw run -c <id> --top-n 15                       # terms extracted per paper
  python -m kw run -c <id> --min-relevance 0.4             # drop low-relevance concepts
  python -m kw run -c <id> --max-concepts 50               # cap normalized ontology size
"""
import argparse

from kw import config


def main() -> None:
    ap = argparse.ArgumentParser(prog='kw', description='Knowledge Workflow — one ordered pipeline.')
    ap.add_argument('command', nargs='?', default='run', choices=['run'])
    ap.add_argument('--collection', '-c', default=config.COLLECTION_ID,
                    help='Zotero collection id (default: env COLLECTION_ID).')
    ap.add_argument('--concepts', default=None,
                    help='Supervised mode: CSV of concepts (skips Step 1 extraction).')
    ap.add_argument('--outputs', default=None, help='Output directory (default: outputs/).')
    ap.add_argument('--no-diagram', action='store_true', help='Skip the cemento draw.io diagram.')
    ap.add_argument('--no-lora', action='store_true', help='Skip the Step 6 LoRA fine-tune.')
    ap.add_argument('--no-visual', action='store_true',
                    help='Skip the Step 7 interactive graph + benchmark.')
    # --- Tuning dials (None => use config default) ---
    ap.add_argument('--limit', type=int, default=None,
                    help='Cap the number of papers processed (default: all).')
    ap.add_argument('--top-n', type=int, default=None, dest='top_n',
                    help=f'Terms extracted per paper (default: TOP_N_PER_PAPER={config.TOP_N_PER_PAPER}).')
    ap.add_argument('--min-relevance', type=float, default=None, dest='min_relevance',
                    help=f'Drop concepts below this relevance 0.0-1.0 (default: {config.MIN_RELEVANCE}).')
    ap.add_argument('--max-concepts', type=int, default=None, dest='max_concepts',
                    help='Cap the normalized ontology size (default: 0 = uncapped, targets 30-80).')
    ap.add_argument('--list-collections', action='store_true', help='List Zotero collections and exit.')
    args = ap.parse_args()

    if args.list_collections:
        from kw import zotero
        for name, key in sorted(zotero.get_collection_map().items()):
            print(f'{key}\t{name}')
        return

    from kw import pipeline
    r = pipeline.run(
        args.collection, concepts_csv=args.concepts, outputs_dir=args.outputs,
        emit_diagram=not args.no_diagram, do_lora=not args.no_lora,
        emit_visual=not args.no_visual,
        limit=args.limit, top_n=args.top_n,
        min_relevance=args.min_relevance, max_concepts=args.max_concepts,
    )
    print('\nOutputs')
    print(f'  GraphDB repo : {r.get("out_dir")}  (ontology TTL + all.jsonld)')
    print(f'  Ontology     : {r.get("ttl")}')
    print(f'  Diagram      : {r.get("diagram")}')
    if r.get('lora'):
        print(f'  LoRA adapter : {r["lora"].get("adapter_version")}')
    if r.get('visual'):
        print(f'  Graph        : {r["visual"].get("html")}')
        print(f'  Benchmark    : {r["visual"].get("benchmark")}')


if __name__ == '__main__':
    main()
