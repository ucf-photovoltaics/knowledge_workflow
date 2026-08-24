"""Command-line entry point for collection processing."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from kweave.agents.extract_agent import ExtractAgent
from kweave.agents.normalization_agent import NormalizationAgent
from kweave.pipeline import run_collection
from kweave.tools.basic_extract import extract_entities, extract_relations
from kweave.tools.scispacy_tool import extract_entities as extract_scispacy_entities
from kweave.tools.zotero import ZoteroClient, ZoteroConfig


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Kweave over a Zotero collection.")
    parser.add_argument("collection_id")
    parser.add_argument("--library-id", default=os.getenv("ZOTERO_LIBRARY_ID"))
    parser.add_argument("--library-type", choices=("groups", "users"), default=os.getenv("ZOTERO_LIBRARY_TYPE", "groups"))
    parser.add_argument("--api-key", default=os.getenv("ZOTERO_API_KEY"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, default=Path("data/results/normalized.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.library_id or not args.api_key:
        raise SystemExit("Set ZOTERO_LIBRARY_ID and ZOTERO_API_KEY or pass their CLI options.")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be a positive integer")

    client = ZoteroClient(ZoteroConfig(args.library_id, args.api_key, args.library_type))
    result = run_collection(
        client,
        args.collection_id,
        ExtractAgent(
            {"baseline": extract_entities, "scispacy": extract_scispacy_entities},
            {"baseline": extract_relations},
        ),
        NormalizationAgent(),
        limit=args.limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.graph.to_dict(), indent=2), encoding="utf-8")
    print(f"Processed {len(result.papers)} papers -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
