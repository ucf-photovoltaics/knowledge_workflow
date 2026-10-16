"""Build source-backed agent contracts, definitions and read-only operational checks.

Author: Brent Thompson <brent.thompson@ucf.edu>
Adds documentation and reviewer navigation without importing or executing pipeline agents.
Checks describe this documentation layer's review policy, not new pipeline enforcement.
"""
import ast
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from rdflib import Literal, RDF, RDFS, OWL, XSD
from codebase_ontology import KW, CCO, PROV, SKOS, function_node


def artifact_node(pattern):
    """Return the same canonical artifact IRI used by the inventory generator."""
    return KW['artifact-pattern/'+hashlib.sha256(pattern.encode()).hexdigest()[:20]]


def build_contracts(graph, root, inventory):
    """Connect reviewed operational contracts and statically observed callable arguments."""
    root=Path(root)
    operations=json.loads((root/'docs/codebase/operations.json').read_text(encoding='utf-8'))
    classes={
        'DataBindingSpecification':'A documented binding between a callable value and an artifact field, including any adaptation performed by its orchestrator.',
        'ArgumentSpecification':'A source-observed formal argument, annotation and default; it is not a validated runtime value.',
        'CheckSpecification':'A bounded, read-only predicate or review instruction used by the documentation agent helper.',
        'RecoverySpecification':'Failure-specific recovery guidance and downstream invalidation scope; it does not perform the recovery.',
        'OperationSpecification':'A source-reviewed substep within a stage plan; it is not an execution occurrence.'}
    for name,definition in classes.items():
        node=KW[name];graph.add((node,RDF.type,OWL.Class))
        graph.add((node,RDFS.subClassOf,CCO.ont00000974 if name=='OperationSpecification' else CCO.ont00000965))
        graph.add((node,RDFS.subClassOf,PROV.Entity));graph.add((node,RDFS.label,Literal(name)))
        graph.add((node,SKOS.definition,Literal(definition,lang='en')))
    objects={
        'hasDataBinding':('StepSpecification','DataBindingSpecification'),
        'bindsArtifact':('DataBindingSpecification','ArtifactSpecification'),
        'implementedBy':('DataBindingSpecification','CodeUnitSpecification'),
        'hasArgument':('CodeUnitSpecification','ArgumentSpecification'),
        'hasCheck':('StepSpecification','CheckSpecification'),
        'evaluatedBy':('CheckSpecification','CodeUnitSpecification'),
        'checksArtifact':('CheckSpecification','ArtifactSpecification'),
        'hasRecovery':('StepSpecification','RecoverySpecification'),
        'invalidatesStep':('StepSpecification','StepSpecification'),
        'canAdvanceTo':('StepSpecification','StepSpecification'),
        'hasOperation':('StepSpecification','OperationSpecification'),
        'operationImplementation':('OperationSpecification','CodeUnitSpecification'),
        'nextOperation':('OperationSpecification','OperationSpecification')}
    for name,(source,target) in objects.items():
        graph.add((KW[name],RDF.type,OWL.ObjectProperty));graph.add((KW[name],RDFS.label,Literal(name)))
        graph.add((KW[name],RDFS.domain,KW[source]));graph.add((KW[name],RDFS.range,KW[target]))
        graph.add((KW[name],SKOS.definition,Literal(f'Documentation relation from {source} to {target}. It describes a binding, plan or dependency rather than asserting execution.',lang='en')))
    text=['definitionStatus','argumentName','argumentKind','typeExpression','defaultExpression','returnTypeExpression',
          'bindingDirection','bindingSelector','bindingExpression','valueTransformation','checkRule','contractJson','recoveryAction','coverageStatus','evaluationArguments']
    for name in text:
        graph.add((KW[name],RDF.type,OWL.DatatypeProperty));graph.add((KW[name],RDFS.label,Literal(name)))
        graph.add((KW[name],RDFS.range,XSD.string))
    graph.add((KW.argumentRequired,RDF.type,OWL.DatatypeProperty));graph.add((KW.argumentRequired,RDFS.range,XSD.boolean))
    graph.add((SKOS.definition,RDF.type,OWL.AnnotationProperty))
    functions={(r['path'],f['name']):f for r in inventory for f in r['functions']}
    for identity,definition in operations.get('callable_definitions',{}).items():
        path,name=identity.split(':',1)
        if (path,name) not in functions:raise ValueError('Unknown documented callable '+identity)
        graph.add((function_node(path,name),SKOS.definition,Literal(definition,lang='en')))
        graph.add((function_node(path,name),KW.definitionStatus,Literal('source-reviewed contract')))
    def entity(node,kind,label,definition):
        graph.add((node,RDF.type,KW[kind]));graph.add((node,RDF.type,OWL.NamedIndividual))
        graph.add((node,RDFS.label,Literal(label)));graph.add((node,SKOS.definition,Literal(definition,lang='en')))
        return node
    for row in inventory:
        if not row['path'].endswith('.py'):continue
        tree=ast.parse((root/row['path']).read_text(encoding='utf-8-sig'))
        def visit(body,scope=''):
            for node in body:
                if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):continue
                qualified=scope+node.name
                if not isinstance(node,ast.ClassDef):
                    function=function_node(row['path'],qualified)
                    graph.add((function,KW.returnTypeExpression,Literal(ast.unparse(node.returns) if node.returns else 'unannotated; inspect implementation')))
                    positional=node.args.posonlyargs+node.args.args
                    defaults=[None]*(len(positional)-len(node.args.defaults))+node.args.defaults
                    arguments=[(a,d,'positional-only' if i<len(node.args.posonlyargs) else 'positional-or-keyword') for i,(a,d) in enumerate(zip(positional,defaults))]
                    arguments += [(a,d,'keyword-only') for a,d in zip(node.args.kwonlyargs,node.args.kw_defaults)]
                    arguments += [(a,None,kind) for a,kind in [(node.args.vararg,'variadic positional'),(node.args.kwarg,'variadic keyword')] if a]
                    for arg,default,kind in arguments:
                        implicit=arg.arg in ('self','cls')
                        argument=entity(KW['argument/'+quote(row['path']+':'+qualified+':'+arg.arg,safe='/.:')],
                            'ArgumentSpecification',arg.arg,
                            f'Formal {kind} argument {arg.arg} of {qualified} in {row["path"]}. '+('Supplied by the bound instance/class.' if implicit else 'Bind a value conforming to its source annotation and reviewed boundary contract.'))
                        graph.add((function,KW.hasArgument,argument));graph.add((argument,KW.argumentName,Literal(arg.arg)))
                        graph.add((argument,KW.argumentKind,Literal('implicit receiver' if implicit else kind)))
                        graph.add((argument,KW.typeExpression,Literal(ast.unparse(arg.annotation) if arg.annotation else 'unannotated')))
                        graph.add((argument,KW.argumentRequired,Literal(not implicit and default is None and not kind.startswith('variadic'))))
                        if default is not None:graph.add((argument,KW.defaultExpression,Literal(ast.unparse(default))))
                visit(node.body,qualified+'.')
        visit(tree.body)
    for stage,contract in operations['stages'].items():
        step=KW['step/'+stage]
        graph.add((step,KW.contractJson,Literal(json.dumps(contract,sort_keys=True))))
        graph.add((step,KW.coverageStatus,Literal('reviewed field-level recipe' if contract.get('input_contract') and contract['algorithm'] else 'reviewed stage boundary; callable internals may remain structural-only')))
        recovery=entity(KW['recovery/'+stage],'RecoverySpecification',stage+' recovery',contract['recovery'])
        graph.add((step,KW.hasRecovery,recovery));graph.add((recovery,KW.recoveryAction,Literal(contract['recovery'])))
        graph.add((step,SKOS.scopeNote,Literal(contract['limitation'],lang='en')))
        for binding in contract['bindings']:
            path,name=binding['function'].split(':',1)
            if (path,name) not in functions:raise ValueError('Unknown binding implementation '+binding['function'])
            node=entity(KW['binding/'+stage+'/'+binding['id']],'DataBindingSpecification',binding['id'].replace('-',' '),binding['transformation'])
            artifact=artifact_node(binding['artifact'])
            entity(artifact,'ArtifactSpecification',binding['artifact'],'Expected content at '+binding['artifact']+' in the selected run scope; not an assertion that it exists.')
            graph.add((artifact,KW.artifactPattern,Literal(binding['artifact'])))
            graph.add((step,KW.expectsInput if binding['direction']=='input' else KW.expectsOutput,artifact))
            graph.add((step,KW.hasDataBinding,node));graph.add((node,KW.bindsArtifact,artifact));graph.add((node,KW.implementedBy,function_node(path,name)))
            for prop,key in [('bindingDirection','direction'),('bindingSelector','selector'),('bindingExpression','argument'),('valueTransformation','transformation')]:graph.add((node,KW[prop],Literal(binding[key])))
        for check in contract['checks']:
            meaning={'paper_contract':'Validate saved paper keys and concept IDs, nonempty string labels and resolvable within-paper claim endpoints before binding papers to normalization.',
                     'canonical_references':'Require saved relation, causal and measurement endpoints to reference saved canonical concept IDs.',
                     'paper_coverage':'Compare supporting papers in canonical concepts with input papers containing concepts. This check does not recover original-to-canonical ID lineage.',
                     'shape':'Check the saved artifact container and required field types defined in checkRule. This bounded boundary schema does not validate scientific meaning.',
                     'identity_coverage':'Compare source and returned identifiers, retaining excluded records rather than silently losing concepts.',
                     'references':'Check local endpoints against saved identifiers, allowing public IRIs only where the documented boundary permits them.',
                     'corpus_coverage':'Compare selected paper keys with saved per-paper products; availability is distinct from scientific acceptance.',
                     'saved_validation':'Require a saved successful structural validation result; this does not establish scientific correctness.',
                     'rdf_pair':'Parse local export snapshots and compare RDF graphs without resolving imports or remote JSON-LD contexts.',
                     'runtime_condition':'Establish the documented live readiness condition outside this read-only saved-result assessment.',
                     'report_package':'Locate the report package, check required readable products and identify recorded skipped figures.',
                     'integration_links':'Resolve mapping and bridge endpoints against explicitly recorded source-domain classes and source run identities.'}
            node=entity(KW['check/'+stage+'/'+check['id']],'CheckSpecification',check['id'].replace('-',' '),check.get('instruction') or meaning[check['kind']])
            graph.add((step,KW.hasCheck,node));graph.add((node,KW.checkRule,Literal(json.dumps(check,sort_keys=True))))
            graph.add((node,KW.evaluatedBy,function_node('scripts/operational_contracts.py','assess')))
            phases=check.get('phases',['before'] if check['kind']=='paper_contract' else ['after'])
            if not phases or any(p not in ('before','after') for p in phases):raise ValueError('Invalid check phase '+check['id'])
            for phase in phases:
                graph.add((node,KW.evaluationArguments,Literal(json.dumps(['python','scripts/ontology_agent.py','assess','--run','RUN_ID','--step',stage,'--phase',phase]))))
            if check.get('pattern'):graph.add((node,KW.checksArtifact,artifact_node(check['pattern'])))
        previous=None
        for operation in contract['algorithm']:
            path,name=operation['function'].split(':',1)
            if (path,name) not in functions:raise ValueError('Unknown algorithm implementation '+operation['function'])
            node=entity(KW['operation/'+stage+'/'+operation['id']],'OperationSpecification',operation['label'],operation['definition'])
            graph.add((step,KW.hasOperation,node));graph.add((node,KW.operationImplementation,function_node(path,name)))
            graph.add((node,KW.order,Literal(operation['order'],datatype=XSD.integer)))
            graph.add((function_node(path,name),SKOS.definition,Literal(operation['definition'],lang='en')))
            graph.add((function_node(path,name),KW.definitionStatus,Literal('source-reviewed contract')))
            if previous:graph.add((previous,KW.nextOperation,node))
            previous=node
    # A rerun's consequences are documentation relationships, never automatic deletions/restarts.
    for step in graph.subjects(RDF.type,KW.StepSpecification):
        pending=[s for s in graph.subjects(KW.requiresCompletionOf,step)];seen=set()
        for child in pending:graph.add((step,KW.canAdvanceTo,child))
        while pending:
            child=pending.pop()
            if child in seen:continue
            seen.add(child);graph.add((step,KW.invalidatesStep,child));pending.extend(graph.subjects(KW.requiresCompletionOf,child))
    worked_paths=set()
    for stage,contract in operations['stages'].items():
        worked_path=contract.get('worked_example','docs/codebase/normalization-walkthrough.md' if stage=='normalize' else None)
        if not worked_path:continue
        path=(root/worked_path).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():raise ValueError('Invalid worked example '+worked_path)
        worked_paths.add(worked_path)
        resource=entity(KW['resource/'+worked_path],'ResourceSpecification',contract['task']+' worked example',
                        'Source-reviewed task instructions for discovering, binding, checking and reviewing '+stage+' without fabricating execution or provenance.')
        for prop,value in [('sourcePath',worked_path),('sourceDigest',hashlib.sha256(path.read_bytes()).hexdigest()),('resourceKind','worked example'),('resourceText',path.read_text(encoding='utf-8'))]:graph.add((resource,KW[prop],Literal(value)))
        graph.add((KW['step/'+stage],KW.usesResource,resource))
    for pattern,definition in operations.get('artifact_definitions',{}).items():
        node=artifact_node(pattern)
        if (node,RDF.type,KW.ArtifactSpecification) in graph:
            graph.remove((node,SKOS.definition,None));graph.add((node,SKOS.definition,Literal(definition,lang='en')))
    # Cover all project-owned nodes while honestly marking source-only behavioral gaps.
    local={s for s in graph.subjects() if str(s).startswith(str(KW))}
    for node in local:
        if list(graph.objects(node,SKOS.definition)):continue
        label=str(graph.value(node,RDFS.label) or str(node).split('#')[-1])
        comment=graph.value(node,RDFS.comment)
        status='source-derived description'
        if graph.value(node,KW.qualifiedName):
            path=str(graph.value(node,KW.sourcePath));name=str(graph.value(node,KW.qualifiedName))
            definition=str(comment) if comment and str(comment)!='Read the linked implementation and its call-site contract.' else f'Callable {name} defined in {path}, with signature ({graph.value(node,KW.signature)}). Its behavioral contract is not curated; inspect the implementation before invoking it directly.'
            if not comment or str(comment)=='Read the linked implementation and its call-site contract.':status='structural-only; behavior not curated'
        elif comment:definition=str(comment) if len(str(comment))<4000 else 'Agent operating instructions prescribing mode selection, scope binding, completion checks and recovery. Full instructions are in rdfs:comment.'
        elif graph.value(node,KW.artifactPattern):definition='Expected input/output content matching '+str(graph.value(node,KW.artifactPattern))+'. This specification does not assert an artifact exists.'
        elif graph.value(node,KW.conditionRule):definition=str(graph.value(node,KW.conditionRule))
        elif graph.value(node,KW.bindingRule):definition=str(graph.value(node,KW.bindingRule))
        elif graph.value(node,KW.configurationName):definition='Configuration requirement '+str(graph.value(node,KW.configurationName))+'. Values remain in authorized runtime settings; no secret is stored in the ontology.'
        elif graph.value(node,KW.resourceKind):definition='Source '+str(graph.value(node,KW.resourceKind))+' content at '+str(graph.value(node,KW.sourcePath))+', linked to its consuming step and protected by a source fingerprint.'
        elif graph.value(node,KW.commandArguments):definition='A '+str(graph.value(node,KW.executionMode))+' invocation template for '+label+'. Bind required parameters and establish conditions before use; this is not an execution record.'
        else:definition='Operational documentation term '+label+', used by the linked source-derived specifications. Inspect its typed relationships and source contract for scope.'
        graph.add((node,SKOS.definition,Literal(definition,lang='en')));graph.add((node,KW.definitionStatus,Literal(status)))
    # New contracts participate in the same stale-snapshot protection as source and schemas.
    for value in list(graph.objects(KW.ontology,KW.documentationInputs)):
        hashes=json.loads(str(value))
        for path in ['docs/codebase/operations.json',*sorted(worked_paths)]:hashes[path]=hashlib.sha256((root/path).read_bytes()).hexdigest()
        graph.remove((KW.ontology,KW.documentationInputs,value));graph.add((KW.ontology,KW.documentationInputs,Literal(json.dumps(hashes,sort_keys=True))))
    return {'definition_nodes':len(local),'stages_with_contracts':len(operations['stages']),
            'arguments':len(set(graph.subjects(RDF.type,KW.ArgumentSpecification))),
            'bindings':len(set(graph.subjects(RDF.type,KW.DataBindingSpecification)))}


def guide(graph, stage):
    """Retrieve a task recipe from RDF, including actual bound artifacts and formal arguments."""
    step=KW['step/'+stage];value=graph.value(step,KW.contractJson)
    if not value:raise ValueError('No operational contract for '+stage)
    result=json.loads(str(value));result['stage']=stage;result['definition']=str(graph.value(step,SKOS.definition))
    result['next_steps']=[str(n).rsplit('/',1)[-1] for n in graph.objects(step,KW.canAdvanceTo)]
    result['downstream_recheck']=[str(n).rsplit('/',1)[-1] for n in graph.objects(step,KW.invalidatesStep)]
    result['implementations']=[]
    result['resources']=[{'iri':str(n),'path':str(graph.value(n,KW.sourcePath)),
                          'kind':str(graph.value(n,KW.resourceKind)),'text':str(graph.value(n,KW.resourceText))}
                         for n in graph.objects(step,KW.usesResource)]
    result['information_transformations']=[json.loads(str(graph.value(n,KW.transformationJson))) for n in graph.subjects(KW.transformationStage,step) if graph.value(n,KW.transformationJson)]
    implementations=set(graph.objects(step,KW.hasImplementation))|set(graph.objects(None,KW.implementedBy))
    relevant={b['function'] for b in result['bindings']}|set(result.get('input_contract',{}).get('source_functions',[]))|{o['function'] for o in result['algorithm']}
    implementations|={function_node(*identity.split(':',1)) for identity in relevant}
    for node in sorted(implementations,key=str):
        identity=str(graph.value(node,KW.sourcePath))+':'+str(graph.value(node,KW.qualifiedName))
        if node not in set(graph.objects(step,KW.hasImplementation)) and identity not in relevant:continue
        result['implementations'].append({'iri':str(node),'source':identity,'line':int(graph.value(node,KW.lineStart) or 0),
            'signature':str(graph.value(node,KW.signature)),'returns':str(graph.value(node,KW.returnTypeExpression)),
            'definition':str(graph.value(node,SKOS.definition)),
            'arguments':[{'name':str(graph.value(a,KW.argumentName)),'type':str(graph.value(a,KW.typeExpression)),
                          'required':bool(graph.value(a,KW.argumentRequired).toPython()),
                          'default':str(graph.value(a,KW.defaultExpression) or '')} for a in graph.objects(node,KW.hasArgument)]})
    return result


def assess(graph, folder, outputs, stage, phase='after'):
    """Evaluate a bounded set of saved-data checks; never run commands or accept scientific claims."""
    from ontology_agent import inspect_run, read_artifact
    if phase not in ('before','after'):raise ValueError('Phase must be before or after')
    recipe=guide(graph,stage);folder=Path(folder).resolve();outputs=Path(outputs).resolve()
    observation=inspect_run(graph,folder,outputs)
    results=[];cache={}
    def read(pattern):
        if Path(pattern).is_absolute() or '..' in Path(pattern).parts:raise ValueError('Unsafe contract artifact pattern')
        if pattern not in cache:
            cache[pattern]=[(p,*read_artifact(p,folder)) for p in sorted(folder.glob(pattern)) if p.is_file()]
        return cache[pattern]
    def check(identifier,passed,message,severity='block'):
        results.append({'id':identifier,'status':'pass' if passed else 'review' if severity=='review' else 'runtime-check' if severity=='runtime' else 'blocked','message':message})
    def select(data,selector='$'):
        if selector=='$':return data
        if not selector.startswith('$.'):raise ValueError('Unsupported contract selector')
        for field in selector[2:].split('.'):
            if not isinstance(data,dict) or field not in data:return None
            data=data[field]
        return data
    def values(pattern,selector='$'):
        rows=read(pattern)
        if not rows or any(m['status']!='readable' for _,m,_ in rows):return None
        selected=[select(data,selector) for _,_,data in rows]
        if any(not isinstance(v,list) for v in selected):return None
        return [v for group in selected for v in group]
    def identifiers(rows,field):
        if rows is None or any(not isinstance(v,dict) or not isinstance(v.get(field),str) or not v[field].strip() for v in rows):return None
        ids=[v[field] for v in rows]
        return set(ids) if len(set(ids))==len(ids) else None
    own=next((r for r in observation['steps'] if r['step']==stage),None)
    if stage in ('preflight','store'):
        check('live-readiness',False,'Setup readiness has no per-run completion record. Establish the recipe runtime conditions explicitly.','runtime')
    elif phase=='after':
        if stage=='reports':check('report-availability',bool(own and own['readiness'] in ('recorded-with-readable-products','available-unrecorded')),'Require readable report products; availability does not invent a completion record.')
        else:check('saved-completion',bool(own and own['readiness']=='recorded-with-readable-products'),'Require recorded completion and readable required products; inspect superseded/partial outcomes separately.')
    else:
        mode=observation['mode'];inv=next((i for i in graph.objects(KW['step/'+stage],KW.hasInvocation) if str(graph.value(i,KW.executionMode))==('cli' if mode in ('integration','report') else mode)),None)
        if inv:
            for parent in graph.objects(inv,KW.requiresStepForMode):
                parent_name=str(parent).rsplit('/',1)[-1];state=next((r for r in observation['steps'] if r['step']==parent_name),None)
                check('prerequisite-'+parent_name,bool(state and state['readiness']=='recorded-with-readable-products'),'Establish prerequisite '+parent_name+' from its saved results; multi-run source selection and unobserved shared-store/preflight readiness require separate checks.','runtime' if parent_name in ('store','preflight') or stage in ('integrate','reports') else 'block')
        else:check('mode-contract',False,'No matching saved-run execution mode; use explicit setup/project checks.')
        for binding in recipe['bindings']:
            if binding.get('modes') and mode not in binding['modes']:continue
            if binding['direction']=='input' and not binding['artifact'].startswith('explicit '):
                rows=read(binding['artifact']);check('input-'+binding['id'],bool(rows) and all(m['status']=='readable' for _,m,_ in rows),'Input binding '+binding['id']+' requires readable '+binding['artifact'])
    types={'string':str,'array':list,'object':dict,'boolean':bool}
    for rule in recipe['checks']:
        kind=rule['kind']
        if phase not in rule.get('phases',['before'] if kind=='paper_contract' else ['after']):continue
        if rule.get('modes') and observation['mode'] not in rule['modes']:continue
        if kind=='runtime_condition':check(rule['id'],False,rule['instruction'],'runtime');continue
        if kind=='scientific_review':check(rule['id'],False,rule['instruction'],'review');continue
        if kind=='shape':
            rows=read(rule['pattern']);ok=bool(rows);count=0
            for _,meta,data in rows:
                data=select(data,rule.get('selector','$'))
                if meta['status']!='readable' or not isinstance(data,types[rule['container']]):ok=False;continue
                if rule.get('nonempty') and not data:ok=False
                items=data if isinstance(data,list) else [data];count+=len(items)
                for item in items:
                    if rule.get('live_only') and isinstance(item,dict) and item.get('excluded'):continue
                    if not isinstance(item,dict) or any(k not in item or not isinstance(item[k],types[t]) for k,t in rule['required'].items()):ok=False
                if rule.get('unique'):
                    ids=[item.get(rule['unique']) for item in items if isinstance(item,dict)]
                    if not all(isinstance(v,str) and v.strip() for v in ids) or len(set(v for v in ids if isinstance(v,str)))!=len(ids):ok=False
            check(rule['id'],ok,f'{rule["pattern"]}: checked {len(rows)} file(s), {count} record(s).',rule.get('severity','block'))
        elif kind=='paper_contract':
            rows=read('papers/*.json');ok=bool(rows);paper_keys=set()
            spec=recipe['input_contract']
            for _,meta,paper in rows:
                if meta['status']!='readable' or not isinstance(paper,dict):ok=False;continue
                if any(k not in paper or not isinstance(paper[k],types[t]) for k,t in spec['required_paper_fields'].items()):ok=False;continue
                if not paper['key'] or paper['key'] in paper_keys:ok=False
                paper_keys.add(paper['key']);ids=[]
                for concept in paper['concepts']:
                    if not isinstance(concept,dict) or any(k not in concept or not isinstance(concept[k],types[t]) or not concept[k] for k,t in spec['concept_fields'].items()):ok=False;continue
                    ids.append(concept['id'])
                if len(set(ids))!=len(ids):ok=False
                known=set(ids)
                for field,ends in [('relations',['s','o']),('causal',['cause','effect']),('measurements',['concept'])]:
                    for item in paper[field]:
                        if not isinstance(item,dict) or any(not isinstance(item.get(e),str) or item[e] not in known for e in ends):ok=False
            check(rule['id'],ok,'Paper keys/concept IDs must be unique; concept labels must be nonempty strings; claim endpoints must resolve within their paper. This is a conservative agent boundary check, not a change to extraction.')
        elif kind=='identity_coverage':
            source=identifiers(values(rule['source'],rule.get('source_selector','$')),rule.get('field','id'))
            target=identifiers(values(rule['target'],rule.get('target_selector','$')),rule.get('field','id'))
            check(rule['id'],source is not None and target is not None and source==target,'Require unique nonempty identifiers and exact source/returned identity coverage, including excluded records.')
        elif kind=='references':
            known=identifiers(values(rule['target']),rule.get('target_field','id'));rows=values(rule['pattern']);ok=known is not None and rows is not None
            for item in rows or []:
                if not isinstance(item,dict):ok=False;continue
                if rule.get('live_only') and item.get('excluded'):continue
                refs=select(item,rule['field'])
                refs=refs if isinstance(refs,list) else [refs]
                for ref in refs:
                    if rule.get('nested_field'):ref=ref.get(rule['nested_field']) if isinstance(ref,dict) else None
                    if rule.get('allow_empty') and ref in ('',None):continue
                    valid=isinstance(ref,str) and (ref in (known or set()) or rule.get('allow_iri') and ref.startswith(('http://','https://')))
                    if not valid:ok=False
            check(rule['id'],ok,'Every documented endpoint must resolve to a saved identifier or an explicitly permitted public IRI.')
        elif kind=='corpus_coverage':
            if observation['mode']=='wrapper':
                expected=identifiers(values('ingestion.json','$.papers'),'key')
            else:
                manifests=read('run.json');manifest=manifests[0][2] if len(manifests)==1 else None
                selected=select(manifest,'$.corpus.selection.selected')
                expected=identifiers(selected,'key') if isinstance(selected,list) else None
            rows=read(rule['pattern']);actual=identifiers([v for _,m,v in rows if m['status']=='readable'],'key')
            check(rule['id'],bool(expected) and actual==expected and len(rows)==len(expected),'Compare all selected paper keys with readable saved products, rejecting omissions, duplicates and unexpected records.')
        elif kind=='saved_validation':
            rows=read(rule['pattern']);data=rows[0][2] if len(rows)==1 else None
            check(rule['id'],isinstance(data,dict) and data.get('valid') is True and data.get('n_issues',0)==0,'Require valid=true and no recorded structural issues; not scientific acceptance.')
        elif kind=='rdf_pair':
            from rdflib import Graph, BNode
            from rdflib.compare import isomorphic
            pairs=[(rule['turtle'],rule['jsonld'])]
            if rule.get('from_manifest'):
                manifests=read('integration.json');manifest=manifests[0][2] if len(manifests)==1 else None
                name=select(manifest,'$.ontology.name')
                if not isinstance(name,str) or not name or Path(name).name!=name or '/' in name or '\\' in name:
                    check(rule['id'],False,'Require a safe ontology name recorded in the integration manifest.');continue
                pairs=[(name+'.ttl',name+'.jsonld')]
            ok=True;deferred=False
            for turtle,jsonld in pairs:
                a,b=read(turtle),read(jsonld)
                if len(a)!=1 or len(b)!=1 or any(row[1]['status']!='readable' for row in a+b):ok=False;continue
                # Parse exactly the bytes fingerprinted by read(), not a potentially changed path.
                try:
                    content_a=a[0][0].read_bytes();content_b=b[0][0].read_bytes()
                    if hashlib.sha256(content_a).hexdigest()!=a[0][1]['sha256'] or hashlib.sha256(content_b).hexdigest()!=b[0][1]['sha256']:ok=False;continue
                    ga=Graph().parse(data=content_a,format='turtle');gb=Graph().parse(data=content_b,format='json-ld')
                    blanks={n for g in (ga,gb) for triple in g for n in triple if isinstance(n,BNode)}
                    if max(len(ga),len(gb))>rule.get('max_triples',12000) or len(blanks)>rule.get('max_blank_nodes',40):
                        deferred=True
                        continue
                    if not isomorphic(ga,gb):ok=False
                except Exception:ok=False
            check(rule['id'],ok and not deferred,'Both exports parsed, but exact RDF isomorphism exceeds the documented graph-size/blank-node comparison limit. Perform a dedicated export audit; equality is not established.' if deferred and ok else 'Local Turtle/JSON-LD exports must be readable and isomorphic; imports are not fetched or reasoned over.','review' if deferred and ok else 'block')
        elif kind=='report_package':
            base=next((location for location in ('.','figures') if (folder/location/'index.md').is_file()),'.')
            ok=True
            for name in ('index.md','report.md','report.html','sweep_summary.csv'):
                rows=read(str(Path(base)/name));ok=ok and len(rows)==1 and rows[0][1]['status']=='readable'
            check(rule['id'],ok,'Require index, Markdown, HTML and sweep-summary products in the same report folder.')
            index=read(str(Path(base)/'index.md'))
            if index and index[0][1]['status']=='readable':
                content=index[0][0].read_text(encoding='utf-8')
                check(rule['id']+'-skipped','\nSkipped:' not in content,'The index records skipped figures; inspect reasons before treating the package as complete.','review')
        elif kind=='integration_links':
            manifests=read('integration.json');manifest=manifests[0][2] if len(manifests)==1 else None
            sources=select(manifest,'$.inputs');known={};ok=isinstance(sources,list) and len(sources)>=2
            for source in sources if isinstance(sources,list) else []:
                if not isinstance(source,dict):ok=False;continue
                rid,domain=source.get('run_id'),source.get('domain')
                if not isinstance(rid,str) or Path(rid).name!=rid or not rid or '/' in rid or '\\' in rid or '..' in rid or not isinstance(domain,str) or not domain:ok=False;continue
                path=outputs/rid/'ontology/enriched.json';meta,data=read_artifact(path,outputs)
                cache['source:'+rid]=[(path,meta,data)]
                if meta['status']!='readable' or not isinstance(data,list):ok=False;continue
                for item in data:
                    if isinstance(item,dict) and not item.get('excluded') and isinstance(item.get('iri'),str):known.setdefault(item['iri'],set()).add((domain,rid))
            for item in values('mappings.json') or []:
                if not isinstance(item,dict):ok=False;continue
                for side in ('a','b'):
                    iri,domain,rid=(item.get(side+suffix) for suffix in ('_iri','_domain','_run'))
                    if not all(isinstance(v,str) for v in (iri,domain,rid)) or (domain,rid) not in known.get(iri,set()):ok=False
            bridges=values('bridge_concepts.json')
            if bridges is None or values('mappings.json') is None:ok=False
            for bridge in bridges or []:
                if not isinstance(bridge,dict) or not isinstance(bridge.get('members'),list):ok=False;continue
                domains=set()
                for member in bridge['members']:
                    if not isinstance(member,dict):ok=False;continue
                    domain=member.get('domain');iri=member.get('iri')
                    if not isinstance(domain,str) or not isinstance(iri,str) or not any(d==domain for d,_ in known.get(iri,set())):ok=False
                    else:domains.add(domain)
                if len(domains)<2 or bridge.get('n_domains')!=len(domains) or sorted(domains)!=bridge.get('domains'):ok=False
            check(rule['id'],ok,'Mapping endpoints and bridge members must belong to the recorded source runs and domains. This does not establish mapping semantics.')
        elif kind in ('canonical_references','paper_coverage'):
            records=read('normalized/concepts.json');concepts=records[0][2] if len(records)==1 and isinstance(records[0][2],list) else []
            known={c['id'] for c in concepts if isinstance(c,dict) and isinstance(c.get('id'),str)};ok=bool(known)
            if kind=='canonical_references':
                for pattern,fields in [('normalized/relations.json',['s','o']),('normalized/causal.json',['cause','effect']),('normalized/measurements.json',['concept'])]:
                    for _,meta,items in read(pattern):
                        if meta['status']!='readable' or not isinstance(items,list):ok=False;continue
                        for value in items:
                            if not isinstance(value,dict) or any(not isinstance(value.get(k),str) or value[k] not in known for k in fields):ok=False
                check(rule['id'],ok,'Canonical relation, causal and measurement endpoints must reference saved canonical concept IDs.')
            else:
                expected={p['key'] for _,m,p in read('papers/*.json') if m['status']=='readable' and isinstance(p,dict) and p.get('concepts') and isinstance(p.get('key'),str)}
                actual={p for c in concepts if isinstance(c,dict) and isinstance(c.get('papers'),list) for p in c['papers'] if isinstance(p,str)}
                check(rule['id'],ok and expected==actual,'Canonical supporting-paper coverage must match input papers containing concepts. This does not reconstruct original-to-canonical merge decisions.')
        else:raise ValueError('Unsupported documented check kind '+kind)
    fingerprints=[]
    for pattern,rows in cache.items():
        for path,meta,_ in rows:
            if not meta.get('sha256'):continue
            fingerprints.append({'scope':'outputs' if pattern.startswith('source:') else 'run','path':meta['path'],'sha256':meta['sha256']})
            try:stable=hashlib.sha256(path.read_bytes()).hexdigest()==meta['sha256']
            except OSError:stable=False
            check('snapshot-'+meta['path'],stable,'The artifact must remain unchanged throughout assessment.')
    blocked=any(r['status']=='blocked' for r in results);review=any(r['status']=='review' for r in results)
    runtime=any(r['status']=='runtime-check' for r in results)
    return {'stage':stage,'phase':phase,'observed_at':observation['observed_at'],'checks':results,
            'decision':'stop-and-recover' if blocked else 'await-runtime-checks' if runtime else 'review-required' if review else 'ready-for-runtime-conditions' if phase=='before' else 'ready-for-next-step-checks',
            'artifact_fingerprints':fingerprints,
            'recovery':recipe['recovery'],'downstream_recheck':recipe['downstream_recheck'],
            'limitations':recipe['limitation'],'runtime_conditions':'Confirm provider/store readiness, authorized scope and process ownership separately. No commands were executed.'}
