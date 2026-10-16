"""Export focused reviewer views and navigable records for the codebase ontology.

Author: Brent Thompson <brent.thompson@ucf.edu>
Uses local WebVOWL assets and original IRIs; generated projections never rewrite source RDF.
"""
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import sys
from rdflib import Graph, URIRef, Literal, RDF, RDFS, OWL, SKOS
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dpv_dashboard.viewer import convert
OUT=ROOT/'outputs/development/codebase-docs/webvowl'
KW='https://w3id.org/ucf-dpv/knowledge-workflow/codebase#'
STAGES={'ingest':'Zotero ingestion','parse':'PDF parsing','extract':'Extraction','normalize':'Normalization',
        'ontology':'Placement','enrich':'Enrichment','interop':'Interoperability','integrate':'Integration',
        'reports':'Reports & figures','preflight':'Preflight','store':'Ontology store'}


def main():
    """Build bounded stage graphs, full downloadable data and source-linked review metadata."""
    src=ROOT/'docs/ontology/knowledge-workflow.ttl'
    if not src.is_file():raise SystemExit('Generate the source ontology first.')
    g=Graph().parse(src);ns=lambda name:URIRef(KW+name)
    OUT.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'dpv_dashboard/www/webvowl',OUT/'assets',dirs_exist_ok=True)
    shutil.copy2(ROOT/'docs/ontology/viewer/reviewer-bridge.js',OUT/'vowl-bridge.js')
    # Hide the upstream sidebar only in this generated copy; the reviewer panel shows original RDF types.
    frame=OUT/'assets/index.html'
    text=frame.read_text(encoding='utf-8').replace('</head>','<link rel="stylesheet" href="../frame.css"></head>')
    frame.write_text(text,encoding='utf-8')
    for name in ['index.html','reviewer.css','reviewer.js','journey.js','journey.css','frame.css','site-nav.css','site-nav.js']:
        shutil.copy2(ROOT/'docs/ontology/viewer'/name,OUT/name)
    schema=convert(g,show_hierarchy=True)
    nodes=set(g.subjects(RDF.type,OWL.NamedIndividual))|{URIRef(n['iri']) for n in schema['classAttribute']}
    nodes|={s for s in g.subjects(RDF.type,OWL.ObjectProperty) if str(s).startswith(KW)}
    nodes|={s for s in g.subjects(RDF.type,OWL.DatatypeProperty) if str(s).startswith(KW)}
    records={};source_paths=set()
    for node in sorted(nodes,key=str):
        label=str(g.value(node,RDFS.label) or str(node).rsplit('/',1)[-1])
        path=g.value(node,ns('sourcePath'));qualified=g.value(node,ns('qualifiedName'))
        stage=str(node).rsplit('/',1)[-1] if str(node).startswith(KW+'step/') else None
        if stage:label=STAGES[stage]
        elif qualified:label=str(qualified)
        elif path and str(path).endswith('.py'):label=Path(str(path)).name
        elif re.search('[a-z][A-Z]',label) and ' ' not in label:label=re.sub(r'(?<!^)([A-Z])',r' \1',label)
        pattern=g.value(node,ns('artifactPattern'))
        if pattern:
            friendly={'papers/*.json':'Paper records','ingestion.json':'Selected corpus','parsed/*.json':'Parsed text',
                      'ontology.ttl':'Formal ontology','ontology.jsonld':'Ontology JSON-LD','domain_layer.ttl':'Literature claims',
                      'corpus_report.md':'Corpus report','report.html':'HTML report','report.md':'Markdown report','index.md':'Figure index'}
            label=friendly.get(str(pattern),Path(str(pattern)).stem.replace('_',' ').capitalize())
            if str(pattern)=='normalized/concepts.json':label='Canonical concepts'
            if str(pattern)=='ontology/classes.json':label='Placed classes'
            if str(pattern)=='ontology/enriched.json':label='Enriched classes'
        definitions=[str(v) for v in g.objects(node,SKOS.definition)]
        record={'iri':str(node),'label':label,'definition':'\n\n'.join(dict.fromkeys(definitions)),
                'definition_status':str(g.value(node,ns('definitionStatus')) or 'source-reviewed specification' if definitions else 'definition unavailable in loaded snapshot'),
                'types':[str(t).rsplit('#',1)[-1] for t in g.objects(node,RDF.type) if t!=OWL.NamedIndividual],
                'fields':{},'links':[],'incoming':[]}
        for predicate in [ns(p) for p in ['signature','returnTypeExpression','sourcePath','lineStart','sourceDigest','artifactPattern','coverageStatus','bindingDirection','bindingSelector','bindingExpression','valueTransformation','argumentName','argumentKind','typeExpression','defaultExpression','argumentRequired','checkRule','recoveryAction','completionRule','recoveryRule','sideEffects','conditionRule','bindingRule','executionMode','commandArguments']]:
            values=[str(v) for v in g.objects(node,predicate)]
            if values:record['fields'][str(predicate).split('#')[-1]]=values
        if path and (qualified or str(g.value(node,ns('resourceKind')) or '')=='worked example'):
            source_paths.add(str(path));record['source_link']='source/'+str(path)+'.html#L'+str(g.value(node,ns('lineStart')) or 1)
        if str(g.value(node,ns('resourceKind')) or '')=='worked example':record['resource_text']=str(g.value(node,ns('resourceText')) or '')
        record['notes']=[str(v) for v in g.objects(node,SKOS.scopeNote)]
        contract=g.value(node,ns('contractJson'))
        if contract:record['contract']=json.loads(str(contract))
        records[str(node)]=record
    for s,p,o in sorted(g,key=lambda row:tuple(str(v) for v in row)):
        if str(s) in records and str(o) in records and p!=RDF.type:
            name=str(g.value(p,RDFS.label) or str(p).split('#')[-1])
            friendly={'canAdvanceTo':'Next stage','hasImplementation':'Uses function','expectsInput':'Reads input','expectsOutput':'Produces output',
                      'hasOperation':'Contains operation','operationImplementation':'Uses function','bindsArtifact':'Binds artifact',
                      'implementedBy':'Bound by function','nextOperation':'Next operation'}.get(name,re.sub(r'(?<!^)([A-Z])',r' \1',name))
            records[str(s)]['links'].append({'predicate':str(p),'label':friendly,'target':str(o)})
            inverse={'expectsInput':'Input to','expectsOutput':'Produced by','hasImplementation':'Implementation of',
                     'bindsArtifact':'Bound through','implementedBy':'Used in binding','hasArgument':'Argument of',
                     'operationImplementation':'Implements operation','hasDataBinding':'Binding of'}.get(str(p).split('#')[-1],'Linked from')
            records[str(o)]['incoming'].append({'predicate':str(p),'label':inverse,'source':str(s)})
    source=OUT/'source'
    for relative in source_paths:
        path=(ROOT/relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():continue
        destination=source/(relative+'.html');destination.parent.mkdir(parents=True,exist_ok=True)
        lines=path.read_text(encoding='utf-8-sig').splitlines()
        page='<!doctype html><!-- Author: Brent Thompson <brent.thompson@ucf.edu>; summary: read-only source snapshot. -->'
        page+='<meta charset="utf-8"><title>'+html.escape(relative)+'</title><style>body{font:14px system-ui;margin:24px;background:#f6f7f8}pre{font:13px Consolas,monospace;background:white;padding:16px;overflow:auto}span{display:block;scroll-margin-top:80px}span:target{background:#ffed9b}a{color:#667}</style>'
        page+='<h1>'+html.escape(relative)+'</h1><p>Read-only code snapshot · SHA256 '+hashlib.sha256(path.read_bytes()).hexdigest()+'</p><pre>'
        page+=''.join('<span id="L'+str(i)+'"><a href="#L'+str(i)+'">'+str(i).rjust(4)+'</a>  '+html.escape(line)+'</span>' for i,line in enumerate(lines,1))+'</pre>'
        destination.write_text(page,encoding='utf-8')
    def payload(selected,edges,title):
        view=Graph()
        for node in selected:
            if str(node) not in records:continue
            view.add((node,RDF.type,OWL.Class));view.add((node,RDFS.label,Literal(records[str(node)]['label'])))
        for s,p,o in edges:
            if s in selected and o in selected:
                view.add((s,p,o));friendly=next((link['label'] for link in records[str(s)]['links'] if link['predicate']==str(p) and link['target']==str(o)),str(p).split('#')[-1])
                view.add((p,RDFS.label,Literal(friendly)))
        result=convert(view,show_hierarchy=True)
        result['header'].update(title={'en':title},description={'en':'Read-only display projection. Original RDF record types and definitions are shown in the reviewer panel.'},author=['Brent Thompson'])
        for attribute in result['classAttribute']:
            record=records[attribute['iri']];attribute['comment']={'en':record['definition']}
        result['_source']={'path':'docs/ontology/knowledge-workflow.ttl','sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
        return result
    def save(name,value):(OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    stage_nodes={ns('step/'+s) for s in STAGES}
    save('workflow-overview.json',payload(stage_nodes,[t for t in g if t[1]==ns('canAdvanceTo')],'UCF DPV · Workflow dependencies'))
    for stage in STAGES:
        step=ns('step/'+stage);artifacts=set(g.objects(step,ns('expectsInput')))|set(g.objects(step,ns('expectsOutput')))
        save('stage-'+stage+'-data.json',payload({step}|artifacts,[t for t in g if t[0]==step and t[1] in [ns('expectsInput'),ns('expectsOutput')]],STAGES[stage]+' · Data flow'))
        functions=set(g.objects(step,ns('hasImplementation')));operations=set(g.objects(step,ns('hasOperation')))
        functions|={f for op in operations for f in g.objects(op,ns('operationImplementation'))}
        # The initial implementation view shows the operation sequence. Function neighborhoods
        # remain one click away in the inspector, avoiding duplicate spoke nodes for every step.
        selected={step}|(operations if operations else functions)
        save('stage-'+stage+'-code.json',payload(selected,[t for t in g if t[1] in [ns('hasImplementation'),ns('hasOperation'),ns('operationImplementation'),ns('nextOperation')]],STAGES[stage]+' · Implementation'))
    schema['header'].update(title={'en':'UCF DPV · Ontology schema'},description={'en':'Formal class/property model. Imported term definitions are preserved where available; unavailable external definitions are explicitly identified.'})
    save('ontology-schema.json',schema)
    save('records.json',{'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'records':records,'stages':STAGES})
    journey=g.value(ns('LiteratureToOntologyWorkflow'),ns('journeyDefinitionJson'))
    if not journey:raise ValueError('Regenerate the ontology with the information journey first.')
    save('journey.json',json.loads(str(journey)))
    from data_journey import export_traces
    trace_run='si-topcon-n15-20261015-150628'
    if (ROOT/'outputs'/trace_run/'normalized/concepts.json').is_file():
        print(json.dumps(export_traces(ROOT/'outputs',OUT,trace_run,'integration-n15-20261015-150628')))
    else:
        save('concept-journey.json',{'status':'unavailable','concepts':[],'message':'The saved n15 example corpus is unavailable in this checkout.'})
    # Full export is available for download; the interactive page opens bounded neighborhoods instead.
    save('complete-codebase.json',payload(set(nodes),[t for t in g if t[1]!=RDF.type],'UCF DPV · Complete codebase records'))
    from documentation_library import build_library
    print(json.dumps(build_library(ROOT,OUT)))
    print(json.dumps({'records':len(records),'stage_views':len(STAGES)*2,'source_snapshots':len(source_paths)}))


if __name__=='__main__':main()
