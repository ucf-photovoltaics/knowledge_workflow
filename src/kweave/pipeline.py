"""End-to-end Zotero → triage → extract → normalize orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from kweave.agents.extract_agent import ExtractAgent
from kweave.agents.normalization_agent import NormalizationAgent
from kweave.agents.triage_agent import DispatchDecision, TriageAgent
from kweave.contracts import ExtractionArtifact, NormalizedGraph, Paper
from kweave.tools.zotero import ZoteroClient


@dataclass(frozen=True, slots=True)
class PipelineResult:
    papers: tuple[Paper, ...]
    triage: tuple[DispatchDecision, ...]
    extractions: tuple[ExtractionArtifact, ...]
    graph: NormalizedGraph


def run_collection(
    zotero: ZoteroClient,
    collection_id: str,
    extractor: ExtractAgent,
    normalizer: NormalizationAgent,
    limit: int | None = None,
    triage_agent: TriageAgent | None = None,
) -> PipelineResult:
    papers = tuple(zotero.get_collection(collection_id, limit=limit).values())
    active_triage = triage_agent or TriageAgent()
    decisions = tuple(active_triage.inspect_paper(paper) for paper in papers)
    extractions = tuple(extractor.extract(paper) for paper in papers)
    graph = normalizer.normalize(extractions)
    return PipelineResult(papers, decisions, extractions, graph)
