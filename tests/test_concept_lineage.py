"""Verify exact normalization identity and original-label provenance through downstream export.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import copy
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, SKOS

from src.agents.normalization import NormalizationAgent
from src.agents.enrichment import EnrichmentAgent
from src.agents.ontology import OntologyAgent
from src.tools import owl, upper


def concept(cid, label, synonyms=()):
    return {"id": cid, "label": label, "type": "device", "synonyms": list(synonyms),
            "definition": "", "mentions": 1, "sections": ["Introduction"], "figures": []}


def papers():
    return [{"key": "P1", "doi": "10.1234/first", "title": "First paper", "figures": [],
             "concepts": [concept("c1", "solar cells", ["PV"]), concept("c2", "silicon")],
             "relations": [], "causal": [], "measurements": []},
            {"key": "P2", "doi": "", "title": "Second paper", "figures": [],
             "concepts": [concept("c1", "solar cell", ["PV"])],
             "relations": [], "causal": [], "measurements": []}]


class OfflineNormalization(NormalizationAgent):
    def __init__(self, ledger=None):
        self.doubts = []

    def _semantic_merge(self, groups):
        self.stats["semantic_merges"] = 0
        return groups

    def _summarize(self, *args):
        return {"summary": "Offline fixture", "themes": []}


def test_exact_map_scopes_local_ids_to_their_papers():
    original = papers()
    original[1]["concepts"][0]["label"] = "PVC"
    groups = [{"label": "photovoltaic cell", "members": [("P1", original[0]["concepts"][0]),
                                                          ("P2", original[1]["concepts"][0])]},
              {"label": None, "members": [("P1", original[0]["concepts"][1])]}]
    concepts, cmap = NormalizationAgent._canonical(groups)
    lineage = NormalizationAgent._lineage(original, concepts, cmap)
    by_original = {(row["paper"], row["original_id"]): row for row in lineage}
    assert len(lineage) == 3
    assert by_original[("P1", "c1")]["canonical_id"] == by_original[("P2", "c1")]["canonical_id"]
    assert by_original[("P1", "c2")]["canonical_id"] != by_original[("P1", "c1")]["canonical_id"]
    merged = next(c for c in concepts if c["label"] == "photovoltaic cell")
    assert set(merged["alt_labels"]) == {"solar cells", "PVC", "PV"}
    assert "silicon" not in merged["alt_labels"]
    assert by_original[("P2", "c1")]["original_label"] == "PVC"
    assert by_original[("P1", "c1")]["original_synonyms"] == ["PV"]
    assert {s["paper"] for s in merged["label_sources"] if s["label"] == "PV"} == {"P1", "P2"}


def test_cleaning_and_normalization_return_recorded_lineage():
    original = papers()
    original[0]["concepts"].append(None)  # existing cleaning rejects this, not an accepted mapping
    result = OfflineNormalization().run(original)
    assert len(result["concept_lineage"]) == result["stats"]["concept_occurrences"] == 3
    assert result["stats"]["concept_lineage_records"] == 3
    canonical = {c["id"]: c for c in result["concepts"]}
    for row in result["concept_lineage"]:
        assert canonical[row["canonical_id"]]["label"] == row["canonical_label"]
        assert row["paper"] in canonical[row["canonical_id"]]["papers"]


def test_same_final_label_fold_retains_every_original():
    original = papers()
    groups = [{"label": "solar cell", "members": [("P1", original[0]["concepts"][0])]},
              {"label": None, "members": [("P2", original[1]["concepts"][0])]}]
    concepts, cmap = NormalizationAgent._canonical(groups)
    assert len(concepts) == 1
    assert set(cmap.values()) == {concepts[0]["id"]}
    assert {(s["paper"], s["concept_id"]) for s in concepts[0]["label_sources"]} == {("P1", "c1"), ("P2", "c1")}


def test_case_dedup_keeps_original_spelling_in_lineage():
    original = papers()
    original[0]["concepts"] = [concept("c1", "Solar Cell")]
    result = OfflineNormalization().run(original)
    assert len(result["concepts"]) == 1
    assert result["concepts"][0]["alt_labels"] == ["PV"]
    assert {r["original_label"] for r in result["concept_lineage"]} == {"Solar Cell", "solar cell"}


def test_invalid_identity_map_fails_with_source_identified():
    original = papers()
    with pytest.raises(ValueError, match="P1:c1"):
        NormalizationAgent._lineage(original, [], {})
    original[0]["concepts"].append(copy.deepcopy(original[0]["concepts"][0]))
    concepts, cmap = NormalizationAgent._canonical(NormalizationAgent._lexical_groups(original))
    with pytest.raises(ValueError, match="Duplicate concept id 'c1' in paper 'P1'"):
        NormalizationAgent._lineage(original, concepts, cmap)


def test_enrichment_preserves_originals_but_can_reject_synonyms():
    original = papers()
    groups = [{"label": "photovoltaic cell", "members": [("P1", original[0]["concepts"][0]),
                                                          ("P2", original[1]["concepts"][0])]}]
    concepts, _ = NormalizationAgent._canonical(groups)
    c = concepts[0]
    c.update(parent=upper.ENTITY, restrictions=[], disjoint_with=[])
    agent = object.__new__(EnrichmentAgent)
    agent._apply({"classes": [{"id": c["id"], "alt_labels": ["invented alias"]}]}, {c["id"]: c}, {})
    assert set(c["alt_labels"]) == {"solar cells", "solar cell"}
    assert "PV" not in c["alt_labels"]
    assert any(s["label"] == "PV" and s["origin"] == "extracted_synonym" for s in c["label_sources"])


def test_old_classes_without_label_sources_keep_existing_review_behavior():
    c = {"id": "k1", "label": "cell", "alt_labels": ["solar cell", "PV"], "parent": upper.ENTITY}
    object.__new__(EnrichmentAgent)._apply({"classes": [{"id": "k1", "alt_labels": ["PV"]}]}, {"k1": c}, {})
    assert c["alt_labels"] == ["PV"]
    c["alt_labels"] = ["solar cell", "PV"]
    object.__new__(EnrichmentAgent)._apply({"classes": [{"id": "k1", "alt_labels": ["PV", "solar cell"]}]}, {"k1": c}, {})
    assert c["alt_labels"] == ["PV", "solar cell"]


def test_placement_carries_label_provenance_forward():
    normalized = OfflineNormalization().run(papers())["concepts"]
    agent = object.__new__(OntologyAgent)
    agent.row_stats = {}
    agent.doubts = []
    picks = {c["id"]: {"parent": upper.ENTITY, "source": "name_match"} for c in normalized}
    with patch.object(agent, "_name_matches", return_value=picks), \
         patch.object(agent, "_pick_split", return_value={}), \
         patch.object(agent, "_pick_combined", return_value={}), \
         patch.object(agent, "_repair"), patch.object(agent, "_lexical_heads"):
        placed = agent.run(normalized, [], "fixture")
    assert {c["id"]: c["label_sources"] for c in placed} == {c["id"]: c["label_sources"] for c in normalized}


def test_owl_export_cites_label_sources_and_preserves_hidden_label_policy():
    original = papers()
    original[1]["concepts"][0]["label"] = "PVC"
    concepts, _ = NormalizationAgent._canonical([{"label": "photovoltaic cell", "members": [
        ("P1", original[0]["concepts"][0]), ("P2", original[1]["concepts"][0])]}])
    c = concepts[0]
    c.update(iri="https://example.org/Cell", parent=upper.ENTITY, excluded=False,
             score=1, tier="core", restrictions=[], disjoint_with=[])
    graph = owl.build(concepts, {}, [], original, "fixture", "fixture")
    assert owl.validate(graph, owl.serialize(graph))["valid"]
    target = URIRef(c["iri"])
    assert (target, SKOS.altLabel, Literal("solar cells", lang="en")) in graph
    assert (target, SKOS.hiddenLabel, Literal("PVC", lang="en")) in graph
    def sources(predicate, label):
        return {value for ax in graph.subjects(OWL.annotatedSource, target)
                if (ax, OWL.annotatedProperty, predicate) in graph
                and (ax, OWL.annotatedTarget, Literal(label, lang="en")) in graph
                for value in graph.objects(ax, DCTERMS.source)}
    assert sources(SKOS.altLabel, "solar cells") == {URIRef("https://doi.org/10.1234/first")}
    assert sources(SKOS.hiddenLabel, "PVC") == {Literal("zotero:P2")}
    assert sources(SKOS.hiddenLabel, "PV") == {URIRef("https://doi.org/10.1234/first"), Literal("zotero:P2")}


def test_pipeline_writer_saves_lineage_and_other_artifacts(tmp_path):
    from src import run
    original = papers()
    class SavedRun:
        dir = tmp_path
        id = "fixture"
        ledger = None
        def papers(self):
            return copy.deepcopy(original)
        def write(self, name, value):
            path = self.dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")
    with patch.object(run, "NormalizationAgent", OfflineNormalization), patch.object(run, "_uncertain"):
        run.normalize(SavedRun(), SimpleNamespace())
    saved = json.loads((tmp_path / "normalized/concept_lineage.json").read_text())
    assert len(saved) == 3
    assert (tmp_path / "normalized/concepts.json").is_file()
    assert (tmp_path / "corpus_report.md").is_file()


def test_quarantine_and_exact_lineage_work_together(tmp_path):
    from src import run
    original = papers()
    original[0]["concepts"].append(concept("bad", "repeated invalid concept " * 40))
    saved = {}
    class SavedRun:
        dir = tmp_path
        id = "combined-fixture"
        ledger = None
        def papers(self):
            return copy.deepcopy(original)
        def write(self, name, value):
            saved[name] = value
    with patch.object(run, "NormalizationAgent", OfflineNormalization), patch.object(run, "_uncertain"):
        run.normalize(SavedRun(), SimpleNamespace())
    assert len(saved["normalized/concept_lineage.json"]) == 3
    assert all(row["original_id"] != "bad" for row in saved["normalized/concept_lineage.json"])
    assert saved["extraction_review/P1.json"][0]["record"]["id"] == "bad"
    assert original[0]["concepts"][-1]["id"] == "bad"
