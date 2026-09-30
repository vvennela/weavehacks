# Competition review

**Sera — the autonomous auto-research harness for inference.**

Sera runs as a local service. `sera setup` installs the hardware runtime, connects Codex ChatGPT login, registers models and checks, configures operator W&B tracing, and starts the service. `sera.Optimize` runs bounded experiments and returns a verified checkpoint.

## Review in this order

1. [README](../README.md): features, setup, and measured results.
2. [CUDA result](../evidence/managed-cuda-release-v1/release.json): ModelOpt FP8 freed 6.39 GiB on NVIDIA L4, with repeated answer checks passing.
3. [General workload results](../evidence/managed-workloads-release-v1/release.json): classification, extraction, and incident summarization, with up to 63.33% lower allocator memory.
4. [RAG result](../evidence/managed-rag-release-v1/release.json): 100,000 synthetic documents, 40.87% lower generator allocator memory, and separate holdout checks.
5. [W&B project](https://wandb.ai/vvennela-n-a/wandb_agent_default_project): experiment traces and measured decisions.
6. [Linux/macOS CI](https://github.com/vvennela/weavehacks/actions/workflows/test.yml), [Apache 2.0 license](../LICENSE), and [release status](../completion.md).

## Present

Show the workload, quality checks, and budget. Start Sera, open the W&B trace, show the selected checkpoint and memory savings, then load the checkpoint for a request. Use the [demo workflow](production-demo-workflow.md).

## Submit

Every team member signs in to AGI House. One person creates the project on the [Part 2 event page](https://agihouse.org/events/coreweave-hacks-part-2-fully-connected), links the repository and W&B project, uploads the presentation, and chooses **Submit Project**. Verify **Submitted** on the platform. The organizer email specifies midnight PT as September 29 ends. Check in by October 1 at 4:15 p.m. PT, in person or through the supplied Zoom link.
