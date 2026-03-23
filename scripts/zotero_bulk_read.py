from pyzotero import Zotero
import pandas as pd
from pypdf import PdfReader
from io import BytesIO
from sklearn.feature_extraction.text import TfidfVectorizer
from datetime import datetime
import re
import spacy

# --- CONFIG ---
LIBRARY_ID = '2189702'
LIBRARY_TYPE = 'group'
API_KEY = 'W3COg3WIiWEvORVM3CiTLwc2'
zot = Zotero(LIBRARY_ID, LIBRARY_TYPE, API_KEY)
nlp = spacy.load('en_core_web_sm')

# --- UTILITIES ---
def make_filename(collection_name, username='Brent_Thompson', version=1):
    """Generate standardized filename: name-user-version-date.csv"""
    date = datetime.now().strftime('%Y%m%d')
    name = collection_name.replace(' ', '_').lower()
    return f"{name}-{username}-v{version}-{date}.csv"

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
def extract_noun_phrases(text):
    """Extract multi-word noun phrases from text using spaCy."""
    return {
        ' '.join(t.text for t in chunk if t.pos_ not in ('DET', 'PRON')).strip().lower()
        for chunk in nlp(text).noun_chunks
        if len(chunk.text.split()) >= 2 and len(chunk.text) > 5
    }

def match_sentences(text, terms):
    """For each term, find all sentences in text that mention it."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return {
        term: ' | '.join(s.strip() for s in sentences if term in s.lower()) or ''
        for term in terms
    }

def build_ontology_matrix(collection_dict, top_n=80, min_docs=2):
    """Build a paper x concept matrix using TF-IDF noun phrase extraction."""
    papers = [(p['title'], p['abstract']) for p in collection_dict.values() if p.get('abstract')]
    if not papers:
        print("No abstracts found.")
        return pd.DataFrame(), pd.DataFrame()
    titles, abstracts = zip(*papers)

    phrase_counts = {}
    for abstract in abstracts:
        for phrase in extract_noun_phrases(abstract):
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

    common = {p for p, c in phrase_counts.items() if c >= min_docs}
    if len(common) < top_n:
        common = {p for p, c in phrase_counts.items() if c >= 1}

    vectorizer = TfidfVectorizer(
        tokenizer=lambda t: [p for p in extract_noun_phrases(t) if p in common],
        token_pattern=None, lowercase=False, max_features=top_n
    )
    vectorizer.fit_transform(abstracts)
    concepts = vectorizer.get_feature_names_out()

    df = pd.DataFrame(
        [{'paper': title, **match_sentences(abstract, concepts)}
         for title, abstract in zip(titles, abstracts)]
    ).set_index('paper')

    freq = pd.DataFrame(
        [{'concept': c, 'doc_frequency': phrase_counts.get(c, 0)} for c in concepts]
    ).sort_values('doc_frequency', ascending=False)

    return df, freq

def build_ontology_from_csv(collection_dict, csv_path, column='concept'):
    """Use terms listed in a CSV column as the target concepts."""
    concepts = pd.read_csv(csv_path)[column].dropna().str.strip().str.lower().tolist()

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

# --- WORKFLOW ---
if __name__ == '__main__':
    # 1. Get collection map
    my_collections = get_collection_map()
    print("Available collections:")
    for name in my_collections:
        print(f"  {name}")

    # 2. Load a collection with full text + metadata
    collection_name = 'Encapsulants'  # <-- change this
    papers = get_collection_with_text(my_collections[collection_name])
    print(f"\nLoaded {len(papers)} papers from '{collection_name}'")

    # 3. Check for missing PDFs
    missing = [p['title'] for p in papers.values() if not p['full_text']]
    if missing:
        print(f"\n{len(missing)} papers without PDF text:")
        for t in missing:
            print(f"  {t}")

    # 4. Build ontology concept matrix from abstracts
    df_concepts, df_freq = build_ontology_matrix(papers, top_n=60, min_docs=10)
    print(f"\nExtracted {len(df_freq)} concepts across {len(df_concepts)} papers")

    # 5. Save CSVs with standardized naming
    prefix = make_filename(collection_name)
    df_concepts.to_csv(f"ontology_{prefix}")
    df_freq.to_csv(f"frequencies_{prefix}", index=False)
    print(f"\nSaved: ontology_{prefix}")
    print(f"Saved: frequencies_{prefix}")

    # 6. Preview top 5 rows
    print("\n--- Concept Matrix (top 5) ---")
    #print(df_concepts.head().to_string())
    #print("\n--- Concept Frequencies (top 5) ---")
    print(df_freq.to_string(index=False))

    # 7. (Optional) Build from a predefined terms CSV
    # df_from_csv = build_ontology_from_csv(papers, 'my_terms.csv', column='concept')
    # df_from_csv.to_csv(f"ontology_custom_{prefix}")
    # print(df_from_csv.head().to_string())