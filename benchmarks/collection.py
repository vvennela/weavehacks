"""Freeze, collect, and audit one Qwen0.6B universe. Replay never runs a GPU."""

from copy import deepcopy
import importlib.metadata
from pathlib import Path
import time

from sera.config import (BASELINE_NAME, MODEL_ID, MODEL_REVISION, LARGE_MODEL_ID,
                         LARGE_MODEL_REVISION, RuntimeConfig, Workload)
from sera.measurement import collect_trial, nearest_rank
from sera.quality import evaluate_quality
from sera.runtime import GENERATION, SeraModel, gpu_snapshot
from sera.storage import content_hash, save_json

from .grade import BENCHMARK_VERSION, grade_case
from .search import IDENTITY_HASHES, _validate, _valid, freeze_manifest


MEASUREMENT = {
    'version': 'sera-collect-trial-v1', 'warmup': 'min(prompt-count,16)-per-load',
    'requests_per_load': 'min(3*prompt-count,96)', 'quality_passes': 1,
    'baseline_self_check_passes': 1, 'percentile': 'nearest-rank',
    'latency': 'worst-per-load-p95', 'cache_scope': 'repeated-prompts-after-per-load-warmup',
    'memory': 'whole-device-one-second-sampled-peak',
    'collection_time': 'owned-runtime-start-through-cleanup',
}
HARDWARE_KEYS = ('uuid', 'name', 'total_mib', 'compute_capability', 'driver')
RUNTIME_PACKAGES = ('vllm', 'torch', 'transformers', 'flashinfer-python')


def freeze_collection(plan):
    """Hash complete source records before measurement. Input tokens come from a pilot."""
    plan = deepcopy(plan)
    records = plan['records']
    if set(records) != {key.removesuffix('_hash') for key in IDENTITY_HASHES}:
        raise ValueError('All identity source records are required')
    profile = records['profile']
    workload = Workload(concurrency=profile['concurrency'])
    cases = records['workload']['cases']
    tokens = records['input_token_ids']
    if (not cases or len({case['id'] for case in cases}) != len(cases)
            or any(not isinstance(case['prompt'], str) or not case['prompt'].strip()
                   or case['max_tokens'] != 64 or 'expected' not in case for case in cases)
            or not isinstance(records['workload']['system_prompt'], str)
            or not records['workload']['system_prompt'].strip()
            or len(tokens) != len(cases)
            or any(not row or any(type(token) is not int or token < 0 for token in row) for row in tokens)):
        raise ValueError('Freeze nonempty strict task cases and exact pilot input token IDs')
    if records['generation'] != {**GENERATION, 'enable_thinking': False}:
        raise ValueError('Generation settings do not match the collector')
    if records['measurement'] != MEASUREMENT:
        raise ValueError('Measurement protocol does not match the collector')
    quality = records['quality_gate']
    if (set(quality) != {'version', 'floor'} or quality['version'] != BENCHMARK_VERSION
            or type(quality['floor']) not in (int, float) or not 0 <= quality['floor'] <= 1):
        raise ValueError('Freeze a sera-task-v1 quality floor')
    if set(records['hardware']) != set(HARDWARE_KEYS) or set(records['runtime']) != set(RUNTIME_PACKAGES):
        raise ValueError('Freeze the exact GPU identity and all four runtime versions')
    revision = LARGE_MODEL_REVISION if plan.get('model_exception') == 'user-approved-qwen72b-fp8-v1' else MODEL_REVISION
    if plan['model_revision'] != revision or plan['tokenizer_revision'] != revision:
        raise ValueError('Collector requires the supported pinned model revision')
    baseline = RuntimeConfig.model_validate(plan['baseline'])
    if baseline.gpu_memory_utilization != profile['gpu_memory_utilization']:
        raise ValueError('Baseline memory fraction differs from the declared profile')
    for values in [plan['baseline'], *plan['candidates']]:
        config = RuntimeConfig.model_validate(values)
        if max(workload.concurrency) > config.max_num_seqs:
            raise ValueError('Candidate cannot serve declared concurrency')
        if max(map(len, tokens)) + GENERATION['max_tokens'] > config.max_model_len:
            raise ValueError('Candidate context cannot cover the frozen inputs')
    identity = {key: plan[key] for key in ('model_id', 'model_revision', 'tokenizer_revision', 'profile_name')}
    identity.update({key: content_hash(records[key.removesuffix('_hash')]) for key in IDENTITY_HASHES})
    manifest = freeze_manifest(identity, baseline, plan['candidates'], budget=plan['budget'],
                               evidence_kind=plan.get('evidence_kind', 'measured'),
                               compatibility=plan.get('compatibility'),
                               random_seeds=plan.get('random_seeds', list(range(20))),
                               max_proposals=plan.get('max_proposals', 32),
                               model_exception=plan.get('model_exception'), comparison_scope=plan.get('comparison_scope'))
    bundle = {'manifest': manifest, 'records': records}
    return {**bundle, 'bundle_hash': content_hash(bundle)}


def validate_bundle(bundle):
    manifest = bundle['manifest']
    plan = {**manifest['identity'], 'records': bundle['records'],
            'baseline': manifest['baseline']['configuration'],
            'candidates': [entry['configuration'] for entry in manifest['candidates']],
            **{key: manifest[key] for key in ('budget', 'evidence_kind', 'compatibility',
                                             'random_seeds', 'max_proposals')}}
    plan.update({key: manifest[key] for key in ('model_exception', 'comparison_scope') if key in manifest})
    if freeze_collection(plan) != bundle:
        raise ValueError('Collection sources or manifest changed after they were frozen')


def measure_live(entry, folder, bundle):
    """Use the existing owned runner, request collector, and cleanup checks."""
    records = bundle['records']
    snapshot = gpu_snapshot()
    hardware = {key: snapshot[key] for key in HARDWARE_KEYS}
    versions = {key: importlib.metadata.version(key) for key in RUNTIME_PACKAGES}
    if hardware != records['hardware'] or versions != records['runtime']:
        raise ValueError('Live GPU/runtime differs from the frozen identity')
    prompts = [[{'role': 'system', 'content': records['workload']['system_prompt']},
                {'role': 'user', 'content': case['prompt']}]
               for case in records['workload']['cases']]
    model = SeraModel(artifact_dir=folder, configuration=RuntimeConfig.model_validate(entry['configuration']),
                      model_id=bundle['manifest']['identity']['model_id'],
                      revision=bundle['manifest']['identity']['model_revision'])
    started = time.monotonic()
    startup_finished = None
    trial = {'status': 'startup-failed', 'runtime': model.record, 'config_hash': entry['config_hash']}
    try:
        model.start()
        startup_finished = time.monotonic()
        trial['status'] = 'request-failed'
        trial = collect_trial(model, prompts, entry['candidate_id'],
                              baseline=entry['candidate_id'] == bundle['manifest']['baseline']['candidate_id'],
                              workload=Workload(concurrency=records['profile']['concurrency']))
    except Exception as error:
        if startup_finished is None:
            startup_finished = time.monotonic()
        trial['error_type'] = type(error).__name__
    finally:
        if startup_finished is None:
            startup_finished = time.monotonic()
        try:
            model.close()
        except Exception as error:
            trial.update(status='cleanup-failed', error_type=type(error).__name__)
        trial['runtime'] = deepcopy(model.record)
        trial['collection_identity'] = {'hardware': hardware, 'runtime': versions}
        trial['collection_seconds'] = time.monotonic() - started
        # Failed start() may itself clean up, but this excludes the later outer close().
        if 'startup_seconds' not in trial['runtime']:
            trial['runtime']['startup_seconds'] = startup_finished - started
            trial['runtime']['startup_timing_scope'] = 'start-call-through-return-or-error'
    return trial


def normalize_trial(bundle, entry, trial):
    """Derive all gates from saved source output, never from agent claims."""
    manifest, records = bundle['manifest'], bundle['records']
    runtime = trial['runtime']
    if trial.get('collection_identity') != {key: records[key] for key in ('hardware', 'runtime')}:
        raise ValueError('Collected hardware or runtime differs from the frozen identity')
    if (runtime.get('model_id') != manifest['identity']['model_id']
            or runtime.get('revision') != manifest['identity']['model_revision']
            or runtime.get('generation') != GENERATION or runtime.get('enable_thinking') is not False):
        raise ValueError('Collected model or generation settings differ from the frozen identity')
    if runtime['configuration'] != entry['configuration'] or trial['config_hash'] != entry['config_hash']:
        raise ValueError('Collected configuration differs from frozen configuration')
    if trial.get('input_token_ids') is not None and trial['input_token_ids'] != records['input_token_ids']:
        raise ValueError('Rendered input tokens differ from frozen pilot')
    cases = records['workload']['cases']
    if trial['status'] == 'collected':
        workload = trial.get('workload', {})
        expected_cache = {
            'prefix_caching_enabled': entry['configuration']['enable_prefix_caching'],
            'measured_scope': MEASUREMENT['cache_scope'], 'cold_cache_measurement': False,
            'warmup_prompts_per_load': min(len(cases), 16)}
        if (workload.get('concurrency') != records['profile']['concurrency']
                or workload.get('quality_concurrency') != 1
                or workload.get('latency_reduction') != 'worst-per-load-percentile'
                or workload.get('cache_evaluation') != expected_cache):
            raise ValueError('Collected workload or cache measurement scope changed')
    indexed = list(range(len(cases)))
    quality = evaluate_quality(trial, indexed, lambda index, output: grade_case(cases[index], output)['passed'],
                               version=records['quality_gate']['version'], floor=records['quality_gate']['floor'])
    loads = trial.get('loads', [])
    expected_loads = records['profile']['concurrency']
    load_complete = [load['concurrency'] for load in loads] == expected_loads
    per_load = {}
    for load in loads:
        requests = load.get('requests', [])
        successful = [request for request in requests if not request.get('error')]
        p95 = nearest_rank([request['latency_ms'] for request in successful], 95)
        if 'reduced' not in load and trial['status'] != 'collected':
            per_load[str(load['concurrency'])] = p95
            continue
        if p95 != load['reduced']['p95_latency_ms']:
            raise ValueError('Saved reduced latency does not match raw request timings')
        if trial['status'] == 'collected' and len(requests) != min(3 * len(cases), 96):
            raise ValueError('Request count differs from frozen measurement procedure')
        per_load[str(load['concurrency'])] = p95
    latencies = list(per_load.values())
    latency = max(latencies) if load_complete and all(value is not None for value in latencies) else None
    collected = trial['status'] == 'collected' and load_complete and trial.get('input_token_ids') is not None
    cleanup = runtime.get('cleanup_pass') is True
    status = 'completed' if collected else 'request-failed'
    if trial['status'] in {'startup-failed', 'infeasible'}:
        status = trial['status']
    if not cleanup:
        status = 'cleanup-failed'
    errors = sum(bool(row.get('error')) for load in loads for row in load.get('requests', []))
    errors += sum(bool(row.get('error')) for phase in ('warmup', 'quality', 'self_check')
                  for row in trial.get(phase, []))
    if trial.get('generation_errors') is not None and trial['generation_errors'] != errors:
        raise ValueError('Saved generation error count does not match source requests')
    telemetry = {}
    for load in loads:
        snapshot = load.get('metrics', {}).get('after-measurement', {})
        for name in ('mean_queue_ms', 'mean_ttft_ms', 'preemptions'):
            telemetry[f"concurrency_{load['concurrency']}_cumulative_snapshot_{name}"] = snapshot.get(name)
    record = {
        'manifest_hash': manifest['manifest_hash'], 'identity': manifest['identity'], **entry,
        'evidence_kind': manifest['evidence_kind'], 'source_evidence_hash': content_hash(trial),
        'status': status, 'feasibility_passed': collected,
        'reliability_passed': collected and cleanup and errors == 0,
        'quality_passed': quality['passed'],
        'quality_valid_outputs': quality['valid_outputs'],
        'quality_score': quality['mean'] if len(trial.get('quality', [])) == len(cases) else None,
        'quality_floor': records['quality_gate']['floor'],
        'generation_errors': errors, 'error_type': trial.get('error_type'), 'telemetry': telemetry,
        'p95_latency_ms': latency, 'per_load_p95_latency_ms': per_load,
        'peak_memory_mib': runtime.get('sampled_peak_memory_mib') or None,
        'startup_seconds': runtime['startup_seconds'], 'gpu_collection_seconds': trial['collection_seconds'],
    }
    return {'record': record, 'artifact_hash': content_hash(record)}


def summarize(manifest, artifacts):
    outcomes = _validate(manifest, artifacts, require_complete=False)
    entries = [manifest['baseline'], *manifest['candidates']]
    missing = [entry['candidate_id'] for entry in entries if entry['candidate_id'] not in outcomes]
    baseline_id = manifest['baseline']['candidate_id']
    baseline_valid = baseline_id in outcomes and _valid(outcomes[baseline_id])
    complete = not missing and baseline_valid
    oracle = min((row for row in outcomes.values() if _valid(row)),
                 key=lambda row: (row['p95_latency_ms'], row['peak_memory_mib'])) if complete else None
    return {'manifest_hash': manifest['manifest_hash'], 'complete': complete, 'baseline_id': baseline_id,
            'missing_candidate_ids': missing, 'baseline_valid': baseline_valid,
            'oracle': deepcopy(oracle), 'rows': [outcomes[entry['candidate_id']] for entry in entries
                                               if entry['candidate_id'] in outcomes],
            'benchmark_claim': 'not-assessed',
            'performance_claim_allowed': complete and manifest['evidence_kind'] == 'measured',
            'scope': MEASUREMENT['cache_scope']}


def collect(bundle, output_dir, *, measure=None):
    """Write an immutable manifest before running baseline, then every frozen candidate."""
    validate_bundle(bundle)
    if measure is not None and bundle['manifest']['evidence_kind'] != 'test-fixture':
        raise ValueError('Injected collectors require test-fixture evidence')
    if measure is None and bundle['manifest']['evidence_kind'] != 'measured':
        raise ValueError('Live collection requires measured evidence')
    measure = measure or measure_live
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    save_json(output_dir / 'bundle.json', bundle)
    artifacts = []
    save_json(output_dir / 'outcomes.json', artifacts)
    stop = 'universe-collected'
    for entry in [bundle['manifest']['baseline'], *bundle['manifest']['candidates']]:
        try:
            trial = measure(entry, output_dir / entry['candidate_id'], deepcopy(bundle))
        except Exception as error:
            # An identity/preflight error has no valid outcome. Do not invent one.
            save_json(output_dir / 'collection-error.json',
                      {'candidate_id': entry['candidate_id'], 'error_type': type(error).__name__})
            stop = 'collection-error'
            break
        save_json(output_dir / f"{entry['candidate_id']}-source.json", trial)
        try:
            artifact = normalize_trial(bundle, entry, trial)
            _validate(bundle['manifest'], [*artifacts, artifact], require_complete=False)
        except (ValueError, KeyError, TypeError):
            stop = 'identity-mismatch'
            break
        artifacts.append(artifact)
        save_json(output_dir / 'outcomes.json', artifacts)
        if artifact['record']['status'] == 'cleanup-failed':
            stop = 'cleanup-failed'
            break
        if entry['candidate_id'] == bundle['manifest']['baseline']['candidate_id'] and not _valid(artifact['record']):
            stop = 'baseline-failed-gates'
            break
    report = summarize(bundle['manifest'], artifacts)
    report['stop_reason'] = stop
    save_json(output_dir / 'summary.json', report)
    return report


def audit_collection(folder):
    """Recompute every normalized envelope from its saved, hash-bound source trial."""
    import json
    folder = Path(folder)
    bundle = json.loads((folder / 'bundle.json').read_text())
    validate_bundle(bundle)
    artifacts = json.loads((folder / 'outcomes.json').read_text())
    _validate(bundle['manifest'], artifacts, require_complete=False)
    entries = {entry['candidate_id']: entry for entry in
               [bundle['manifest']['baseline'], *bundle['manifest']['candidates']]}
    for artifact in artifacts:
        key = artifact['record']['candidate_id']
        source = json.loads((folder / f'{key}-source.json').read_text())
        if normalize_trial(bundle, entries[key], source) != artifact:
            raise ValueError('Outcome does not match saved source evidence')
    return bundle, artifacts, summarize(bundle['manifest'], artifacts)


def render_table(summary):
    lines = ['# Frozen configuration measurements', '',
             f"Complete universe: {summary['complete']}. Search claim: not assessed.", '',
             'Request latency covers repeated prompts after per-load warmup. Startup is separate.', '',
             '| Configuration | Changes from baseline | Status | Task score | Worst p95 ms | Per-load p95 ms | Peak MiB | Startup s |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    baseline_id = summary.get('baseline_id', BASELINE_NAME)
    baseline = next((row['configuration'] for row in summary['rows'] if row['candidate_id'] == baseline_id), {})
    for row in summary['rows']:
        loads = ', '.join(f'{key}: {value}' for key, value in row.get('per_load_p95_latency_ms', {}).items())
        changes = ', '.join(f'{key}={value}' for key, value in row['configuration'].items()
                            if baseline.get(key) != value) or 'named baseline'
        identifier = baseline_id if row['candidate_id'] == baseline_id else row['candidate_id'][:12]
        lines.append(f"| {identifier} | {changes} | {row['status']} | {row.get('quality_score')} | "
                     f"{row['p95_latency_ms']} | {loads} | {row['peak_memory_mib']} | {row['startup_seconds']} |")
    lines.extend(['', 'Full configurations and hashes are in bundle.json and outcomes.json.',
                  'A complete table establishes measurements, not agent search superiority.', ''])
    return '\n'.join(lines)
