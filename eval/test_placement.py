# -*- coding: utf-8 -*-
"""
Offline tests for the MDS-Onto grounding refactor.

What changed and why these tests exist:

  1. Eight of the ten branch classes were minted INSIDE the mds: namespace
     (Process, Device, Characterization, Reliability, Economics,
     ResearchPublication, Concept, and an unverified Sample). Only Material and
     Measurement were real MDS-Onto terms. "Grounded in MDS-Onto" was therefore
     not true of any run.
  2. mds:Concept was a catch-all absorbing ~41% of concepts. "Could not decide"
     and "is a generic concept" were recorded as the same fact.
  3. Branch classes were re-parented under that minted catch-all, overriding
     whatever real hierarchy MDS-Onto defines for Material and Measurement.
  4. A BFO block emitted obo: IRIs directly. MDS-Onto is already BFO-grounded via
     PMDco, so real MDS terms bring that transitively and Kweave needs none.

Runs offline: no portal, no LLM, no network. PLACEMENT_LLM is forced off so the
ladder degrades to keywords deterministically.

    python eval/test_placement.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ['PLACEMENT_LLM'] = 'false'
os.environ['DEFINE_CONCEPTS'] = 'false'
os.environ['CONCEPT_CLASSES'] = 'true'

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kw import ontology, placement  # noqa: E402

FAILURES = []


def check(cond, msg):
    if cond:
        print(f'  ok   {msg}')
    else:
        print(f'  FAIL {msg}')
        FAILURES.append(msg)


# ---------------------------------------------------------------------------
def test_branch_set_is_real():
    print('\n[1] every branch is a real MDS-Onto term, in the mds/ namespace')
    for curie, iri in ontology.MDS_BRANCHES.items():
        check(iri.startswith(ontology.MDS_BASE), f'{curie} is under mds/')

    retired = {'mds:Process', 'mds:Device', 'mds:Characterization',
               'mds:Reliability', 'mds:Economics', 'mds:ResearchPublication',
               'mds:Concept'}
    for r in retired:
        check(r not in ontology.MDS_BRANCHES, f'{r} is no longer a branch')

    check(not hasattr(ontology, '_CLASS_UPPER_PARENTS'),
          'the BFO upper-parent table is gone')
    check(not hasattr(ontology, '_MDS_CLASSES'),
          'the old minted branch table is gone')

    print('\n[2] the six canonical domains use the mdsdom namespace')
    check(ontology.MDSDOM_BASE == 'https://cwrusdle.bitbucket.io/mdsdom/',
          'mdsdom base matches what the portal serves')
    for d in ('Expo', 'Manufact', 'Charact', 'BuildEnv', 'Geo', 'Chem'):
        check(ontology.MDSDOM[d].startswith(ontology.MDSDOM_BASE), f'{d} under mdsdom/')

    print('\n[3] minted terms live outside mds:')
    check(ontology.KW_RESEARCH_RECORD.startswith(ontology.KW_BASE),
          'ResearchPublication is minted in kw:, not mds:')
    check(not ontology.KW_RESEARCH_RECORD.startswith(ontology.MDS_BASE),
          'ResearchPublication is NOT inside the mds: namespace')


# ---------------------------------------------------------------------------
def test_classifier_returns_none():
    print('\n[4] the keyword rung returns None instead of a catch-all')
    check(ontology._classify_concept('zzzz unmatchable qqqq') is None,
          'an unmatched concept yields None, not mds:Concept')
    check(ontology._classify_concept('open circuit voltage') == 'mds:Property',
          'a measured quantity routes to mds:Property')
    check(ontology._classify_concept('surface passivation layer') == 'mds:Material',
          'surface passivation layer is a Material, not a Characterization')
    check(ontology._classify_concept('contact resistance') == 'mds:Property',
          'contact resistance is a Property, not a Material')
    check(ontology._classify_concept('scanning electron microscope') == 'mds:Equipment',
          'an instrument routes to mds:Equipment')
    check(ontology._classify_concept('silicon wafer') == 'mds:Sample',
          'a specimen routes to mds:Sample')

    print('\n[5] placement records every decision')
    placements, stats = ontology.place_concepts(
        ['open circuit voltage', 'silver paste', 'zzzz unmatchable qqqq'], {})
    check(stats.total == 3, 'all three concepts accounted for')
    check(stats.counts['unplaced'] == 1, 'exactly one unplaced')
    check('zzzz unmatchable qqqq' in stats.report()['unplaced_concepts'],
          'the unplaced concept is named in the report')
    check(placements['zzzz unmatchable qqqq'] is None, 'unplaced maps to None')

    print('\n[6] a portal match short-circuits the ladder')
    matches = {'silver paste': {'iri': ontology.MDS_BASE + 'Material',
                                'definition': 'x', 'domain': '', 'subdomain': '',
                                'study_stage': ''}}
    _, s2 = ontology.place_concepts(['silver paste'], matches)
    check(s2.counts['portal'] == 1, 'the portal rung claimed it')
    check(s2.counts['keyword'] == 0, 'keywords were not consulted')


# ---------------------------------------------------------------------------
def _fixture(tmp):
    d = Path(tmp) / 'testcoll'
    d.mkdir(parents=True, exist_ok=True)
    suffix = 'testcoll-Tester-v8-20260822'
    (d / f'schema_{suffix}.csv').write_text(
        'doi,domain,open circuit voltage,silver paste,zzzz unmatchable qqqq\n'
        '10.1/x,Photovoltaics,0.68 V | "Voc was 0.68 V",screen printed,foo\n',
        encoding='utf-8')
    (d / f'concepts_{suffix}.csv').write_text(
        'canonical,paper_term\n'
        'open circuit voltage,Voc\nsilver paste,Ag paste\n'
        'zzzz unmatchable qqqq,qqqq\n',
        encoding='utf-8')
    return str(d / f'schema_{suffix}.csv')


def test_emitted_ttl():
    print('\n[7] the emitted ontology')
    with tempfile.TemporaryDirectory() as tmp:
        schema = _fixture(tmp)
        out = ontology.build_collection_ontology(schema, tmp, 'Photovoltaics')
        ttl = Path(out).read_text(encoding='utf-8')

        check('/mds/Concept>' not in ttl and '/mds/Concept ' not in ttl,
              'no mds:Concept catch-all anywhere in the output')
        check('purl.obolibrary.org/obo/BFO_' not in ttl,
              'no BFO IRIs emitted (MDS-Onto carries that transitively)')
        for gone in ('/mds/Process>', '/mds/Device>', '/mds/Reliability>',
                     '/mds/Economics>', '/mds/ResearchPublication>'):
            check(gone not in ttl, f'no minted {gone.strip("<>/")} class')

        check(f'<{ontology.MDS_BASE}Material>' in ttl, 'mds:Material is referenced')
        check(f'rdfs:isDefinedBy <{ontology.MDS_BASE}>' in ttl,
              'reused branches carry rdfs:isDefinedBy (MIREOT stub)')
        check(ontology.MDSDOM_BASE in ttl, 'the mdsdom domain namespace appears')
        check(ontology.KW_BASE in ttl, 'minted terms use the kw: namespace')

        # the unplaced concept must hang off a real domain root, not a fake class
        check('Zzzz' in ttl or 'zzzz' in ttl, 'the unplaced concept still made it in')

        rep = json.loads((Path(tmp) / 'testcoll' / 'placement_report.json')
                         .read_text(encoding='utf-8'))
        check(rep['total'] == 3, 'placement report counts every concept')
        check(rep['counts']['unplaced'] == 1, 'report names one unplaced concept')
        check('rates' in rep and 0 <= rep['rates']['keyword'] <= 1,
              'report carries a keyword fallback rate')

        print('\n[8] the ontology still parses as Turtle')
        try:
            import rdflib
            g = rdflib.Graph()
            g.parse(data=ttl, format='turtle')
            check(len(g) > 0, f'rdflib parsed {len(g)} triples')
        except ImportError:
            print('  --   rdflib not installed; skipped')


# ---------------------------------------------------------------------------
def test_iri_registry():
    print('\n[9] IRI registry pins a concept across relabels')
    from kw.iri_registry import IRIRegistry, normalise

    check(normalise('Open-Circuit Voltage') == normalise('open circuit voltage'),
          'hyphenation and case fold to the same key')
    check(normalise('solar cells') == normalise('solar cell'),
          'a trailing plural on the head word folds')
    check(normalise('glass') == 'glass', 'a real trailing ss is not stripped')
    check(normalise('stress') == 'stress', 'stress does not become stres')

    with tempfile.TemporaryDirectory() as tmp:
        reg = IRIRegistry(Path(tmp) / 'r.json')
        mint = lambda l: 'https://x/' + l.replace(' ', '')
        first = reg.iri_for('open circuit voltage', mint)
        again = reg.iri_for('Open-Circuit Voltage', mint)
        check(first == again, 'a reworded concept reuses its original IRI')
        check('Open-Circuit Voltage' in reg.alt_labels('open circuit voltage'),
              'the new surface form is retained as an altLabel')
        reg.save()
        reloaded = IRIRegistry(Path(tmp) / 'r.json')
        check(reloaded.iri_for('open circuit voltage', mint) == first,
              'pinning survives a reload')

    print('\n[10] a corrupt registry does not take the run down')
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / 'bad.json'
        bad.write_text('{not json at all', encoding='utf-8')
        reg = IRIRegistry(bad)
        check(len(reg) == 0, 'a corrupt registry rebuilds empty instead of raising')


def test_registry_end_to_end():
    print('\n[11] two runs, reworded concept, one class not two')
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / 'coll'
        d.mkdir(parents=True)
        sfx = 'coll-T-v8-20260822'
        (d / f'schema_{sfx}.csv').write_text(
            'doi,domain,open circuit voltage\n10.1/x,Photovoltaics,0.68 V\n', encoding='utf-8')
        (d / f'concepts_{sfx}.csv').write_text(
            'canonical,paper_term\nopen circuit voltage,Voc\n', encoding='utf-8')
        ontology.build_collection_ontology(str(d / f'schema_{sfx}.csv'), tmp, 'Photovoltaics')
        reg1 = json.loads((Path(tmp) / 'iri_registry.json').read_text(encoding='utf-8'))
        check(len(reg1) == 1, 'first run registers one concept')
        iri1 = list(reg1.values())[0]['iri']

        # second run, same concept reworded
        (d / f'schema_{sfx}.csv').write_text(
            'doi,domain,Open-Circuit Voltage\n10.1/x,Photovoltaics,0.68 V\n', encoding='utf-8')
        (d / f'concepts_{sfx}.csv').write_text(
            'canonical,paper_term\nOpen-Circuit Voltage,Voc\n', encoding='utf-8')
        ontology.build_collection_ontology(str(d / f'schema_{sfx}.csv'), tmp, 'Photovoltaics')
        reg2 = json.loads((Path(tmp) / 'iri_registry.json').read_text(encoding='utf-8'))
        check(len(reg2) == 1, 'the relabel did NOT mint a second class')
        check(list(reg2.values())[0]['iri'] == iri1, 'the IRI is unchanged across runs')


if __name__ == '__main__':
    test_branch_set_is_real()
    test_classifier_returns_none()
    test_emitted_ttl()
    test_iri_registry()
    test_registry_end_to_end()
    print()
    if FAILURES:
        print(f'{len(FAILURES)} check(s) failed:')
        for f in FAILURES:
            print(f'  - {f}')
        sys.exit(1)
    print('all checks passed')
