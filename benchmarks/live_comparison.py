"""Approved 72B exploratory live swarm versus the same frozen full grid."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from unittest.mock import patch

from sera.config import (Budget, Constraints, InvestigationSpace, LARGE_MODEL_ID,
                         LARGE_MODEL_REVISION, Objective, RuntimeConfig, Workload)
from sera.runtime import GENERATION
from sera.storage import content_hash, save_json

from .collection import (HARDWARE_KEYS, MEASUREMENT, RUNTIME_PACKAGES, audit_collection,
                         freeze_collection, measure_live, normalize_trial, render_table,
                         summarize, validate_bundle)
from .grade import BENCHMARK_VERSION, SYSTEM_PROMPT, grade_case, load_cases
from .search import StopSearch, _validate, _valid, replay


CHANGES = {'enforce_eager': [False], 'max_num_batched_tokens': [2048], 'enable_prefix_caching': [True]}
RULE = {
    'version': 'exploratory-first-hit-v1', 'score': 'worst-per-load-p95',
    'eligibility': 'completed-and-feasibility-reliability-task-gates-pass',
    'oracle': 'best-valid-in-complete-frozen-universe', 'near_oracle_fraction': 0.05,
    'baseline_trial_count': 0, 'unreached': None,
    'sera_win': 'sera-reaches-and-grid-unreached-or-sera-first-hit-strictly-earlier',
    'ties': 'not-a-win', 'terminal_latency': 'report-separately',
    'strict_section_19_4_claim': False,
}


def _prompts(cases):
    return [[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': case['prompt']}]
            for case in cases]


def build_registration(reference, *, evidence_kind='measured'):
    """Use the prior run only to pin identity; no prior timing enters a prompt."""
    cases = load_cases(Path(__file__).with_name('easy_cases.json'))
    baseline = RuntimeConfig(quantization='fp8_per_tensor')
    if (reference.get('model_id') != LARGE_MODEL_ID or reference.get('model_revision') != LARGE_MODEL_REVISION
            or reference.get('evaluation_cases') != cases or reference.get('prompts') != _prompts(cases)):
        raise ValueError('Reference must use the unchanged pinned model, eight tasks, and system prompt')
    source = reference['baseline']
    runtime = source['runtime']
    if runtime['configuration'] != baseline.model_dump() or runtime['generation'] != GENERATION:
        raise ValueError('Reference settings differ from the approved FP8 baseline')
    records = {
        'workload': {'cases': cases, 'system_prompt': SYSTEM_PROMPT},
        'input_token_ids': deepcopy(source['input_token_ids']),
        'profile': {'concurrency': [1, 2, 4, 8], 'gpu_memory_utilization': 0.9},
        'generation': {**GENERATION, 'enable_thinking': False},
        'quality_gate': {'version': BENCHMARK_VERSION, 'floor': 0.99},
        'measurement': deepcopy(MEASUREMENT),
        'hardware': {key: runtime['gpu'][key] for key in HARDWARE_KEYS},
        'runtime': {key: runtime['versions'][key] for key in RUNTIME_PACKAGES},
    }
    candidates = [baseline.model_dump() | {lever: values[0]} for lever, values in CHANGES.items()]
    bundle = freeze_collection({
        'model_id': LARGE_MODEL_ID, 'model_revision': LARGE_MODEL_REVISION,
        'tokenizer_revision': LARGE_MODEL_REVISION, 'profile_name': 'qwen72b-warm-eight-task-live-grid-v1',
        'records': records, 'baseline': baseline.model_dump(), 'candidates': candidates,
        'budget': len(candidates), 'evidence_kind': evidence_kind,
        'model_exception': 'user-approved-qwen72b-fp8-v1', 'comparison_scope': 'exploratory-live-vs-grid-v1'})
    record = {
        'schema_version': 'sera-live-grid-registration-v1', 'bundle': bundle,
        'source_reference_hash': content_hash(reference),
        'source_reference_use': 'identity-and-input-tokens-only; all compared timings are new',
        'prior_result_knowledge_disclosed': True,
        'limitations': ['Prior 72B demo results informed this small control selection; this is not blind discovery.',
                       'One repeated-prompt profile; not a statistical, global-optimality, or pressure-reversal claim.',
                       'User-approved exception to the Qwen0.6B-only section19 model/baseline.',
                       'The live loop has no total trial cap; the fixed universe has three unique configurations.',
                       'Full grid is scored after live choices close, using identical cached outcomes.'],
        'live_search': {'max_candidate_trials': None, 'automatic_space': False,
                        'stop': 'objective-plateau-plus-confirmation-or-no-legal-candidates',
                        'changes': CHANGES, 'objective_min_improvement_fraction': 0.05},
        'acceptance_rule': RULE, 'strict_section_19_4_claim': False,
    }
    return record | {'registration_hash': content_hash(record)}


def validate_registration(registration):
    body = {key: value for key, value in registration.items() if key != 'registration_hash'}
    if content_hash(body) != registration.get('registration_hash') or registration['acceptance_rule'] != RULE:
        raise ValueError('Preregistered comparison changed')
    validate_bundle(registration['bundle'])
    expected = RuntimeConfig(quantization='fp8_per_tensor')
    hashes = {RuntimeConfig.model_validate(expected.model_dump() | {key: value[0]}).config_hash
              for key, value in CHANGES.items()}
    manifest = registration['bundle']['manifest']
    if (manifest.get('comparison_scope') != 'exploratory-live-vs-grid-v1'
            or {entry['config_hash'] for entry in manifest['candidates']} != hashes
            or registration['live_search']['max_candidate_trials'] is not None
            or registration['live_search']['automatic_space'] is not False):
        raise ValueError('Comparison must use the approved frozen three-candidate uncapped live loop')


def live_arguments(registration):
    validate_registration(registration)
    manifest = registration['bundle']['manifest']
    cases = registration['bundle']['records']['workload']['cases']
    prompts = _prompts(cases)
    by_prompt = {content_hash(prompt): case for prompt, case in zip(prompts, cases)}

    def evaluate(prompt, output):
        return grade_case(by_prompt[content_hash(prompt)], output)['passed']

    return dict(models=[LARGE_MODEL_ID], prompts=prompts, mode='swarm',
                baseline_configuration=RuntimeConfig(quantization='fp8_per_tensor'),
                budget=Budget(max_candidate_trials=None), automatic_space=False,
                investigation_space=InvestigationSpace(supported_changes=deepcopy(CHANGES),
                    candidate_hashes=[entry['config_hash'] for entry in manifest['candidates']]),
                evaluation=evaluate, evaluation_version=BENCHMARK_VERSION,
                constraints=Constraints(quality_floor=0.99),
                objective=Objective(priority='latency', min_improvement_fraction=0.05),
                workload=Workload(concurrency=[1, 2, 4, 8]))


def timed_runtime_class(base, *, expected_inputs=None):
    """Add benchmark-owned interval records; leave serving and cleanup unchanged."""
    class TimedRuntime(base):
        def prepare(self, prompt):
            payload, tokens = super().prepare(prompt)
            if expected_inputs is not None and expected_inputs.get(content_hash(prompt)) != tokens:
                raise ValueError('Fresh rendered tokens differ from the frozen reference')
            return payload, tokens

        def start(self):
            self._benchmark_started = time.monotonic()
            self.record['benchmark_timing'] = {'started_utc': datetime.now(timezone.utc).isoformat(),
                                               'scope': 'owned-start-through-close-including-agent-idle'}
            try:
                return super().start()
            finally:
                now = time.monotonic()
                timing = self.record['benchmark_timing']
                timing['start_call_seconds'] = now - self._benchmark_started
                if self.record.get('cleanup_pass') is True:
                    timing['owned_seconds'] = now - self._benchmark_started
                self._save()

        def close(self):
            already_closed = self.record.get('cleanup_pass') is True
            try:
                return super().close()
            finally:
                if hasattr(self, '_benchmark_started') and not already_closed:
                    self.record['benchmark_timing']['owned_seconds'] = time.monotonic() - self._benchmark_started
                    self.record['benchmark_timing']['closed_utc'] = datetime.now(timezone.utc).isoformat()
                    self._save()

    return TimedRuntime


def run_live(registration_path, output_dir):
    """Only this entry point runs GPU/provider calls. Freeze in a separate command first."""
    import sera
    from sera import pipeline
    from sera.runtime import gpu_snapshot
    import importlib.metadata

    registration = json.loads(Path(registration_path).read_text())
    arguments = live_arguments(registration)
    if registration['bundle']['manifest']['evidence_kind'] != 'measured':
        raise ValueError('Live execution cannot use fixture evidence')
    records = registration['bundle']['records']
    gpu = gpu_snapshot()
    if ({key: gpu[key] for key in HARDWARE_KEYS} != records['hardware']
            or {key: importlib.metadata.version(key) for key in RUNTIME_PACKAGES} != records['runtime']
            or gpu['used_mib'] > 128):
        raise ValueError('GPU or runtime differs from the frozen identity, or GPU is busy')
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=False)
    save_json(folder / 'registration.json', registration)
    save_json(folder / 'bundle.json', registration['bundle'])
    launch = {'registration_hash': registration['registration_hash'],
              'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'running',
              'source_settings': 'live_arguments(registration); explicit FP8 baseline; no total trial cap'}
    import subprocess
    launch['source_git_revision'] = subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    save_json(folder / 'live-run.json', launch)
    result = None
    try:
        expected_inputs = {content_hash(prompt): tokens for prompt, tokens in
                           zip(arguments['prompts'], records['input_token_ids'])}
        with patch.object(pipeline, 'SeraModel', timed_runtime_class(pipeline.SeraModel,
                                                                    expected_inputs=expected_inputs)):
            result = sera.optimize(**arguments, output_dir=folder / 'live')
            try:
                if not result.models:
                    raise RuntimeError('Live loop did not return a usable runner')
                response = result.models[0].generate(arguments['prompts'][0])
                passed = arguments['evaluation'](arguments['prompts'][0], response.text)
                save_json(folder / 'runner-probe.json', {'response': response.to_dict(), 'passed': passed,
                          'config_hash': result.models[0].configuration.config_hash,
                          'scope': 'fresh request on one unchanged task; not a new performance trial'})
                if not passed:
                    raise RuntimeError('Returned runner failed the unchanged task probe')
            finally:
                result.close()
        launch.update(status='closed', result_hash=content_hash(result.report),
                      closed_at=datetime.now(timezone.utc).isoformat(), weave_url=result.weave_url)
        save_json(folder / 'live-run.json', launch)
        return result.report
    except BaseException as error:
        launch.update(status='failed', error_type=type(error).__name__)
        save_json(folder / 'live-run.json', launch)
        raise


def _read(path):
    return json.loads(Path(path).read_text())


def _check_visible_history(evidence, visible):
    """Reject saved provider evidence that cites future trial history or trace scopes."""
    if not isinstance(evidence, dict):
        return
    if 'oracle' in evidence:
        raise ValueError('Oracle was included in live agent evidence')
    for row in evidence.get('history', []):
        trial = row.get('trial', {})
        if trial.get('trial_id') not in visible:
            raise ValueError('Live agent evidence includes an unselected outcome')
    for row in evidence.get('trace_scope', []):
        if row.get('trial_id') not in visible:
            raise ValueError('Live trace scope includes an unselected outcome')
    for inspection in evidence.get('inspections', []):
        for row in (inspection.get('result') or {}).get('records', []):
            if row.get('trial_id') not in visible:
                raise ValueError('Live inspection includes an unselected outcome')


def _closed_live(folder):
    registration = _read(folder / 'registration.json')
    validate_registration(registration)
    bundle = registration['bundle']
    if _read(folder / 'bundle.json') != bundle:
        raise ValueError('Collection bundle differs from the live registration')
    report = _read(folder / 'live/result.json')
    launch = _read(folder / 'live-run.json')
    if (launch.get('status') != 'closed' or launch.get('registration_hash') != registration['registration_hash']
            or launch.get('result_hash') != content_hash(report)
            or report.get('status') != 'closed' or report.get('returned_runner_closed') is not True):
        raise ValueError('Live run is not closed and bound to its preregistration/result hash')
    manifest, records = bundle['manifest'], bundle['records']
    expected_hashes = {entry['config_hash'] for entry in manifest['candidates']}
    if (report.get('model_id') != LARGE_MODEL_ID or report.get('model_revision') != LARGE_MODEL_REVISION
            or report.get('baseline_name') != manifest['baseline']['candidate_id']
            or report.get('baseline_configuration') != manifest['baseline']['configuration']
            or report.get('prompts') != _prompts(records['workload']['cases'])
            or report.get('generation') != records['generation']
            or report.get('constraints', {}).get('quality_floor') != 0.99
            or report.get('evaluation', {}).get('version') != BENCHMARK_VERSION
            or report.get('objective') != {'priority': 'latency', 'min_improvement_fraction': 0.05}
            or report.get('automatic_space') is not False or report.get('swarm_enabled') is not True
            or set(report.get('investigation_space', {}).get('candidate_hashes', [])) != expected_hashes
            or report.get('search', {}).get('budget') != {'max_candidate_trials': None}
            or report.get('search', {}).get('initial_trials_used') != 0
            or report.get('trace_status') != 'enabled'):
        raise ValueError('Live request differs from the frozen comparison or tracing did not complete')
    trials = [report['baseline'], *report.get('search_trials', [])]
    if (report['search']['trials_used'] != len(trials) - 1
            or len({trial['config_hash'] for trial in trials}) != len(trials)
            or len({trial['trial_id'] for trial in trials}) != len(trials)):
        raise ValueError('Live trial identity or counts are inconsistent')
    known = {'baseline'}
    selected = []
    for round_record in report['search']['rounds']:
        for check in round_record.get('specialists', []):
            for key in ('initial_evidence', 'evidence'):
                _check_visible_history(check.get(key), known)
        _check_visible_history(round_record.get('arbiter_evidence'), known)
        new = round_record['trial_ids']
        if len(new) > 1 or any(key in known for key in new):
            raise ValueError('Live round repeated a trial or executed multiple arbiter choices')
        selected.extend(new)
        known.update(new)
    if selected != [trial['trial_id'] for trial in trials[1:]]:
        raise ValueError('Recorded live choice order differs from trial order')
    returned = report.get('returned_runtimes', [])
    chosen = next((trial for trial in trials if trial['trial_id'] == report['decision']['selected']), None)
    probe = _read(folder / 'runner-probe.json')
    response = probe.get('response', {})
    if (chosen is None or len(returned) != 1 or returned[0].get('cleanup_pass') is not True
            or returned[0].get('config_hash') != chosen['config_hash']
            or probe.get('config_hash') != chosen['config_hash'] or probe.get('passed') is not True
            or response.get('error') or not response.get('token_ids')
            or response.get('finish_reason') not in {'stop', 'length'}
            or not grade_case(records['workload']['cases'][0], response.get('text'))['passed']):
        raise ValueError('Returned runner probe/configuration/cleanup did not pass independent validation')
    return registration, report, launch


def import_live(folder):
    """Normalize the live-selected outcomes only; do not execute remaining configurations."""
    folder = Path(folder)
    if (folder / 'outcomes.json').exists():
        raise FileExistsError('Live outcomes were already imported')
    registration, report, launch = _closed_live(folder)
    bundle = registration['bundle']
    manifest, records = bundle['manifest'], bundle['records']
    entries = {entry['config_hash']: entry for entry in [manifest['baseline'], *manifest['candidates']]}
    artifacts, sources = [], []
    original = [report['baseline'], *report.get('search_trials', [])]
    for source in original:
        key = source['config_hash']
        if key not in entries:
            raise ValueError('Live trial is outside the frozen candidate universe')
        trial = deepcopy(source)
        runtime = trial['runtime']
        timing = runtime.get('benchmark_timing') or {}
        if runtime.get('cleanup_pass') is not True or type(timing.get('owned_seconds')) not in (int, float):
            raise ValueError('Live trial lacks verified cleanup or measured owned-runtime timing')
        trial.update(collection_seconds=timing['owned_seconds'],
                     source_live_result_hash=content_hash(report), source_live_trial_hash=content_hash(source),
                     collection_identity={'hardware': {key: runtime['gpu'][key] for key in HARDWARE_KEYS},
                                          'runtime': {key: runtime['versions'][key] for key in RUNTIME_PACKAGES}})
        if 'startup_seconds' not in runtime:
            if type(timing.get('start_call_seconds')) not in (int, float):
                raise ValueError('Failed startup lacks its observed start-call interval')
            runtime.update(startup_seconds=timing['start_call_seconds'],
                           startup_timing_scope='start-call-through-return-or-error')
        artifact = normalize_trial(bundle, entries[key], trial)
        artifacts.append(artifact)
        sources.append((entries[key]['candidate_id'], trial))
    _validate(manifest, artifacts, require_complete=False)
    if not _valid(artifacts[0]['record']):
        raise ValueError('Fresh baseline did not pass the frozen gates')
    for candidate_id, trial in sources:
        save_json(folder / f'{candidate_id}-source.json', trial)
    save_json(folder / 'outcomes.json', artifacts)
    audit = {'registration_hash': registration['registration_hash'], 'live_result_hash': content_hash(report),
             'live_launch_hash': content_hash(launch), 'live_stop_reason': report['search']['stop_reason'],
             'selected_candidate_ids': [entry['record']['candidate_id'] for entry in artifacts[1:]],
             'live_trial_ids': [trial['trial_id'] for trial in original[1:]],
             'live_rounds': len(report['search']['rounds']), 'no_future_history_or_trace_scope': True,
             'returned_runner_probe_regraded': True, 'strict_section_19_4_claim': False}
    save_json(folder / 'live-import.json', audit)
    summary = summarize(manifest, artifacts)
    save_json(folder / 'summary.json', summary)
    return audit | {'complete': summary['complete']}


def _audit_import(folder):
    registration, report, launch = _closed_live(folder)
    bundle, artifacts, summary = audit_collection(folder)
    imported = _read(folder / 'live-import.json')
    if (imported['registration_hash'] != registration['registration_hash']
            or imported['live_result_hash'] != content_hash(report)
            or imported['live_launch_hash'] != content_hash(launch)):
        raise ValueError('Live import lost its source binding')
    expected_ids = [trial['config_hash'] for trial in report['search_trials']]
    if imported['selected_candidate_ids'] != expected_ids:
        raise ValueError('Imported live sequence changed')
    by_id = {artifact['record']['candidate_id']: artifact for artifact in artifacts}
    for trial in [report['baseline'], *report['search_trials']]:
        key = bundle['manifest']['baseline']['candidate_id'] if trial is report['baseline'] else trial['config_hash']
        source = _read(folder / f'{key}-source.json')
        if (key not in by_id or source.get('source_live_result_hash') != content_hash(report)
                or source.get('source_live_trial_hash') != content_hash(trial)):
            raise ValueError('Imported source is not bound to the live trial')
    return registration, report, bundle, artifacts, summary, imported


def collect_missing(folder, *, measure=None):
    """Only after the live loop/probe/cleanup finish, fill unseen oracle outcomes."""
    folder = Path(folder)
    registration, report, bundle, artifacts, summary, imported = _audit_import(folder)
    if measure is not None and bundle['manifest']['evidence_kind'] != 'test-fixture':
        raise ValueError('Injected measurement requires fixture evidence')
    if measure is None and bundle['manifest']['evidence_kind'] != 'measured':
        raise ValueError('Live measurement cannot use fixture evidence')
    measure = measure or measure_live
    for entry in bundle['manifest']['candidates']:
        if entry['candidate_id'] not in summary['missing_candidate_ids']:
            continue
        runtime_folder = folder / f"oracle-{entry['candidate_id']}"
        source_path = folder / f"{entry['candidate_id']}-source.json"
        if runtime_folder.exists() or source_path.exists():
            raise ValueError('An incomplete previous collection needs an explicit source audit, not a repeated trial')
        trial = measure(entry, runtime_folder, deepcopy(bundle))
        save_json(source_path, trial)
        artifact = normalize_trial(bundle, entry, trial)
        _validate(bundle['manifest'], [*artifacts, artifact], require_complete=False)
        artifacts.append(artifact)
        save_json(folder / 'outcomes.json', artifacts)
        if artifact['record']['status'] == 'cleanup-failed':
            raise ValueError('Oracle collection stopped after cleanup failed')
    summary = summarize(bundle['manifest'], artifacts)
    save_json(folder / 'summary.json', summary)
    (folder / 'measurements.md').write_text(render_table(summary))
    return summary


def compare_grid(folder):
    """Replay recorded live choices and full grid on the same complete outcome table."""
    folder = Path(folder)
    registration, report, bundle, artifacts, summary, imported = _audit_import(folder)
    if not summary['complete']:
        raise ValueError('Incomplete universe: no oracle or grid comparison')
    selected = iter(imported['selected_candidate_ids'])

    def recorded_choice(view):
        try:
            return next(selected)
        except StopIteration:
            raise StopSearch() from None

    sera = replay(bundle['manifest'], artifacts, policy=recorded_choice, policy_name='recorded-live-sera')
    grid = replay(bundle['manifest'], artifacts)
    sera_hit, grid_hit = sera['trials_to_near_oracle'], grid['trials_to_near_oracle']
    won = sera_hit is not None and (grid_hit is None or sera_hit < grid_hit)
    attempts = [attempt for call in report.get('agent_calls', []) for attempt in call.get('attempts', [])]
    provider_ms = [attempt.get('latency_ms') for attempt in attempts]
    result = {'schema_version': 'sera-exploratory-live-grid-v1',
              'registration_hash': registration['registration_hash'], 'live_result_hash': content_hash(report),
              'acceptance_rule': registration['acceptance_rule'], 'sera': sera, 'grid': grid,
              'exploratory_search_win': won,
              'performance_claim_allowed': bundle['manifest']['evidence_kind'] == 'measured',
              'strict_section_19_4_claim': False, 'random_or_ablation_runs': 0,
              'live_stop_reason': imported['live_stop_reason'], 'weave_url': report.get('weave_url'),
              'live_returned_trial_id': report['decision']['selected'],
              'provider_attempt_seconds_sum': sum(value for value in provider_ms if type(value) in (int, float)) / 1000,
              'provider_attempts_without_timing': sum(type(value) not in (int, float) for value in provider_ms),
              'limits': registration['limitations'] + [
                  'First-hit counts score best quality-valid measured evidence; deployment still uses its 5% gain target.',
                  'Provider attempt durations sum parallel calls; they are not end-to-end wall time.',
                  'Grid is replayed on the identical table, not rerun on a differently noisy GPU.']}
    save_json(folder / 'grid-comparison.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freeze = commands.add_parser('freeze')
    freeze.add_argument('--reference', required=True)
    freeze.add_argument('--output-file', required=True)
    run = commands.add_parser('run-live')
    run.add_argument('--registration', required=True)
    run.add_argument('--output-dir', required=True)
    for name in ('import-live', 'collect-missing', 'compare-grid'):
        command = commands.add_parser(name)
        command.add_argument('--run-dir', required=True)
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        registration = build_registration(json.loads(Path(args.reference).read_text()))
        with Path(args.output_file).open('x') as stream:
            json.dump(registration, stream, indent=2, allow_nan=False)
        print(f"Frozen exploratory registration: {registration['registration_hash']}")
    elif args.command == 'run-live':
        report = run_live(args.registration, args.output_dir)
        print(f"Live loop closed: {report['search']['stop_reason']}; {report.get('weave_url')}")
    else:
        function = {'import-live': import_live, 'collect-missing': collect_missing, 'compare-grid': compare_grid}[args.command]
        result = function(args.run_dir)
        print(json.dumps({key: result[key] for key in ('complete', 'exploratory_search_win', 'live_stop_reason')
                          if key in result}))


if __name__ == '__main__':
    main()
