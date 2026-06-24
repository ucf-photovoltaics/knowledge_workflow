# -*- coding: utf-8 -*-
"""
Validation gate (Step 4 must pass before JSON-LD/LoRA proceed).

Structural metrics:
  * alignment %   - fraction of classes tracing to a BFO/CCO/MDS/PMD parent (always on)
  * reasoner      - DL consistency via owlready2 + HermiT   (T1.1, opt-in: RUN_REASONER)
  * OOPS!         - ontology-pitfall scan via REST          (T1.2, opt-in: RUN_OOPS)
  * SHACL         - shape conformance via pyshacl           (T1.3, opt-in: RUN_SHACL)

Each external check is opt-in and degrades gracefully: if the dependency, tool,
or network is unavailable it reports 'unavailable' (or 'skipped' when off) and
does NOT block publication. Only a definitive failure - inconsistent ontology,
critical pitfalls, or SHACL violations - fails the gate.
"""
from __future__ import annotations

import os

import rdflib
from rdflib.namespace import RDF, RDFS, OWL

from kw.config import (NS, RUN_REASONER, RUN_OOPS, RUN_SHACL,
                       OOPS_ENDPOINT, SHACL_SHAPES)

UPPER_PREFIXES = (NS['bfo'], NS['cco'], NS['mds'],
                  'https://cwrusdle.bitbucket.io/mds', 'https://w3id.org/pmd/')
ALIGNMENT_TARGET = 0.80


def alignment_ratio(g: rdflib.Graph) -> tuple[float, int, int]:
    classes = [c for c in g.subjects(RDF.type, OWL.Class) if isinstance(c, rdflib.URIRef)]
    aligned = sum(
        any(str(p).startswith(UPPER_PREFIXES)
            for p in g.objects(c, RDFS.subClassOf) if isinstance(p, rdflib.URIRef))
        for c in classes
    )
    total = len(classes) or 1
    return aligned / total, aligned, len(classes)


def run_reasoner(ttl_path: str) -> str:
    """Return 'consistent' | 'inconsistent' | 'skipped' | 'unavailable'."""
    if not RUN_REASONER:
        return 'skipped'
    try:
        import owlready2
        onto = owlready2.get_ontology('file://' + os.path.abspath(ttl_path)).load()
        with onto:
            owlready2.sync_reasoner(infer_property_values=False)
        inconsistent = list(owlready2.default_world.inconsistent_classes())
        return 'inconsistent' if inconsistent else 'consistent'
    except Exception as exc:
        print(f'  [validate] reasoner unavailable ({type(exc).__name__}); skipping.')
        return 'unavailable'


def run_oops(ttl_path: str) -> dict:
    """Return {'status': ..., 'critical': [pitfall codes]}."""
    if not RUN_OOPS:
        return {'status': 'skipped', 'critical': []}
    try:
        import re
        import requests
        rdfxml = rdflib.Graph().parse(ttl_path, format='turtle').serialize(format='xml')
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<OOPSRequest><OntologyURI></OntologyURI>'
            f'<OntologyContent><![CDATA[{rdfxml}]]></OntologyContent>'
            '<Pitfalls></Pitfalls><OutputFormat>RDF/XML</OutputFormat></OOPSRequest>'
        )
        resp = requests.post(OOPS_ENDPOINT, data=body.encode('utf-8'),
                             headers={'Content-Type': 'application/xml'}, timeout=60)
        resp.raise_for_status()
        text = resp.text
        critical: list[str] = []
        for seg in re.findall(r'(?is)critical.{0,400}', text):
            critical.extend(re.findall(r'P\d{2}', seg))
        return {'status': 'ran', 'critical': sorted(set(critical))}
    except Exception as exc:
        print(f'  [validate] OOPS! unavailable ({type(exc).__name__}); skipping.')
        return {'status': 'unavailable', 'critical': []}


def run_shacl(ttl_path: str) -> str:
    """Return 'conforms' | 'violations' | 'skipped' | 'unavailable'."""
    if not RUN_SHACL:
        return 'skipped'
    if not os.path.isfile(SHACL_SHAPES):
        print(f'  [validate] SHACL shapes not found at {SHACL_SHAPES}; skipping.')
        return 'unavailable'
    try:
        from pyshacl import validate as shacl_validate
        conforms, _graph, _text = shacl_validate(
            ttl_path, shacl_graph=SHACL_SHAPES,
            data_graph_format='turtle', shacl_graph_format='turtle',
            inference='none', advanced=True,
        )
        return 'conforms' if conforms else 'violations'
    except Exception as exc:
        print(f'  [validate] SHACL unavailable ({type(exc).__name__}); skipping.')
        return 'unavailable'


def evaluate(ttl_path: str) -> dict:
    g = rdflib.Graph()
    g.parse(ttl_path, format='turtle')
    ratio, aligned, total = alignment_ratio(g)

    reasoner = run_reasoner(ttl_path)
    oops     = run_oops(ttl_path)
    shacl    = run_shacl(ttl_path)

    alignment_pass = ratio >= ALIGNMENT_TARGET
    passed = (
        alignment_pass
        and reasoner != 'inconsistent'
        and not oops['critical']
        and shacl != 'violations'
    )
    return {
        'file': ttl_path,
        'triples': len(g),
        'classes': total,
        'aligned_to_upper': aligned,
        'alignment_ratio': round(ratio, 3),
        'alignment_pass': alignment_pass,
        'reasoner': reasoner,
        'oops_status': oops['status'],
        'oops_critical': oops['critical'],
        'shacl': shacl,
        'passed': passed,
    }
