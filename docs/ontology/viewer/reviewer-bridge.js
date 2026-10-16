/* Author: Brent Thompson <brent.thompson@ucf.edu>
Summary: Connect the standalone reviewer to WebVOWL with coalesced graph framing.
The pipeline dashboard's bridge and vendor code remain unchanged. */
window.addEventListener('load',()=>{
 const app=webvowl.app();let provenance={},fitTimer,loadedPayload;
 function fitVisibleNodes(payload){
  const ids=new Set(payload.class.map(n=>String(n.id))),svg=document.querySelector('svg.vowlGraph');
  if(!svg)return;const points=[...svg.querySelectorAll('g.node')].filter(n=>ids.has(n.id)).map(n=>{
   const matrix=n.transform.baseVal.consolidate()?.matrix;return matrix?[matrix.e,matrix.f]:null;
  }).filter(p=>p&&p.every(Number.isFinite));
  if(!points.length)return;const width=svg.getBoundingClientRect().width,height=svg.getBoundingClientRect().height;
  if(width<=0||height<=0)return;
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),left=Math.min(...xs)-80,right=Math.max(...xs)+80,top=Math.min(...ys)-80,bottom=Math.max(...ys)+80;
  const scale=Math.min((width-32)/(right-left),(height-32)/(bottom-top),1.2),translation=[(width-scale*(left+right))/2,(height-scale*(top+bottom))/2];
  if(!Number.isFinite(scale)||scale<=0)return;
  const graph=app.getGraph();graph.setZoom(scale);graph.setTranslation(translation);
  d3.select(svg).select('g').interrupt().attr('transform','translate('+translation+')scale('+scale+')');
  // Synchronize the native D3 zoom handler with its public imported zoom/translation settings.
  // A zero-delta event leaves the fitted transform unchanged and keeps subsequent controls consistent.
  const rect=svg.getBoundingClientRect();svg.dispatchEvent(new WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:0,clientX:rect.left+width/2,clientY:rect.top+height/2,view:window}));
 }
 location.hash='dpv-empty';app.initialize();
 // Keep WebVOWL's Center/Reset requests on the same visible-node bounds as initial framing.
 app.getGraph().forceRelocationEvent=()=>{if(loadedPayload)fitVisibleNodes(loadedPayload);};
 app.getOptions().selectionModules().push({
  handle(element){
   if(d3.event?.defaultPrevented||!element||typeof element.iri!=='function')return;
   const id=typeof element.id==='function'?element.id():'';
   parent.postMessage(provenance.edges?.[id]?{type:'dpv-vowl-select',edgeId:id,token:provenance.token}:{type:'dpv-vowl-select',iri:element.iri()},location.origin);
  },reset(){}
 });
 const ready=setInterval(()=>{
  if(app.getOptions()?.loadingModule()?.successfullyLoadedOntology())parent.postMessage({type:'dpv-vowl-ready'},location.origin);
 },500);
 setInterval(()=>{
  if(provenance.token)parent.postMessage({type:'dpv-vowl-stats',token:provenance.token,nodes:document.querySelectorAll('g.node').length,edges:document.querySelectorAll('g.label').length},location.origin);
 },1500);
 window.addEventListener('message',event=>{
  if(event.origin!==location.origin||event.source!==parent||event.data?.type!=='dpv-vowl-data')return;
  const payload=event.data.payload;
  if(!payload||!Array.isArray(payload.class)||!payload._dpv?.token)return;
  clearInterval(ready);clearTimeout(fitTimer);provenance=payload._dpv;loadedPayload=payload;
  try{
   // Suppress WebVOWL's separate automatic centering pass; it can overlap the reviewer fit.
   const display={...payload,settings:{...payload.settings,global:{...payload.settings?.global,zoom:1,translation:[0,0]}}};
   app.getOptions().ontologyMenu().getLoadingFunction()(JSON.stringify(display),'UCF-DPV');
   const token=provenance.token;
   // Bounds come only from actual payload nodes, excluding off-screen editor/halo geometry.
   fitTimer=setTimeout(()=>{
    if(provenance.token===token)fitVisibleNodes(payload);
   },1500);
  }catch(error){document.body.textContent='Unable to load this reviewer graph: '+error.message;}
 });
});
