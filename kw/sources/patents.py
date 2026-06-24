# -*- coding: utf-8 -*-
"""
Patent source adapter (T5.1).

Broadens automated extraction from papers to patents — a target the SMSE special
issue calls out explicitly. It honors the same corpus contract as kw.zotero, so
nothing downstream changes:

    {title_lower: {key, title, doi, abstract, date, authors, full_text}}

Input is a local export (JSON list or CSV) so it runs offline and is provider-
agnostic; a live API client (Google Patents / USPTO / Lens.org) can later populate
the same records. Field names are mapped leniently from common patent exports.

CLI / programmatic use:
    from kw.sources import patents
    corpus = patents.get_collection_with_text('my_patents.json', limit=5)
    # then: kw.pipeline can consume `corpus` the same way as Zotero papers.
"""
from __future__ import annotations

import csv
import json
import os

# Lenient field aliases: export column -> our contract key.
_ALIASES = {
    'title':     ['title', 'invention_title', 'patent_title', 'name'],
    'doi':       ['doi', 'patent_number', 'publication_number', 'id', 'patent_id'],
    'abstract':  ['abstract', 'abstract_text', 'summary'],
    'date':      ['date', 'publication_date', 'grant_date', 'filing_date', 'year'],
    'authors':   ['authors', 'inventors', 'inventor', 'assignee', 'applicant'],
    'full_text': ['full_text', 'description', 'claims', 'body', 'text'],
}


def _pick(record: dict, keys: list[str]) -> str:
    for k in keys:
        for rk in record:
            if rk.lower() == k:
                v = record[rk]
                return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return ''


def _to_contract(record: dict, idx: int) -> dict:
    title = _pick(record, _ALIASES['title']) or f'patent_{idx:04d}'
    authors_raw = _pick(record, _ALIASES['authors'])
    authors = [{'name': a.strip()} for a in authors_raw.split(';') if a.strip()] \
        if authors_raw else []
    return {
        'key':       _pick(record, _ALIASES['doi']) or f'patent-{idx:04d}',
        'title':     title,
        'doi':       _pick(record, _ALIASES['doi']),
        'abstract':  _pick(record, _ALIASES['abstract']),
        'date':      _pick(record, _ALIASES['date']),
        'authors':   authors,
        'full_text': _pick(record, _ALIASES['full_text']),
    }


def _load_records(path: str) -> list[dict]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f'patent export not found: {path}')
    if path.lower().endswith('.json'):
        data = json.load(open(path, encoding='utf-8'))
        if isinstance(data, dict):                     # {"patents": [...]} or single record
            data = data.get('patents') or data.get('results') or [data]
        return list(data)
    # CSV / TSV
    delim = '\t' if path.lower().endswith('.tsv') else ','
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f, delimiter=delim))


def get_collection_with_text(path: str, limit: int | None = None) -> dict[str, dict]:
    """Return the uniform corpus dict from a local patent export (JSON/CSV)."""
    records = _load_records(path)
    corpus: dict[str, dict] = {}
    for i, rec in enumerate(records):
        item = _to_contract(rec, i)
        if not (item['abstract'] or item['full_text']):
            continue
        corpus[item['title'].lower()] = item
        if limit is not None and len(corpus) >= limit:
            break
    return corpus
