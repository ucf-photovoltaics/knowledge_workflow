"""Citation counts per DOI, tried in order: OpenCitations Index (open CC0 data, no key; one DOI per request),
then OpenAlex cited_by_count (key optional), then Crossref is-referenced-by-count (no key).

A DOI moves on to the next source when the current one has no positive count for it; if every source
says 0 (or has nothing), the first explicit 0 is kept. Counts are cached in outputs/cache/citations.json
with their source and fetch date, so a collection's top-N selection stays fixed across runs.
Delete an entry (or the file) to refresh it.
"""
import json
import time
from datetime import date

import requests

from src.config import CACHE, secret
from src.tools.progress import log

OPENCITATIONS = "https://api.opencitations.net/index/v2/citation-count/doi:"
OPENALEX = "https://api.openalex.org/works"
CROSSREF = "https://api.crossref.org/works"
BATCH = 50
OC_INTERVAL = 60 / 170  # stay under OpenCitations' 180 requests/minute
PATH = CACHE / "citations.json"


def norm(doi: str) -> str:
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        d = d.removeprefix(prefix)
    return d


def _get(url: str, params: dict | None = None, headers: dict | None = None):
    for attempt in range(5):
        r = requests.get(url, params=params, headers=headers, timeout=60)
        if r.status_code in (401, 403):
            raise PermissionError(f"refused the request (HTTP {r.status_code})")
        if r.status_code not in (429, 500, 502, 503, 504):
            r.raise_for_status()
            return r.json()
        time.sleep(2 ** attempt)
    r.raise_for_status()


def _opencitations(dois: list[str]) -> dict[str, int]:
    token = secret("OPENCITATIONS_TOKEN")
    headers = {"authorization": token} if token else None
    out = {}
    for n, d in enumerate(dois, 1):
        data = _get(OPENCITATIONS + requests.utils.quote(d, safe="/:;()"), headers=headers)
        if data:
            out[d] = int(data[0].get("count", 0))
        if n % 25 == 0:
            log(f"    opencitations: {n}/{len(dois)} DOIs")
        time.sleep(OC_INTERVAL)
    return out


def _openalex(dois: list[str]) -> dict[str, int]:
    data = _get(OPENALEX, {"filter": "doi:" + "|".join(dois), "select": "doi,cited_by_count",
                           "per-page": BATCH, "api_key": secret("OPENALEX_API_KEY")})
    return {norm(w["doi"]): w["cited_by_count"] for w in data.get("results", []) if w.get("doi")}


def _crossref(dois: list[str]) -> dict[str, int]:
    safe = [d for d in dois if "," not in d]  # commas would split the filter
    data = _get(CROSSREF, {"filter": ",".join(f"doi:{d}" for d in safe), "rows": BATCH,
                           "select": "DOI,is-referenced-by-count"})
    return {norm(w["DOI"]): w.get("is-referenced-by-count") for w in data.get("message", {}).get("items", [])}


SOURCES = (("opencitations", _opencitations), ("openalex", _openalex), ("crossref", _crossref))


def counts(dois: list[str]) -> dict[str, dict]:
    """DOI (normalized) -> {"count": int | None, "source": str | None, "fetched": ISO date}."""
    cache = json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else {}
    todo = sorted({norm(d) for d in dois if d} - set(cache))
    unavailable = set()
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        found, zero, remaining = {}, {}, list(batch)
        for name, fetch in SOURCES:
            if not remaining or name in unavailable:
                continue
            try:
                got = fetch(remaining)
            except (requests.RequestException, PermissionError, ValueError) as e:
                unavailable.add(name)
                log(f"citations: {name} unavailable ({e}); using the next source")
                continue
            for d, c in got.items():
                if c:
                    found[d] = (c, name)
                elif c == 0:
                    zero.setdefault(d, (0, name))
            remaining = [d for d in remaining if d not in found]
        for d in batch:
            count, source = found.get(d) or zero.get(d) or (None, None)
            cache[d] = {"count": count, "source": source, "fetched": date.today().isoformat()}
        by_source = {}
        for d in batch:
            by_source[cache[d]["source"] or "none"] = by_source.get(cache[d]["source"] or "none", 0) + 1
        log(f"  citations {i + 1}-{i + len(batch)} of {len(todo)}: {by_source}")
    if todo:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(cache, indent=0, sort_keys=True), encoding="utf-8")
    return {norm(d): cache[norm(d)] for d in dois if d}
