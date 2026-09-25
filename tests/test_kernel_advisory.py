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
    assert len(calls) == 17
    assert sum(settings['model']=='gpt-6-luna' for settings,_ in calls)==15
    assert all(settings['reasoning_effort']=='high' for settings,_ in calls
               if settings['model']=='gpt-6-astra')
    assert 'Use fixed FP32 loop bounds' in calls[-1][1]
    assert team.propose(history(tmp_path),timeout=60) is None
    assert len(calls)==17


def test_coordinator_can_replace_roles_between_rounds(tmp_path):
    first=list(DEFAULT_ADVISOR_IDS)
    alternate=next(role for role in ADVISOR_ROLES if role not in first)
    second=first[:-1]+[alternate]
    calls=[]
    team=KernelAdvisoryTeam(work_dir=tmp_path/'team',task='FP32 only',profile={},
        max_rounds=2,agent_factory=factory_for(calls,[first,second]))
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
