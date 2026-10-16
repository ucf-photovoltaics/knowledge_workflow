"""Read-only joins from ontology results to canonical concepts, papers and evidence.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from dpv_dashboard import catalog, external, model


def records(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def text(value):
    return value if isinstance(value, str) else str(value or "")


def evidence_status(row):
    return row.get("evidence_status") or row.get("status") or ("verified" if row.get("verified") is True else
            "unverified" if row.get("verified") is False else "not recorded")


def upper_label(iri):
    terms = catalog.load(model.ROOT / "src/resources/upper/bfo_cco.json", {})
    return (terms.get("classes", {}).get(iri) or terms.get("properties", {}).get(iri) or {}).get("label")


def source_roots(root):
    if root is None:
        return []
    manifest = catalog.load(root / "integration.json", {})
    if not manifest:
        return [root]
    result = []
    for entry in records(manifest.get("inputs", [])):
        name = entry.get("run_id", "")
        if not isinstance(name, str) or Path(name).name != name or name in ("", ".", ".."):
            continue
        candidate = model.inside(root.parent, name)
        if (candidate / "run.json").is_file():
            result.append(candidate)
    return result


def index(root):
    if root is None:
        return _index("", ())
    paths = [root / name for name in ("run.json", "integration.json", "ingestion.json", "normalized/concepts.json",
        "normalized/concept_lineage.json", "normalized/contradictions.json", "ontology/classes.json",
        "ontology/enriched.json", "ontology/mappings.json", "ontology/uncertain.json", "ontology/review_issues.json",
        "ontology/validation.json", "mappings.json", "bridge_concepts.json", "candidates.json", "validation.json")]
    paths += sorted((root / "papers").glob("*.json"))
    paths += sorted((root / "parsed").glob("*.json"))
    signature = tuple((str(path), catalog.fingerprint(path)) for path in paths)
    return _index(str(root), signature)


@lru_cache(maxsize=8)
def _index(root, signature):
    return RunIndex(Path(root) if root else None)


class RunIndex:
    def __init__(self, root):
        self.root = root
        load = lambda name, default=None: catalog.load(root / name, default) if root else default
        self.manifest = load("run.json", {})
        self.ingestion = load("ingestion.json", {})
        self.integration = load("integration.json", {})
        self.kind = "integration" if self.integration else "run"
        self.papers = {}
        self.parsed = {}
        self.unavailable_papers = 0
        if root:
            for path in sorted((root / "parsed").glob("*.json")):
                parsed = catalog.load(path, {})
                if isinstance(parsed, dict):
                    self.parsed[parsed.get("key", path.stem)] = parsed
            for path in sorted((root / "papers").glob("*.json")):
                paper = catalog.load(path)
                if isinstance(paper, dict) and paper.get("key"):
                    self.papers[paper["key"]] = paper
                else:
                    self.unavailable_papers += 1
        self.canonical = {row["id"]: row for row in records(load("normalized/concepts.json", [])) if row.get("id")}
        self.classes = {row["id"]: row for row in records(load("ontology/classes.json", [])) if row.get("id")}
        self.enriched = {row["id"]: row for row in records(load("ontology/enriched.json", [])) if row.get("id")}
        self.mappings = records(load("mappings.json" if self.integration else "ontology/mappings.json", []))
        self.contradictions = records(load("normalized/contradictions.json", []))
        self.bridges = records(load("bridge_concepts.json", []))
        self.candidates = records(load("candidates.json", []))
        self.validation = load("validation.json" if self.integration else "ontology/validation.json", {})
        self.review = records(load("ontology/review_issues.json", []))
        uncertain = load("ontology/uncertain.json", {})
        self.uncertain = [{"stage": stage, **row} for stage, rows in uncertain.get("items", {}).items() for row in records(rows)] if isinstance(uncertain, dict) else []
        self.concepts = {**self.canonical, **self.classes, **self.enriched}
        self.iri_ids = {row["iri"]: cid for cid, row in self.concepts.items() if row.get("iri")}
        self.originals = {(paper_key, row["id"]): row for paper_key, paper in self.papers.items()
                          for row in records(paper.get("concepts", [])) if row.get("id")}
        self.lineage_present = bool(root and (root / "normalized/concept_lineage.json").is_file())
        saved = load("normalized/concept_lineage.json")
        self.lineage_readable = isinstance(saved, list)
        self.lineage = self._lineage(records(saved))
        self.by_canonical = defaultdict(list)
        for row in self.lineage:
            if row.get("canonical_id"):
                self.by_canonical[row["canonical_id"]].append(row)
        self._claims = None

    def label(self, cid):
        return self.concepts.get(cid, {}).get("label") or (upper_label(cid) if isinstance(cid, str) and cid.startswith("http") else None) or cid or "not recorded"

    def _lineage(self, saved):
        if self.lineage_present:
            result, identities = [], set()
            for row in saved:
                identity = (row.get("paper"), row.get("original_id"))
                if not all(isinstance(part, str) for part in identity) or not isinstance(row.get("canonical_id"), str):
                    result.append({**row, "canonical_id": "", "lineage_status": "unavailable (malformed saved identity)",
                                   "match_basis": "invalid saved mapping row"})
                    continue
                valid = identity in self.originals and row.get("canonical_id") in self.concepts
                status = "recorded" if valid else "recorded; source or target unavailable"
                if valid and row.get("original_label") is not None and text(self.originals[identity].get("label")).strip() != text(row["original_label"]).strip():
                    status = "recorded; source label differs"
                if valid and row.get("canonical_label") is not None and self.label(row["canonical_id"]) != row["canonical_label"]:
                    status = "recorded; target label differs"
                result.append({**row, "lineage_status": status, "match_basis": "saved normalization map"})
                identities.add(identity)
            result += [{"paper": paper, "original_id": cid, "original_label": original.get("label", ""),
                        "canonical_id": "", "canonical_label": "", "lineage_status": "unavailable (not recorded)" if self.lineage_readable else "unavailable (lineage artifact unreadable)",
                        "match_basis": "no saved mapping for this source"}
                       for (paper, cid), original in self.originals.items() if (paper, cid) not in identities]
            counts = Counter((r.get("paper"), r.get("original_id")) for r in result if r["lineage_status"] == "recorded")
            for row in result:
                if row["lineage_status"] == "recorded" and counts[(row["paper"], row["original_id"])] > 1:
                    row["lineage_status"] = "ambiguous (duplicate saved identity)"
            return result
        aliases = defaultdict(set)
        for cid, concept in self.canonical.items():
            for alias in [concept.get("label", ""), *concept.get("alt_labels", [])]:
                if isinstance(alias, str) and alias.strip():
                    aliases[alias.strip().casefold()].add(cid)
        result = []
        for (paper, original_id), original in self.originals.items():
            candidates = {cid for cid in aliases.get(text(original.get("label")).strip().casefold(), set())
                          if paper in self.canonical[cid].get("papers", [])}
            cid = next(iter(candidates)) if len(candidates) == 1 else ""
            result.append({"paper": paper, "original_id": original_id, "original_label": original.get("label", ""),
                           "canonical_id": cid, "canonical_label": self.label(cid) if cid else "",
                           "lineage_status": "reconstructed (unique label + paper)" if cid else "ambiguous" if candidates else "unavailable",
                           "candidate_ids": sorted(candidates), "match_basis": "label/alternative-label and supporting paper; merge decision not recorded"})
        return result

    def paper_rows(self):
        return [{"paper": key, "title": paper.get("title", ""), "year": paper.get("year", ""), "doi": paper.get("doi", ""),
                 "concepts": len(paper.get("concepts", [])), "relations": len(paper.get("relations", [])),
                 "causal_claims": len(paper.get("causal", [])), "measurements": len(paper.get("measurements", []))}
                for key, paper in self.papers.items()]

    @lru_cache(maxsize=256)
    def claims(self, paper=None, canonical=None):
        if self._claims is None:
            rows = []
            for key, record in self.papers.items():
                originals = {c["id"]: c.get("label", c["id"]) for c in records(record.get("concepts", [])) if c.get("id")}
                for kind, field in (("relation", "relations"), ("causal", "causal"), ("measurement", "measurements")):
                    for number, claim in enumerate(records(record.get(field, [])), 1):
                        left = claim.get("s") if kind == "relation" else claim.get("cause") if kind == "causal" else claim.get("property") or claim.get("concept")
                        right = claim.get("o") if kind == "relation" else claim.get("effect") if kind == "causal" else claim.get("entity")
                        quote = claim.get("evidence", "")
                        rows.append({"paper": key, "title": record.get("title", ""), "kind": kind, "claim_number": number,
                            "subject_id": left or "", "subject": originals.get(left, left or "not recorded"),
                            "predicate": claim.get("p") or claim.get("polarity") or "reported value",
                            "object_id": right or "", "object": originals.get(right, right or "not recorded"),
                            "value": claim.get("value", ""), "unit": claim.get("unit", ""), "condition": claim.get("condition", ""),
                            "quote": quote if isinstance(quote, str) else quote,
                            "verification": evidence_status(claim), "property_missing": claim.get("property_missing", False)})
            self._claims = rows
        rows = self._claims
        if paper:
            rows = [row for row in rows if row["paper"] == paper]
        if canonical:
            originals = {(row["paper"], row["original_id"]) for row in self.by_canonical.get(canonical, [])
                         if row["lineage_status"] == "recorded" or row["lineage_status"].startswith("reconstructed")}
            rows = [row for row in rows if (row["paper"], row["subject_id"]) in originals or (row["paper"], row["object_id"]) in originals]
        return rows

    def stage_rows(self, stage, view):
        if stage == "extract":
            return self.paper_rows() if view == "papers" else self.claims()
        if stage == "normalize":
            if view == "lineage":
                return self.lineage
            if view == "contradictions":
                return [{**row, "cause_label": self.label(row.get("cause")), "effect_label": self.label(row.get("effect")),
                         "canonical_id": row.get("cause", "")} for row in self.contradictions]
            return [{"canonical_id": cid, "label": c.get("label"), "type": c.get("type"), "alternative_labels": c.get("alt_labels", []),
                     "supporting_papers": c.get("papers", []), "rank": c.get("rank"), "importance": c.get("score"),
                     "original_occurrences": len(self.by_canonical.get(cid, []))} for cid, c in self.canonical.items()]
        if stage == "ontology":
            if view == "hierarchy":
                rows = []
                for cid, c in self.classes.items():
                    current, seen, chain = cid, set(), []
                    while current and current not in seen:
                        seen.add(current)
                        chain.append(self.label(current))
                        current = self.classes.get(current, {}).get("parent")
                    rows.append({"canonical_id": cid, "label": c.get("label"), "hierarchy_root_to_leaf": list(reversed(chain)),
                                 "cycle_detected": bool(current), "iri": c.get("iri", "")})
                return rows
            return [{"canonical_id": cid, "label": c.get("label"), "parent": self.label(c.get("parent")),
                     "parent_id_or_iri": c.get("parent"), "placement_source": c.get("parent_source", "not recorded"),
                     "parent_evidence": c.get("parent_evidence", []), "review_flags": c.get("review_flags", []),
                     "excluded": c.get("excluded", False), "iri": c.get("iri", "")} for cid, c in self.classes.items()]
        if stage == "enrich":
            rows = []
            for cid, c in self.enriched.items():
                common = {"canonical_id": cid, "label": c.get("label", "")}
                if view == "definitions":
                    rows.append({**common, "definition": c.get("definition", ""), "definition_status": c.get("definition_status", "not recorded"),
                                 "source": c.get("definition_source", ""), "source_definitions": c.get("definitions", [])})
                else:
                    for value in records(c.get(view, [])):
                        rows.append({**value, **common, "candidate_label": value.get("label", "") if view == "candidates" else "",
                                     "target_label": self.label(value.get("o")) if view == "restrictions" else value.get("label", "")})
            return rows
        if stage == "interop":
            return [{"canonical_id": m.get("id", ""), "local_label": self.label(m.get("id")),
                     "local_definition": self.concepts.get(m.get("id"), {}).get("definition", ""), "external_label": m.get("label", ""),
                     "external_definition": m.get("definition", ""), "relation": m.get("relation"), "confidence": m.get("confidence"),
                     "ontology": m.get("ontology"), "target_iri": m.get("iri"), "method": m.get("method"),
                     "scores": m.get("scores", {}), "hop": m.get("hop", 0)} for m in self.mappings]
        if stage == "integrate":
            if view == "bridges":
                return [{"bridge_label": b.get("label"), "domains": b.get("domains"), **member}
                        for b in self.bridges for member in records(b.get("members", []))]
            if view == "candidates":
                return [{"pair": c.get("id"), "decision": c.get("decision", "not recorded"), "reviewed": c.get("reviewed"),
                         "a_label": c.get("a", {}).get("label"), "a_domain": c.get("a", {}).get("domain"), "a_iri": c.get("a", {}).get("iri"),
                         "b_label": c.get("b", {}).get("label"), "b_domain": c.get("b", {}).get("domain"), "b_iri": c.get("b", {}).get("iri"),
                         "similarity": c.get("similarity"), "kind": c.get("kind")} for c in self.candidates]
            return self.mappings
        if stage == "parse":
            return [{"paper": key, "title": p.get("title", ""), **p.get("parse_stats", {}),
                     "extraction_windows": len(p["chunks"]) if isinstance(p.get("chunks"), list) else p.get("n_chunks", "not recorded")}
                    for key, p in (self.parsed or self.papers).items()]
        if stage == "ingest":
            return records(self.ingestion.get("papers", [])) or records(self.manifest.get("corpus", {}).get("selection", {}).get("selected", [])) or self.paper_rows()
        return []

    def review_rows(self, stage=None, canonical=None):
        rows = [{"source": "review_issues.json", **row} for row in self.review]
        rows += [{"source": "uncertain.json", **row} for row in self.uncertain]
        rows += [{"source": "validation.json", "stage": "integrate" if self.integration else "interop", "finding": value}
                 for value in self.validation.get("issues", [])] if isinstance(self.validation, dict) else []
        return [row for row in rows if (not stage or row.get("stage") in (None, stage)) and
                (not canonical or row.get("id") == canonical or row.get("canonical_id") == canonical)]

    def progress(self, stage):
        status = external.states(self.root, self.kind).get(stage, "waiting") if self.root else "waiting"
        if self.root:
            saved = catalog.load(self.root / "dashboard.json", {}).get("stages", {}).get(stage)
            if saved:
                status = saved.get("status", status)
        counts = {}
        if stage == "ingest":
            selection = self.ingestion.get("selection") or self.manifest.get("corpus", {}).get("selection", {})
            counts = {"selected papers": len(selection.get("selected", [])), "distinct available items": selection.get("items_in_collection", "not recorded"),
                      "skipped without PDF": len(selection.get("skipped_no_pdf", []))}
        elif stage == "parse":
            rows = self.stage_rows("parse", "parsing")
            counts = {"papers with parsing statistics": len(rows), "sections": sum(r.get("n_sections", 0) for r in rows),
                      "separate window files": len(self.parsed)}
        elif stage == "extract":
            selected = len(self.ingestion.get("papers", [])) if self.ingestion else self.manifest.get("corpus", {}).get("items", "not recorded")
            counts = {"readable saved papers": len(self.papers), "selected papers": selected,
                      "claims": len(self.claims()), "quotes needing review": sum(r["verification"] != "verified" for r in self.claims())}
            if self.unavailable_papers:
                counts["unreadable or oversized paper records"] = self.unavailable_papers
        elif stage == "normalize":
            counts = {"canonical concepts": len(self.canonical), "original occurrences": len(self.originals),
                      "contradictions": len(self.contradictions), "recorded lineage rows": sum(r["lineage_status"] == "recorded" for r in self.lineage)}
        elif stage == "ontology":
            counts = {"retained classes": sum(not c.get("excluded") for c in self.classes.values()),
                      "excluded classes": sum(bool(c.get("excluded")) for c in self.classes.values()), "fallback placements": sum(c.get("parent_source") in
                      ("type_default", "category_default", "cycle_break") for c in self.classes.values())}
        elif stage == "enrich":
            counts = dict(Counter(c.get("definition_status", "not recorded") for c in self.enriched.values()))
            counts["restrictions"] = sum(len(c.get("restrictions", [])) for c in self.enriched.values())
        elif stage in ("interop", "integrate"):
            counts = {"mappings": len(self.mappings), "validation issues": self.validation.get("n_issues", "not recorded")}
            if stage == "integrate":
                counts.update({"bridge groups": len(self.bridges), "unreviewed candidates": sum(not c.get("reviewed") for c in self.candidates)})
        else:
            counts = {"saved papers": len(self.papers)}
        return status, counts

    def narrative(self, stage):
        status, counts = self.progress(stage)
        from dpv_dashboard import presentation
        parts = [f"{presentation.friendly(name)}: {value}" for name, value in counts.items()]
        sentence = "Saved results — " + "; ".join(parts) + ". "
        if stage == "normalize":
            if self.originals and len(self.originals) >= len(self.canonical):
                sentence += f"The normalized vocabulary has {len(self.originals) - len(self.canonical)} fewer entries than the per-paper concept records; this includes repeated terms across papers. "
            sentence += ("Exact provenance is available only for valid rows in the saved normalization map. " if self.lineage_present and self.lineage_readable else
                         "The lineage artifact is unreadable; no reconstructed map is substituted. " if self.lineage_present else
                         "This older run has no exact lineage artifact; unique label-and-paper matches below are reconstructed and do not establish merge decisions. ")
        if stage in ("ontology", "enrich", "interop"):
            sentence += f"{len(self.review_rows(stage))} saved review findings are available. "
            findings = Counter(text(row.get("kind")) for row in self.review_rows(stage) if row.get("kind"))
            if findings:
                sentence += "Frequent saved review issues: " + ", ".join(f"{name} ({count})" for name, count in findings.most_common(2)) + ". "
        if stage == "interop":
            common = Counter(m.get("ontology", "unspecified") for m in self.mappings)
            if common:
                name, count = common.most_common(1)[0]
                sentence += f"{name} supplies the most mappings ({count}). "
        if stage == "extract":
            if counts.get("claims"):
                sentence += f"{counts['quotes needing review'] / counts['claims']:.0%} of saved claims need quote review; use Inspect review findings to examine them. "
            types = Counter(c.get("type", "unclassified") for c in self.originals.values())
            if types:
                sentence += "The most common extracted types are " + ", ".join(f"{k} ({v})" for k, v in types.most_common(3)) + ". "
            labels = Counter(text(c.get("label")) for c in self.originals.values() if c.get("label"))
            if labels:
                sentence += "Frequent extracted labels: " + ", ".join(f"{name} ({count})" for name, count in labels.most_common(3)) + ". "
        if stage == "integrate":
            pairs = Counter(tuple(sorted((m["a_domain"], m["b_domain"]))) for m in self.mappings
                            if isinstance(m.get("a_domain"), str) and isinstance(m.get("b_domain"), str))
            if pairs:
                pair, count = pairs.most_common(1)[0]
                sentence += f"The most connected domain pair is {' / '.join(pair)} ({count} saved mappings). "
        if stage == "parse":
            sentence += "Extraction windows may be retained inside paper records; zero separate window files does not mean zero windows. "
        if stage == "enrich":
            sentence += f"Definition statuses cover {len(self.enriched)} saved class records, including {sum(bool(c.get('excluded')) for c in self.enriched.values())} excluded records. "
        return sentence + f"Status: {presentation.friendly(status)}. Counts describe saved artifacts; recent log activity does not establish process ownership."
