"""Free-form parent answers from small models are read tolerantly, but never guessed."""
import unittest

from src.agents.ontology import CATEGORIES, OntologyAgent, answer_texts


class ParentAnswerTests(unittest.TestCase):
    def setUp(self):
        a = OntologyAgent.__new__(OntologyAgent)
        a.roots = {"material entity": CATEGORIES["material entity"], "quality": CATEGORIES["quality"]}
        a.by_id = {"k1": {"label": "battery"}, "k38": {"label": "cell"}}
        a.cands = {"k1": [{"iri": "http://x/Artifact", "label": "Material Artifact", "definition": ""},
                            {"iri": "http://x/Frame", "label": "Widget Assembly Frame", "definition": ""}]}
        self.a = a

    def test_readings(self):
        self.assertEqual(answer_texts("U:Material Artifact - An artifact that")[0], "Material Artifact")
        self.assertIn("Material Artifact", answer_texts("UMaterial Artifact"))
        self.assertIn("material entity", answer_texts("Material Artifact (or U:material entity)"))
        self.assertNotIn("k442", answer_texts("made_of(k442)"))

    def test_resolve(self):
        r = self.a._resolve
        self.assertEqual(r("k1", "U:Material Artifact - def"), ("http://x/Artifact", "candidate"))
        self.assertEqual(r("k1", "UMaterial Artifact"), ("http://x/Artifact", "candidate"))
        self.assertEqual(r("k1", "Material Artifact (or U:material entity)"), ("http://x/Artifact", "candidate"))
        self.assertEqual(r("k1", "u:k38"), ("k38", "corpus"))
        self.assertEqual(r("k1", "U:quality"), (CATEGORIES["quality"], "root"))
        self.assertEqual(r("k1", "Widget-Assembly Frames"), ("http://x/Frame", "fuzzy"))
        self.assertEqual(r("k1", "Biodiesel Generator - A type of electrical generator"), (None, "unresolved"))
        self.assertEqual(r("k1", None), (None, "no_answer"))


if __name__ == "__main__":
    unittest.main()
