# Sera local frontend

From the repository root, run `python3 web/server.py` and open
http://localhost:8877/. This serves the homepage and the authenticated lab preview.

Sign in with the demo login, shown on the sign-in page and printed at startup:

    demo@serademo.com / clustersss

It is seeded into the database on every start, so it survives a wiped or missing
database. Pass `--no-demo-account` to skip seeding it. For your own account use
**Sign in → Create an account**. Accounts are local to this Mac; no email
is sent. Passwords are salted and hashed with PBKDF2-SHA256.
Sessions use HttpOnly, SameSite cookies and expire after 24 hours. Signing out
revokes the current session. The ignored `.local/accounts.sqlite3` database is
outside the publicly served directory and preserves accounts across restarts.

The lab remains an interactive design preview; authentication does not execute
the optimization backend. Run the server instead of `python -m http.server` to
retain route protection and account endpoints. This server binds only to loopback.

## The notebook

`/notebook` is the first page after sign-in: a marimo notebook, exported to
WebAssembly, that runs Sera's real optimization loop in your browser. Pick one of
three open-weight models, press **Run**, and `Phase1.run()` executes against a
fresh ledger. The tables are built from that ledger, so re-running genuinely
re-measures rather than replaying anything.

The notebook embeds Sera's own source and unpacks it into the browser filesystem.
Sera is pure Python over numpy and pyyaml; the only module needing subprocess or
urllib is the vLLM runner, which is excluded from the bundle because nothing in
the Phase 1 path imports it.

Build it before demoing, because the export is not committed:

```bash
scripts/build_notebook.sh
```

That writes `output/notebook/` (~28MB of vendored marimo runtime, gitignored).
The server serves it under `/notebook-app/`, behind the same session check as the
rest of the workspace, resolving every path to confirm it stays inside that
directory. Until it is built, `/notebook-app/` answers 503 with the command to run.

**The first load needs internet.** Pyodide, numpy and pyyaml are fetched from
`cdn.jsdelivr.net` and are not vendored into the export. The browser caches them
afterwards, so open the notebook once on the demo machine while you have a
connection and later loads are local. Everything Sera-specific is already inside
the page.

A browser cannot reach a GPU, so the substrate is Sera's analytic simulator. The
loop, the specialists, the arbiter and the gates are the real ones; the thing
underneath them is a model rather than hardware, and the notebook says so. For
measured numbers, run `python -m sera --spec <spec> --vllm` on a GPU node.

