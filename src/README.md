# Legacy compatibility package

`sera_loop` preserves the earlier two-phase optimizer API and its tests.
The v1 product entry point is [`sera.Optimize`](../sera/managed_client.py), configured with `sera setup`.
This package remains installed for existing callers; it is not the v1 service implementation.
