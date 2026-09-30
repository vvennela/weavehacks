# v1 examples

Run `sera setup` once, then describe a workload and supply its quality checks:

```bash
sera optimize "Reduce memory for ticket classification" --examples examples/classification-checks.json
sera optimize "Reduce memory for invoice extraction" --examples examples/extraction-checks.json
sera optimize "Reduce memory for incident summaries" --examples examples/text-checks.json
```

Use [rag_intent.py](rag_intent.py) for a registered document collection.
Setup configures Codex ChatGPT login, the hardware runtime, and operator W&B tracing.

The older `latency.py`, `latency_then_throughput.py`, and `replay_saved_run.py` examples
preserve the legacy serving API. `optimize_cpu_kernel.py` is a separate CPU research example.
