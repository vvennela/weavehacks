# Sera demo

**Sera — the autonomous auto-research harness for inference.**

## Show the product

1. Run `sera setup`. Register a pinned model, quality checks, and a research budget. Setup connects Codex ChatGPT login, installs the hardware runtime, configures operator W&B tracing, and starts the local service.
2. Describe a workload: `sera optimize "Minimize memory for support-ticket classification" --examples checks.json`.
3. Open the W&B trace. Show the baseline, specialist proposals, measured candidates, and selection decision.
4. Show the returned checkpoint and measured memory savings. Load it with `result.load()` and run a fresh request.
5. Show a second workload: `sera.Optimize("Answer questions from our manuals using less memory", documents="manuals")`.

## Explain the value

“Sera turns an inference workload and a hardware budget into measured optimization experiments. Astra coordinates 15 specialists. Sera tests their proposals, checks output quality and performance, and returns a verified model that uses less memory. Teams use the same process to fit workloads on existing hardware and reduce inference capacity needs.”

## Show the results

- [CUDA Qwen3-8B on NVIDIA L4](../evidence/managed-cuda-release-v1/release.json): ModelOpt FP8 freed 6.39 GiB, a 39.19% reduction in sampled device memory. All eight answer checks passed across repeated measurements.
- [RAG over 100,000 synthetic documents](../evidence/managed-rag-release-v1/release.json): the MLX INT8 generator used 40.87% less allocator memory. All 13 acceptance questions and 24 independent holdout questions passed.

Use the saved evidence when presenting these measurements. A new live run produces its own result and trace. Check quality against workload-specific examples and name the memory metric being shown.

## Review the repository

[README](../README.md) · [Release status](../completion.md) · [CI](https://github.com/vvennela/weavehacks/actions/workflows/test.yml)
