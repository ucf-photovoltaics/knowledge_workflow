# -*- coding: utf-8 -*-
"""
Regression test for the stale validation gate.

Observed 2026-08-23 on a real queue run:

    [queue 1/2] FAIL in 92s | validation gate: PASS

The Si-PERC run crashed in Step 1 (the LLM provider was unreachable) and never
got anywhere near validation. But a validation_report.json from the SUCCESSFUL
2026-08-17 run of the same collection was still sitting in the output folder, and
gate_passed() read it without asking which run wrote it.

A crashed run wearing an earlier run's passing gate is the most dangerous
possible output: it is the exact shape that made the earlier Si-SHJ failures look
like successes, and it is the same class of bug as the date-glob in
ontology._run_files.

    python eval/test_gate_staleness.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('run_queue', ROOT / 'scripts' / 'run_queue.py')
run_queue = importlib.util.module_from_spec(spec)
sys.modules['run_queue'] = run_queue
spec.loader.exec_module(run_queue)

FAILURES = []


def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        FAILURES.append(msg)


def _write_report(d: Path, passed: bool):
    d.mkdir(parents=True, exist_ok=True)
    (d / 'validation_report.json').write_text(
        json.dumps({'passed': passed}), encoding='utf-8')


def main():
    print('\n[1] a report written BEFORE the run started is not this run\'s evidence')
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'si_perc'
        _write_report(out, passed=True)          # the 2026-08-17 run's report
        old = time.time() - 3600
        os.utime(out / 'validation_report.json', (old, old))

        run_start = time.time()                  # today's run starts now
        check(run_queue.gate_passed(str(out)) is True,
              'without the guard the stale PASS is still readable (the old behaviour)')
        check(run_queue.gate_passed(str(out), newer_than=run_start) is None,
              'with the guard a stale report yields None, not PASS')

    print('\n[2] a report this run actually wrote is still trusted')
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'si_perc'
        run_start = time.time()
        time.sleep(0.05)
        _write_report(out, passed=True)
        check(run_queue.gate_passed(str(out), newer_than=run_start) is True,
              'a fresh PASS is reported as PASS')
        _write_report(out, passed=False)
        check(run_queue.gate_passed(str(out), newer_than=run_start) is False,
              'a fresh FAIL is reported as FAIL')

    print('\n[3] no report at all')
    with tempfile.TemporaryDirectory() as tmp:
        check(run_queue.gate_passed(tmp, newer_than=time.time()) is None,
              'a missing report yields None')

    print()
    if FAILURES:
        print(f'{len(FAILURES)} check(s) failed:')
        for f in FAILURES:
            print('  - ' + f)
        sys.exit(1)
    print('all checks passed')


if __name__ == '__main__':
    main()
