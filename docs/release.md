# Release status

Sera provides a local inference research service with a Python API and terminal commands.

- `sera setup` installs the hardware runtime, connects Codex ChatGPT login, registers models, checks and budgets, and starts the service with operator-owned W&B tracing.
- `sera.Optimize(description, examples=checks)` compiles a workload into bounded experiments. Registered document collections use `documents="collection"`.
- Astra coordinates 15 Luna specialists. The harness measures baselines and candidates, enforces acceptance gates, and exports the selected checkpoint.
- The result supports checkpoint verification and model loading. Service jobs support cancellation, request recovery, deadlines, and owned-process cleanup.
- NVIDIA ModelOpt supplies the CUDA quantization path. MLX supplies the Apple Silicon path.

## Verified runs

- [CUDA Qwen3-8B FP8](../evidence/managed-cuda-release-v1/release.json): 39.19% lower sampled device memory on NVIDIA L4, 6.39 GiB freed, repeated answer checks passed, fresh checkpoint reload, verified W&B trace.
- [MLX RAG](../evidence/managed-rag-release-v1/release.json): 100,000 synthetic records, selected INT8 checkpoint, 13 acceptance questions and 24 independent holdout questions passed, 40.87% lower generator allocator memory.
- [General workloads](../evidence/managed-workloads-release-v1/release.json): classification, extraction, and incident summarization selected verified checkpoints, with 39.82%, 62.26%, and 63.33% lower allocator memory.
- [Build and test record](../evidence/managed-workloads-release-v1/validation.json): source suite, installed-wheel checks, and Linux/macOS CI.
- [Restart and recovery](../evidence/managed-workloads-release-v1/lifecycle.json): saved authentication, service restart, and recovery of the same completed job.

Each evidence record identifies its source revision and measurement scope. The deployment target is a local service on the machine that runs inference. Automatic setup targets Apple Silicon and Linux NVIDIA hardware; ROCm uses a separate operator-configured runtime.
