# Sera CPU MatMul run

Status: running.

Goal: exceed 1,800 GFLOP/s on this M4 Pro under the unchanged single-threaded 512-square float32 hill. Three repeated official reports per source, paired with unchanged controls; one final held-out run. No best-of-repeats promotion. The hill itself retains its fixed best-of-three scoring rule.

Live state: search/result.json. Signed evaluator reports and source snapshots are in search/trial-*/. Codex prompts and responses are in agent/. This is a trusted local research run, not a sandboxed production service.

Status: completed. Target met: False.

- existing-sme: passed; scores=[1541.2532704114913, 1333.2842863403828, 1328.0665951598835]; controls=[]

Final GFLOP/s: 1533.1897399707996. Winner: /Users/vishnuv/Documents/Documents/weavehacks/evidence/cpu-libxsmm-reference-2026-09-24/baseline-run/search/trial-000/source/kernel.c
