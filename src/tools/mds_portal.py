"""Thin wrapper over the MDS-Onto Open Portal client (mds_onto_open_api.py, vendored unchanged)."""
from functools import lru_cache

import requests

from src.config import secret
from src.tools import mds_onto_open_api as _api
from src.tools.progress import log

PORTAL = "https://www.mdsonto-portal.com:8443"
_warned = set()


@lru_cache
def list_ontologies() -> dict[str, str]:
    """Acronym -> name for every ontology on the portal."""
    r = requests.get(f"{PORTAL}/ontologies", timeout=60,
                     params={"apikey": secret("MDS_API_KEY"), "display_links": "false", "display_context": "false"})
    r.raise_for_status()
    return {o["acronym"]: o.get("name", "") for o in r.json()}


def check_acronyms(ontologies: str | None) -> tuple[str | None, list[str]]:
    """Keep only acronyms the portal knows (one unknown acronym makes the portal return nothing)."""
    if not ontologies:
        return None, []
    wanted = [o.strip() for o in ontologies.split(",") if o.strip()]
    try:
        known = list_ontologies()
    except requests.RequestException:
        return ontologies, []  # cannot verify; pass through unchanged
    return ",".join(o for o in wanted if o in known) or None, [o for o in wanted if o not in known]


def search(query: str, ontologies: str | None = None, max_results: int = 10, exact: bool = False) -> list[dict]:
    """ontologies: comma-separated portal acronyms, e.g. "MDS-ONTO,IOF,PMDCO,QUDT". Unknown ones are dropped."""
    ontologies, unknown = check_acronyms(ontologies)
    if unknown and tuple(unknown) not in _warned:
        _warned.add(tuple(unknown))
        log(f"MDS portal: unknown ontology acronyms ignored: {', '.join(unknown)}")
    return _api.search_mds_ontology(query, ontologies=ontologies, max_results=max_results,
                                    require_exact_match=exact, api_key=secret("MDS_API_KEY"))


def domains() -> dict:
    return _api.get_ontology_domains()
