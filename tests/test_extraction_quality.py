import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from unittest.mock import Mock
from src.agents import extraction
from src.agents.extraction import ExtractionAgent
from src.tools import concept_quality

BAD = (Path(__file__).parent / "fixtures/malformed-concept-label.txt").read_text(encoding="utf-8")


def record():
    return {"key": "P1", "concepts": [{"id": "c107", "label": BAD}, {"id": "c1", "label": "Solar cell"}, {"id": "c2", "label": "Silicon"}],
            "relations": [{"s": "c1", "p": "has_part", "o": "c2"}, {"s": "c1", "p": "bad", "o": "c107"}],
            "causal": [{"cause": "c107", "effect": "c2"}], "measurements": [{"concept": "c107", "value": "1"}],
            "figures": [{"id": "F1", "concepts": ["c107", "c1"]}]}


def test_actual_label_is_quarantined_with_dependent_records_and_preserved_raw():
    source = record()
    before = copy.deepcopy(source)
    safe = concept_quality.quarantine(source)
    assert len(BAD) == 17513
    assert [c["id"] for c in safe["concepts"]] == ["c1", "c2"]
    assert len(safe["relations"]) == 1 and safe["causal"] == [] and safe["measurements"] == []
    assert safe["figures"][0]["concepts"] == ["c1"]
    assert len(safe["quality_review"]) == 5 and safe["quality_review"][0]["record"]["label"] == BAD
    assert source == before
    again = concept_quality.quarantine(safe)
    assert again == safe


def test_merge_and_finalize_preserve_valid_claims_after_id_renumbering():
    source = record()
    source["concepts"][0]["id"] = "c3"
    source["relations"][1]["o"] = "c3"
    merged = ExtractionAgent._merge([source])
    assert len(merged["concepts"]) == 2 and len(merged["relations"]) == 1
    paper = {"sections": [{"heading": "Results", "text": "Solar cell has silicon."}], "figures": [{"id": "F1"}]}
    finalized = ExtractionAgent._finalize(merged, paper)
    assert len(finalized["relations"]) == 1 and finalized["quality_review"]
    assert all(c["label"] != BAD for c in finalized["concepts"])


def test_mult_pass_does_not_feed_bad_labels_forward_or_confuse_old_ids():
    agent = ExtractionAgent.__new__(ExtractionAgent)
    agent.passes = ["concepts", "relations"]
    agent.prompts = {"concepts": "concept prompt", "relations": "relation prompt"}
    agent.new_concepts = Counter()
    agent.call = Mock(side_effect=[{"concepts": [{"id": "c1", "label": BAD}, {"id": "c2", "label": "Solar cell"}, {"id": "c3", "label": "Silicon"}]},
        {"new_concepts": [{"id": "n1", "label": BAD}], "relations": [{"s": "c1", "p": "has_part", "o": "c2"}, {"s": "c1", "p": "bad", "o": "n1"}]}])
    agent._fill_evidence = Mock()
    calls = []
    result = agent._multi_pass("source text", "", [], "section 1", "P1", calls)
    assert BAD not in agent.call.call_args_list[1].args[0]
    assert calls[0]["output"]["concepts"][0]["label"] == BAD
    merged = ExtractionAgent._merge([result])
    assert len(merged["concepts"]) == 2 and len(merged["relations"]) == 1


def test_legacy_cache_is_guarded_without_overwriting_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(extraction, "CACHE", tmp_path)
    agent = ExtractionAgent.__new__(ExtractionAgent)
    agent.fingerprint, agent.model, agent.ledger = "fixture", "fixture-model", Mock()
    agent._chunks = Mock(return_value=["chunk"])
    agent.call = Mock(side_effect=AssertionError("No model call on cache hit"))
    digest = hashlib.sha256(b"fixturechunk").hexdigest()[:16]
    path = tmp_path / "extraction" / f"P1-{digest}.json"
    path.parent.mkdir()
    path.write_text(json.dumps(record()), encoding="utf-8")
    before = path.read_bytes()
    result = agent.run({"key": "P1"})
    assert result["cache_hit"] and len(result["concepts"]) == 2
    assert path.read_bytes() == before
    agent.call.assert_not_called()


def test_normalization_boundary_guards_existing_paper_records(tmp_path, monkeypatch):
    from src import run
    source = record()
    before = copy.deepcopy(source)
    saved = {}
    class Run:
        dir, id, ledger = tmp_path, "fixture", None
        def papers(self): return [source]
        def write(self, name, data): saved[name] = data
    class Agent:
        doubts = []
        def __init__(self, ledger): pass
        def run(self, papers):
            assert len(papers[0]["concepts"]) == 2
            return {k: [] for k in ("concepts", "relations", "causal", "measurements", "contradictions", "causal_order", "summary")}
    monkeypatch.setattr(run, "NormalizationAgent", Agent)
    monkeypatch.setattr(run, "_uncertain", lambda *args: None)
    monkeypatch.setattr(run.reports, "corpus_report", lambda *args: {"canonical_concepts": 2})
    run.normalize(Run(), None)
    assert saved["extraction_review/P1.json"][0]["record"]["label"] == BAD
    assert source == before
