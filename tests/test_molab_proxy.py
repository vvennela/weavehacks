"""The molab reverse proxy, proven against a fake marimo that never leaves loopback.

The real sandbox is remote, ephemeral, and (right now) GPU-less, so none of it can
be a test dependency. Instead this file stands up a small server that behaves like
marimo where it matters — `/api/status`, the `?access_token=` 303 that mints a
session cookie, a chunked event stream, and a real RFC 6455 endpoint — and drives
the proxy against it.

The load-bearing assertions are the ones that are easy to get wrong and impossible
to notice on stage: that the access token never crosses back to the browser, that a
streamed response is relayed as it is produced rather than collected first, and that
the kernel WebSocket survives the round trip with its handshake intact.
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web import molab_proxy  # noqa: E402
from web.molab_proxy import MolabError, ProxyServer, validate  # noqa: E402

TOKEN = 'tok_SUPERSECRET_do_not_leak_a1b2c3d4'
SESSION_COOKIE = 'sess-abc123'
# How long the fake stalls between the two halves of its event stream. Long enough
# that a buffering proxy is unmistakable, short enough not to slow the suite.
STREAM_GAP = 0.8
WS_GUID = '258EAFA5-E914-47DA-95CA-5AB0DC85B11C'

MARIMO_STATUS = {
    'status': 'healthy',
    'filenames': ['/marimo/notebook.py'],
    'mode': 'edit',
    'sessions': 1,
    'version': '0.24.0',
    'python_version': '3.13.11',
    'requirements': [],
    'node_version': None,
    'lsp_running': False,
}


# ---------------------------------------------------------------------------
# WebSocket wire helpers, shared by the fake server and the test client
# ---------------------------------------------------------------------------

def ws_accept(key):
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


def ws_frame(opcode, payload, mask=False):
    out = bytearray([0x80 | opcode])
    size = len(payload)
    flag = 0x80 if mask else 0
    if size < 126:
        out.append(flag | size)
    elif size < 65536:
        out.append(flag | 126)
        out += size.to_bytes(2, 'big')
    else:
        out.append(flag | 127)
        out += size.to_bytes(8, 'big')
    if mask:
        key = os.urandom(4)
        out += key
        out += bytes(byte ^ key[i % 4] for i, byte in enumerate(payload))
    else:
        out += payload
    return bytes(out)


def ws_read_frame(fp):
    """(opcode, payload) or None at EOF. Unmasks client frames."""
    head = fp.read(2)
    if len(head) < 2:
        return None
    opcode = head[0] & 0x0F
    masked = bool(head[1] & 0x80)
    size = head[1] & 0x7F
    if size == 126:
        size = int.from_bytes(fp.read(2), 'big')
    elif size == 127:
        size = int.from_bytes(fp.read(8), 'big')
    key = fp.read(4) if masked else b''
    payload = fp.read(size) if size else b''
    if masked:
        payload = bytes(byte ^ key[i % 4] for i, byte in enumerate(payload))
    return opcode, payload


def chunk(data):
    return b'%x\r\n' % len(data) + data + b'\r\n'


# ---------------------------------------------------------------------------
# The fake marimo sandbox
# ---------------------------------------------------------------------------

class FakeMarimoHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass

    # -- helpers -----------------------------------------------------------
    def authed(self):
        if self.headers.get('Authorization') == f'Bearer {self.server.token}':
            return True
        if f'session_8080={SESSION_COOKIE}' in (self.headers.get('Cookie') or ''):
            return True
        query = parse_qs(urlsplit(self.path).query)
        return query.get('access_token', [None])[0] == self.server.token

    def respond(self, status, ctype, body, extra=()):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        for name, value in extra:
            self.send_header(name, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def deny(self):
        self.respond(403, 'application/json', b'{"error":"Unauthorized"}')

    # -- routing -----------------------------------------------------------
    def do_GET(self):
        path = urlsplit(self.path).path
        query = parse_qs(urlsplit(self.path).query)
        self.server.record(self)

        if path in ('/ws', '/ws_sync'):
            self.websocket()
        elif path == '/api/status':
            self.status_route()
        elif path == '/' and 'access_token' in query:
            self.mint_route()
        elif path == '/':
            self.index_route()
        elif path == '/plain':
            self.respond(200, 'text/plain; charset=utf-8', b'hello from marimo')
        elif path == '/headers':
            seen = {k.lower(): v for k, v in self.headers.items()}
            self.respond(200, 'application/json', json.dumps(seen).encode())
        elif path == '/stream':
            self.stream_route()
        else:
            self.respond(404, 'application/json', b'{"error":"not found"}')

    def do_POST(self):
        self.server.record(self)
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length else b''
        payload = {
            'echo': body.decode('utf-8', 'replace'),
            'content_type': self.headers.get('Content-Type'),
            'length': length,
        }
        self.respond(200, 'application/json', json.dumps(payload).encode())

    # -- routes ------------------------------------------------------------
    def status_route(self):
        if self.server.status_delay:
            time.sleep(self.server.status_delay)
        if self.server.status_needs_auth and not self.authed():
            self.deny()
            return
        payload = json.dumps(self.server.status_payload).encode()
        self.respond(200, 'application/json', payload)

    def mint_route(self):
        if not self.authed():
            self.deny()
            return
        self.send_response(303)
        self.send_header('Location', '/')
        self.send_header('Content-Length', '0')
        self.send_header(
            'Set-Cookie',
            f'session_8080={SESSION_COOKIE}; HttpOnly; Path=/; SameSite=lax')
        self.end_headers()

    def index_route(self):
        if not self.authed():
            self.deny()
            return
        body = b'<html><body>marimo notebook</body></html>'
        self.respond(200, 'text/html; charset=utf-8', body, extra=(
            # Exactly the pair that makes a direct iframe impossible.
            ('Content-Security-Policy', "frame-ancestors 'self' https://evil.example"),
            ('X-Frame-Options', 'DENY'),
            ('Set-Cookie', 'extra_cookie=oreo; Path=/'),
            # Hop-by-hop noise that must not survive the relay.
            ('Keep-Alive', 'timeout=5'),
            ('Trailer', 'X-Nope'),
            ('Proxy-Authenticate', 'Basic realm="nope"'),
            ('X-Marimo', 'yes'),
        ))

    def stream_route(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Transfer-Encoding', 'chunked')
        self.end_headers()
        self.wfile.write(chunk(b'data: first\n\n'))
        self.server.first_chunk_at = time.monotonic()
        time.sleep(STREAM_GAP)
        self.wfile.write(chunk(b'data: second\n\n'))
        self.wfile.write(b'0\r\n\r\n')
        self.server.finished_at = time.monotonic()
        self.close_connection = True

    def websocket(self):
        key = self.headers.get('Sec-WebSocket-Key')
        if not self.authed() or not key:
            self.deny()
            return
        self.close_connection = True
        self.wfile.write(
            b'HTTP/1.1 101 Switching Protocols\r\n'
            b'Upgrade: websocket\r\n'
            b'Connection: Upgrade\r\n'
            + f'Sec-WebSocket-Accept: {ws_accept(key)}\r\n'.encode()
            + b'Set-Cookie: upstream_ws_cookie=nope; Path=/\r\n'
            b'\r\n')
        while True:
            frame = ws_read_frame(self.rfile)
            if frame is None:
                break
            opcode, payload = frame
            try:
                if opcode == 0x8:
                    self.wfile.write(ws_frame(0x8, payload))
                    break
                self.wfile.write(ws_frame(0xA if opcode == 0x9 else opcode, payload))
            except OSError:
                break


class FakeMarimo(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True

    def __init__(self, token=TOKEN):
        self.token = token
        self.hits = []
        self.lock = threading.Lock()
        self.status_payload = dict(MARIMO_STATUS)
        self.status_needs_auth = True
        self.status_delay = 0.0
        self.first_chunk_at = None
        self.finished_at = None
        super().__init__(('127.0.0.1', 0), FakeMarimoHandler)

    @property
    def origin(self):
        return f'http://127.0.0.1:{self.server_port}'

    def record(self, handler):
        with self.lock:
            self.hits.append((handler.command, handler.path,
                              {k.lower(): v for k, v in handler.headers.items()}))

    def paths(self):
        with self.lock:
            return [path for _method, path, _headers in self.hits]

    def last_headers(self):
        with self.lock:
            return self.hits[-1][2]

    def handle_error(self, request, client_address):
        # A client that walks away mid-stream is expected here, not a failure.
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def serve(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


@pytest.fixture
def fake():
    server = FakeMarimo()
    thread = serve(server)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def logs(monkeypatch):
    """Everything the proxy would have written to stderr, captured verbatim."""
    captured = []
    monkeypatch.setattr(molab_proxy, '_log_write', captured.append)
    return captured


@pytest.fixture
def make_proxy():
    started = []

    def build(get_upstream, authorize=lambda handler: True):
        server = ProxyServer(0, get_upstream, authorize)
        thread = serve(server)
        started.append((server, thread))
        return server

    yield build
    for server, thread in started:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------

def call(server, path, method='GET', headers=None, body=None, timeout=10):
    """One request at the proxy. Returns (status, headers dict, body bytes)."""
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        return response.status, dict(response.headers), response.read()
    finally:
        conn.close()


def raw_headers(server, path):
    """The proxy's response head as bytes, so duplicates cannot hide in a dict."""
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
    try:
        conn.request('GET', path)
        response = conn.getresponse()
        head = b'\r\n'.join(
            f'{k}: {v}'.encode() for k, v in response.getheaders())
        return response.status, head, response.read()
    finally:
        conn.close()


def open_socket(server):
    sock = socket.create_connection(('127.0.0.1', server.server_port), timeout=10)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


def read_head(sock):
    """Read exactly through CRLFCRLF, one byte at a time, leaving frames intact."""
    head = b''
    while not head.endswith(b'\r\n\r\n'):
        byte = sock.recv(1)
        if not byte:
            break
        head += byte
    return head


def free_port():
    probe = socket.socket()
    probe.bind(('127.0.0.1', 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


# ---------------------------------------------------------------------------
# 1-2. validate()
# ---------------------------------------------------------------------------

def test_validate_captures_status_and_mints_the_cookie(fake):
    upstream = validate(fake.origin, TOKEN, timeout=5)

    assert upstream.url == fake.origin
    assert upstream.status['version'] == '0.24.0'
    assert upstream.status['mode'] == 'edit'
    # The 303's Set-Cookie was kept here rather than handed to anyone.
    assert upstream.cookie_header == f'session_8080={SESSION_COOKIE}'
    assert '/api/status' in fake.paths()
    assert any(path.startswith('/?access_token=') for path in fake.paths())


def test_validate_normalizes_a_pasted_url(fake):
    upstream = validate(fake.origin + '/notebook/?x=1', TOKEN, timeout=5)
    assert upstream.url == fake.origin


def test_validate_reports_an_unreachable_host():
    port = free_port()
    with pytest.raises(MolabError) as caught:
        validate(f'http://127.0.0.1:{port}', TOKEN, timeout=3)
    message = str(caught.value)
    assert 'listening' in message.lower() or 'reach' in message.lower()
    assert str(port) in message


def test_validate_reports_a_tls_failure(fake):
    """An https:// URL pointed at a plaintext port is the commonest paste error."""
    with pytest.raises(MolabError) as caught:
        validate(f'https://127.0.0.1:{fake.server_port}', TOKEN, timeout=5)
    assert 'tls' in str(caught.value).lower()


def test_validate_reports_a_rejected_token(fake):
    with pytest.raises(MolabError) as caught:
        validate(fake.origin, 'wrong-token-entirely', timeout=5)
    assert 'token' in str(caught.value).lower()


def test_validate_reports_a_server_that_is_not_marimo(fake):
    fake.status_needs_auth = False
    fake.status_payload = {'hello': 'world'}
    with pytest.raises(MolabError) as caught:
        validate(fake.origin, TOKEN, timeout=5)
    assert 'not marimo' in str(caught.value).lower()


def test_validate_reports_marimo_that_is_unhealthy(fake):
    fake.status_payload = dict(MARIMO_STATUS, status='degraded')
    with pytest.raises(MolabError) as caught:
        validate(fake.origin, TOKEN, timeout=5)
    message = str(caught.value)
    assert 'degraded' in message and 'marimo' in message.lower()


def test_validate_reports_a_timeout(fake):
    fake.status_delay = 1.5
    with pytest.raises(MolabError) as caught:
        validate(fake.origin, TOKEN, timeout=0.25)
    assert 'in time' in str(caught.value).lower()


def test_validate_rejects_an_empty_url_and_token(fake):
    with pytest.raises(MolabError):
        validate('', TOKEN)
    with pytest.raises(MolabError):
        validate(fake.origin, '   ')


# ---------------------------------------------------------------------------
# 3. the token never leaks
# ---------------------------------------------------------------------------

def test_the_token_never_reaches_the_browser_or_the_log(fake, make_proxy, logs):
    """Every path, happy and unhappy, is swept for the token."""
    seen = []

    # validate() failures, which are the ones that carry server detail.
    for url, token in ((fake.origin, TOKEN),
                       (fake.origin, 'wrong-token-entirely'),
                       (f'https://127.0.0.1:{fake.server_port}', TOKEN),
                       (f'http://127.0.0.1:{free_port()}', TOKEN),
                       ('not a url at all', TOKEN)):
        try:
            validate(url, token, timeout=3)
        except MolabError as exc:
            seen.append(str(exc))

    upstream = validate(fake.origin, TOKEN, timeout=5)
    seen.append(repr(upstream))
    seen.append(str(upstream.status))

    # `/headers` is deliberately absent: it is the fake's own mirror of the
    # upstream request, where the bearer token is *supposed* to appear.
    proxy = make_proxy(lambda: upstream)
    for path, method, body in (('/', 'GET', None),
                               ('/plain', 'GET', None),
                               ('/api/status', 'GET', None),
                               ('/missing', 'GET', None),
                               ('/echo', 'POST', b'{"a":1}')):
        status, head, payload = raw_headers(proxy, path) if method == 'GET' else (
            call(proxy, path, method=method, body=body,
                 headers={'Content-Type': 'application/json'}))
        seen.append(str(status))
        seen.append(head.decode('latin-1') if isinstance(head, bytes) else str(head))
        seen.append(payload.decode('latin-1'))

    # The unhappy proxy paths too: no upstream, and a refused sign-in.
    denied = make_proxy(lambda: upstream, authorize=lambda handler: False)
    empty = make_proxy(lambda: None)
    for server in (denied, empty):
        status, head, payload = raw_headers(server, '/')
        seen.extend([str(status), head.decode('latin-1'), payload.decode('latin-1')])

    # And a WebSocket, whose handshake is the one place a header is hand-rolled.
    sock = open_socket(proxy)
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall(
            f'GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{proxy.server_port}\r\n'
            f'Upgrade: websocket\r\nConnection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode())
        seen.append(read_head(sock).decode('latin-1'))
    finally:
        sock.close()

    seen.extend(logs)
    assert logs, 'the proxy should have logged something to sweep'
    for text in seen:
        assert TOKEN not in text, f'access token leaked into: {text!r}'
    # The fake, by contrast, was genuinely authenticated — so this is a real sweep.
    assert any('authorization' in headers for _m, _p, headers in fake.hits)


# ---------------------------------------------------------------------------
# 4-7. HTTP relay
# ---------------------------------------------------------------------------

def test_get_relays_status_body_and_content_type(fake, make_proxy):
    proxy = make_proxy(lambda: validate(fake.origin, TOKEN, timeout=5))

    status, headers, body = call(proxy, '/plain')
    assert status == 200
    assert body == b'hello from marimo'
    assert headers['Content-Type'] == 'text/plain; charset=utf-8'

    missing_status, _headers, missing_body = call(proxy, '/missing')
    assert missing_status == 404
    assert missing_body == b'{"error":"not found"}'


def test_hop_by_hop_headers_are_stripped_in_both_directions(fake, make_proxy):
    upstream = validate(fake.origin, TOKEN, timeout=5)
    proxy = make_proxy(lambda: upstream)

    status, headers, body = call(proxy, '/headers', headers={
        'TE': 'trailers',
        'Trailer': 'X-Nope',
        'Proxy-Authorization': 'Basic bogus',
        'Proxy-Connection': 'keep-alive',
        'Keep-Alive': 'timeout=99',
        'Cookie': 'sera_session=our-own-secret',
        'Referer': 'http://localhost:8877/notebook',
        'Origin': 'http://localhost:8877',
        'X-Forwarded-For': '10.0.0.1',
        'Accept-Encoding': 'gzip, br',
        'X-Kept': 'yes',
    })
    assert status == 200
    upstream_saw = json.loads(body)

    for banned in ('te', 'trailer', 'proxy-authorization', 'proxy-connection',
                   'keep-alive', 'referer', 'origin', 'x-forwarded-for'):
        assert banned not in upstream_saw, f'{banned} was forwarded to molab'
    # Our own session cookie must never reach a third party; theirs must.
    assert 'sera_session' not in upstream_saw.get('cookie', '')
    assert f'session_8080={SESSION_COOKIE}' in upstream_saw['cookie']
    assert upstream_saw['authorization'] == f'Bearer {TOKEN}'
    assert upstream_saw['accept-encoding'] == 'identity'
    assert upstream_saw['host'] == f'127.0.0.1:{fake.server_port}'
    assert upstream_saw['x-kept'] == 'yes'

    # Response direction: the fake's hop-by-hop noise does not come back.
    _status, index_headers, _body = call(proxy, '/')
    lowered = {k.lower() for k in index_headers}
    assert 'keep-alive' not in lowered
    assert 'trailer' not in lowered
    assert 'proxy-authenticate' not in lowered
    assert index_headers['X-Marimo'] == 'yes'


def test_csp_is_replaced_and_upstream_cookies_are_withheld(fake, make_proxy):
    proxy = make_proxy(lambda: validate(fake.origin, TOKEN, timeout=5))
    status, head, body = raw_headers(proxy, '/')

    assert status == 200
    assert b'marimo notebook' in body
    text = head.decode('latin-1').lower()
    assert 'set-cookie' not in text, 'the sandbox session must stay server side'
    assert 'x-frame-options' not in text, 'DENY would veto the very embed we want'
    assert text.count('content-security-policy:') == 1
    assert 'evil.example' not in text
    assert f"frame-ancestors 'self' {molab_proxy.PARENT_ORIGIN}" in head.decode('latin-1')


def test_post_relays_its_body(fake, make_proxy):
    proxy = make_proxy(lambda: validate(fake.origin, TOKEN, timeout=5))
    payload = json.dumps({'cell': 'run', 'code': 'x' * 5000}).encode()

    status, _headers, body = call(proxy, '/echo', method='POST', body=payload,
                                  headers={'Content-Type': 'application/json'})
    assert status == 200
    echoed = json.loads(body)
    assert echoed['length'] == len(payload)
    assert echoed['echo'] == payload.decode()
    assert echoed['content_type'] == 'application/json'


# ---------------------------------------------------------------------------
# 8. streaming
# ---------------------------------------------------------------------------

def test_a_stream_is_relayed_as_it_is_produced(fake, make_proxy):
    """A buffering proxy would hold `first` until the upstream finished."""
    proxy = make_proxy(lambda: validate(fake.origin, TOKEN, timeout=5))
    sock = open_socket(proxy)
    try:
        started = time.monotonic()
        sock.sendall(f'GET /stream HTTP/1.1\r\n'
                     f'Host: 127.0.0.1:{proxy.server_port}\r\n\r\n'.encode())
        buffer = b''
        while b'first' not in buffer:
            data = sock.recv(4096)
            assert data, 'proxy closed before sending anything'
            buffer += data
        first_seen = time.monotonic() - started

        assert fake.finished_at is None, 'upstream had already finished — we buffered'
        assert first_seen < STREAM_GAP / 2, f'first bytes took {first_seen:.2f}s'
        assert b'text/event-stream' in buffer

        while b'second' not in buffer:
            data = sock.recv(4096)
            if not data:
                break
            buffer += data
        assert b'second' in buffer
        assert fake.first_chunk_at is not None and fake.finished_at is not None
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# 9-10. front door
# ---------------------------------------------------------------------------

def test_a_refused_sign_in_is_403_json_and_never_touches_molab(fake, make_proxy):
    upstream = validate(fake.origin, TOKEN, timeout=5)
    before = len(fake.hits)
    proxy = make_proxy(lambda: upstream, authorize=lambda handler: False)

    status, headers, body = call(proxy, '/api/kernel/run', method='POST', body=b'{}')
    assert status == 403
    assert headers['Content-Type'] == 'application/json'
    assert json.loads(body)['error'] == 'not_signed_in'
    # Not a redirect: this renders inside an iframe, where a 303 shows nothing.
    assert 'Location' not in headers
    assert len(fake.hits) == before, 'the proxy contacted molab for an unsigned request'


def test_no_sandbox_yields_503_json(make_proxy):
    proxy = make_proxy(lambda: None)
    status, headers, body = call(proxy, '/')
    assert status == 503
    assert headers['Content-Type'] == 'application/json'
    payload = json.loads(body)
    assert payload['error'] == 'no_sandbox'
    assert 'sandbox' in payload['detail'].lower()


def test_the_proxy_binds_loopback_only(make_proxy):
    proxy = make_proxy(lambda: None)
    assert proxy.server_address[0] == '127.0.0.1'
    assert proxy.daemon_threads is True


# ---------------------------------------------------------------------------
# 11. WebSocket round trip
# ---------------------------------------------------------------------------

def test_websocket_round_trip_through_the_proxy(fake, make_proxy):
    upstream = validate(fake.origin, TOKEN, timeout=5)
    proxy = make_proxy(lambda: upstream)

    sock = open_socket(proxy)
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall(
            f'GET /ws?session_id=s-1&file=%2Fmarimo%2Fnotebook.py HTTP/1.1\r\n'
            f'Host: 127.0.0.1:{proxy.server_port}\r\n'
            f'Upgrade: websocket\r\nConnection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n'
            f'Cookie: sera_session=our-own-secret\r\n\r\n'.encode())
        head = read_head(sock).decode('latin-1')

        assert '101' in head.split('\r\n')[0]
        # The browser validates this against the real server, not against us.
        assert f'Sec-WebSocket-Accept: {ws_accept(key)}' in head
        assert 'set-cookie' not in head.lower()

        sock.settimeout(10)
        fp = sock.makefile('rb')
        for message in (b'hello kernel', b'x' * 500):
            sock.sendall(ws_frame(0x1, message, mask=True))
            opcode, payload = ws_read_frame(fp)
            assert opcode == 0x1
            assert payload == message

        sock.sendall(ws_frame(0x8, b'', mask=True))
        opcode, _payload = ws_read_frame(fp)
        assert opcode == 0x8
        fp.close()
    finally:
        sock.close()

    # The query string had to survive: marimo reads session_id and file off it.
    ws_hits = [(path, headers) for method, path, headers in fake.hits
               if path.startswith('/ws')]
    assert ws_hits, 'the fake never saw the upgrade'
    path, headers = ws_hits[-1]
    assert 'session_id=s-1' in path and 'file=' in path
    assert headers['authorization'] == f'Bearer {TOKEN}'
    assert 'sera_session' not in headers.get('cookie', '')
    assert headers['sec-websocket-key'] == key


def test_websocket_without_a_sandbox_is_a_clean_503(make_proxy):
    proxy = make_proxy(lambda: None)
    sock = open_socket(proxy)
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall(
            f'GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{proxy.server_port}\r\n'
            f'Upgrade: websocket\r\nConnection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode())
        head = read_head(sock).decode('latin-1')
        assert '503' in head.split('\r\n')[0]
    finally:
        sock.close()


def test_websocket_refuses_an_unsigned_upgrade_without_touching_molab(fake, make_proxy):
    """The one path that hands over a raw socket must be gated first, not last."""
    upstream = validate(fake.origin, TOKEN, timeout=5)
    before = len(fake.hits)
    proxy = make_proxy(lambda: upstream, authorize=lambda handler: False)

    sock = open_socket(proxy)
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall(
            f'GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{proxy.server_port}\r\n'
            f'Upgrade: websocket\r\nConnection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode())
        head = read_head(sock).decode('latin-1')
        assert '403' in head.split('\r\n')[0]
        assert 'sec-websocket-accept' not in head.lower()
    finally:
        sock.close()
    assert len(fake.hits) == before
