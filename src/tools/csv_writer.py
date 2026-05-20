# -*- coding: utf-8 -*-
"""
CSV I/O tool.

Handles filename generation, saving pipeline outputs, and loading
existing concept CSVs for reuse across runs.
"""

import os
import glob
import pandas as pd
from datetime import datetime

from src.models.concept import ConceptTable
from src.models.schema  import SchemaRow


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------

def make_filename(collection_name: str, username: str = 'Brent_Thompson', version: int = 7) -> str:
    """
    Return a standardised CSV filename:
        <collection_slug>-<username>-v<version>-<YYYYMMDD>.csv
    """
    date = datetime.now().strftime('%Y%m%d')
    name = collection_name.replace(' ', '_').lower().replace('>', '').replace('-', '')
    return f'{name}-{username}-v{version}-{date}.csv'


def find_latest_file(pattern: str) -> str | None:
    """Return the most-recently-modified file matching *pattern*, or None."""
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else None


def collection_slug(collection_name: str) -> str:
    """Normalise a collection name into a filesystem-safe slug."""
    return collection_name.replace(' ', '_').lower().replace('>', '').replace('-', '')


# ---------------------------------------------------------------------------
# Save pipeline outputs
# ---------------------------------------------------------------------------

def save_concepts_csv(table: ConceptTable, out_path: str) -> None:
    """Write the flat concept-extraction table to *out_path*."""
    rows = [
        {
            'paper':      r.paper,
            'doi':        r.doi,
            'canonical':  r.canonical,
            'paper_term': r.paper_term,
            'relevance':  round(r.relevance, 4),
        }
        for r in table.rows
    ]
    pd.DataFrame(rows).to_csv(out_path, index=False)


def save_schema_csv(schema_rows: list[SchemaRow], canonical_concepts: list[str], out_path: str) -> None:
    """
    Write the wide-format schema table to *out_path*.
    Columns: domain, doi, <concept_1>, …, <concept_N>
    """
    columns = ['domain', 'doi'] + canonical_concepts
    rows = []
    for sr in schema_rows:
        row = {'domain': sr.domain, 'doi': sr.doi}
        for c in canonical_concepts:
            row[c] = sr.cells.get(c, '')
        rows.append(row)
    pd.DataFrame(rows, columns=columns).to_csv(out_path, index=False)


# ---------------------------------------------------------------------------
# Load existing concept CSVs (for reuse / cemento pipeline)
# ---------------------------------------------------------------------------

def load_concepts(csv_path: str) -> pd.DataFrame:
    """
    Return a DataFrame with at least [concept, doc_frequency].
    Handles V3/V4/V5 concepts_*.csv and rankings_*.csv formats.
    """
    df   = pd.read_csv(csv_path)
    cols = {c.lower().strip() for c in df.columns}

    if 'concept' in cols and 'doc_frequency' in cols:
        # rankings (V1–V4): concept, doc_frequency, avg_relevance
        out = df.copy()
        out['concept'] = out['concept'].str.strip()

    elif 'canonical' in cols:
        # V5 concepts: paper, doi, canonical, paper_term, relevance
        df['canonical'] = df['canonical'].str.strip().str.lower()
        out = (
            df.groupby('canonical')
              .agg(doc_frequency=('paper', 'nunique'))
              .reset_index()
              .rename(columns={'canonical': 'concept'})
        )

    elif 'concept' in cols and 'paper' in cols:
        # V3 concepts: paper, concept, relevance
        df['concept'] = df['concept'].str.strip().str.lower()
        out = (
            df.groupby('concept')
              .agg(doc_frequency=('paper', 'nunique'))
              .reset_index()
        )

    else:
        raise ValueError(
            f'Unrecognised CSV format in {csv_path}.\n'
            f'Expected: rankings (concept, doc_frequency), '
            f'V5 (paper, doi, canonical, …), or V3 (paper, concept, relevance).\n'
            f'Found columns: {list(df.columns)}'
        )

    out = out.dropna(subset=['concept'])
    out = out[out['concept'].str.strip() != '']
    return out.sort_values(
        ['doc_frequency', 'concept'], ascending=[False, True]
    ).reset_index(drop=True)
