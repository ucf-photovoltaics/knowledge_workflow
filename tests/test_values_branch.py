"""Extraction and pipeline improvements on the values-tables branch: unfound quotes re-asked, values and ids out of
labels, section kinds, quote support, same-name external definitions, embedding thresholds, and the values workbook."""
import random
import sys
from collections import Counter
from pathlib import Path

from src import config
from src.agents import extraction
from src.agents.enrichment import EnrichmentAgent
from src.agents.extraction import ExtractionAgent, _clean_label, section_kind
from src.agents.normalization import NormalizationAgent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import review_sample  # noqa: E402

SECTION = "The TOPCon cells reached an efficiency of 25.4% under standard test conditions after firing."


def test_labels_lose_values_and_leaked_ids():
    assert _clean_label("front-side efficiency > 23%") == "front-side efficiency"
    assert _clean_label("temperature = 85 °C") == "temperature"
    assert _clean_label("n7_round_trip_efficiency") == "round trip efficiency"
    for kept in ("IEC 61215", "Ga2O3", "PV module", "c12"):
        assert _clean_label(kept) == kept


def test_section_kinds():
    assert [section_kind(h) for h in ("Abstract", "1. Introduction", "2. Experimental details", "3 Results and discussion",
                                      "Conclusions", "Acknowledgement-free heading")] == \
        ["abstract", "introduction", "methods", "results", "conclusions", "other"]


def agent(answer):
    a = object.__new__(ExtractionAgent)
    a.evidence, a.evidence_prompt = Counter(), ""
    a.call = lambda *args, **kw: answer
    return a


def test_unfound_quote_is_replaced_only_by_a_found_one():
    out = {"measurements": [{"property": "c1", "value": "25.4", "evidence": "cells reached a record 26.1% efficiency"},
                            {"property": "c1", "value": "25.4", "evidence": "cells reached a record 26.1% efficiency"}]}
    answer = {"quotes": [{"id": "m1", "evidence": "TOPCon cells reached an efficiency of 25.4%"},
                         {"id": "m2", "evidence": "efficiency was very high in every test"}]}
    a = agent(answer)
    a._fill_evidence(SECTION, out, ("measurements",), {"c1": "efficiency"}, "P1", "section 1/1", [])
    assert out["measurements"][0]["evidence"] == "TOPCon cells reached an efficiency of 25.4%"
    assert out["measurements"][1]["evidence"] == "cells reached a record 26.1% efficiency"  # new one not found either
    assert a.evidence["asked_unfound"] == 2 and a.evidence["refound"] == 1


def test_items_get_the_section_their_quote_is_in():
    paper = {"sections": [{"heading": "1. Introduction", "text": "Silicon cells dominate the market."},
                          {"heading": "3. Results", "text": SECTION}], "figures": []}
    x = {"concepts": [], "relations": [], "causal": [], "figure_links": {},
         "measurements": [{"concept": "c1", "entity": "", "value": "25.4", "evidence": "an efficiency of 25.4% under standard"}]}
    m = ExtractionAgent._finalize(x, paper)["measurements"][0]
    assert (m["section"], m["section_kind"], m["evidence_status"]) == ("3. Results", "results", "verified")


def test_quote_support_is_recorded_per_claim_and_value():
    a = object.__new__(NormalizationAgent)
    a.stats, a.row_stats = {}, {}
    a.call_rows = lambda rows, *args, **kw: [{"id": r["id"], "support": "no" if r["id"] == "r0" else "yes"} for r in rows]
    concepts = [{"id": "k1", "label": "TOPCon cell"}, {"id": "k2", "label": "efficiency"}]
    relations = [{"s": "k1", "p": "has_quality", "o": "k2", "evidence": [{"text": SECTION, "status": "verified"}]}]
    values = [{"concept": "k2", "entity": "k1", "value": "25.4", "unit": "%", "evidence": SECTION},
              {"concept": "k2", "value": "1", "evidence": "too short"}]
    a._check_support(concepts, relations, [], values)
    assert relations[0]["quote_support"] == "no" and values[0]["quote_support"] == "yes"
    assert "quote_support" not in values[1]  # no usable quote: not asked
    assert a.stats["quote_support"] == {"no": 1, "yes": 1}


def test_external_definition_is_imported_with_its_term():
    a = object.__new__(EnrichmentAgent)
    a.model_definitions, a.definition_source = False, "vllm:m"
    a.external = {"k1": {"E1": {"iri": "http://example.org/qudt/Efficiency"}}}
    c = {"id": "k1", "label": "efficiency", "alt_labels": [], "restrictions": [], "disjoint_with": [], "parent": "x"}
    a._apply({"classes": [{"id": "k1", "definition": "A ratio of output to input power.", "basis": "external",
                           "source": "E1", "category_conflict": False}]}, {"k1": c}, {})
    assert (c["definition_status"], c["definition_source"]) == ("imported", "http://example.org/qudt/Efficiency")
    a._apply({"classes": [{"id": "k1", "definition": "Something.", "basis": "external", "source": "E9",
                           "category_conflict": False}]}, {"k1": c}, {})
    assert c["definition_status"] == "none"  # an id that was not offered


def test_embedding_thresholds_follow_the_model():
    gemma = config.EMBED_MODELS["embeddinggemma"]
    assert config.EMBED["model"] == "embeddinggemma" and config.EMBED["synonym_threshold"] == gemma["synonym_threshold"]
    assert config.INTEGRATION["min_similarity"] == gemma["pair_threshold"]
    assert config.ONTOLOGY_SEARCH["min_cosine"] == gemma["store_min_cosine"]
    assert config.ONTOLOGY_STORE.name.endswith("ontology_store-embeddinggemma") or "KW_ONTOLOGY_STORE" in __import__("os").environ


def test_values_workbook_rows():
    run = {"labels": {"k1": "TOPCon cell", "k2": "efficiency"}, "titles": {"P1": "A TOPCon paper"},
           "cfg": {"model_extraction": "m"},
           "values": [{"concept": "k2", "entity": "k1", "value": "25.4", "unit": "%", "basis": "measured",
                       "evidence": SECTION, "paper": "P1"}]}
    (row, key), = review_sample.values(run, random.Random(1), 5)
    assert row["Technology"] == "TOPCon cell" and row["Basis"] == "measured in this work" and key["origin"] == "basis:measured"
    assert "values" in review_sample.CHECKS and row.keys() <= set(review_sample.COLUMNS["values"])
