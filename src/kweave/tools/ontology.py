"""Load and search local Turtle ontology assets without third-party dependencies."""

from __future__ import annotations

from pathlib import Path
import re


_LABEL = re.compile(r"(?P<iri><[^>]+>|[A-Za-z][\w-]*:[\w.-]+)\s+[^.]*?rdfs:label\s+\"(?P<label>[^\"]+)\"", re.DOTALL)


def ontology_files(directory: str | Path) -> tuple[Path, ...]:
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"Ontology directory does not exist: {root}")
    return tuple(sorted(root.glob("*.ttl")))


def search_labels(directory: str | Path, query: str) -> list[tuple[str, str, str]]:
    if not query.strip():
        raise ValueError("query must be non-empty")
    needle = query.casefold()
    matches: list[tuple[str, str, str]] = []
    for path in ontology_files(directory):
        text = path.read_text(encoding="utf-8")
        for match in _LABEL.finditer(text):
            if needle in match.group("label").casefold():
                matches.append((path.name, match.group("iri"), match.group("label")))
    return matches
