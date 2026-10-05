"""Rows the model leaves out are re-sent in smaller batches; answers inside an echoed schema are read."""
import json
import unittest
from collections import Counter

from src.agents.base import Agent, items


class Fake(Agent):
    name = "fake"

    def __init__(self):
        self.row_stats, self.doubts, self.sizes = {}, [], []

    def call(self, user, item, system=None, label=None, soft=False, cache_valid=None):
        rows = json.loads(user.split("\n", 1)[1])
        self.sizes.append(len(rows))
        if len(rows) > 5:  # big batches: the schema comes back, nothing else
            return {"type": "object", "properties": {"keep": {"type": "array"}}}
        return {"keep": [{"id": r["id"], "candidates": [1]} for r in rows]}


class RowRetryTests(unittest.TestCase):
    def test_third_try_in_smaller_batches(self):
        rows = [{"id": f"k{i}"} for i in range(20)]
        a = Fake()
        self.assertEqual(a.call_rows(rows, "", "filter", "keep", "candidates", size=20, retries=1), [])
        b = Fake()
        got = b.call_rows(rows, "", "filter", "keep", "candidates", size=20, retries=2)
        self.assertEqual(len(got), 20)
        self.assertEqual(b.sizes, [20, 10, 10, 5, 5, 5, 5])
        self.assertEqual(b.row_stats["filter"], Counter(rows=20, answered_first=0, recovered=20, missing=0,
                                                        recovered_retry2=20))

    def test_answers_inside_schema_echo(self):
        echo = {"type": "object", "required": ["keep"],
                "properties": {"keep": {"type": "array", "items": {"type": "object"}},
                               "_values": [{"keep": [{"id": "k1", "candidates": [2]}]}],
                               "k2": {"id": "k2", "candidates": []}}}
        self.assertEqual({r["id"] for r in items(echo, "keep", "candidates") if r["id"].startswith("k")}, {"k1", "k2"})


if __name__ == "__main__":
    unittest.main()
