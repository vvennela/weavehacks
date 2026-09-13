"""Deterministic search-space suggestions; never starts trials itself.

Normal-mode suggestions are single-setting alternatives, not a Cartesian product.
Explicit spaces are preserved for the existing runtime validator to check later.
"""

from copy import deepcopy
import math

from .config import (InvestigationSpace, LARGE_MODEL_ID, MODEL_ID, RuntimeConfig,
                     Workload, resolve_investigation_space, CONTROL_ROLES)
from .runtime import GENERATION
from .storage import content_hash


def _number(value, upper=None):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    return value if upper is None or value <= upper else None


def _bucket(value):
    return max(128, 1 << (value - 1).bit_length())


def _load_evidence(baseline, workload, missing):
    loads = baseline.get('loads')
    if not isinstance(loads, list) or not loads:
        missing.append('No per-load before/after telemetry; queue and preemption evidence unavailable.')
        return []
    observations = []
    seen = set()
    for load in loads:
        if not isinstance(load, dict):
            missing.append('Malformed load telemetry ignored.')
            continue
        concurrency = load.get('concurrency')
        if type(concurrency) is not int or concurrency not in workload.concurrency or concurrency in seen:
            missing.append('Unknown or duplicate load concurrency ignored.')
            continue
        seen.add(concurrency)
        metrics = load.get('metrics') or {}
        metrics = metrics if isinstance(metrics, dict) else {}
        before, after = metrics.get('before-measurement'), metrics.get('after-measurement')
        before = before if isinstance(before, dict) else {}
        after = after if isinstance(after, dict) else {}
        first, last = _number(before.get('preemptions')), _number(after.get('preemptions'))
        delta = last - first if first is not None and last is not None and last >= first else None
        queue, kv = _number(after.get('mean_queue_ms')), _number(after.get('kv_cache_percent'), 100)
        if delta is None:
            missing.append(f'Load {concurrency}: preemption counters missing, invalid, or reset.')
        if queue is None:
            missing.append(f'Load {concurrency}: cumulative queue mean unavailable or invalid.')
        if kv is None:
            missing.append(f'Load {concurrency}: post-load KV snapshot unavailable or invalid.')
        observations.append(dict(concurrency=concurrency, preemptions_delta=delta,
            preemption_scope='difference between this load before/after counters',
            mean_queue_ms=queue, queue_scope='cumulative since startup; includes warmup and earlier loads',
            kv_cache_percent=kv, kv_scope='after-load snapshot, not an in-flight peak'))
    return observations


def propose_search_space(baseline, *, model_id, workload, explicit_space=None):
    """Return a serializable space plus reasons, or space=None when none is justified.

    Optimize uses this only with automatic_space=True. Calling it does not authorize trials.
    It never adds precision settings or alters a caller's explicit/frozen universe.
    """
    report = dict(policy_version='sera-evidence-space-v1', status='no-candidate', space=None,
                  candidates=[], evidence={}, rationale=[], missing_or_invalid=[],
                  limits=['Suggestions require existing runtime validation and trial authorization.',
                          'No quality or performance improvement is predicted by this policy.',
                          'No precision settings, combinations, or Cartesian products are generated.'])
    if explicit_space is not None:
        supplied = explicit_space.model_dump() if isinstance(explicit_space, InvestigationSpace) else explicit_space
        supplied = deepcopy(supplied)
        InvestigationSpace.model_validate(supplied)
        report.update(status='explicit-preserved', space=supplied)
        report['rationale'].append('Explicit values, order, and candidate-hash subset preserved unchanged; '
                                   'parent/workload legality remains the existing validator\'s responsibility.')
        return report
    if model_id not in {MODEL_ID, LARGE_MODEL_ID}:
        raise ValueError('Policy supports only the current single-model Qwen optimizer models')
    workload = Workload.model_validate(workload)
    missing = report['missing_or_invalid']
    try:
        values = baseline['runtime']['configuration']
        if not isinstance(values, dict) or set(values) != set(RuntimeConfig.model_fields):
            raise ValueError('Incomplete baseline configuration')
        config = RuntimeConfig.model_validate(values)
    except (KeyError, TypeError, ValueError):
        missing.append('A complete valid baseline configuration is required; no defaults were guessed.')
        return report
    recorded_model = baseline['runtime'].get('model_id')
    if recorded_model is not None and recorded_model != model_id:
        raise ValueError('Requested model differs from the recorded baseline')
    tokens = baseline.get('input_token_ids')
    if (not isinstance(tokens, list) or not tokens or any(
            not isinstance(row, list) or not row or any(type(token) is not int or token < 0 for token in row)
            for row in tokens)):
        missing.append('Valid nonempty baseline input token IDs are required; no lengths were guessed.')
        return report
    required = max(map(len, tokens)) + GENERATION['max_tokens']
    concurrency = max(workload.concurrency)
    evidence = dict(model_id=model_id, baseline_configuration_hash=config.config_hash,
                    input_token_ids_hash=content_hash(tokens),
                    max_input_tokens=max(map(len, tokens)), output_token_allowance=GENERATION['max_tokens'],
                    required_context_tokens=required, peak_declared_concurrency=concurrency,
                    declared_wave_token_envelope=required * concurrency,
                    wave_scope='planning envelope for declared requests, not measured engine batch occupancy',
                    kv_pressure_established=False)
    report['evidence'] = evidence
    if required > config.max_model_len or concurrency > config.max_num_seqs:
        missing.append('Recorded prompt length or declared concurrency exceeds the baseline limits.')
        return report
    observations = _load_evidence(baseline, workload, missing)
    evidence['loads'] = observations
    changes = {}

    def suggest(lever, value, reason):
        if value == getattr(config, lever):
            return
        try:
            candidate = RuntimeConfig.model_validate(config.model_dump() | {lever: value})
        except ValueError:
            missing.append(f'{lever}: suggested value conflicts with coupled runtime bounds.')
            return
        changes.setdefault(lever, []).append(value)
        report['candidates'].append(dict(changed={lever: value}, configuration=candidate.model_dump(),
                                         config_hash=candidate.config_hash, reason=reason))
        report['rationale'].append(reason)

    context = _bucket(required)
    if context <= config.max_model_len:
        suggest('max_model_len', context, 'Smallest bounded context bucket covering every input plus output allowance.')
    suggest('max_num_seqs', concurrency, 'Sequence limit matches the largest declared client concurrency.')
    batch_target = min(65536, _bucket(required * concurrency))
    preempted = any((row['preemptions_delta'] or 0) > 0 for row in observations)
    if batch_target < config.max_num_batched_tokens:
        suggest('max_num_batched_tokens', max(config.max_num_seqs, batch_target),
                'Lower batch-token limit covers the declared token-wave envelope; this is not a speedup claim.')
    elif preempted:
        lower = max(config.max_num_seqs, config.max_num_batched_tokens // 2)
        suggest('max_num_batched_tokens', lower,
                'Recorded preemption counter increase supports testing a smaller batch-token limit.')
    elif (concurrency > 1 and batch_target > config.max_num_batched_tokens
          and {row['concurrency'] for row in observations} == set(workload.concurrency)
          and len(observations) == len(baseline.get('loads', []))
          and all(row['preemptions_delta'] == 0 for row in observations)
          and any((row['mean_queue_ms'] or 0) > 0 for row in observations)):
        higher = min(batch_target, config.max_num_batched_tokens * 2, 65536)
        suggest('max_num_batched_tokens', higher,
                'Concurrent token demand exceeds the current batch limit; positive cumulative queue '
                'history and zero observed load preemption deltas support one larger-batch experiment. '
                'The queue mean is not a measured-window average.')
    else:
        report['rationale'].append('No larger-batch suggestion: demand, cumulative queue evidence, '
                                   'or complete zero-preemption load observations are insufficient.')
    if changes:
        space = InvestigationSpace(supported_changes=changes)
        resolved = resolve_investigation_space(space, baseline=config, model_id=model_id, workload=workload)
        report.update(status='generated', space=dict(supported_changes=changes,
                                                     candidate_hashes=resolved['candidate_hashes']))
    return report


def expand_search_space(baseline, trials, *, model_id, workload):
    """Generate the next normal-mode pool from actual outcomes, never a frozen benchmark.

    Single-control experiments retain the original reference as parent. A pairwise
    combination is allowed only when both constituent changes passed task quality
    in separate measured trials. Every full configuration is deduplicated.
    """
    seed = propose_search_space(baseline, model_id=model_id, workload=workload)
    report = dict(policy_version='sera-expanding-space-v1', status='no-candidate', space=None,
                  candidates=[], candidate_parents={}, rejected=[], rationale=[],
                  history_trial_ids=[trial['trial_id'] for trial in trials],
                  evidence=deepcopy(seed['evidence']), missing_or_invalid=seed['missing_or_invalid'],
                  limits=['Generated settings are experiments, not certified gains.',
                          'Original workload and quality requirements remain fixed.',
                          'Only independently quality-passing single changes can be combined.'])
    if 'required_context_tokens' not in seed['evidence'] or any(
            'exceeds the baseline' in message for message in seed['missing_or_invalid']):
        return report
    workload = Workload.model_validate(workload)
    base = RuntimeConfig.model_validate(baseline['runtime']['configuration'])
    base_values = base.model_dump()
    required = seed['evidence']['required_context_tokens']
    concurrency = max(workload.concurrency)
    base_id = baseline['trial_id']
    seen = {base.config_hash, *(trial['config_hash'] for trial in trials)}
    candidates = {}
    parents = {base_id: dict(configuration=base_values, component_trial_ids=[])}

    def add(parent_id, lever, value, *, components=(), reason):
        parent = parents[parent_id]['configuration']
        if type(parent[lever]) is type(value) and parent[lever] == value:
            return
        try:
            config = RuntimeConfig.model_validate(parent | {lever: value})
            if config.max_model_len < required or config.max_num_seqs < concurrency:
                return
            if model_id == LARGE_MODEL_ID and config.kv_cache_dtype != 'auto':
                return
        except ValueError:
            report['rejected'].append(dict(parent_trial_id=parent_id, changed={lever: value},
                                           reason='Runtime bounds or coupled settings are invalid.'))
            return
        if config.config_hash in seen or config.config_hash in candidates:
            return
        candidates[config.config_hash] = dict(config_hash=config.config_hash,
            configuration=config.model_dump(), parent_trial_id=parent_id,
            component_trial_ids=list(components), changed={lever: value}, reason=reason)

    # Execution alternatives are not hidden behind a claim of measured pressure.
    # The investigator must decide whether their test is useful for this workload.
    for lever in ('enforce_eager', 'enable_prefix_caching', 'enable_chunked_prefill'):
        add(base_id, lever, not base_values[lever], reason='Test a supported execution strategy; compatibility and gain remain unmeasured.')
    if model_id == MODEL_ID:
        add(base_id, 'kv_cache_dtype', 'fp8', reason='Test the supported small-model cache format under the fixed task gate.')
    for candidate in seed['candidates']:
        lever, value = next(iter(candidate['changed'].items()))
        add(base_id, lever, value, reason=candidate['reason'])

    # Outcomes add neighbors, including after a no-gain result. They never reset
    # the objective plateau counter merely by creating more choices.
    anchors = [baseline, *[trial for trial in trials if trial.get('status') == 'collected']]
    for trial in anchors:
        values = trial['runtime']['configuration']
        for lever in ('max_num_batched_tokens', 'max_num_seqs', 'max_model_len'):
            center = values[lever]
            neighbors = {center // 2, center * 2}
            if lever == 'max_num_batched_tokens':
                neighbors.add(max(base.max_num_seqs, center // 4))
            for value in sorted(neighbors):
                add(base_id, lever, value, reason=f'Explore a neighboring {lever} value around measured trial {trial["trial_id"]}.')
        fraction = values['gpu_memory_utilization']
        for value in (round(fraction - .05, 4), round(fraction + .05, 4)):
            # Do not generate an arbitrary tiny memory budget for a fit-first model.
            if value >= .5:
                add(base_id, 'gpu_memory_utilization', value,
                    reason=f'Test allocation headroom around measured trial {trial["trial_id"]}; fit remains subject to startup validation.')

    passing = []
    for trial in trials:
        if trial.get('status') != 'collected' or trial.get('task_quality', {}).get('passed') is not True:
            continue
        values = trial['runtime']['configuration']
        changed = {key: value for key, value in values.items() if value != base_values[key]}
        if len(changed) == 1 and next(iter(changed)) in CONTROL_ROLES:
            passing.append((trial, changed))
    for index, (left, left_change) in enumerate(passing):
        for right, right_change in passing[index + 1:]:
            if set(left_change) == set(right_change):
                continue
            parents[left['trial_id']] = dict(configuration=deepcopy(left['runtime']['configuration']),
                                             component_trial_ids=[left['trial_id']])
            lever, value = next(iter(right_change.items()))
            add(left['trial_id'], lever, value, components=[left['trial_id'], right['trial_id']],
                reason='Combine two independently measured, quality-passing changes; the combination must pass again.')
    changes = {}
    for candidate in candidates.values():
        lever, value = next(iter(candidate['changed'].items()))
        if value not in changes.setdefault(lever, []):
            changes[lever].append(value)
    report.update(candidates=list(candidates.values()), candidate_parents=parents)
    report['rationale'] = list(dict.fromkeys(candidate['reason'] for candidate in candidates.values()))
    if candidates:
        report.update(status='generated', space=dict(supported_changes=changes,
                      candidate_hashes=sorted(candidates)))
    return report
