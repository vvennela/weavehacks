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
