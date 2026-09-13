# Demo workspace handoff

Local preview: http://localhost:8877/lab

Copy is updated. Logo, colors, fonts, and the marketing animation are preserved.
The workspace now has only Overview, Workflow, and Trial ledger.
No production deployment or notebook connection was changed.

## Changes for Barrat

- Marketing pages now describe the scheduling, memory/context, and output-quality investigators.
- Model cards distinguish Qwen2.5-72B FAST_START from the separate Qwen0.6B + GLM9B sharing test.
- The evidence panel shows the measured 771.05 → 618.59 ms result and links its Weave trace.
- Setup distinguishes the free-to-view replay/simulator from GPU and hosted model usage.
- All workspace views use the same audited Qwen72B GPU demo recording, not the simulator ledger.
- Account copy no longer says that a hosted account is stored on the visitor's Mac.

## Routes and assets for deployment

- `/lab` → `output/sera-lab-preview.html`: Overview, with the 19.77% measured p95 gain.
- `/notebook` → `output/lab-notebook.html`: Workflow, with Recorded loop / Run notebook tabs.
- `/lab/trials` → `output/sera-lab-preview.html`: four trials, proposals, and arbiter decisions.
- Both workspace pages load the new `output/sera-workspace.js`.
- Ship `output/sera-demo-replay.js` and `output/sera-demo-replay.css` for the native
  replay player. The replay has no iframe or second page header. The live Molab
  notebook remains an external embed in its own tab.
- Ship `output/demo-run.json` and `output/demo-replay.html` as static assets.
- Allow the specific public `/demo-run.json` file through the deployment's static-file allowlist.
  The local server change demonstrates this without exposing arbitrary JSON files.

The new notebook tab reads the existing `/api/config` field `molab_url`.
Keep that field pointed at the Cloudflare Worker. No new connection API is needed.
The old `sera-notebook.js` and `sera-lab.js` are no longer loaded by workspace pages;
do not carry their simulator UI or local-relay connector into the new pages.
Keep the current sign-in/session protection on the three workspace routes.

The no-GPU message must say that FAST_START stops, not that it simulates.
Setup must say: clone `notebooks/FAST_START.py`, select a GPU, enter keys in the
private clone, then Shift+Enter on Run 1 or Run 2. Their replay downloads appear
after each run. Never publish a shared notebook with active API keys.

Barrat owns the Worker target update. Use the current FAST_START sandbox URL and
pairing token through the Worker deployment's secret configuration, not in Git.
The workspace displays `openai-example-v2`, a saved recording. Running the notebook
does not replace that recording or import its new results into the overview.
The notebook's own report and replay remain the source for a new run.

## Local checks

`uv run --frozen --extra dev pytest -q tests/test_website_copy.py tests/test_demo_workspace.py tests/test_molab_proxy.py`

The copy, demo-record consistency, static-file serving, and local proxy checks pass:
41 tests. JavaScript syntax checks pass. The recorded-loop controls also pass their
two Node tests. Nothing has been pushed or deployed from this review.
