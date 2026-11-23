/* Research navigation and browser-local views. Never store chat inputs or credentials. */
(() => {
  const fields = ['preset','depth','relation_filter','domain_filter','focus','graph_size','literature','hierarchy','mappings','disjoint'];
  let history = [], index = -1, restoring = false, hidden = [], hiddenUndo = [], selected = '';
  let scope = '';
  const input = id => document.getElementById('exploration-' + id);
  const scopeKey = () => ['experiment','existing','exploration-source','exploration-ontology'].map(id=>document.getElementById(id)?.value || '').join('|');
  const message = text => {
    let status = document.getElementById('workspace-feedback');
    if (!status) { status=document.createElement('p'); status.id='workspace-feedback'; status.setAttribute('role','status'); document.querySelector('.workspace-toolbar')?.after(status); }
    status.textContent=text;
  };
  const read = () => Object.fromEntries(fields.map(id=>[id,input(id)?.type==='checkbox' ? input(id).checked : input(id)?.value || '']));
  const storageKey = () => 'dpv-research-views:' + scopeKey();
  function refreshSaved() {
    try {
      const select=input('saved_view'); if (!select) return;
      const values=JSON.parse(localStorage.getItem(storageKey()) || '{}');
      const prior=select.value;
      select.replaceChildren(new Option('Choose a saved view',''), ...Object.keys(values).sort().map(name=>new Option(name,name)));
      if (Object.hasOwn(values,prior)) select.value=prior;
    } catch (_) {}
  }
  document.addEventListener('toggle',e=>{if(e.target.tagName==='DETAILS' && e.target.open) refreshSaved();},true);
  const record = () => {
    if (restoring) return;
    const nextScope=scopeKey();
    if (scope!==nextScope) { scope=nextScope; history=[]; index=-1; hidden=[]; hiddenUndo=[]; selected=''; }
    const view=read();
    if (JSON.stringify(history[index])===JSON.stringify(view)) return;
    history=history.slice(0,index+1); history.push(view);
    if (history.length>50) history.shift();
    index=history.length-1;
  };
  function apply(view) {
    if (!view || typeof view!=='object') return;
    restoring=true;
    fields.forEach(id=>{
      const el=input(id); const value=view[id];
      if (!el || value===undefined || !['string','boolean'].includes(typeof value)) return;
      if (el.type==='checkbox') el.checked=Boolean(value);
      else {
        if (el.tagName==='SELECT' && value && !Array.from(el.options).some(o=>o.value===value)) {
          if (id!=='focus') return;
          const opt=document.createElement('option'); opt.value=value; opt.textContent=value; el.append(opt);
        }
        el.value=value;
      }
      el.dispatchEvent(new Event('change',{bubbles:true}));
    });
    setTimeout(()=>{restoring=false;},300);
  }
  document.addEventListener('change', e=>{
    if (fields.some(id=>e.target.id==='exploration-'+id)) record();
  });
  document.addEventListener('click', async e=>{
    const route=e.target.closest('.research-route');
    if (route) {
      document.querySelector('a[data-value="'+route.dataset.page+'"]')?.click();
      if (route.dataset.explorationTab) document.querySelector('#exploration-tabs a[data-value="'+route.dataset.explorationTab+'"]')?.click();
      return;
    }
    const focus=e.target.closest('.inspector-focus');
    if (focus && window.Shiny) { Shiny.setInputValue('exploration-workspace_focus',{iri:focus.dataset.iri,depth:focus.dataset.depth || '1'},{priority:'event'}); return; }
    const copy=e.target.closest('.copy-iri');
    if (copy) { try { await navigator.clipboard.writeText(copy.dataset.iri); message('Ontology identifier copied.'); } catch (_) { message('Select the identifier in the inspector to copy it.'); } return; }
    const artifact=e.target.closest('.artifact-recommendation');
    if (artifact && window.Shiny) { Shiny.setInputValue('inventory-recommended',artifact.dataset.path,{priority:'event'}); return; }
    const edge=e.target.closest('.workspace-edge');
    if (edge && window.Shiny) { Shiny.setInputValue('exploration-edge',{id:edge.dataset.edge,token:edge.dataset.token,at:Date.now()},{priority:'event'}); return; }
    const action=e.target.closest('.workspace-action')?.dataset.action;
    if (!action) return;
    const box=document.querySelector('#exploration-vowl')?.closest('.vowl-container');
    const payload=box ? JSON.parse(box.querySelector('.vowl-data').textContent) : null;
    record();
    if (['fit','freeze','pin','export'].includes(action)) {
      if (!payload) { message('Wait for the graph to finish loading.'); return; }
      box.querySelector('iframe').contentWindow.postMessage({type:'dpv-vowl-action',action,token:payload._dpv.token},location.origin);
      if (action==='freeze') { const button=e.target.closest('button'); button.textContent=button.textContent==='Freeze layout' ? 'Resume layout' : 'Freeze layout'; }
    }
    if (action==='back' && index>0) apply(history[--index]);
    if (action==='forward' && index<history.length-1) apply(history[++index]);
    if (action==='hide' && selected) { hiddenUndo.push([...hidden]); hidden=[...new Set([...hidden,selected])]; }
    if (action==='undo' && hiddenUndo.length) hidden=hiddenUndo.pop();
    if (['hide','undo'].includes(action) && window.Shiny) Shiny.setInputValue('exploration-hidden_nodes',hidden,{priority:'event'});
    if (action==='reset') {
      hidden=[]; hiddenUndo=[];
      window.Shiny?.setInputValue('exploration-hidden_nodes',[],{priority:'event'});
      apply({preset:'overview',depth:'0',focus:'',relation_filter:'',domain_filter:'',graph_size:'160',literature:true,hierarchy:false,mappings:true,disjoint:false});
    }
    if (action==='save') {
      const name=input('view_name')?.value.trim();
      if (!name || name.length>80 || !payload) { message('Enter a view name of 1–80 characters after the graph loads.'); return; }
      try {
        const views=JSON.parse(localStorage.getItem(storageKey()) || '{}');
        if (Object.keys(views).length>=30 && !Object.hasOwn(views,name)) { message('This browser already has 30 views for this scope. Reuse a view name to replace it.'); return; }
        Object.defineProperty(views,name,{value:{version:1,scope:scopeKey(),sourceSignature:payload._dpv.source_signature,view:read(),hidden},enumerable:true,configurable:true,writable:true});
        localStorage.setItem(storageKey(),JSON.stringify(views)); refreshSaved(); message('Named view saved for this source version in this browser.'); }
      catch (_) { message('Browser storage is unavailable. Use the JSON export to retain the graph.'); }
    }
    if (action==='restore') {
      try {
        const views=JSON.parse(localStorage.getItem(storageKey()) || '{}');
        const value=views[input('saved_view')?.value];
        if (value?.scope!==scopeKey() || value.version!==1) { message('No saved view for this source scope.'); return; }
        if (!payload || value.sourceSignature!==payload._dpv.source_signature) { message('Source files changed since this view was saved. Inspect the current graph and save a new view.'); return; }
        hidden=Array.isArray(value.hidden) ? value.hidden.filter(v=>typeof v==='string').slice(0,1000) : [];
        window.Shiny?.setInputValue('exploration-hidden_nodes',hidden,{priority:'event'});
        apply(value.view); message('Saved view restored against the currently authorized source version.');
      } catch (_) { message('Saved view could not be read.'); }
    }
  });
  window.addEventListener('message', e=>{
    if (e.origin!==location.origin || e.data?.type!=='dpv-vowl-inspect') return;
    const frame=document.getElementById('exploration-vowl');
    const box=frame?.closest('.vowl-container');
    if (frame?.contentWindow!==e.source || !box) return;
    const payload=JSON.parse(box.querySelector('.vowl-data').textContent);
    if (payload._dpv.token!==e.data.token || !payload.classAttribute.some(n=>n.iri===e.data.iri)) return;
    selected=e.data.iri;
    if (window.Shiny) Shiny.setInputValue('exploration-selection',{iri:selected,token:e.data.token,at:Date.now()},{priority:'event'});
  });
  const navigation = () => {
    const list=document.querySelector('.nav-pills');
    if (!list || document.getElementById('workflow-navigation-toggle')) return;
    const links=Array.from(list.querySelectorAll('a[data-value]')).filter(a=>['ingest','parse','extract','normalize','ontology','enrich','interop','integrate','reports'].includes(a.dataset.value));
    if (!links.length) return;
    const button=document.createElement('button'); button.id='workflow-navigation-toggle'; button.className='btn workflow-toggle';
    button.textContent='How results were produced'; button.setAttribute('aria-expanded','false');
    links[0].parentElement.before(button);
    const show=value=>{button.setAttribute('aria-expanded',String(value)); links.forEach(a=>a.parentElement.hidden=!value);};
    show(links.some(a=>a.classList.contains('active')));
    button.addEventListener('click',()=>show(button.getAttribute('aria-expanded')!=='true'));
    document.addEventListener('shown.bs.tab',()=>{if(links.some(a=>a.classList.contains('active'))) show(true);});
  };
  document.addEventListener('DOMContentLoaded',()=>{
    navigation(); new MutationObserver(navigation).observe(document.body,{childList:true,subtree:true});
    if (window.jQuery) jQuery(document).on('shiny:inputchanged',event=>{
      if (fields.some(id=>event.name==='exploration-'+id)) record();
    });
  });
})();
