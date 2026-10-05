"""Runs in parallel share eval_runs.csv: no row may be lost."""
import csv
import tempfile
import unittest
from multiprocessing import Pool
from pathlib import Path

from src.tools import reports


def _write(args):
    path, worker = args
    for i in range(20):
        reports.upsert_eval(Path(path), {"run_id": f"w{worker}-{i}", "row_type": "run", f"col{worker}": i})


class SharedFileTests(unittest.TestCase):
    def test_parallel_upserts_keep_every_row(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "eval_runs.csv")
            with Pool(4) as pool:
                pool.map(_write, [(path, w) for w in range(4)])
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 80)
            self.assertFalse(any(Path(d).glob("*.lock")))


if __name__ == "__main__":
    unittest.main()
