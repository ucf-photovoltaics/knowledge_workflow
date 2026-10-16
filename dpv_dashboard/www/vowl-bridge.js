/*
Author: Brent Thompson <brent.thompson@ucf.edu>
Summary: vowl-bridge support for Knowledge Workflow; retain the existing operational notes below.
*/
// Loaded by the separately built, unmodified upstream WebVOWL application.
window.addEventListener('load', () => {
  const app = webvowl.app();
  let provenance = {};
  setInterval(() => {
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
        parent.postMessage({type: 'dpv-vowl-select', iri: element.iri()}, location.origin);
      }
    },
    reset() {}
  });
  const ready = setInterval(() => {
    if (app.getOptions()?.loadingModule()?.successfullyLoadedOntology()) {
      parent.postMessage({type: 'dpv-vowl-ready'}, location.origin);
    }
  }, 500);
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== parent || event.data?.type !== 'dpv-vowl-data') return;
    clearInterval(ready);
    provenance = event.data.payload._dpv || {};
    try {
      app.getOptions().ontologyMenu().getLoadingFunction()(JSON.stringify(event.data.payload), 'UCF-DPV');
      // Fit once after the force layout has settled inside the embedded viewport.
      setTimeout(() => app.getGraph().forceRelocationEvent(true), 1500);
    } catch (error) {
      document.body.textContent = 'Unable to load the WebVOWL graph: ' + error.message;
    }
  });
});
