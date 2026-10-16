"""Enrich the codebase graph with connected contracts, resources and external definitions.

Author: Brent Thompson <brent.thompson@ucf.edu>
Statically reads repository source and pinned ontologies; never executes pipeline modules.
"""
import ast
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD

KW = Namespace('https://w3id.org/ucf-dpv/knowledge-workflow/codebase#')
CCO = Namespace('https://www.commoncoreontologies.org/')
PROV = Namespace('http://www.w3.org/ns/prov#')
SKOS = Namespace('http://www.w3.org/2004/02/skos/core#')
DCT = Namespace('http://purl.org/dc/terms/')


def file_node(path):
    return KW['file/'+quote(path, safe='/')]


def function_node(path, name):
    return KW['function/'+quote(path+':'+name, safe='/.:')]


def freshness_errors(graph, root):
    """Reject stale documentation without importing application modules or reading settings."""
    root = Path(root).resolve()
    expected = {}
    for node in graph.subjects(KW.sourceDigest, None):
        path = graph.value(node, KW.sourcePath)
        if path:expected[str(path)] = str(graph.value(node, KW.sourceDigest))
    for value in graph.objects(KW.ontology, KW.documentationInputs):
        expected.update(json.loads(str(value)))
    errors = []
    resources={p.relative_to(root).as_posix() for pattern in ['src/resources/schemas/*.json','src/resources/prompts/*.md'] for p in root.glob(pattern)}
    documented={p for p in expected if p.startswith(('src/resources/schemas/','src/resources/prompts/'))}
    if resources!=documented:errors.append('Prompt/schema inventory changed; regenerate documentation')
    for name, digest in expected.items():
        path = (root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            errors.append('Missing or out-of-scope source: '+name)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append('Stale documentation: '+name)
    if not expected:errors.append('No source fingerprints in graph')
    return errors


def enrich(graph, root, inventory, contract):
    """Connect the inventory and make planning/inspection rules machine-readable."""
    root = Path(root)
    graph.bind('skos', SKOS)
    extra_classes = {
        'CodebaseSnapshot': (CCO.ont00000853, 'A source-derived documentation snapshot, not the running program.'),
        'ResourceSpecification': (CCO.ont00000965, 'Prescriptive source content such as a model prompt or JSON schema.'),
        'EnvironmentConditionSpecification': (CCO.ont00000965, 'A condition an executing agent must establish before invoking a command.'),
        'RuntimeObservation': (CCO.ont00000853, 'A timestamped read-only observation of recorded state; not a process or completion claim.'),
    }
    for name, (parent, definition) in extra_classes.items():
        graph.add((KW[name], RDF.type, OWL.Class))
        graph.add((KW[name], RDFS.subClassOf, parent))
        graph.add((KW[name], RDFS.subClassOf, PROV.Entity))
        graph.add((KW[name], RDFS.label, Literal(name)))
        graph.add((KW[name], SKOS.definition, Literal(definition)))
    objects = {
        'documentsWorkflow': ('CodebaseSnapshot','WorkflowSpecification'),
        'hasCodeUnit': ('CodebaseSnapshot','CodeUnitSpecification'),
        'containsCodeUnit': ('CodeUnitSpecification','CodeUnitSpecification'),
        'importsCodeUnit': ('CodeUnitSpecification','CodeUnitSpecification'),
        'staticallyReferences': ('CodeUnitSpecification','CodeUnitSpecification'),
        'usesResource': ('StepSpecification','ResourceSpecification'),
        'definedIn': ('ConfigurationSpecification','CodeUnitSpecification'),
        'requiresCondition': ('InvocationSpecification','EnvironmentConditionSpecification'),
        'requiresStepForMode': ('InvocationSpecification','StepSpecification'),
        'coversStep': ('InvocationSpecification','StepSpecification'),
        'observesStep': ('RuntimeObservation','StepSpecification'),
        'observesArtifact': ('RuntimeObservation','ArtifactRecord'),
        'requiredOutput': ('StepSpecification','ArtifactSpecification'),
    }
    for name, (domain, target) in objects.items():
        graph.add((KW[name], RDF.type, OWL.ObjectProperty))
        graph.add((KW[name], RDFS.label, Literal(name)))
        graph.add((KW[name], RDFS.domain, KW[domain]))
        graph.add((KW[name], RDFS.range, KW[target]))
        graph.add((KW[name], SKOS.definition, Literal(f'Source-checked documentation link from {domain} to {target}; not an assertion of successful execution.')))
    graph.add((KW.containsCodeUnit, OWL.inverseOf, KW.containedIn))
    text_properties = ['conditionRule','resourceText','resourceKind','documentationInputs','settingKind',
                       'recordedStatus','readiness','observedAt','observedDigest','observationJson','artifactLocations']
    for name in text_properties:
        graph.add((KW[name], RDF.type, OWL.DatatypeProperty))
        graph.add((KW[name], RDFS.label, Literal(name)))
        graph.add((KW[name], RDFS.range, XSD.string))
    for cls in ['CodeUnitSpecification','WorkflowSpecification','StepSpecification','ArtifactSpecification',
                'InvocationSpecification','ParameterSpecification','ConfigurationSpecification','OperatingGuideSpecification']:
        graph.add((KW[cls], RDFS.subClassOf, PROV.Entity))
    for cls in ['WorkflowSpecification','StepSpecification']:
        graph.add((KW[cls], RDFS.subClassOf, PROV.Plan))
    snapshot = KW.CodebaseDocumentation
    graph.add((snapshot,RDF.type,KW.CodebaseSnapshot))
    graph.add((snapshot,RDF.type,OWL.NamedIndividual))
    graph.add((snapshot,RDFS.label,Literal('Source-linked Knowledge Workflow codebase documentation')))
    graph.add((snapshot,KW.documentsWorkflow,KW.LiteratureToOntologyWorkflow))
    modules = {item['path']:file_node(item['path']) for item in inventory}
    module_names = {p[:-3].replace('/','.') if not p.endswith('/__init__.py') else p[:-12].replace('/','.') : p
                    for p in modules if p.endswith('.py')}
    functions = {(item['path'],f['name']):function_node(item['path'],f['name']) for item in inventory for f in item['functions']}
    for path, module in modules.items():
        graph.add((snapshot,KW.hasCodeUnit,module))
        if not path.endswith('.py'): continue
        tree = ast.parse((root/path).read_text(encoding='utf-8-sig'))
        aliases = {}
        for statement in tree.body:
            if isinstance(statement,ast.Import):
                for alias in statement.names:
                    aliases[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
            elif isinstance(statement,ast.ImportFrom) and statement.module and not statement.level:
                for alias in statement.names:
                    aliases[alias.asname or alias.name] = statement.module+'.'+alias.name
        for observed in next(x for x in inventory if x['path']==path)['imports']:
            if observed in module_names:graph.add((module,KW.importsCodeUnit,modules[module_names[observed]]))
        for target in aliases.values():
            if target in module_names:graph.add((module,KW.importsCodeUnit,modules[module_names[target]]))
        for f in next(x for x in inventory if x['path']==path)['functions']:
            caller = functions[(path,f['name'])]
            graph.add((module,KW.containsCodeUnit,caller))
            for call in f['calls']:
                resolved = None
                if (path,call) in functions:
                    resolved = functions[(path,call)]
                elif call.split('.')[0] in aliases:
                    full = aliases[call.split('.')[0]] + call[len(call.split('.')[0]):]
                    for mod, other in module_names.items():
                        if full.startswith(mod+'.') and (other,full[len(mod)+1:]) in functions:
                            resolved = functions[(other,full[len(mod)+1:])]
                            break
                if resolved:graph.add((caller,KW.staticallyReferences,resolved))
    # Reuse artifact specifications by exact pattern so production and consumption connect.
    for step in list(graph.subjects(RDF.type,KW.StepSpecification)):
        for predicate in [KW.expectsInput,KW.expectsOutput]:
            for old in list(graph.objects(step,predicate)):
                pattern = str(graph.value(old,KW.artifactPattern))
                node = KW['artifact-pattern/'+hashlib.sha256(pattern.encode()).hexdigest()[:20]]
                graph.add((node,RDF.type,KW.ArtifactSpecification));graph.add((node,RDF.type,OWL.NamedIndividual))
                graph.add((node,RDFS.label,Literal(pattern)));graph.add((node,KW.artifactPattern,Literal(pattern)))
                graph.remove((step,predicate,old));graph.add((step,predicate,node))
                graph.remove((old,None,None))
    for row in contract['steps']:
        step = KW['step/'+row['id']]
        graph.add((step,KW.artifactLocations,Literal(json.dumps(row.get('artifact_locations',['.'])))))
        for pattern in row.get('required_artifacts',[]):
            artifact = KW['artifact-pattern/'+hashlib.sha256(pattern.encode()).hexdigest()[:20]]
            graph.add((artifact,RDF.type,KW.ArtifactSpecification));graph.add((artifact,RDF.type,OWL.NamedIndividual))
            graph.add((artifact,RDFS.label,Literal(pattern)));graph.add((artifact,KW.artifactPattern,Literal(pattern)))
            graph.add((step,KW.requiredOutput,artifact))
        for mode in ['cli','wrapper']:
            invocation = KW[f'invocation/{row["id"]}/{mode}']
            if (invocation,RDF.type,KW.InvocationSpecification) not in graph:continue
            for dependency in row.get(mode+'_prerequisites',[]):
                graph.add((invocation,KW.requiresStepForMode,KW['step/'+dependency]))
            for key in row.get('conditions',[]):
                condition = KW['condition/'+key]
                graph.add((condition,RDF.type,KW.EnvironmentConditionSpecification));graph.add((condition,RDF.type,OWL.NamedIndividual))
                graph.add((condition,RDFS.label,Literal(key)));graph.add((condition,KW.conditionRule,Literal(contract['conditions'][key])))
                graph.add((invocation,KW.requiresCondition,condition))
            for covered in contract.get('coverage',{}).get(mode+'_'+row['id'],[row['id']]):
                graph.add((invocation,KW.coversStep,KW['step/'+covered]))
        for pattern in row.get('resource_patterns',[]):
            for path in sorted(root.glob(pattern)):
                relative = path.relative_to(root).as_posix()
                resource = KW['resource/'+quote(relative,safe='/')]
                graph.add((resource,RDF.type,KW.ResourceSpecification));graph.add((resource,RDF.type,OWL.NamedIndividual))
                graph.add((resource,RDFS.label,Literal(relative)));graph.add((resource,KW.sourcePath,Literal(relative)))
                graph.add((resource,KW.sourceDigest,Literal(hashlib.sha256(path.read_bytes()).hexdigest())))
                graph.add((resource,KW.resourceKind,Literal('schema' if path.suffix=='.json' else 'prompt')))
                graph.add((resource,KW.resourceText,Literal(path.read_text(encoding='utf-8'))));graph.add((step,KW.usesResource,resource))
    definitions = {}
    for path in modules:
        if path.startswith(('src/','dpv_dashboard/')) and path.endswith('.py'):
            tree = ast.parse((root/path).read_text(encoding='utf-8-sig'))
            for statement in tree.body:
                if isinstance(statement,(ast.Assign,ast.AnnAssign)):
                    for target in statement.targets if isinstance(statement,ast.Assign) else [statement.target]:
                        if isinstance(target,ast.Name):definitions.setdefault(target.id,[]).append(path)
    for node in graph.subjects(RDF.type,KW.ConfigurationSpecification):
        name = str(graph.value(node,KW.configurationName))
        locations = definitions.get(name,[])
        if name.startswith('domain.'):locations=['dpv_dashboard/model.py']
        for path in locations:graph.add((node,KW.definedIn,modules[path]))
        graph.add((node,KW.settingKind,Literal('source-defined configuration' if locations else 'environment/project requirement; inspect implementation')))
    # Add imported definitions and ancestor labels with explicit provenance, not guessed synonyms.
    imported = Graph()
    for item in json.loads((root/'docs/ontology/imports/lock.json').read_text()):
        imported += Graph().parse(root/'docs/ontology/imports'/item['file'])
    used = {o for s,p,o in graph if p in (RDFS.subClassOf,RDFS.subPropertyOf) and isinstance(o,URIRef) and not str(o).startswith(str(KW))}
    pending = list(used)
    while pending:
        term = pending.pop()
        for predicate in [RDFS.label,SKOS.definition,RDFS.comment]:
            for value in imported.objects(term,predicate):graph.add((term,predicate,value))
        for parent in imported.objects(term,RDFS.subClassOf):
            if isinstance(parent,URIRef):
                graph.add((term,RDFS.subClassOf,parent))
                if parent not in used:used.add(parent);pending.append(parent)
    for node in list(graph.subjects(RDF.type,OWL.Class)):
        if str(node).startswith(str(KW)):
            for definition in list(graph.objects(node,RDFS.comment)):graph.add((node,SKOS.definition,definition))
            for parent in graph.objects(node,RDFS.subClassOf):graph.add((node,DCT.source,parent))
    # Contract/schema text is also a source of truth and must participate in freshness checks.
    paths = ['docs/codebase/workflow.json','docs/codebase/agent-guide.md','docs/ontology/shapes.ttl']
    paths += [str(p.relative_to(root)).replace('\\','/') for p in root.glob('src/resources/schemas/*.json')]
    paths += [str(p.relative_to(root)).replace('\\','/') for p in root.glob('src/resources/prompts/*.md')]
    hashes = {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sorted(paths)}
    graph.add((KW.ontology,KW.documentationInputs,Literal(json.dumps(hashes,sort_keys=True))))
    return {'connected_files':len(modules),'static_reference_edges':len(list(graph.triples((None,KW.staticallyReferences,None)))),
            'resource_links':len(list(graph.triples((None,KW.usesResource,None)))), 'external_terms_enriched':len(used)}
