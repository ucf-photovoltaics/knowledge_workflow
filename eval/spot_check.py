# -*- coding: utf-8 -*-
"""
T2.4 — gold-standard spot-check with inter-annotator agreement.

Two sub-commands:

  sample  — draw N schema cells + M REBEL triples from an output folder into a
            review CSV with blank `annotator1` / `annotator2` columns (mark each
            1 = correct, 0 = incorrect).

  score   — read the filled review CSV and report per-annotator precision and
            Cohen's kappa for the schema cells and the triples separately.

Usage:
    python eval/spot_check.py sample outputs_test/<slug> [n_cells] [m_triples]
    python eval/spot_check.py score  eval/spot_check_review.csv
"""
from __future__ import annotations

import csv
import glob
import json
import os
import random
import sys

REVIEW = os.path.join(os.path.dirname(__file__), 'spot_check_review.csv')
FIELDS = ['kind', 'source_paper', 'item', 'annotator1', 'annotator2']


def _sample(out_folder: str, n_cells: int, m_triples: int) -> None:
    rows: list[dict] = []

    # schema cells from schema_*.csv
    for sp in glob.glob(os.path.join(out_folder, 'schema_*.csv')):
        df = list(csv.DictReader(open(sp, encoding='utf-8')))
        cells = []
        for r in df:
            for col, val in r.items():
                if col in ('domain', 'doi') or not val.strip():
                    continue
                cells.append((r.get('doi', ''), f'{col} = {val.split(" | ")[0]}'))
        random.shuffle(cells)
        for doi, item in cells[:n_cells]:
            rows.append({'kind': 'cell', 'source_paper': doi, 'item': item,
                         'annotator1': '', 'annotator2': ''})
        break

    # REBEL triples from rebel_triples.jsonld
    rj = os.path.join(out_folder, 'rebel_triples.jsonld')
    if os.path.isfile(rj):
        graph = json.load(open(rj, encoding='utf-8')).get('@graph', [])
        random.shuffle(graph)
        for node in graph[:m_triples]:
            item = f'{node.get("mds:subject")} -[{node.get("mds:predicate")}]- {node.get("mds:object")}'
            rows.append({'kind': 'triple', 'source_paper': node.get('prov:wasDerivedFrom', ''),
                         'item': item, 'annotator1': '', 'annotator2': ''})

    with open(REVIEW, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f'Wrote {len(rows)} items to {REVIEW} — fill annotator1/annotator2 (1=correct, 0=incorrect).')


def _kappa(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n == 0:
        return float('nan')
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa1 = sum(a) / n
    pb1 = sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return round((po - pe) / (1 - pe), 3) if pe != 1 else 1.0


def _score(review_csv: str) -> None:
    rows = list(csv.DictReader(open(review_csv, encoding='utf-8')))
    for kind in ('cell', 'triple'):
        sub = [r for r in rows if r['kind'] == kind
               and r['annotator1'].strip() and r['annotator2'].strip()]
        if not sub:
            print(f'{kind:7s}: no annotated rows')
            continue
        a = [int(r['annotator1']) for r in sub]
        b = [int(r['annotator2']) for r in sub]
        prec_a = round(sum(a) / len(a), 3)
        prec_b = round(sum(b) / len(b), 3)
        print(f'{kind:7s}: n={len(sub)}  precision(annot1)={prec_a}  '
              f'precision(annot2)={prec_b}  cohens_kappa={_kappa(a, b)}')


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == 'sample':
        folder = sys.argv[2]
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 50
        m = int(sys.argv[4]) if len(sys.argv) > 4 else 50
        _sample(folder, n, m)
    elif cmd == 'score':
        _score(sys.argv[2])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
