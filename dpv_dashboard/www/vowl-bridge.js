/*
Author: Brent Thompson <brent.thompson@ucf.edu>
Summary: vowl-bridge support for Knowledge Workflow; retain the existing operational notes below.
*/
// Loaded by the separately built, unmodified upstream WebVOWL application.
window.addEventListener('load', () => {
  const app = webvowl.app();
  let provenance = {};
  let selectedIri = '';
  const visibleNodes = () => Array.from(document.querySelectorAll('g.node')).map(node => d3.select(node).datum())
    .filter(node => node && typeof node.iri === 'function');
  const snapshot = () => {
    if (!provenance.scope) return;
    const nodes = visibleNodes();
    const positions = Object.fromEntries(nodes.slice(0, 1600).filter(n => typeof n.iri === 'function' && Number.isFinite(n.x) && Number.isFinite(n.y))
      .map(n => [n.iri(), {pos:[n.x,n.y], pinned:n.pinned()}]));
    try { sessionStorage.setItem('dpv-layout:' + provenance.scope, JSON.stringify(positions)); } catch (_) {}
  };
  setInterval(() => {
    snapshot();
    if (provenance.scope) document.querySelectorAll('[id^="killFilterMessages_"]').forEach(button => button.click());
    if (provenance.token) parent.postMessage({type:'dpv-vowl-stats', token:provenance.token,
      nodes:document.querySelectorAll('g.node').length, edges:document.querySelectorAll('g.label').length}, location.origin);
  }, 1500);
  location.hash = 'dpv-empty';
  app.initialize();
  app.getOptions().selectionModules().push({
    handle(element) {
      if (d3.event && d3.event.defaultPrevented) return;
      if (element && typeof element.iri === 'function') {
        const id = typeof element.id === 'function' ? element.id() : '';
        if (provenance.edges?.[id]) {
          parent.postMessage({type: 'dpv-vowl-select', edgeId:id, token:provenance.token}, location.origin);
          return;
        }
      }
    },
    reset() {}
  });
  document.addEventListener('click', event => {
    const node = event.target.closest?.('g.node');
    if (!node) return;
    const element = d3.select(node).datum();
    if (element && typeof element.iri === 'function') {
      selectedIri = element.iri();
      parent.postMessage({type:'dpv-vowl-inspect', iri:selectedIri, token:provenance.token}, location.origin);
    }
  }, true);
  document.addEventListener('dblclick', event => {
    const node = event.target.closest?.('g.node');
    if (!node) return;
    const element = d3.select(node).datum();
    if (element && typeof element.iri === 'function') {
      parent.postMessage({type: 'dpv-vowl-select', iri: element.iri(), token:provenance.token}, location.origin);
    }
  }, true);
  const ready = setInterval(() => {
    if (app.getOptions()?.loadingModule()?.successfullyLoadedOntology()) {
      parent.postMessage({type: 'dpv-vowl-ready'}, location.origin);
    }
  }, 500);
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== parent) return;
    if (event.data?.type === 'dpv-vowl-action' && event.data.token === provenance.token) {
      const graph = app.getGraph();
      if (event.data.action === 'fit') graph.forceRelocationEvent(true);
      if (event.data.action === 'freeze') graph.paused(!graph.paused());
      if (event.data.action === 'pin') {
        const node = visibleNodes().find(n => n.iri() === selectedIri);
        if (node) { if (node.pinned()) node.removePin(); else node.drawPin(); }
      }
      if (event.data.action === 'export') {
        const svg = document.querySelector('#canvasArea svg');
        if (svg) {
          const clone = svg.cloneNode(true);
          clone.setAttribute('xmlns','http://www.w3.org/2000/svg');
          const metadata = document.createElementNS('http://www.w3.org/2000/svg','metadata');
          metadata.textContent = JSON.stringify({scope:provenance.scope, view:provenance.view, coverage:provenance.coverage, subset:true,
            note:'Filtered graph subset. Recorded relationships do not establish causation.'});
          clone.prepend(metadata);
          const styles = document.createElementNS('http://www.w3.org/2000/svg','style');
          styles.textContent = Array.from(document.styleSheets).flatMap(sheet => { try { return Array.from(sheet.cssRules).map(r=>r.cssText); } catch (_) { return []; } }).join('\n');
          clone.prepend(styles);
          const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], {type:'image/svg+xml'}));
          const a = document.createElement('a'); a.href=url; a.download='research-graph-subset.svg'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
        }
      }
      snapshot();
      return;
    }
    if (event.data?.type !== 'dpv-vowl-data') return;
    clearInterval(ready);
    provenance = event.data.payload._dpv || {};
    if (provenance.scope && !document.getElementById('dpv-research-layout')) {
      const style=document.createElement('style'); style.id='dpv-research-layout';
      style.textContent='#detailsArea,#sidebarExpandButton{display:none!important}#canvasArea{width:100%!important}';
      document.head.append(style);
    }
    try {
      const saved = JSON.parse(sessionStorage.getItem('dpv-layout:' + provenance.scope) || '{}');
      event.data.payload.classAttribute.forEach(node => {
        const value = saved[node.iri];
        if (value && Array.isArray(value.pos) && value.pos.every(Number.isFinite)) { node.pos=value.pos; node.pinned=!!value.pinned; }
      });
      app.getOptions().ontologyMenu().getLoadingFunction()(JSON.stringify(event.data.payload), 'UCF-DPV');
      // Fit once after the force layout has settled inside the embedded viewport.
      setTimeout(() => { app.getGraph().updateCanvasContainerSize(); app.getGraph().forceRelocationEvent(true); }, 1500);
    } catch (error) {
      document.body.textContent = 'Unable to load the WebVOWL graph: ' + error.message;
    }
  });
});
