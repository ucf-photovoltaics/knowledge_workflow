"""Lexical head rule: "rear AlOx passivation layer" sits under "passivation layer" when that is also a concept.

Applied only when the reading is obvious:
- the head is itself a concept of the same extracted type;
- the head is specific (several words, or one non-generic word of 5+ letters);
- no negating or prepositional modifier ("non-", "-free", "rate of degradation" is not a kind of degradation).
"""
import re

from src.agents.normalization import norm_key

GENERIC = {"system", "systems", "process", "method", "effect", "property", "material", "value", "rate", "model",
           "data", "factor", "type", "level", "layer", "structure", "device", "sample", "parameter", "condition",
           "state", "phase", "analysis", "result", "technique", "technology", "unit", "part", "area", "region"}
NEGATING = {"non", "anti", "without", "free", "pseudo", "quasi", "un", "not", "no"}
PREPOSITIONS = {"of", "in", "for", "on", "at", "by", "with", "under", "from", "to", "via", "per", "and", "or"}


def normalize(label: str) -> str:
    return norm_key(re.sub(r"\([^)]*\)", " ", label))


def clean_query(label: str) -> str:
    """A portal search query: no parentheses, LaTeX, or hyphen/underscore joins."""
    text = re.sub(r"\$[^$]*\$|\([^)]*\)|\[[^\]]*\]", " ", label)
    return re.sub(r"\s+", " ", re.sub(r"[-_/]", " ", text)).strip()


def match_key(label: str) -> str:
    """Comparable form of a label across ontologies: 'OpenCircuitVoltage' == 'open-circuit voltage (Voc)'."""
    return normalize(re.sub(r"([a-z])([A-Z])", r"\1 \2", label))


def head_query(label: str) -> str | None:
    """The general term of a long label ('rear AlOx passivation layer' -> 'passivation layer')."""
    words = clean_query(label).split()
    return " ".join(words[-2:]) if len(words) >= 3 else None


def heads(concepts: list[dict]) -> dict[str, str]:
    """child id -> head concept id, for the longest obvious head of each concept."""
    index = {}
    for c in concepts:
        index.setdefault(normalize(c["label"]), c)
    out = {}
    for c in concepts:
        words = normalize(c["label"]).split()
        for k in range(1, len(words)):  # longest head first
            head = index.get(" ".join(words[k:]))
            if head is not None and head is not c and _obvious(c, head, words[:k]):
                out[c["id"]] = head["id"]
                break
    return out


def _obvious(child: dict, head: dict, modifiers: list[str]) -> bool:
    if child.get("type") != head.get("type"):
        return False
    head_words = normalize(head["label"]).split()
    if len(head_words) == 1 and (head_words[0] in GENERIC or len(head_words[0]) < 5):
        return False
    return not any(m.strip("-") in NEGATING | PREPOSITIONS or m.endswith("free") for m in modifiers)
