# -*- coding: utf-8 -*-
"""
T2.1 — multi-domain structural-metrics harness.

Discovers every *_onto.ttl under the given output roots, runs the validation gate
on each, and writes one table (CSV + a printed summary) for the paper's Evaluation
section.

Usage:
    python eval/run_all.py                      # scans outputs/ and outputs_test/
    python eval/run_all.py outputs my_runs      # scan specific roots
"""
from __future__ import annotations

import csv
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kw import validate  # noqa: E402

FIELDS = ['ontology', 'classes', 'aligned_to_upper', 'alignment_ratio',
          'alignment_pass', 'reasoner', 'oops_status', 'oops_critical',
          'shacl', 'passed', 'triples']


def find_ttls(roots: list[str]) -> list[str]:
    found: list[str] = []
    for root in roots:
        found += glob.glob(os.path.join(root, '**', '*_onto.ttl'), recursive=True)
    return sorted(set(found))


def main() -> None:
    roots = sys.argv[1:] or ['outputs', 'outputs_test']
    ttls = find_ttls(roots)
    if not ttls:
        print(f'No *_onto.ttl found under: {", ".join(roots)}')
        return

    rows = []
    for ttl in ttls:
        try:
            r = validate.evaluate(ttl)
        except Exception as exc:
            print(f'  [skip] {ttl}: {exc}')
            continue
        r['ontology'] = os.path.relpath(ttl)
        r['oops_critical'] = ';'.join(r.get('oops_critical') or [])
        rows.append({k: r.get(k, '') for k in FIELDS})

    out = os.path.join(os.path.dirname(__file__), 'metrics.csv')
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f'\n{"ontology":40s} {"classes":>7} {"align":>6} {"pass":>5} {"reasoner":>10}')
    print('-' * 74)
    for r in rows:
        print(f'{os.path.basename(r["ontology"]):40s} {r["classes"]:>7} '
              f'{r["alignment_ratio"]:>6} {str(r["passed"]):>5} {r["reasoner"]:>10}')
    print(f'\n{len(rows)} ontolog(ies) -> {out}')


if __name__ == '__main__':
    main()
