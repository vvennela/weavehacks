def show_sera_public_api_release_result():
    import json
    from pathlib import Path
    import marimo as mo

    folder = Path('/marimo/sera-evidence/public-api-release-v1')
    record = json.loads((folder / 'rehearsal.json').read_text())
    return mo.md(f"""
## Installed Sera API: saved live result

**Runtime check passed. Task correctness failed.**

The installed package ran three Luna investigators for three rounds, measured three candidates,
stopped automatically, returned a usable runner, and released GPU memory on close.
No total trial cap was set.

This quick-mode check used one prompt. It measured agreement with the baseline, not truth.
The baseline answered `1 + 1` with `1`; the returned runner answered `2 + 2` with `2`.
Use the separate Qwen72B recordings for task-quality claims.

[Open the Weave trace]({record['weave_url']}). The saved export contains 175 calls and
41 typed agent responses. Caller generation and cleanup occurred after the root span ended.

This cell reads saved evidence. It does not start a GPU experiment.
""")

show_sera_public_api_release_result()
