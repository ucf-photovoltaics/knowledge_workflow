"""Ontology store on two tiny ontologies: home attribution, label search, ancestors, mapping propagation."""
import pytest

pytest.importorskip("pyoxigraph")

from src.tools import ontostore

OBO = "http://purl.obolibrary.org/obo/"
BFO = f"""@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
<{OBO}bfo.owl> a owl:Ontology ; owl:versionInfo "2020" .
<{OBO}BFO_0000001> a owl:Class ; rdfs:label "entity" .
<{OBO}BFO_0000019> a owl:Class ; rdfs:label "quality" ; rdfs:subClassOf <{OBO}BFO_0000001> .
"""
MDS = f"""@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> . @prefix mds: <https://cwrusdle.bitbucket.io/mds/> .
<https://cwrusdle.bitbucket.io/mds/Ontology> a owl:Ontology ; owl:versionInfo "0.3.1.36" .
<{OBO}BFO_0000019> a owl:Class ; rdfs:label "Quality (MDS copy)" .
mds:OpenCircuitVoltage a owl:Class ; rdfs:label "OpenCircuitVoltage" ; skos:altLabel "Voc" ;
    skos:definition "The voltage across a cell with no current flowing." ;
    rdfs:subClassOf <{OBO}BFO_0000019> ; skos:exactMatch mds:OCP .
mds:OCP a owl:Class ; rdfs:label "open circuit potential" ; skos:closeMatch mds:Potential .
mds:Potential a owl:Class ; rdfs:label "electric potential" .
mds:Old a owl:Class ; rdfs:label "obsolete voltage" ; owl:deprecated true .
"""


@pytest.fixture
def store(tmp_path, monkeypatch):
    files, root = tmp_path / "ontologies", tmp_path / "store"
    files.mkdir()
    (files / "BFO.ttl").write_text(BFO)
    (files / "MDS.ttl").write_text(MDS)
    monkeypatch.setattr(ontostore, "FILES", files)
    monkeypatch.setattr(ontostore, "ONTOLOGY_STORE", root)
    monkeypatch.setattr(ontostore, "DB", root / "terms.sqlite")
    monkeypatch.setattr(ontostore, "VECTORS", root / "vectors.npy")
    monkeypatch.setattr(ontostore, "MANIFEST", root / "manifest.json")
    monkeypatch.setattr(ontostore, "ONTOLOGY_SOURCES", {
        "BFO": {"url": "unused", "file": "BFO.ttl", "home": [f"{OBO}BFO_"]},
        "MDS-Onto": {"url": "unused", "file": "MDS.ttl", "home": ["https://cwrusdle.bitbucket.io/mds/"]}})
    monkeypatch.setitem(ontostore.EMBED, "model", None)
    ontostore.build()
    yield ontostore
    ontostore._reset()


def test_build_and_lookups(store):
    assert store.status(check_portal=False)["problems"] == []
    assert store.manifest()["sources"]["MDS-Onto"]["version"] == "0.3.1.36"
    assert store.term(f"{OBO}BFO_0000019")["ontology"] == "BFO"  # re-declared by MDS-Onto, still BFO's
    ocv = "https://cwrusdle.bitbucket.io/mds/OpenCircuitVoltage"
    assert [t["iri"] for t in store.exact("open-circuit voltage")] == [ocv]
    assert store.exact("obsolete voltage") == []  # deprecated
    assert store.exact("-") == []
    assert store.ancestors(ocv) == (f"{OBO}BFO_0000019", f"{OBO}BFO_0000001") and store.reaches_bfo(ocv)
    hits = store.search(["open circuit voltage", "Voc"], kinds=("class",))
    assert hits[0]["iri"] == ocv and hits[0]["exact"]
    hops = {p["iri"].rsplit("/", 1)[-1]: (p["hop"], p["relations"]) for p in store.propagate(ocv)}
    assert hops == {"OCP": (1, ["exact"]), "Potential": (2, ["exact", "close"])}
    assert store.score(ocv, ["Voc"])["exact"] is True
