# -*- coding: utf-8 -*-
"""
Zotero integration tool.

Provides three functions used by the orchestrator to fetch papers and PDFs:
  get_collection_map  — list all collections with their IDs
  get_pdf_text        — extract full text from a Zotero item's PDF attachment
  get_collection_with_text — fetch all papers in a collection with metadata + full text
"""

from io import BytesIO
from pyzotero import Zotero
from pypdf import PdfReader
from src.config import ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY


# Shared Zotero client — instantiated once on import
zot = Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)


def get_collection_map() -> dict[str, str]:
    """
    Return {'Parent > Subcollection': collection_id} for every collection
    in the Zotero library, including nested paths.
    """
    all_collections = zot.everything(zot.collections())
    key_to_data     = {c['key']: c['data'] for c in all_collections}
    collection_map  = {}

    for c in all_collections:
        key        = c['key']
        name       = c['data']['name']
        parent_key = c['data'].get('parentCollection', False)
        path       = name

        while parent_key:
            parent_data = key_to_data.get(parent_key)
            if parent_data:
                path       = f"{parent_data['name']} > {path}"
                parent_key = parent_data.get('parentCollection', False)
            else:
                break

        collection_map[path] = key

    return collection_map


def get_pdf_text(item_key: str) -> str:
    """
    Extract and return the full plain text from the first PDF attachment
    found under item_key.  Returns '' if no PDF is found or extraction fails.
    """
    for child in zot.children(item_key):
        if child['data'].get('contentType') == 'application/pdf':
            try:
                reader = PdfReader(BytesIO(zot.file(child['key'])))
                return ''.join(p.extract_text() or '' for p in reader.pages)
            except Exception:
                pass
    return ''


def get_collection_with_text(collection_id: str) -> dict[str, dict]:
    """
    Fetch every paper in *collection_id* and attach full PDF text.

    Returns:
        {title_lower: {key, title, doi, abstract, date, authors, full_text}}
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

    return collection
