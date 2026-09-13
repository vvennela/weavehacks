(() => {
  const $ = id => document.getElementById(id);
  const frame = $('notebook-frame'), note = $('notebook-status');
  const tabs = [...document.querySelectorAll('[data-substrate]')];
  if (!frame || !tabs.length) return;

  let molabUrl = '';
  const LOCAL = '/notebook-app/';

  // Remember the last choice so a reload does not drop you back on a tab you were
  // not using. Wrapped because storage throws in some privacy modes.
  const remember = value => { try { localStorage.setItem('sera-substrate', value); } catch {} };
  const remembered = () => { try { return localStorage.getItem('sera-substrate'); } catch { return null; } };

  function select(substrate) {
    const gpu = substrate === 'gpu';
    if (gpu && !molabUrl) {
      note.textContent = 'No molab notebook is configured. Start the server with '
        + 'SERA_MOLAB_URL set to your notebook’s /app URL, then reload.';
      note.hidden = false;
      return;
    }
    tabs.forEach(t => {
      const on = t.dataset.substrate === substrate;
      t.classList.toggle('active', on);
      t.setAttribute('aria-selected', String(on));
    });
    frame.src = gpu ? molabUrl : LOCAL;
    frame.title = gpu ? 'Sera Lab on molab' : 'Sera Lab, local simulator';
    note.textContent = gpu
      ? 'Running on molab. Attach an RTX Pro 6000 Blackwell with the notebook specs button inside the notebook, then press Run for measured vLLM numbers.'
      : 'Running locally in your browser through WebAssembly, on Sera’s analytic simulator. No GPU, no weights, and no network once loaded.';
    note.hidden = false;
    remember(substrate);
  }

  tabs.forEach(t => t.addEventListener('click', () => select(t.dataset.substrate)));

  fetch('/api/config')
    .then(r => (r.ok ? r.json() : {}))
    .then(data => { molabUrl = data.molab_url || ''; })
    .catch(() => {})
    .finally(() => {
      const gpuTab = tabs.find(t => t.dataset.substrate === 'gpu');
      if (gpuTab) gpuTab.disabled = !molabUrl;
      select(molabUrl && remembered() !== 'local' ? 'gpu' : 'local');
    });
})();
