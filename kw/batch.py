# -*- coding: utf-8 -*-
"""
Batch runner: queue a list of Zotero collections through the pipeline, one at a
time. Sequential by design — a single laptop GPU + single Ollama server make
parallel runs slower and risk CUDA OOM, and sequential keeps the shared
benchmark CSV append-safe.

  python -m kw.batch K7LGYHKZ ABC123 DEF456        # keys (or names) as args
  python -m kw.batch --file collections.txt         # one per line
  python -m kw.batch --all                           # every collection in the library
  python -m kw.batch --file collections.txt --limit 20 --top-n 40 --no-lora

--file: one collection per line; blank lines and #comments are ignored. Each
entry may be a Zotero collection KEY or a collection NAME (names are resolved
against the library). Runs continue past a failure unless --stop-on-error; a
summary is printed at the end and the per-run benchmark row is appended as usual.
"""
import argparse
import sys
import time
import traceback


def _read_file(path: str) -> list[str]:
    out: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.split("#", 1)[0].strip()
            if s:
                out.append(s)
    return out


def _resolve(tokens: list[str]) -> list[tuple[str, str]]:
    """Map each token (collection KEY or NAME) to (key, label)."""
    from kw import zotero
    name_to_key = zotero.get_collection_map()        # {name: key}
    keys = set(name_to_key.values())
    resolved: list[tuple[str, str]] = []
    for t in tokens:
        if t in keys:
            resolved.append((t, t))                   # already a key
        elif t in name_to_key:
            resolved.append((name_to_key[t], t))      # name -> key
        else:
            resolved.append((t, t))                   # unknown: pass through (pipeline warns)
    return resolved


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="kw.batch",
        description="Queue multiple Zotero collections through the pipeline sequentially.")
    ap.add_argument("collections", nargs="*", help="Collection keys or names.")
    ap.add_argument("--file", help="File with one collection key/name per line (# comments ok).")
    ap.add_argument("--all", action="store_true", help="Run every collection in the library.")
    ap.add_argument("--outputs", default=None, help="Output directory (default: outputs/).")
    ap.add_argument("--no-diagram", action="store_true")
    ap.add_argument("--no-lora", action="store_true")
    ap.add_argument("--no-visual", action="store_true")
    # Dials (None => config default), mirror `python -m kw run`.
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--top-n", type=int, default=None, dest="top_n")
    ap.add_argument("--min-relevance", type=float, default=None, dest="min_relevance")
    ap.add_argument("--max-concepts", type=int, default=None, dest="max_concepts")
    ap.add_argument("--stop-on-error", action="store_true",
                    help="Abort the queue on the first failure (default: continue).")
    a = ap.parse_args()

    tokens = list(a.collections)
    if a.file:
        tokens += _read_file(a.file)

    from kw import zotero, pipeline
    if a.all:
        tokens += list(zotero.get_collection_map().values())

    seen: set[str] = set()
    tokens = [t for t in tokens if not (t in seen or seen.add(t))]   # de-dup, keep order
    if not tokens:
        sys.exit("No collections given. Pass keys/names as args, --file, or --all.")

    queue = _resolve(tokens)
    print(f"[batch] queued {len(queue)} collection(s)")

    results = []
    for i, (key, label) in enumerate(queue, 1):
        bar = "=" * 70
        print(f"\n{bar}\n[batch {i}/{len(queue)}] {label} ({key})\n{bar}")
        t0 = time.time()
        try:
            r = pipeline.run(
                key, outputs_dir=a.outputs,
                emit_diagram=not a.no_diagram, do_lora=not a.no_lora,
                emit_visual=not a.no_visual,
                limit=a.limit, top_n=a.top_n,
                min_relevance=a.min_relevance, max_concepts=a.max_concepts,
            )
            dt = time.time() - t0
            results.append((label, key, "OK", len(r.get("concepts") or []), dt, ""))
            print(f"[batch {i}/{len(queue)}] OK in {dt:.0f}s")
        except Exception as exc:                       # noqa: BLE001
            dt = time.time() - t0
            results.append((label, key, "FAIL", 0, dt, str(exc)))
            print(f"[batch {i}/{len(queue)}] FAILED in {dt:.0f}s: {exc}")
            traceback.print_exc()
            if a.stop_on_error:
                print("[batch] --stop-on-error set; aborting remaining queue.")
                break

    ok = sum(1 for r in results if r[2] == "OK")
    print(f"\n{'='*70}\n[batch] summary — {ok}/{len(results)} succeeded\n{'='*70}")
    for label, key, status, ncon, dt, err in results:
        line = f"  {status:4} {label[:45]:45} {ncon:4} concepts  {dt:6.0f}s"
        if err:
            line += f"  | {err[:60]}"
        print(line)
    return 0 if ok == len(results) and results else 1


if __name__ == "__main__":
    raise SystemExit(main())
