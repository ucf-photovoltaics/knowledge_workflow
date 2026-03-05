# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 20:00:25 2026

@author: brent thompson
"""

from pyzotero import Zotero
import pandas as pd
from pypdf import PdfReader
from io import BytesIO
from keybert import KeyBERT
from datetime import datetime
import re, glob, os

# --- CONFIG ---
LIBRARY_ID = '2189702'
LIBRARY_TYPE = 'group'
API_KEY = ''
zot = Zotero(LIBRARY_ID, LIBRARY_TYPE, API_KEY)
kw_model = KeyBERT()

# --- UTILITIES ---
def make_filename(collection_name, username='Brent_Thompson', version=1):
    """Generate standardized filename: name-user-version-date.csv"""
    date = datetime.now().strftime('%Y%m%d')
    name = collection_name.replace(' ', '_').lower()
    return f"{name}-{username}-v{version}-{date}.csv"

def find_latest_file(pattern):
    """Find the most recent file matching a glob pattern."""
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=lambda f: os.path.getmtime(f))

# --- ZOTERO ---
def get_collection_map():
    """Return {collection_name: collection_id} for all collections."""
    return {c['data']['name']: c['key'] for c in zot.collections()}

def get_pdf_text(item_key):
    """Extract full text from a Zotero item's PDF attachment."""
    for child in zot.children(item_key):
        if child['data'].get('contentType') == 'application/pdf':
            try:
                reader = PdfReader(BytesIO(zot.file(child['key'])))
                return ''.join(p.extract_text() or '' for p in reader.pages)
            except:
                pass
    return ""

def get_collection_texts(collection_id):
    """Return {title: full_text} for all papers in a collection."""
    items = zot.everything(zot.collection_items(collection_id))
    return {
        data['title']: get_pdf_text(item['key'])
        for item in items
        if (data := item['data']).get('itemType') not in ('attachment', 'note')
        and data.get('title')
    }

def get_collection_with_text(collection_id):
    """Return {title: {metadata + full_text}} for all papers in a collection."""
    items = zot.everything(zot.collection_items(collection_id))
    collection = {}
    for item in items:
        data = item['data']
        if data.get('itemType') in ('attachment', 'note') or not data.get('title'):
            continue
        collection[data['title'].lower()] = {
            'key': item['key'], 'title': data['title'],
            'doi': data.get('DOI'), 'abstract': data.get('abstractNote'),
            'date': data.get('date'), 'authors': data.get('creators', []),
            'full_text': get_pdf_text(item['key'])
        }
    return collection

# --- NLP ---
def extract_key_concepts(text, top_n=20):
    """Extract the most important concepts from a single text using KeyBERT."""
    keywords = kw_model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 3),
        stop_words='english',
        use_mmr=True,
        diversity=0.5,
        top_n=top_n
    )
    return [(phrase, round(score, 4)) for phrase, score in keywords]

def match_sentences(text, terms):
    """For each term, find all sentences in text that mention it."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return {
        term: ' | '.join(s.strip() for s in sentences if term in s.lower()) or ''
        for term in terms
    }

def build_concept_table(collection_dict, top_n=20):
    """Extract top concepts per paper into a flat table."""
    rows = []
    for paper in collection_dict.values():
        if not paper.get('abstract'):
            continue
        concepts = extract_key_concepts(paper['abstract'], top_n=top_n)
        for phrase, score in concepts:
            rows.append({
                'paper': paper['title'],
                'concept': phrase,
                'relevance': score
            })
    return pd.DataFrame(rows)

def build_concept_rankings(df_keys):
    """Aggregate concepts across all papers, ranked by frequency and relevance."""
    return df_keys.groupby('concept').agg(
        doc_frequency=('paper', 'count'),
        avg_relevance=('relevance', 'mean')
    ).sort_values(['doc_frequency', 'avg_relevance'], ascending=False)

def build_ontology_matrix(collection_dict, concepts):
    """Build a paper x concept matrix with source sentences from abstracts."""
    papers = [(p['title'], p['abstract']) for p in collection_dict.values() if p.get('abstract')]
    if not papers:
        print("No abstracts found.")
        return pd.DataFrame()
    titles, abstracts = zip(*papers)

    df = pd.DataFrame(
        [{'paper': title, **match_sentences(abstract, concepts)}
         for title, abstract in zip(titles, abstracts)]
    ).set_index('paper')
    return df

def build_ontology_from_csv(collection_dict, csv_path, column='concept'):
    """Use terms listed in a CSV column as the target concepts."""
    concepts = pd.read_csv(csv_path)[column].dropna().str.strip().str.lower().tolist()
    return build_ontology_matrix(collection_dict, concepts)

# --- WORKFLOW ---
if __name__ == '__main__':
    # 1. Get collection map
    my_collections = get_collection_map()
    print("Available collections:")
    for name in my_collections:
        print(f"  {name}")

    # 2. Load a collection with full text + metadata
    collection_name = 'Perovskites'  # <-- change this
    papers = get_collection_with_text(my_collections[collection_name])
    print(f"\nLoaded {len(papers)} papers from '{collection_name}'")

    # 3. Check for missing PDFs
    missing = [p['title'] for p in papers.values() if not p['full_text']]
    if missing:
        print(f"\n{len(missing)} papers without PDF text:")
        for t in missing:
            print(f"  {t}")

    # 4. Extract key concepts per paper
    df_keys = build_concept_table(papers, top_n=20)
    print(f"\nExtracted {len(df_keys)} concept-paper pairs")

    # 5. Rank concepts across collection
    df_rankings = build_concept_rankings(df_keys)
    print(f"\n{len(df_rankings)} unique concepts found")

    # 6. Build ontology matrix using top concepts
    top_concepts = df_rankings.head(80).index.tolist()
    df_ontology = build_ontology_matrix(papers, top_concepts)

    # 7. Save CSVs with standardized naming
    prefix = make_filename(collection_name)
    df_keys.to_csv(f"concepts_{prefix}", index=False)
    df_rankings.to_csv(f"rankings_{prefix}")
    df_ontology.to_csv(f"ontology_{prefix}")
    print(f"\nSaved: concepts_{prefix}")
    print(f"Saved: rankings_{prefix}")
    print(f"Saved: ontology_{prefix}")

    # 8. Preview
    print("\n--- Key Concepts (top 5 papers) ---")
    print(df_keys.head(20).to_string(index=False))
    print("\n--- Concept Rankings (top 20) ---")
    print(df_rankings.head(20).to_string())
    print("\n--- Ontology Matrix (top 5) ---")
    print(df_ontology.head().to_string())

    # 9. (Optional) Build from a predefined terms CSV
    latest = find_latest_file(f"rankings_*{collection_name.replace(' ', '_').lower()}*.csv")
    if latest:
        print(f"\nLoading concepts from: {latest}")
        df_from_csv = build_ontology_from_csv(papers, latest, column='concept')
        df_from_csv.to_csv(f"ontology_custom_{prefix}")
        print(f"Saved: ontology_custom_{prefix}")
        print(df_from_csv.to_string())
    else:
        print("\nNo previous rankings file found. Run the full pipeline first.")