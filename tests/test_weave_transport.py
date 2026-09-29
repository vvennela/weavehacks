"""The pinned Weave stack must accept the authentication object it creates."""

import pytest


def test_weave_graphql_transport_accepts_httpx_basic_auth():
    pytest.importorskip('weave')
    httpx = pytest.importorskip('httpx')
    transport_module = pytest.importorskip('gql.transport.httpx')
    transport = transport_module.HTTPXTransport(
        url='https://api.wandb.ai/graphql', auth=httpx.BasicAuth('api', 'fixture'))
    try:
        # Constructing the client makes no request. This catches incompatible
        # auth classes before a real key or a network connection is needed.
        transport.connect()
    finally:
        transport.close()
