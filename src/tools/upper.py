"""BFO 2020 + CCO terms and OBO Relations Ontology (RO) properties, cached in resources/upper/bfo_cco.json,
plus the curated menus shown to agents."""
import json
from functools import lru_cache

from src.config import RESOURCES

UPPER = RESOURCES / "upper"
CCO_RAW = "https://raw.githubusercontent.com/CommonCoreOntology/CommonCoreOntologies/develop/src"
SOURCE_FILES = [f"{CCO_RAW}/cco-iris/CommonCoreOntologiesMerged.ttl", f"{CCO_RAW}/cco-imports/bfo-core.ttl"]
RO_FILE = "https://raw.githubusercontent.com/oborel/obo-relations/master/ro.owl"
PREFIX = {"bfo": "BFO", "cco": "CCO", "ro": "RO"}
ENTITY = "http://purl.obolibrary.org/obo/BFO_0000001"


def build():
    """Refresh bfo_cco.json from the CCO and RO repositories (only needed for new CCO/BFO/RO releases)."""
    import rdflib
    from rdflib.namespace import OWL, RDF, RDFS, SKOS
    g = rdflib.Graph()
    for url in SOURCE_FILES:
        g.parse(url, format="turtle")

    def txt(s, p):
        v = g.value(s, p)
        return str(v) if v else ""

    def named(objs):
        return sorted(str(o) for o in objs if isinstance(o, rdflib.URIRef))

    def src(s):
        return "bfo" if "purl.obolibrary.org/obo/BFO_" in str(s) else "cco"

    out = {"sources": {"bfo": "http://purl.obolibrary.org/obo/bfo.owl",
                       "cco": "https://www.commoncoreontologies.org/CommonCoreOntologiesMerged",
                       "ro": "http://purl.obolibrary.org/obo/ro.owl"},
           "classes": {}, "properties": {}}
    for s in g.subjects(RDF.type, OWL.Class):
        if isinstance(s, rdflib.URIRef) and g.value(s, RDFS.label):
            out["classes"][str(s)] = {"label": txt(s, RDFS.label), "definition": txt(s, SKOS.definition),
                                      "source": src(s), "parents": named(g.objects(s, RDFS.subClassOf))}
    for s in g.subjects(RDF.type, OWL.ObjectProperty):
        if isinstance(s, rdflib.URIRef) and g.value(s, RDFS.label):
            d, r, inv = g.value(s, RDFS.domain), g.value(s, RDFS.range), g.value(s, OWL.inverseOf)
            out["properties"][str(s)] = {
                "label": txt(s, RDFS.label), "definition": txt(s, SKOS.definition), "source": src(s),
                "domain": str(d) if isinstance(d, rdflib.URIRef) else None,
                "range": str(r) if isinstance(r, rdflib.URIRef) else None,
                "inverse": str(inv) if isinstance(inv, rdflib.URIRef) else None,
                "parents": named(g.objects(s, RDFS.subPropertyOf))}

    ro = rdflib.Graph().parse(RO_FILE, format="xml")  # RO properties not already defined by BFO/CCO
    iao_def = rdflib.URIRef("http://purl.obolibrary.org/obo/IAO_0000115")
    for s in ro.subjects(RDF.type, OWL.ObjectProperty):
        if isinstance(s, rdflib.URIRef) and ro.value(s, RDFS.label) and str(s) not in out["properties"]:
            d, r, inv = ro.value(s, RDFS.domain), ro.value(s, RDFS.range), ro.value(s, OWL.inverseOf)
            out["properties"][str(s)] = {
                "label": str(ro.value(s, RDFS.label)), "definition": str(ro.value(s, iao_def) or ""), "source": "ro",
                "domain": str(d) if isinstance(d, rdflib.URIRef) else None,
                "range": str(r) if isinstance(r, rdflib.URIRef) else None,
                "inverse": str(inv) if isinstance(inv, rdflib.URIRef) else None,
                "parents": sorted(str(o) for o in ro.objects(s, RDFS.subPropertyOf) if isinstance(o, rdflib.URIRef))}
    (UPPER / "bfo_cco.json").write_text(json.dumps(out, indent=0), encoding="utf-8")
    terms.cache_clear()
    _property_index.cache_clear()


@lru_cache
def terms() -> dict:
    return json.loads((UPPER / "bfo_cco.json").read_text(encoding="utf-8"))


@lru_cache
def facets() -> dict:
    """MDS-Onto study stages and MDSDom domains/subdomains (resources/upper/mds_facets.json)."""
    return json.loads((UPPER / "mds_facets.json").read_text(encoding="utf-8"))


@lru_cache
def menus() -> dict:
    return json.loads((UPPER / "menus.json").read_text(encoding="utf-8"))


def class_menu() -> dict[str, str]:
    """Curated upper classes: label -> IRI."""
    idx = {v["label"].lower(): iri for iri, v in terms()["classes"].items()}
    return {lab: idx[lab.lower()] for lab in menus()["classes"] if lab.lower() in idx}


@lru_cache
def _property_index() -> dict[str, str]:
    """'SOURCE:label' (lowercase) -> IRI, e.g. 'ro:has quality'. Labels repeat across BFO/CCO/RO."""
    return {f"{PREFIX[v['source']]}:{v['label']}".lower(): iri for iri, v in terms()["properties"].items()}


def property_menu() -> dict[str, str]:
    """Curated BFO/CCO/RO properties side by side: 'SOURCE:label' -> IRI."""
    return {k: _property_index()[k.lower()] for k in menus()["properties"] if k.lower() in _property_index()}


def property_iri(key: str) -> str | None:
    """IRI for 'SOURCE:label', e.g. 'CCO:affects'."""
    return _property_index().get(key.lower())


def ancestors(iri: str) -> list[str]:
    """All named upper ancestors of an upper class, nearest first."""
    classes, seen, queue = terms()["classes"], [], list(terms()["classes"].get(iri, {}).get("parents", []))
    while queue:
        p = queue.pop(0)
        if p not in seen:
            seen.append(p)
            queue += classes.get(p, {}).get("parents", [])
    return seen


def describe(iri: str) -> dict:
    return terms()["classes"].get(iri) or terms()["properties"].get(iri) or {}
