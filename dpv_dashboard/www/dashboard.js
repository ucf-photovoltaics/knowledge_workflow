/*
Author: Brent Thompson <brent.thompson@ucf.edu>
Summary: dashboard support for Knowledge Workflow; retain the existing operational notes below.
*/
// Same-origin iframe handshake. Payloads remain inert JSON until the viewer is ready.
(() => {
  document.addEventListener('input', event => {
    if (!event.target.matches('.figure-filter')) return;
    const query = event.target.value.toLocaleLowerCase();
    event.target.closest('details').querySelectorAll('.figure-card').forEach(card => {
      card.hidden = !card.textContent.toLocaleLowerCase().includes(query);
    });
  });
  document.addEventListener('mouseover', event => {
    const reference = event.target.closest('.research-reference');
    if (!reference) return;
    const preview = reference.querySelector('.research-popover');
    if (!preview) return;
    const rect = reference.getBoundingClientRect();
    preview.style.position = 'fixed';
    preview.style.left = Math.max(8, Math.min(rect.left, innerWidth - 410)) + 'px';
    preview.style.top = Math.max(8, Math.min(rect.bottom, innerHeight - 440)) + 'px';
    preview.querySelectorAll('img[data-preview-src]').forEach(img => {
      if (!img.getAttribute('src')) img.src = img.dataset.previewSrc;
    });
  });
  document.addEventListener('click', event => {
    const step = event.target.closest('.pipeline-step[data-stage]');
    if (step) {
      const stage = step.dataset.stage;
      const page = document.querySelector('a[data-value="' + stage + '"]');
      if (!page) return;
      page.click();
      requestAnimationFrame(() => {
        const pane = document.querySelector('.tab-pane.active[data-value="' + stage + '"]');
        if (!pane) return;
        const heading = pane.querySelector('h2');
        if (heading) { heading.tabIndex = -1; heading.focus({preventScroll:true}); }
        (pane.querySelector('.stage-heading') || pane).scrollIntoView({block:'start',behavior:'instant'});
      });
      return;
    }
    const report = event.target.closest('.report-open');
    if (report && window.Shiny) {
      Shiny.setInputValue(report.dataset.input, report.dataset.file, {priority:'event'});
      return;
    }
    const navigation = event.target.closest('.research-nav');
    if (navigation && window.Shiny) {
      event.preventDefault(); event.stopPropagation();
      Shiny.setInputValue('research_navigate', {root: navigation.dataset.root, canonical: navigation.dataset.canonical,
        paper: navigation.dataset.paper, tab: navigation.dataset.tab}, {priority: 'event'});
      return;
    }
    const link = event.target.closest('.research-open');
    if (!link || !window.Shiny) return;
    event.preventDefault();
    event.stopPropagation();
    Shiny.setInputValue('research_open', {root: link.dataset.root, paper: link.dataset.paper,
      canonical: link.dataset.canonical, figure: link.dataset.figure, claim:link.dataset.claim, gallery:link.dataset.gallery === 'true'}, {priority: 'event'});
  });
  function connect() {
    const exploration = document.querySelector('#exploration-tabs');
    const graphActive = exploration?.querySelector('[data-value="WebVOWL"].active');
    document.querySelectorAll('.graph-only-controls').forEach(control => { control.hidden = !graphActive; });
    const context = document.querySelector('.view-context');
    const readonly = context?.dataset.readonly === 'true';
    document.body.dataset.viewMode = readonly ? 'readonly' : 'project';
    document.querySelectorAll('#automatic,#resume,#cancel,[id$="-run"],[id$="-restart"],#project,#domain,#attempt').forEach(control => {
      control.disabled = readonly;
      control.title = readonly ? 'Viewing saved outputs. Select Dashboard project to enable execution and project configuration.' : '';
    });
    document.querySelectorAll('.vowl-container').forEach(box => {
      const frame = box.querySelector('iframe');
      if (!frame || frame.dataset.connected) return;
      frame.dataset.connected = 'true';
      box.querySelector('.viewer-fullscreen').addEventListener('click', () => {
        if (document.fullscreenElement) document.exitFullscreen(); else box.requestFullscreen();
      });
    });
  }
  document.addEventListener('shown.bs.tab', connect);
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || !['dpv-vowl-ready','dpv-vowl-select','dpv-vowl-stats'].includes(event.data?.type)) return;
    document.querySelectorAll('.vowl-container').forEach(box => {
      const frame = box.querySelector('iframe');
      if (frame.contentWindow !== event.source) return;
      if (event.data.type === 'dpv-vowl-stats') {
        const payload = JSON.parse(box.querySelector('.vowl-data').textContent);
        if (payload._dpv.token !== event.data.token) return;
        box.querySelector('.graph-rendered-status').textContent = `Graph supplied: ${payload.class.length} nodes / ${payload.property.length} relationships. WebVOWL currently renders ${event.data.nodes} nodes / ${event.data.edges} relationship labels. Its Filter controls can collapse or hide elements.`;
        return;
      }
      if (event.data.type === 'dpv-vowl-select') {
        if (typeof event.data.edgeId === 'string' && window.Shiny) {
          Shiny.setInputValue('exploration-edge', {id:event.data.edgeId, token:event.data.token}, {priority:'event'});
          return;
        }
        if (typeof event.data.iri === 'string' && window.Shiny) {
          Shiny.setInputValue('provenance_graph', {iri: event.data.iri, frame: frame.id}, {priority: 'event'});
        }
        return;
      }
      const payload = JSON.parse(box.querySelector('.vowl-data').textContent);
      frame.contentWindow.postMessage({type: 'dpv-vowl-data', payload}, location.origin);
    });
  });
  document.addEventListener('DOMContentLoaded', () => {
    // Compatibility for an already-running dashboard: add navigation through static assets
    // without restarting its supervised pipeline worker. New launches render this in app.py
    // and serve the bundle themselves; this branch then has no effect.
    const header = document.querySelector('.header-right');
    if (header && !header.querySelector('.documentation-button')) {
      const documentation = document.createElement('a');
      documentation.className = 'documentation-button';
      documentation.href = 'http://127.0.0.1:8058/library.html';
      documentation.textContent = 'Documentation';
      header.prepend(documentation);
    }
    new MutationObserver(connect).observe(document.body, {childList: true, subtree: true});
    connect();
  });
})();
