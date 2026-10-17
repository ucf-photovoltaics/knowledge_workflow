"""Verify information flow and saved concept provenance without executing the pipeline.

Author: Brent Thompson <brent.thompson@ucf.edu>
Exercises paper-local identities, lineage uncertainty, source graph membership and safe snapshots.
"""
import json
from pathlib import Path
import sys
import pytest
from rdflib import Graph, RDF, OWL, URIRef, Literal, SKOS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from codebase_ontology import KW, CCO, function_node
from data_journey import build_traces, export_traces, Snapshot, identifier


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')


@pytest.fixture
def saved(tmp_path):
    outputs=tmp_path/'outputs';run=outputs/'domain-n15';run.mkdir(parents=True)
    concepts=[{'id':'k1','label':'tunnel oxide layer','alt_labels':['tunnel oxide','SiO2 film'],'papers':['P1','P2']},
              {'id':'k2','label':'silicon','alt_labels':[],'papers':['P1']}]
    write(run/'normalized/concepts.json',concepts)
    for key,label in [('P1','tunnel oxide'),('P2','SiO2 film')]:
        write(run/'papers'/(key+'.json'),{'key':key,'title':'Source '+key,'doi':'10.1234/'+key,'pdf':'PRIVATE_LOCAL_PATH','raw_calls':['PRIVATE_RAW_CALL'],
              'parse_stats':{'pages':5},'concepts':[{'id':'c1','label':label,'figures':['F1']},{'id':'c2','label':'silicon'}],
              'relations':[{'s':'c1','p':'part_of','o':'c2','evidence':'The tunnel oxide is part of the contact.','verified':True}],
              'causal':[],'measurements':[],'figures':[{'id':'F1','label':'Figure 1','page':2,'caption':'A contact cross section.'}]})
    write(run/'normalized/relations.json',[{'s':'k1','p':'part_of','o':'k2','evidence':[{'paper':'P1','text':'A contact.','verified':True}]}])
    for kind in ('causal','measurements'):write(run/'normalized'/(kind+'.json'),[])
    classes=[{**c,'iri':'https://example.org/'+c['id'],'parent':'http://purl.obolibrary.org/obo/BFO_0000040','parent_source':'fixture','excluded':False} for c in concepts]
    write(run/'ontology/classes.json',classes)
    write(run/'ontology/enriched.json',[{**c,'definition':'','definition_status':'none','restrictions':[],'review_flags':['unsupported_definition']} for c in classes])
    write(run/'ontology/mappings.json',[{'id':'k1','iri':'https://external.org/oxide','label':'Oxide','relation':'close'}])
    g=Graph()
    for c in classes:g.add((URIRef(c['iri']),RDF.type,OWL.Class))
    g.add((URIRef(classes[0]['iri']),SKOS.definition,Literal('An imported oxide definition.')))
    (run/'ontology.ttl').write_text(g.serialize(format='turtle'),encoding='utf-8')
    claims=Graph();claims.add((URIRef('https://example.org/concept/oxide'),URIRef('https://example.org/ontologyClass'),URIRef(classes[0]['iri'])))
    (run/'domain_layer.ttl').write_text(claims.serialize(format='turtle'),encoding='utf-8')
    integration=outputs/'integration-n15';integration.mkdir()
    write(integration/'integration.json',{'inputs':[{'run_id':run.name,'domain':'a'},{'run_id':'other','domain':'b'}],'ontology':{'files':['master_merged.ttl']}})
    write(integration/'mappings.json',[]);write(integration/'bridge_concepts.json',[])
    (integration/'master_merged.ttl').write_text(g.serialize(format='turtle'),encoding='utf-8')
    return outputs,run,integration


def target(package):
    return next(c for c in package['concepts'] if c['id']=='k1')


def test_ontology_models_information_transformations_with_real_implementations():
    g=Graph().parse(ROOT/'docs/ontology/knowledge-workflow.ttl')
    assert len(set(g.subjects(RDF.type,KW.InformationStateSpecification)))==10
    assert len(set(g.subjects(RDF.type,KW.InformationTransformationSpecification)))==9
    t=KW['transformation/normalize']
    assert (t,KW.transformsInputState,KW['information/extracted']) in g
    assert (t,KW.producesInformationState,KW['information/canonical']) in g
    assert (t,KW.transformationImplementation,function_node('src/agents/normalization.py','NormalizationAgent.run')) in g
    assert (KW['transformation/report'],KW.optionalInputState,KW['information/integrated']) in g
    assert (KW.InformationStateSpecification,URIRef('http://www.w3.org/2000/01/rdf-schema#subClassOf'),CCO.ont00000965) in g
    assert all(g.value(n,SKOS.definition) for kind in (KW.InformationStateSpecification,KW.InformationTransformationSpecification) for n in g.subjects(RDF.type,kind))


def test_agent_guide_exposes_retained_and_omitted_information():
    from operational_contracts import guide
    g=Graph().parse(ROOT/'docs/ontology/knowledge-workflow.ttl')
    recipe=guide(g,'normalize')
    t=next(t for t in recipe['information_transformations'] if t['id']=='normalize')
    assert t['from']==['extracted'] and t['to']==['canonical']
    assert 'saved original-to-canonical identity map' in t['adds']
    assert any(function.endswith('NormalizationAgent._lineage') for function in t['functions'])
    assert 'legacy n15' in t['limitation']


def test_repeated_paper_local_ids_remain_distinct_candidates(saved):
    outputs,run,integration=saved
    c=target(build_traces(outputs,run.name,integration.name))
    assert {(o['paper'],o['concept']['id']) for o in c['original_candidates']}=={('P1','c1'),('P2','c1')}
    assert all(o['status']=='reconstructed-candidate' for o in c['original_candidates'])
    assert c['lineage']['status']=='unavailable-exact-map'
    assert c['placed']['id']==c['canonical']['id']=='k1'


def test_original_label_shared_by_canonical_targets_is_ambiguous(saved):
    outputs,run,_=saved;path=run/'normalized/concepts.json';rows=json.loads(path.read_text())
    rows.append({'id':'k3','label':'different oxide','alt_labels':['tunnel oxide'],'papers':['P1']});write(path,rows)
    c=target(build_traces(outputs,run.name))
    original=next(o for o in c['original_candidates'] if o['paper']=='P1')
    assert original['status']=='reconstructed-ambiguous' and original['candidate_canonical_ids']==['k1','k3']


def test_partial_recorded_map_is_not_filled_with_inferred_merges(saved):
    outputs,run,_=saved
    write(run/'normalized/concept_lineage.json',[{'paper':'P1','original_id':'c1','original_label':'tunnel oxide','canonical_id':'k1','canonical_label':'tunnel oxide layer'}])
    c=target(build_traces(outputs,run.name))
    assert c['lineage']['status']=='recorded-map-with-possible-gaps'
    assert len(c['original_candidates'])==1 and c['original_candidates'][0]['status']=='recorded'


def test_changed_saved_lineage_label_requires_review(saved):
    outputs,run,_=saved
    write(run/'normalized/concept_lineage.json',[{'paper':'P1','original_id':'c1','original_label':'Wrong label','canonical_id':'k1'}])
    assert target(build_traces(outputs,run.name))['original_candidates'][0]['status']=='recorded-needs-review'


def test_merged_membership_is_independent_of_cross_domain_mapping(saved):
    outputs,run,integration=saved;c=target(build_traces(outputs,run.name,integration.name))
    assert c['exports']['formal_class_present'] is True
    assert c['exports']['literature_concept_iris']==['https://example.org/concept/oxide']
    assert c['integration']['merged_class_present'] is True and c['integration']['mappings']==[]
    assert c['exports']['formal_definitions']==['An imported oxide definition.']


def test_integration_not_selecting_run_does_not_claim_membership(saved):
    outputs,run,integration=saved
    write(integration/'integration.json',{'inputs':[{'run_id':'another-run'}],'ontology':{'files':['master_merged.ttl']}})
    c=target(build_traces(outputs,run.name,integration.name))
    assert c['integration']['source_run_recorded'] is False and c['integration']['merged_class_present'] is None


def test_changed_iri_and_reviewed_aliases_are_not_hidden(saved):
    outputs,run,_=saved;path=run/'ontology/enriched.json';rows=json.loads(path.read_text())
    rows[0]['iri']='https://example.org/changed';rows[0]['alt_labels']=['tunnel oxide','reviewed oxide'];write(path,rows)
    c=target(build_traces(outputs,run.name))
    assert 'IRI changed' in c['identity_warning'] and c['exports']['formal_class_present'] is False
    assert c['enrichment_alias_changes']=={'added':['reviewed oxide'],'removed':['SiO2 film']}


def test_snapshots_are_read_only_redacted_and_links_resolve(saved,tmp_path):
    outputs,run,integration=saved
    before={p:p.read_bytes() for p in outputs.rglob('*') if p.is_file()};destination=tmp_path/'preview'
    export_traces(outputs,destination,run.name,integration.name)
    index=json.loads((destination/'concept-journey.json').read_text())
    c=json.loads((destination/next(x['path'] for x in index['concepts'] if x['id']=='k1')).read_text())
    for p in c['papers']:
        assert (destination/p['href']).is_file()
        html=(destination/p['href']).read_text()
        assert 'PRIVATE_RAW_CALL' not in html and 'PRIVATE_LOCAL_PATH' not in html
        assert 'id="c1"' in html and 'id="figure-F1"' in html
    assert all(p.read_bytes()==data for p,data in before.items())


def test_snapshot_detects_source_change(saved):
    outputs,run,_=saved;snapshot=Snapshot(outputs);snapshot.read(run.name+'/normalized/concepts.json')
    write(run/'normalized/concepts.json',[])
    with pytest.raises(ValueError,match='changed'):snapshot.fingerprints()


@pytest.mark.parametrize('bad',['../run','a/b','C:\\private','..','a..b'])
def test_unsafe_identifiers_are_rejected(bad):
    with pytest.raises(ValueError):identifier(bad)
