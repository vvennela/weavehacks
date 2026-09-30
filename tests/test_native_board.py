from sera.native_board import rank_ballots


def test_joint_rank_uses_every_ballot_and_stable_ties():
    assert rank_ballots([['b', 'a', 'c'], ['c', 'b', 'a']], ['a', 'b', 'c']) == ['b', 'c', 'a']


def test_invalid_ballot_cannot_enter_the_board():
    import pytest
    with pytest.raises(ValueError):
        rank_ballots([['a', 'a']], ['a', 'b'])


def test_fifteen_specialists_vote_on_shared_board_before_batch_selection(tmp_path):
    import json

    from sera.native_board import ROLES, NativeBoard

    created = []
    class Agent:
        def __init__(self, **kwargs):
            self.model = kwargs['model']
            self.prompts = []
            created.append(self)
        def request(self, prompt, schema, *, timeout):
            self.prompts.append(prompt)
            properties = schema['properties']
            if 'roles' in properties:
                return {'roles': ROLES, 'reason': 'Assign each distinct role.'}
            if 'recipe_id' in properties:
                return {'recipe_id': 'b', 'reason': 'Protect sensitive weights.', 'risk': 'Quality loss.'}
            assert 'Shared proposal board:' in prompt
            assert all(role in prompt for role in ROLES)
            return {'ranking': ['b', 'a', 'c'], 'reason': 'Joint review.'}
    board = NativeBoard(tmp_path / 'board', agent_factory=Agent)
    evidence = {'available_recipes': [{'recipe_id': key} for key in ['a', 'b', 'c']]}
    assert board.plan(evidence, timeout_seconds=10) == ['b', 'a']
    assert len(created) == 16
    assert created[0].model == 'gpt-6-astra'
    assert all(agent.model == 'gpt-6-luna' and len(agent.prompts) == 2 for agent in created[1:])
    saved = json.loads((tmp_path / 'board' / 'board.json').read_text())
    assert len(saved['proposals']) == len(saved['ballots']) == 15
    assert board.propose(evidence, timeout_seconds=10).recipe_id == 'b'
    remaining = {'available_recipes': [{'recipe_id': key} for key in ['a', 'c']]}
    assert board.propose(remaining, timeout_seconds=10).recipe_id == 'a'


class SchemaAgent:
    def __init__(self, **kwargs):
        self.model = kwargs['model']
        kwargs['work_dir'].mkdir(parents=True, exist_ok=False)
    def request(self, prompt, schema, *, timeout):
        from sera.native_board import ROLES
        fields = schema['properties']
        if 'roles' in fields:
            return {'roles': ROLES, 'reason': 'Assign roles.'}
        if 'recipe_id' in fields:
            return {'recipe_id': fields['recipe_id']['enum'][0], 'reason': 'New experiment.', 'risk': 'Unknown quality.'}
        if 'ranking' in fields:
            return {'ranking': fields['ranking']['items']['enum'], 'reason': 'Joint order.'}
        return {'decision': 'adopt', 'reason': 'Software gates passed.'}


def test_board_resume_keeps_pending_batch_and_request_budget(tmp_path):
    from sera.native_board import NativeBoard
    evidence = {'available_recipes': [{'recipe_id': x} for x in ['a', 'b', 'c']]}
    folder = tmp_path / 'board'
    board = NativeBoard(folder, agent_factory=SchemaAgent, max_model_calls=64)
    assert board.propose(evidence, timeout_seconds=10).recipe_id == 'a'
    assert len(board.model_calls) == 31
    resumed = NativeBoard(folder, agent_factory=SchemaAgent, max_model_calls=64, resume=True)
    assert resumed.propose(evidence, timeout_seconds=10).recipe_id == 'b'
    assert len(resumed.model_calls) == 31
    evidence = {'available_recipes': [{'recipe_id': 'c'}]}
    assert resumed.propose(evidence, timeout_seconds=10).recipe_id == 'c'
    assert len(resumed.model_calls) == 62
    assert resumed.review({'software_gates_passed': True}, timeout_seconds=10)['decision'] == 'adopt'
    assert len(resumed.model_calls) == 63


def test_board_excludes_already_measured_prior_recipes(tmp_path):
    from sera.native_board import NativeBoard
    evidence = {'available_recipes': [{'recipe_id': x} for x in ['failed', 'new', 'another']],
                'prior': {'trials': [{'recipe_id': 'failed', 'quality': .8}]}}
    board = NativeBoard(tmp_path / 'board', agent_factory=SchemaAgent)
    assert board.plan(evidence, timeout_seconds=10) == ['new', 'another']


def test_board_cannot_start_a_batch_without_31_requests_left(tmp_path):
    import pytest

    from sera.native_board import NativeBoard
    board = NativeBoard(tmp_path / 'board', agent_factory=SchemaAgent, max_model_calls=30)
    with pytest.raises(RuntimeError, match='budget'):
        board.plan({'available_recipes': [{'recipe_id': 'a'}]}, timeout_seconds=10)
    assert not board.model_calls
