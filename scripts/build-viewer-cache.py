"""Build portable dashboard bundles; source outputs remain read-only."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dpv_dashboard import catalog, exploration, external, research, viewer_cache, visual_graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="Only this run folder name")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--shards", type=int, default=int(os.environ.get("CLOUD_RUN_TASK_COUNT", "1")))
    parser.add_argument("--shard-index", type=int, default=int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0")))
    args = parser.parse_args()
    if args.shards < 1 or not 0 <= args.shard_index < args.shards:
        parser.error("Shard index must be in the configured shard range.")
    if not os.environ.get("DPV_VIEWER_CACHE"):
        parser.error("Set DPV_VIEWER_CACHE to a writable cache directory.")
    records = external.discover()
    selected = []
    for record in records.values():
        root = Path(record["path"])
        if record["kind"] not in ("run", "integration") or (args.only and root.name != args.only):
            continue
        for path in sorted(root.rglob("*.ttl")):
            try:
                name = viewer_cache.relative(path)
            except ValueError:
                continue
            if int(hashlib.sha256(name.encode()).hexdigest(), 16) % args.shards == args.shard_index:
                selected.append((root, path))
    if args.only and not selected and args.shards == 1:
        parser.error("The requested run has no accessible ontology files.")
    counts = {"built": 0, "unchanged": 0, "failed": 0}
    started = time.monotonic()
    for root, path in selected:
        for literature in (True, False):
            try:
                status = viewer_cache.build(root, path, literature, args.force)
                counts[status] += 1
                message = {"source": viewer_cache.relative(path), "literature": literature, "status": status}
            except Exception as error:
                counts["failed"] += 1
                message = {"source": viewer_cache.relative(path), "literature": literature,
                           "status": "failed", "error": type(error).__name__ + ": " + str(error)}
            print(json.dumps(message), flush=True)
        for function in (visual_graph.assemble, visual_graph.projection, exploration.graph, viewer_cache._asset):
            function.cache_clear()
        # Research indexes are bounded already; release their entries between ontologies.
        research._index.cache_clear()
        gc.collect()
    print(json.dumps({"totals": counts, "ontologies": len(selected),
                      "seconds": round(time.monotonic() - started, 2)}), flush=True)
    return bool(counts["failed"])


if __name__ == "__main__":
    sys.exit(main())
