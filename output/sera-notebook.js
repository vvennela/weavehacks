(() => {
  const $ = id => document.getElementById(id);
  const frame = $('notebook-frame'), panel = $('molab-panel'), note = $('notebook-status');
  const tabs = [...document.querySelectorAll('[data-substrate]')];
  const link = $('molab-open'), missing = $('molab-missing'), preview = $('molab-preview');
  if (!frame || !tabs.length) return;

  let molabUrl = '';

  const remember = v => { try { localStorage.setItem('sera-substrate', v); } catch {} };
  const remembered = () => { try { return localStorage.getItem('sera-substrate'); } catch { return null; } };

  function select(substrate) {
    const gpu = substrate === 'gpu';
    tabs.forEach(t => {
      const on = t.dataset.substrate === substrate;
      t.classList.toggle('active', on);
      t.setAttribute('aria-selected', String(on));
    });
    panel.hidden = !gpu;
    frame.hidden = gpu;
    if (gpu) {
      // Never leave a cross-origin frame loading behind a hidden panel.
      frame.removeAttribute('src');
      if (preview) preview.open = false;
      note.textContent = molabUrl
        ? 'molab runs on a real RTX Pro 6000 Blackwell, but a session cannot be embedded — open it in its own tab.'
        : 'No molab notebook is configured yet.';
    } else {
      frame.src = '/notebook-app/';
      note.textContent = 'Running locally in your browser through WebAssembly, on Sera’s '
        + 'analytic simulator. Seconds rather than minutes, no GPU, and no network once loaded.';
    }
    note.hidden = false;
    remember(substrate);
  }

  tabs.forEach(t => t.addEventListener('click', () => select(t.dataset.substrate)));

  // The read-only preview is opt-in: it is a WebAssembly render of the notebook's
  // code, it takes a while, and a spinner sitting on the page reads as breakage.
  if (preview) {
    preview.addEventListener('toggle', () => {
      const box = $('molab-preview-frame');
      if (preview.open && box && !box.src && molabUrl) box.src = molabUrl;
    });
  }

  fetch('/api/config')
    .then(r => (r.ok ? r.json() : {}))
    .then(data => { molabUrl = data.molab_url || ''; })
    .catch(() => {})
    .finally(() => {
      if (link && molabUrl) link.href = molabUrl.replace(/\/app$/, '');
      if (link) link.hidden = !molabUrl;
      if (missing) missing.hidden = !!molabUrl;
      if (preview) preview.hidden = !molabUrl;
      select(remembered() === 'local' ? 'local' : 'gpu');
    });
})();
