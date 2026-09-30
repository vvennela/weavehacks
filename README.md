# Sera

**The autonomous auto-research harness for inference.**

Describe your workload. Sera tests inference optimizations on your hardware, reduces model memory, and returns a verified checkpoint that passes your quality and performance checks.

## What Sera does

- **Understands the workload:** classification, extraction, chat, summarization, translation, and document question answering.
- **Runs autonomous experiments:** Astra coordinates 15 Luna specialists, tests their ranked proposals, and keeps the best result within your budget.
- **Optimizes for your hardware:** native MLX on Apple Silicon and NVIDIA ModelOpt on CUDA.
- **Enforces your requirements:** required precision, quality checks, memory limits, speed limits, and experiment budgets.
- **Returns a usable model:** export, verify, and load the selected checkpoint. Every research run has a verified W&B trace.
- **Builds RAG from documents:** index a registered collection, retrieve evidence, and optimize the answering model against question-and-answer checks.

## Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install "git+https://github.com/vvennela/weavehacks.git"
sera setup
```

Setup installs the hardware runtime, connects your Codex ChatGPT login, registers models and checks, saves the operator's W&B configuration, and starts the local service. Credentials stay in private local files.

```python
import json
import sera

checks = json.load(open("checks.json"))
result = sera.Optimize("Minimize memory for support-ticket classification", examples=checks)

with result.load() as model:
    answer = model.generate(
        [{"role": "user", "content": "Classify this ticket: my package arrived broken"}],
        max_tokens=64, seed=0)
    print(answer["text"])
```

Use [these example checks](examples/classification-checks.json), or supply your own prompts and expected JSON answers. Plain-text tasks accept exact, required-text, forbidden-text, and word-count checks. Pass `documents="your-collection"` to optimize document question answering.

```bash
sera optimize "Minimize memory for ticket classification" --examples checks.json
sera status
sera stop
```

## Measured results

| Workload | Hardware | Result | Evidence |
| --- | --- | --- | --- |
| Qwen3-8B inference, ModelOpt FP8 | NVIDIA L4 | **39.19% less sampled device memory; 6.39 GiB freed.** All eight answer checks passed across repeated measurements. | [CUDA run](evidence/managed-cuda-release-v1/release.json) |
| RAG over 100,000 synthetic documents, INT8 | Apple M4 Pro, MLX | **40.87% less generator allocator memory.** All 13 acceptance questions and 24 independent holdout questions passed. | [RAG run](evidence/managed-rag-release-v1/release.json) |

These records include pinned models, measured baselines, selected checkpoints, and W&B traces. Quality is measured against the supplied checks. Device memory and MLX allocator memory are separate metrics.

[Linux/macOS CI](https://github.com/vvennela/weavehacks/actions/workflows/test.yml) runs the test suite, builds the wheel, and checks the installed package. [Release status](completion.md) · [Demo workflow](docs/production-demo-workflow.md)

[Apache 2.0 license](LICENSE). Third-party code and assets retain their existing notices.
