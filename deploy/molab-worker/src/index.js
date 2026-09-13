/**
 * Reverse proxy that lets useseraai.com embed a live molab notebook.
 *
 * molab answers with
 *
 *   content-security-policy: frame-ancestors 'self' https://*.marimo.io ...
 *
 * so a browser refuses to frame the sandbox from our domain. marimo's frontend
 * comes from a CDN and its base_url is fixed when the sandbox starts, so the
 * proxy has to be root-mounted on its own origin rather than under a path.
 *
 * This runs on a Worker rather than in the Vercel function because the notebook
 * kernel is a WebSocket, and Vercel's serverless runtime cannot hold one open.
 * Workers proxy sockets natively: fetch() returns a `webSocket` on a 101 and we
 * hand that straight back to the browser.
 *
 * No credential lives here. The molab sandbox does not enforce authentication —
 * anonymous requests already receive the notebook and its server token — so the
 * proxy forwards requests as-is. If molab ever starts requiring a token, this
 * needs a secret and a header, not a rewrite.
 */

const UPSTREAM = 'https://sb-4d6d72981b11fb9d.sb.molab.run';

// Who may frame the proxied notebook. Anything not listed here is refused by
// the browser, so the embed cannot be lifted onto someone else's page.
const FRAME_ANCESTORS = [
  "'self'",
  'https://useseraai.com',
  'https://www.useseraai.com',
  'http://localhost:8877',
];

// Hop-by-hop headers describe one connection and must not be forwarded.
const HOP_BY_HOP = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailer', 'trailers', 'transfer-encoding', 'upgrade',
]);

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const upstream = new URL(UPSTREAM);
    const target = new URL(url.pathname + url.search, upstream);

    // The kernel socket. Passing the original request through lets the runtime
    // negotiate the upgrade end to end, so Sec-WebSocket-Accept stays valid for
    // the key the browser actually sent.
    if ((request.headers.get('Upgrade') || '').toLowerCase() === 'websocket') {
      const wsResponse = await fetch(new Request(target, request));
      return new Response(wsResponse.body, {
        status: wsResponse.status,
        statusText: wsResponse.statusText,
        headers: wsResponse.headers,
        webSocket: wsResponse.webSocket,
      });
    }

    const headers = new Headers(request.headers);
    for (const name of HOP_BY_HOP) headers.delete(name);
    // Cloudflare routes on Host, and marimo is happier seeing its own origin
    // than ours; our page URLs are no business of the sandbox either.
    headers.set('Host', upstream.host);
    headers.delete('origin');
    headers.delete('referer');

    let response;
    try {
      response = await fetch(new Request(target, {
        method: request.method,
        headers,
        body: request.body,
        redirect: 'manual',
      }));
    } catch (err) {
      return json(502, {
        error: 'The molab sandbox is not responding. It may have shut down.',
      });
    }

    const out = new Headers(response.headers);
    for (const name of HOP_BY_HOP) out.delete(name);
    out.delete('content-security-policy-report-only');
    out.delete('x-frame-options');
    // The whole point: replace molab's frame-ancestors with one naming us.
    out.set('content-security-policy', `frame-ancestors ${FRAME_ANCESTORS.join(' ')}`);

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: out,
    });
  },
};

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}
