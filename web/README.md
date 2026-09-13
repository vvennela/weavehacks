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

> **Verification status — 2026-09-13.** Everything in the *Local — simulator*
> subsection, and every route and auth claim above, was checked by running this
> server today (see "What was verified" at the end). The **molab connect form,
> the reverse proxy and the `/api/molab/*` endpoints described below were still
> being written when this was last edited** — that part is written in the
> conditional and is marked *(not yet verified here)*. Do not quote it as
> working until you have run it.

`/notebook` is the first page after sign-in. It has two tabs, and both run Sera's
real optimization loop — they differ only in what is underneath it.

### molab — Blackwell GPU

molab gives the notebook a free **NVIDIA RTX PRO 6000 Blackwell** in a CoreWeave
sandbox. Confirmed on the card today: **97887 MiB** VRAM, compute capability
**12.0** (`sm_120`), driver **595.71.05**, running **marimo 0.24.0 in edit mode**
— a real kernel, not an export. **vLLM 0.29.0** served **Qwen3-8B** on it, and a
completion came back in **587.9 ms for 40 tokens**. This is what
`specs/molab.yaml` was written against.

Full runbook, including the exact commands and the measured baseline sweep:
**[`docs/live-molab-setup.md`](../docs/live-molab-setup.md)**.

**On embedding — the earlier note in this file was wrong.** It said a molab
session cannot be embedded and that an iframe only ever gets a read-only
WebAssembly preview with no GPU. That is true of the *published app* URL,
`molab.marimo.io/notebooks/<id>/app`, which is a WASM export. It is **not** true
of the live sandbox at `sb-<id>.sb.molab.run`, which is a real marimo server with
the GPU attached.

What actually blocks a direct iframe is the sandbox's own CSP:

```
content-security-policy: frame-ancestors 'self' https://*.marimo.io https://sb-<id>-session.sb.molab.run
```

`http://localhost:<port>` is not in that list, so the browser refuses the frame —
silently, with only a console message. The fix is therefore a proxy, not a
downgrade to the read-only preview: the site serves a **root-mounted reverse
proxy on a second loopback port (default 8878)** and frames that instead. It has
to be mounted at the root of its own port rather than under a path prefix,
because marimo's client requests absolute paths (`/api/...`, `/assets/...`) and
opens its websocket to the origin root.

Authentication to the sandbox is by access token: requesting
`https://sb-<id>.sb.molab.run/?access_token=<TOKEN>` makes the server set a
`session_8080` cookie, and subsequent requests ride that cookie.

*(Not yet verified here.)* Once the connect endpoints land, the sandbox URL and
token are entered in the **connect** form on the molab tab rather than baked into
the environment, because attaching a GPU in molab's **notebook specs** UI mints a
**new sandbox URL and a new token** every time — so a hardcoded id is wrong by
the next attach. `SERA_MOLAB_URL` remains as the way to preset one. The molab
access token grants arbitrary code execution on the sandbox, so it must never be
committed.

Push Sera's notebook into the live kernel with:

```bash
MARIMO_TOKEN=<token> scripts/push_notebook_to_molab.sh --url https://sb-<id>.sb.molab.run/
```

It is idempotent — cells match by position, so a second run edits in place.

### Local — simulator

The WebAssembly build, which runs in your browser through Pyodide against Sera's
analytic model. Seconds rather than minutes, no GPU, no weights, and no network
once loaded — the fallback for when molab is unreachable, the session has idled
out, or the venue wifi has. Build it with:

```bash
scripts/build_notebook.sh
```

That writes `output/notebook/` (~28MB of vendored marimo runtime, gitignored),
served under `/notebook-app/` behind the session check, with every path resolved
to confirm it stays inside that directory. Its first load fetches Pyodide, numpy
and pyyaml from `cdn.jsdelivr.net`, which the export does not vendor, so open it
once on the demo machine while you have a connection and the browser caches it.

### Timings

Honest rather than encouraging. A cold run on the GPU is roughly 15-20 minutes
for Qwen3-8B and 25-35 for the 14B and 16B models, because each trial is a vLLM
engine start plus CUDA graph capture. Weight downloads are a separate button so
the transfer stays out of the timed run, and trials stream in as they land rather
than appearing all at once at the end.

For what a single served model actually does on this card — 69.71 output tok/s at
concurrency 1, rising to 450.15 at concurrency 8, with e2e p50 going 1837 ms →
2270 ms — see the measured table in `docs/live-molab-setup.md`.

## What was verified

Run today against this server, on a scratch port and a scratch database:

- Boots with no traceback; prints its URL and the demo login.
- `GET /` → 200.
- Unauthenticated: `/api/session`, `/api/config`, `/api/metrics` → 401;
  `/notebook`, `/lab`, `/designs` → 303 to `/sign-in`.
- `POST /api/sign-in` with `demo@serademo.com` / `clustersss` → 200
  `{"ok": true, "redirect": "/notebook"}`.
- Authenticated: `/notebook` → 200, and `/`, `/product`, `/solutions`, `/models`,
  `/resources`, `/lab`, `/lab/performance`, `/lab/models`, `/lab/trials`,
  `/designs`, `/api/session`, `/api/config`, `/api/metrics` all → 200.
  `/get-started` → 303 to `/notebook`, which is correct when signed in.
- Every stylesheet, script, icon and internal link referenced by
  `output/lab-notebook.html` resolves → 200.

Not verified, because it did not exist yet at the time of writing:
`--proxy-port`, the reverse proxy on 8878, and `/api/molab/*` (`/api/molab/status`
returned 404).
