"""Runtime changes must preserve coverage, cache identity, evidence text, and search ranking."""
import json
import os
import time
from unittest.mock import Mock

import numpy as np
import pytest

from src import run
from src.agents import base, enrichment
from src.agents.base import Agent
from src.agents.extraction import ExtractionAgent
from src.tools import llm, mds_portal, ontostore, retrieval
from src.tools.ledger import Ledger


class CacheAgent(Agent):
    name = "enrichment"


def row_agent(reply):
    agent = Agent.__new__(Agent)
    agent.row_stats, agent.doubts = {}, []
    agent.call = Mock(side_effect=reply)
    return agent


def test_empty_answers_complete_but_missing_values_and_other_batches_retry():
    agent = row_agent([
        {"keep": [{"id": "k1", "candidates": []}, {"id": "k2"}, {"id": "k3", "candidates": [1]}]},
        {"keep": [{"id": "k3", "candidates": []}]},
        {"keep": [{"id": "k2", "candidates": []}]},
    ])
    got = agent.call_rows([{"id": f"k{i}"} for i in range(1, 4)], "", "filter", "keep", "candidates", size=2)
    assert {r["id"] for r in got} == {"k1", "k2", "k3"}
    assert agent.row_stats["filter"]["answered_first"] == 2
    assert agent.row_stats["filter"]["recovered"] == 1
    assert agent.doubts == []


def test_empty_string_counts_and_id_only_stays_unanswered():
    agent = row_agent([{"classes": [{"id": "k1", "definition": ""}, {"id": "k2"}]}])
    got = agent.call_rows([{"id": "k1"}, {"id": "k2"}], "", "definitions", "classes", "definition", retries=0)
    assert got == [{"id": "k1", "definition": ""}]
    assert agent.row_stats["definitions"]["missing"] == 1
    assert agent.doubts[0]["id"] == "k2"


def test_call_cache_identity_and_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "CACHE", tmp_path / "cache")
    chat = Mock(return_value=('{"classes":[{"id":"k1","definition":""}]}', llm.Usage(10, 0, 3, .1)))
    monkeypatch.setattr(llm, "chat", chat)
    agent = CacheAgent(Ledger(tmp_path / "run" / "ledger.jsonl"))
    agent.call("input", "first")
    assert agent.call("input", "second") == {"classes": [{"id": "k1", "definition": ""}]}
    assert chat.call_count == 1
    audit = [json.loads(s) for s in (tmp_path / "run" / "calls.jsonl").read_text().splitlines()]
    assert audit[-1]["cache_hit"] and audit[-1]["source_usage"]["input_tokens"] == 10
    assert agent.ledger.summary("agent")["enrichment"]["calls"] == 1
    agent.call("different input", "third")
    agent.call("input", "fourth", system="different prompt")
    agent.model = "different-model"
    agent.call("input", "fifth")
    agent.profile = {**agent.profile, "base_url": "http://different.example"}
    agent.call("input", "sixth")
    agent.profile = {**agent.profile, "request": {"max_tokens": 10}}
    agent.call("input", "seventh")
    assert chat.call_count == 6


def test_incomplete_calls_are_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "CACHE", tmp_path / "cache")
    chat = Mock(return_value=('{"classes":[{"id":"k1"}]}', llm.Usage()))
    monkeypatch.setattr(llm, "chat", chat)
    agent = CacheAgent(Ledger(tmp_path / "ledger.jsonl"))
    for _ in range(2):
        assert agent.call_rows([{"id": "k1"}], "", "definitions", "classes", "definition", retries=0) == []
    assert chat.call_count == 2
    assert not list((tmp_path / "cache").glob("calls/*.json"))


def test_complete_empty_row_is_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "CACHE", tmp_path / "cache")
    chat = Mock(return_value=('{"classes":[{"id":"k1","definition":""}]}', llm.Usage()))
    monkeypatch.setattr(llm, "chat", chat)
    agent = CacheAgent(Ledger(tmp_path / "ledger.jsonl"))
    for _ in range(2):
        assert agent.call_rows([{"id": "k1"}], "", "definitions", "classes", "definition") == [
            {"id": "k1", "definition": ""}]
    assert chat.call_count == 1
    assert agent.row_stats["definitions"]["missing"] == 0


def test_corrupt_call_cache_is_replaced(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "CACHE", tmp_path / "cache")
    chat = Mock(return_value=('{"summary":"ok"}', llm.Usage()))
    monkeypatch.setattr(llm, "chat", chat)
    agent = CacheAgent(Ledger(tmp_path / "ledger.jsonl"))
    agent.call("input", "summary")
    path = next((tmp_path / "cache" / "calls").glob("*.json"))
    path.write_text("not json", encoding="utf-8")
    assert agent.call("input", "summary") == {"summary": "ok"}
    assert chat.call_count == 2
    assert json.loads(path.read_text())["source_item"] == "summary"


def test_embedding_cache_preserves_order_and_model_namespace(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    provider = Mock(side_effect=lambda texts, batch: ([[float(len(t)), 1.] for t in texts], llm.Usage(2)))
    monkeypatch.setattr(llm, "_embed_uncached", provider)
    first, usage = llm.embed(["a", "long", "a"])
    assert first == [[1., 1.], [4., 1.], [1., 1.]] and not usage.cache_hit
    assert provider.call_args.args[0] == ["a", "long"]
    assert llm.embed(["long", "a"])[1].cache_hit
    llm.embed(["a", "new"])
    assert provider.call_args.args[0] == ["new"]
    monkeypatch.setitem(llm.EMBED, "model", "another-model")
    llm.embed(["a"])
    assert provider.call_count == 3
    monkeypatch.setitem(llm.EMBED, "base_url", "http://other.example")
    llm.embed(["a"])
    assert provider.call_count == 4


def test_bad_embeddings_do_not_enter_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    provider = Mock(return_value=([[float("nan")]], llm.Usage()))
    monkeypatch.setattr(llm, "_embed_uncached", provider)
    for _ in range(2):
        with pytest.raises(ValueError, match="invalid vectors"):
            llm.embed(["a"])
    assert provider.call_count == 2
    with pytest.raises(ValueError, match="list of strings"):
        llm.embed([None])


def test_retrieval_memory_is_scoped_by_model(monkeypatch):
    monkeypatch.setattr(retrieval, "_vectors", {})
    monkeypatch.setattr(retrieval, "_identity", None)
    provider = Mock(return_value=([[1., 0.]], llm.Usage()))
    monkeypatch.setattr(llm, "embed", provider)
    retrieval.embed(["a"])
    retrieval.embed(["a"])
    monkeypatch.setitem(retrieval.EMBED, "model", "other")
    retrieval.embed(["a"])
    assert provider.call_count == 2


def test_limit_stops_pdf_fetch_but_skips_missing_pdfs(monkeypatch):
    papers = [{"key": str(i), "title": str(i), "doi": str(i), "pdf": None} for i in range(5)]
    monkeypatch.setattr(run.zotero, "list_items", lambda *a: papers)
    monkeypatch.setattr(run.citations, "counts", lambda dois: {d: {"count": 10 - int(d), "fetched": "today"} for d in dois})
    fetched = []

    def fetch(paper, *args):
        fetched.append(paper["key"])
        paper["pdf_source"] = "cache" if paper["key"] != "0" else None
        paper["pdf"] = "available.pdf" if paper["key"] != "0" else None

    monkeypatch.setattr(run.zotero, "attach_pdf", fetch)
    chosen, selection = run.select_papers({"collection_key": "c", "library_id": "l"}, 50, limit=1)
    assert fetched == ["0", "1"] and chosen[0]["key"] == "1"
    assert len(selection["selected"]) == 1
    with pytest.raises(ValueError, match="positive"):
        run.select_papers({}, 50, limit=0)


def test_chunk_packing_preserves_text_headings_and_captions():
    agent = ExtractionAgent.__new__(ExtractionAgent)
    agent.profile = {"max_input_chars": 48000}
    paper = {"title": "test", "sections": [{"heading": str(i), "text": f"section{i} " * 200} for i in range(3)],
             "figures": [{"id": "F1", "caption": "the caption"}]}
    paper["sections"][1]["text"] += " Fig. 1."
    chunks = agent._chunks(paper)
    assert len(chunks) == 1
    assert "F1: the caption" in chunks[0]
    for s in paper["sections"]:
        assert f"## {s['heading']}\n{s['text'].strip()}" in chunks[0]
    agent.profile = {"max_input_chars": 1000}
    paper["sections"] = [{"heading": "Long", "text": "1234567890" * 250}]
    chunks = agent._chunks(paper)
    bodies = [c.split("## Long\n", 1)[1].strip() for c in chunks]
    assert "".join(bodies) == paper["sections"][0]["text"]
    assert all(len(c) < 1000 for c in chunks)


def test_empty_portal_results_expire_and_failures_are_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(enrichment, "CACHE", tmp_path)
    search = Mock(return_value=[])
    for _ in range(2):
        assert enrichment._portal_fetch(search, None, "portal", "voltage", False) == []
    assert search.call_count == 1
    cache = next(tmp_path.glob("portal/*.json"))
    os.utime(cache, (time.time() - 90000,) * 2)
    enrichment._portal_fetch(search, None, "portal", "voltage", False)
    assert search.call_count == 2
    search.side_effect = RuntimeError("offline")
    for _ in range(2):
        with pytest.raises(RuntimeError):
            enrichment._portal_fetch(search, None, "portal", "new query", False)
    assert len(list(tmp_path.glob("portal/*.json"))) == 1


def test_portal_jobs_are_deduplicated_across_classes(monkeypatch):
    fetch = Mock(return_value=[])
    monkeypatch.setattr(enrichment, "_portal_fetch", fetch)
    monkeypatch.setattr(enrichment, "secret", lambda name: None)
    monkeypatch.setattr(ontostore, "has_vectors", lambda: False)
    monkeypatch.setattr(ontostore, "search", lambda *a, **kw: [])
    agent = enrichment.EnrichmentAgent.__new__(enrichment.EnrichmentAgent)
    classes = [{"id": f"k{i}", "label": "solar cell", "alt_labels": [], "definitions": [], "iri": f"iri:{i}"}
               for i in range(2)]
    agent._candidates(classes)
    queries = [(c.args[3], c.args[4]) for c in fetch.call_args_list]
    assert len(queries) == len(set(queries)) and queries
    assert all(c["candidates"] == [] for c in classes)


def test_mds_search_preserves_metadata_and_propagates_failures(monkeypatch):
    response = Mock()
    props = {mds_portal._api.PROPERTY_MAP["domain"]: ["PV-Cell"]}
    response.json.return_value = {"collection": [{"@id": "https://test/term", "prefLabel": "voltage",
                                                  "links": {"ontology": "https://test/MDS"}, "properties": props,
                                                  "definition": ["a voltage"]}]}
    monkeypatch.setattr(mds_portal.requests, "get", Mock(return_value=response))
    hit = mds_portal.search("voltage")[0]
    assert hit["MDS_Domain"] == "PV-Cell" and hit["Definition"] == "a voltage"
    response.raise_for_status.side_effect = RuntimeError("offline")
    with pytest.raises(RuntimeError):
        mds_portal.search("voltage")


@pytest.mark.parametrize("pool", [3, 12, 20])
@pytest.mark.parametrize("restricted", [False, True])
@pytest.mark.parametrize("ties", [False, True])
def test_vector_search_matches_full_sort(monkeypatch, pool, restricted, ties):
    rng = np.random.default_rng(42)
    matrix = rng.normal(size=(12, 4)).astype(np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    if ties:
        matrix[1:5] = matrix[0]
    ids = [f"iri:{i}" for i in range(12)]
    onts = np.array(["BFO"] * 6 + ["other"] * 6)
    kinds = np.array(["class"] * 12)
    dep = np.array([False] * 11 + [True])
    vec = (matrix, ids, dict(zip(ids, range(12))), onts, kinds, dep)
    query = matrix[0]
    monkeypatch.setattr(ontostore, "require", lambda: None)
    monkeypatch.setattr(ontostore, "_vectors", lambda: vec)
    ontostore._search_vectors.cache_clear()
    terms = {i: {"iri": i, "label": i, "ontology": onts[n], "kind": "class", "deprecated": bool(dep[n]),
                 "definition": "", "labels": [{"text": i}]} for n, i in enumerate(ids)}
    monkeypatch.setattr(ontostore, "term", terms.get)
    monkeypatch.setattr(ontostore, "_db", lambda: None)
    options = {"ontologies": ("BFO",)} if restricted else {}
    got = ontostore.search([], query, k=12, pool=pool, nearest=3, **options)
    sims = matrix @ query / (np.linalg.norm(query) + 1e-12)
    mask = ~dep & (onts == "BFO" if restricted else True)
    masked = np.where(mask, sims, -1.)
    expected = []
    for rank, j in enumerate(np.argsort(-masked)[:pool]):
        if mask[j] and (masked[j] >= ontostore.ONTOLOGY_SEARCH["min_cosine"] or rank < 3):
            expected.append((ids[j], round(ontostore._fuse(0., 0., float(masked[j])), 3)))
    expected.sort(key=lambda x: -x[1])
    assert [(x["iri"], x["score"]) for x in got] == expected
    ontostore._search_vectors.cache_clear()
