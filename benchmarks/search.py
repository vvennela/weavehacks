"""Frozen saved-outcome replay. No inference, provider calls, or product selection."""

from copy import deepcopy
import json
import math
import random
import re
import statistics
import time

from sera.config import BASELINE_NAME, MODEL_ID, RuntimeConfig
from sera.storage import content_hash


IDENTITY_HASHES = (
    'workload_hash', 'input_token_ids_hash', 'profile_hash', 'generation_hash',
    'quality_gate_hash', 'measurement_hash', 'hardware_hash', 'runtime_hash',
)


class StopSearch(Exception):
    """A policy deliberately abstains; this is not an invalid proposal or GPU trial."""


def _hash(value, length=64):
    return isinstance(value, str) and re.fullmatch(f'[0-9a-f]{{{length}}}', value) is not None


def _identity(identity):
    required = {'model_id', 'model_revision', 'tokenizer_revision', 'profile_name', *IDENTITY_HASHES}
    if (set(identity) != required or identity['model_id'] != MODEL_ID
            or not _hash(identity['model_revision'], 40)
            or not _hash(identity['tokenizer_revision'], 40)
            or not isinstance(identity['profile_name'], str) or not identity['profile_name'].strip()
            or any(not _hash(identity[key]) for key in IDENTITY_HASHES)):
        raise ValueError('Invalid benchmark identity; all pinned identity hashes are required')


def _config(config):
    return RuntimeConfig.model_validate(config)


def _entry(config, candidate_id=None):
    config = _config(config)
    return {'candidate_id': candidate_id or config.config_hash,
            'configuration': config.model_dump(), 'config_hash': config.config_hash}


def _config_order(entry):
    return json.dumps(entry['configuration'], sort_keys=True, separators=(',', ':'))


def freeze_manifest(identity, baseline, candidates, *, budget, evidence_kind='measured',
                    compatibility=None, random_seeds=tuple(range(20)), max_proposals=32):
    """Call and save before outcome collection. Only memory fraction may alter baseline."""
    _identity(identity)
    baseline = _config(baseline)
    if baseline != RuntimeConfig(gpu_memory_utilization=baseline.gpu_memory_utilization):
        raise ValueError('Named baseline may override only its declared memory fraction')
    candidates = [_entry(config) for config in candidates]
    if not 2 <= len(candidates) <= 12:
        raise ValueError('Freeze 2 to 12 nonbaseline candidates')
    if type(budget) is not int or not 1 <= budget <= 8 or budget >= len(candidates):
        raise ValueError('Trial budget must be 1..8 and smaller than the nonbaseline universe')
    if (type(max_proposals) is not int or not budget <= max_proposals <= 128
            or evidence_kind not in {'measured', 'test-fixture'}):
        raise ValueError('Invalid proposal limit or evidence kind')
    seeds = list(random_seeds)
    if len(seeds) != 20 or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != 20:
        raise ValueError('Freeze exactly 20 distinct integer random seeds')
    compatibility = dict(compatibility or {})
    if any(not _hash(value) for value in compatibility.values()):
        raise ValueError('Compatibility records require content hashes')
    seen = {baseline.config_hash}
    for candidate in candidates:
        if candidate['config_hash'] in seen:
            raise ValueError('Duplicate or baseline candidate configuration')
        seen.add(candidate['config_hash'])
        values = candidate['configuration']
        changed = {key for key, value in values.items() if value != baseline.model_dump()[key]}
        if not changed <= {'quantization', 'kv_cache_dtype', 'max_num_seqs', 'max_num_batched_tokens',
                           'enable_prefix_caching', 'enable_chunked_prefill', 'enforce_eager'}:
            raise ValueError('Candidate changes fixed workload or hardware settings')
        for mode, enabled in [('weights-fp8', values['quantization'] is not None),
                              ('kv-fp8', values['kv_cache_dtype'] == 'fp8'),
                              ('weights-and-kv-fp8', values['quantization'] is not None
                               and values['kv_cache_dtype'] == 'fp8')]:
            if enabled and mode not in compatibility:
                raise ValueError(f'Missing passed compatibility evidence hash for {mode}')
    manifest = {
        'schema_version': 'sera-search-replay-v1', 'identity': deepcopy(identity),
        'baseline': _entry(baseline, BASELINE_NAME),
        'candidates': sorted(candidates, key=_config_order), 'budget': budget,
        'evidence_kind': evidence_kind, 'compatibility': compatibility,
        'random_seeds': seeds, 'max_proposals': max_proposals,
        'objective': 'min-p95-latency-then-peak-memory', 'near_oracle_fraction': 0.05,
    }
    return {**manifest, 'manifest_hash': content_hash(manifest)}


def _finite(value, *, zero=False):
    return type(value) in (int, float) and math.isfinite(value) and (value >= 0 if zero else value > 0)


def _valid(record):
    return record['status'] == 'completed' and all(record[key] for key in (
        'feasibility_passed', 'reliability_passed', 'quality_passed'))


def _validate(manifest, artifacts, *, require_complete=True):
    expected = freeze_manifest(
        manifest['identity'], manifest['baseline']['configuration'],
        [entry['configuration'] for entry in manifest['candidates']],
        budget=manifest['budget'], evidence_kind=manifest['evidence_kind'],
        compatibility=manifest['compatibility'], random_seeds=manifest['random_seeds'],
        max_proposals=manifest['max_proposals'],
    )
    if manifest != expected:
        raise ValueError('Manifest hash, baseline, order, or frozen settings do not match')
    entries = {entry['candidate_id']: entry for entry in [manifest['baseline'], *manifest['candidates']]}
    outcomes = {}
    required = {
        'manifest_hash', 'identity', 'candidate_id', 'configuration', 'config_hash',
        'evidence_kind', 'source_evidence_hash', 'status', 'feasibility_passed',
        'reliability_passed', 'quality_passed', 'p95_latency_ms', 'peak_memory_mib',
        'startup_seconds', 'gpu_collection_seconds',
    }
    for artifact in artifacts:
        if set(artifact) != {'record', 'artifact_hash'}:
            raise ValueError('Outcome artifact needs exactly record and artifact_hash')
        record = artifact['record']
        if content_hash(record) != artifact['artifact_hash'] or not required <= set(record):
            raise ValueError('Outcome artifact hash or fields do not match')
        if set(record) - required - {'telemetry', 'per_load_p95_latency_ms', 'quality_score',
                                    'quality_floor', 'quality_valid_outputs', 'generation_errors', 'error_type'}:
            raise ValueError('Unknown outcome fields')
        candidate_id = record['candidate_id']
        if candidate_id not in entries or candidate_id in outcomes:
            raise ValueError('Unknown or duplicate outcome candidate')
        if (record['manifest_hash'] != manifest['manifest_hash']
                or record['identity'] != manifest['identity']
                or record['evidence_kind'] != manifest['evidence_kind']
                or any(record[key] != entries[candidate_id][key] for key in ('configuration', 'config_hash'))
                or not _hash(record['source_evidence_hash'])):
            raise ValueError('Outcome identity, configuration, provenance, or manifest mismatch')
        if (record['status'] not in {'completed', 'startup-failed', 'request-failed', 'cleanup-failed', 'infeasible'}
                or any(type(record[key]) is not bool for key in (
                    'feasibility_passed', 'reliability_passed', 'quality_passed'))
                or any(not _finite(record[key], zero=True) for key in ('startup_seconds', 'gpu_collection_seconds'))):
            raise ValueError('Invalid trial status, gates, or timing')
        if record['gpu_collection_seconds'] < record['startup_seconds']:
            raise ValueError('GPU collection time must include startup time')
        for key in ('p95_latency_ms', 'peak_memory_mib'):
            if record[key] is not None and not _finite(record[key]):
                raise ValueError('Invalid objective metric')
            if _valid(record) and record[key] is None:
                raise ValueError('A valid outcome requires latency and peak-memory measurements')
        telemetry = record.get('telemetry', {})
        if not isinstance(telemetry, dict) or any(
                not isinstance(key, str) or (value is not None and not _finite(value, zero=True))
                for key, value in telemetry.items()):
            raise ValueError('Telemetry must contain only finite nonnegative numbers or null')
        loads = record.get('per_load_p95_latency_ms', {})
        if not isinstance(loads, dict) or any(
                key not in {'1', '2', '4', '8'} or (value is not None and not _finite(value))
                for key, value in loads.items()):
            raise ValueError('Invalid per-load latency measurements')
        for field in ('quality_score', 'quality_floor'):
            score = record.get(field)
            if score is not None and (not _finite(score, zero=True) or score > 1):
                raise ValueError('Invalid quality score or floor')
        if 'quality_valid_outputs' in record and type(record['quality_valid_outputs']) is not bool:
            raise ValueError('Invalid quality output validity flag')
        errors = record.get('generation_errors')
        if errors is not None and (type(errors) is not int or errors < 0):
            raise ValueError('Invalid generation error count')
        if record.get('error_type') is not None and not isinstance(record['error_type'], str):
            raise ValueError('Invalid error type')
        outcomes[candidate_id] = deepcopy(record)
    if require_complete and outcomes.keys() != entries.keys():
        raise ValueError('Incomplete outcome universe: no oracle or comparison is permitted')
    if require_complete and not _valid(outcomes[BASELINE_NAME]):
        raise ValueError('Initial baseline must be measured and pass the frozen gates')
    return outcomes


def fixed_grid(view):
    return view['remaining_candidate_ids'][0]


def random_policy(seed):
    generator = random.Random(seed)
    return lambda view: generator.choice(view['remaining_candidate_ids'])


def _objective(record):
    return record['p95_latency_ms'], record['peak_memory_mib']


def replay(manifest, artifacts, *, policy=None, policy_name='fixed-grid', seed=None):
    """Policies receive copies of selected evidence only. They return one candidate ID."""
    # Copy inputs before any callback; a callback cannot mutate this run's outcomes.
    manifest, artifacts = deepcopy(manifest), deepcopy(artifacts)
    outcomes = _validate(manifest, artifacts)
    policy = fixed_grid if policy is None else policy
    baseline = outcomes[BASELINE_NAME]
    selected, proposals, curve = [], [], []
    best = baseline

    def point():
        return {'trials': len(selected), 'candidate_id': best['candidate_id'],
                'p95_latency_ms': best['p95_latency_ms'], 'peak_memory_mib': best['peak_memory_mib']}

    curve.append(point())
    all_ids = [entry['candidate_id'] for entry in manifest['candidates']]
    stop_reason = 'proposal-limit'
    for _ in range(manifest['max_proposals']):
        if len(selected) == manifest['budget']:
            stop_reason = 'budget-exhausted'
            break
        view = deepcopy({
            'manifest_hash': manifest['manifest_hash'], 'identity': manifest['identity'],
            'baseline': baseline, 'candidates': manifest['candidates'],
            'observed': [outcomes[candidate_id] for candidate_id in selected],
            'remaining_candidate_ids': [candidate_id for candidate_id in all_ids if candidate_id not in selected],
            'remaining_trials': manifest['budget'] - len(selected), 'proposal_log': proposals,
        })
        started = time.perf_counter()
        try:
            candidate_id = policy(view)
        except StopSearch:
            proposals.append({'candidate_id': None, 'status': 'stopped',
                              'policy_seconds': time.perf_counter() - started})
            stop_reason = 'policy-stopped'
            break
        except Exception as error:
            proposals.append({'candidate_id': None, 'status': 'policy-error',
                              'error_type': type(error).__name__, 'policy_seconds': time.perf_counter() - started})
            stop_reason = 'policy-error'
            break
        elapsed = time.perf_counter() - started
        if not isinstance(candidate_id, str) or candidate_id not in all_ids:
            status = 'out-of-universe'
        elif candidate_id in selected:
            status = 'repeated'
        else:
            status = 'selected'
            selected.append(candidate_id)
            outcome = outcomes[candidate_id]
            if _valid(outcome) and _objective(outcome) < _objective(best):
                best = outcome
            curve.append(point())
        proposals.append({'candidate_id': candidate_id if isinstance(candidate_id, str) else None,
                          'status': status, 'policy_seconds': elapsed})
    if len(selected) == manifest['budget']:
        stop_reason = 'budget-exhausted'
    # Oracle and regret are never included in a policy view.
    oracle = min((record for record in outcomes.values() if _valid(record)), key=_objective)
    for item in curve:
        item['latency_regret_ms'] = item['p95_latency_ms'] - oracle['p95_latency_ms']
    near = next((item['trials'] for item in curve
                 if item['p95_latency_ms'] <= oracle['p95_latency_ms'] * 1.05), None)
    return {
        'manifest_hash': manifest['manifest_hash'], 'policy': policy_name, 'seed': seed,
        'evidence_kind': manifest['evidence_kind'],
        'performance_claim_allowed': manifest['evidence_kind'] == 'measured',
        'benchmark_claim': 'not-assessed', 'budget': manifest['budget'],
        'trials_used': len(selected), 'stop_reason': stop_reason,
        'curve': curve, 'oracle': {key: oracle[key] for key in ('candidate_id', 'p95_latency_ms', 'peak_memory_mib')},
        'trials_to_near_oracle': near, 'proposals': proposals,
        'invalid_trials': sum(not _valid(outcomes[key]) for key in selected),
        'quality_failures': sum(not outcomes[key]['quality_passed'] for key in selected),
        'repeated_proposals': sum(item['status'] == 'repeated' for item in proposals),
        'candidate_count': len(all_ids), 'gpu_trials_during_replay': 0,
        'gpu_collection_seconds': sum(record['gpu_collection_seconds'] for record in outcomes.values()),
        'startup_seconds': sum(record['startup_seconds'] for record in outcomes.values()),
        'policy_seconds': sum(item['policy_seconds'] for item in proposals),
    }


def run_comparison(manifest, artifacts, *, policies=None):
    """Run grid, 20 frozen random seeds, and independent injectable agent/ablation callbacks."""
    manifest, artifacts = deepcopy(manifest), deepcopy(artifacts)
    grid = replay(manifest, artifacts)
    random_runs = [replay(manifest, artifacts, policy=random_policy(seed),
                          policy_name='uniform-random', seed=seed) for seed in manifest['random_seeds']]
    additional = {name: replay(manifest, artifacts, policy=policy, policy_name=name)
                  for name, policy in (policies or {}).items()}
    hits = [run['trials_to_near_oracle'] for run in random_runs]
    # Unreached thresholds are right-censored, not replaced with a fabricated trial count.
    return {
        'manifest_hash': manifest['manifest_hash'], 'grid': grid, 'random': random_runs,
        'policies': additional, 'benchmark_claim': 'not-assessed',
        'random_median_final_p95_ms': statistics.median(run['curve'][-1]['p95_latency_ms'] for run in random_runs),
        'random_near_oracle_hits': hits,
        'random_near_oracle_hit_fraction': sum(hit is not None for hit in hits) / len(hits),
    }
