"""Generate source-linked codebase documentation and the operational workflow ontology.

Author: Brent Thompson <brent.thompson@ucf.edu>
Reads first-party source statically; never imports pipeline modules or executes workflow examples.
"""
import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote
from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, XSD, URIRef

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/codebase'
ONT = ROOT / 'docs/ontology'
AUTHOR = 'Brent Thompson <brent.thompson@ucf.edu>'
CODE = {'.py', '.ps1', '.sh', '.js', '.css', '.html', '.ipynb', '.rq'}
EXCLUDE = ('outputs/', 'paper/', 'dpv_dashboard/www/webvowl/', 'docs/ontology/imports/')
NS = Namespace('https://w3id.org/ucf-dpv/knowledge-workflow/codebase#')
CCO = Namespace('https://www.commoncoreontologies.org/')
PROV = Namespace('http://www.w3.org/ns/prov#')
DCT = Namespace('http://purl.org/dc/terms/')


def code_files():
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    return sorted({p for p in names if not p.startswith(EXCLUDE) and (Path(p).suffix in CODE or p == 'script.txt') and (ROOT / p).is_file()})


def inventory():
    items = []
    for name in code_files():
        path = ROOT / name
        text = path.read_text(encoding='utf-8-sig')
        item = {'path': name, 'language': path.suffix, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'functions': [], 'imports': []}
        if path.suffix == '.py':
            tree = ast.parse(text)
            item['summary'] = (ast.get_docstring(tree) or f'First-party {path.stem.replace("_", " ")} module.').split('\n\n')[0]
            def visit(nodes, scope=''):
                for node in nodes:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        qualified = scope + node.name
                        if not isinstance(node, ast.ClassDef):
                            item['functions'].append({'name': qualified, 'line': node.lineno, 'end_line': node.end_lineno,
                                'signature': ast.unparse(node.args), 'returns': ast.unparse(node.returns) if node.returns else 'not annotated',
                                'summary': (ast.get_docstring(node) or 'Read the linked implementation and its call-site contract.').split('\n\n')[0],
                                'calls': sorted({ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)})})
                        visit(node.body, qualified + '.')
            visit(tree.body)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    item['imports'].extend(n.name for n in node.names)
                elif isinstance(node, ast.ImportFrom):
                    item['imports'].append('.' * node.level + (node.module or ''))
        else:
            lines = [s.strip(' #/*<>!-') for s in text.splitlines()[:30] if s.strip() and 'Author:' not in s]
            item['summary'] = next((s for s in lines if len(s) > 20 and not s.startswith(('#!', '<!DOCTYPE', 'param('))), f'{path.stem.replace("_", " ")} {path.suffix} support file.')[:400]
        item['imports'] = sorted(set(item['imports']))
        items.append(item)
    return items


def author_headers():
    """Apply only headers, recording an exact patch; Python executable AST must match."""
    import difflib
    patches, status = [], []
    for name in code_files():
        path = ROOT / name
        before = path.read_text(encoding='utf-8-sig')
        if f'Author: {AUTHOR}' in before[:12000]:
            status.append({'path': name, 'status': 'already present'})
            continue
        if path.suffix == '.py':
            tree = ast.parse(before)
            old_doc = ast.get_docstring(tree, clean=False)
            lines = before.splitlines(keepends=True)
            if old_doc is not None:
                node = tree.body[0]
                new_doc = old_doc.rstrip() + '\n\nAuthor: ' + AUTHOR + '\n'
                quoted = '"""' + new_doc.replace('\\', '\\\\').replace('"""', '\\"""') + '"""'
                after = ''.join(lines[:node.lineno-1]) + quoted + '\n' + ''.join(lines[node.end_lineno:])
            else:
                at = 0
                while at < min(2, len(lines)) and (lines[at].startswith('#!') or re.search(r'coding[:=]', lines[at])):
                    at += 1
                summary = f'{path.stem.replace("_", " ").capitalize()} support for the Knowledge Workflow system.'
                after = ''.join(lines[:at]) + f'"""{summary}\n\nAuthor: {AUTHOR}\n"""\n' + ''.join(lines[at:])
            check = ast.parse(after)
            def executable(t):
                if t.body and isinstance(t.body[0], ast.Expr) and isinstance(t.body[0].value, ast.Constant) and isinstance(t.body[0].value.value, str):
                    t.body.pop(0)
                return ast.dump(t, include_attributes=False)
            if executable(tree) != executable(check):
                raise ValueError(f'Executable AST changed: {name}')
        elif path.suffix == '.ipynb':
            value = json.loads(before)
            value['cells'].insert(0, {'cell_type': 'markdown', 'metadata': {}, 'source': [f'# Knowledge Workflow model training notebook\n', f'Author: {AUTHOR}\n', 'Prepares or runs the optional local model training/evaluation workflow; review runtime requirements before execution.\n']})
            after = json.dumps(value, indent=1, ensure_ascii=False) + '\n'
        else:
            summary = f'{path.stem.replace("_", " ")} support for Knowledge Workflow; retain the existing operational notes below.'
            header = f'Author: {AUTHOR}\nSummary: {summary}\n'
            if path.suffix in ('.js', '.css'):
                header = '/*\n' + header + '*/\n'
            elif path.suffix == '.html':
                header = '<!--\n' + header + '-->\n'
            else:
                header = ''.join('# ' + line + '\n' for line in header.splitlines())
            lines = before.splitlines(keepends=True)
            at = 1 if lines and (lines[0].startswith('#!') or lines[0].lower().startswith('<!doctype')) else 0
            after = ''.join(lines[:at]) + header + ''.join(lines[at:])
        patches.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/'+name, tofile='b/'+name))
        path.write_text(after, encoding='utf-8')
        status.append({'path': name, 'status': 'header updated; executable Python AST unchanged' if path.suffix == '.py' else 'language-appropriate header updated'})
    target = ROOT / 'outputs/development/codebase-docs'
    target.mkdir(parents=True, exist_ok=True)
    (target/'author-headers.patch').write_text(''.join(patches), encoding='utf-8')
    (DOC/'author-headers.json').write_text(json.dumps(status, indent=2)+'\n', encoding='utf-8')


def build():
    DOC.mkdir(parents=True, exist_ok=True)
    ONT.mkdir(parents=True, exist_ok=True)
    contract = json.loads((DOC/'workflow.json').read_text(encoding='utf-8'))
    items = inventory()
    (DOC/'inventory.json').write_text(json.dumps(items, indent=2)+'\n', encoding='utf-8')
    g = Graph()
    for name, ns in [('kw',NS),('cco',CCO),('prov',PROV),('dcterms',DCT)]: g.bind(name,ns)
    ontology = NS.ontology
    g.add((ontology,RDF.type,OWL.Ontology));g.add((ontology,DCT.creator,Literal(AUTHOR)))
    g.add((ontology,OWL.versionInfo,Literal('2026-10-16 operational codebase snapshot')))
    g.add((ontology,RDFS.comment,Literal(contract['namespace_status'])))
    lock = json.loads((ONT/'imports/lock.json').read_text())
    for item in lock:
        imported = Graph().parse(ONT/'imports'/item['file'])
        if hashlib.sha256((ONT/'imports'/item['file']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Import digest changed: '+item['file'])
        iri = next(imported.subjects(RDF.type,OWL.Ontology))
        version = next(imported.objects(iri,OWL.versionIRI),iri)
        item.update(ontology_iri=str(iri),version_iri=str(version))
        g.add((ontology,OWL.imports,version))
    (ONT/'imports/lock.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8')
    ice, prescribed, plan, process = CCO.ont00000958, CCO.ont00000965, CCO.ont00000974, CCO.ont00000366
    classes = {'CodeUnitSpecification':prescribed,'WorkflowSpecification':plan,'StepSpecification':plan,'ArtifactSpecification':prescribed,'OperatingGuideSpecification':prescribed,
               'InvocationSpecification':prescribed,'ParameterSpecification':prescribed,'ConfigurationSpecification':prescribed,
               'ExecutionProcess':process,'ExecutionRecord':ice,'ArtifactRecord':ice}
    for name,parent in classes.items():
        g.add((NS[name],RDF.type,OWL.Class));g.add((NS[name],RDFS.subClassOf,parent));g.add((NS[name],RDFS.label,Literal(re.sub(r'(?<!^)([A-Z])',r' \1',name))))
    definitions = {
        'CodeUnitSpecification':'Prescriptive code content of a first-party module or callable, distinguished from its storage bearer and executions.',
        'WorkflowSpecification':'A plan prescribing the literature-to-ontology workflow and its allowable step dependencies.',
        'StepSpecification':'A plan prescribing a bounded operation, its prerequisites, implementations and checks; not an actual execution.',
        'ArtifactSpecification':'An expected input or output content specification, represented by a path pattern or explicitly descriptive input requirement; not an assertion of existence.',
        'OperatingGuideSpecification':'Prescriptive agent instructions for setup, binding, scope selection, examples, review and recovery.',
        'InvocationSpecification':'A command argument-vector template with mode and parameter bindings; documentation does not assert it has executed.',
        'ParameterSpecification':'A required argument binding rule whose placeholder must resolve to an authorized real value before execution.',
        'ConfigurationSpecification':'A named configuration requirement; secret values are deliberately absent.',
        'ExecutionProcess':'An actual information-processing occurrence following a step specification; no such occurrence is asserted by documentation generation.',
        'ExecutionRecord':'Information content describing an actual execution; distinct from the process it describes.',
        'ArtifactRecord':'Information content recording a concrete run artifact and its provenance, distinct from an expected artifact specification.'}
    for name, definition in definitions.items():g.add((NS[name],RDFS.comment,Literal(definition)))
    g.add((NS.ExecutionProcess,RDFS.subClassOf,PROV.Activity));g.add((NS.ExecutionRecord,RDFS.subClassOf,PROV.Entity));g.add((NS.ArtifactRecord,RDFS.subClassOf,PROV.Entity))
    # Plans/code contents are ICEs, never execution processes or material storage media.
    objects = {'hasStep':('WorkflowSpecification','StepSpecification'),'hasOperatingGuide':('WorkflowSpecification','OperatingGuideSpecification'),'requiresCompletionOf':('StepSpecification','StepSpecification'),
               'hasImplementation':('StepSpecification','CodeUnitSpecification'),'expectsInput':('StepSpecification','ArtifactSpecification'),
               'expectsOutput':('StepSpecification','ArtifactSpecification'),'hasInvocation':('StepSpecification','InvocationSpecification'),
               'requiresBinding':('InvocationSpecification','ParameterSpecification'),'requiresSetting':('StepSpecification','ConfigurationSpecification'),
               'containedIn':('CodeUnitSpecification','CodeUnitSpecification'),'executesSpecification':('ExecutionProcess','StepSpecification'),
               'describesExecution':('ExecutionRecord','ExecutionProcess')}
    for name,(domain,ran) in objects.items():
        g.add((NS[name],RDF.type,OWL.ObjectProperty));g.add((NS[name],RDFS.domain,NS[domain]));g.add((NS[name],RDFS.range,NS[ran]));g.add((NS[name],RDFS.label,Literal(name)))
        g.add((NS[name],RDFS.comment,Literal(f'Relates a {domain} to a {ran} according to the project operational contract; does not itself assert execution.')))
    literals = ['sourcePath','qualifiedName','lineStart','signature','sourceDigest','artifactPattern','commandArguments','executionMode',
                'completionRule','recoveryRule','sideEffects','configurationName','bindingRule','order','callTargetText','evidenceStatus']
    for name in literals:
        g.add((NS[name],RDF.type,OWL.DatatypeProperty));g.add((NS[name],RDFS.label,Literal(name)))
        g.add((NS[name],RDFS.comment,Literal('Operational metadata: '+re.sub(r'([A-Z])',r' \1',name).lower()+'. Source paths are repository-relative; examples are templates.')))
        g.add((NS[name],RDFS.range,XSD.integer if name in ('lineStart','order') else XSD.string))
    def entity(uri,kind,label):
        g.add((uri,RDF.type,NS[kind]));g.add((uri,RDF.type,OWL.NamedIndividual));g.add((uri,RDFS.label,Literal(label)));return uri
    units={}
    lines=['# Source module and callable reference','', 'Author: '+AUTHOR,'',
           'Generated statically; call expressions are syntactic observations, not a complete resolved call graph. All file links point to first-party code. Third-party code and runtime outputs are excluded.','']
    for item in items:
        module=entity(NS['file/'+quote(item['path'],safe='/')],'CodeUnitSpecification',item['path'])
        for key,val in [('sourcePath',item['path']),('sourceDigest',item['sha256'])]:g.add((module,NS[key],Literal(val)))
        g.add((module,RDFS.comment,Literal(item['summary'])))
        lines += [f"## {item['path']}",'',item['summary'].replace('\n',' '),'',f"[Source](../../{item['path']}) · SHA256 `{item['sha256']}`",'',
                  '| Callable | Line | Signature | Summary |','|---|---:|---|---|']
        for f in item['functions']:
            identity=item['path']+':'+f['name'];node=entity(NS['function/'+quote(identity,safe='/.:')],'CodeUnitSpecification',identity);units[identity]=node
            for key,val in [('sourcePath',item['path']),('qualifiedName',f['name']),('lineStart',f['line']),('signature',f['signature']),('sourceDigest',item['sha256'])]:g.add((node,NS[key],Literal(val)))
            g.add((node,NS.containedIn,module));g.add((node,RDFS.comment,Literal(f['summary'])))
            for call in f['calls']:g.add((node,NS.callTargetText,Literal(call)))
            clean=lambda s:str(s).replace('|','\\|').replace('\n',' ')
            lines.append(f"| `{f['name']}` | {f['line']} | `{clean(f['signature'])}` | {clean(f['summary'])} |")
        lines += ['', 'Imports: '+', '.join('`'+x+'`' for x in item['imports']), '']
    workflow=entity(NS.LiteratureToOntologyWorkflow,'WorkflowSpecification','Literature to reviewed domain ontologies and integration')
    operating=entity(NS.AgentOperatingInstructions,'OperatingGuideSpecification','Agent instructions: setup, mode selection, examples and recovery')
    g.add((workflow,NS.hasOperatingGuide,operating))
    g.add((operating,RDFS.comment,Literal((DOC/'agent-guide.md').read_text(encoding='utf-8'))))
    guide=['# Agent operational step reference','', 'Author: '+AUTHOR,'',
           'Start from `LiteratureToOntologyWorkflow` in the RDF graph. Examples are templates, statically checked against entry points but never executed during documentation generation. Resolve every uppercase binding before execution. Use only one execution mode per run.','']
    for row in contract['steps']:
        step=entity(NS['step/'+row['id']],'StepSpecification',row['label']);g.add((workflow,NS.hasStep,step))
        g.add((step,RDFS.comment,Literal(row['description'])));g.add((step,NS.order,Literal(row['order'],datatype=XSD.integer)))
        for key,field in [('completionRule','completion'),('recoveryRule','recovery'),('sideEffects','effects')]:g.add((step,NS[key],Literal(row[field])))
        for dep in row['prerequisites']:g.add((step,NS.requiresCompletionOf,NS['step/'+dep]))
        guide += [f"## {row['id']}: {row['label']}",'',row['description'],'', 'Prerequisites: '+', '.join(row['prerequisites']), '', 'Implementations:']
        for identity in row['functions']:
            if identity not in units:raise ValueError('Unknown operational function '+identity)
            g.add((step,NS.hasImplementation,units[identity]));guide.append('- `'+identity+'`')
        for field,predicate in [('inputs',NS.expectsInput),('outputs',NS.expectsOutput)]:
            guide += ['',field.capitalize()+':']
            for n,value in enumerate(row[field]):
                artifact=entity(NS[f"artifact/{row['id']}/{field}/{n}"],'ArtifactSpecification',value);g.add((artifact,NS.artifactPattern,Literal(value)));g.add((step,predicate,artifact));guide.append('- `'+value+'`')
        for setting in row['configuration']:
            config=entity(NS['setting/'+quote(setting,safe='')],'ConfigurationSpecification',setting);g.add((config,NS.configurationName,Literal(setting)));g.add((step,NS.requiresSetting,config))
        for mode in ['cli','wrapper']:
            argv=row.get(mode)
            if not argv:continue
            invocation=entity(NS[f"invocation/{row['id']}/{mode}"],'InvocationSpecification',mode+' '+row['id'])
            g.add((step,NS.hasInvocation,invocation));g.add((invocation,NS.commandArguments,Literal(json.dumps(argv))))
            g.add((invocation,NS.executionMode,Literal(mode)));g.add((invocation,NS.evidenceStatus,Literal('source-checked template; not live-executed')))
            guide += ['',mode+' prerequisites: '+', '.join(row.get(mode+'_prerequisites',[])),
                      '',mode+' argument vector:', '```json',json.dumps(argv),'```']
            for binding,rule in contract['bindings'].items():
                if any(re.search(r'(?<![A-Z0-9_])'+re.escape(binding)+r'(?![A-Z0-9_])',arg) for arg in argv):
                    param=entity(NS['parameter/'+binding],'ParameterSpecification',binding);g.add((param,NS.bindingRule,Literal(rule)));g.add((invocation,NS.requiresBinding,param))
        guide += ['', 'Completion: '+row['completion'],'','Recovery: '+row['recovery'],'','Effects: '+row['effects'],'']
        guide += ['Required saved products: '+', '.join('`'+p+'`' for p in row.get('required_artifacts',[])),
                  '', 'Conditions:'] + ['- '+contract['conditions'][c] for c in row.get('conditions',[])] + ['']
    (DOC/'modules.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (DOC/'agent-steps.md').write_text('\n'.join(guide)+'\n',encoding='utf-8')
    from codebase_ontology import enrich
    enrichment = enrich(g, ROOT, items, contract)
    from operational_contracts import build_contracts
    enrichment.update(build_contracts(g, ROOT, items))
    from data_journey import enrich_journey
    enrichment.update(enrich_journey(g, ROOT))
    (ONT/'enrichment.json').write_text(json.dumps(enrichment,indent=2)+'\n',encoding='utf-8')
    g.serialize(ONT/'knowledge-workflow.ttl',format='turtle')
    g.serialize(ONT/'knowledge-workflow.jsonld',format='json-ld',indent=2)
    print(f'{len(items)} code files, {len(units)} callables, {len(contract["steps"])} steps, {len(g)} triples')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--author-headers',action='store_true',help='Apply approved first-party author headers before generating the inventory')
    args=parser.parse_args()
    if args.author_headers:author_headers()
    build()
