# -*- coding: utf-8 -*-
"""
MDS-Onto grounding via the OntoPortal search API.

Resolves each pipeline concept to a REAL MDS-Onto term so the generated ontology
reuses existing IRIs and pulls authentic metadata instead of minting guessed
classes. For a matched concept we get:
  * the real class IRI (@id)            -> skos:exactMatch, reuse instead of mint
  * skos:definition                     -> real definitions (was missing)
  * mds:hasDomain / hasSubDomain        -> real domain -> subdomain -> concept hierarchy
  * mds:hasStudyStage                   -> grounding tag

Opt-in (GROUND_MDSONTO) and network-graceful: if disabled or the portal is
unreachable, resolve_concepts() returns {} and the emitter falls back to the
local keyword classifier. Results are cached to disk for speed + reproducibility.

API shape follows the user's OntoPortal MCP client (search_mdsonto).
"""
from __future__ import annotations

import os
import json
import datetime as _dt

PORTAL_BASE = os.getenv('MDSONTO_PORTAL', 'https://www.mdsonto-portal.com:8443')
API_KEY     = os.getenv('MDSONTO_API_KEY', '3d3c6d70-4de1-4770-95f7-76e0bd59ef87')
ACRONYM     = os.getenv('MDSONTO_ACRONYM', 'MDS-ONTO')
ENABLE      = os.getenv('GROUND_MDSONTO', 'false').lower() == 'true'
# OntoPortal requires administeredBy (a portal username) to create an ontology.
PORTAL_ADMIN_USER = os.getenv('PORTAL_ADMIN_USER', '')
CACHE_PATH  = os.getenv('MDSONTO_CACHE',
                        os.path.join(os.path.dirname(os.path.dirname(__file__)), '.mdsonto_cache.json'))

_SKOS = 'http://www.w3.org/2004/02/skos/core#'
_MDS  = 'https://cwrusdle.bitbucket.io/mds/'
PROP = {
    'definition': _SKOS + 'definition',
    'altLabel':   _SKOS + 'altLabel',
    'domain':     _MDS + 'hasDomain',
    'subDomain':  _MDS + 'hasSubDomain',
    'studyStage': _MDS + 'hasStudyStage',
}

_cache: dict | None = None


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.load(open(CACHE_PATH, encoding='utf-8'))
        except Exception:
            _cache = {}
    return _cache


def _save_cache() -> None:
    try:
        json.dump(_cache or {}, open(CACHE_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except Exception:
        pass


def _extract(props: dict, uri: str) -> str:
    if not props:
        return ''
    val = props.get(uri)
    if not val:
        return ''
    if isinstance(val, list):
        return '; '.join(str(v) for v in val if v)
    return str(val)


def _search(query: str, max_records: int = 20, timeout: int = 30) -> list[dict]:
    """Raw OntoPortal search. Returns [] on any failure (network-graceful)."""
    try:
        import requests
        params = {
            'q': query, 'apikey': API_KEY, 'page': 1, 'pagesize': max_records,
            'require_exact_match': 'false', 'also_search_properties': 'true',
            'also_search_obsolete': 'false',
            'include': 'prefLabel,synonym,definition,properties',
        }
        if ACRONYM:
            params['ontologies'] = ACRONYM
        resp = requests.get(f'{PORTAL_BASE}/search', params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data.get('collection', [])
        return data if isinstance(data, list) else []
    except Exception as exc:
        print(f'  [mdsonto] search failed for {query!r} ({type(exc).__name__}); skipping.')
        return []


def _best(records: list[dict], concept: str) -> dict | None:
    """Pick a confident match: exact prefLabel/synonym, else clear containment."""
    cl = concept.strip().lower()
    if not records:
        return None
    # exact prefLabel
    for r in records:
        if str(r.get('prefLabel', '')).strip().lower() == cl:
            return r
    # exact synonym
    for r in records:
        syns = r.get('synonym') or []
        if isinstance(syns, str):
            syns = [syns]
        if any(str(s).strip().lower() == cl for s in syns):
            return r
    # containment (concept in label or label in concept), shortest label wins
    cand = [r for r in records
            if cl in str(r.get('prefLabel', '')).lower()
            or str(r.get('prefLabel', '')).lower() in cl]
    if cand:
        return min(cand, key=lambda r: len(str(r.get('prefLabel', ''))))
    return None


def _format(rec: dict, concept: str) -> dict:
    props = rec.get('properties', {}) or {}
    definition = _extract(props, PROP['definition'])
    if not definition and rec.get('definition'):
        d = rec['definition']
        definition = '; '.join(d) if isinstance(d, list) else str(d)
    return {
        'concept':     concept,
        'iri':         rec.get('@id', ''),
        'label':       rec.get('prefLabel', ''),
        'definition':  definition,
        'domain':      _extract(props, PROP['domain']),
        'subdomain':   _extract(props, PROP['subDomain']),
        'study_stage': _extract(props, PROP['studyStage']),
    }


def resolve_concept(concept: str) -> dict | None:
    """Resolve one concept to a confident MDS-Onto match, or None."""
    cache = _load_cache()
    if concept in cache:
        return cache[concept]
    rec = _best(_search(concept), concept)
    result = _format(rec, concept) if rec and rec.get('@id') else None
    cache[concept] = result
    return result


def resolve_concepts(concept_list: list[str]) -> dict[str, dict]:
    """Resolve a list; returns {concept: match} only for confident matches.
    Empty if GROUND_MDSONTO is off (so the emitter falls back cleanly)."""
    if not ENABLE:
        return {}
    out: dict[str, dict] = {}
    for c in concept_list:
        m = resolve_concept(c)
        if m and m.get('iri'):
            out[c] = m
    _save_cache()
    return out


def _normalize_acronym(acronym: str) -> str:
    """OntoPortal-safe acronym: letters/digits/dash/underscore, starts with a letter.

    The portal matches submissions to an ontology by its EXACT stored acronym, so
    we normalise once and reuse the same string for create, lookup, and submit.
    """
    import re
    a = re.sub(r'[^A-Za-z0-9_-]', '', str(acronym or '')).strip('-_').upper()
    if a and a[0].isdigit():
        a = 'O' + a
    return a or 'MDS_ONTO'


def fetch_contract(acronym: str = '', timeout: int = 60) -> dict:
    """Pull an existing ontology + its latest submission from the portal.

    This is the 'contract' to mirror when submitting: it shows exactly which
    fields a valid ontology/submission carries on THIS portal. Defaults to the
    reference MDS-ONTO ontology. Network-graceful: returns error info instead of
    raising so it can be run as a quick diagnostic.

    Run from the project root with:
        python -m kw.mdsonto contract            # MDS-ONTO reference
        python -m kw.mdsonto contract MY_ACRONYM # inspect your own ontology
    """
    out: dict = {'portal': PORTAL_BASE, 'acronym': acronym or ACRONYM}
    try:
        import requests
    except ImportError:
        out['error'] = 'requests not installed'
        return out
    acr = acronym or ACRONYM
    headers = {'Authorization': f'apikey token={API_KEY}'}

    def _get(path, **params):
        try:
            r = requests.get(f'{PORTAL_BASE}{path}', headers=headers,
                             params=params or None, timeout=timeout)
            body = r.json() if (r.ok and r.content) else r.text[:600]
            return {'status': r.status_code, 'body': body}
        except Exception as exc:  # noqa: BLE001
            return {'status': None, 'error': f'{type(exc).__name__}: {exc}'}

    out['ontology'] = _get(f'/ontologies/{acr}')
    out['latest_submission'] = _get(f'/ontologies/{acr}/latest_submission', display='all')
    return out


def submit_to_portal(ttl_path: str, acronym: str, name: str,
                     contact_name: str = '', contact_email: str = '',
                     admin_user: str = '', timeout: int = 120) -> dict:
    """Upload a TTL ontology file to the OntoPortal instance as a new submission.

    Ensures the ontology entry exists (creating it with administeredBy if needed),
    then CONFIRMS it by reading back the portal's canonical acronym before POSTing
    the submission. The read-back is what fixes the
        422 "You must provide a valid `acronym` to create a new submission"
    error: the submission endpoint matches on the ontology's stored acronym, so we
    submit against exactly what the portal returns rather than what we guessed.

    Returns a dict with 'status', 'submission_url', 'submission_id', 'acronym'.
    Raises on HTTP errors (with the portal's response body) so callers can decide
    whether to treat as fatal.
    """
    try:
        import requests
    except ImportError:
        return {'status': 'unavailable', 'submission_url': None,
                'error': 'requests not installed'}

    def _check(resp):
        """raise_for_status, but include the portal's response body so the failing
        field (e.g. 'acronym' / 'administeredBy is required') is actually visible."""
        try:
            resp.raise_for_status()
        except Exception as e:
            body = ''
            try:
                body = resp.text[:800]
            except Exception:
                pass
            raise RuntimeError(f'{e} | portal said: {body}') from e

    acronym = _normalize_acronym(acronym)
    admin = admin_user or PORTAL_ADMIN_USER
    headers = {'Authorization': f'apikey token={API_KEY}'}

    # OntoPortal requires a contact (name + email) on every submission; an empty
    # one triggers a 400: {"contact":{"existence":"`` value cannot be nil"}}.
    contact_email = (contact_email or '').strip()
    if not contact_email:
        raise RuntimeError(
            "OntoPortal submission needs a contact email - set "
            "PORTAL_CONTACT_EMAIL=<you@example.com> (and optionally "
            "PORTAL_CONTACT_NAME) in your .env.")
    contact = [{'name': contact_name or admin or 'curator', 'email': contact_email}]

    # 1. Ensure the ontology entry exists (create REQUIRES administeredBy).
    onto_url = f'{PORTAL_BASE}/ontologies/{acronym}'
    r = requests.get(onto_url, headers=headers, timeout=timeout)
    if r.status_code == 404:
        if not admin:
            raise RuntimeError(
                "OntoPortal needs 'administeredBy' to create an ontology - "
                "set PORTAL_ADMIN_USER=<your portal username> in .env")
        payload = {'acronym': acronym, 'name': name,
                   'administeredBy': [admin], 'contact': contact}
        _check(requests.post(f'{PORTAL_BASE}/ontologies', json=payload,
                             headers=headers, timeout=timeout))
    elif r.status_code not in (200, 201):
        _check(r)

    # 1b. Read the ontology back and use the portal's CANONICAL acronym. The
    # submissions endpoint matches on this exact value; submitting against a
    # mismatched / not-yet-persisted acronym is what produced the 422.
    confirm = requests.get(onto_url, headers=headers, timeout=timeout)
    if confirm.status_code != 200:
        _check(confirm)
        raise RuntimeError(
            f"Ontology {acronym!r} could not be confirmed on the portal after "
            f"create (HTTP {confirm.status_code}). portal said: {confirm.text[:400]}")
    canonical = (confirm.json() or {}).get('acronym') or acronym

    # 2. POST the TTL file as a new submission (file + OWL + contact required).
    sub_url = f'{PORTAL_BASE}/ontologies/{canonical}/submissions'
    data = {'acronym': canonical,            # submission must name its ontology
            'ontology': canonical,
            'hasOntologyLanguage': 'OWL',
            'released': _dt.date.today().isoformat(),
            'contact': contact_email}
    with open(ttl_path, 'rb') as fh:
        resp = requests.post(
            sub_url,
            headers=headers,
            files={'file': (os.path.basename(ttl_path), fh, 'text/turtle')},
            data=data,
            timeout=timeout,
        )
    _check(resp)
    result = resp.json() if resp.content else {}
    return {
        'status': 'submitted',
        'submission_url': result.get('@id', sub_url),
        'submission_id': result.get('submissionId'),
        'acronym': canonical,
    }


def write_csv(matches: dict[str, dict], path: str) -> str:
    """Persist matches as mdsonto_<...>.csv for the emitter to consume."""
    import csv
    cols = ['concept', 'iri', 'label', 'definition', 'domain', 'subdomain', 'study_stage']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for m in matches.values():
            w.writerow({k: m.get(k, '') for k in cols})
    return path


# ---------------------------------------------------------------------------
# CLI: inspect the portal contract  (python -m kw.mdsonto contract [ACRONYM])
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'contract'
    if cmd == 'contract':
        acr = sys.argv[2] if len(sys.argv) > 2 else ''
        print(json.dumps(fetch_contract(acr), indent=2, ensure_ascii=False))
    else:
        print("usage: python -m kw.mdsonto contract [ACRONYM]")
