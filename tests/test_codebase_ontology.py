"""Verify ontology-guided planning and read-only provenance against guarded fixtures.

Author: Brent Thompson <brent.thompson@ucf.edu>
Exercises mode separation, incomplete products, stale snapshots and honest execution semantics.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import pytest
from rdflib import Graph, Literal, RDF

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from codebase_ontology import KW, freshness_errors
from ontology_agent import inspect_run, observation_graph, plan, read_artifact


@pytest.fixture
def graph():
    return Graph().parse(ROOT/'docs/ontology/knowledge-workflow.ttl')


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding='utf-8')


def run_fixture(tmp_path):
    folder=tmp_path/'outputs'/'test-run'
    write(folder/'run.json',{'stages':{'extract':{'completed':'2026-10-16T01:00:00+00:00'}},'corpus':{'failed':[]}})
    write(folder/'papers'/'a.json',{'concepts':[]})
    return folder


def extraction(result):
    return next(s for s in result['steps'] if s['step']=='extract')


def test_modes_plan_different_extraction_work(graph):
    cli=plan(graph,'normalize','cli',{'COLLECTION':'si-topcon','RUN_ID':'review-1'})
    assert [r['step'] for r in cli['steps']]==['store','preflight','extract','normalize']
    assert set(cli['steps'][2]['covers_steps'])=={'ingest','parse','extract'}
    assert all('RUN_ID' not in r['argv'] for r in cli['steps'])
    wrapper=plan(graph,'normalize','wrapper',{'PROJECT_ID':'project-1','DOMAIN_ID':'domain-1'})
    assert [r['step'] for r in wrapper['steps']]==['ingest','parse','extract','normalize']
    assert all(r['mode']=='wrapper' for r in wrapper['steps'])


@pytest.mark.parametrize('bindings',[{}, {'RUN_ID':'../other'}, {'TOKEN':'secret'}, {'RUN_ID':'RUN_ID'}])
def test_binding_failures(graph,bindings):
    with pytest.raises(ValueError):plan(graph,'normalize','cli',bindings)


def test_mode_cycle_rejected(graph):
    graph.add((KW['invocation/extract/cli'],KW.requiresStepForMode,KW['step/normalize']))
    with pytest.raises(ValueError,match='cycle'):plan(graph,'normalize','cli',{'COLLECTION':'si','RUN_ID':'x'})


def test_missing_mode_does_not_fall_back(graph):
    with pytest.raises(ValueError,match='unique'):plan(graph,'parse','cli',{})


def test_recorded_completion_requires_readable_products(graph,tmp_path):
    folder=run_fixture(tmp_path)
    assert extraction(inspect_run(graph,folder,folder.parent))['readiness']=='recorded-with-readable-products'
    (folder/'papers/a.json').unlink()
    assert extraction(inspect_run(graph,folder,folder.parent))['readiness']=='blocked'
    (folder/'papers/a.json').write_text('{',encoding='utf-8')
    assert extraction(inspect_run(graph,folder,folder.parent))['readiness']=='blocked'


def test_presence_not_completion_or_semantic_acceptance(graph,tmp_path):
    folder=run_fixture(tmp_path)
    write(folder/'run.json',{'stages':{}})
    row=extraction(inspect_run(graph,folder,folder.parent))
    assert row['readiness']=='not-recorded'
    assert 'Scientific' in row['review']


def test_partial_extraction_and_later_failure_block(graph,tmp_path):
    folder=run_fixture(tmp_path)
    write(folder/'run.json',{'stages':{'extract':{'completed':'2026-10-16T01:00:00+00:00'}},
                           'corpus':{'failed':['paper-2']},
                           'errors':[{'stage':'extract','time':'2026-10-16T02:00:00+00:00','error':'do not expose'}]})
    result=inspect_run(graph,folder,folder.parent)
    row=extraction(result)
    assert row['readiness']=='blocked'
    assert any('Partial extraction' in s for s in row['issues'])
    assert any('later failure' in s for s in row['issues'])
    assert 'do not expose' not in json.dumps(result)


def test_observations_are_records_not_executions(graph,tmp_path):
    folder=run_fixture(tmp_path)
    before={p:p.read_bytes() for p in folder.rglob('*') if p.is_file()}
    observed=observation_graph(inspect_run(graph,folder,folder.parent))
    assert list(observed.subjects(RDF.type,KW.RuntimeObservation))
    assert not list(observed.subjects(RDF.type,KW.ExecutionProcess))
    assert list(observed.objects(None,KW.observedDigest))
    assert all(p.read_bytes()==data for p,data in before.items())


def test_freshness_checks_contracts_and_source(tmp_path):
    path=tmp_path/'workflow.json';path.write_text('{}')
    graph=Graph();graph.add((KW.ontology,KW.documentationInputs,Literal(json.dumps({'workflow.json':hashlib.sha256(path.read_bytes()).hexdigest()}))))
    assert not freshness_errors(graph,tmp_path)
    path.write_text('{"changed":true}')
    assert freshness_errors(graph,tmp_path)


def test_remote_context_not_fetched(tmp_path):
    path=tmp_path/'x.jsonld'
    write(path,{'@context':'https://example.invalid/no-network','@id':'urn:test'})
    assert read_artifact(path,tmp_path)[0]['status']=='uninspected-remote-context'


def test_duplicate_domains_block_integration(graph,tmp_path):
    folder=tmp_path/'outputs'/'integration'
    write(folder/'integration.json',{'inputs':[{'domain':'same','run_id':'a'},{'domain':'same','run_id':'b'}],
                                    'ontology':{'files':['master.ttl']}})
    result=inspect_run(graph,folder,folder.parent)
    assert result['steps'][0]['readiness']=='blocked'
    assert any('distinct named domains' in issue for issue in result['steps'][0]['issues'])


def test_out_of_scope_run_rejected(graph,tmp_path):
    folder=run_fixture(tmp_path)
    with pytest.raises(ValueError):inspect_run(graph,tmp_path,folder.parent)


def test_source_rerun_blocks_old_integration(graph,tmp_path):
    outputs=tmp_path/'outputs';folder=outputs/'integration'
    inputs=[]
    for name in ['domain-a','domain-b']:
        source=outputs/name
        write(source/'run.json',{'stages':{'interop':{'completed':'2026-10-16T03:00:00+00:00'}}})
        write(source/'ontology/enriched.json',{'classes':[]})
        write(source/'ontology/validation.json',{'valid':True})
        (source/'ontology.ttl').write_text('<urn:test> <urn:relation> <urn:object> .')
        inputs.append({'run_id':name,'domain':name})
    write(folder/'integration.json',{'created':'2026-10-16T02:00:00+00:00','inputs':inputs,'ontology':{'files':['master.ttl']}})
    for pattern in ['mappings.json','bridge_concepts.json','candidates.json']:write(folder/pattern,[])
    write(folder/'validation.json',{'valid':True})
    (folder/'master.ttl').write_text('<urn:test> <urn:relation> <urn:object> .')
    result=inspect_run(graph,folder,outputs)
    assert all(s['status']=='source-rerun-after-integration' for s in result['sources'])
    assert result['steps'][0]['readiness']=='blocked'


def test_cli_intermediate_products_are_not_wrapper_requirements(graph,tmp_path):
    folder=run_fixture(tmp_path)
    result=inspect_run(graph,folder,folder.parent)
    assert result['mode']=='cli'
    assert all(s['readiness']=='inspect-combined-extraction' for s in result['steps'] if s['step'] in ('ingest','parse'))


def test_reports_found_in_figures_without_inventing_completion(graph,tmp_path):
    folder=run_fixture(tmp_path)
    for name in ['report.html','report.md','index.md']:
        (folder/'figures').mkdir(exist_ok=True)
        (folder/'figures'/name).write_text('Readable report')
    result=inspect_run(graph,folder,folder.parent)
    row=next(s for s in result['steps'] if s['step']=='reports')
    assert row['recorded_status']=='not-recorded'
    assert row['readiness']=='available-unrecorded'
    assert all(p['location']=='figures' for p in row['required_artifacts'])
    report=inspect_run(graph,folder/'figures',folder.parent)
    assert report['mode']=='report'
    assert [s['step'] for s in report['steps']]==['reports']


def test_missing_implementation_rejected_by_shape(graph):
    shacl=pytest.importorskip('pyshacl')
    graph.remove((KW['step/normalize'],KW.hasImplementation,None))
    conforms,_,_=shacl.validate(graph,shacl_graph=Graph().parse(ROOT/'docs/ontology/shapes.ttl'))
    assert not conforms


def test_validator_detects_disconnected_units(graph):
    spec=importlib.util.spec_from_file_location('validate_codebase',ROOT/'scripts/validate-codebase-ontology.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    graph.remove((KW.CodebaseDocumentation,KW.hasCodeUnit,None))
    errors=module.operational_errors(graph,ROOT,json.loads((ROOT/'docs/codebase/inventory.json').read_text()))
    assert any('Disconnected code units' in e for e in errors)
