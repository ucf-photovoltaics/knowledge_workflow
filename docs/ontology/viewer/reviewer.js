/* Author: Brent Thompson <brent.thompson@ucf.edu>
Summary: Read-only stage, definition, contract and source navigation over exported RDF records. */
const $=id=>document.getElementById(id),KW='https://w3id.org/ucf-dpv/knowledge-workflow/codebase#';
let records={},stages={},stage='normalize',current=null,selected=null,revision=0,history=[];
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const readable=value=>value.replace(/([a-z])([A-Z])/g,'$1 $2').replace(/_/g,' ');
function recordLink(iri,label){const b=el('button',label||records[iri]?.label||iri,'record-link');b.onclick=()=>selectRecord(iri,true);return b;}
function callableRecord(identity){const split=identity.indexOf(':');return Object.values(records).find(r=>r.fields.sourcePath?.[0]===identity.slice(0,split)&&r.label===identity.slice(split+1));}
function section(title,open=false){const d=el('details');d.open=open;d.append(el('summary',title));$('inspector').append(d);return d;}
function field(parent,name,value){if(value===undefined||value===null||value==='')return;const d=el('div',undefined,'field');d.append(el('strong',readable(name)),el('div',String(value)));parent.append(d);}
function inspect(iri,push=true){
 const record=records[iri];if(!record)return;
 if(push&&selected&&selected!==iri)history.push(selected);selected=iri;
 const panel=$('inspector');panel.replaceChildren();
 const graphButton=el('button','↑ Back to graph','back');graphButton.onclick=()=>$('graph-title').scrollIntoView({behavior:'smooth',block:'start'});panel.append(graphButton);
 if(history.length){const b=el('button','← Previous record','back');b.onclick=()=>inspect(history.pop(),false);panel.append(b);}
 panel.append(el('div',record.types.map(readable).join(' · '),'types'),el('h2',record.label));
 const status=record.fields.coverageStatus?.[0]||record.definition_status;
 if(status)panel.append(el('span',status,'badge'));
 panel.append(el('h3','Definition · skos:definition'),el('div',record.definition||'An authoritative definition is unavailable in this loaded snapshot.','definition'));
 for(const note of record.notes||[])panel.append(el('p',note,'warning'));
 if(record.definition_status?.startsWith('structural-only'))panel.append(el('p','The identity and source are documented. This callable’s behavioral contract still needs source review before direct use.','warning'));
 if(record.source_link?.startsWith('source/')){const a=el('a',record.resource_text?'Open worked example':'Open source at line '+(record.fields.lineStart?.[0]||'1'));a.href=record.source_link;a.target='_blank';a.rel='noopener';panel.append(a);}
 if(record.resource_text){const d=section('Worked task instructions',true);d.append(el('pre',record.resource_text));}
 if(record.fields.signature)panel.append(el('pre',record.label+'('+record.fields.signature[0]+')\nReturns: '+(record.fields.returnTypeExpression?.[0]||'Not annotated')));
 const implementations=record.links.filter(link=>link.predicate===KW+'operationImplementation');
 if(implementations.length){const d=section('Implementation function',true);for(const link of implementations)d.append(recordLink(link.target));}
 const argumentLinks=record.links.filter(link=>link.predicate===KW+'hasArgument');
 if(argumentLinks.length){const d=section('Arguments · '+argumentLinks.length,true);for(const link of argumentLinks){const a=records[link.target],p=el('div',undefined,'field');p.append(recordLink(link.target),el('div',(a.fields.typeExpression?.[0]||'Unannotated')+' · '+(a.fields.argumentKind?.[0]||'')+' · '+(a.fields.argumentRequired?.[0]==='true'?'Required':'Implicit, optional or variadic')+(a.fields.defaultExpression?' · Default '+a.fields.defaultExpression[0]:''),'muted'));d.append(p);}}
 const contract=record.contract;
 if(contract){
  field(panel,'Research task',contract.task);
  if(contract.input_contract){const d=section('Input & return contract',true);d.append(el('p',contract.input_contract.description));d.append(el('pre',JSON.stringify(contract.input_contract.required_inputs||contract.input_contract.required_paper_fields,null,2)));field(d,'Initialization',contract.input_contract.initialization);field(d,'Side effects',contract.input_contract.mutation);field(d,'Returns',contract.input_contract.returns.join('\n'));}
  const worked=record.links.filter(link=>link.predicate===KW+'usesResource'&&records[link.target]?.resource_text);
  if(worked.length){const d=section('Worked example',true);for(const link of worked)d.append(recordLink(link.target,'Read the '+record.label+' worked example'));}
  const bindings=section('Data bindings · '+contract.bindings.length,true);
  for(const b of contract.bindings){const d=el('div',undefined,'binding');d.append(el('strong',(b.direction==='input'?'Input · ':'Output · ')+b.artifact),el('div',b.selector+' ↔ '+b.argument));const target=callableRecord(b.function);
   if(b.modes)field(d,'Execution mode',b.modes.join(', '));
   if(target)d.append(recordLink(target.iri,b.function.split(':').slice(1).join(':')));d.append(el('p',b.transformation));bindings.append(d);}
  if(contract.algorithm.length){const d=section('Operations · source-reviewed order');for(const op of contract.algorithm){const p=el('div',undefined,'binding');p.append(el('strong',op.order+'. '+op.label),el('p',op.definition));const target=callableRecord(op.function);if(target)p.append(recordLink(target.iri,op.function.split(':').slice(1).join(':')));d.append(p);}}
  const checks=section('Checks & review · '+contract.checks.length);
  checks.append(el('p','These are documentation-layer checks. They do not change pipeline acceptance rules.','muted'));
  for(const c of contract.checks){const p=el('div',undefined,'check');p.append(el('strong',c.id+' · '+c.severity),el('div',c.instruction||((c.pattern||'Saved results')+' · '+readable(c.kind))),el('div','When: '+(c.phases||['after']).join(' / ')+(c.modes?' · '+c.modes.join(', '):''),'muted'));checks.append(p);}
  const recovery=section('Recovery & downstream impact');recovery.append(el('p',contract.recovery),el('p',contract.limitation,'warning'));
  for(const link of record.links.filter(l=>l.predicate===KW+'invalidatesStep'))recovery.append(el('div','Recheck after a rerun: '),recordLink(link.target));
  const contractStage=record.iri.split('/').pop();
  const agent=section('Agent entry points');agent.append(el('pre','python scripts/ontology_agent.py guide --step '+contractStage+'\npython scripts/ontology_agent.py assess --run RUN_ID --step '+contractStage+' --phase before\npython scripts/ontology_agent.py assess --run RUN_ID --step '+contractStage+' --phase after'));
 }
 const links=section('Connected records · '+(record.links.length+(record.incoming?.length||0)));
 for(const link of record.links){const p=el('div',undefined,'field');p.append(el('div',link.label,'link-label'),recordLink(link.target));links.append(p);}
 for(const link of record.incoming||[]){const p=el('div',undefined,'field');p.append(el('div',link.label,'link-label'),recordLink(link.source));links.append(p);}
 const metadata=section('RDF identity & source metadata');field(metadata,'IRI',record.iri);
 for(const [key,values] of Object.entries(record.fields))field(metadata,key,values.join('\n'));
}
function localGraph(iri){
 const record=records[iri],edges=[],nodes=new Set([iri]);
 for(const link of record.links.slice(0,18)){nodes.add(link.target);edges.push({s:iri,p:link.predicate,o:link.target,label:link.label});}
 for(const other of Object.values(records)){if(nodes.size>=26)break;const link=other.links.find(l=>l.target===iri);if(link){nodes.add(other.iri);edges.push({s:other.iri,p:link.predicate,o:iri,label:link.label});}}
 const ids=new Map([...nodes].map((id,i)=>[id,String(i+1)]));
 return {header:{title:{en:record.label+' · Neighborhood'},languages:['en']},namespace:[],class:[...nodes].map(id=>({id:ids.get(id),type:'owl:Class'})),classAttribute:[...nodes].map(id=>({id:ids.get(id),iri:id,label:{en:records[id]?.label||id},comment:{en:records[id]?.definition||''}})),property:edges.map((e,i)=>({id:'p'+i,type:'owl:ObjectProperty'})),propertyAttribute:edges.map((e,i)=>({id:'p'+i,iri:e.p,domain:ids.get(e.s),range:ids.get(e.o),label:{en:e.label}})),_dpv:{token:'lookup-'+(++revision),edges:Object.fromEntries(edges.map((e,i)=>['p'+i,{subject:e.s,predicate:e.p,object:e.o,relation:e.label}]))}};
}
async function loadView(){
 const version=++revision,mode=$('view').value;let payload;current=null;
 paintStages();$('code-search').hidden=['journey','trace'].includes(mode);
 if(['journey','trace'].includes(mode)){current=null;if($('viewer').getAttribute('src')!=='about:blank')$('viewer').src='about:blank';await DPVJourney.render(mode);return;}
 $('workspace').classList.remove('journey-mode');$('journey').hidden=true;$('viewer').hidden=false;
 // A fresh embedded graph isolates WebVOWL's mutable zoom/layout state between focused views.
 $('viewer').getBoundingClientRect();
 $('viewer').src='assets/index.html?reviewer=6&view='+version;
 $('projection-note').textContent='Named records are projected as WebVOWL nodes. The inspector retains their original RDF types.';
 $('status').textContent='Loading focused view…';
 if(mode==='lookup'){if(!selected)selected=KW+'step/'+stage;payload=localGraph(selected);}else{
  const name=mode==='workflow'?'workflow-overview.json':mode==='schema'?'ontology-schema.json':'stage-'+stage+'-'+mode+'.json';
  const response=await fetch(name,{cache:'no-store'});if(!response.ok)throw new Error('View file unavailable');payload=await response.json();if(version!==revision)return;
 }
 current=payload;$('graph-title').textContent=payload.header.title.en;
 $('graph-hint').textContent=mode==='lookup'?'A bounded neighborhood keeps the graph readable. Follow connected records to continue.':mode==='workflow'?'Conceptual dependencies. CLI extraction combines ingestion, parsing and extraction; use mode-specific recipes to execute.':'Select a node or relationship. Definitions, data bindings and source links appear in the record inspector.';
 $('status').textContent=payload.class.length+' nodes · '+payload.property.length+' relationships';
 $('viewer').contentWindow.postMessage({type:'dpv-vowl-data',payload},location.origin);
}
async function selectRecord(iri,focus=false){
 if(!records[iri])return;inspect(iri);$('results').hidden=true;
 if(iri.startsWith(KW+'step/')){stage=iri.split('/').pop();if(['journey','trace'].includes($('view').value))$('view').value='code';paintStages();if(!['workflow','schema'].includes($('view').value))await loadView();}
 else if(focus){$('view').value='lookup';await loadView();}
 if(window.matchMedia('(max-width:900px)').matches)$('inspector').scrollIntoView({behavior:'smooth',block:'start'});
}
function paintStages(){
 $('stages').replaceChildren();
 for(const [id,label] of Object.entries(stages)){const b=el('button',label);b.setAttribute('aria-current',String(id===stage&&!['journey','trace'].includes($('view').value)));b.onclick=()=>{stage=id;paintStages();if(['workflow','schema','lookup','journey','trace'].includes($('view').value))$('view').value='data';inspect(KW+'step/'+id);loadView().catch(showError);};$('stages').append(b);}
}
function showError(error){$('status').textContent='Unable to display view: '+error.message;}
$('view').onchange=()=>loadView().catch(showError);
$('show-record').onclick=()=>$('inspector').scrollIntoView({behavior:'smooth',block:'start'});
$('search').oninput=()=>{
 const query=$('search').value.trim().toLowerCase();$('results').replaceChildren();$('results').hidden=!query;if(!query)return;
 const matches=Object.values(records).filter(r=>(r.label+' '+r.iri+' '+(r.fields.sourcePath||[]).join(' ')+' '+(r.fields.artifactPattern||[]).join(' ')).toLowerCase().includes(query)).sort((a,b)=>Number(b.types.includes('CodeUnitSpecification'))-Number(a.types.includes('CodeUnitSpecification'))).slice(0,25);
 for(const match of matches){const b=el('button');b.append(el('strong',match.label),el('div',(match.fields.sourcePath?.[0]||match.types.map(readable).join(' · ')),'muted'));b.onclick=()=>selectRecord(match.iri,true).catch(showError);$('results').append(b);}
 if(!matches.length)$('results').append(el('p','No matching record. Try a function name, source path, artifact or stage.'));
};
window.addEventListener('message',event=>{
 if(event.origin!==location.origin||event.source!==$('viewer').contentWindow)return;const message=event.data;
 if(message?.type==='dpv-vowl-ready'&&current)$('viewer').contentWindow.postMessage({type:'dpv-vowl-data',payload:current},location.origin);
 if(message?.type==='dpv-vowl-stats'&&current&&message.token===current._dpv.token&&message.nodes>0)$('status').textContent=current.class.length+' source nodes · '+current.property.length+' relationships · ready';
 if(message?.type==='dpv-vowl-select'){
  if(message.iri)selectRecord(message.iri,false).catch(showError);
  else if(message.token===current?._dpv.token&&current._dpv.edges[message.edgeId]){
   const edge=current._dpv.edges[message.edgeId],panel=$('inspector');panel.replaceChildren(el('div','Relationship','types'),el('h2',edge.relation));
   const property=records[edge.predicate];panel.append(el('h3','Definition · skos:definition'),el('div',property?.definition||'Relationship shown from the source RDF.','definition'),el('h3','From'),recordLink(edge.subject),el('h3','To'),recordLink(edge.object));
  }
 }
});
fetch('records.json',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error('Record index unavailable');return response.json();}).then(data=>{records=data.records;stages=data.stages;DPVJourney.init({el,field,section,records,stages,KW,recordLink,callableRecord,showError,openTrace(){ $('view').value='trace';loadView().catch(showError);},openStage(id){stage=id;$('view').value='code';paintStages();inspect(KW+'step/'+id);loadView().catch(showError);}});paintStages();return loadView();}).catch(showError);
