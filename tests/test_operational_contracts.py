"""Test task navigation, paper bindings, documented checks and explicit definition coverage.

Author: Brent Thompson <brent.thompson@ucf.edu>
Uses fixture runs and source-derived RDF only; never launches a pipeline or model.
"""
import json
from pathlib import Path
import sys
import pytest
from rdflib import Graph, RDF, SKOS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from codebase_ontology import KW, function_node
from operational_contracts import guide, assess


@pytest.fixture(scope='module')
def graph():
    return Graph().parse(ROOT/'docs/ontology/knowledge-workflow.ttl')


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data),encoding='utf-8')


@pytest.fixture
def run(tmp_path):
    folder=tmp_path/'outputs'/'domain-a'
    write(folder/'run.json',{'stages':{'extract':{'completed':'2026-10-16T01:00:00+00:00'},'normalize':{'completed':'2026-10-16T02:00:00+00:00'}},'corpus':{'failed':[]}})
    for paper,cid,label in [('P1','c1','Silicon'),('P2','c7','Solar cell')]:
        write(folder/'papers'/(paper+'.json'),{'key':paper,'concepts':[{'id':cid,'label':label}], 'relations':[],'causal':[],'measurements':[]})
    write(folder/'normalized/concepts.json',[{'id':'k1','label':'Silicon','alt_labels':[],'papers':['P1']},{'id':'k2','label':'Solar cell','alt_labels':[],'papers':['P2']}])
    write(folder/'normalized/relations.json',[{'s':'k1','p':'part_of','o':'k2'}])
    for name,value in [('causal',[]),('measurements',[]),('contradictions',[]),('causal_order',{}),('summary',{}),('corpus_stats',{})]:write(folder/'normalized'/(name+'.json'),value)
    return folder


def test_every_project_node_has_nonempty_skos_definition(graph):
    nodes={s for s in graph.subjects() if str(s).startswith(str(KW))}
    assert nodes
    assert all(any(str(v).strip() for v in graph.objects(node,SKOS.definition)) for node in nodes)


def test_structural_descriptions_do_not_claim_reviewed_behavior(graph):
    statuses=list(graph.objects(None,KW.definitionStatus))
    assert any(str(s).startswith('structural-only') for s in statuses)


def test_normalization_recipe_answers_binding_and_call_questions(graph):
    recipe=guide(graph,'normalize')
    assert len(recipe['algorithm'])==9
    assert 'ontology' in recipe['next_steps']
    assert {'ontology','enrich','interop','integrate','reports'}<=set(recipe['downstream_recheck'])
    papers=next(b for b in recipe['bindings'] if b['id']=='papers')
    assert papers['artifact']=='papers/*.json' and papers['argument']=='papers'
    assert papers['function']=='src/agents/normalization.py:NormalizationAgent.run'
    target=next(f for f in recipe['implementations'] if f['source']==papers['function'])
    assert any(a['name']=='papers' and a['type']=='list[dict]' and a['required'] for a in target['arguments'])
    assert target['returns']=='dict'
    stats=next(b for b in recipe['bindings'] if b['id']=='corpus-stats')
    assert stats['function']=='src/tools/reports.py:corpus_report'
    assert 'not a direct serialization of norm.stats' in stats['transformation']


def test_contracts_cover_every_stage_with_reviewed_operations_and_inputs(graph):
    for stage in ['preflight','store','ingest','parse','extract','normalize','ontology','enrich','interop','integrate','reports']:
        recipe=guide(graph,stage)
        assert recipe['task'] and recipe['recovery'] and recipe['limitation']
        assert recipe['input_contract'] and recipe['algorithm'] and recipe['bindings'] and recipe['checks']
        assert any(r['kind']=='worked example' and r['text'] for r in recipe['resources'])
        assert str(graph.value(KW['step/'+stage],KW.coverageStatus))=='reviewed field-level recipe'
    assert str(graph.value(KW['step/normalize'],KW.coverageStatus))=='reviewed field-level recipe'


def test_before_checks_accept_fixture_but_do_not_execute(graph,run):
    before={p:p.read_bytes() for p in run.rglob('*') if p.is_file()}
    result=assess(graph,run,run.parent,'normalize','before')
    assert result['decision']=='ready-for-runtime-conditions'
    assert all(p.read_bytes()==data for p,data in before.items())
    assert 'No commands were executed' in result['runtime_conditions']


def test_after_checks_require_scientific_review_even_with_valid_joins(graph,run):
    result=assess(graph,run,run.parent,'normalize','after')
    assert result['decision']=='review-required'
    assert not any(c['status']=='blocked' for c in result['checks'])
    assert result['artifact_fingerprints']


@pytest.mark.parametrize('broken',[{'id':'c1','label':{}},{'id':'c1','label':''},{'id':[],'label':'Silicon'}])
def test_malformed_concepts_block_normalization(graph,run,broken):
    write(run/'papers/P1.json',{'key':'P1','concepts':[broken],'relations':[],'causal':[],'measurements':[]})
    assert assess(graph,run,run.parent,'normalize','before')['decision']=='stop-and-recover'


def test_unresolved_paper_reference_blocks(graph,run):
    data=json.loads((run/'papers/P1.json').read_text())
    data['relations']=[{'s':'c1','p':'part_of','o':'c999'}];write(run/'papers/P1.json',data)
    assert assess(graph,run,run.parent,'normalize','before')['decision']=='stop-and-recover'


def test_wrong_canonical_endpoint_blocks_downstream(graph,run):
    write(run/'normalized/relations.json',[{'s':'k1','p':'part_of','o':'k999'}])
    result=assess(graph,run,run.parent,'normalize','after')
    assert result['decision']=='stop-and-recover'
    assert next(c for c in result['checks'] if c['id']=='canonical-references')['status']=='blocked'


def test_paper_coverage_loss_blocks_without_inventing_lineage(graph,run):
    write(run/'normalized/concepts.json',[{'id':'k1','label':'Silicon','alt_labels':[],'papers':['P1']}])
    result=assess(graph,run,run.parent,'normalize','after')
    assert next(c for c in result['checks'] if c['id']=='input-output-coverage')['status']=='blocked'
    assert 'not persisted' in result['limitations']


def test_no_saved_completion_is_not_success(graph,run):
    write(run/'run.json',{'stages':{'extract':{'completed':'2026-10-16T01:00:00+00:00'}}})
    assert assess(graph,run,run.parent,'normalize','after')['decision']=='stop-and-recover'


def test_direct_invocation_remains_distinct_from_orchestrator(graph):
    recipe=guide(graph,'normalize')
    assert 'Prefer the trusted CLI/wrapper' in recipe['input_contract']['initialization']
    assert graph.value(function_node('src/run.py','normalize'),KW.signature)
    assert graph.value(function_node('src/agents/normalization.py','NormalizationAgent.run'),KW.signature)


def test_agent_can_follow_graph_from_stage_to_argument_artifact_and_checker(graph):
    bindings=list(graph.objects(KW['step/normalize'],KW.hasDataBinding))
    papers=next(b for b in bindings if str(graph.value(b,KW.bindingExpression))=='papers')
    function=graph.value(papers,KW.implementedBy)
    assert str(graph.value(graph.value(papers,KW.bindsArtifact),KW.artifactPattern))=='papers/*.json'
    assert any(str(graph.value(a,KW.argumentName))=='papers' for a in graph.objects(function,KW.hasArgument))
    assert 'Transform a list of persisted paper records' in str(graph.value(function,SKOS.definition))
    for check in graph.objects(KW['step/normalize'],KW.hasCheck):
        assert graph.value(check,KW.evaluatedBy)==function_node('scripts/operational_contracts.py','assess')
        assert json.loads(str(graph.value(check,KW.evaluationArguments)))[-1] in ('before','after')


@pytest.fixture
def scientific_run(run):
    manifest=json.loads((run/'run.json').read_text())
    manifest['collection']={'name':'domain-a'}
    manifest['corpus']['selection']={'selected':[{'key':'P1'},{'key':'P2'}]}
    for i,stage in enumerate(('ontology','enrich','interop'),3):manifest['stages'][stage]={'completed':f'2026-10-16T0{i}:00:00+00:00'}
    write(run/'run.json',manifest)
    concepts=json.loads((run/'normalized/concepts.json').read_text())
    for c in concepts:c.update(type='material',definitions=[],alt_labels=[])
    write(run/'normalized/concepts.json',concepts)
    classes=[{**c,'iri':'https://example.org/'+c['id'],'parent':'http://purl.obolibrary.org/obo/BFO_0000040','parent_source':'type_default','excluded':False} for c in concepts]
    write(run/'ontology/classes.json',classes)
    enriched=[{**c,'definition':'A material entity.','definition_status':'model_generated','restrictions':[],'disjoint_with':[]} for c in classes]
    write(run/'ontology/enriched.json',enriched)
    write(run/'ontology/properties.json',{})
    write(run/'ontology/mappings.json',[])
    write(run/'ontology/validation.json',{'valid':True,'n_issues':0})
    for name in ('metrics','imported_definitions','facets'):write(run/'ontology'/(name+'.json'),{} if name!='imported_definitions' else [])
    for name in ('corpus_report.md','ontology_report.md'):(run/name).write_text('# Review\n',encoding='utf-8')
    from rdflib import URIRef, OWL
    graph=Graph();graph.add((URIRef('https://example.org/ontology'),RDF.type,OWL.Ontology))
    for base in ('ontology','domain_layer'):
        (run/(base+'.ttl')).write_text(graph.serialize(format='turtle'),encoding='utf-8')
        (run/(base+'.jsonld')).write_text(graph.serialize(format='json-ld'),encoding='utf-8')
    return run


@pytest.mark.parametrize('stage',['ontology','enrich','interop'])
def test_scientific_stages_check_actual_saved_joins(graph,scientific_run,stage):
    result=assess(graph,scientific_run,scientific_run.parent,stage,'after')
    assert result['decision']=='review-required',result['checks']
    assert not any(c['status']=='blocked' for c in result['checks'])


@pytest.mark.parametrize('stage,path',[('ontology','ontology/classes.json'),('enrich','ontology/enriched.json')])
def test_missing_canonical_identity_is_not_silent_loss(graph,scientific_run,stage,path):
    data=json.loads((scientific_run/path).read_text());write(scientific_run/path,data[:1])
    result=assess(graph,scientific_run,scientific_run.parent,stage,'after')
    assert any(c['status']=='blocked' and 'coverage' in c['id'] for c in result['checks'])


def test_excluded_classes_do_not_require_live_enrichment(graph,scientific_run):
    path=scientific_run/'ontology/enriched.json';data=json.loads(path.read_text());data[1]={'id':'k2','excluded':True}
    write(path,data)
    assert assess(graph,scientific_run,scientific_run.parent,'enrich','after')['decision']=='review-required'


@pytest.mark.parametrize('stage,path,field,value',[
    ('ontology','ontology/classes.json','parent','missing-parent'),
    ('enrich','ontology/enriched.json','restrictions',[{'p':'part_of','o':'missing-id'}]),
    ('enrich','ontology/enriched.json','disjoint_with',['missing-id'])])
def test_unresolved_ontology_endpoints_block(graph,scientific_run,stage,path,field,value):
    data=json.loads((scientific_run/path).read_text());data[0][field]=value;write(scientific_run/path,data)
    assert assess(graph,scientific_run,scientific_run.parent,stage,'after')['decision']=='stop-and-recover'


def test_false_saved_validation_is_not_success(graph,scientific_run):
    write(scientific_run/'ontology/validation.json',{'valid':False,'n_issues':2})
    result=assess(graph,scientific_run,scientific_run.parent,'interop','after')
    assert next(c for c in result['checks'] if c['id']=='structural-validation')['status']=='blocked'


def test_parseable_but_different_exports_are_rejected(graph,scientific_run):
    write(scientific_run/'ontology.jsonld',[{'@id':'https://example.org/unrelated','@type':'http://www.w3.org/2002/07/owl#Class'}])
    result=assess(graph,scientific_run,scientific_run.parent,'interop','after')
    assert next(c for c in result['checks'] if c['id']=='formal-roundtrip')['status']=='blocked'


def test_large_export_comparison_is_explicitly_deferred(graph,scientific_run):
    from rdflib import BNode, URIRef, Literal
    g=Graph()
    for i in range(45):g.add((BNode(),URIRef('https://example.org/value'),Literal(i)))
    (scientific_run/'ontology.ttl').write_text(g.serialize(format='turtle'),encoding='utf-8')
    (scientific_run/'ontology.jsonld').write_text(g.serialize(format='json-ld'),encoding='utf-8')
    result=assess(graph,scientific_run,scientific_run.parent,'interop','after')
    check=next(c for c in result['checks'] if c['id']=='formal-roundtrip')
    assert check['status']=='review' and 'equality is not established' in check['message']


def test_mapping_local_identifier_must_exist(graph,scientific_run):
    write(scientific_run/'ontology/mappings.json',[{'id':'lost','relation':'exact','iri':'https://example.org/external'}])
    result=assess(graph,scientific_run,scientific_run.parent,'interop','after')
    assert next(c for c in result['checks'] if c['id']=='mapping-local-ids')['status']=='blocked'


def test_one_concept_can_map_to_multiple_external_terms(graph,scientific_run):
    write(scientific_run/'ontology/mappings.json',[
        {'id':'k1','relation':'exact','iri':'https://example.org/external-a'},
        {'id':'k1','relation':'close','iri':'https://example.org/external-b'}])
    result=assess(graph,scientific_run,scientific_run.parent,'interop','after')
    assert result['decision']=='review-required',result['checks']


def test_extraction_coverage_checks_selection_not_only_completion(graph,scientific_run):
    result=assess(graph,scientific_run,scientific_run.parent,'extract','after')
    assert next(c for c in result['checks'] if c['id']=='selected-extracted-coverage')['status']=='pass'
    (scientific_run/'papers/P2.json').unlink()
    result=assess(graph,scientific_run,scientific_run.parent,'extract','after')
    assert next(c for c in result['checks'] if c['id']=='selected-extracted-coverage')['status']=='blocked'


@pytest.fixture
def wrapper_run(tmp_path):
    folder=tmp_path/'outputs'/'wrapper'
    write(folder/'dashboard.json',{'stages':{s:{'status':'completed'} for s in ('ingest','parse')}})
    write(folder/'ingestion.json',{'papers':[{'key':'P1','title':'Example','pdf':'selected.pdf','sources':[]}],'selection':{}})
    write(folder/'parsed/P1.json',{'key':'P1','pdf_hash':'fixture','chunks':['text'],'sections':[{'heading':'Results','text':'Some results'}],'figures':[]})
    return folder


def test_wrapper_parsing_coverage_and_sections_are_checked(graph,wrapper_run):
    assert assess(graph,wrapper_run,wrapper_run.parent,'parse','after')['decision']=='review-required'
    write(wrapper_run/'parsed/P2.json',{'key':'P2','pdf_hash':'fixture','chunks':[],'sections':[],'figures':[]})
    assert assess(graph,wrapper_run,wrapper_run.parent,'parse','after')['decision']=='stop-and-recover'


def test_wrapper_ingestion_requires_selected_pdf_metadata(graph,wrapper_run):
    assert assess(graph,wrapper_run,wrapper_run.parent,'ingest','after')['decision']=='review-required'
    write(wrapper_run/'ingestion.json',{'papers':[{'key':'P1'}],'selection':{}})
    assert assess(graph,wrapper_run,wrapper_run.parent,'ingest','after')['decision']=='stop-and-recover'


@pytest.mark.parametrize('stage',['preflight','store'])
def test_setup_never_invents_ready_from_domain_outputs(graph,scientific_run,stage):
    assert assess(graph,scientific_run,scientific_run.parent,stage,'after')['decision']=='await-runtime-checks'


def test_before_checks_do_not_require_later_outputs(graph,scientific_run):
    (scientific_run/'ontology/classes.json').unlink()
    result=assess(graph,scientific_run,scientific_run.parent,'ontology','before')
    assert not any(c['status']=='blocked' for c in result['checks']),result['checks']
    assert not any(c['id']=='canonical-class-coverage' for c in result['checks'])


def test_report_availability_and_skips_are_distinct_from_completion(graph,tmp_path):
    folder=tmp_path/'outputs'/'review';folder.mkdir(parents=True)
    for name in ('index.md','report.md','report.html','sweep_summary.csv'):(folder/name).write_text('Review\n',encoding='utf-8')
    result=assess(graph,folder,folder.parent,'reports','after')
    assert result['decision']=='review-required'
    assert next(c for c in result['checks'] if c['id']=='report-availability')['status']=='pass'
    (folder/'index.md').write_text('# Figures\nSkipped:\n- plot: missing data\n',encoding='utf-8')
    result=assess(graph,folder,folder.parent,'reports','after')
    assert next(c for c in result['checks'] if c['id']=='readable-package-skipped')['status']=='review'
    (folder/'report.html').unlink()
    assert assess(graph,folder,folder.parent,'reports','after')['decision']=='stop-and-recover'


@pytest.fixture
def integration_run(scientific_run):
    import shutil
    from rdflib import URIRef, OWL
    outputs=scientific_run.parent;other=outputs/'domain-b';shutil.copytree(scientific_run,other)
    enriched=json.loads((other/'ontology/enriched.json').read_text())
    for c in enriched:c['iri']=c['iri'].replace('example.org/','example.org/b-')
    write(other/'ontology/enriched.json',enriched)
    folder=outputs/'integration';folder.mkdir()
    write(folder/'integration.json',{'created':'2026-10-16T07:00:00+00:00','inputs':[{'run_id':'domain-a','domain':'a'},{'run_id':'domain-b','domain':'b'}],'ontology':{'name':'master','files':['master.ttl','master.jsonld','master_merged.ttl']}})
    for name in ('validation.json',):write(folder/name,{'valid':True,'n_issues':0})
    write(folder/'mappings.json',[{'a_iri':'https://example.org/k1','a_domain':'a','a_run':'domain-a','b_iri':'https://example.org/b-k1','b_domain':'b','b_run':'domain-b','relation':'exact'}])
    write(folder/'bridge_concepts.json',[{'label':'Silicon','domains':['a','b'],'n_domains':2,'members':[{'iri':'https://example.org/k1','domain':'a'},{'iri':'https://example.org/b-k1','domain':'b'}]}])
    write(folder/'candidates.json',[])
    (folder/'integration_report.md').write_text('# Integration\n',encoding='utf-8')
    g=Graph();g.add((URIRef('https://example.org/master'),RDF.type,OWL.Ontology))
    for name,fmt in [('master.ttl','turtle'),('master.jsonld','json-ld'),('master_merged.ttl','turtle')]:
        (folder/name).write_text(g.serialize(format=fmt),encoding='utf-8')
    return folder


def test_integration_resolves_mapping_and_bridge_provenance(graph,integration_run):
    result=assess(graph,integration_run,integration_run.parent,'integrate','after')
    assert result['decision']=='review-required',result['checks']
    path=integration_run/'mappings.json';data=json.loads(path.read_text());data[0]['b_run']='domain-a';write(path,data)
    result=assess(graph,integration_run,integration_run.parent,'integrate','after')
    assert next(c for c in result['checks'] if c['id']=='mapping-and-bridge-provenance')['status']=='blocked'


def test_integration_unknown_bridge_member_blocks(graph,integration_run):
    path=integration_run/'bridge_concepts.json';data=json.loads(path.read_text());data[0]['members'][0]['iri']='https://example.org/lost';write(path,data)
    result=assess(graph,integration_run,integration_run.parent,'integrate','after')
    assert result['decision']=='stop-and-recover'


def test_integration_rejects_path_escape_and_malformed_endpoints(graph,integration_run):
    path=integration_run/'mappings.json';data=json.loads(path.read_text());data[0]['a_iri']={};write(path,data)
    assert assess(graph,integration_run,integration_run.parent,'integrate','after')['decision']=='stop-and-recover'
    path=integration_run/'integration.json';data=json.loads(path.read_text());data['ontology']['name']='../outside';write(path,data)
    assert assess(graph,integration_run,integration_run.parent,'integrate','after')['decision']=='stop-and-recover'
