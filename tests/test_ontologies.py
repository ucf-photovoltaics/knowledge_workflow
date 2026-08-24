"""Local ontology asset checks."""

from pathlib import Path
import unittest

from kweave.tools.ontology import ontology_files, search_labels


ONTOLOGIES = Path(__file__).resolve().parents[1] / "data" / "ontologies"


class OntologyTests(unittest.TestCase):
    def test_requested_turtle_assets_are_present(self) -> None:
        names = {path.name for path in ontology_files(ONTOLOGIES)}
        self.assertTrue({"cco-merged.ttl", "mds-onto-0.3.1.31.ttl", "qudt-3.5.0.ttl", "iof-core.ttl"} <= names)

    def test_local_labels_are_searchable(self) -> None:
        self.assertTrue(search_labels(ONTOLOGIES, "material"))


if __name__ == "__main__":
    unittest.main()
