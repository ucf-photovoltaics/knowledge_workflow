"""Contract tests for the optional scispaCy extraction tool."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from kweave.tools.scispacy_tool import Concept, tag_and_link


class _FakePipeline:
    def __init__(self) -> None:
        entity = SimpleNamespace(
            text="BRCA1",
            start_char=0,
            end_char=5,
            _=SimpleNamespace(kb_ents=(("C0677776", 0.95),)),
        )
        self.document = SimpleNamespace(ents=(entity,))
        record = SimpleNamespace(canonical_name="BRCA1 gene", aliases=("BRCA1",))
        self.linker = SimpleNamespace(
            kb=SimpleNamespace(cui_to_entity={"C0677776": record})
        )

    def __call__(self, text: str):
        return self.document

    def get_pipe(self, name: str):
        self.assert_pipe_name = name
        return self.linker


class ScispacyToolTests(unittest.TestCase):
    def test_returns_serializable_concept_contract(self) -> None:
        with patch(
            "kweave.tools.scispacy_tool._load_pipeline",
            return_value=_FakePipeline(),
        ):
            concepts = tag_and_link("BRCA1 is associated with breast cancer.")

        self.assertEqual(
            Concept(
                span="BRCA1",
                start=0,
                end=5,
                cui="C0677776",
                canonical_name="BRCA1 gene",
                score=0.95,
                aliases=("BRCA1",),
            ),
            concepts[0],
        )

    def test_rejects_invalid_input_before_loading_model(self) -> None:
        with self.assertRaises(ValueError):
            tag_and_link("   ")
        with self.assertRaises(ValueError):
            tag_and_link("text", threshold=1.1)


if __name__ == "__main__":
    unittest.main()

