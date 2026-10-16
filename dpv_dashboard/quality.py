"""Conservative malformed-concept checks; flag for review rather than repair labels.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import re
from collections import Counter

MAX_LABEL_CHARS = 240
MAX_LABEL_WORDS = 32
BLOCKING_FLAGS = {"malformed_label", "label_too_long", "label_word_limit", "repeated_label_text", "extraction_quarantined", "degenerate_output"}


def label_issues(value):
    if not isinstance(value, str) or not value.strip():
        return ["malformed_label"]
    words = re.findall(r"\w+", value.casefold())
    issues = []
    if len(value) > MAX_LABEL_CHARS:
        issues.append("label_too_long")
    if len(words) > MAX_LABEL_WORDS:
        issues.append("label_word_limit")
    if len(words) >= 12 and max(Counter(tuple(words[i:i + 4]) for i in range(len(words) - 3)).values(), default=0) >= 3:
        issues.append("repeated_label_text")
    return issues


def concept_issues(record):
    issues = label_issues(record.get("label"))
    for field in ("synonyms", "alt_labels"):
        aliases = record.get(field, [])
        if aliases is None:
            aliases = []
        if not isinstance(aliases, list) or any(label_issues(alias) for alias in aliases):
            issues.append("malformed_alias")
    if record.get("quality_flags") or record.get("quality_status") in ("quarantined", "rejected"):
        issues.append("extraction_quarantined")
    if record.get("excluded") is True:
        issues.append("excluded_source_record")
    flags = record.get("review_flags", [])
    flags = [flags] if isinstance(flags, str) else flags if isinstance(flags, list) else []
    issues += [flag for flag in flags if isinstance(flag, str) and flag in BLOCKING_FLAGS]
    return sorted(set(issues))


def bounded(value, limit=160):
    text = value if isinstance(value, str) else ""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")
