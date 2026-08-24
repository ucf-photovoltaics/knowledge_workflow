"""Optional FastMCP exposure for the three-agent workflow."""

from __future__ import annotations

from dataclasses import asdict

from kweave.agents.extract_agent import ExtractAgent
from kweave.agents.normalization_agent import NormalizationAgent
from kweave.agents.triage_agent import TriageAgent
from kweave.contracts import ExtractionArtifact, Paper
from kweave.tools.basic_extract import extract_entities, extract_relations

try:
    from fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - exercised only without optional server dependency
    raise RuntimeError("Install Kweave with the 'mcp' extra to run the MCP server") from exc


mcp = FastMCP("Kweave")


@mcp.tool
def triage_artifact(file_path: str) -> dict:
    """Inspect a local artifact and return its pipeline dispatch decision."""
    return asdict(TriageAgent().inspect_path(file_path))


@mcp.tool
def extract_paper(key: str, title: str, text: str) -> dict:
    """Run the dependency-free extraction suite over one paper."""
    artifact = ExtractAgent(
        {"baseline": extract_entities},
        {"baseline": extract_relations},
    ).extract(Paper(key=key, title=title, full_text=text))
    return asdict(artifact)


@mcp.tool
def normalize_extractions(extractions: list[dict]) -> dict:
    """Normalize serialized extraction results into a unified graph."""
    artifacts = []
    for record in extractions:
        artifacts.append(
            ExtractionArtifact(
                paper_key=str(record["paper_key"]),
                title=str(record["title"]),
            )
        )
    return NormalizationAgent().normalize(artifacts).to_dict()


if __name__ == "__main__":
    mcp.run()
