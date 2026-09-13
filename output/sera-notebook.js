(() => {
  const $ = id => document.getElementById(id);

  // The tab query is scoped: #molab-fallback carries data-goto, not data-substrate,
  // precisely so a button inside a panel can never be adopted as a third tab.
  const tabs = [...document.querySelectorAll('.substrate-tabs [data-substrate]')];
  const panel = $('molab-panel'), localPanel = $('local-panel'), localFrame = $('notebook-frame');
  const note = $('notebook-status');
  if (!tabs.length || !panel || !localPanel || !localFrame || !note) return;

  const states = {
    connect: $('molab-connect'),
    connecting: $('molab-connecting'),
    live: $('molab-live'),
    down: $('molab-down'),
  };
  const badges = $('molab-badges'), badge = $('molab-badge'), gpuBadge = $('molab-gpu-badge'), age = $('molab-age');
  const liveActions = $('molab-live-actions'), external = $('molab-external');
  const frame = $('molab-frame'), foot = $('molab-live-foot');
  const form = $('molab-form'), urlField = $('molab-url'), tokenField = $('molab-token');
  const reveal = $('molab-token-show'), submit = $('molab-connect-submit'), connectError = $('molab-connect-error');
  const connecting = $('molab-connecting-text'), cancel = $('molab-cancel');
  const downTitle = $('molab-down-title'), downDetail = $('molab-down-detail'), downAge = $('molab-down-age');

  const POLL_MS = 12000;   // how often a live session is re-checked
  const TICK_MS = 5000;    // how often the "checked N ago" line is redrawn
  const LOCAL_NOTE = 'Running locally in your browser through WebAssembly, on Sera’s '
    + 'analytic simulator. Seconds rather than minutes, no GPU, and no network once loaded.';

  let substrate = 'gpu';
  let state = 'connecting';
  let session = null;     // the last /api/molab/status payload we trusted
  let lastSeen = 0;       // epoch ms of the last answer from the sandbox
  let inflight = null;    // AbortController for the in-progress connect
  let pollTimer = 0, tickTimer = 0;

  const remember = v => { try { localStorage.setItem('sera-substrate', v); } catch {} };
  const remembered = () => { try { return localStorage.getItem('sera-substrate'); } catch { return null; } };

  // #notebook-status is the one live region on the page: every state change writes
  // exactly one sentence here, and nothing else announces.
  const say = text => { note.hidden = !text; note.textContent = text; };

  function ago(ms) {
    const s = Math.round(ms / 1000);
    if (s < 10) return 'just now';
    if (s < 60) return s + 's ago';
    const m = Math.round(s / 60);
    return m === 1 ? 'a minute ago' : m + ' minutes ago';
  }

  const clean = value => (typeof value === 'string' && value.trim() ? value.trim() : '');

  // ---------------------------------------------------------------- transport

  async function call(path, body) {
    const init = body === undefined
      ? { headers: { 'Accept': 'application/json' } }
      : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    if (body !== undefined) {
      inflight = new AbortController();
      init.signal = inflight.signal;
    }
    let response;
    try {
      response = await fetch(path, init);
    } finally {
      if (body !== undefined) inflight = null;
    }
    if (response.status === 401) { location.replace('/sign-in'); throw new Error('Signed out.'); }
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) throw new Error(clean(data.error) || 'The local Sera server refused that (HTTP ' + response.status + ').');
    return data;
  }

  // ------------------------------------------------------------------ states

  function setState(next) {
    state = next;
    Object.keys(states).forEach(key => { if (states[key]) states[key].hidden = key !== next; });
    const live = next === 'live';
    if (badges) badges.hidden = !live;
    if (liveActions) liveActions.hidden = !live;
    renderAge();
    schedule();
  }

  function setConnecting(text, cancellable) {
    if (connecting) connecting.textContent = text;
    if (cancel) cancel.hidden = !cancellable;
    setState('connecting');
    say(text);
  }

  function renderAge() {
    if (age) age.textContent = state === 'live' && lastSeen ? 'checked ' + ago(Date.now() - lastSeen) : '';
    if (downAge) {
      downAge.textContent = state !== 'down' ? ''
        : lastSeen ? 'Sera last got an answer from it ' + ago(Date.now() - lastSeen) + '.'
        : 'Sera has not had an answer from it since this page loaded.';
    }
  }

  function schedule() {
    clearInterval(pollTimer); clearInterval(tickTimer);
    if (substrate !== 'gpu') return;
    if (state !== 'live' && state !== 'down') return;
    pollTimer = setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, POLL_MS);
    tickTimer = setInterval(renderAge, TICK_MS);
  }

  // The badge must never claim hardware the backend has not positively confirmed.
  // gpu === true is the only case that may say a GPU is there.
  function renderHardware(gpu, detail) {
    if (!gpuBadge || !foot) return '';
    let line;
    if (gpu === true) {
      gpuBadge.textContent = 'GPU attached';
      gpuBadge.className = 'badge';
      line = 'Sera confirmed a GPU on this sandbox. The demo checks the runtime before starting a measured run.'
        + (detail ? ' Reported as: ' + detail + '.' : '');
    } else if (gpu === false) {
      gpuBadge.textContent = 'No GPU attached';
      gpuBadge.className = 'badge danger';
      line = 'No GPU is attached. The demo stops before model execution; it does not substitute simulator results. '
        + 'Attach one from molab’s notebook specs menu — molab restarts the sandbox and gives it a new '
        + 'address, so you will need to connect again.'
        + (detail ? ' Sandbox reports: ' + detail + '.' : '');
    } else {
      gpuBadge.textContent = 'GPU not verified';
      gpuBadge.className = 'badge neutral';
      line = 'The session is live, but Sera could not confirm what hardware is attached — trust the '
        + 'notebook’s own hardware readout over this page.'
        + (detail ? ' Sera got back: ' + detail + '.' : '');
    }
    foot.textContent = line;
    return line;
  }

  function goLive(data) {
    session = data;
    lastSeen = Date.now();
    const src = clean(data.proxy_url);
    if (badge) badge.textContent = 'Live molab session';
    if (external) external.href = src || '#';
    // Only assign when it actually changed: a poll must not reload the kernel.
    if (frame && frame.getAttribute('src') !== src) frame.src = src;
    const hardware = renderHardware(data.gpu === true ? true : data.gpu === false ? false : null, clean(data.detail));
    setState('live');
    say(hardware);
  }

  // Leaving the live state must also retire the hardware claim, not just hide it:
  // a stale "GPU attached" is the one thing this panel may never show.
  function clearHardware() {
    if (gpuBadge) { gpuBadge.textContent = 'GPU not verified'; gpuBadge.className = 'badge neutral'; }
    if (foot) foot.textContent = '';
  }

  function goDown(data, why) {
    session = data && data.connected ? data : session;
    if (frame) frame.removeAttribute('src');  // never a stale frame under a live badge
    clearHardware();
    const host = clean(data && data.url) || (session ? clean(session.url) : '');
    if (downTitle) downTitle.textContent = host ? 'No answer from ' + host : 'The molab sandbox stopped answering';
    const reason = clean(why) || clean(data && data.detail)
      || 'Sera could not reach the sandbox through the local relay. molab sandboxes stop on their own '
      + 'when they idle, and attaching a GPU replaces the address entirely.';
    if (downDetail) downDetail.textContent = reason;
    setState('down');
    say(reason + ' Sera has taken the frame down rather than leave a dead session on screen — retry, '
      + 'connect a new sandbox, or fall back to the local simulator.');
  }

  function goConnect(message) {
    session = null;
    if (frame) frame.removeAttribute('src');
    clearHardware();
    setState('connect');
    say(message || 'No molab session is connected. Paste a sandbox URL and its access token to run this notebook on molab.');
  }

  function apply(data) {
    if (!data || !data.connected) { goConnect(); return; }
    if (data.healthy && clean(data.proxy_url)) goLive(data);
    else goDown(data);
  }

  async function refresh() {
    if (state === 'connecting' && inflight) return;   // a connect is mid-flight; let it finish
    try {
      apply(await call('/api/molab/status'));
    } catch (err) {
      if (err instanceof TypeError) {
        if (session && session.connected) {
          goDown(session, 'Sera’s local server stopped answering, so it cannot say whether the sandbox is still up.');
        } else {
          goConnect('Sera’s local server is not answering. Start it again, then reload this page.');
        }
        return;
      }
      if (err && err.message === 'Signed out.') return;
      goConnect(err && err.message ? err.message : 'Sera could not read the molab connection status.');
    }
  }

  // ------------------------------------------------------------------- input

  // Accepts a bare host, a full sandbox URL, or a URL still carrying ?access_token=.
  function parseSandbox(raw) {
    const value = clean(raw);
    if (!value) return null;
    let parsed;
    try {
      parsed = new URL(/^[a-z][a-z0-9+.\-]*:\/\//i.test(value) ? value : 'https://' + value);
    } catch { return null; }
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return null;
    if (!parsed.hostname || parsed.hostname.indexOf('.') < 0) return null;
    return { origin: parsed.origin, token: parsed.searchParams.get('access_token') || '' };
  }

  function liftToken() {
    if (!urlField || !tokenField) return;
    const parsed = parseSandbox(urlField.value);
    if (!parsed) return;
    if (parsed.token && !clean(tokenField.value)) tokenField.value = parsed.token;
    urlField.value = parsed.origin;
  }

  function fail(message, field) {
    if (connectError) { connectError.textContent = message; connectError.hidden = false; }
    say(message);
    if (field) field.focus();
  }

  if (urlField) {
    urlField.addEventListener('change', liftToken);
    urlField.addEventListener('paste', () => setTimeout(liftToken, 0));
  }

  if (reveal && tokenField) {
    reveal.addEventListener('click', () => {
      const hidden = tokenField.type === 'password';
      tokenField.type = hidden ? 'text' : 'password';
      reveal.textContent = hidden ? 'Hide' : 'Show';
      reveal.setAttribute('aria-pressed', String(hidden));
      reveal.setAttribute('aria-label', hidden ? 'Hide access token' : 'Show access token');
    });
  }

  if (form) {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      liftToken();
      const parsed = parseSandbox(urlField && urlField.value);
      if (!parsed) { fail('That does not look like a sandbox address. Paste the https:// URL molab opened the notebook on.', urlField); return; }
      const token = clean(tokenField && tokenField.value);
      if (!token) { fail('Paste the access_token molab put in the notebook URL the first time it opened.', tokenField); return; }
      if (connectError) connectError.hidden = true;
      if (submit) submit.disabled = true;
      setConnecting('Reaching ' + parsed.origin + '…', true);
      try {
        const data = await call('/api/molab/connect', { url: parsed.origin, token });
        if (data.status && typeof data.status === 'object') apply(data.status);
        else await refresh();
      } catch (err) {
        if (err && err.name === 'AbortError') {
          goConnect('Cancelled. Sera stopped waiting — checking whether the connection landed anyway…');
          refresh();
        } else if (err instanceof TypeError) {
          setState('connect');
          fail('Cannot reach the local Sera server. Is it still running?');
        } else if (err && err.message === 'Signed out.') {
          return;
        } else {
          setState('connect');
          fail(err && err.message ? err.message : 'Sera could not connect to that sandbox.');
        }
      } finally {
        if (submit) submit.disabled = false;
      }
    });
  }

  if (cancel) cancel.addEventListener('click', () => { if (inflight) inflight.abort(); });

  const reload = $('molab-reload');
  if (reload && frame) {
    reload.addEventListener('click', () => {
      const src = session ? clean(session.proxy_url) : '';
      if (!src) return;
      frame.removeAttribute('src');
      // Re-assign on the next frame so the browser really re-fetches the same URL.
      requestAnimationFrame(() => { frame.src = src; });
      say('Reloading the molab frame.');
    });
  }

  const disconnect = $('molab-disconnect');
  if (disconnect) {
    disconnect.addEventListener('click', async () => {
      disconnect.disabled = true;
      try {
        await call('/api/molab/disconnect', {});
      } catch (err) {
        if (err && err.message === 'Signed out.') return;
      } finally {
        disconnect.disabled = false;
      }
      lastSeen = 0;
      if (tokenField) { tokenField.value = ''; tokenField.type = 'password'; }
      if (reveal) { reveal.textContent = 'Show'; reveal.setAttribute('aria-pressed', 'false'); reveal.setAttribute('aria-label', 'Show access token'); }
      goConnect('Disconnected. Sera erased the stored token. The sandbox itself keeps running on molab.');
    });
  }

  const retry = $('molab-retry');
  if (retry) {
    retry.addEventListener('click', () => {
      setConnecting('Re-checking the sandbox…', false);
      refresh();
    });
  }

  const reconnect = $('molab-reconnect');
  if (reconnect) {
    reconnect.addEventListener('click', () => {
      goConnect('Enter the address and token of the sandbox you want Sera to use.');
      if (urlField) urlField.focus();
    });
  }

  document.querySelectorAll('[data-goto]').forEach(button => {
    button.addEventListener('click', () => select(button.dataset.goto, true));
  });

  // -------------------------------------------------------------------- tabs

  function select(next, focusTab) {
    substrate = next === 'local' ? 'local' : 'gpu';
    tabs.forEach(tab => {
      const on = tab.dataset.substrate === substrate;
      tab.classList.toggle('active', on);
      tab.setAttribute('aria-selected', String(on));
      tab.tabIndex = on ? 0 : -1;
      if (on && focusTab) tab.focus();
    });
    panel.hidden = substrate !== 'gpu';
    localPanel.hidden = substrate === 'gpu';
    if (substrate === 'gpu') {
      // Never leave the WebAssembly notebook running behind a hidden panel. The molab
      // frame is the exception: it holds a live kernel socket, so it survives a tab flip
      // and is torn down only by goDown/goConnect.
      localFrame.removeAttribute('src');
      refresh();
    } else {
      if (!localFrame.getAttribute('src')) localFrame.src = '/notebook-app/';
      say(LOCAL_NOTE);
    }
    remember(substrate);
    schedule();
  }

  tabs.forEach(tab => tab.addEventListener('click', () => select(tab.dataset.substrate, false)));

  const tablist = document.querySelector('.substrate-tabs');
  if (tablist) {
    tablist.addEventListener('keydown', event => {
      const at = tabs.indexOf(document.activeElement);
      if (at < 0) return;
      let to = -1;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') to = (at + 1) % tabs.length;
      else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') to = (at - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') to = 0;
      else if (event.key === 'End') to = tabs.length - 1;
      if (to < 0) return;
      event.preventDefault();
      select(tabs[to].dataset.substrate, true);
    });
  }

  // ------------------------------------------------------------------- start

  setConnecting('Checking for a saved molab session…', false);
  select(remembered() === 'local' ? 'local' : 'gpu', false);
})();
