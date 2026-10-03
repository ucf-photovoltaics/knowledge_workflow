"""Zotero: list collections, fetch a collection's top-level items, and cache their PDFs.

PDF lookup order: local cache -> zotero.org file download -> local Zotero storage -> linked-file path.
"""
import shutil
from functools import lru_cache
from pathlib import Path

from pyzotero import zotero

from src.config import ZOTERO, secret


@lru_cache
def _client(library_id: str) -> zotero.Zotero:
    return zotero.Zotero(library_id, ZOTERO["library_type"], secret("ZOTERO_API_KEY"))


def list_collections(library_id: str) -> list[dict]:
    z = _client(library_id)
    return [{"key": c["key"], "name": c["data"]["name"], "parent": c["data"].get("parentCollection") or "",
             "items": c.get("meta", {}).get("numItems", 0)} for c in z.everything(z.collections())]


def _local_copy(att: dict) -> Path | None:
    d = att["data"]
    if d.get("linkMode") == "linked_file" and d.get("path"):
        p = d["path"]
        if p.startswith("attachments:"):
            if not ZOTERO["linked_base"]:
                return None
            p = Path(ZOTERO["linked_base"]) / p[len("attachments:"):]
        return Path(p) if Path(p).is_file() else None
    if ZOTERO["local_storage"] and d.get("filename"):
        p = Path(ZOTERO["local_storage"]) / att["key"] / d["filename"]
        return p if p.is_file() else None
    return None


def _fetch_pdf(z, item_key: str, path: Path) -> str | None:
    """Copy the item's first available PDF to `path`; return where it came from."""
    for att in (c for c in z.children(item_key) if c["data"].get("contentType") == "application/pdf"):
        if att["data"].get("linkMode") in ("imported_file", "imported_url"):
            try:
                path.write_bytes(z.file(att["key"]))
                return "zotero.org"
            except Exception:  # not synced to zotero.org; try the local copy below
                pass
        local = _local_copy(att)
        if local:
            shutil.copyfile(local, path)
            return "local"
    return None


def list_items(library_id: str, collection_key: str) -> list[dict]:
    """Top-level items of a collection (metadata only, no PDFs)."""
    z = _client(library_id)
    items = []
    for it in z.everything(z.collection_items_top(collection_key)):
        d = it["data"]
        if d["itemType"] in ("attachment", "note", "annotation"):
            continue
        doi = d.get("DOI", "") or next((ln.split(":", 1)[1].strip() for ln in d.get("extra", "").splitlines()
                                        if ln.lower().startswith("doi:")), "")
        items.append({
            "key": d["key"], "title": d.get("title", ""), "doi": doi,
            "year": it.get("meta", {}).get("parsedDate", "")[:4],
            "authors": [f"{c.get('lastName', '')}, {c.get('firstName', '')}".strip(", ") or c.get("name", "")
                        for c in d.get("creators", []) if c.get("creatorType") == "author"],
            "pdf": None, "pdf_source": None,
        })
    return items


def attach_pdf(paper: dict, pdf_dir: Path, library_id: str) -> dict:
    """Set paper["pdf"] / paper["pdf_source"] (cache, zotero.org, local, or None)."""
    pdf_dir.mkdir(parents=True, exist_ok=True)
    path = pdf_dir / f"{paper['key']}.pdf"
    source = "cache" if path.exists() else _fetch_pdf(_client(library_id), paper["key"], path)
    paper.update(pdf=str(path) if source else None, pdf_source=source)
    return paper
