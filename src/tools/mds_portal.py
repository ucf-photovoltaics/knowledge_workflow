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
    # The vendored search swallows HTTP/JSON errors as [], which cannot safely be negative-cached.
    if max_results < 1:
        raise ValueError("Portal search result limit must be positive")
    out, page = [], 1
    while len(out) < max_results:
        params = {"q": query, "apikey": secret("MDS_API_KEY"), "page": page, "pagesize": min(50, max_results),
                  "require_exact_match": "true" if exact else "false", "also_search_properties": "true",
                  "also_search_obsolete": "false", "include": "prefLabel,synonym,definition,properties,cui,semanticType"}
        if ontologies:
            params["ontologies"] = ontologies
        response = requests.get(f"{PORTAL}/search", params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("collection"), list):
            raise ValueError("MDS portal returned no search collection")
        for r in data["collection"]:
            if not r.get("@id") or not r.get("prefLabel"):
                continue
            props = r.get("properties") or {}
            definition = _api._extract_property(props, _api.PROPERTY_MAP["definition"])
            if definition == "N/A" and r.get("definition"):
                defs = r["definition"]
                definition = "; ".join(defs) if isinstance(defs, list) else str(defs)
            out.append({"Label": r["prefLabel"], "ID": r["@id"],
                        "Ontology": str((r.get("links") or {}).get("ontology", "")).rsplit("/", 1)[-1] or "Unknown",
                        "Definition": definition,
                        **{f"MDS_{label}": _api._extract_property(props, _api.PROPERTY_MAP[prop])
                           for label, prop in (("Domain", "domain"), ("SubDomain", "subDomain"),
                                               ("StudyStage", "studyStage"))}})
        if not data["collection"] or page >= int(data.get("pageCount", page)):
            break
        page += 1
    return out[:max_results]


def domains() -> dict:
    return _api.get_ontology_domains()
