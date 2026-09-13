"""Reverse proxy that puts a live molab notebook behind our own origin.

molab sandboxes answer with

    content-security-policy: frame-ancestors 'self' https://*.marimo.io ...

so the browser refuses to frame one directly from our demo page. marimo's
frontend is served from a CDN and its base_url is baked in when the sandbox
server starts, so a subpath proxy cannot work either: the JS builds absolute
"/api/..." and "/ws" URLs. The only embed that works is a *root-mounted* proxy
on a second local port, which is what this module is.

Two things are relayed that a naive proxy gets wrong:

  * `/sse` and long polling responses are streamed chunk by chunk, never
    buffered, so the notebook's live output arrives as it is produced.
  * `/ws` and `/ws_sync` (the kernel connection) are relayed as opaque bytes
    after the client's Sec-WebSocket-Key and the upstream's Sec-WebSocket-Accept
    cross unmodified. The browser therefore validates the handshake against the
    real marimo server and any negotiated permessage-deflate is end to end.

The sandbox access token is held here, server side. It is attached to upstream
requests only; it is never written into a response, a header, or a log line.
Every user-facing string goes through `_scrub()` on the way out.
"""

from __future__ import annotations

import base64
import errno
import hashlib
import http.client
import json
import os
import re
import selectors
import socket
import ssl
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, urlsplit

# The origin the demo page is served from. The replacement CSP names it so the
# proxied notebook may be framed by our own site and by nothing else.
# RFC 6455 1.3: the constant a server mixes with the client's key to prove it
# understood the upgrade. Used to re-derive Sec-WebSocket-Accept for the browser.
WEBSOCKET_GUID = '258EAFA5-E914-47DA-95CA-5AB0DC85B11C'

PARENT_ORIGIN = 'http://localhost:8877'
FRAME_ANCESTORS = f"frame-ancestors 'self' {PARENT_ORIGIN}"

# RFC 7230 6.1: these describe a single hop and must never be forwarded.
HOP_BY_HOP = frozenset({
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'proxy-connection', 'te', 'trailer', 'trailers', 'transfer-encoding', 'upgrade',
})

# Request headers we regenerate or deliberately withhold from molab.
# Host and SNI must name the sandbox (Cloudflare routes on them); Origin and
# Referer would only leak our page URLs; the browser's Cookie carries the Sera
# session, which is ours and no business of a third party.
DROP_FROM_REQUEST = HOP_BY_HOP | {
    'host', 'origin', 'referer', 'cookie', 'authorization', 'accept-encoding',
    'forwarded', 'x-forwarded-for', 'x-forwarded-proto', 'x-forwarded-host',
    'content-length',
}

# Response headers we replace or swallow. The upstream Set-Cookie stays server
# side: the sandbox session belongs to the proxy, not to the browser.
DROP_FROM_RESPONSE = HOP_BY_HOP | {
    'content-security-policy', 'content-security-policy-report-only',
    'x-frame-options', 'set-cookie', 'content-length', 'date', 'server',
}

# Sec-WebSocket-* must survive byte for byte or the browser rejects the reply.
WS_FORWARD = ('sec-websocket-key', 'sec-websocket-version', 'sec-websocket-protocol',
              'sec-websocket-extensions', 'user-agent')

CONNECT_TIMEOUT = 15.0
HANDSHAKE_TIMEOUT = 20.0
BUFSIZE = 65536
MAX_HEAD = 64 * 1024
MAX_PENDING = 1 << 20
# How often the byte pump wakes to re-check the server's stop flag. Not an idle
# timeout: a quiet WebSocket is never torn down.
POLL_INTERVAL = 5.0
# Once one direction has closed, how long the other gets to drain.
LINGER_AFTER_HALF_CLOSE = 30.0


class MolabError(Exception):
    """A failure to explain to the operator. args[0] is safe to display."""


def _scrub(text, *secrets):
    """Remove secrets from a string that is about to escape this module."""
    out = str(text)
    for secret in secrets:
        if secret:
            out = out.replace(str(secret), '<redacted>')
    return out


def _log_write(text):
    """Single sink for this module's logging, so tests can watch it."""
    sys.stderr.write(text)


def normalize_url(url):
    """A bare origin: scheme and authority, no path, no query, no trailing /."""
    raw = (url or '').strip()
    if not raw:
        raise MolabError('Paste the molab sandbox URL first.')
    if '://' not in raw:
        raw = 'https://' + raw
    parts = urlsplit(raw)
    if parts.scheme not in ('http', 'https'):
        raise MolabError('The sandbox URL must start with https://')
    if not parts.hostname or re.search(r'[\s\x00-\x1f\x7f]', parts.netloc):
        raise MolabError('That does not look like a sandbox URL.')
    return f'{parts.scheme}://{parts.netloc}'


class MolabUpstream:
    """A validated molab sandbox, plus the credentials to reach it.

    The access token is private. Nothing on this object renders it, including
    repr(), so an accidental f-string in a log line cannot leak it.
    """

    def __init__(self, url, token, status, cookies=None, ssl_context=None):
        self.url = normalize_url(url)
        self.status = dict(status or {})
        self._token = token or ''
        self._cookies = dict(cookies or {})
        self._lock = threading.Lock()
        self.ssl_context = ssl_context
        parts = urlsplit(self.url)
        self.tls = parts.scheme == 'https'
        self.host = parts.hostname
        self.port = parts.port or (443 if self.tls else 80)
        self.authority = parts.netloc

    # -- credentials -------------------------------------------------------
    @property
    def cookie_header(self):
        with self._lock:
            if not self._cookies:
                return None
            return '; '.join(f'{k}={v}' for k, v in self._cookies.items())

    def remember_cookies(self, set_cookie_values):
        """Keep the sandbox's session cookies here rather than in the browser."""
        with self._lock:
            for value in set_cookie_values:
                jar = SimpleCookie()
                try:
                    jar.load(value)
                except Exception:
                    continue
                for name, morsel in jar.items():
                    self._cookies[name] = morsel.value

    def credential_headers(self):
        """Headers that authenticate us to marimo. Upstream only, never echoed."""
        headers = []
        cookie = self.cookie_header
        if cookie:
            headers.append(('Cookie', cookie))
        if self._token:
            # validate_auth() accepts a bearer token, so this works even when the
            # sandbox has restarted and invalidated every cookie it ever minted.
            headers.append(('Authorization', f'Bearer {self._token}'))
        return headers

    def scrub(self, text):
        return _scrub(text, self._token)

    def connect(self, timeout=CONNECT_TIMEOUT):
        """A fresh upstream connection. One per request keeps this thread safe."""
        if self.tls:
            context = self.ssl_context or ssl.create_default_context()
            return http.client.HTTPSConnection(
                self.host, self.port, timeout=timeout, context=context)
        return http.client.HTTPConnection(self.host, self.port, timeout=timeout)

    def __repr__(self):
        return f'<MolabUpstream {self.url}>'


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

def _describe(exc, host, port):
    """Turn a connection failure into something an operator can act on."""
    if isinstance(exc, ssl.SSLCertVerificationError):
        return f"Could not verify {host}'s TLS certificate."
    if isinstance(exc, ssl.SSLError):
        return f'TLS handshake with {host} failed. Is that really an https:// sandbox?'
    if isinstance(exc, socket.gaierror):
        return f'Could not resolve {host}. Check the sandbox URL.'
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return f'{host} did not answer in time. The sandbox may be asleep.'
    if isinstance(exc, ConnectionRefusedError):
        return f'Nothing is listening on {host}:{port}.'
    if isinstance(exc, ConnectionResetError):
        return f'{host} closed the connection before answering.'
    if isinstance(exc, OSError) and exc.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH):
        return f'No route to {host}.'
    if isinstance(exc, http.client.HTTPException):
        return f'{host} answered but did not speak HTTP. That is not a marimo server.'
    if isinstance(exc, OSError):
        return f'Could not reach {host}:{port} ({exc.strerror or exc}).'
    return f'Could not reach {host}:{port}.'


def _fetch(upstream, path, timeout, extra_headers=()):
    """One upstream GET, fully read. Raises MolabError with a safe message."""
    conn = upstream.connect(timeout=timeout)
    try:
        headers = {'Accept-Encoding': 'identity', 'User-Agent': 'sera-molab-proxy'}
        for name, value in upstream.credential_headers():
            headers[name] = value
        for name, value in extra_headers:
            headers[name] = value
        conn.request('GET', path, headers=headers)
        response = conn.getresponse()
        body = response.read(1 << 20)
        set_cookies = response.headers.get_all('Set-Cookie') or []
        return response.status, dict(response.headers), body, set_cookies
    except MolabError:
        raise
    except Exception as exc:
        raise MolabError(_describe(exc, upstream.host, upstream.port)) from None
    finally:
        conn.close()


def _looks_like_marimo(payload):
    """marimo's /api/status shape (health.py): status + version + mode."""
    if not isinstance(payload, dict):
        return False
    return 'status' in payload and ('version' in payload or 'mode' in payload)


def validate(url, token, timeout=15.0):
    """Prove the sandbox is a healthy marimo, then mint its session cookie.

    Returns a MolabUpstream. Raises MolabError whose message is safe to show
    to the operator and which never contains the token.
    """
    try:
        origin = normalize_url(url)
        if not (token or '').strip():
            raise MolabError('Paste the sandbox access token as well as the URL.')
        token = token.strip()
        probe = MolabUpstream(origin, token, {})

        status_code, _headers, body, _cookies = _fetch(probe, '/api/status', timeout)
        if status_code in (401, 403):
            raise MolabError(
                'The sandbox rejected that access token. Copy a fresh link from molab.')
        if status_code == 404:
            raise MolabError(
                f'{probe.host} answered, but it has no /api/status. '
                'That is not a marimo notebook server.')
        if status_code >= 500:
            raise MolabError(
                f'The sandbox is reachable but marimo returned HTTP {status_code}.')
        if status_code != 200:
            raise MolabError(f'Unexpected HTTP {status_code} from {probe.host}/api/status.')

        try:
            payload = json.loads(body.decode('utf-8', 'replace'))
        except ValueError:
            payload = None
        if not _looks_like_marimo(payload):
            raise MolabError(
                f'{probe.host} answered /api/status with something that is not marimo. '
                'Check the URL points at a molab sandbox.')
        if str(payload.get('status', '')).lower() not in ('healthy', 'ok'):
            reported = str(payload.get('status', 'unknown'))
            raise MolabError(
                f'marimo is running on {probe.host} but reports itself {reported!r}. '
                'Restart the sandbox and try again.')

        # Mint the session cookie. marimo answers ?access_token= with a 303 that
        # strips the query and a Set-Cookie we keep on this side of the wire.
        upstream = MolabUpstream(origin, token, payload)
        mint_code, _h, _b, set_cookies = _fetch(
            upstream, '/?access_token=' + quote(token, safe=''), timeout)
        if mint_code in (401, 403):
            raise MolabError(
                'The sandbox rejected that access token. Copy a fresh link from molab.')
        upstream.remember_cookies(set_cookies)
        return upstream
    except MolabError as exc:
        # Belt and braces: no message leaves this function carrying the token.
        raise MolabError(_scrub(exc.args[0] if exc.args else 'Sandbox check failed.',
                                token)) from None


# ---------------------------------------------------------------------------
# WebSocket byte pump
# ---------------------------------------------------------------------------

def _recv(sock):
    """One recv, draining any whole TLS records already decrypted underneath.

    A selector will never re-announce bytes that OpenSSL has already pulled off
    the fd, so a plain recv() can deadlock on an SSLSocket without this.
    """
    data = sock.recv(BUFSIZE)
    if data and isinstance(sock, ssl.SSLSocket):
        while sock.pending():
            more = sock.recv(BUFSIZE)
            if not more:
                break
            data += more
    return data


def pump(client, upstream, to_upstream=b'', to_client=b'', stop=None,
         poll_interval=POLL_INTERVAL, linger=LINGER_AFTER_HALF_CLOSE):
    """Relay opaque bytes between two blocking sockets until both are done.

    Deliberately single threaded: one OpenSSL object must not be read and
    written from two threads at once, and there is no second thread to leak.
    """
    for sock, data in ((upstream, to_upstream), (client, to_client)):
        if data:
            sock.sendall(data)

    peer = {client: upstream, upstream: client}
    deadline = None
    sel = selectors.DefaultSelector()
    try:
        sel.register(client, selectors.EVENT_READ)
        sel.register(upstream, selectors.EVENT_READ)
        while sel.get_map():
            timeout = poll_interval
            if deadline is not None:
                timeout = min(timeout, max(0.0, deadline - time.monotonic()))
            events = sel.select(timeout)
            if stop is not None and stop.is_set():
                break
            if not events:
                if deadline is not None and time.monotonic() >= deadline:
                    break
                continue
            for key, _mask in events:
                sock = key.fileobj
                other = peer[sock]
                try:
                    data = _recv(sock)
                except (OSError, ssl.SSLError):
                    data = b''
                if not data:
                    # Half close: stop reading this side, tell the peer nothing
                    # more is coming, keep draining the other direction.
                    try:
                        sel.unregister(sock)
                    except (KeyError, ValueError):
                        pass
                    try:
                        other.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
                    if deadline is None:
                        deadline = time.monotonic() + linger
                    continue
                try:
                    other.sendall(data)
                except OSError:
                    for dead in (client, upstream):
                        try:
                            sel.unregister(dead)
                        except (KeyError, ValueError):
                            pass
                    break
    finally:
        sel.close()


def _read_head(sock, timeout=HANDSHAKE_TIMEOUT):
    """Read exactly through the first CRLFCRLF; return (head, leftover).

    http.client is unusable here: HTTPResponse buffers behind its own reader and
    would swallow the first WebSocket frames.
    """
    deadline = time.monotonic() + timeout
    buf = bytearray()
    while True:
        index = buf.find(b'\r\n\r\n')
        if index != -1:
            return bytes(buf[:index + 4]), bytes(buf[index + 4:])
        if len(buf) > MAX_HEAD:
            raise MolabError('The sandbox sent an oversized handshake response.')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise MolabError('The sandbox did not complete the WebSocket handshake.')
        sock.settimeout(remaining)
        try:
            chunk = sock.recv(BUFSIZE)
        except (TimeoutError, socket.timeout):
            raise MolabError('The sandbox did not complete the WebSocket handshake.') from None
        except OSError as exc:
            raise MolabError(_describe(exc, 'the sandbox', '')) from None
        if not chunk:
            raise MolabError('The sandbox closed the WebSocket handshake early.')
        buf += chunk


def _strip_set_cookie(head):
    """Drop Set-Cookie from a raw response head, keeping the rest byte for byte."""
    lines = head.split(b'\r\n')
    kept = [line for line in lines if not line.lower().startswith(b'set-cookie:')]
    return b'\r\n'.join(kept)


def _sanitize(value):
    """No CR/LF may cross into a header we are re-serializing."""
    return str(value).replace('\r', ' ').replace('\n', ' ').strip()


def _canon(name):
    special = {
        'sec-websocket-key': 'Sec-WebSocket-Key',
        'sec-websocket-version': 'Sec-WebSocket-Version',
        'sec-websocket-protocol': 'Sec-WebSocket-Protocol',
        'sec-websocket-extensions': 'Sec-WebSocket-Extensions',
        'user-agent': 'User-Agent',
    }
    return special.get(name, '-'.join(part.capitalize() for part in name.split('-')))


# ---------------------------------------------------------------------------
# The proxy itself
# ---------------------------------------------------------------------------

class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'sera-molab-proxy'
    sys_version = ''

    # -- plumbing ----------------------------------------------------------
    def log_message(self, fmt, *args):
        upstream = getattr(self, '_upstream_for_log', None)
        text = fmt % args
        text = upstream.scrub(text) if upstream is not None else text
        _log_write(f'{self.address_string()} - {text}\n')

    def log_error(self, fmt, *args):
        self.log_message(fmt, *args)

    def handle_one_request(self):
        # A browser that navigates away mid-stream resets the socket, and stock
        # http.server answers that with a traceback on stderr. It is ordinary
        # here, not an incident.
        try:
            super().handle_one_request()
        except (ConnectionResetError, BrokenPipeError, TimeoutError):
            self.close_connection = True

    def json_response(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', FRAME_ANCESTORS)
        if self.close_connection:
            self.send_header('Connection', 'close')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    # -- dispatch ----------------------------------------------------------
    def relay(self):
        try:
            self._relay()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except MolabError as exc:
            self.close_connection = True
            self.safe_error(502, str(exc))
        except Exception as exc:  # noqa: BLE001 - a proxy must not take the page down
            self.close_connection = True
            upstream = getattr(self, '_upstream_for_log', None)
            detail = _scrub(exc, getattr(upstream, '_token', None)) if upstream else str(exc)
            self.safe_error(502, f'The sandbox connection failed: {detail}')

    def safe_error(self, status, detail):
        try:
            self.json_response(status, {'error': 'upstream_failed', 'detail': detail})
        except OSError:
            pass

    do_GET = relay
    do_HEAD = relay
    do_POST = relay
    do_PUT = relay
    do_PATCH = relay
    do_DELETE = relay
    do_OPTIONS = relay

    def _relay(self):
        # Our own front door first: an unauthenticated caller must not be able to
        # make the proxy touch molab at all.
        if not self.server.authorize(self):
            self.close_connection = True
            self.json_response(403, {
                'error': 'not_signed_in',
                'detail': 'Sign in to Sera to open the live notebook.',
            })
            return

        upstream = self.server.get_upstream()
        if upstream is None:
            self.close_connection = True
            self.json_response(503, {
                'error': 'no_sandbox',
                'detail': 'No molab sandbox is connected. Attach one from the lab notebook.',
            })
            return
        self._upstream_for_log = upstream

        if self.is_websocket_request():
            self.relay_websocket(upstream)
            return
        self.relay_http(upstream)

    # -- websocket detection ----------------------------------------------
    def is_websocket_request(self):
        connection = self.headers.get('Connection', '')
        upgrade = self.headers.get('Upgrade', '')
        if 'upgrade' not in connection.lower():
            return False
        return upgrade.strip().lower() == 'websocket'

    # -- plain HTTP --------------------------------------------------------
    def upstream_request_headers(self, upstream):
        headers = []
        for name, value in self.headers.items():
            if name.lower() in DROP_FROM_REQUEST:
                continue
            headers.append((name, _sanitize(value)))
        # marimo installs no compression middleware, but Cloudflare will happily
        # gzip. identity costs nothing on loopback and keeps the bytes opaque.
        headers.append(('Accept-Encoding', 'identity'))
        headers.extend(upstream.credential_headers())
        return headers

    def request_body_frames(self):
        """Yield the request body in pieces, without ever holding all of it."""
        length = self.headers.get('Content-Length')
        if length is not None:
            try:
                remaining = int(length)
            except ValueError:
                remaining = 0
            while remaining > 0:
                chunk = self.rfile.read(min(BUFSIZE, remaining))
                if not chunk:
                    return
                remaining -= len(chunk)
                yield chunk
            return
        if 'chunked' in self.headers.get('Transfer-Encoding', '').lower():
            while True:
                line = self.rfile.readline(MAX_PENDING)
                if not line:
                    return
                size_text = line.split(b';', 1)[0].strip()
                try:
                    size = int(size_text, 16)
                except ValueError:
                    return
                if size == 0:
                    # Consume the trailer section and stop.
                    while True:
                        trailer = self.rfile.readline(MAX_PENDING)
                        if not trailer or trailer in (b'\r\n', b'\n'):
                            return
                remaining = size
                while remaining > 0:
                    chunk = self.rfile.read(min(BUFSIZE, remaining))
                    if not chunk:
                        return
                    remaining -= len(chunk)
                    yield chunk
                self.rfile.read(2)  # the CRLF that closes the chunk

    def relay_http(self, upstream):
        conn = upstream.connect(timeout=CONNECT_TIMEOUT)
        try:
            conn.connect()
            # No read deadline once we are streaming: /sse stays open by design.
            if conn.sock is not None:
                conn.sock.settimeout(None)

            conn.putrequest(self.command, self.path, skip_host=True, skip_accept_encoding=True)
            conn.putheader('Host', upstream.authority)
            for name, value in self.upstream_request_headers(upstream):
                conn.putheader(name, value)

            has_body = (self.headers.get('Content-Length') is not None
                        or 'chunked' in self.headers.get('Transfer-Encoding', '').lower())
            if has_body and self.headers.get('Content-Length') is not None:
                conn.putheader('Content-Length', self.headers['Content-Length'])
                conn.endheaders()
                for chunk in self.request_body_frames():
                    conn.send(chunk)
            elif has_body:
                conn.putheader('Transfer-Encoding', 'chunked')
                conn.endheaders()
                for chunk in self.request_body_frames():
                    conn.send(b'%x\r\n' % len(chunk) + chunk + b'\r\n')
                conn.send(b'0\r\n\r\n')
            else:
                conn.endheaders()

            response = conn.getresponse()
            upstream.remember_cookies(response.headers.get_all('Set-Cookie') or [])
            self.send_upstream_response(response)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def send_upstream_response(self, response):
        bodyless = (self.command == 'HEAD' or response.status in (204, 304)
                    or 100 <= response.status < 200)
        content_length = response.headers.get('Content-Length')
        chunked_out = not bodyless and content_length is None

        self.send_response(response.status, response.reason)
        for name, value in response.headers.items():
            if name.lower() in DROP_FROM_RESPONSE:
                continue
            self.send_header(name, _sanitize(value))
        # One CSP, ours, so the notebook frames inside the demo page and nowhere
        # else. X-Frame-Options is dropped above; it would veto the frame.
        self.send_header('Content-Security-Policy', FRAME_ANCESTORS)
        if bodyless:
            if content_length is not None:
                self.send_header('Content-Length', content_length)
        elif chunked_out:
            self.send_header('Transfer-Encoding', 'chunked')
        else:
            self.send_header('Content-Length', content_length)
        self.end_headers()

        if bodyless:
            return
        try:
            while True:
                # read1, not read: read() would block for a full buffer and turn
                # a live SSE stream into a batch job.
                chunk = response.read1(BUFSIZE)
                if not chunk:
                    break
                if chunked_out:
                    self.wfile.write(b'%x\r\n' % len(chunk) + chunk + b'\r\n')
                else:
                    self.wfile.write(chunk)
            if chunked_out:
                self.wfile.write(b'0\r\n\r\n')
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.close_connection = True

    # -- websocket ---------------------------------------------------------
    def pending_client_bytes(self):
        """Anything the client pipelined behind the handshake, if anything."""
        sock = self.connection
        try:
            sock.setblocking(False)
        except OSError:
            return b''
        try:
            data = self.rfile.read1(MAX_PENDING)
        except Exception:
            data = b''
        finally:
            try:
                sock.setblocking(True)
            except OSError:
                pass
        return data or b''

    def websocket_handshake_bytes(self, upstream):
        lines = [
            f'GET {self.path} HTTP/1.1',
            f'Host: {upstream.authority}',
            'Connection: Upgrade',
            'Upgrade: websocket',
            f'Origin: {upstream.url}',
        ]
        seen_version = False
        for name in WS_FORWARD:
            for raw in self.headers.get_all(name) or []:
                value = _sanitize(raw)
                if not value:
                    continue
                if name == 'sec-websocket-version':
                    seen_version = True
                lines.append(f'{_canon(name)}: {value}')
        if not seen_version:
            lines.append('Sec-WebSocket-Version: 13')
        for name, value in upstream.credential_headers():
            lines.append(f'{name}: {_sanitize(value)}')
        return ('\r\n'.join(lines) + '\r\n\r\n').encode('latin-1')

    def relay_websocket(self, upstream):
        self.close_connection = True
        if not self.headers.get('Sec-WebSocket-Key'):
            self.json_response(400, {'error': 'bad_upgrade',
                                     'detail': 'Missing Sec-WebSocket-Key.'})
            return
        if self.headers.get('Content-Length') or self.headers.get('Transfer-Encoding'):
            # A body on an upgrade request is a request smuggling vector.
            self.json_response(400, {'error': 'bad_upgrade',
                                     'detail': 'A body is not allowed on an upgrade.'})
            return

        pending = self.pending_client_bytes()
        sock = None
        try:
            sock = socket.create_connection((upstream.host, upstream.port),
                                            timeout=CONNECT_TIMEOUT)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if upstream.tls:
                context = upstream.ssl_context or ssl.create_default_context()
                try:
                    # An edge free to pick h2 leaves us unable to send an
                    # RFC 6455 Upgrade at all (h2 uses :protocol instead).
                    context.set_alpn_protocols(['http/1.1'])
                except NotImplementedError:
                    pass
                sock = context.wrap_socket(sock, server_hostname=upstream.host)
            sock.sendall(self.websocket_handshake_bytes(upstream))
            head, leftover = _read_head(sock)
        except MolabError as exc:
            _close_quietly(sock)
            self.json_response(502, {'error': 'upstream_failed',
                                     'detail': upstream.scrub(str(exc))})
            return
        except OSError as exc:
            _close_quietly(sock)
            detail = upstream.scrub(_describe(exc, upstream.host, upstream.port))
            self.json_response(502, {'error': 'upstream_failed', 'detail': detail})
            return

        status_line = head.split(b'\r\n', 1)[0].decode('latin-1', 'replace')
        if ' 101' not in status_line:
            _close_quietly(sock)
            self.json_response(502, {
                'error': 'upgrade_refused',
                'detail': f'The sandbox refused the notebook socket ({status_line.strip()}).',
            })
            return

        # The 101 crosses minus any Set-Cookie, but Sec-WebSocket-Accept is
        # recomputed from THIS client's key rather than forwarded. Measured
        # against the live sandbox, the accept coming back did not match the key
        # the browser sent, and a browser fails the upgrade on that mismatch
        # (RFC 6455 4.1) even though a raw socket does not notice. Deriving it
        # here is correct whatever the upstream or its CDN did with the key.
        try:
            self.wfile.write(_rewrite_accept(_strip_set_cookie(head),
                                             self.headers.get('Sec-WebSocket-Key')))
        except OSError:
            _close_quietly(sock)
            return

        client = self.connection
        try:
            client.settimeout(None)
            sock.settimeout(None)
            pump(client, sock, to_upstream=pending, to_client=leftover,
                 stop=getattr(self.server, 'stopping', None))
        finally:
            _close_quietly(sock)
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def _rewrite_accept(head, client_key):
    """Replace Sec-WebSocket-Accept with the value derived from client_key.

    RFC 6455 4.1: the browser aborts unless the accept equals
    base64(sha1(key + GUID)) for the key IT sent. Forwarding the upstream's
    accept only works if the upstream saw that same key, which is not
    guaranteed once a CDN sits in the path.
    """
    if not client_key:
        return head
    digest = base64.b64encode(
        hashlib.sha1((client_key.strip() + WEBSOCKET_GUID).encode()).digest()).decode()
    kept = [line for line in head.split(b'\r\n')
            if not line.lower().startswith(b'sec-websocket-accept:')]
    # Insert after the status line so the header block stays well formed.
    kept.insert(1, f'Sec-WebSocket-Accept: {digest}'.encode())
    return b'\r\n'.join(kept)


def _close_quietly(sock):
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


class ProxyServer(ThreadingHTTPServer):
    """Root-mounted reverse proxy for one molab sandbox, on loopback only.

    get_upstream() -> MolabUpstream or None, consulted per request so the
    sandbox can be swapped (molab mints a new URL when you attach a GPU)
    without restarting anything.
    authorize(handler) -> bool, the Sera session check. Cookies are not port
    scoped, so the sera_session set on :8877 reaches this port unchanged.
    """

    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True

    def __init__(self, port, get_upstream, authorize):
        self.get_upstream = get_upstream
        self.authorize = authorize
        self.stopping = threading.Event()
        super().__init__(('127.0.0.1', port), ProxyHandler)

    def handle_error(self, request, client_address):
        # Never let a raw traceback reach stderr: it would bypass _scrub().
        exc = sys.exc_info()[1]
        try:
            upstream = self.get_upstream()
        except Exception:
            upstream = None
        text = f'{type(exc).__name__}: {exc}'
        text = upstream.scrub(text) if upstream is not None else text
        _log_write(f'{client_address[0]} - relay error: {text}\n')

    def shutdown(self):
        self.stopping.set()
        super().shutdown()

    def server_close(self):
        self.stopping.set()
        super().server_close()


def main(argv=None):
    """Run the proxy standalone against SERA_MOLAB_URL / SERA_MOLAB_TOKEN."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--port', type=int, default=8878)
    parser.add_argument('--url', default=os.environ.get('SERA_MOLAB_URL', ''))
    parser.add_argument('--token', default=os.environ.get('SERA_MOLAB_TOKEN', ''))
    args = parser.parse_args(argv)

    try:
        upstream = validate(args.url, args.token)
    except MolabError as exc:
        print(f'molab sandbox unusable: {exc}', file=sys.stderr)
        return 1
    print(f'proxying {upstream.url} at http://127.0.0.1:{args.port}', file=sys.stderr)
    server = ProxyServer(args.port, lambda: upstream, lambda handler: True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
