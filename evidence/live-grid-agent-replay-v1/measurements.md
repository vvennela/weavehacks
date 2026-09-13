# Frozen configuration measurements

Complete universe: True. Search claim: not assessed.

Request latency covers repeated prompts after per-load warmup. Startup is separate.

| Configuration | Changes from baseline | Status | Task score | Worst p95 ms | Per-load p95 ms | Peak MiB | Startup s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sera-fp8-weight-reference-v1 | named baseline | completed | 1.0 | 770.6823209991853 | 1: 572.1306430023105, 2: 648.2719099985843, 4: 725.678558999789, 8: 770.6823209991853 | 88687 | 68.07289270299952 |
| fa106b43532b | enforce_eager=False | completed | 1.0 | 765.6131900002947 | 1: 570.7280129972787, 2: 646.3642160015297, 4: 718.3574529990437, 8: 765.6131900002947 | 88347 | 81.08243679700172 |
| db44d4ab0777 | max_num_batched_tokens=2048 | completed | 1.0 | 770.4568759982067 | 1: 571.9249549983942, 2: 647.7920239995001, 4: 726.5452250030648, 8: 770.4568759982067 | 88561 | 68.07246891500108 |
| 595475b749e9 | enable_prefix_caching=True | completed | 1.0 | 625.7277270015038 | 1: 557.8476510017936, 2: 617.4534900019353, 4: 625.7277270015038, 8: 618.179508997855 | 88431 | 67.07289243200285 |

Full configurations and hashes are in bundle.json and outcomes.json.
A complete table establishes measurements, not agent search superiority.
