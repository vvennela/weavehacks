"""Bind saved isolated measurements to the exact proposed shared-GPU plan."""

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from .measurement import reduce_loads, reduce_requests
from .runtime import GENERATION
from .storage import content_hash
from .placement_config import validate_placement_plan


def _require(condition, reason):
    if not condition:
        raise ValueError('Placement reference rejected: ' + reason)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _check_requests(requests, indices, input_tokens):
    _require(isinstance(requests, list) and len(requests) == len(indices), 'request count')
    for item, index in zip(requests, indices):
        _require(isinstance(item, dict) and type(item.get('prompt_index')) is int
                 and item['prompt_index'] == index, 'prompt index')
        _require(item.get('prompt_token_ids') == input_tokens[index], 'input tokens')
        _require(not item.get('error') and isinstance(item.get('text'), str) and bool(item['text'].strip()),
                 'request errors')
        tokens = item.get('token_ids')
        _require(isinstance(tokens, list) and bool(tokens) and all(type(token) is int and token >= 0 for token in tokens),
                 'output tokens')
        _require(item.get('finish_reason') in {'stop', 'length'} and _number(item.get('latency_ms')),
                 'incomplete request')
        usage = item.get('usage', {})
        _require(type(usage.get('prompt_tokens')) is int and usage['prompt_tokens'] == len(input_tokens[index])
                 and type(usage.get('completion_tokens')) is int and usage['completion_tokens'] == len(tokens),
                 'token usage')


def bind_placement_reference(path, plan, profiles):
    """Recompute gates and latency from saved requests; never trust a pass flag.

    Hashes identify local input artifacts. They do not authenticate who measured
    them; only records from a trusted measurement environment should be supplied.
    """
    from .placement import _gate
    source = Path(path).resolve()
    raw = source.read_bytes()
    record = json.loads(raw)
    expected_manifest = {model:profile.manifest() for model,profile in profiles.items()}
    _require(record.get('schema_version') == 'sera-placement-v1', 'schema')
    _require(record.get('plan_hash') == plan.plan_hash and validate_placement_plan(record.get('plan')).plan_hash == plan.plan_hash, 'plan binding')
    _require(record.get('workload_hash') == content_hash(expected_manifest)
             and record.get('workloads') == expected_manifest, 'workload binding')
    isolated = deepcopy(record.get('isolated', {}))
    _require(set(isolated) == set(profiles), 'both isolated models are required')
    gates = {}
    fingerprints = []
    for service in plan.services:
        model_id = service.model_id
        profile = profiles[model_id]
        trial = isolated[model_id]
        runtime = trial.get('runtime', {})
        _require(runtime.get('model_id') == model_id and runtime.get('revision') == service.revision,
                 'pinned model identity')
        _require(runtime.get('configuration') == service.configuration.model_dump()
                 and trial.get('config_hash') == service.configuration.config_hash, 'configuration binding')
        _require(runtime.get('cleanup_pass') is True and runtime.get('status') == 'closed', 'isolated cleanup')
        gpu, versions = runtime.get('gpu', {}), runtime.get('versions', {})
        _require(isinstance(gpu.get('uuid'), str) and bool(gpu['uuid'])
                 and gpu.get('total_mib', 0)*1024**2 == plan.physical_gpu_bytes, 'physical GPU binding')
        _require(versions.get('vllm') == '0.26.0' and all(isinstance(versions.get(name), str) and versions[name]
                 for name in ('torch', 'transformers', 'flashinfer-python')), 'runtime version binding')
        fingerprints.append(({key:gpu.get(key) for key in
            ('uuid', 'name', 'total_mib', 'compute_capability', 'driver')}, versions))
        peak = runtime.get('sampled_peak_memory_mib')
        _require(type(peak) is int and 0 < peak*1024**2 <= service.allocation_bytes
                 and runtime.get('telemetry_errors') == 0, 'isolated memory gate')
        count = len(profile.prompts)
        tokens = trial.get('input_token_ids')
        _require(isinstance(tokens, list) and len(tokens) == count and all(
            isinstance(row, list) and row and all(type(token) is int and token >= 0 for token in row)
            for row in tokens), 'input token manifest')
        _require(all(len(row)+GENERATION['max_tokens'] <= service.configuration.max_model_len for row in tokens),
                 'context limit')
        loads = trial.get('loads', [])
        _require([load.get('concurrency') for load in loads] == profile.workload.concurrency, 'load levels')
        _require(trial.get('workload', {}).get('concurrency') == profile.workload.concurrency, 'workload levels')
        requests, warmup = [], []
        for load in loads:
            _check_requests(load.get('warmup'), list(range(min(count, 16))), tokens)
            _check_requests(load.get('requests'), [i % count for i in range(min(3*count, 96))], tokens)
            window = load.get('measurement_window', {})
            started, ended = window.get('started'), window.get('ended')
            elapsed = load.get('reduced', {}).get('request_wall_seconds')
            _require(_number(started) and _number(ended) and ended > started and _number(elapsed)
                     and math.isclose(ended-started, elapsed, rel_tol=1e-6, abs_tol=1e-6), 'measurement window')
            recomputed = reduce_requests(load['requests'], elapsed)
            _require(recomputed == load.get('reduced'), 'raw load metrics do not match saved reduction')
            requests.extend(load['requests'])
            warmup.extend(load['warmup'])
        _require(trial.get('requests') == requests and trial.get('warmup') == warmup, 'request ledger binding')
        _require(trial.get('reduced') == reduce_loads(loads), 'raw aggregate metrics do not match saved reduction')
        _check_requests(trial.get('quality'), list(range(count)), tokens)
        _require(trial.get('self_check', []) == [] and trial.get('generation_errors') == 0, 'isolated protocol')
        gate = _gate(trial, profile, service)
        _require(gate['passed'], 'absolute task or latency requirements')
        gates[model_id] = gate | dict(memory_pass=True)
    _require(fingerprints[0] == fingerprints[1], 'isolated GPU/runtime identities differ')
    return dict(isolated=isolated, gates=gates,
                provenance=dict(path=str(source), sha256=hashlib.sha256(raw).hexdigest(),
                                plan_hash=plan.plan_hash, workload_hash=content_hash(expected_manifest),
                                weave_url=record.get('weave_url'), source='saved-isolated-measurements'))
