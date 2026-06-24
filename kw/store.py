# -*- coding: utf-8 -*-
"""
CSV I/O — filenames, saving pipeline outputs, loading concept lists for reuse.
"""
import os
import glob
import re
import pandas as pd
from datetime import datetime

from kw.models import ConceptTable, SchemaRow

VERSION = 8  # single source for the file-version tag (was sprinkled v5/v6/v7)


def collection_slug(collection_name: str) -> str:
    """Readable filesystem-safe slug (P7: no more run-together names)."""
    s = collection_name.lower().replace('>', ' ').replace('/', ' ')
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_')
    return s or 'collection'


def make_filename(collection_name: str, username: str = 'Brent_Thompson',
                  version: int = VERSION) -> str:
    date = datetime.now().strftime('%Y%m%d')
    return f'{collection_slug(collection_name)}-{username}-v{version}-{date}.csv'


def find_latest_file(pattern: str) -> str | None:
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else None


def save_concepts_csv(table: ConceptTable, out_path: str) -> None:
    rows = [{'paper': r.paper, 'doi': r.doi, 'canonical': r.canonical,
             'paper_term': r.paper_term, 'relevance': round(r.relevance, 4)}
            for r in table.rows]
    pd.DataFrame(rows).to_csv(out_path, index=False)


def save_schema_csv(schema_rows: list[SchemaRow], canonical_concepts: list[str],
                    out_path: str) -> None:
    columns = ['domain', 'doi'] + canonical_concepts
    rows = []
    for sr in schema_rows:
        row = {'domain': sr.domain, 'doi': sr.doi}
        for c in canonical_concepts:
            row[c] = sr.cells.get(c, '')
        rows.append(row)
    pd.DataFrame(rows, columns=columns).to_csv(out_path, index=False)


def load_concept_list(csv_path: str, column: str = '') -> list[str]:
    """Load a flat list of concepts for SUPERVISED mode.

    Accepts any CSV with a 'concept' or 'canonical' column (or an explicit one).
    """
    df = pd.read_csv(csv_path)
    col = column or ('concept' if 'concept' in df.columns else
                     'canonical' if 'canonical' in df.columns else df.columns[0])
    return (df[col].dropna().astype(str).str.strip().str.lower()
            .replace('', pd.NA).dropna().unique().tolist())


def load_concepts(csv_path: str) -> pd.DataFrame:
    """Return a DataFrame with [concept, doc_frequency] (for tagging/draw.io)."""
    df   = pd.read_csv(csv_path)
    cols = {c.lower().strip() for c in df.columns}
    if 'concept' in cols and 'doc_frequency' in cols:
        out = df.copy(); out['concept'] = out['concept'].str.strip()
    elif 'canonical' in cols:
        df['canonical'] = df['canonical'].str.strip().str.lower()
        out = (df.groupby('canonical').agg(doc_frequency=('paper', 'nunique'))
                 .reset_index().rename(columns={'canonical': 'concept'}))
    elif 'concept' in cols and 'paper' in cols:
        df['concept'] = df['concept'].str.strip().str.lower()
        out = (df.groupby('concept').agg(doc_frequency=('paper', 'nunique')).reset_index())
    else:
        raise ValueError(f'Unrecognised CSV format in {csv_path}. Columns: {list(df.columns)}')
    out = out.dropna(subset=['concept'])
    out = out[out['concept'].str.strip() != '']
    return out.sort_values(['doc_frequency', 'concept'],
                           ascending=[False, True]).reset_index(drop=True)
