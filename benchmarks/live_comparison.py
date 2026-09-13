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

from .collection import HARDWARE_KEYS, MEASUREMENT, RUNTIME_PACKAGES, freeze_collection, validate_bundle
from .grade import BENCHMARK_VERSION, SYSTEM_PROMPT, grade_case, load_cases


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freeze = commands.add_parser('freeze')
    freeze.add_argument('--reference', required=True)
    freeze.add_argument('--output-file', required=True)
    run = commands.add_parser('run-live')
    run.add_argument('--registration', required=True)
    run.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        registration = build_registration(json.loads(Path(args.reference).read_text()))
        with Path(args.output_file).open('x') as stream:
            json.dump(registration, stream, indent=2, allow_nan=False)
        print(f"Frozen exploratory registration: {registration['registration_hash']}")
    else:
        report = run_live(args.registration, args.output_dir)
        print(f"Live loop closed: {report['search']['stop_reason']}; {report.get('weave_url')}")


if __name__ == '__main__':
    main()
