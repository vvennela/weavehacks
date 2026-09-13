# Qwen FP8 KV-cache runtime check

Result: PASS for startup, generation, metrics availability, and GPU memory release. This does not establish preserved task quality.

The same pinned Qwen3-0.6B model and isolated baseline flags were used, changing only `--kv-cache-dtype` from `auto` to `fp8`. vLLM selected FlashInfer attention. The server reached readiness in 58.255 seconds, completed three 32-token requests, and returned GPU memory to zero.

The raw outputs differ from the BF16 smoke outputs. No token-agreement or task-quality gate was applied to this smoke check. Logs warn that FP8 cache precision can reduce accuracy without a proper scaling factor; this run used the runtime defaults, without a separate calibration step.

Sampled peak memory was 88,669 MiB under the fixed 0.90 allocation fraction. This check does not claim a lower allocated-memory peak, faster inference, FP8 weight support, or GLM compatibility.

Exact flags and outputs are in result.json; kernel selection and warnings are in server.log. The runtime versions match the preceding BF16 check in ../qwen-baseline-cuda-link/environment.json. Task-level comparison follows separately in the frozen sera-task-v1 pilot.
