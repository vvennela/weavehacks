"""Offline fixtures for the approved, explicitly exploratory 72B comparison."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from benchmarks.live_comparison import build_registration, live_arguments, timed_runtime_class
from benchmarks.grade import SYSTEM_PROMPT, load_cases
from sera.config import LARGE_MODEL_ID, LARGE_MODEL_REVISION, RuntimeConfig
from sera.runtime import GENERATION


def reference():
    cases = load_cases('benchmarks/easy_cases.json')
    prompts = [[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': case['prompt']}]
               for case in cases]
    return {'model_id': LARGE_MODEL_ID, 'model_revision': LARGE_MODEL_REVISION,
            'evaluation_cases': cases, 'prompts': prompts,
            'baseline': {'input_token_ids': [[1, index + 2] for index in range(8)],
                         'runtime': {'configuration': RuntimeConfig(quantization='fp8_per_tensor').model_dump(),
                                     'generation': GENERATION,
                                     'gpu': {'uuid': 'fixture', 'name': 'fixture', 'total_mib': 96000,
                                             'compute_capability': '12.0', 'driver': 'fixture'},
                                     'versions': {key: 'fixture' for key in
                                                  ('vllm', 'torch', 'transformers', 'flashinfer-python')}}}}


def test_registration_freezes_three_candidates_but_not_a_live_trial_cap():
    registration = build_registration(reference(), evidence_kind='test-fixture')
    manifest = registration['bundle']['manifest']
    assert manifest['budget'] == len(manifest['candidates']) == 3
    assert registration['live_search']['max_candidate_trials'] is None
    assert registration['strict_section_19_4_claim'] is False
    assert registration['prior_result_knowledge_disclosed'] is True
    arguments = live_arguments(registration)
    assert arguments['budget'].max_candidate_trials is None
    assert arguments['automatic_space'] is False
    assert len(arguments['investigation_space'].candidate_hashes) == 3
    assert arguments['constraints'].quality_floor == 0.99
    assert arguments['evaluation'](arguments['prompts'][0], '{"answer":5}') is True
    assert arguments['evaluation'](arguments['prompts'][0], '```json\n{"answer":5}\n```') is False


def test_registration_rejects_changed_questions():
    changed = reference()
    changed['prompts'][0][1]['content'] = 'easier question'
    with pytest.raises(ValueError):
        build_registration(changed, evidence_kind='test-fixture')


def test_actual_saved_reference_can_freeze_without_model_calls():
    saved = json.loads(Path('evidence/live-luna-expanded-v2/result.json').read_text())
    registration = build_registration(saved)
    assert registration['registration_hash'] == '2843eee593b706529bd178369ef91a529900ee6cb8412ce27ffa553e019c1eb5'
    assert registration['bundle']['records']['runtime']['vllm'] == '0.26.0'
    assert registration['bundle']['records']['hardware']['uuid'] == 'GPU-3119bd7a-a9d8-bbf2-2dc3-f5954d41e7e9'


def test_runtime_timing_keeps_startup_and_owned_interval_separate(monkeypatch):
    class Runtime:
        def __init__(self):
            self.record = {}

        def start(self):
            self.record['startup_seconds'] = 2
            return self

        def close(self):
            self.record['cleanup_pass'] = True
            return self.record

        def _save(self):
            pass

    ticks = iter([10, 12, 18])
    monkeypatch.setattr('benchmarks.live_comparison.time.monotonic', lambda: next(ticks))
    model = timed_runtime_class(Runtime)()
    model.start()
    model.close()
    assert model.record['startup_seconds'] == 2
    assert model.record['benchmark_timing']['owned_seconds'] == 8


def test_live_reference_tokens_are_checked_before_generation():
    from sera.storage import content_hash
    class Runtime:
        def prepare(self, prompt):
            return {}, [999]
    model = timed_runtime_class(Runtime, expected_inputs={content_hash('task'): [1, 2]})()
    with pytest.raises(ValueError, match='tokens'):
        model.prepare('task')


def campaign(tmp_path):
    from sera.storage import content_hash, save_json
    registration = build_registration(reference(), evidence_kind='test-fixture')
    bundle = registration['bundle']
    records = bundle['records']
    entries = [bundle['manifest']['baseline'], *bundle['manifest']['candidates']]

    def trial(entry, name, p95):
        return {'trial_id': name, 'status': 'collected', 'config_hash': entry['config_hash'],
                'runtime': {'configuration': entry['configuration'], 'model_id': LARGE_MODEL_ID,
                            'config_hash': entry['config_hash'],
                            'revision': LARGE_MODEL_REVISION, 'generation': GENERATION,
                            'enable_thinking': False, 'gpu': records['hardware'], 'versions': records['runtime'],
                            'cleanup_pass': True, 'sampled_peak_memory_mib': 2000,
                            'startup_seconds': 2, 'benchmark_timing': {'owned_seconds': 5, 'start_call_seconds': 2}},
                'input_token_ids': records['input_token_ids'], 'generation_errors': 0,
                'quality': [{'prompt_index': index, 'text': json.dumps({'answer': case['expected']}), 'error': None}
                            for index, case in enumerate(records['workload']['cases'])],
                'workload': {'concurrency': [1, 2, 4, 8], 'quality_concurrency': 1,
                             'latency_reduction': 'worst-per-load-percentile',
                             'cache_evaluation': {'prefix_caching_enabled': entry['configuration']['enable_prefix_caching'],
                                                 'measured_scope': 'repeated-prompts-after-per-load-warmup',
                                                 'cold_cache_measurement': False, 'warmup_prompts_per_load': 8}},
                'loads': [{'concurrency': level, 'requests': [{'latency_ms': p95, 'error': None}] * 24,
                           'reduced': {'p95_latency_ms': p95}} for level in [1, 2, 4, 8]]}

    baseline = trial(entries[0], 'baseline', 100)
    candidate = trial(entries[-1], 'trial-1', 80)
    report = {'status': 'closed', 'returned_runner_closed': True, 'trace_status': 'enabled',
              'model_id': LARGE_MODEL_ID, 'model_revision': LARGE_MODEL_REVISION,
              'baseline_name': entries[0]['candidate_id'], 'baseline_configuration': entries[0]['configuration'],
              'prompts': _test_prompts(records['workload']['cases']),
              'generation': records['generation'], 'constraints': {'quality_floor': 0.99},
              'objective': {'priority': 'latency', 'min_improvement_fraction': 0.05},
              'evaluation': {'version': 'sera-task-v1'}, 'baseline': baseline,
              'automatic_space': False, 'swarm_enabled': True,
              'investigation_space': {'candidate_hashes': [item['config_hash'] for item in entries[1:]]},
              'search_trials': [candidate], 'search': {'budget': {'max_candidate_trials': None},
                  'initial_trials_used': 0, 'trials_used': 1, 'stop_reason': 'arbiter-declined',
                  'rounds': [{'trial_ids': ['trial-1'], 'specialists': []}]},
              'decision': {'selected': 'trial-1'}, 'returned_runtimes': [candidate['runtime']],
              'agent_calls': [], 'weave_url': 'fixture://not-a-real-weave-trace'}
    (tmp_path / 'live').mkdir()
    save_json(tmp_path / 'registration.json', registration)
    save_json(tmp_path / 'bundle.json', bundle)
    save_json(tmp_path / 'live/result.json', report)
    save_json(tmp_path / 'live-run.json', {'status': 'closed', 'registration_hash': registration['registration_hash'],
                                         'result_hash': content_hash(report)})
    save_json(tmp_path / 'runner-probe.json', {'passed': True, 'config_hash': candidate['config_hash'],
        'response': {'text': '{"answer":5}', 'token_ids': [1], 'finish_reason': 'stop'}})
    return registration, entries, trial


def _test_prompts(cases):
    return [[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': case['prompt']}]
            for case in cases]


def test_import_live_then_missing_collection_then_full_grid(tmp_path):
    from benchmarks.live_comparison import import_live, collect_missing, compare_grid
    registration, entries, make_trial = campaign(tmp_path)
    imported = import_live(tmp_path)
    assert imported['selected_candidate_ids'] == [entries[-1]['candidate_id']]
    assert imported['complete'] is False
    with pytest.raises(ValueError, match='Incomplete'):
        compare_grid(tmp_path)
    measured = []

    def measure(entry, folder, bundle):
        measured.append(entry['candidate_id'])
        trial = make_trial(entry, entry['candidate_id'], 99)
        trial['collection_identity'] = {key: bundle['records'][key] for key in ('hardware', 'runtime')}
        trial['collection_seconds'] = 5
        return trial

    completed = collect_missing(tmp_path, measure=measure)
    assert measured == [entry['candidate_id'] for entry in entries[1:-1]]
    assert completed['complete'] is True
    comparison = compare_grid(tmp_path)
    assert comparison['sera']['trials_to_near_oracle'] == 1
    assert comparison['grid']['trials_to_near_oracle'] == 3
    assert comparison['exploratory_search_win'] is True
    assert comparison['strict_section_19_4_claim'] is False
    assert comparison['performance_claim_allowed'] is False


@pytest.mark.parametrize('change', ['open', 'probe', 'timing'])
def test_import_rejects_open_runner_bad_probe_or_missing_timing(tmp_path, change):
    from benchmarks.live_comparison import import_live
    from sera.storage import content_hash, save_json
    campaign(tmp_path)
    if change == 'probe':
        save_json(tmp_path / 'runner-probe.json', {'passed': True, 'response': {'text': '{"answer":99}'}})
    else:
        report = json.loads((tmp_path / 'live/result.json').read_text())
        if change == 'open':
            report['returned_runner_closed'] = False
        else:
            report['baseline']['runtime'].pop('benchmark_timing')
        save_json(tmp_path / 'live/result.json', report)
        launch = json.loads((tmp_path / 'live-run.json').read_text())
        launch['result_hash'] = content_hash(report)
        save_json(tmp_path / 'live-run.json', launch)
    with pytest.raises(ValueError):
        import_live(tmp_path)
    assert not (tmp_path / 'outcomes.json').exists()


def test_live_candidate_failure_is_retained_and_baseline_can_be_returned(tmp_path):
    from benchmarks.live_comparison import import_live
    from sera.storage import content_hash, save_json
    registration, entries, _ = campaign(tmp_path)
    report = json.loads((tmp_path / 'live/result.json').read_text())
    trial = report['search_trials'][0]
    trial.update(status='startup-failed', quality=[], loads=[])
    trial.pop('input_token_ids')
    report['decision']['selected'] = 'baseline'
    report['returned_runtimes'] = [report['baseline']['runtime']]
    save_json(tmp_path / 'live/result.json', report)
    launch = json.loads((tmp_path / 'live-run.json').read_text())
    launch['result_hash'] = content_hash(report)
    save_json(tmp_path / 'live-run.json', launch)
    save_json(tmp_path / 'runner-probe.json', {'passed': True, 'config_hash': entries[0]['config_hash'],
        'response': {'text': '{"answer":5}', 'token_ids': [1], 'finish_reason': 'stop'}})
    result = import_live(tmp_path)
    assert result['selected_candidate_ids'] == [entries[-1]['candidate_id']]
    outcomes = json.loads((tmp_path / 'outcomes.json').read_text())
    assert outcomes[1]['record']['status'] == 'startup-failed'
    assert outcomes[1]['record']['quality_score'] is None
    assert outcomes[1]['record']['p95_latency_ms'] is None


def test_import_rejects_future_history_before_any_oracle_collection(tmp_path):
    from benchmarks.live_comparison import import_live
    from sera.storage import content_hash, save_json
    campaign(tmp_path)
    report = json.loads((tmp_path / 'live/result.json').read_text())
    report['search']['rounds'][0]['specialists'] = [
        {'initial_evidence': {'history': [{'trial': {'trial_id': 'trial-1'}}]}}]
    save_json(tmp_path / 'live/result.json', report)
    launch = json.loads((tmp_path / 'live-run.json').read_text())
    launch['result_hash'] = content_hash(report)
    save_json(tmp_path / 'live-run.json', launch)
    with pytest.raises(ValueError, match='unselected'):
        import_live(tmp_path)
