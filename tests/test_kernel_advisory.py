import json
from pathlib import Path

import pytest

from sera.kernel_advisory import KernelAdvisoryTeam
from sera.kernel_advisor_roles import ADVISOR_ROLES, DEFAULT_ADVISOR_IDS


def history(tmp_path):
    source = tmp_path / 'kernel.c'
    source.write_text('baseline source')
    return [dict(name='baseline', source=str(source), source_hash='baseline',
                 status='passed', scores=[1000]*3, control_scores=[], reports=['signed.json'],
                 comparison_identity={'tree_hash':'frozen'})]


def factory_for(calls, rosters=None, fail_advisor=False):
    rosters = iter(rosters or [list(DEFAULT_ADVISOR_IDS)])
    def factory(**settings):
        class Agent:
            def request(self, prompt, schema, *, timeout):
                calls.append((settings, prompt))
                if 'roles' in schema['properties']:
                    return dict(roles=next(rosters), rationale='Measured bottlenecks')
                if 'ranking' in schema['properties']:
                    return dict(ranking=schema['properties']['ranking']['items']['enum'], reason='Collective preference')
                if settings['model'] == 'gpt-6-luna':
                    if fail_advisor:
                        raise RuntimeError('advisor failed')
                    return dict(advice='Use fixed FP32 loop bounds', risks='Check tails', abstain=False)
                return dict(name='coordinated', source='new source', hypothesis='constant loops', stop=False)
        return Agent()
    return factory


def test_fifteen_luna_advise_one_astra_high_implementation(tmp_path):
    calls=[]
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team', task='FP32 only',
        profile={'capabilities':['cpu']}, max_rounds=1, agent_factory=factory_for(calls))
    candidate=team.propose(history(tmp_path), timeout=60)
    assert candidate.source == 'new source'
    assert candidate.specialist_id == 'astra_coordinator'
    assert len(calls) == 32
    assert sum(settings['model']=='gpt-6-luna' for settings,_ in calls)==30
    assert all(settings['reasoning_effort']=='high' for settings,_ in calls
               if settings['model']=='gpt-6-astra')
    assert 'Use fixed FP32 loop bounds' in calls[-1][1]
    assert team.propose(history(tmp_path),timeout=60) is None
    assert len(calls)==32


def test_coordinator_can_replace_roles_between_rounds(tmp_path):
    first=list(DEFAULT_ADVISOR_IDS)
    alternate=next(role for role in ADVISOR_ROLES if role not in first)
    second=first[:-1]+[alternate]
    calls=[]
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team',task='FP32 only',profile={},
        max_rounds=2,batch_size=1,agent_factory=factory_for(calls,[first,second]))
    measured=history(tmp_path)
    team.propose(measured,timeout=60)
    team.propose(measured,timeout=60)
    state=json.loads((tmp_path/'team/state.json').read_text())
    assert [r['roles'] for r in state['rounds']]==[first,second]


@pytest.mark.parametrize('roles',[['unknown']*15,list(DEFAULT_ADVISOR_IDS)[:-1]])
def test_invalid_roster_never_dispatches_advisors(tmp_path,roles):
    calls=[]
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team',task='test',profile={},
        agent_factory=factory_for(calls,[roles]))
    with pytest.raises(ValueError,match='15 distinct'):
        team.propose(history(tmp_path),timeout=60)
    assert len(calls)==1


def test_failed_advice_cannot_be_presented_as_verified_evidence(tmp_path):
    calls=[]
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team',task='test',profile={},
        agent_factory=factory_for(calls,fail_advisor=True))
    with pytest.raises(RuntimeError,match='advisors'):
        team.propose(history(tmp_path),timeout=60)
    state=json.loads((tmp_path/'team/state.json').read_text())
    assert all(r['status']=='failed' for r in state['rounds'][0]['advice'])
    assert len(calls)==16


def test_expired_deadline_dispatches_no_agents(tmp_path):
    calls=[]
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team',task='test',profile={},
        agent_factory=factory_for(calls))
    with pytest.raises(TimeoutError):
        team.propose(history(tmp_path),timeout=0)
    assert calls==[]


def test_advisory_team_is_exported():
    import sera
    assert sera.KernelAdvisoryTeam is KernelAdvisoryTeam


def test_astra_reviews_recorded_experiment_and_persists_reason(tmp_path):
    calls=[]
    def factory(**settings):
        class Agent:
            def request(self,prompt,schema,*,timeout):
                calls.append((settings,prompt))
                return dict(decision='reject',reason='The repeated timing gain is unconfirmed')
        return Agent()
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team',task='FP32',profile={},agent_factory=factory)
    measured=history(tmp_path)
    decision=team.adjudicate(measured,measured[0],eligible=False,timeout=60)
    assert decision['decision']=='reject'
    assert calls[0][0]['model']=='gpt-6-astra'
    assert calls[0][0]['reasoning_effort']=='high'
    assert '1000' in calls[0][1]
    state=json.loads((tmp_path/'team/state.json').read_text())
    assert state['adjudications'][0]['status']=='reviewed'
    assert state['adjudications'][0]['source_hash']=='baseline'


def test_setup_failure_is_recorded(tmp_path):
    def factory(**settings):
        raise OSError('setup failed')
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team',task='FP32',profile={},agent_factory=factory)
    with pytest.raises(OSError):
        team.propose(history(tmp_path),timeout=60)
    state=json.loads((tmp_path/'team/state.json').read_text())
    assert state['rounds'][0]['status']=='failed'


def test_swarm_selects_batch_astra_implements_without_selecting_again(tmp_path):
    calls=[]
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team',task='FP32',profile={},
        max_rounds=2,batch_size=2,agent_factory=factory_for(calls))
    measured=history(tmp_path)
    team.propose(measured,timeout=60)
    team.propose(measured,timeout=60)
    state=json.loads((tmp_path/'team/state.json').read_text())
    assert len(state['rounds'])==1
    assert len(state['rounds'][0]['ballots'])==15
    assert state['rounds'][0]['experiment_order']==list(DEFAULT_ADVISOR_IDS[:2])
    assert [r['experiment_id'] for r in state['rounds'][0]['implementations']]==list(DEFAULT_ADVISOR_IDS[:2])
    assert len(calls)==33  # one roster, 15 recommendations, 15 votes, two implementations
    assert 'Swarm-selected experiment' in calls[-1][1]


def test_every_specialist_ranks_the_same_board_and_calls_stay_bounded(tmp_path):
    calls=[]
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team',task='FP32',profile={},
        max_rounds=1,max_calls=32,agent_factory=factory_for(calls))
    team.propose(history(tmp_path),timeout=60)
    votes=[prompt for _,prompt in calls if 'Immutable shared board:' in prompt]
    assert len(votes)==15
    assert len({p.split('Immutable shared board:')[1] for p in votes})==1
    assert team.calls==32
    with pytest.raises(RuntimeError,match='budget'):
        team.adjudicate(history(tmp_path),history(tmp_path)[0],eligible=False,timeout=60)
    assert len(calls)==32


def test_second_batch_implementation_receives_fresh_experiment_evidence(tmp_path):
    calls=[]
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team',task='FP32',profile={},
        max_rounds=2,batch_size=2,agent_factory=factory_for(calls))
    measured=history(tmp_path)
    team.propose(measured,timeout=60)
    measured[0]['scores']=[1234.5]*3
    team.propose(measured,timeout=60)
    assert '1234.5' in calls[-1][1]


def test_invalid_specialist_ranking_gets_one_bounded_format_repair(tmp_path):
    calls=[]
    base=factory_for(calls)
    attempts={}
    def factory(**settings):
        agent=base(**settings)
        original=agent.request
        def request(prompt,schema,*,timeout):
            if 'ranking' in schema['properties']:
                role=str(settings['work_dir'])
                attempts[role]=attempts.get(role,0)+1
                if attempts[role]==1:
                    calls.append((settings,prompt))
                    ids=schema['properties']['ranking']['items']['enum']
                    return dict(ranking=[ids[0]]*len(ids),reason='invalid repeated ID')
            return original(prompt,schema,timeout=timeout)
        agent.request=request
        return agent
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team',task='FP32',profile={},
        max_rounds=1,agent_factory=factory)
    assert team.propose(history(tmp_path),timeout=60).source=='new source'
    assert set(attempts.values())=={2}
    assert len(calls)==47
    state=json.loads((tmp_path/'team/state.json').read_text())
    assert all(vote['format_repairs']==1 for vote in state['rounds'][0]['ballots'])


@pytest.mark.parametrize('attempt_budget,expected_source', [(3, None), (4, 'new source')])
def test_duplicate_batch_replans_only_with_remaining_attempts(tmp_path, attempt_budget, expected_source):
    calls = []
    roster = list(DEFAULT_ADVISOR_IDS)
    base = factory_for(calls, [roster, roster])

    def factory(**settings):
        agent = base(**settings)
        original = agent.request

        def request(prompt, schema, *, timeout):
            result = original(prompt, schema, timeout=timeout)
            folder = Path(settings['work_dir']).name
            if folder.startswith('implementation-') and int(folder.split('-')[1]) <= 3:
                return dict(name='duplicate', source='', hypothesis='Already tested', stop=True)
            return result

        agent.request = request
        return agent

    team = KernelAdvisoryTeam(work_dir=tmp_path/'team', task='FP32', profile={},
        max_rounds=attempt_budget, batch_size=3, agent_factory=factory)
    candidate = team.propose(history(tmp_path), timeout=60)
    assert (candidate.source if candidate else None) == expected_source
    assert team.proposal_count == attempt_budget
    assert len(team.rounds) == (2 if expected_source else 1)
    assert team.calls == (66 if expected_source else 34)


def test_astra_can_edit_a_hash_bound_source_without_repeating_the_file(tmp_path):
    import hashlib
    calls = []
    measured = history(tmp_path)
    measured[0]['source_hash'] = hashlib.sha256(b'baseline source').hexdigest()
    base = factory_for(calls)

    def factory(**settings):
        agent = base(**settings)
        original = agent.request

        def request(prompt, schema, *, timeout):
            result = original(prompt, schema, timeout=timeout)
            if Path(settings['work_dir']).name.startswith('implementation-'):
                return dict(name='edited', hypothesis='Change the measured source', stop=False,
                    source='', base_source_hash=measured[0]['source_hash'],
                    edits=[dict(old='baseline source', new='modified source')])
            return result

        agent.request = request
        return agent

    team = KernelAdvisoryTeam(work_dir=tmp_path/'team', task='FP32', profile={},
        max_rounds=1, agent_factory=factory)
    candidate = team.propose(measured, timeout=60)
    assert candidate.source == 'modified source'
    assert Path(measured[0]['source']).read_text() == 'baseline source'
    saved = json.loads((tmp_path/'team/state.json').read_text())
    assert saved['rounds'][0]['implementations'][0]['source_hash'] == hashlib.sha256(
        b'modified source').hexdigest()


def test_duplicate_source_response_advances_to_next_ranked_experiment(tmp_path):
    import hashlib
    calls = []
    measured = history(tmp_path)
    measured[0]['source_hash'] = hashlib.sha256(b'baseline source').hexdigest()
    base = factory_for(calls)

    def factory(**settings):
        agent = base(**settings)
        original = agent.request

        def request(prompt, schema, *, timeout):
            result = original(prompt, schema, timeout=timeout)
            if Path(settings['work_dir']).name == 'implementation-001':
                return dict(name='no-op', hypothesis='Unchanged experiment', stop=False,
                    source='', base_source_hash=measured[0]['source_hash'],
                    edits=[dict(old='baseline source', new='baseline source')])
            return result

        agent.request = request
        return agent

    team = KernelAdvisoryTeam(work_dir=tmp_path/'team', task='FP32', profile={},
        max_rounds=2, batch_size=2, agent_factory=factory)
    candidate = team.propose(measured, timeout=60)
    assert candidate.source == 'new source'
    records = team.rounds[0]['implementations']
    assert [item['experiment_id'] for item in records] == list(DEFAULT_ADVISOR_IDS[:2])
    assert [item['status'] for item in records] == ['abstained', 'proposed']
    assert team.calls == 33
    assert team.proposal_count == 2


def test_replacement_specialists_receive_skipped_experiment_reasons(tmp_path):
    calls = []
    team = KernelAdvisoryTeam(work_dir=tmp_path/'team', task='FP32 only', profile={},
        max_rounds=2, batch_size=1, agent_factory=factory_for(calls))
    team.rounds = [dict(round=1, roles=[], advice=[], implementations=[dict(
        experiment_id='vector_access', status='abstained',
        reason='Paired LD1W has no post-index writeback form')], board=[dict(
        experiment_id='vector_access', recommendation='Fold pointer updates into paired loads',
        risks='Instruction legality')])]
    candidate = team.propose(history(tmp_path), timeout=60)
    assert candidate.source == 'new source'
    # The roster selector, every advisor, every voter, and the implementer get
    # the skipped proposal and its disposition, even when their roles changed.
    assert len(calls) == 32
    for _, prompt in calls:
        assert 'Fold pointer updates into paired loads' in prompt
        assert 'Paired LD1W has no post-index writeback form' in prompt
        assert 'abstained' in prompt


@pytest.mark.parametrize("call_limit", [32, 33])
def test_implementation_timeout_consumes_attempt_and_keeps_ranked_queue(tmp_path, call_limit):
    import subprocess
    calls = []
    base_factory = factory_for(calls)
    attempts = []
    def factory(**settings):
        base = base_factory(**settings)
        class Agent:
            def request(self, prompt, schema, *, timeout):
                if 'source' in schema['properties']:
                    attempts.append(prompt)
                    if len(attempts) == 1:
                        calls.append((settings, prompt))
                        raise subprocess.TimeoutExpired('codex', timeout)
                return base.request(prompt, schema, timeout=timeout)
        return Agent()
    team = KernelAdvisoryTeam(work_dir=tmp_path/'team', task='FP32', profile={},
        max_rounds=2, batch_size=2, agent_factory=factory, max_calls=call_limit)
    if call_limit == 32:
        with pytest.raises(subprocess.TimeoutExpired):
            team.propose(history(tmp_path), timeout=60)
        assert team.calls == 32
        assert team.proposal_count == 1
        assert team.pending == [DEFAULT_ADVISOR_IDS[1]]
        return
    candidate = team.propose(history(tmp_path), timeout=60)
    assert candidate.source == 'new source'
    assert team.calls == 33
    assert team.proposal_count == 2
    assert len(team.rounds) == 1
    records = team.rounds[0]['implementations']
    assert [r['experiment_id'] for r in records] == list(DEFAULT_ADVISOR_IDS[:2])
    assert [r['status'] for r in records] == ['failed', 'proposed']
    assert 'TimeoutExpired' in records[0]['error']
    assert team.propose(history(tmp_path), timeout=60) is None


def test_astra_can_select_strassen_specialist_without_increasing_swarm_size(tmp_path):
    roster = list(DEFAULT_ADVISOR_IDS[:-1]) + ['strassen_one_level']
    calls = []
    team = KernelAdvisoryTeam(work_dir=tmp_path/'team',
        task='User approved one-level FP32 Strassen with unchanged gates', profile={},
        max_rounds=1, agent_factory=factory_for(calls, [roster]))
    candidate = team.propose(history(tmp_path), timeout=60)
    assert candidate.source == 'new source'
    state = json.loads((tmp_path/'team/state.json').read_text())
    assert state['rounds'][0]['roles'] == roster
    assert len(state['rounds'][0]['advice']) == 15
    assert len(state['rounds'][0]['ballots']) == 15
    assert sum(settings['model'] == 'gpt-6-luna' for settings, _ in calls) == 30


def test_all_prompt_routes_share_sources_but_apply_edits_to_full_measured_base(tmp_path):
    import hashlib
    body = ''.join(f'float value_{i} = {i};\n' for i in range(2000))
    sources = [body+'float marker = 1;\n', body+'float marker = 2;\n']
    measured = []
    for index, source in enumerate(sources):
        path = tmp_path/f'kernel-{index}.c'
        path.write_text(source)
        measured.append(dict(name=str(index),source=str(path),
            source_hash=hashlib.sha256(source.encode()).hexdigest(),status='passed',
            scores=[1000+index]*10,control_scores=[1000]*10,comparison_identity={'tree_hash':'frozen'}))
    prompts = []
    def factory(**settings):
        class Agent:
            def request(self, prompt, schema, *, timeout):
                prompts.append(prompt)
                assert 'prompt_source_patch' in prompt
                assert json.dumps(sources[1]) not in prompt
                if 'roles' in schema['properties']:
                    return dict(roles=list(DEFAULT_ADVISOR_IDS),rationale='test')
                if 'ranking' in schema['properties']:
                    return dict(ranking=schema['properties']['ranking']['items']['enum'],reason='test')
                if 'advice' in schema['properties']:
                    return dict(advice='change marker',risks='test',abstain=False)
                if 'decision' in schema['properties']:
                    return dict(decision='reject',reason='ineligible')
                return dict(name='edited',hypothesis='test',stop=False,source='',
                    base_source_hash=measured[1]['source_hash'],
                    edits=[dict(old='float marker = 2;',new='float marker = 3;')])
        return Agent()
    team = KernelAdvisoryTeam(work_dir=tmp_path/'team',task='test',profile={},
                              max_rounds=1,agent_factory=factory)
    candidate = team.propose(measured,timeout=60)
    assert candidate.source == sources[1].replace('marker = 2','marker = 3')
    team.adjudicate(measured,measured[1],eligible=False,timeout=60)
    assert len(prompts) == 33
    assert [Path(r['source']).read_text() for r in measured] == sources
