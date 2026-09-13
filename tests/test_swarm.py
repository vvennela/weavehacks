"""Offline swarm outcomes: parallel reads, shared findings, and one safe choice."""

from contextvars import ContextVar
from copy import deepcopy
from threading import Barrier

import pytest

from sera.agent import ArbiterDecision, Proposal
from sera.config import CONTROL_ROLES, MODEL_ID, RuntimeConfig, Workload
from sera.investigation import remaining_candidates
from sera.swarm import choose_swarm_experiments
from sera.tracing import InspectionReadError


context = ContextVar('swarm-test-context', default=None)
INVESTIGATORS = ('scheduling', 'memory_context', 'output_quality')


def evidence():
    return dict(trial_id='baseline', model_id=MODEL_ID, revision='pinned',
        configuration=RuntimeConfig().model_dump(), remaining_trials=4,
        metrics={'p95_latency_ms': 100}, supported_changes={
            'kv_cache_dtype': ['fp8'], 'max_num_batched_tokens': [2048]},
        history=[], previous_rounds=[], request_evidence={'config_hash': RuntimeConfig().config_hash})


def proposal(evidence, lever='max_num_batched_tokens', *, invalid=False, abstain=False):
    return Proposal(action='keep-baseline' if abstain else 'trial', proposal_id='same-id',
        agent_role=CONTROL_ROLES[lever], parent_trial_id='baseline', model_id=MODEL_ID,
        changed_lever=None if abstain else lever,
        proposed_value=None if abstain else evidence['supported_changes'][lever][0],
        evidence_used=['invented' if invalid else 'p95_latency_ms'],
        predicted_metric_change='Lower latency', confidence=.5,
        expected_trial_cost=0 if abstain else 1, falsification_condition='No measured gain',
        reason='Use observed latency')


class Agent:
    def __init__(self, *, initial_barrier=None, refine_barrier=None, invalid=False,
                 invalid_inspection=False, decline=False, abstain=False, child=False):
        self.history = []
        self.children = []
        self.initial_barrier, self.refine_barrier = initial_barrier, refine_barrier
        self.invalid, self.invalid_inspection = invalid, invalid_inspection
        self.decline, self.abstain, self.child = decline, abstain, child

    def fork(self):
        child = Agent(initial_barrier=self.initial_barrier, refine_barrier=self.refine_barrier,
            invalid=self.invalid, invalid_inspection=self.invalid_inspection,
            abstain=self.abstain, child=True)
        self.children.append(child)
        return child

    def request(self, role, supplied, instruction):
        self.history.append(dict(role=role, evidence=deepcopy(supplied), context=context.get()))
        if supplied.get('swarm_phase') == 'inspect':
            if self.initial_barrier and len(self.history) == 1:
                self.initial_barrier.wait(timeout=3)
            return ArbiterDecision(ranked_proposal_ids=(['forbidden'] if self.invalid_inspection
                else supplied['legal_proposal_ids'][:1]), reason='Inspect saved evidence')
        if role == 'arbiter':
            return ArbiterDecision(ranked_proposal_ids=[] if self.decline
                else supplied['legal_proposal_ids'][:1], reason='Rank evidence')
        if supplied['swarm_phase'] == 'refine' and self.refine_barrier:
            self.refine_barrier.wait(timeout=3)
        lever = ('kv_cache_dtype' if supplied['investigator_id'] == 'memory_context'
                 and supplied['swarm_phase'] == 'propose' else 'max_num_batched_tokens')
        return proposal(supplied, lever, invalid=self.invalid, abstain=self.abstain)


def run(agent, reader=None):
    supplied = evidence()
    legal = remaining_candidates(supplied, RuntimeConfig(), {RuntimeConfig().config_hash},
                                 Workload(), {'input_token_ids': [[1]]})
    record = dict(round=1, specialists=[], trial_ids=[])
    result = choose_swarm_experiments(agent, supplied, legal, record, 4,
        reader or (lambda query_id, request: {'query_id': query_id, 'source': 'fixture'}))
    return result, record


def test_parallel_inspections_and_refinement_share_findings_without_history_races():
    agent = Agent(initial_barrier=Barrier(3), refine_barrier=Barrier(3))
    token = context.set('parent-trace')
    try:
        chosen, record = run(agent)
    finally:
        context.reset(token)
    assert len(chosen) == 1  # No forced exploration even with four trials left.
    assert len(agent.children) == 3
    assert len({id(child.history) for child in agent.children}) == 3
    assert [entry['investigator_id'] for entry in record['shared_findings']] == list(INVESTIGATORS)
    for child in agent.children:
        assert len(child.history) == 4  # two queries, initial proposal, refinement
        assert all(call['context'] == 'parent-trace' for call in child.history)
        assert child.history[-1]['evidence']['shared_findings'] == record['shared_findings']
        assert len(child.history[-1]['evidence']['shared_findings']) == 3
        assert child.history[2]['evidence']['supported_changes'] == evidence()['supported_changes']
    merged = agent.history[:-1]
    assert [entry['investigator_id'] for entry in merged] == [name for name in INVESTIGATORS for _ in range(4)]
    assert agent.history[-1]['role'] == 'arbiter'
    assert len(record['arbiter_evidence']['legal_proposal_ids']) == 3
    assert record['specialists'][1]['initial_proposal']['changed_lever'] == 'kv_cache_dtype'
    assert record['specialists'][1]['proposal']['changed_lever'] == 'max_num_batched_tokens'
    assert record['specialists'][1]['role'] == 'batching'
    for phase in ('initial', 'refine'):
        intervals = [item['phase_timings'][phase] for item in record['specialists']]
        assert max(item['started_monotonic'] for item in intervals) < min(
            item['ended_monotonic'] for item in intervals)
    for item in record['specialists']:
        assert item['evidence']['shared_findings_hash'] == record['swarm']['shared_findings_hash']


@pytest.mark.parametrize('failure', ['invalid', 'decline', 'abstain'])
def test_invalid_citations_abstention_and_empty_arbiter_never_force_trial(failure):
    chosen, record = run(Agent(**{failure: True}))
    assert chosen == []
    assert len(record['specialists']) == 3
    if failure == 'invalid':
        assert all(item['status'] == 'rejected' for item in record['specialists'])
        assert all(item['initial_proposal']['evidence_used'] == ['invented']
                   and item['proposal']['evidence_used'] == ['invented']
                   for item in record['specialists'])
    if failure == 'abstain':
        assert all(item['status'] == 'abstained' for item in record['specialists'])


def test_invalid_inspection_never_reaches_reader_and_errors_are_saved():
    reads = []
    chosen, record = run(Agent(invalid_inspection=True), lambda *args: reads.append(args))
    assert reads == []
    assert len(chosen) == 1  # Independently valid proposals still use existing measurements.
    assert all(item['inspections'][0]['error'] == 'ValueError' for item in record['swarm']['investigators'])


def test_reader_failure_is_explicit_and_cannot_mutate_shared_evidence():
    def fail(query_id, supplied):
        supplied['metrics']['p95_latency_ms'] = -100
        raise RuntimeError('secret should not be saved')
    chosen, record = run(Agent(), fail)
    assert len(chosen) == 1
    assert all(item['inspections'][0]['error'] == 'RuntimeError' for item in record['swarm']['investigators'])
    assert record['arbiter_evidence']['metrics']['p95_latency_ms'] == 100
    assert all(item['degraded'] and item['inspection_status'] == 'degraded'
               for item in record['shared_findings'])
    assert all(item['evidence']['degraded'] for item in record['specialists'])
    assert 'secret should not be saved' not in str(record)


def test_shared_fork_history_is_rejected_before_any_parallel_requests():
    agent = Agent()
    agent.fork = lambda: agent
    chosen, record = run(agent)
    assert chosen == []
    assert not agent.history
    assert record['swarm']['error'] == 'ValueError'


def test_refinement_failure_does_not_silently_reuse_initial_proposal():
    agent = Agent()
    original_fork = agent.fork
    def fork():
        child = original_fork()
        request = child.request
        def fail_refinement(role, supplied, instruction):
            if supplied.get('swarm_phase') == 'refine':
                raise RuntimeError('failed refinement')
            return request(role, supplied, instruction)
        child.request = fail_refinement
        return child
    agent.fork = fork
    chosen, record = run(agent)
    assert chosen == []
    assert all(item['initial_status'] == 'accepted' and item['status'] == 'rejected'
               and item['error'] == 'RuntimeError' for item in record['specialists'])


def test_non_record_reader_result_is_an_explicit_inspection_failure():
    chosen, record = run(Agent(), lambda *_: object())
    assert len(chosen) == 1
    assert all(item['inspections'][0]['status'] == 'failed'
               and 'result' not in item['inspections'][0]
               for item in record['swarm']['investigators'])


def test_reader_failure_uses_allowlisted_explanation_not_exception_text():
    def reader(*args):
        error = InspectionReadError('incomplete-requests')
        error.safe_message = 'unsafe overwritten instance message'
        error.args = ('secret error text',)
        raise error
    _, record = run(Agent(), reader)
    for investigator in record['swarm']['investigators']:
        error = investigator['inspections'][0]
        assert error['reason_code'] == 'incomplete-requests'
        assert error['safe_message'] == InspectionReadError.messages['incomplete-requests']
    assert 'secret error text' not in str(record)
    assert 'unsafe overwritten' not in str(record)
