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

`/notebook` is the first page after sign-in. It has two tabs, and both run Sera's
real optimization loop — they differ only in what is underneath it.

**molab — Blackwell GPU.** Opens a molab notebook, where marimo provides a free
RTX Pro 6000 Blackwell (96GB, 125 TFLOPS) in a CoreWeave sandbox. Sera runs real
vLLM there, so every row is measured on hardware. This is what `specs/molab.yaml`
was written against.

It opens rather than embeds, deliberately. molab's embeddable `/app` view is a
read-only WebAssembly preview with no GPU and no session — iframing it would show
"Fork to edit and run your own code" and defeat the reason for using molab at all.
The tab is a launch panel with the setup steps; the read-only preview is available
behind a disclosure, and loads only when opened so nothing sits spinning.

Setting it up, once:

1. Push this branch, then on molab create a **synced notebook** from the GitHub
   URL of `notebooks/molab_lab.py`.
2. Open it and attach the GPU with the **notebook specs** button in the app header.
3. Press **Install Sera and vLLM**, then **Download weights**, then **Run**.
4. Start the site with the notebook's `/app` URL so the tab can embed it:

   ```bash
   SERA_MOLAB_URL=https://molab.marimo.io/notebooks/<id>/app python3 web/server.py
   ```

   Without it the molab tab is disabled and says so. The URL is served to the page
   by `/api/config`, behind the same session check as everything else.

**Local — simulator.** The WebAssembly build, which runs in your browser through
Pyodide against Sera's analytic model. Seconds rather than minutes, no GPU, no
weights, and no network once loaded — the fallback for when molab is unreachable,
the session has idled out, or the venue wifi has. Build it with:

```bash
scripts/build_notebook.sh
```

That writes `output/notebook/` (~28MB of vendored marimo runtime, gitignored),
served under `/notebook-app/` behind the session check, with every path resolved
to confirm it stays inside that directory. Its first load fetches Pyodide, numpy
and pyyaml from `cdn.jsdelivr.net`, which the export does not vendor, so open it
once on the demo machine while you have a connection and the browser caches it.

Timings on the GPU are honest rather than encouraging: a cold run is roughly
15-20 minutes for Qwen3-8B and 25-35 for the 14B and 16B models, because each
trial is a vLLM engine start plus CUDA graph capture. Weight downloads are a
separate button so the transfer stays out of the timed run, and trials stream in
as they land rather than appearing all at once at the end.

