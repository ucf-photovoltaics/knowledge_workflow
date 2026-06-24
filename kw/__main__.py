# -*- coding: utf-8 -*-
"""
CLI
  python -m kw --list-collections
  python -m kw run -c <collection_id>                       # unsupervised, both outputs
  python -m kw run -c <id> --concepts list.csv              # supervised
  python -m kw run -c <id> --no-diagram --no-lora           # ontology/JSON-LD only
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
    )
    print('\nOutputs')
    print(f'  GraphDB repo : {r.get("out_dir")}  (ontology TTL + all.jsonld)')
    print(f'  Ontology     : {r.get("ttl")}')
    print(f'  Diagram      : {r.get("diagram")}')
    if r.get('lora'):
        print(f'  LoRA adapter : {r["lora"].get("adapter_version")}')


if __name__ == '__main__':
    main()
