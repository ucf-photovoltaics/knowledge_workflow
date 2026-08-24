"""Tests for artifact inspection and initial pipeline routing."""

from pathlib import Path
import tempfile
import unittest

from kweave.agents.triage_agent import PipelineTarget, triage


class TriageAgentTests(unittest.TestCase):
    def test_pdf_signature_wins_over_misleading_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "paper.txt"
            artifact.write_bytes(b"%PDF-1.7\n")

            decision = triage(artifact)

        self.assertEqual("application/pdf", decision.inspection.mime_type)
        self.assertEqual(PipelineTarget.ACADEMIC_PAPER, decision.target)

    def test_presentation_routes_to_presentation_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "slides.pptx"
            artifact.write_bytes(b"PK")

            decision = triage(artifact)

        self.assertEqual(PipelineTarget.PRESENTATION, decision.target)

    def test_missing_artifact_fails_fast(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "does not exist"):
            triage("missing-paper.pdf")

    def test_unknown_type_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact.unknown"
            artifact.write_bytes(b"unknown")

            with self.assertRaisesRegex(ValueError, "Unable to determine MIME type"):
                triage(artifact)


if __name__ == "__main__":
    unittest.main()
