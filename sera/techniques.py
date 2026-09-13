"""Version-pinned research catalog. A technique description is not execution authority."""

from copy import deepcopy


DOCS = 'https://docs.vllm.ai/en/v0.26.0/'
EXPERTISE = {
    'scheduling': 'Batching, queueing, shared-prefix reuse, and prefill/decode scheduling.',
    'memory_context': 'Weight and cache memory, context requirements, allocation, and fit constraints.',
    'output_quality': 'Execution latency, graph/kernel strategy, and preservation of measured task quality.',
}

# id, owner, controls, applicability, risk, documentation, implementation status
TECHNIQUES = (
    ('batch-budget', 'scheduling', ['max_num_batched_tokens'],
     'Compare neighboring budgets using prompt lengths, load and latency.',
     'Larger batches can increase token latency; smaller batches can reduce throughput.',
     'configuration/optimization/', 'implemented'),
    ('sequence-capacity', 'scheduling', ['max_num_seqs'],
     'Investigate queueing and useful concurrent capacity.',
     'More capacity than offered traffic may add no value; preserve declared load.',
     'configuration/conserving_memory/', 'implemented'),
    ('context-capacity', 'memory_context', ['max_model_len'],
     'Compare safe limits covering every input and the unchanged output allowance.',
     'A smaller limit does not itself prove less reserved memory; reject truncation.',
     'configuration/conserving_memory/', 'implemented'),
    ('gpu-allocation', 'memory_context', ['gpu_memory_utilization'],
     'Test allocation headroom or cache capacity against measured memory and preemptions.',
     'A lower allocation can prevent startup or cause preemptions; no fit guarantee.',
     'configuration/engine_args/', 'implemented'),
    ('prefix-reuse', 'scheduling', ['enable_prefix_caching'],
     'Inputs share prefixes and repeated prefill contributes latency.',
     'Report cache warmth and reuse; repeated test prompts are not general traffic.',
     'features/automatic_prefix_caching/', 'implemented'),
    ('chunked-prefill', 'scheduling', ['enable_chunked_prefill'],
     'Prompt processing and token generation compete within a batch.',
     'Disabling chunking requires batch tokens to cover maximum context.',
     'configuration/optimization/', 'implemented'),
    ('graph-execution', 'output_quality', ['enforce_eager'],
     'Compare eager and graph-enabled execution when launch overhead may matter.',
     'Graph capture adds startup work and memory; this exact GPU/build still needs a trial.',
     'design/cuda_graphs/', 'implemented'),
    ('kv-precision', 'memory_context', ['kv_cache_dtype'],
     'Long contexts or measured cache pressure justify testing cache precision.',
     'Only active model-specific formats are legal; task quality must pass again.',
     'features/quantization/quantized_kvcache/', 'implemented'),
    ('fp8-weights', 'memory_context', ['quantization'],
     'Original weights do not fit, or weight memory dominates.',
     'Current support is the separate fit-first online FP8 path, not a new search control.',
     'features/quantization/online/', 'fit-first-only'),
    ('int4-weights', 'memory_context', ['quantization'],
     'Weight capacity or bandwidth limits deployment.',
     'Needs a compatible same-model recipe, checkpoint and validated kernels.',
     'features/quantization/llm_compressor/int4/', 'adapter-required'),
    ('int8-w8a8', 'memory_context', ['quantization'],
     'An alternative on supported hardware only.',
     'vLLM 0.26.0 excludes compute capability >=10.0, including this Blackwell card.',
     'features/quantization/llm_compressor/int8_w8a8/', 'hardware-blocked'),
    ('partial-prefill', 'scheduling', ['max_num_partial_prefills', 'max_long_partial_prefills'],
     'Long and short prompts compete for prefill capacity.',
     'Inspect fairness and tail latency; requires chunked-prefill compatibility.',
     'api/vllm/config/scheduler/', 'adapter-required'),
    ('async-scheduling', 'scheduling', ['async_scheduling'],
     'CPU scheduling gaps leave GPU work waiting.',
     'Check scheduler interactions and exact-build support.',
     'api/vllm/config/scheduler/', 'adapter-required'),
    ('attention-backend', 'output_quality', ['attention_backend'],
     'Measurements indicate attention execution is worth investigating.',
     'Backend support depends on architecture, dtype, head size and exact GPU capability.',
     'design/attention_backends/', 'adapter-required'),
    ('graph-coverage', 'output_quality', ['cudagraph_mode', 'cudagraph_capture_sizes'],
     'Graph execution works but capture overhead or memory is excessive.',
     'Capture coverage must match actual batch shapes and backend support.',
     'design/cuda_graphs/', 'adapter-required'),
    ('ngram-speculation', 'output_quality', ['speculative_config'],
     'Generated text repeats spans from the input.',
     'Measure acceptance and verification overhead; no automatic speedup.',
     'features/speculative_decoding/n_gram/', 'adapter-required'),
    ('suffix-speculation', 'output_quality', ['speculative_config'],
     'Text repeats across input and generation history.',
     'Requires another dependency and controlled history/cache conditions.',
     'features/speculative_decoding/suffix/', 'adapter-required'),
    ('draft-speculation', 'output_quality', ['speculative_config'],
     'A compatible cheap draft can propose tokens the target often accepts.',
     'Extra model memory and vocabulary compatibility need validation.',
     'features/speculative_decoding/draft_model/', 'adapter-required'),
    ('weight-offload', 'memory_context', ['cpu_offload_gb'],
     'Host memory can relieve a GPU fit constraint.',
     'CPU-GPU transfer can dominate latency; the current runner fixes offload at zero.',
     'api/vllm/config/offload/', 'adapter-required'),
    ('kv-offload', 'memory_context', ['kv_transfer_config'],
     'Reusable prefix state exceeds GPU cache capacity.',
     'Requires host-resource measurement, a connector, and explicit reuse conditions.',
     'features/kv_offloading_usage/', 'adapter-required'),
)


def technique_catalog(supported_changes):
    result = []
    for identifier, owner, controls, applicability, risk, page, implementation in TECHNIQUES:
        active = ({key: deepcopy(supported_changes[key]) for key in controls
                   if supported_changes.get(key)} if implementation == 'implemented' else {})
        status = ('available-for-trial' if active else 'inactive-in-this-round') if implementation == 'implemented' else implementation
        result.append(dict(technique_id=identifier, owner=owner, controls=controls[:],
            applicability=applicability, risk=risk, source_url=DOCS + page,
            status=status, active_values=active))
    return result


def techniques_for(investigator, supported_changes):
    return [row for row in technique_catalog(supported_changes) if row['owner'] == investigator]


def specialist_shortlist(investigator, options, *, peer_hashes=()):
    """At most eight distinct options, favoring expertise and shared valid proposals."""
    controls = {control for _, owner, values, *_ in TECHNIQUES if owner == investigator for control in values}
    unique = {item['config_hash']: item for item in options}
    ranked = sorted(unique.values(), key=lambda item: (
        item['config_hash'] not in peer_hashes,
        not bool(controls.intersection(item['changed']))))
    return deepcopy(ranked[:8])
