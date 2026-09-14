# -*- coding: utf-8 -*-
"""
T2.2 — ablation: LLM-only vs LLM+REBEL.

Runs the pipeline twice on the same collection (REBEL off, then on) and reports
what REBEL adds: number of relational triples, predicate-vocabulary coverage, and
how many triple endpoints resolve to concept nodes (graph connectivity).

This is a LIVE driver — it needs the LLM endpoint + Zotero, like run_test.py.

Usage:
    python eval/ablation_rebel.py <collection_id> [limit]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

from kw import config, pipeline  # noqa: E402


def main() -> None:
    collection = sys.argv[1] if len(sys.argv) > 1 else config.COLLECTION_ID
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    print(f'== Ablation on {collection} (limit {limit}) ==')

    off = pipeline.run(collection, outputs_dir='outputs_ablation/off',
                       emit_diagram=False, do_lora=False, limit=limit, do_rebel=False)
    on = pipeline.run(collection, outputs_dir='outputs_ablation/on',
                      emit_diagram=False, do_lora=False, limit=limit, do_rebel=True)

    def line(tag, r):
        ms = r.get('merge_stats') or {}
        print(f'  {tag:10s} triples={r.get("n_triples", 0):4d}  '
              f'rel_vocab_cov={r.get("relation_coverage")}  '
              f'endpoint_resolution={ms.get("resolution_rate")}  '
              f'classes={(r.get("validation") or {}).get("classes")}')

    print('\nResult:')
    line('LLM-only', off)
    line('LLM+REBEL', on)
    print(f'\nREBEL added {on.get("n_triples", 0)} relational triples this run.')


if __name__ == '__main__':
    main()
