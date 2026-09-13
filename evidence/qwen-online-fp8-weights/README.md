# Online FP8 weight compatibility

The cached pinned Qwen3-0.6B model ran with vLLM 0.26.0, BF16 KV, and `--quantization fp8_per_tensor` on the supplied sm_120 GPU. Startup took 41.213 seconds. Three completion requests returned nonempty output, metrics were available, and cleanup returned GPU memory to 0 MiB.

This is a kernel and lifecycle check, not a task-quality pass. One completion said two plus two equals five. It also does not establish Qwen2.5-72B fit or quality; that requires its own run.

The installed online FP8 loader creates meta-device weight placeholders and processes layers while loading. This avoids assuming that the complete BF16 model must first reside on the GPU. Source inspection and the small runtime check support a bounded large-model trial, not a guarantee that it will succeed.
