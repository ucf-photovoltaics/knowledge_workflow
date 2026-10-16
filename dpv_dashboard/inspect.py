"""Readable, evidence-derived summaries and artifact table views.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

import json
from collections import Counter
import pandas as pd
from dpv_dashboard.model import read, artifact_files


def rows(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [{"field": k, "value": v} for k, v in value.items()]
    return [{"value": value}]


def table(value):
    records = rows(value)
    return pd.DataFrame([{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                          for k, v in (r if isinstance(r, dict) else {"value": r}).items()} for r in records])


def summary(folder, stage):
    if not folder:
        return "Select a project and domain to inspect its outputs. Results will appear as the workflow progresses."
    files = artifact_files(folder, stage)
    if not files:
        return "No outputs have been saved for this stage in the selected attempt. Run the preceding stages to prepare its inputs."
    if stage == "ingest":
        data = read(folder / "ingestion.json", {})
        selection = data.get("selection", {})
        return (f"This domain selected {len(data.get('papers', [])):,} papers with PDFs from "
                f"{selection.get('items_in_collection', 0):,} distinct papers across "
                f"{len(selection.get('expanded_collections', []))} collections including descendants. "
                f"The selection ranks citations across the whole domain; {len(selection.get('skipped_no_pdf', []))} "
                f"higher-ranked papers were passed over because no PDF was available. "
                f"{selection.get('duplicate_memberships', 0)} duplicate collection memberships were consolidated.")
    if stage == "parse":
        parsed = [read(p, {}) for p in files]
        return (f"Parsed {len(parsed)} papers into {sum(len(p.get('sections', [])) for p in parsed):,} sections and "
                f"{sum(len(p.get('chunks', [])) for p in parsed):,} extraction windows, retaining "
                f"{sum(p.get('parse_stats', {}).get('chars_kept', 0) for p in parsed):,} characters and "
                f"{sum(len(p.get('figures', [])) for p in parsed)} figure captions. These windows use the existing extraction chunker.")
    if stage in ("extract", "normalize"):
        if stage == "extract":
            papers = [read(p, {}) for p in folder.glob("papers/*.json")]
            concepts = [c for p in papers for c in p.get("concepts", [])]
            relations = [r for p in papers for r in p.get("relations", [])]
            causal = [c for p in papers for c in p.get("causal", [])]
        else:
            concepts = read(folder / "normalized/concepts.json", [])
            relations = read(folder / "normalized/relations.json", [])
            causal = read(folder / "normalized/causal.json", [])
        types = Counter(str(c.get("type") or "unclassified") for c in concepts)
        labels = Counter(str(c.get("label", "")) for c in concepts)
        common = ", ".join(f"{k} ({v})" for k, v in types.most_common(3)) or "not yet available"
        topics = ", ".join(k for k, v in labels.most_common(4)) or "not yet available"
        return (f"The saved outputs contain {len(concepts):,} concepts, {len(relations):,} relations and {len(causal):,} causal claims. "
                f"The most frequent concept types are {common}; frequent labels include {topics}. "
                "These counts describe the saved artifacts and do not establish extraction completeness or semantic correctness.")
    if stage in ("ontology", "enrich", "interop"):
        classes = read(folder / ("ontology/classes.json" if stage == "ontology" else "ontology/enriched.json"), [])
        live = [c for c in classes if not c.get("excluded")]
        categories = Counter(str(c.get("bfo_category") or c.get("category") or c.get("type") or "unclassified") for c in live)
        mappings = read(folder / "ontology/mappings.json", []) if stage == "interop" else []
        targets = Counter(str(m.get("target_ontology") or m.get("ontology") or "unspecified") for m in mappings)
        detail = f" The most-used mapping ontology is {targets.most_common(1)[0][0]}." if targets else ""
        return (f"This attempt contains {len(live):,} retained classes and {len(classes) - len(live)} excluded concepts. "
                f"The leading category is {categories.most_common(1)[0][0] if categories else 'not yet available'}. "
                f"There are {sum(bool(c.get('definition')) for c in live):,} definitions, "
                f"{sum(len(c.get('restrictions', [])) for c in live):,} relation restrictions and "
                f"{len(mappings):,} finalized external mappings.{detail} Review flags and source evidence remain available below.")
    if stage == "integrate":
        mappings = read(folder / "mappings.json", [])
        bridges = read(folder / "bridge_concepts.json", [])
        return f"Integration produced {len(mappings):,} cross-domain mappings and {len(bridges):,} bridge concept groups. The merged ontology can be explored in WebVOWL below."
    return f"This project has {len(files):,} report and figure artifacts available. Select a report, figure, or table to inspect and download its saved results."
