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
WebAssembly, that runs in the browser. Pick one of three open-weight models and
press **Run** to see Sera tune its serving configuration — every trial, every
revert, and the recommendation at the end.

Build it before demoing, because the export is not committed:

```bash
scripts/build_notebook.sh            # reuse the captured ledgers
scripts/build_notebook.sh --rerun    # re-measure the three specs first
```

That writes `output/notebook/` (~27MB of vendored marimo runtime, gitignored).
The server serves it under `/notebook-app/`, behind the same session check as the
rest of the workspace, resolving every path to confirm it stays inside that
directory. Until it is built, `/notebook-app/` answers 503 with the command to run.

The numbers shown are replayed from ledgers captured by `python -m sera`, and the
notebook states which substrate produced them. Today that is the analytic
simulator; re-capture with `--vllm` on a GPU node and the page relabels itself,
because the substrate is read from the ledger rather than hardcoded.
