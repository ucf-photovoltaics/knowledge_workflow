"""End-to-end contract test for Zotero collection processing."""

from urllib.parse import urlparse
import unittest

from kweave.agents.extract_agent import ExtractAgent
from kweave.agents.normalization_agent import NormalizationAgent
from kweave.contracts import Entity, Relation
from kweave.pipeline import run_collection
from kweave.tools.zotero import ZoteroClient, ZoteroConfig


def fake_transport(url: str, headers: dict[str, str]):
    path = urlparse(url).path
    if path.endswith("/collections"):
        return [{"key": "COLL", "data": {"name": "Collection", "parentCollection": False}}]
    if path.endswith("/collections/COLL/items"):
        return [{"key": "P1", "data": {"itemType": "journalArticle", "title": "Paper", "abstractNote": "Perovskite improves efficiency.", "DOI": "10/example"}}]
    if path.endswith("/items/P1/children"):
        return [{"key": "A1", "data": {"itemType": "attachment", "contentType": "application/pdf"}}]
    if path.endswith("/items/A1/fulltext"):
        return {"content": "Perovskite improves efficiency."}
    raise AssertionError(f"Unexpected URL: {url}")


class ZoteroPipelineTests(unittest.TestCase):
    def test_collection_flows_through_extract_and_normalize(self) -> None:
        client = ZoteroClient(ZoteroConfig("123", "secret"), transport=fake_transport)

        def entities(text: str):
            return [Entity("Perovskite", "Material", source_tool="fixture")]

        def relations(text: str, found: tuple[Entity, ...]):
            return [Relation("Perovskite", "improves", "efficiency", evidence=text, source_tool="fixture")]

        result = run_collection(
            client,
            "COLL",
            ExtractAgent({"fixture": entities}, {"fixture": relations}),
            NormalizationAgent(),
        )

        self.assertEqual("P1", result.papers[0].key)
        self.assertEqual("perovskite", result.graph.entities[0].text)
        self.assertEqual("improves", result.graph.relations[0].predicate)


if __name__ == "__main__":
    unittest.main()
