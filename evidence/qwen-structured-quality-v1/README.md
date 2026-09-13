# Structured-output pilot: startup failed, quality not measured

Source revision: `04313eabbefbf9389024403f6d967268d2b52203`.
Model: pinned `Qwen/Qwen3-0.6B`, BF16, native JSON decoding.

The server failed before any of the eight questions ran. FlashInfer's CUDA compilation could not find `curand.h`. The header exists in the base Python environment, but the CUDA compiler was using the notebook virtual environment's include directory. The original server log and runtime record are preserved here.

GPU cleanup passed and returned memory to 0 MiB. The result's zero completed-task count is not an observed 0/8 answer score. No answer-quality or request-latency conclusion can be drawn from this attempt.

The later empty-token validation fix does not change this record: no responses were generated. A retry must use a new evidence directory and retain the same task profile.
