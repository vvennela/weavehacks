# Sera candidate catalog and expanding search

Status: implemented normal-mode expansion, pending live validation of the expanded loops. The executable catalog in `sera/techniques.py` contains 20 families with version-pinned vLLM 0.26.0 sources. Catalog inclusion does not mean a technique is executable or validated on this model and GPU.

## What changed

The previous normal-mode generator produced a fixed two-choice pool for the saved Qwen72B workload. `expand_search_space` now runs again after outcomes. It generates neighboring values, records rejected settings and attempted hashes, and combines two independently measured, quality-passing changes. Each combination retains its component trial IDs and must pass again against the original baseline.

The proposal schema supports eight controls: batch-token limit, sequence limit, context limit, FP8 KV, prefix caching, chunked prefill, eager/graph execution, and GPU memory fraction. Qwen72B still blocks FP8 KV with its current FP8-weight runner. Weight FP8 remains a separate fit-first decision. Tensor parallelism remains one.

Each of the three specialists receives up to eight distinct legal candidate options, weighted toward its expertise. Refinement can include peer proposals. The arbiter selects an experiment; eight options is not eight GPU trials. Separate Luna and Astra swarms use the same workload, gates, and capabilities. Three investigators run concurrently within each swarm; their GPU runs are sequential. Frozen benchmark runs remain fixed. Normal-mode stopping remains uncapped plateau plus one confirmation, not proof of global optimality.

## Broad catalog

These are optimization families, not an exhaustive list of every engine flag. A candidate is a complete executable configuration with provenance, not merely the word “quantization.” Status describes Sera today, not all vLLM installations.

| Family | Candidate examples | Evidence needed before selection | Sera status |
| --- | --- | --- | --- |
| Weight precision | BF16 reference, FP8, compatible INT8, compatible INT4 | Fit estimate, checkpoint/kernel compatibility, task scores | Online FP8 fit-first works; other formats need adapters and validation |
| KV-cache precision | BF16/auto versus compatible FP8 | Cache pressure, context requirements, task scores | Typed control; disabled for Qwen72B combination |
| Batch-token budget | Smaller/larger values around measured settings | Input lengths, queueing, preemptions, request timing | Typed control; refreshed neighbors |
| Sequence capacity | Values around useful concurrency, within memory limits | Offered traffic and memory pressure | Typed control; current validator requires capacity at least maximum client concurrency |
| Context capacity | Several safe buckets covering required input plus output | Declared maximum context, tokenized inputs, runtime support | Typed control; 256 failed startup on the saved Qwen72B run |
| Prefix reuse | Prefix caching off/on | Real shared prefixes and cache-hit measurements | Typed and wired; saved evidence labels repeated prompts after warmup, not cold-cache traffic |
| Prefill scheduling | Chunked prefill off/on; compatible token budgets | Input-processing versus token-generation timing | Typed and wired; disabling requires batch tokens at least the context limit |
| GPU cache allocation | Memory fraction or explicit KV allocation | Available memory, workspace, co-tenants, peak use | Memory fraction is typed and wired; explicit KV allocation needs an adapter |
| Compilation and CUDA graphs | Eager versus compatible compiled/graph execution | Startup cost, steady-state timing, memory overhead | Typed and wired; live compatibility and gain still require a trial |
| Kernel/backend choice | Supported attention or quantized linear backend | Exact model/build/GPU compatibility and measurements | Not exposed; separate engineering work |
| Speculative generation | No speculation; compatible draft model; supported prompt-lookup method | Draft acceptance, token-generation cost, extra memory | Not exposed; requires runtime and metric work |
| Tensor parallelism | One model split across 2, 4, or 8 GPUs | GPU count, interconnect, fit and latency | Fixed at one; unavailable on the current single GPU |
| Replica count | Independent model copies with request routing | Throughput target, per-replica fit, queueing | Not implemented; needs multi-GPU serving/routing |
| Layer/expert distribution | Pipeline parallelism; expert parallelism for a compatible MoE model | Model architecture, topology, transfer cost | Outside MVP; not applicable to every model |
| Two-model placement | Device assignment; per-service memory/KV allocation | Each service's task gates and measured interference | Separate phase-two path, not current single-model search |
| Memory offload | Supported weight or KV offload | Host memory, transfer bandwidth, end-to-end latency | Not enabled; needs adapter and system measurement |
| Startup reuse | Cached model files, reusable compilation artifacts, persistent service | Startup breakdown and session duration | Files cached; restart cost remains; not a request-latency gain |
| Host/request path | Tokenizer workers, CPU placement, queue admission, connection reuse | CPU and client/server timing breakdown | Outside current candidate schema |
| Cross-engine plan | Equivalent supported vLLM versus SGLang runtime | Same workload/gates, separate engine adapter | Architecture extension; not a current fallback claim |
| Model/provider choice | Smaller model, cascade, hosted endpoint | Explicit permission to change model or execution location | Changes the user contract; never a hidden optimization |

vLLM documents weight-format support as implementation- and hardware-dependent. Its matrix is not proof of this GPU's compatibility. [Quantization](https://docs.vllm.ai/en/stable/features/quantization/). Cache precision needs its own checks. [Quantized KV cache](https://docs.vllm.ai/en/stable/features/quantization/quantized_kvcache/).

Batching, prefill scheduling, compilation, and parallelism are workload-dependent choices, not guaranteed wins. [Optimization and tuning](https://docs.vllm.ai/en/stable/configuration/optimization/). Context, batch size, graph memory, and cache allocation interact with memory use. [Conserving memory](https://docs.vllm.ai/en/stable/configuration/conserving_memory/).

Prefix caching avoids recomputing shared input prefixes; it does not directly accelerate generation of new tokens. [Prefix caching](https://docs.vllm.ai/en/stable/features/automatic_prefix_caching/). Speculative generation uses a proposer and verification; usefulness depends on workload and compatibility. [Speculative decoding](https://docs.vllm.ai/en/stable/features/speculative_decoding/). The final four rows also include Sera architecture proposals, not claims that these paths are currently implemented.

## Search contract

1. **Discover capabilities.** Record model revision, installed engine, GPU topology, compatible formats, memory, and tested failures. Mark each family supported, unverified, incompatible, or outside the user's contract. Do not treat a missing measurement as zero.
2. **Generate a small working set from the catalog.** Use current measurements and declared requirements. Batch budgets can get lower and upper neighbors; context can get multiple safe buckets. Do not launch their full Cartesian product.
3. **Ask three investigators to investigate different bottlenecks.** Each can request evidence and propose an existing candidate or a typed new value within supported bounds. Each must cite its parent trial, evidence, hypothesis, expected cost, and falsification condition. They need not invent different answers when the evidence agrees.
4. **Validate before ranking/execution.** Check capability, memory and context requirements, configuration hash, previous attempts, and source citations. Reject invented flags and unsafe values before starting a server. An arbiter chooses which valid experiment is worth running; it can abstain with a scoped reason.
5. **Update the search after every outcome.** A useful result can open neighboring values. A quality failure closes that configuration. A startup failure records the failed build/configuration combination; it does not establish that a whole optimization family is bad. Explicitly separate causal hypotheses from observed error messages.
6. **Compose proven changes.** Once isolated changes pass, form a combination with all parent trial IDs and re-test it. Retain the original reference for comparisons. Do not assume two individually useful changes remain useful together.
7. **Stop with a scoped explanation.** Preserve the requested no-progress plus one-confirmation rule. Before declaring no useful alternatives, record which relevant families were considered, blocked, or still unexplored. A tiny empty working set is not global optimality. A failed startup is not a measured plateau. A new search neighborhood must not reset plateau counters unless a measured result qualifies as progress.

The catalog is broad; the active working set is small and replenished. This avoids both a fixed two-choice menu and an unaffordable full grid. Deterministic rules provide legal bounds; investigator hypotheses provide prioritization. No new orchestration service is required for this first change.

## Implementation limits

Normal mode persists a versioned candidate ledger and refreshes neighbors each round. It deduplicates full configurations within the run, including failed attempts. It does not yet import failure history from earlier runs or compose more than two changes. Runtime bounds, declared load, quality, and output requirements remain enforced.

Our eight-question workload measures repeated prompts after per-load warmup. Prefix-cache gains on this traffic must not be presented as gains on unseen cold inputs. Saved trial and Weave metric records label this scope. Graph execution adds startup and memory risks. INT8 W8A8 is hardware-blocked on this Blackwell card according to the version-pinned catalog source; other unimplemented formats, speculation, offload, and multi-GPU execution remain unavailable to proposals.

Acceptance checks for the expanding generator:

- New legal candidates appear after measured feedback without a supplied human value list.
- No duplicate configuration runs because it has a new proposal name.
- Known failed configurations are not silently retried in the same environment.
- Fixed benchmark universes never expand.
- Failed quality, unsupported precision, or insufficient context cannot pass through generation.
- Stop records distinguish agent abstention, candidate exhaustion, startup blockage, and measured no-progress confirmation.
- Saved evidence shows the generated pool, rejected options, selected experiment, and next pool.

Do not add more live benchmarks to compensate for a missing generator. Test generation and state transitions locally first. Then run one unchanged workload through the new loop and report its actual choices.

## ARIA's role

ARIA can recommend and run experiments through W&B Launch; that documented path needs a job, queue, and Launch agent connected to compute. It is not an automatic connection to the existing Molab kernel. [ARIA autoresearch](https://docs.wandb.ai/aria/autoresearch).

A practical later design is ARIA as a research planner above Sera: it reads reports, proposes a next search plan, and submits it to Sera's typed validator and executor. The W&B MCP server exposes data-query and report tools; those tools are not themselves an API for invoking ARIA as a model. [W&B MCP server](https://docs.wandb.ai/platform/mcp-server). No ARIA connection or Launch resources were created for this comparison.

The earlier saved Luna/Astra comparisons used the old two-choice pool. They do not validate the expanded implementation. New runs must use the new schema certificate (34 provider cases), separate output folders, and the same unchanged workload and gates.
