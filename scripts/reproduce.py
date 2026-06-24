# -*- coding: utf-8 -*-
"""
T4.4 — reproducibility check.

Builds the OWL 2 ontology from a pinned sample schema and runs the validation
gate, fully offline and deterministic (no LLM, no network). Use it to confirm a
fresh clone reproduces the reference metrics, and to print the pinned settings
that make a full run reproducible.

Usage:
    python scripts/reproduce.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from kw import ontology, validate, rebel, lora, config  # noqa: E402

SAMPLE = os.path.join(ROOT, 'eval', 'sample', 'gaas_reference', 'schema_gaas.csv')
OUTDIR = os.path.join(ROOT, 'outputs_repro')


def main() -> None:
    print('== Pinned settings ==')
    print(f'  LLM model        : {config.MODEL}')
    print(f'  output mode      : {config.LLM_OUTPUT_MODE}')
    print(f'  REBEL model/rev  : {rebel.REBEL_MODEL} @ {rebel.REBEL_REVISION}')
    print(f'  LoRA base model  : {lora.BASE_MODEL}')
    print(f'  alignment target : {validate.ALIGNMENT_TARGET}')

    print('\n== Build + validate the reference ontology ==')
    ttl = ontology.build_collection_ontology(SAMPLE, OUTDIR, domain_val='gaas')
    print(f'  ontology -> {ttl}')

    report = validate.evaluate(ttl)
    for k in ('classes', 'aligned_to_upper', 'alignment_ratio',
              'reasoner', 'shacl', 'oops_status', 'passed'):
        print(f'  {k:16s}: {report[k]}')

    ok = report['alignment_ratio'] >= validate.ALIGNMENT_TARGET
    print(f'\nReference reproduced: {"OK" if ok else "MISMATCH"} '
          f'(alignment {report["alignment_ratio"]} >= {validate.ALIGNMENT_TARGET})')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
