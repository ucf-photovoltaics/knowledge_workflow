"""Serializable scispaCy concept extraction.

The optional NLP dependency is loaded lazily so importing Kweave does not
download a model or require scispaCy in workflows that do not use this tool.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from kweave.contracts import Entity


@dataclass(frozen=True, slots=True)
class Concept:
    """A linked concept that can cross process and persistence boundaries."""

    span: str
    start: int
    end: int
    cui: str | None
    canonical_name: str | None
    score: float | None
    aliases: tuple[str, ...] = ()


@lru_cache(maxsize=None)
def _load_pipeline(model: str, vocab: str) -> Any:
    """Load and cache a configured scispaCy pipeline."""
    try:
        import spacy
        from scispacy.abbreviation import AbbreviationDetector
    except ImportError as exc:
        raise RuntimeError(
            "scispaCy support is optional; install scispacy, spaCy, and the "
            f"{model!r} model before using tag_and_link()"
        ) from exc

    pipeline = spacy.load(model)
    if "abbreviation_detector" not in pipeline.pipe_names:
        pipeline.add_pipe("abbreviation_detector")
    if "scispacy_linker" not in pipeline.pipe_names:
        pipeline.add_pipe(
            "scispacy_linker",
            config={
                "linker_name": vocab,
                "resolve_abbreviations": True,
            },
        )
    return pipeline


def tag_and_link(
    text: str,
    model: str = "en_core_sci_md",
    vocab: str = "umls",
    threshold: float = 0.7,
) -> list[Concept]:
    """Extract entities and return their highest-scoring canonical links."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")

    pipeline = _load_pipeline(model, vocab)
    document = pipeline(text)
    linker = pipeline.get_pipe("scispacy_linker")
    concepts: list[Concept] = []

    for entity in document.ents:
        candidates = [
            (cui, float(score))
            for cui, score in getattr(entity._, "kb_ents", ())
            if float(score) >= threshold
        ]
        if not candidates:
            concepts.append(
                Concept(entity.text, entity.start_char, entity.end_char, None, None, None)
            )
            continue

        cui, score = max(candidates, key=lambda item: item[1])
        canonical = linker.kb.cui_to_entity.get(cui)
        concepts.append(
            Concept(
                span=entity.text,
                start=entity.start_char,
                end=entity.end_char,
                cui=cui,
                canonical_name=getattr(canonical, "canonical_name", None),
                score=score,
                aliases=tuple(getattr(canonical, "aliases", ()) or ()),
            )
        )

    return concepts


def extract_entities(text: str) -> list[Entity]:
    """Adapt linked concepts to the shared extract-agent entity contract."""
    return [
        Entity(
            text=concept.span,
            label=concept.canonical_name or "scientific concept",
            canonical_id=concept.cui,
            score=concept.score,
            start=concept.start,
            end=concept.end,
            source_tool="scispacy",
        )
        for concept in tag_and_link(text)
    ]
