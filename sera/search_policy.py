"""Standalone deterministic search-space suggestions; never starts or enables trials.

Normal-mode suggestions are single-setting alternatives, not a Cartesian product.
Explicit spaces are preserved for the existing runtime validator to check later.
"""

from copy import deepcopy
import math

from .config import (InvestigationSpace, LARGE_MODEL_ID, MODEL_ID, RuntimeConfig,
                     Workload, resolve_investigation_space)
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

    This function is not wired into optimize. Calling it does not authorize trials.
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
        candidate = RuntimeConfig.model_validate(config.model_dump() | {lever: value})
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
