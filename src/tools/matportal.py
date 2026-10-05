"""MatPortal (matportal.org, the materials-science OntoPortal) search over its REST API.

Returns records in the same shape as mds_portal.search ({"Label", "ID", "Ontology", "Definition"}) so enrichment
treats both portals alike. Needs MATPORTAL_API_KEY in .env (from your matportal.org account).
"""
from functools import lru_cache

import requests

from src.config import MATPORTAL, secret
from src.tools.progress import log

_warned = set()


def _get(path: str, params: dict):
    r = requests.get(MATPORTAL["base_url"].rstrip("/") + path, timeout=60,
                     params={"apikey": secret("MATPORTAL_API_KEY"), **params})
    r.raise_for_status()
    return r.json()


@lru_cache
def list_ontologies() -> dict[str, str]:
    """Acronym -> name for every ontology on MatPortal."""
    return {o["acronym"]: o.get("name", "") for o in _get("/ontologies", {"display_links": "false",
                                                                         "display_context": "false"})}


def check_acronyms(ontologies: str | None) -> tuple[str | None, list[str]]:
    """Keep only acronyms MatPortal knows (an unknown acronym makes OntoPortal return nothing)."""
    if not ontologies:
        return None, []
    wanted = [o.strip() for o in ontologies.split(",") if o.strip()]
    try:
        known = list_ontologies()
    except requests.RequestException:
        return ontologies, []
    return ",".join(o for o in wanted if o in known) or None, [o for o in wanted if o not in known]


def search(query: str, ontologies: str | None = None, max_results: int = 10, exact: bool = False) -> list[dict]:
    ontologies, unknown = check_acronyms(ontologies)
    if unknown and tuple(unknown) not in _warned:
        _warned.add(tuple(unknown))
        log(f"MatPortal: unknown ontology acronyms ignored: {', '.join(unknown)}")
    params = {"q": query, "pagesize": max_results, "include": "prefLabel,definition", "display_context": "false",
              "require_exact_match": "true" if exact else "false"}
    if ontologies:
        params["ontologies"] = ontologies
    data = _get("/search", params)
    if not isinstance(data, dict) or not isinstance(data.get("collection"), list):
        raise ValueError("MatPortal returned no search collection")
    out = []
    for r in data["collection"][:max_results]:
        onto = str((r.get("links") or {}).get("ontology", "")).rstrip("/").rsplit("/", 1)[-1]
        d = r.get("definition") or []
        if r.get("@id") and r.get("prefLabel"):
            out.append({"Label": r["prefLabel"], "ID": r["@id"], "Ontology": onto or "MATPORTAL",
                        "Definition": "; ".join(d) if isinstance(d, list) else str(d)})
    return out
