"""Offline fixtures for the approved, explicitly exploratory 72B comparison."""

from copy import deepcopy
import json

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
