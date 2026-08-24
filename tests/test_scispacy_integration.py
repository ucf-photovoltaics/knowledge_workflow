"""Real-model smoke test, skipped when the optional NLP stack is absent."""

import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("en_core_sci_md"), "scispaCy model is not installed")
class ScispacyIntegrationTests(unittest.TestCase):
    def test_real_model_extracts_scientific_entities(self) -> None:
        from kweave.tools.scispacy_tool import tag_and_link

        concepts = tag_and_link("BRCA1 is associated with breast cancer.", threshold=0.0)
        self.assertTrue(concepts)
        self.assertTrue(any(concept.span for concept in concepts))


if __name__ == "__main__":
    unittest.main()
