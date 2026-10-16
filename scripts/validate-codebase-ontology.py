"""Validate offline ontology imports, operational links, SHACL and bounded OWL-RL consistency.

Author: Brent Thompson <brent.thompson@ucf.edu>
Does not execute pipeline commands or modify source artifacts.
"""
import hashlib
import json
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef, SKOS
from rdflib.compare import isomorphic
from rdflib.collection import Collection
from codebase_ontology import freshness_errors
from ontology_agent import invocation
import importlib.util
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/ontology'
KW = Namespace('https://w3id.org/ucf-dpv/knowledge-workflow/codebase#')


def operational_errors(graph, root, inventory):
    """Check navigation, mode-specific dependencies and contract/source freshness before reasoning."""
    errors = freshness_errors(graph, root)
    files = {str(graph.value(n,KW.sourcePath)) for n in graph.objects(KW.CodebaseDocumentation,KW.hasCodeUnit)}
    if files != {row['path'] for row in inventory}:errors.append('Snapshot does not connect every inventory file')
    reached = set(graph.objects(KW.CodebaseDocumentation,KW.hasCodeUnit))
    reached.update(o for n in list(reached) for o in graph.objects(n,KW.containsCodeUnit))
    units = set(graph.subjects(RDF.type,KW.CodeUnitSpecification))
    if units-reached:errors.append('Disconnected code units')
    steps = set(graph.subjects(RDF.type,KW.StepSpecification))
    for mode in ['cli','wrapper']:
        active,done=set(),set()
        def visit(step):
            if step in active:raise ValueError('Mode-specific dependency cycle: '+mode)
            if step in done:return
            active.add(step)
            inv=invocation(graph,step,mode)
            if not list(graph.objects(inv,KW.requiresCondition)):errors.append('Missing environmental conditions '+str(inv))
            if not list(graph.objects(inv,KW.coversStep)):errors.append('Missing invocation coverage '+str(inv))
            argv=json.loads(str(graph.value(inv,KW.commandArguments)))
            required={str(p).rsplit('/',1)[-1] for p in graph.objects(inv,KW.requiresBinding)}
            known={str(p).rsplit('/',1)[-1] for p in graph.subjects(RDF.type,KW.ParameterSpecification)}
            used={token for arg in argv for token in re.findall(r'(?<![A-Z0-9_])[A-Z][A-Z0-9_]+(?![A-Z0-9_])',arg) if token in known}
            if required!=used:errors.append('Invocation binding mismatch '+str(inv))
            for parent in graph.objects(inv,KW.requiresStepForMode):
                if parent not in steps:raise ValueError('Missing prerequisite step')
                visit(parent)
            active.remove(step);done.add(step)
        for step in steps:
            if any(str(graph.value(i,KW.executionMode))==mode for i in graph.objects(step,KW.hasInvocation)):
                try:visit(step)
                except ValueError as exc:errors.append(str(exc));active.clear()
    # Artifact flow is checked explicitly, in addition to reachability of code and templates.
    for upstream,downstream in [('parse','extract'),('extract','normalize'),('normalize','ontology'),('ontology','enrich')]:
        outputs=set(graph.objects(KW['step/'+upstream],KW.expectsOutput))
        if not outputs.intersection(graph.objects(KW['step/'+downstream],KW.expectsInput)):
            errors.append('Disconnected artifact flow '+upstream+' -> '+downstream)
    for term in graph.subjects(RDF.type,OWL.Class):
        if str(term).startswith(str(KW)) and not (list(graph.objects(term,RDFS.comment)) or list(graph.objects(term,URIRef('http://www.w3.org/2004/02/skos/core#definition')))):
            errors.append('Undefined local class '+str(term))
    for term in {s for s in graph.subjects() if str(s).startswith(str(KW))}:
        if not any(str(v).strip() for v in graph.objects(term,SKOS.definition)):errors.append('Missing SKOS definition '+str(term))
    for step in steps:
        if not graph.value(step,KW.contractJson) or not graph.value(step,KW.hasRecovery):errors.append('Missing operational recipe '+str(step))
        else:
            recipe=json.loads(str(graph.value(step,KW.contractJson)))
            if not recipe.get('input_contract') or not recipe.get('algorithm') or not recipe.get('bindings') or not recipe.get('checks'):
                errors.append('Incomplete field-level stage recipe '+str(step))
            orders=[op['order'] for op in recipe.get('algorithm',[])]
            if orders!=list(range(1,len(orders)+1)):errors.append('Invalid operation order '+str(step))
            if not any(str(graph.value(r,KW.resourceKind))=='worked example' for r in graph.objects(step,KW.usesResource)):
                errors.append('Missing worked example '+str(step))
            for check in graph.objects(step,KW.hasCheck):
                rule=json.loads(str(graph.value(check,KW.checkRule)))
                expected=rule.get('phases',['before'] if rule['kind']=='paper_contract' else ['after'])
                observed=[json.loads(str(v))[-1] for v in graph.objects(check,KW.evaluationArguments)]
                if set(expected)!=set(observed):errors.append('Check phase mismatch '+str(check))
    for binding in graph.subjects(RDF.type,KW.DataBindingSpecification):
        if not graph.value(binding,KW.implementedBy) or not graph.value(binding,KW.bindsArtifact):errors.append('Disconnected data binding '+str(binding))
    return errors


def main():
    from pyshacl import validate
    from owlrl import DeductiveClosure, OWLRL_Semantics
    graph = Graph().parse(BASE/'knowledge-workflow.ttl')
    jsonld = Graph().parse(BASE/'knowledge-workflow.jsonld', format='json-ld')
    errors = []
    if not isomorphic(graph, jsonld): errors.append('Turtle/JSON-LD differ')
    lock = json.loads((BASE/'imports/lock.json').read_text())
    combined = Graph()
    for item in lock:
        path = BASE/'imports'/item['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']: errors.append('Import fingerprint: '+item['file'])
        imported = Graph().parse(path)
        if list(imported.objects(None, OWL.imports)): errors.append('Unresolved transitive imports: '+item['file'])
        combined += imported
    allowed_imports = {URIRef(row['version_iri']) for row in lock}
    if set(graph.objects(None,OWL.imports)) != allowed_imports: errors.append('Unpinned imports')
    for name in ['ont00000958','ont00000965','ont00000974','ont00000366']:
        uri = URIRef('https://www.commoncoreontologies.org/'+name)
        if (uri,RDF.type,OWL.Class) not in combined: errors.append('Missing CCO class '+name)
    combined += graph
    ok, _, report = validate(graph, shacl_graph=Graph().parse(BASE/'shapes.ttl'), inference='none')
    if not ok:errors.append('SHACL failed')
    (BASE/'shacl-report.txt').write_text(report,encoding='utf-8')
    inventory = json.loads((ROOT/'docs/codebase/inventory.json').read_text())
    errors.extend(operational_errors(graph,ROOT,inventory))
    spec=importlib.util.spec_from_file_location('document_codebase',ROOT/'scripts/document-codebase.py')
    source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
    if set(source.code_files()) != {row['path'] for row in inventory}:errors.append('Inventory misses added/removed first-party code')
    if source.inventory()!=inventory:errors.append('Inventory differs from current static source analysis')
    steps = set(graph.subjects(RDF.type,KW.StepSpecification))
    def visit(step,stack):
        if step in stack:
            errors.append('Step dependency cycle');return
        for parent in graph.objects(step,KW.requiresCompletionOf):
            if parent not in steps:errors.append('Missing prerequisite '+str(parent))
            visit(parent,stack|{step})
    for step in steps:visit(step,set())
    functions = {(row['path'],f['name']):f for row in inventory for f in row['functions']}
    for function in graph.subjects(KW.qualifiedName,None):
        identity=(str(graph.value(function,KW.sourcePath)),str(graph.value(function,KW.qualifiedName)))
        if identity not in functions:errors.append('Function link missing '+str(identity))
        elif int(graph.value(function,KW.lineStart)) != functions[identity]['line']:errors.append('Stale function line '+str(identity))
        elif str(graph.value(function,KW.signature)) != functions[identity]['signature']:errors.append('Stale function signature '+str(identity))
    invocations = list(graph.subjects(RDF.type,KW.InvocationSpecification))
    for invocation in invocations:
        argv=json.loads(str(graph.value(invocation,KW.commandArguments)))
        if not isinstance(argv,list) or not all(isinstance(a,str) and a for a in argv):errors.append('Invalid argument vector')
        for param in graph.objects(invocation,KW.requiresBinding):
            if not graph.value(param,KW.bindingRule):errors.append('Binding rule missing')
    # OWL-RL materialization is bounded verification, not complete OWL 2 DL classification.
    DeductiveClosure(OWLRL_Semantics).expand(combined)
    disjoint = {(a,b) for a,b in combined.subject_objects(OWL.disjointWith)}
    for group in combined.subjects(RDF.type,OWL.AllDisjointClasses):
        members=list(Collection(combined,combined.value(group,OWL.members)))
        disjoint.update((a,b) for a in members for b in members if a!=b)
    custom = set(graph.subjects(RDF.type,OWL.NamedIndividual))
    conflicts=[]
    for node in custom:
        types=set(combined.objects(node,RDF.type))
        if OWL.Nothing in types or any(a in types and b in types for a,b in disjoint):conflicts.append(str(node))
    for cls in graph.subjects(RDF.type,OWL.Class):
        ancestors=set(combined.objects(cls,RDFS.subClassOf))|{cls}
        if OWL.Nothing in ancestors or any(a in ancestors and b in ancestors for a,b in disjoint):conflicts.append(str(cls))
    if conflicts:errors.append('Inferred type conflicts')
    result={'valid_within_checked_scope':not errors,'errors':errors,'shacl_conforms':bool(ok),'steps':len(steps),
            'invocation_templates':len(invocations),'source_files':len(inventory),'triples':len(graph),
            'inferred_type_conflicts':conflicts,'reasoning':'OWL-RL materialization plus named disjointness checks over pinned imports',
            'full_owl2_dl_reasoner':'Not run: Java/complete DL reasoner unavailable. No full BFO/CCO certification claimed.',
            'execution_examples':'Source-checked argument templates; no literature/model workflows executed.'}
    result['operational_checks']='All code units reachable; source/resource/contract fingerprints; shared artifact flow; mode-specific prerequisites, bindings and conditions.'
    local_nodes={s for s in graph.subjects() if str(s).startswith(str(KW))}
    result['definition_coverage']={'project_nodes':len(local_nodes),'with_skos_definition':sum(bool(list(graph.objects(n,SKOS.definition))) for n in local_nodes)}
    result['operational_contracts']={'stages':len(set(graph.subjects(KW.contractJson,None))),
                                     'data_bindings':len(set(graph.subjects(RDF.type,KW.DataBindingSpecification))),
                                     'formal_arguments':len(set(graph.subjects(RDF.type,KW.ArgumentSpecification))),
            'detailed_worked_examples':[str(s).rsplit('/',1)[-1] for s in sorted(graph.subjects(KW.contractJson,None),key=str)],
            'source_reviewed_operations':len(set(graph.subjects(RDF.type,KW.OperationSpecification)))}
    (BASE/'validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    if errors:raise SystemExit(1)


if __name__ == '__main__':main()
