# -*- coding: utf-8 -*-
"""
REBEL — Step 2 (mining), runs ALONGSIDE the LLM.

Extracts flat S-P-O triples exactly as stated in the paper text, then persists
them into the GraphDB repo (triples CSV + rebel_triples.jsonld) so the relational
/ causal facts land in the graph next to the concept data.

Degrades gracefully: if transformers/torch or the model are unavailable,
extraction returns [] and the rest of the pipeline runs unchanged.
Reproducibility: pin REBEL_REVISION to a commit hash.
"""
from __future__ import annotations

import os
import csv
import json

from kw.models import Triple, Provenance
from kw.config import MDS_NS

REBEL_MODEL    = os.getenv('REBEL_MODEL', 'Babelscape/rebel-large')
REBEL_REVISION = os.getenv('REBEL_REVISION', 'main')   # TODO: pin to a commit hash
# REBEL coverage: scan the whole paper in 512-token windows (True) instead of
# only the first ~512 tokens. Chunk size is in characters (~512 REBEL tokens).
REBEL_FULL_TEXT     = os.getenv('REBEL_FULL_TEXT', 'true').lower() != 'false'
REBEL_CHUNK_CHARS   = int(os.getenv('REBEL_CHUNK_CHARS',   '1600'))   # ~512 tokens/window
REBEL_CHUNK_OVERLAP = int(os.getenv('REBEL_CHUNK_OVERLAP', '200'))    # carry across boundaries
REBEL_MAX_CHARS     = int(os.getenv('REBEL_MAX_CHARS',     '0'))      # 0 = whole paper
# Default CPU: stable PyTorch lacks sm_120 kernels for Blackwell (RTX 50-series),
# so 'cuda' will only work with a CUDA 12.8+/13.x nightly build. Failures here are
# caught in _load() and the stage degrades to a no-op.
def _auto_device() -> str:
    """'cuda' when a working CUDA torch is present, else 'cpu'. Env REBEL_DEVICE overrides."""
    forced = os.getenv('REBEL_DEVICE')
    if forced:
        return forced
    try:
        import torch
        return 'cuda' if torch.cuda.is_available() else 'cpu'
    except Exception:
        return 'cpu'


REBEL_DEVICE   = _auto_device()


def gpu_banner() -> str:
    """One-line GPU/VRAM summary for run startup (safe on CPU-only / no torch)."""
    try:
        import torch
        if not torch.cuda.is_available():
            import sys as _sys
            cvd = os.environ.get('CUDA_VISIBLE_DEVICES')
            extra = f' | CUDA_VISIBLE_DEVICES={cvd!r}' if cvd is not None else ''
            return (f'[gpu] CUDA not available -> CPU | torch {torch.__version__} | '
                    f'py {_sys.executable}{extra}')
        i = torch.cuda.current_device()
        free, total = torch.cuda.mem_get_info(i)
        gb = 1024 ** 3
        return (f'[gpu] {torch.cuda.get_device_name(i)} | torch {torch.__version__} | '
                f'VRAM {free/gb:.1f}/{total/gb:.1f} GB free | rebel_device={REBEL_DEVICE}')
    except Exception as exc:
        return f'[gpu] status unavailable ({exc}) -> CPU'

_tok = None
_model = None


def _load() -> bool:
    """Load REBEL once onto REBEL_DEVICE. Returns False (and warns) on failure."""
    global _tok, _model, REBEL_DEVICE
    if _model is not None:
        return True
    try:
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        _tok   = AutoTokenizer.from_pretrained(REBEL_MODEL, revision=REBEL_REVISION)
        _model = AutoModelForSeq2SeqLM.from_pretrained(REBEL_MODEL, revision=REBEL_REVISION)
        try:
            _model.to(REBEL_DEVICE)
        except Exception as dev_exc:
            if REBEL_DEVICE != 'cpu':
                print(f'  [rebel] {REBEL_DEVICE} unavailable ({dev_exc}); falling back to CPU.')
                REBEL_DEVICE = 'cpu'
                _model.to('cpu')
            else:
                raise
        print(f'  [rebel] model loaded on {REBEL_DEVICE}')
        return True
    except Exception as exc:
        print(f'  [rebel] unavailable ({exc}); skipping triple extraction.')
        return False


def _parse(decoded: str) -> list[tuple[str, str, str]]:
    """Canonical REBEL decoder: parse <triplet>/<subj>/<obj> tokens into (s, p, o)."""
    triplets: list[tuple[str, str, str]] = []
    subject = relation = object_ = ''
    current = 'x'
    text = decoded.replace('<s>', '').replace('<pad>', '').replace('</s>', '')
    for token in text.split():
        if token == '<triplet>':
            current = 't'
            if relation:
                triplets.append((subject.strip(), relation.strip(), object_.strip()))
                relation = ''
            subject = ''
        elif token == '<subj>':
            current = 's'
            if relation:
                triplets.append((subject.strip(), relation.strip(), object_.strip()))
            object_ = ''
        elif token == '<obj>':
            current = 'o'
            relation = ''
        else:
            if current == 't':
                subject += ' ' + token
            elif current == 's':
                object_ += ' ' + token
            elif current == 'o':
                relation += ' ' + token
    if subject and relation and object_:
        triplets.append((subject.strip(), relation.strip(), object_.strip()))
    return triplets


def extract_triplets(text: str, source_paper: str = '',
                     max_input: int = 512, num_beams: int = 3) -> list[Triple]:
    """Run REBEL on one chunk of text. Returns [] if REBEL is unavailable.

    Each triple carries a confidence (T1.6) derived from the beam's
    length-normalized sequence log-probability.
    """
    if not text or not _load():
        return []
    import math
    inputs = _tok([text], return_tensors='pt', truncation=True, max_length=max_input)
    inputs = inputs.to(REBEL_DEVICE)
    gen = _model.generate(**inputs, max_length=256, num_beams=num_beams,
                          length_penalty=0.0, no_repeat_ngram_size=3,
                          output_scores=True, return_dict_in_generate=True)
    seq = gen.sequences
    decoded = _tok.batch_decode(seq, skip_special_tokens=False)[0]

    conf = 1.0
    try:
        scores = getattr(gen, 'sequences_scores', None)
        if scores is not None:
            gen_len = max(1, int(seq.shape[1]))
            conf = float(math.exp(float(scores[0]) / gen_len))
            conf = max(0.0, min(1.0, conf))
    except Exception:
        conf = 1.0

    return [
        Triple(subject=s, predicate=p, object=o,
               provenance=Provenance(source_paper=source_paper, tool='rebel',
                                     model=REBEL_MODEL, confidence=round(conf, 3)))
        for s, p, o in _parse(decoded)
    ]


def _char_chunks(text: str, size: int, overlap: int) -> list[str]:
    """Overlapping character windows covering the whole text."""
    if size <= 0 or len(text) <= size:
        return [text] if text else []
    step = max(1, size - overlap)
    return [text[i:i + size] for i in range(0, len(text), step)]


def extract_corpus(papers: dict) -> list[Triple]:
    """Step 2 (REBEL half): triples across the corpus.

    With REBEL_FULL_TEXT (default) each paper's full text is scanned in
    overlapping 512-token windows and triples are de-duplicated across chunks,
    so REBEL covers the entire paper rather than just its first ~512 tokens.
    Safe no-op if REBEL is unavailable.
    """
    out: list[Triple] = []
    n_papers = n_chunks = n_chars = 0
    for paper in papers.values():
        text = paper.get('full_text') or paper.get('abstract') or ''
        if REBEL_MAX_CHARS:
            text = text[:REBEL_MAX_CHARS]
        if not text:
            continue
        n_papers += 1
        n_chars += len(text)
        title = paper.get('title', '')
        if REBEL_FULL_TEXT:
            windows = _char_chunks(text, REBEL_CHUNK_CHARS, REBEL_CHUNK_OVERLAP)
        else:
            windows = [text[:4000]]
        seen: set[tuple] = set()
        for chunk in windows:
            n_chunks += 1
            for t in extract_triplets(chunk, source_paper=title):
                key = (t.subject.lower().strip(),
                       t.predicate.lower().strip(),
                       t.object.lower().strip())
                if key not in seen:
                    seen.add(key)
                    out.append(t)
    mode = 'full-text' if REBEL_FULL_TEXT else 'head-only'
    print(f'  [rebel] {mode}: scanned {n_chars} chars in {n_chunks} chunk(s) '
          f'across {n_papers} paper(s) -> {len(out)} triples')
    return out


def save_triples(triples: list[Triple], out_dir: str, prefix: str, ns: str = MDS_NS) -> dict:
    """Persist triples into the GraphDB repo: triples_<prefix>.csv + rebel_triples.jsonld."""
    csv_path = os.path.join(out_dir, 'triples_' + prefix)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['subject', 'predicate', 'predicate_norm', 'object',
                    'subject_id', 'object_id', 'confidence', 'source_paper'])
        for t in triples:
            w.writerow([t.subject, t.predicate, t.predicate_norm, t.object,
                        t.subject_id, t.object_id, t.provenance.confidence,
                        t.provenance.source_paper])

    ctx = {
        'mds':  ns,
        'prov': 'http://www.w3.org/ns/prov#',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
        'xsd':  'http://www.w3.org/2001/XMLSchema#',
    }
    graph = []
    for i, t in enumerate(triples):
        node = {
            '@id':                f'{ns}relation/{i:05d}',
            '@type':              'mds:ExtractedRelation',
            'rdfs:label':         f'{t.subject} - {t.predicate} - {t.object}',
            'mds:subject':        t.subject,
            'mds:predicate':      t.predicate,
            'mds:object':         t.object,
            'mds:tool':           t.provenance.tool,
            'mds:confidence':     {'@value': t.provenance.confidence, '@type': 'xsd:decimal'},
            'prov:wasDerivedFrom': t.provenance.source_paper,
        }
        if t.predicate_norm:
            node['mds:relation'] = {'@id': t.predicate_norm}
        if t.subject_id:
            node['mds:subjectConcept'] = {'@id': t.subject_id}
        if t.object_id:
            node['mds:objectConcept'] = {'@id': t.object_id}
        graph.append(node)
    jsonld_path = os.path.join(out_dir, 'rebel_triples.jsonld')
    _tmp = f'{jsonld_path}.tmp'
    with open(_tmp, 'w', encoding='utf-8') as f:
        json.dump({'@context': ctx, '@graph': graph}, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(_tmp, jsonld_path)
    return {'csv': csv_path, 'jsonld': jsonld_path, 'count': len(triples)}
