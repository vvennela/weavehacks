# Structured-output retry: startup failed, quality not measured

Source revision: `2dc88cc5ed8d93c18cd4ca7b2113f93a7726f4fd`.
Same pinned BF16 Qwen model, eight questions, and structured-decoding profile as attempt one.

The cuRAND header was found, but compiler include precedence selected the base environment's CUDA 13.3 compiler header with the virtual environment's CUDA 13.0 compiler. The resulting `__cudaLaunch` macro mismatch stopped FlashInfer compilation before any questions ran. Cleanup passed and GPU memory returned to zero.

The result and runtime record are unchanged exports. `runtime/compiler-error.json` contains an exact error excerpt and SHA-256 hash of the full 4.5 MB repetitive log. The full log remains at the recorded Molab path. Zero completed answers is not an observed task score.

The separate [compile-only check](../cuda-header-order-v1/README.md) reproduced and resolved the include-order error without launching a model.
