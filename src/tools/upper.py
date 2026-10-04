"""BFO 2020 + CCO terms and OBO Relations Ontology (RO) properties, cached in resources/upper/bfo_cco.json, the
curated menus (category roots, type defaults, causal rules, LoRA tasks), and lookups of any other external term
through the ontology store (src/tools/ontostore.py)."""
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
    """All named ancestors of an external class or property, nearest first: BFO/CCO from bfo_cco.json, every
    other ontology (MDS-Onto, PMDCO, IOF, ...) from the ontology store, followed up to BFO."""
    seen, queue = [], list(describe(iri).get("parents", []))
    while queue:
        p = queue.pop(0)
        if p not in seen and p != iri:
            seen.append(p)
            queue += describe(p).get("parents", [])
    return seen


def describe(iri: str) -> dict:
    """label, definition, source, parents (and domain, range, inverse for properties) of an external term:
    the curated BFO/CCO/RO cache first, then the ontology store when it is built."""
    found = terms()["classes"].get(iri) or terms()["properties"].get(iri)
    if found:
        return found
    from src.tools import ontostore
    return ontostore.term(iri) or {}


BFO = "http://purl.obolibrary.org/obo/BFO_"
CONTINUANT, OCCURRENT, IC, SDC = BFO + "0000002", BFO + "0000003", BFO + "0000004", BFO + "0000020"
MATERIAL, PROCESS = BFO + "0000040", BFO + "0000015"
# Paper-style relation phrases -> menu properties that formalize them, most specific first, and the subject/object
# categories the relation needs where the properties leave domain or range open. First property that fits wins.
RELATION_GROUPS = [
    (["part_of", "is_part_of", "component_of", "belongs_to"], ["BFO:continuant part of", "BFO:occurrent part of"], None, None),
    (["has_part", "contains", "consists_of", "includes"], ["BFO:has continuant part", "BFO:has occurrent part"], None, None),
    (["has_property", "has_quality", "characterized_by", "exhibits"], ["RO:has quality", "RO:has characteristic"], IC, None),
    (["has_disposition", "susceptible_to", "prone_to"], ["RO:has disposition"], None, None),
    (["has_function", "functions_as", "serves_to"], ["RO:has function"], None, None),
    (["has_role", "acts_as", "plays_role_of"], ["RO:has role"], None, None),
    (["capable_of", "can_perform"], ["RO:capable of"], None, None),
    (["has_input", "consumes", "takes_as_input"], ["CCO:has input", "RO:has input"], None, CONTINUANT),
    (["has_output", "produces", "yields", "generates"], ["CCO:has output", "RO:has output"], PROCESS, CONTINUANT),
    (["input_of", "used_in", "consumed_by"], ["CCO:is input of", "RO:input of"], CONTINUANT, PROCESS),
    (["output_of", "produced_by", "result_of"], ["CCO:is output of", "RO:output of"], CONTINUANT, PROCESS),
    (["participates_in", "involved_in", "takes_part_in"], ["RO:participates in", "BFO:participates in"], None, None),
    (["has_participant", "involves"], ["RO:has participant", "BFO:has participant"], None, None),
    (["located_in", "found_in", "positioned_in"], ["RO:located in"], None, None),
    (["adjacent_to", "next_to", "in_contact_with"], ["RO:adjacent to"], None, None),
    (["connected_to", "attached_to", "bonded_to"], ["RO:connected to"], IC, IC),
    (["composed_primarily_of", "mainly_made_of"], ["RO:composed primarily of"], None, None),
    (["derived_from", "made_from", "obtained_from"], ["RO:derives from"], MATERIAL, MATERIAL),
    (["transformation_of", "converted_from"], ["RO:transformation of"], MATERIAL, MATERIAL),
    (["measured_by", "quantified_by"], ["CCO:is measured by"], None, None),
    (["measures", "is_measurement_of"], ["CCO:is a measurement of"], None, None),
    (["describes", "is_about", "reports_on"], ["CCO:is about"], None, None),
    (["precedes", "followed_by", "comes_before"], ["BFO:precedes"], None, None),
    (["occurs_in", "takes_place_in"], ["BFO:occurs in"], OCCURRENT, IC),
    (["regulates", "controls", "tunes"], ["RO:regulates characteristic"], None, SDC),
    (["realizes", "manifests"], ["BFO:realizes"], None, None),
]
# Extraction predicates outside the groups above, and older predicate names, resolved to a group phrase.
EXTRA_GROUPS = [(["correlated_with", "correlates_with"], ["RO:correlated with"], None, None)]
ALIASES = {"made_of": "composed_primarily_of", "used_for": "capable_of", "derives_from": "derived_from",
           "is_measured_by": "measured_by"}


def relation_group(pred: str) -> tuple | None:
    """(properties, subject category, object category) for an extracted predicate, or None (is_a, related_to,
    or a phrase no group formalizes)."""
    p = ALIASES.get(pred, pred)
    return next(((props, s, o) for aliases, props, s, o in RELATION_GROUPS + EXTRA_GROUPS if p in aliases), None)


def relation_iri(pred: str) -> str | None:
    """One IRI for a predicate in the literature layer: the group's first property without a domain/range
    restriction (BFO/RO generic), else its first property."""
    group = relation_group(pred)
    generic = property_iri({"part_of": "RO:part of", "has_part": "RO:has part"}.get(ALIASES.get(pred, pred), ""))
    iris = [i for i in [generic, *(property_iri(k) for k in (group[0] if group else []))] if i]
    open_ = [i for i in iris if describe(i).get("domain") in (None, ENTITY) and describe(i).get("range") in (None, ENTITY)]
    return (open_ or iris or [None])[0]
