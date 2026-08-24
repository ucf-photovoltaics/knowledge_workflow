"""Lightweight artifact inspection used before expensive parsing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import mimetypes
from pathlib import Path


class DocumentKind(StrEnum):
    """Document classes understood by the ingestion router."""

    PDF = "pdf"
    PRESENTATION = "presentation"
    TEXT = "text"
    IMAGE = "image"


@dataclass(frozen=True, slots=True)
class ArtifactInspection:
    """Serializable facts discovered without parsing document contents."""

    path: Path
    mime_type: str
    kind: DocumentKind


_SIGNATURES = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


def detect_mime_type(path: Path) -> str:
    """Return a MIME type using known magic bytes before the file extension."""

    if not path.is_file():
        raise FileNotFoundError(f"Artifact does not exist or is not a file: {path}")

    with path.open("rb") as artifact:
        prefix = artifact.read(8)

    for signature, mime_type in _SIGNATURES:
        if prefix.startswith(signature):
            return mime_type

    guessed_type, _ = mimetypes.guess_type(path.name)
    if guessed_type is None:
        raise ValueError(f"Unable to determine MIME type for artifact: {path}")
    return guessed_type


def inspect_artifact(path: str | Path) -> ArtifactInspection:
    """Inspect a local artifact and classify it for pipeline dispatch."""

    resolved_path = Path(path).expanduser().resolve()
    mime_type = detect_mime_type(resolved_path)

    if mime_type == "application/pdf":
        kind = DocumentKind.PDF
    elif mime_type in {
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }:
        kind = DocumentKind.PRESENTATION
    elif mime_type.startswith("image/"):
        kind = DocumentKind.IMAGE
    elif mime_type.startswith("text/") or mime_type in {"application/json", "application/xml"}:
        kind = DocumentKind.TEXT
    else:
        raise ValueError(f"Unsupported artifact MIME type: {mime_type}")

    return ArtifactInspection(path=resolved_path, mime_type=mime_type, kind=kind)
