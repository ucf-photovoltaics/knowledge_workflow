"""Overload step-down, answers reused per row across runs, and calls that need two fields per row."""
import json
from threading import RLock

import pytest

from src.agents import base
from src.agents.base import Agent
from src.tools import workers
from src.tools.ledger import Ledger


@pytest.fixture(autouse=True)
def reset_workers():
    workers.configure(2)
    yield
    workers.configure(2)


def test_step_down_halves_and_counts_one_burst_once():
    workers.configure(8)
    with workers.slot() as before:
        pass
    workers.fallback("HTTP 503", generation=before)
    assert workers.active_limit == 4
    workers.fallback("HTTP 503", generation=before)  # another request from the same burst
    assert workers.active_limit == 4
    with workers.slot() as now:
        pass
    workers.fallback("timeout", timeout=True, generation=now)
    assert workers.active_limit == 4  # one timeout is not enough
    workers.fallback("timeout", timeout=True, generation=now)
    assert workers.active_limit == 2
    workers.fallback("HTTP 503")
    workers.fallback("HTTP 503")
    assert workers.active_limit == 1
    assert [e["workers"] for e in workers.events] == [4, 2, 1]


class Rows(Agent):
    name = "enrichment"

    def __init__(self, run_dir, labels):
        self._lock, self.row_stats, self.doubts = RLock(), {}, []
        self.ledger = Ledger(run_dir / "ledger.jsonl")
        self.profile = {"provider": "openai", "base_url": "http://localhost:11434/v1", "request": {}}
        self.model, self.concept_labels, self.sent = "test-model", labels, []

    def call(self, user, item, system=None, label=None, soft=False, cache_valid=None):
        rows = json.loads(user.split("\n", 1)[1])
        self.sent += [r["id"] for r in rows]
        return {"classes": [{"id": r["id"], "disjoint_with": [s.split(":")[0] for s in r["siblings"][:1]],
                             **({"basis": "none"} if "basis" in (system or "") else {})} for r in rows]}


def sibling_rows(ids, labels, evidence=None):
    """One row per id; each lists the next id as a sibling, as enrichment does."""
    return [{"id": i, "label": labels[i], "siblings": [f"{j}: {labels[j]}" for j in ids[n + 1:n + 2]],
             "evidence": (evidence or {}).get(i, [])} for n, i in enumerate(ids)]


@pytest.fixture
def row_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(base, "REUSE_ANSWERS", True)
    return tmp_path


def test_rows_reused_across_runs_with_renumbered_ids(row_cache):
    first = Rows(row_cache / "tea-n5", {"k1": "Solar cell", "k2": "Wafer", "k3": "Module"})
    got = first.call_rows(sibling_rows(["k1", "k2", "k3"], first.concept_labels), "", "disjointness", "classes",
                          "disjoint_with", size=8)
    assert first.sent == ["k1", "k2", "k3"] and len(got) == 3
    # the next size: the same concepts under new ids, one new concept, and new evidence for "Module"
    labels = {"k7": "Solar cell", "k2": "Wafer", "k9": "Module", "k4": "Glass"}
    second = Rows(row_cache / "tea-n10", labels)
    rows = sibling_rows(["k7", "k2", "k9", "k4"], labels, evidence={"k9": ["new quote"]})
    got = {a["id"]: a for a in second.call_rows(rows, "", "disjointness", "classes", "disjoint_with", size=8)}
    assert second.sent == ["k9", "k4"]  # Module's row changed (new evidence, new sibling); Glass is new
    assert got["k7"]["disjoint_with"] == ["k2"]  # stored as "Wafer", read back under this run's id
    assert second.row_stats["disjointness"]["reused"] == 2
    audit = [json.loads(line) for line in (row_cache / "tea-n10" / "rows.jsonl").read_text().splitlines()]
    assert sorted(a["id"] for a in audit if a["source"] == "reused") == ["k2", "k7"]


def test_shared_label_and_fresh_mode_are_never_reused(row_cache, monkeypatch):
    labels = {"k1": "Cell", "k2": "cell", "k3": "Wafer"}
    for run in ("a", "b"):
        agent = Rows(row_cache / run, labels)
        agent.call_rows(sibling_rows(["k1", "k2", "k3"], labels), "", "disjointness", "classes", "disjoint_with")
    assert agent.sent == ["k1", "k2"]  # rows naming the two "cell" concepts are asked again
    monkeypatch.setattr(base, "REUSE_ANSWERS", False)
    agent = Rows(row_cache / "c", labels)
    agent.call_rows(sibling_rows(["k1", "k2", "k3"], labels), "", "disjointness", "classes", "disjoint_with")
    assert agent.sent == ["k1", "k2", "k3"]


def test_two_required_fields():
    class Tags(Rows):
        def call(self, user, item, system=None, label=None, soft=False, cache_valid=None):
            rows = json.loads(user.split("\n", 1)[1])
            self.sent.append(len(rows))
            return {"tags": [{"id": r["id"], "study_stage": ["Sample"], **({"domain": "General"} if len(rows) < 8 else {})}
                             for r in rows]}

    agent = Tags.__new__(Tags)
    agent._lock, agent.row_stats, agent.doubts, agent.sent = RLock(), {}, [], []
    got = agent.call_rows([{"id": f"k{i}"} for i in range(8)], "", "facets", "tags", ("study_stage", "domain"), size=8)
    assert len(got) == 8 and agent.sent == [8, 5, 3]  # the first answer lacked domain: every row was re-sent
    assert agent.row_stats["facets"]["answered_first"] == 0
