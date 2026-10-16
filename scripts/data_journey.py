"""Model information transformations and export read-only concept journey snapshots.

Author: Brent Thompson <brent.thompson@ucf.edu>
Separates workflow specifications from observed saved records. Never imports pipeline agents,
reads credentials, writes a source run, or asserts reconstructed merges as recorded lineage.
"""
import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from rdflib import Graph, Literal, RDF, RDFS, OWL, URIRef
from codebase_ontology import KW, CCO, PROV, SKOS, function_node


def enrich_journey(graph, root):
    """Connect information states and transformations to artifacts, stages and source functions."""
    from operational_contracts import artifact_node
    root=Path(root);path='docs/codebase/data-flow.json'
    flow=json.loads((root/path).read_text(encoding='utf-8'))
    states={s['id']:s for s in flow['states']}
    if len(states)!=len(flow['states']) or any(s not in states for s in flow['main_path']):raise ValueError('Invalid information-state identities')
    for name,parent,definition in [
        ('InformationStateSpecification',CCO.ont00000965,'A prescription of the structure and identity of an information representation at a workflow boundary; it is not the physical material or scientific concept the data describes.'),
        ('InformationTransformationSpecification',CCO.ont00000974,'A plan for transforming specified information representations while retaining, adding or omitting documented content; it is not an assertion that a process occurred.')]:
        graph.add((KW[name],RDF.type,OWL.Class));graph.add((KW[name],RDFS.subClassOf,parent));graph.add((KW[name],RDFS.subClassOf,PROV.Entity))
        graph.add((KW[name],RDFS.label,Literal(name)));graph.add((KW[name],SKOS.definition,Literal(definition,lang='en')))
    properties={
        'hasInformationState':('WorkflowSpecification','InformationStateSpecification','Specifies an information representation used by this workflow.'),
        'hasInformationTransformation':('WorkflowSpecification','InformationTransformationSpecification','Specifies an information transformation plan within this workflow.'),
        'transformsInputState':('InformationTransformationSpecification','InformationStateSpecification','Identifies an input representation potentially consumed by this plan; optionalInputState marks inputs that are not required for every execution mode.'),
        'optionalInputState':('InformationTransformationSpecification','InformationStateSpecification','Identifies an optional input representation; absence does not prohibit the transformation.'),
        'producesInformationState':('InformationTransformationSpecification','InformationStateSpecification','Identifies the output representation prescribed by this transformation plan.'),
        'representedByArtifact':('InformationStateSpecification','ArtifactSpecification','Identifies expected saved artifacts carrying this information representation.'),
        'transformationStage':('InformationTransformationSpecification','StepSpecification','Links the information transformation to its implementing workflow stage.'),
        'transformationImplementation':('InformationTransformationSpecification','CodeUnitSpecification','Links a transformation plan to source code implementing its documented adaptation.')}
    for name,(source,target,definition) in properties.items():
        graph.add((KW[name],RDF.type,OWL.ObjectProperty));graph.add((KW[name],RDFS.domain,KW[source]));graph.add((KW[name],RDFS.range,KW[target]))
        graph.add((KW[name],RDFS.label,Literal(name)));graph.add((KW[name],SKOS.definition,Literal(definition,lang='en')))
    for name,definition in [('informationStateJson','Structured information-state fields and scope.'),('transformationJson','Structured retention, addition, omission and provenance limits for an information transformation.'),('journeyDefinitionJson','The complete source-reviewed information journey, including presentation order and transformation scope.')]:
        graph.add((KW[name],RDF.type,OWL.AnnotationProperty));graph.add((KW[name],RDFS.label,Literal(name)));graph.add((KW[name],SKOS.definition,Literal(definition,lang='en')))
    graph.add((KW.LiteratureToOntologyWorkflow,KW.journeyDefinitionJson,Literal(json.dumps(flow,sort_keys=True))))
    def entity(node,kind,label,definition):
        graph.add((node,RDF.type,KW[kind]));graph.add((node,RDF.type,OWL.NamedIndividual));graph.add((node,RDFS.label,Literal(label)));graph.add((node,SKOS.definition,Literal(definition,lang='en')))
    for key,state in states.items():
        node=KW['information/'+key];entity(node,'InformationStateSpecification',state['label'],state['description'])
        graph.add((KW.LiteratureToOntologyWorkflow,KW.hasInformationState,node));graph.add((node,KW.informationStateJson,Literal(json.dumps(state,sort_keys=True))))
        graph.add((node,SKOS.scopeNote,Literal(state['note'],lang='en')))
        for pattern in state['artifacts']:
            artifact=artifact_node(pattern)
            if (artifact,RDF.type,KW.ArtifactSpecification) not in graph:raise ValueError('Unconnected journey artifact '+pattern)
            graph.add((node,KW.representedByArtifact,artifact))
    for transform in flow['transformations']:
        node=KW['transformation/'+transform['id']];entity(node,'InformationTransformationSpecification',transform['label'],transform['label']+'. '+transform['limitation'])
        graph.add((KW.LiteratureToOntologyWorkflow,KW.hasInformationTransformation,node));graph.add((node,KW.transformationJson,Literal(json.dumps(transform,sort_keys=True))))
        step=KW['step/'+transform['stage']]
        if (step,RDF.type,KW.StepSpecification) not in graph:raise ValueError('Unknown transformation stage')
        graph.add((node,KW.transformationStage,step))
        for prop,key in [('transformsInputState','from'),('producesInformationState','to')]:
            for state in transform[key]:
                if state not in states:raise ValueError('Unknown transformation state '+state)
                graph.add((node,KW[prop],KW['information/'+state]))
        for state in transform.get('optional_from',[]):
            if state not in transform['from']:raise ValueError('Optional input must also be a declared input')
            graph.add((node,KW.optionalInputState,KW['information/'+state]))
        for identity in transform['functions']:
            function=function_node(*identity.split(':',1))
            if not graph.value(function,KW.qualifiedName):raise ValueError('Unknown transformation function '+identity)
            graph.add((node,KW.transformationImplementation,function))
    for value in list(graph.objects(KW.ontology,KW.documentationInputs)):
        hashes=json.loads(str(value));hashes[path]=hashlib.sha256((root/path).read_bytes()).hexdigest()
        graph.remove((KW.ontology,KW.documentationInputs,value));graph.add((KW.ontology,KW.documentationInputs,Literal(json.dumps(hashes,sort_keys=True))))
    return {'information_states':len(states),'information_transformations':len(flow['transformations'])}


def identifier(value):
    """Accept a simple saved-run or record identifier without path traversal."""
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',value) or '..' in value:raise ValueError('Invalid journey record identifier')
    return value


def label_key(value):
    """Return a conservative label comparison key; equality is not a recorded merge decision."""
    return ' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',value).casefold())) if isinstance(value,str) else ''


class Snapshot:
    """Read bounded stable source bytes under one authorized outputs root with fingerprints."""
    def __init__(self, root):
        self.root=Path(root).resolve();self.cache={}

    def read(self, relative, optional=False):
        path=(self.root/relative).resolve()
        if not path.is_relative_to(self.root):raise ValueError('Journey source escapes outputs')
        key=path.relative_to(self.root).as_posix()
        if key not in self.cache:
            if optional and not path.is_file():return None
            before=path.stat()
            if before.st_size>64*1024*1024:raise ValueError('Journey source exceeds 64 MiB limit')
            data=path.read_bytes();after=path.stat()
            if (before.st_mtime_ns,before.st_size)!=(after.st_mtime_ns,after.st_size):raise ValueError('Journey source changed while being read')
            self.cache[key]=(path,data,hashlib.sha256(data).hexdigest())
        return self.cache[key][1]

    def json(self, relative, optional=False):
        raw=self.read(relative,optional)
        return json.loads(raw) if raw is not None else None

    def fingerprints(self):
        for path,_,digest in self.cache.values():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Journey source changed during export; retry the snapshot')
        return [{'path':key,'sha256':digest} for key,(_,_,digest) in sorted(self.cache.items())]


def public_record(value, fields):
    """Select public scientific fields; exclude raw model calls, runtime config and local PDF paths."""
    return {key:value[key] for key in fields if key in value} if isinstance(value,dict) else {}


def build_traces(outputs, run_id, integration_id=None):
    """Observe saved joins and reconstruct candidate original labels without asserting exact lineage."""
    run_id=identifier(run_id);integration_id=identifier(integration_id) if integration_id else None
    snapshot=Snapshot(outputs);prefix=run_id+'/'
    concepts=snapshot.json(prefix+'normalized/concepts.json')
    if not isinstance(concepts,list) or not concepts:raise ValueError('Canonical concepts must be a nonempty list')
    by_id={identifier(c['id']):c for c in concepts if isinstance(c,dict) and isinstance(c.get('label'),str)}
    if len(by_id)!=len(concepts):raise ValueError('Canonical concepts need unique IDs and string labels')
    papers={}
    for path in sorted((Path(outputs)/run_id/'papers').glob('*.json')):
        paper=snapshot.json(prefix+'papers/'+path.name)
        if not isinstance(paper,dict):raise ValueError('Invalid saved paper')
        key=identifier(paper.get('key'))
        if key in papers:raise ValueError('Duplicate paper key')
        papers[key]=paper
    classes=snapshot.json(prefix+'ontology/classes.json',True) or []
    enriched=snapshot.json(prefix+'ontology/enriched.json',True) or []
    mappings=snapshot.json(prefix+'ontology/mappings.json',True) or []
    imports=snapshot.json(prefix+'ontology/imported_definitions.json',True) or []
    facets=snapshot.json(prefix+'ontology/facets.json',True) or {}
    normalized={kind:snapshot.json(prefix+'normalized/'+kind+'.json',True) or [] for kind in ('relations','causal','measurements')}
    for rows in [classes,enriched,mappings,imports,*normalized.values()]:
        if not isinstance(rows,list):raise ValueError('A saved scientific record collection must be a JSON list')
    lineage=snapshot.json(prefix+'normalized/concept_lineage.json',True)
    lineage_exists=prefix+'normalized/concept_lineage.json' in snapshot.cache
    saved_links={}
    for row in lineage if isinstance(lineage,list) else []:
        if isinstance(row,dict) and all(isinstance(row.get(k),str) for k in ('paper','original_id','canonical_id')):
            saved_links.setdefault((row['paper'],row['original_id']),[]).append(row)
    placed={c['id']:c for c in classes if isinstance(c,dict) and isinstance(c.get('id'),str)}
    enriched_by={c['id']:c for c in enriched if isinstance(c,dict) and isinstance(c.get('id'),str)}
    graphs={}
    for name in ('ontology.ttl','domain_layer.ttl'):
        raw=snapshot.read(prefix+name,True)
        graphs[name]=Graph().parse(data=raw,format='turtle') if raw else None
    integration={};integration_mappings=[];bridges=[];merged=None;integration_applies=False
    if integration_id:
        integration=snapshot.json(integration_id+'/integration.json',True) or {}
        integration_applies=any(isinstance(s,dict) and s.get('run_id')==run_id for s in integration.get('inputs',[]))
        if integration_applies:
            integration_mappings=snapshot.json(integration_id+'/mappings.json',True) or []
            bridges=snapshot.json(integration_id+'/bridge_concepts.json',True) or []
            names=integration.get('ontology',{}).get('files',[])
            name=next((n for n in names if isinstance(n,str) and n.endswith('_merged.ttl')),None)
            if name:
                if Path(name).name!=name:raise ValueError('Unsafe merged export name')
                raw=snapshot.read(integration_id+'/'+name,True)
                if raw:merged=Graph().parse(data=raw,format='turtle')
    # Restrict candidate aliases by recorded supporting-paper membership; report ambiguity explicitly.
    alias_targets={}
    for cid,c in by_id.items():
        for key in c.get('papers',[]):
            if not isinstance(key,str):continue
            for name in [c['label'],*c.get('alt_labels',[])]:
                normalized_name=label_key(name)
                if normalized_name:alias_targets.setdefault((key,normalized_name),set()).add(cid)
    traces=[]
    for cid,c in by_id.items():
        original=[];paper_refs=[]
        for key in c.get('papers',[]):
            if not isinstance(key,str):continue
            p=papers.get(key)
            paper_refs.append({'key':key,'title':p.get('title',key) if p else key,'available':bool(p),'parse_stats':p.get('parse_stats',{}) if p else {},'href':'snapshots/'+run_id+'/papers/'+quote(key,safe='')+'.json.html'})
            if not p:continue
            for row in p.get('concepts',[]):
                if not isinstance(row,dict) or not isinstance(row.get('id'),str):continue
                saved=saved_links.get((key,row.get('id')),[]) if isinstance(row.get('id'),str) else []
                targets={v['canonical_id'] for v in saved if v['canonical_id'] in by_id} if lineage_exists else alias_targets.get((key,label_key(row.get('label'))),set())
                if cid not in targets:continue
                local_id=row.get('id');claims=[]
                for kind,fields in [('relations',('s','o')),('causal',('cause','effect')),('measurements',('concept','entity'))]:
                    for claim in p.get(kind,[]):
                        if not isinstance(claim,dict) or local_id not in [claim.get(f) for f in fields]:continue
                        labels={str(x.get('id')):x.get('label','Unnamed concept') for x in p.get('concepts',[]) if isinstance(x,dict)}
                        out=public_record(claim,['s','p','o','cause','effect','polarity','concept','entity','value','unit','condition','evidence','verified','evidence_status'])
                        out.update(kind=kind,endpoint_labels={f:labels.get(str(claim.get(f)),str(claim.get(f,''))) for f in fields});claims.append(out)
                recorded_valid=len(saved)==1 and saved[0].get('original_label',row.get('label'))==row.get('label') and saved[0].get('canonical_label',c['label'])==c['label']
                original.append({'paper':key,'concept':public_record(row,['id','label','type','definition','synonyms','figures','mentions','sections']),
                    'status':('recorded' if recorded_valid else 'recorded-needs-review') if lineage_exists else 'reconstructed-ambiguous' if len(targets)>1 else 'reconstructed-candidate','candidate_canonical_ids':sorted(targets),
                    'basis':'Saved concept_lineage.json row; source/target labels and duplicate source identities checked.' if lineage_exists else 'Normalized label equals a canonical label or alternate label within a recorded supporting paper; the merge decision was not saved.',
                    'claims':claims,'href':'snapshots/'+run_id+'/papers/'+quote(key,safe='')+'.json.html#'+quote(str(local_id),safe='')})
        pc=placed.get(cid);ec=enriched_by.get(cid);iri=(ec or pc or {}).get('iri')
        identity_warning='The saved class IRI changed between placement and enrichment. Export membership is checked using the later enriched IRI.' if pc and ec and pc.get('iri')!=ec.get('iri') else ''
        old_aliases={v for v in c.get('alt_labels',[]) if isinstance(v,str)}
        new_aliases={v for v in (ec or {}).get('alt_labels',[]) if isinstance(v,str)} if ec and 'alt_labels' in ec else None
        local_mappings=[m for m in mappings if isinstance(m,dict) and m.get('id')==cid]
        matched_imports=[m for m in imports if isinstance(m,dict) and m.get('id')==cid] if isinstance(imports,list) else []
        domain_graph=graphs['ontology.ttl'];claims_graph=graphs['domain_layer.ttl']
        class_node=URIRef(iri) if isinstance(iri,str) else None
        formal_present=(class_node,RDF.type,OWL.Class) in domain_graph if domain_graph is not None and class_node else None
        literature_nodes=[str(s) for s,p,o in claims_graph.triples((None,None,class_node)) if str(p).endswith('ontologyClass')] if claims_graph is not None and class_node else []
        connected=[m for m in integration_mappings if isinstance(m,dict) and iri and iri in (m.get('a_iri'),m.get('b_iri'))]
        bridge_groups=[b for b in bridges if isinstance(b,dict) and any(isinstance(m,dict) and m.get('iri')==iri for m in b.get('members',[]))]
        canonical_claims={kind:[v for v in rows if isinstance(v,dict) and cid in [v.get(f) for f in ('s','o','cause','effect','concept','entity')]] for kind,rows in normalized.items()}
        related_ids={v for rows in canonical_claims.values() for row in rows for k,v in row.items() if k in ('s','o','cause','effect','concept','entity') and isinstance(v,str)}
        related_ids|={v.get('o') for v in (ec or {}).get('restrictions',[]) if isinstance(v,dict) and isinstance(v.get('o'),str)}
        traces.append({'id':cid,'label':c['label'],'canonical':public_record(c,['id','label','alt_labels','type','papers','n_papers','mentions','definitions','score','tier','rank']),
            'related_labels':{i:by_id[i]['label'] for i in related_ids if i in by_id},
            'papers':paper_refs,'original_candidates':original,'lineage':{'status':'recorded-map-with-possible-gaps' if lineage_exists else 'unavailable-exact-map','recorded':'Supporting paper keys and canonical alt_labels are saved.','reconstructed':'No label reconstruction is substituted for missing rows in a saved map.' if lineage_exists else 'Original concept candidates are label-based, not recorded merge decisions.','missing':'Inspect missing/duplicate or changed-label source mappings.' if lineage_exists else 'Exact (paper key, original concept ID) → canonical ID mapping is not persisted by the current pipeline.'},
            'canonical_claims':canonical_claims,'placed':public_record(pc,['id','label','iri','parent','parent_source','excluded','review_flags']) if pc else None,
            'enriched':public_record(ec,['id','label','iri','alt_labels','definition','definition_source','definition_status','restrictions','disjoint_with','review_flags']) if ec else None,
            'identity_warning':identity_warning,'enrichment_alias_changes':{'added':sorted(new_aliases-old_aliases),'removed':sorted(old_aliases-new_aliases)} if new_aliases is not None else None,
            'mappings':local_mappings,'imported_definitions':matched_imports,'facets':facets.get(cid) if isinstance(facets,dict) else None,
            'exports':{'formal_class_present':formal_present,'formal_definitions':[str(o) for o in domain_graph.objects(class_node,SKOS.definition)] if domain_graph is not None and class_node else [],'literature_concept_iris':literature_nodes,'formal_href':'snapshots/'+run_id+'/ontology.ttl.html','claims_href':'snapshots/'+run_id+'/domain_layer.ttl.html'},
            'integration':{'run':integration_id,'source_run_recorded':integration_applies,'merged_class_present':(class_node,RDF.type,OWL.Class) in merged if merged is not None and class_node else None,'mappings':connected,'bridges':bridge_groups},
            'artifact_links':{name:'snapshots/'+run_id+'/'+name+'.html#'+quote(cid,safe='') for name in ['normalized/concepts.json','ontology/classes.json','ontology/enriched.json','ontology/mappings.json']}})
    # Only public scientific subsets are exported as browseable source snapshots.
    artifacts={prefix+'normalized/concepts.json':concepts,prefix+'ontology/classes.json':classes,prefix+'ontology/enriched.json':enriched,prefix+'ontology/mappings.json':mappings}
    if lineage_exists:artifacts[prefix+'normalized/concept_lineage.json']=[public_record(r,['paper','original_id','original_label','canonical_id','canonical_label']) for r in lineage if isinstance(r,dict)] if isinstance(lineage,list) else {'status':'unrecognized saved lineage shape'}
    for key,p in papers.items():artifacts[prefix+'papers/'+key+'.json']=public_record(p,['key','title','doi','year','authors','parse_stats','concepts','relations','causal','measurements','figures','verification'])
    fingerprints=snapshot.fingerprints()
    return {'run':run_id,'paper_count':len(papers),'integration':integration_id,'observed_at':datetime.now(timezone.utc).isoformat(),'status':'saved-snapshot','fingerprints':fingerprints,
            'default_concept':next((c['id'] for c in traces if c['label'].casefold()=='tunnel oxide layer'),traces[0]['id']),
            'concepts':traces,'artifacts':artifacts,'rdf_sources':{prefix+n:snapshot.cache[prefix+n][1].decode('utf-8-sig') for n in ('ontology.ttl','domain_layer.ttl') if prefix+n in snapshot.cache}}


def export_traces(outputs, destination, run_id, integration_id=None):
    """Write a separate observation package and escaped, whitelisted artifact previews."""
    package=build_traces(outputs,run_id,integration_id);destination=Path(destination)
    def write(relative,text):
        path=(destination/relative).resolve()
        if not path.is_relative_to(destination.resolve()):raise ValueError('Unsafe trace destination')
        path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(text,encoding='utf-8');temporary.replace(path)
    def preview(relative,data):
        title=html.escape(relative);body='<!doctype html><!-- Author: Brent Thompson <brent.thompson@ucf.edu>; Summary: escaped read-only scientific artifact snapshot. --><meta charset="utf-8"><title>'+title+'</title><style>body{font:15px/1.6 system-ui;max-width:1000px;margin:30px auto;padding:15px;color:#20303c}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f8;padding:15px}section{border-top:1px solid #ccd6dc;padding:12px 0}a{color:#175b8b}h2{scroll-margin-top:20px}</style><a href="'+('../'*len(Path(relative).parts))+'index.html">Back to the journey</a><h1>'+title+'</h1><p>Saved scientific fields only · snapshot '+html.escape(package['observed_at'])+'. Raw calls, credentials, runtime configuration and local PDF paths are excluded.</p>'
        if isinstance(data,dict) and 'concepts' in data:
            body+='<h2>'+html.escape(str(data.get('title','Paper record')))+'</h2>'
            doi=data.get('doi')
            if isinstance(doi,str) and doi.startswith('10.'):body+='<a rel="noopener" target="_blank" href="https://doi.org/'+quote(doi,safe='/')+'">Open publication by DOI</a>'
            for concept in data.get('concepts',[]):
                if not isinstance(concept,dict):continue
                body+='<section><h2 id="'+html.escape(str(concept.get('id','')),quote=True)+'">'+html.escape(str(concept.get('label','Concept')))+'</h2><pre>'+html.escape(json.dumps(concept,indent=2,ensure_ascii=False))+'</pre></section>'
            for figure in data.get('figures',[]):
                if not isinstance(figure,dict):continue
                body+='<section><h2 id="figure-'+html.escape(str(figure.get('id','')),quote=True)+'">'+html.escape(str(figure.get('label',figure.get('id','Figure'))))+'</h2><p>Caption record; page '+html.escape(str(figure.get('page','unavailable')))+'. The image is not part of this documentation snapshot.</p><p>'+html.escape(str(figure.get('caption','')))+ '</p></section>'
        if isinstance(data,list) and all(isinstance(row,dict) and isinstance(row.get('id'),str) for row in data):
            grouped={};names={c['id']:c['label'] for c in package['concepts']}
            for row in data:grouped.setdefault(row['id'],[]).append(row)
            for key,rows in grouped.items():
                body+='<section><h2 id="'+html.escape(key,quote=True)+'">'+html.escape(names.get(key,rows[0].get('label',key)))+'</h2><pre>'+html.escape(json.dumps(rows[0] if len(rows)==1 else rows,indent=2,ensure_ascii=False))+'</pre></section>'
        else:body+='<h2>Saved artifact fields</h2><pre>'+html.escape(data if isinstance(data,str) else json.dumps(data,indent=2,ensure_ascii=False))+'</pre>'
        write('snapshots/'+relative+'.html',body)
    for relative,data in package.pop('artifacts').items():preview(relative,data)
    for relative,data in package.pop('rdf_sources').items():preview(relative,data)
    summaries=[]
    for trace in package.pop('concepts'):
        relative='traces/'+run_id+'/'+identifier(trace['id'])+'.json'
        write(relative,json.dumps(trace,ensure_ascii=False));summaries.append({'id':trace['id'],'label':trace['label'],'path':relative})
    package['concepts']=summaries
    write('concept-journey.json',json.dumps(package,indent=2,ensure_ascii=False))
    return {'trace_concepts':len(summaries),'trace_run':run_id}
