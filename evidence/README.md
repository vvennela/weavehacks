# Release evidence

The current README cites these measured runs:

- [CUDA Qwen3-8B](managed-cuda-release-v1/): BF16 and ModelOpt FP8 on an NVIDIA L4.
- [Classification, extraction, and summarization](managed-workloads-release-v1/): native MLX workloads and checkpoint reloads.
- [RAG](managed-rag-release-v1/): document retrieval and generator optimization.
- [Qwen3-4B comparison](native-mixed-search-qwen3-4b-v1/): paired recipe comparison and held-out checks.
- [CPU observed peak and repeatability](cpu-best-kernel-repeatability-2026-09-25/): exact kernel source and repeated measurements.
- [72B deployment](large-fit-v1/): recorded large-model deployment.
- [Earlier serving result](openai-example-v2/): the historical serving result identified in the README.

## Research history

Every other directory is research history, including earlier approaches, unsuccessful trials,
provider checks, and CPU experiments. These records preserve provenance; they are not v1 product code.
The [archive index](research-history.json) lists compressed agent records, checksums, and original directories. Their measurement results stay at their original paths. Restore an archive with `tar -xzf evidence/<archive> -C <restore_directory>` using the paths in the index.
