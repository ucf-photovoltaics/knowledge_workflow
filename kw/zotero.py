# -*- coding: utf-8 -*-
"""
Zotero source — fetch papers + PDF full text.

Returns the uniform corpus contract every downstream stage consumes:
    {title_lower: {key, title, doi, abstract, date, authors, full_text}}
"""
from io import BytesIO

from pyzotero import Zotero
from pypdf import PdfReader

from kw.config import ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY

zot = Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)


def get_collection_map() -> dict[str, str]:
    """Return {'Parent > Subcollection': collection_id} for every collection."""
    all_collections = zot.everything(zot.collections())
    key_to_data     = {c['key']: c['data'] for c in all_collections}
    collection_map  = {}
    for c in all_collections:
        name       = c['data']['name']
        parent_key = c['data'].get('parentCollection', False)
        path       = name
        while parent_key:
            parent_data = key_to_data.get(parent_key)
            if not parent_data:
                break
            path       = f"{parent_data['name']} > {path}"
            parent_key = parent_data.get('parentCollection', False)
        collection_map[path] = c['key']
    return collection_map


def get_pdf_text(item_key: str) -> str:
    """Full text of the first PDF attachment under item_key, or '' on failure."""
    for child in zot.children(item_key):
        if child['data'].get('contentType') == 'application/pdf':
            try:
                reader = PdfReader(BytesIO(zot.file(child['key'])))
                return ''.join(p.extract_text() or '' for p in reader.pages)
            except Exception as exc:                       # P8: log, don't swallow silently
                print(f'    [warn] PDF extract failed for {item_key}: {exc}')
    return ''


def get_collection_with_text(collection_id: str, limit: int | None = None) -> dict[str, dict]:
    """Fetch papers in *collection_id* with metadata + full PDF text.

    If *limit* is set, stops after that many valid papers (PDF text is only
    extracted for the papers actually included — useful for quick tests).
    """
    items      = zot.everything(zot.collection_items(collection_id))
    collection = {}
    for item in items:
        data = item['data']
        if data.get('itemType') in ('attachment', 'note') or not data.get('title'):
            continue
        collection[data['title'].lower()] = {
            'key':       item['key'],
            'title':     data['title'],
            'doi':       data.get('DOI', ''),
            'abstract':  data.get('abstractNote', ''),
            'date':      data.get('date', ''),
            'authors':   data.get('creators', []),
            'full_text': get_pdf_text(item['key']),
        }
        if limit is not None and len(collection) >= limit:
            break
    return collection
