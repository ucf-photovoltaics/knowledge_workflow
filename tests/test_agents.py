"""Focused contracts for extraction and normalization agents."""

import unittest

from kweave.agents.extract_agent import ExtractAgent
from kweave.agents.normalization_agent import NormalizationAgent
from kweave.contracts import Entity, ExtractionArtifact, Paper, Relation


class AgentTests(unittest.TestCase):
    def test_optional_extract_tool_failure_is_recorded(self) -> None:
        def broken(text: str):
            raise RuntimeError("model missing")

        result = ExtractAgent({"optional": broken}).extract(Paper("P", "Paper", abstract="text"))
        self.assertEqual(("optional: model missing",), result.errors)

    def test_normalizer_deduplicates_and_canonicalizes(self) -> None:
        artifacts = [
            ExtractionArtifact(
                "P",
                "Paper",
                entities=(Entity(" Perovskite ", "Material", score=0.8), Entity("perovskite", "material", score=0.9)),
                relations=(Relation("Perovskite", "improves efficiency", "Cell"),),
            )
        ]
        graph = NormalizationAgent(predicate_canonicalizer=lambda value: value.replace(" ", "_")).normalize(artifacts)
        self.assertEqual(1, len(graph.entities))
        self.assertEqual("improves_efficiency", graph.relations[0].predicate)


if __name__ == "__main__":
    unittest.main()
