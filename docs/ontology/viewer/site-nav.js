/* Author: Brent Thompson <brent.thompson@ucf.edu>
Summary: Return to the serving dashboard and filter the static documentation library. */
(() => {
  // Dashboard-mounted documentation follows its current host and custom port.
  // The standalone 8058 preview returns to the standard local dashboard.
  document.querySelectorAll('[data-dashboard-link]').forEach(link => {
    link.href = location.pathname.startsWith('/documentation/') ? '/' : 'http://localhost:8056/';
  });
  const search = document.querySelector('#documentation-search');
  if (!search) return;
  search.addEventListener('input', () => {
    const query = search.value.trim().toLocaleLowerCase();
    let count = 0;
    document.querySelectorAll('.library-group').forEach(group => {
      let visible = 0;
      group.querySelectorAll('li').forEach(item => {
        item.hidden = !item.textContent.toLocaleLowerCase().includes(query);
        if (!item.hidden) { visible++; count++; }
      });
      group.hidden = visible === 0;
    });
    document.querySelector('#documentation-count').textContent = count ? `${count} documents` : 'No matching documents. Try a stage name or “guide”.';
  });
})();
