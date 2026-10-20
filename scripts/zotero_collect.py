"""Build one Zotero collection from several, for a domain larger than any single collection (e.g. TEA-Extended).

  python scripts/zotero_collect.py --into 2189702 --name TEA-Extended --from 2189702:22PUQURH 37619:IEA_KEY ... \
      --exclude 2189702:QWNMWBPD 6423676:4JRCEDBH        # plan only: what would be added and copied
  python scripts/zotero_collect.py ... --apply           # create the collection and fill it

Reads the top-level items of each --from collection (group libraries). An item already in the target library is
added to the new collection; an item from another library is copied there (metadata, then its stored PDF, which uses
the target library's file storage). Items whose DOI or title is in an --exclude collection are left out, so the domain
shares no papers with the other domains of its use case. Sources are never changed. Rerunning adds only what is missing.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import argparse
import re
import sys
import tempfile
from pathlib import Path

from pyzotero import zotero

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import secret  # noqa: E402

SKIP_TYPES = ("attachment", "note", "annotation")
READ_ONLY = ("key", "version", "collections", "relations", "dateAdded", "dateModified")
STORED = ("imported_file", "imported_url")
_clients = {}


def client(library: str) -> zotero.Zotero:
    if library not in _clients:
        _clients[library] = zotero.Zotero(library, "group", secret("ZOTERO_API_KEY"))
    return _clients[library]


def ids(data: dict) -> set[str]:
    """Identity of a paper across libraries: its DOI and its normalized title."""
    doi = (data.get("DOI") or "").strip().lower().removeprefix("https://doi.org/")
    title = re.sub(r"[^a-z0-9]+", " ", (data.get("title") or "").lower()).strip()
    return {x for x in (doi and "doi:" + doi, title and "title:" + title) if x}


def top_items(spec: str) -> list[dict]:
    library, key = spec.split(":")
    z = client(library)
    return [dict(i, library=library) for i in z.everything(z.collection_items_top(key))
            if i["data"]["itemType"] not in SKIP_TYPES]


def pdfs(item: dict) -> list[dict]:
    return [a for a in client(item["library"]).children(item["key"])
            if a["data"].get("contentType") == "application/pdf" and a["data"].get("linkMode") in STORED]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--into", required=True, help="target group library id")
    ap.add_argument("--name", required=True, help="collection to create (reused if it exists)")
    ap.add_argument("--from", dest="sources", nargs="+", required=True, help="LIBRARY:COLLECTION_KEY ...")
    ap.add_argument("--exclude", nargs="*", default=[], help="LIBRARY:COLLECTION_KEY of the use case's other domains")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    excluded = set()
    for spec in a.exclude:
        for i in top_items(spec):
            excluded |= ids(i["data"])
    target = client(a.into)
    existing = {}
    for i in target.everything(target.top()):
        if i["data"]["itemType"] not in SKIP_TYPES:
            for x in ids(i["data"]):
                existing.setdefault(x, i)
    coll = next((c for c in target.everything(target.collections()) if c["data"]["name"] == a.name
                 and not c["data"].get("parentCollection")), None)
    inside = {x for i in (target.everything(target.collection_items_top(coll["key"])) if coll else [])
              for x in ids(i["data"])}

    seen, add, copy, skipped = set(), [], [], {"excluded": 0, "duplicate": 0, "already in": 0}
    for spec in a.sources:
        for i in top_items(spec):
            x = ids(i["data"])
            if x & excluded:
                skipped["excluded"] += 1
            elif x & seen:
                skipped["duplicate"] += 1
            elif x & inside:
                skipped["already in"] += 1
            elif i["library"] == a.into:
                add.append(i)
            elif x & set(existing):
                add.append(existing[next(iter(x & set(existing)))])
            else:
                copy.append(i)
            seen |= x
    with_pdf = sum(1 for i in copy if pdfs(i))
    print(f"{a.name}: {len(inside)} papers in it now; add {len(add)} from {a.into}; copy {len(copy)} from other "
          f"libraries ({with_pdf} with a stored PDF to upload, {len(copy) - with_pdf} without); skipped {skipped}")
    if not a.apply:
        print("plan only; add --apply to create and fill the collection")
        return

    if not coll:
        made = target.create_collections([{"name": a.name}])
        coll = {"key": next(iter(made["successful"].values()))["key"]}
    print(f"collection key: {coll['key']}  (src/config.py COLLECTIONS: library_id {a.into}, collection_key {coll['key']})")
    for n, i in enumerate(add, 1):
        target.addto_collection(coll["key"], target.item(i["key"]))
        print(f"  [{n}/{len(add)}] added {i['data'].get('title', '')[:70]}")
    failed = 0
    for n, i in enumerate(copy, 1):
        data = {k: v for k, v in i["data"].items() if k not in READ_ONLY}
        made = target.create_items([{**data, "collections": [coll["key"]]}])
        if not made["successful"]:
            failed += 1
            print(f"  [{n}/{len(copy)}] FAILED {data.get('title', '')[:70]}: {made['failed']}")
            continue
        key = next(iter(made["successful"].values()))["key"]
        for att in pdfs(i):
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / (att["data"].get("filename") or f"{att['key']}.pdf")
                path.write_bytes(client(i["library"]).file(att["key"]))
                target.attachment_simple([str(path)], parentid=key)
        print(f"  [{n}/{len(copy)}] copied {data.get('title', '')[:70]}")
    print(f"done: {len(add)} added, {len(copy) - failed} copied, {failed} failed; collection key {coll['key']}")


if __name__ == "__main__":
    main()
