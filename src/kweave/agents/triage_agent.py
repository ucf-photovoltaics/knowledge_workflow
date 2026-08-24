"""Pipeline dispatch decisions for inspected artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from kweave.contracts import Paper
from kweave.tools.triage import ArtifactInspection, DocumentKind, inspect_artifact


class PipelineTarget(StrEnum):
    """Downstream pipelines currently exposed by the triage agent."""

    ACADEMIC_PAPER = "academic_paper"
    PRESENTATION = "presentation"
    IMAGE_VISION = "image_vision"
    DIRECT_TEXT = "direct_text"


class DocumentGenre(StrEnum):
    ACADEMIC_PAPER = "academic_paper"
    PRESENTATION = "presentation"
    IMAGE = "image"
    PLAIN_TEXT = "plain_text"


class LayoutComplexity(StrEnum):
    STRUCTURED = "structured"
    SIMPLE = "simple"
    VISUAL = "visual"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DispatchDecision:
    """A reviewable routing decision made from an artifact inspection."""

    inspection: ArtifactInspection | None
    target: PipelineTarget
    reason: str
    genre: DocumentGenre
    layout: LayoutComplexity


_TARGET_BY_KIND = {
    DocumentKind.PDF: PipelineTarget.ACADEMIC_PAPER,
    DocumentKind.PRESENTATION: PipelineTarget.PRESENTATION,
    DocumentKind.IMAGE: PipelineTarget.IMAGE_VISION,
    DocumentKind.TEXT: PipelineTarget.DIRECT_TEXT,
}


def triage(path: str | Path) -> DispatchDecision:
    """Inspect an artifact and select its initial downstream pipeline."""

    inspection = inspect_artifact(path)
    target = _TARGET_BY_KIND[inspection.kind]
    genre_by_kind = {
        DocumentKind.PDF: DocumentGenre.ACADEMIC_PAPER,
        DocumentKind.PRESENTATION: DocumentGenre.PRESENTATION,
        DocumentKind.IMAGE: DocumentGenre.IMAGE,
        DocumentKind.TEXT: DocumentGenre.PLAIN_TEXT,
    }
    layout_by_kind = {
        DocumentKind.PDF: LayoutComplexity.STRUCTURED,
        DocumentKind.PRESENTATION: LayoutComplexity.VISUAL,
        DocumentKind.IMAGE: LayoutComplexity.VISUAL,
        DocumentKind.TEXT: LayoutComplexity.SIMPLE,
    }
    return DispatchDecision(
        inspection=inspection,
        target=target,
        reason=f"Detected {inspection.mime_type} and classified it as {inspection.kind.value}.",
        genre=genre_by_kind[inspection.kind],
        layout=layout_by_kind[inspection.kind],
    )


class TriageAgent:
    """Classify both local artifacts and papers already ingested from Zotero."""

    def inspect_path(self, path: str | Path) -> DispatchDecision:
        return triage(path)

    def inspect_paper(self, paper: Paper) -> DispatchDecision:
        has_text = bool((paper.full_text or paper.abstract).strip())
        reason = "Zotero supplied indexed full text." if paper.full_text else "Using Zotero abstract text."
        if not has_text:
            reason = "Zotero supplied metadata but no extractable text."
        return DispatchDecision(
            inspection=None,
            target=PipelineTarget.DIRECT_TEXT,
            reason=reason,
            genre=DocumentGenre.ACADEMIC_PAPER,
            layout=LayoutComplexity.STRUCTURED if paper.full_text else LayoutComplexity.UNKNOWN,
        )
