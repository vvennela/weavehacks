# Qwen baseline runtime check

Result: PASS for startup, nonempty generation, metrics availability, and GPU memory release. This is not completion of the first Sera milestone.

Run date: 2026-09-13 UTC. Runtime: Molab, NVIDIA RTX PRO 6000 Blackwell Server Edition, compute capability 12.0. Exact versions are in environment.json; model revision, flags, prompts, outputs, and timing are in result.json.

## Observations

- Startup reached readiness in 68.319 seconds; total check took 69.944 seconds.
- Three raw completion requests each returned 32 tokens and HTTP 200.
- The metrics endpoint returned HTTP 200 and vLLM metrics, saved in metrics.prom.
- Sampled GPU memory peaked at 88,303 MiB and returned to 0 MiB after shutdown. Sampling does not establish the exact peak.
- Logs show BF16 weights, automatic KV-cache precision, FlashAttention 2 attention, and FlashInfer sampling. FP8 was not requested.
- vLLM reserved about 84.05 GiB for KV cache under the fixed 0.90 memory fraction. This is not the model's weight footprint; logs report 1.12 GiB for loaded weights.
- Shutdown logged a forced worker termination and a semaphore cleanup warning. GPU cleanup passed; graceful worker shutdown and repeated lifecycle reliability are not established.

## Setup fix

Three prior startup attempts failed: compiler discovery, mismatched CUDA compiler and headers, then CUDA runtime linking. They remain saved in Molab under separate trial folders.

The working setup pins CUDA compiler, CRT, and NVVM to 13.0.88 and CCCL to 13.0.85, alongside CUDA runtime 13.0.96. The child process uses the installed compiler directory for CUDA_HOME and PATH. A trial-local libcudart.so symlink points to the installed libcudart.so.13; LIBRARY_PATH and LD_LIBRARY_PATH expose the library to the linker and loader. System CUDA files were not replaced.

The link probe passed before server launch. The exact notebook function used is saved in ../../experiments/vllm_smoke.py. It is an experiment function for the Molab runtime, not the Sera public runner. It writes to /marimo/sera-evidence and rejects an existing trial directory to protect evidence.

## Limits and next step

The arithmetic response was incorrect; other output also contains factual errors. Nonempty text is only a runtime smoke criterion. No task-quality or token-agreement gate was run. Cached model weights and prior compilation attempts were present, so this startup time is not a clean-install benchmark.

No FP8 configuration, candidate comparison, speedup, Weave trace, or usable returned Sera runner is established by this record. Next: a separate, bounded Qwen FP8 KV-cache check. Do not expand to GLM or agents yet.
