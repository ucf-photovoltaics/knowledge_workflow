"""Alignment replies may reference only candidates shown in the current batch."""
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agents.interoperability import InteroperabilityAgent


def candidate(label_match=False):
    return {"label": "external material", "ontology": "BFO", "definition": "A material entity.",
            "iri": "https://test.example/external", "score": .8, "label_match": label_match}


def concept(cid, candidates=None, excluded=False):
    return {"id": cid, "label": cid, "iri": "https://test.example/" + cid,
            "parent": None, "excluded": excluded, "candidates": candidates or []}


def mapping(cid, n=1, relation="close"):
    return {"id": cid, "candidate": n, "relation": relation}


class AlignmentTests(unittest.TestCase):
    def align(self, classes, replies, local=False, screening=None, batch=20):
        agent = InteroperabilityAgent.__new__(InteroperabilityAgent)
        agent.stats = Counter()
        agent.call = Mock(side_effect=replies)
        agent.call_rows = Mock(return_value=screening or [])
        with patch("src.agents.interoperability.tier", return_value="local" if local else "remote"), \
                patch("src.agents.interoperability.label_of", return_value="root"), \
                patch("src.agents.interoperability.BATCH", batch), \
                patch("src.agents.interoperability.ontostore.term", side_effect=lambda iri: {
                    "iri": iri, "label": "external material", "ontology": "BFO", "kind": "class",
                    "definition": "A material entity.", "labels": [], "deprecated": False}):
            return agent.align(classes)

    def test_no_candidate_class_reply_does_not_crash(self):
        classes = [concept("k1", [candidate()]), concept("k345")]
        result = self.align(classes, [{"mappings": [mapping("k345"), mapping("k1")]}])
        self.assertEqual([m["id"] for m in result], ["k1"])

    def test_class_from_another_batch_is_not_accepted(self):
        classes = [concept("k1", [candidate()]), concept("k2", [candidate()])]
        result = self.align(classes, [{"mappings": [mapping("k2")]}, {"mappings": []}], batch=1)
        self.assertEqual(result, [])

    def test_unknown_excluded_and_invalid_candidates_are_ignored(self):
        classes = [concept("k1", [candidate()]), concept("excluded", [candidate()], True)]
        replies = [mapping("unknown"), mapping("excluded"), mapping("k1", 0), mapping("k1", 2),
                   mapping("k1", -1), mapping("k1", "invalid"), mapping("k1", None), mapping("k1", 1, "invalid")]
        self.assertEqual(self.align(classes, [{"mappings": replies}]), [])

    def test_screened_class_and_screened_candidate_are_ignored(self):
        classes = [concept("k1", [candidate(), candidate()]), concept("k345", [candidate()])]
        screening = [{"id": "k1", "candidates": [1]}, {"id": "k345", "candidates": []}]
        replies = [mapping("k345"), mapping("k1", 2), mapping("k1")]
        result = self.align(classes, [{"mappings": replies}], local=True, screening=screening)
        self.assertEqual([m["id"] for m in result], ["k1"])

    def test_valid_mapping_normalization_and_downgrade_are_preserved(self):
        result = self.align([concept("k1", [candidate()])],
                            [{"mappings": [mapping(["k1"], relation=["EXACT"])]}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["relation"], "close")
        self.assertEqual(result[0]["downgraded_from"], "exact")
        self.assertEqual(result[0]["confidence"], .8)

if __name__ == "__main__": unittest.main()
