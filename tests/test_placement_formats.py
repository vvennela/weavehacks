"""Structured decoding is explicit, versioned, and carried into every request."""

from copy import deepcopy
import json

import pytest

from sera.placement import PlacementWorkload
from test_placement import environment, inputs, FakeModel, MODEL_ID, GLM_MODEL_ID


FORMAT = {'type':'json_schema', 'json_schema':{'name':'fixture-answer', 'schema':{
    'type':'object', 'properties':{'answer':{'type':'integer'}},
    'required':['answer'], 'additionalProperties':False}}}


def formatted_inputs(environment):
    args = inputs(environment)
    args['workloads'] = {model:PlacementWorkload(profile.prompts, profile.evaluator,
        profile.evaluator_version, profile.workload, response_formats=[deepcopy(FORMAT)],
        response_format_version='fixture-requested-integer-v1') for model,profile in args['workloads'].items()}
    return args


def test_every_isolated_joint_and_postreturn_request_keeps_the_exact_schema(environment, monkeypatch, tmp_path):
    original = FakeModel._generate_prepared
    seen = []
    def generate(self, payload, tokens):
        seen.append((self.model_id, self.owner is not None, deepcopy(payload)))
        assert payload['response_format'] == FORMAT
        return original(self, payload, tokens)
    monkeypatch.setattr(FakeModel, '_generate_prepared', generate)
    result = environment.place(**formatted_inputs(environment), output_dir=tmp_path/'run')
    assert len(result.models) == 2
    for model in result.models:
        assert model.generate('2+2').text == '4'
    assert {shared for _,shared,_ in seen} == {False, True}
    assert {model for model,_,_ in seen} == {MODEL_ID, GLM_MODEL_ID}
    for trial in [*result.report['isolated'].values(), *result.report['joint']['trials'].values()]:
        assert all(row['response_format'] == FORMAT for row in trial['requests'] + trial['quality'] + trial['warmup'])
    assert result.report['workloads'][MODEL_ID]['response_format_version'] == 'fixture-requested-integer-v1'
    result.close()


def test_new_prompt_requires_an_explicit_format_and_does_not_guess_task_type(environment, tmp_path):
    result = environment.place(**formatted_inputs(environment), output_dir=tmp_path/'run')
    model = result.models[0]
    with pytest.raises(ValueError, match='response_format'):
        model.generate('new question')
    assert model.generate('new question', response_format=FORMAT).text == '4'
    with pytest.raises(ValueError, match='measured prompt'):
        changed = deepcopy(FORMAT)
        changed['json_schema']['schema']['properties']['answer']['type'] = 'string'
        model.generate('2+2', response_format=changed)
    result.close()


@pytest.mark.parametrize('change', ['version', 'schema', 'request'])
def test_reference_cannot_be_reused_under_a_changed_decoding_profile(environment, tmp_path, change):
    args = formatted_inputs(environment)
    environment.measure_placement_references(**args, output_dir=tmp_path/'reference')
    path = tmp_path/'reference'/'result.json'
    record = json.loads(path.read_text())
    if change == 'version':
        record['workloads'][MODEL_ID]['response_format_version'] = 'other'
    elif change == 'schema':
        record['workloads'][MODEL_ID]['response_formats'][0]['json_schema']['schema']['properties']['answer']['type'] = 'string'
    else:
        record['isolated'][MODEL_ID]['quality'][0].pop('response_format')
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        environment.place(**args, output_dir=tmp_path/'joint', isolated_reference=path)
    assert len(FakeModel.instances) == 2


def test_formats_need_one_entry_per_prompt_and_explicit_version():
    with pytest.raises(ValueError):
        PlacementWorkload(['question'], lambda *_:True, 'task-v1', response_formats=[FORMAT]).validated()
    with pytest.raises(ValueError):
        PlacementWorkload(['question'], lambda *_:True, 'task-v1', response_formats=[],
                          response_format_version='schema-v1').validated()
