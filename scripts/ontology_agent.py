"""Plan trusted ontology invocations and observe saved runs without executing pipeline work.

Author: Brent Thompson <brent.thompson@ucf.edu>
Returns structured argument vectors, prerequisite checks and timestamped artifact observations.
It never imports pipeline settings, reads credentials, launches commands or alters run outputs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote
from rdflib import Graph, Literal, RDF
from codebase_ontology import KW, PROV, freshness_errors

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r'(?<![A-Z0-9_])[A-Z][A-Z0-9_]+(?![A-Z0-9_])')


def invocation(graph, step, mode):
    """Require one unambiguous command in the selected execution mode."""
    values = [i for i in graph.objects(step, KW.hasInvocation)
              if str(graph.value(i, KW.executionMode)) == mode]
    if len(values) != 1:raise ValueError(f'No unique {mode} invocation for {step}')
    return values[0]


def plan(graph, target, mode, bindings):
    """Topologically bind a mode-specific plan; leave environmental checks explicit."""
    if mode not in ('cli', 'wrapper'):raise ValueError('Mode must be cli or wrapper')
    if not isinstance(bindings, dict):raise ValueError('Bindings must be a JSON object')
    known = {str(p).rsplit('/', 1)[-1] for p in graph.subjects(RDF.type, KW.ParameterSpecification)}
    if set(bindings)-known:raise ValueError('Unknown binding names: '+', '.join(sorted(set(bindings)-known)))
    for name, value in bindings.items():
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,119}', value) or '..' in value:
            raise ValueError('Binding must be a simple authorized name or identifier: '+name)
        if value == name:raise ValueError('Unresolved binding: '+name)
    rows, done = [], set()

    def visit(step, stack):
        if step in stack:raise ValueError('Mode-specific dependency cycle')
        if step in done:return
        inv = invocation(graph, step, mode)
        for parent in sorted(graph.objects(inv, KW.requiresStepForMode), key=str):visit(parent, stack|{step})
        needed = {str(p).rsplit('/', 1)[-1] for p in graph.objects(inv, KW.requiresBinding)}
        if needed-set(bindings):raise ValueError('Missing bindings: '+', '.join(sorted(needed-set(bindings))))
        argv = json.loads(str(graph.value(inv, KW.commandArguments)))
        if not isinstance(argv, list) or not argv or not all(isinstance(v,str) and v for v in argv):
            raise ValueError('Invalid command argument vector')
        def substitute(match):
            token = match.group()
            return bindings[token] if token in needed else token
        bound = [TOKEN.sub(substitute, arg) for arg in argv]
        if any(token in needed for arg in bound for token in TOKEN.findall(arg)):
            raise ValueError('Command still contains unresolved bindings')
        rows.append({'step':str(step).rsplit('/',1)[-1], 'mode':mode, 'argv':bound,
                     'covers_steps':[str(s).rsplit('/',1)[-1] for s in graph.objects(inv,KW.coversStep)],
                     'conditions':[str(graph.value(c,KW.conditionRule)) for c in graph.objects(inv,KW.requiresCondition)],
                     'required_artifacts':[str(graph.value(a,KW.artifactPattern)) for a in graph.objects(step,KW.requiredOutput)],
                     'artifact_locations':json.loads(str(graph.value(step,KW.artifactLocations) or '["."]')),
                     'completion_rule':str(graph.value(step,KW.completionRule)),
                     'recovery_rule':str(graph.value(step,KW.recoveryRule)),
                     'side_effects':str(graph.value(step,KW.sideEffects))})
        done.add(step)
    visit(KW['step/'+target], set())
    return {'target':target, 'mode':mode, 'execution':'plan only; no commands launched',
            'instruction':'For each step, first establish conditions and inspect saved completion. Execute only missing work in authorized scope. A store build is conditional on missing readiness; never rebuild an active valid store. Review outputs before advancing.',
            'steps':rows}


def read_artifact(path, root):
    """Read a bounded, stable artifact and return only public structural metadata."""
    path, root = Path(path).resolve(), Path(root).resolve()
    if not path.is_relative_to(root):raise ValueError('Artifact escapes selected run directory')
    info = {'path':path.relative_to(root).as_posix()}
    try:
        before = path.stat()
        if before.st_size > 64*1024*1024:return {**info,'status':'uninspected-size-limit'}, None
        content = path.read_bytes()
        after = path.stat()
        if (before.st_mtime_ns,before.st_size) != (after.st_mtime_ns,after.st_size):
            return {**info,'status':'changed-during-read'}, None
        info.update(sha256=hashlib.sha256(content).hexdigest(), bytes=len(content))
        if not content.strip():return {**info,'status':'empty'}, None
        data = json.loads(content) if path.suffix == '.json' else None
        if path.suffix in ('.ttl','.jsonld'):
            if path.suffix=='.jsonld':
                data=json.loads(content)
                def remote_context(value):
                    if isinstance(value,list):return any(remote_context(v) for v in value)
                    if not isinstance(value,dict):return False
                    context=value.get('@context')
                    if isinstance(context,str) or (isinstance(context,list) and any(isinstance(v,str) for v in context)):
                        return True
                    return '@import' in value or any(remote_context(v) for v in value.values())
                if remote_context(data):return {**info,'status':'uninspected-remote-context'}, None
            parsed = Graph().parse(data=content, format='turtle' if path.suffix=='.ttl' else 'json-ld')
            info['triples'] = len(parsed)
        elif isinstance(data,(dict,list)):info['records_or_fields'] = len(data)
        elif path.suffix == '.json':return {**info,'status':'invalid-json-record'}, None
        return {**info,'status':'readable'}, data
    except Exception as exc:
        # Never echo content, provider URLs, exception messages or secret-bearing manifest fields.
        return {**info,'status':'unreadable','error_type':type(exc).__name__}, None


def inspect_run(graph, folder, outputs):
    """Separate saved completion, readable products and review needs in a read-only snapshot."""
    folder, outputs = Path(folder).resolve(), Path(outputs).resolve()
    if not folder.is_relative_to(outputs) or folder == outputs or not folder.is_dir():
        raise ValueError('Select an existing run directory inside outputs')
    artifacts, data = {}, {}
    def read(path):
        relative = path.relative_to(folder).as_posix()
        if relative not in artifacts:
            artifacts[relative], data[relative] = read_artifact(path,folder)
        return data[relative]
    for name in ['run.json','dashboard.json','integration.json']:
        if (folder/name).exists():read(folder/name)
    manifest = data.get('run.json') if data.get('run.json') is not None else {}
    dashboard = data.get('dashboard.json') if data.get('dashboard.json') is not None else {}
    integration = data.get('integration.json') if data.get('integration.json') is not None else {}
    if not all(isinstance(v,dict) for v in [manifest,dashboard,integration]):raise ValueError('Invalid manifest object')
    result = {'run':folder.relative_to(outputs).as_posix(), 'observed_at':datetime.now(timezone.utc).isoformat(),
              'semantics':'Recorded completion and artifact readability only; no live-process or scientific acceptance inference.',
              'steps':[], 'sources':[]}
    is_integration = (folder/'integration.json').exists()
    is_report=not any((folder/n).exists() for n in ['run.json','dashboard.json','integration.json']) and any((folder/n).exists() for n in ['report.md','report.html','index.md'])
    result['mode']='report' if is_report else ('integration' if is_integration else ('wrapper' if (folder/'dashboard.json').exists() else 'cli'))
    for step in sorted(graph.subjects(RDF.type,KW.StepSpecification),key=str):
        name = str(step).rsplit('/',1)[-1]
        if is_report and name!='reports':continue
        if name in ('store','preflight') or (is_integration and name!='integrate') or (not is_integration and name=='integrate'):continue
        if name in ('ingest','parse') and result['mode']=='cli':
            result['steps'].append({'step':name,'recorded_status':'not-separately-recorded',
                                    'readiness':'inspect-combined-extraction','required_artifacts':[], 'issues':[],
                                    'review':'CLI extract covers this operation; wrapper-only intermediate products are not required for this mode.'})
            continue
        state = dashboard.get('stages',{}).get(name,{})
        cli = manifest.get('stages',{}).get(name,{})
        if not isinstance(state,dict) or not isinstance(cli,dict):raise ValueError('Invalid stage record')
        recorded = state.get('status') or ('completed' if cli.get('completed') else 'not-recorded')
        if is_integration:recorded='integration-manifest-present'
        issues, patterns = [], []
        locations=json.loads(str(graph.value(step,KW.artifactLocations) or '["."]'))
        base=folder
        for location in locations:
            candidate=(folder/location).resolve()
            if not candidate.is_relative_to(folder):raise ValueError('Artifact location escapes run')
            if any(candidate.glob('report.*')) and name=='reports':base=candidate;break
        if not state and cli.get('completed'):
            def stamp(value):
                return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
            try:
                completed=stamp(cli['completed'])
                for failure in manifest.get('errors',[]):
                    if failure.get('stage')==name and stamp(failure.get('time'))>=completed:
                        issues.append('A later failure supersedes recorded completion')
                for parent in graph.objects(step,KW.requiresCompletionOf):
                    prior=manifest.get('stages',{}).get(str(parent).rsplit('/',1)[-1],{})
                    if prior.get('completed') and stamp(prior['completed'])>completed:
                        issues.append('An upstream stage completed later; downstream freshness needs review')
            except (ValueError,TypeError,AttributeError):issues.append('Invalid completion/failure timestamp')
        for artifact in graph.objects(step,KW.requiredOutput):
            pattern = str(graph.value(artifact,KW.artifactPattern))
            if Path(pattern).is_absolute() or '..' in Path(pattern).parts:raise ValueError('Unsafe artifact pattern')
            matches = sorted(p for p in base.glob(pattern) if p.is_file())
            patterns.append({'pattern':pattern,'location':base.relative_to(folder).as_posix(),'files':len(matches)})
            if not matches:issues.append('Missing '+pattern)
            for path in matches:
                read(path)
                if artifacts[path.relative_to(folder).as_posix()]['status']!='readable':issues.append('Unusable '+path.relative_to(folder).as_posix())
        if name=='extract':
            corpus = manifest.get('corpus',{})
            failed = corpus.get('failed',[]) if isinstance(corpus,dict) else []
            if failed or cli.get('failed'):issues.append('Partial extraction: recorded failed papers require explicit review')
        if name=='interop':
            validation = data.get('ontology/validation.json')
            if isinstance(validation,dict) and validation.get('valid') is False:issues.append('Saved structural validation failed')
        if name=='integrate':
            validation = data.get('validation.json')
            if isinstance(validation,dict) and validation.get('valid') is False:issues.append('Saved integration validation failed')
            inputs = integration.get('inputs',[])
            if not isinstance(inputs,list):raise ValueError('Invalid integration input list')
            domains = [s.get('domain') for s in inputs if isinstance(s,dict)]
            if len(domains)<2 or len(set(domains))!=len(domains) or not all(domains):issues.append('Integration requires distinct named domains')
            for source in inputs:
                if not isinstance(source,dict):continue
                run_id = source.get('run_id','')
                if not isinstance(run_id,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',run_id) or '..' in run_id:
                    issues.append('Invalid integration source identifier');continue
                source_folder = outputs/run_id
                source_info = {'run':run_id,'domain':source.get('domain'),'status':'missing'}
                if source_folder.is_dir() and source_folder.resolve().is_relative_to(outputs):
                    smeta, saved = read_artifact(source_folder/'run.json',source_folder)
                    source_info.update(status='unconfirmed',artifacts=[smeta])
                    completed_source=saved.get('stages',{}).get('interop',{}) if isinstance(saved,dict) else {}
                    if completed_source.get('completed'):
                        source_info['status']='interop-recorded'
                    for product in ['ontology.ttl','ontology/enriched.json','ontology/validation.json']:
                        meta, content=read_artifact(source_folder/product,source_folder)
                        source_info['artifacts'].append(meta)
                        if meta['status']!='readable':source_info['status']='unusable-products'
                        if product=='ontology/validation.json' and isinstance(content,dict) and content.get('valid') is False:
                            source_info['status']='source-validation-failed'
                    if completed_source.get('valid') is False:source_info['status']='source-validation-failed'
                    corpus=saved.get('corpus',{}) if isinstance(saved,dict) else {}
                    if corpus.get('failed'):source_info['status']='partial-source-extraction'
                    if completed_source.get('completed') and integration.get('created'):
                        try:
                            if datetime.fromisoformat(completed_source['completed'])>datetime.fromisoformat(integration['created']):
                                source_info['status']='source-rerun-after-integration'
                        except (ValueError,TypeError):source_info['status']='unconfirmed-timestamp'
                result['sources'].append(source_info)
                if source_info['status']!='interop-recorded':issues.append('Unconfirmed integration source '+run_id)
            files = integration.get('ontology',{}).get('files',[])
            if not files:issues.append('No exported ontology files recorded')
            for filename in files:
                if not isinstance(filename,str) or Path(filename).name!=filename:raise ValueError('Unsafe ontology filename')
                read(folder/filename)
                if artifacts[filename]['status']!='readable':issues.append('Unusable '+filename)
        complete = recorded in ('completed','integration-manifest-present')
        readiness='blocked' if issues else ('recorded-with-readable-products' if complete else 'not-recorded')
        if name=='reports' and not complete:
            readiness='available-unrecorded' if not issues else 'not-recorded'
        if name in ('ingest','parse') and not state:issues.append('CLI records extraction as a combined operation; no separate stage record')
        if any(a['status']!='readable' for p,a in artifacts.items() if p in ('run.json','dashboard.json','integration.json')):
            issues.append('Unusable manifest prevents a reliable observation')
        result['steps'].append({'step':name,'recorded_status':recorded,
                                'readiness':readiness,
                                'required_artifacts':patterns,'issues':issues,
                                'review':'Scientific evidence, warnings and freshness of downstream results still require review.'})
    # Recheck every read file after collection: a live run can mutate earlier files during inspection.
    for name, info in artifacts.items():
        if info.get('sha256'):
            try:
                if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=info['sha256']:info['status']='changed-during-snapshot'
            except OSError:info['status']='changed-during-snapshot'
    if any(a['status'].startswith('changed-') for a in artifacts.values()):
        for row in result['steps']:
            row['readiness']='blocked';row['issues'].append('Run changed during snapshot; inspect again after writes settle')
    for source in result['sources']:
        for artifact in source.get('artifacts',[]):
            if artifact.get('sha256'):
                path=outputs/source['run']/artifact['path']
                try:stable=hashlib.sha256(path.read_bytes()).hexdigest()==artifact['sha256']
                except OSError:stable=False
                if not stable:
                    artifact['status']='changed-during-snapshot';source['status']='changed-during-snapshot'
                    for row in result['steps']:
                        row['readiness']='blocked';row['issues'].append('Integration source changed during snapshot')
    result['artifacts']=list(artifacts.values())
    return result


def observation_graph(result):
    """Represent observations as information records, without inventing execution processes."""
    graph=Graph();graph.bind('kw',KW);graph.bind('prov',PROV)
    identity=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    documentation=result.get('documentation')
    specification=KW['documentation-artifact/'+documentation['sha256']] if documentation else None
    if specification:
        graph.add((specification,RDF.type,KW.ArtifactRecord));graph.add((specification,RDF.type,PROV.Entity))
        graph.add((specification,KW.sourcePath,Literal(documentation['path'])))
        graph.add((specification,KW.observedDigest,Literal(documentation['sha256'])))
    for row in result['steps']:
        node=KW['observation/'+identity+'/'+row['step']]
        graph.add((node,RDF.type,KW.RuntimeObservation));graph.add((node,RDF.type,PROV.Entity))
        graph.add((node,KW.observesStep,KW['step/'+row['step']]))
        if specification:graph.add((node,PROV.wasDerivedFrom,specification))
        for prop,value in [('recordedStatus',row['recorded_status']),('readiness',row['readiness']),
                           ('observedAt',result['observed_at']),('observationJson',json.dumps(row,sort_keys=True))]:
            graph.add((node,KW[prop],Literal(value)))
        for artifact in result['artifacts']:
            record=KW['observation-artifact/'+identity+'/'+quote(artifact['path'],safe='/')]
            graph.add((record,RDF.type,KW.ArtifactRecord));graph.add((record,RDF.type,PROV.Entity))
            graph.add((record,KW.sourcePath,Literal(result['run']+'/'+artifact['path'])))
            if artifact.get('sha256'):graph.add((record,KW.observedDigest,Literal(artifact['sha256'])))
            graph.add((record,KW.recordedStatus,Literal(artifact['status'])))
            graph.add((node,KW.observesArtifact,record));graph.add((node,PROV.wasDerivedFrom,record))
        for source in result['sources']:
            for artifact in source.get('artifacts',[]):
                record=KW['observation-artifact/'+identity+'/'+quote(source['run']+'/'+artifact['path'],safe='/')]
                graph.add((record,RDF.type,KW.ArtifactRecord));graph.add((record,RDF.type,PROV.Entity))
                graph.add((record,KW.sourcePath,Literal(source['run']+'/'+artifact['path'])))
                if artifact.get('sha256'):graph.add((record,KW.observedDigest,Literal(artifact['sha256'])))
                graph.add((node,KW.observesArtifact,record));graph.add((node,PROV.wasDerivedFrom,record))
    return graph


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph',type=Path,default=ROOT/'docs/ontology/knowledge-workflow.ttl')
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('plan');p.add_argument('--mode',choices=['cli','wrapper'],required=True)
    p.add_argument('--target',required=True);p.add_argument('--bindings',type=Path,required=True)
    p=commands.add_parser('inspect');p.add_argument('--run',required=True)
    p.add_argument('--rdf',action='store_true',help='Print Turtle observation instead of JSON')
    p=commands.add_parser('guide');p.add_argument('--step',required=True)
    p=commands.add_parser('assess');p.add_argument('--step',required=True);p.add_argument('--run',required=True)
    p.add_argument('--phase',choices=['before','after'],default='after')
    args=parser.parse_args()
    try:
        graph=Graph().parse(args.graph)
        stale=freshness_errors(graph,ROOT)
        spec=importlib.util.spec_from_file_location('document_codebase',ROOT/'scripts/document-codebase.py')
        source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
        documented={str(graph.value(n,KW.sourcePath)) for n in graph.objects(KW.CodebaseDocumentation,KW.hasCodeUnit)}
        if documented!=set(source.code_files()):stale.append('Code inventory changed; regenerate documentation')
        if stale:raise ValueError('; '.join(stale))
        if args.command=='guide':
            from operational_contracts import guide
            result=guide(graph,args.step)
        elif args.command=='assess':
            from operational_contracts import assess
            result=assess(graph,ROOT/'outputs'/args.run,ROOT/'outputs',args.step,args.phase)
        elif args.command=='plan':
            result=plan(graph,args.target,args.mode,json.loads(args.bindings.read_text(encoding='utf-8')))
        else:
            result=inspect_run(graph,ROOT/'outputs'/args.run,ROOT/'outputs')
            result['documentation']={'path':args.graph.relative_to(ROOT).as_posix(),
                                     'sha256':hashlib.sha256(args.graph.read_bytes()).hexdigest()}
            if args.rdf:
                print(observation_graph(result).serialize(format='turtle'));return
        print(json.dumps(result,indent=2))
    except (ValueError,OSError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(2)


if __name__=='__main__':main()
