"""Conservative malformed-concept checks; flag for review rather than repair labels."""
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


def quarantine(record):
    """Copy valid outputs; preserve rejected rows and their dependent links for review."""
    result = dict(record)
    prior = record.get("quality_review")
    review = [r for r in prior if isinstance(r, dict) and isinstance(r.get("kind"), str)] if isinstance(prior, list) else []
    bad = set()
    for field in ("concepts", "new_concepts"):
        if field not in record:
            continue
        kept = []
        values = record.get(field)
        if values is not None and not isinstance(values, list):
            review.append({"kind": "malformed_concept", "reasons": ["malformed_label"], "record": values})
        for item in values if isinstance(values, list) else []:
            if not isinstance(item, dict):
                review.append({"kind": "malformed_concept", "reasons": ["malformed_label"], "record": item})
                continue
            reasons = concept_issues(item)
            if reasons:
                synonyms = item.get("synonyms") if isinstance(item.get("synonyms"), list) else []
                bad.update(v.strip() for v in [item.get("id"), item.get("label"), *synonyms]
                           if isinstance(v, str) and v.strip())
                review.append({"kind": "malformed_concept", "reasons": reasons, "record": item})
            else:
                kept.append(dict(item))
        result[field] = kept
    # Labels remain comparable across passes; local IDs do not survive renumbering/merging.
    for item in review:
        value = item.get("record")
        if item.get("kind") == "malformed_concept" and isinstance(value, dict):
            value = value.get("label")
            if isinstance(value, str) and value.strip():
                bad.add(value.strip())
    fields = {"relations": ("s", "o"), "causal": ("cause", "effect"), "causal_statements": ("cause", "effect"),
              "causal_claims": ("cause", "effect"), "measurements": ("property", "entity", "concept")}
    for field, references in fields.items():
        if field not in record:
            continue
        kept = []
        values = record.get(field)
        if values is not None and not isinstance(values, list):
            review.append({"kind": "dependent_" + field, "reasons": ["extraction_quarantined"], "record": values})
        for item in values if isinstance(values, list) else []:
            invalid = not isinstance(item, dict)
            if not invalid:
                invalid = any(value is not None and value != "" and (not isinstance(value, str) or value.strip() in bad or label_issues(value))
                              for value in (item.get(key) for key in references))
            if invalid:
                review.append({"kind": "dependent_" + field, "reasons": ["extraction_quarantined"], "record": item})
            else:
                kept.append(dict(item))
        result[field] = kept
    if "figures" in record:
        figures = []
        values = record["figures"]
        if values is not None and not isinstance(values, list):
            review.append({"kind": "dependent_figures", "reasons": ["extraction_quarantined"], "record": values})
        for figure in values if isinstance(values, list) else []:
            if not isinstance(figure, dict):
                continue
            value = dict(figure)
            links = value.get("concepts") or []
            if isinstance(links, list):
                value["concepts"] = [link for link in links if isinstance(link, str) and link.strip() not in bad and not label_issues(link)]
                if value["concepts"] != links:
                    review.append({"kind": "dependent_figures", "reasons": ["extraction_quarantined"], "record": figure})
            figures.append(value)
        result["figures"] = figures
    result["quality_review"] = review
    result["checks"] = {**record.get("checks", {}), "quality_rejected_concepts": sum(r["kind"] == "malformed_concept" for r in review),
                        "quality_rejected_links": sum(r["kind"].startswith("dependent_") for r in review)}
    return result
