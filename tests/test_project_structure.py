"""Project-layout contract tests."""

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProjectStructureTests(unittest.TestCase):
    """Keep the directories required by the project-structure card available."""

    def test_required_directories_exist(self) -> None:
        required_directories = (
            "src/kweave/agents",
            "src/kweave/tools",
            "src/kweave/evals",
            "data/ontologies",
            "data/input",
            "data/results",
        )

        missing = [
            relative_path
            for relative_path in required_directories
            if not (PROJECT_ROOT / relative_path).is_dir()
        ]

        self.assertEqual([], missing, f"Missing required directories: {missing}")


if __name__ == "__main__":
    unittest.main()
