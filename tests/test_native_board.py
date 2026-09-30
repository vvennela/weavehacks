from sera.native_board import rank_ballots


def test_joint_rank_uses_every_ballot_and_stable_ties():
    assert rank_ballots([['b', 'a', 'c'], ['c', 'b', 'a']], ['a', 'b', 'c']) == ['b', 'c', 'a']


def test_invalid_ballot_cannot_enter_the_board():
    import pytest
    with pytest.raises(ValueError):
        rank_ballots([['a', 'a']], ['a', 'b'])


def test_fifteen_specialists_vote_on_shared_board_before_batch_selection(tmp_path):
    import json
    from sera.native_board import NativeBoard, ROLES

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
