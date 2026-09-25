"""Specialists jointly rank experiments; Astra implements and reviews results."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
from threading import Lock

from .codex_agent import CodexJSONAgent
from .kernel_advisor_roles import ADVISOR_ROLES, DEFAULT_ADVISOR_IDS
from .kernel_search import KernelCandidate
from .kernel_edits import candidate_source
from .storage import content_hash, save_json
from .kernel_swarm_plan import rank_experiments


def object_schema(properties):
    return dict(type='object', additionalProperties=False,
                properties=properties, required=list(properties))


PLAN_SCHEMA = object_schema(dict(
    roles=dict(type='array', items=dict(type='string', enum=list(ADVISOR_ROLES)),
               minItems=15, maxItems=15), rationale=dict(type='string')))
ADVICE_SCHEMA = object_schema(dict(advice=dict(type='string'), risks=dict(type='string'),
                                  abstain=dict(type='boolean')))
REVIEW_SCHEMA = object_schema(dict(
    decision=dict(type='string', enum=['adopt', 'reject', 'revise']), reason=dict(type='string')))
SOURCE_SCHEMA = object_schema(dict(name=dict(type='string'), hypothesis=dict(type='string'),
    source=dict(type='string'), stop=dict(type='boolean'), base_source_hash=dict(type='string'),
    edits=dict(type='array', maxItems=64,
               items=object_schema(dict(old=dict(type='string'), new=dict(type='string'))))))
RULES = (
    'Use only supplied evidence. No tools, file reads, commands, services or private evaluator inputs. '
    'Preserve the fixed benchmark, FP32 arithmetic, general gemm ABI, thread count and error tolerance. '
    'No external libraries, answer caching, input-specific outputs, or evaluator changes. '
    'All packing and allocation stays inside gemm. Advice is unverified, not a measured fact. '
    'Do not infer causality from noisy scores or attribute joint outcomes to one advisor. '
)


class KernelAdvisoryTeam:
    """Caller owns budgets and evaluation; Astra chooses roles and implements.

    Each batch has fifteen specialist proposals and fifteen shared-board rankings.
    A central board replaces peer conversations; its text is repeated to each voter.
    Evaluated history is supplied by kernel_search, never by an agent.
    """

    def __init__(self, *, work_dir, task, profile, max_rounds=6, timeout=180,
                 agent_factory=None, batch_size=3, max_calls=108):
        if type(max_rounds) is not int or not 0 <= max_rounds <= 100:
            raise ValueError('max_rounds must be an integer from 0 to 100')
        if type(batch_size) is not int or not 1 <= batch_size <= 15:
            raise ValueError('batch_size must be from 1 to 15')
        if type(max_calls) is not int or max_calls < 1:
            raise ValueError('max_calls must be positive')
        self.batch_size, self.max_calls = batch_size, max_calls
        self.calls, self.proposal_count = 0, 0
        self.call_lock = Lock()
        self.pending, self.advisors = [], {}
        self.folder = Path(work_dir).resolve()
        self.folder.mkdir(parents=True, exist_ok=False)
        self.task, self.profile = task, json.loads(json.dumps(profile))
        self.max_rounds, self.timeout = max_rounds, timeout
        self.factory = agent_factory or CodexJSONAgent
        self.rounds, self.identity = [], None
        self.adjudications = []
        self._save()

    def _save(self):
        save_json(self.folder / 'state.json', dict(
            schema_version='sera-kernel-swarm-v2', coordinator='gpt-6-astra',
            coordinator_reasoning='high', advisor_model='gpt-6-luna', advisor_count=15,
            max_rounds=self.max_rounds, max_model_calls=self.max_calls, calls=self.calls, batch_size=self.batch_size,
            pending=list(self.pending), implementations=self.proposal_count,
            adjudications=self.adjudications,
            profile=self.profile, rounds=self.rounds))

    def _request(self, agent, prompt, schema, deadline):
        timeout = self._remaining(deadline)
        with self.call_lock:
            if self.calls >= self.max_calls:
                raise RuntimeError('Swarm model-call budget exhausted')
            self.calls += 1
        return agent.request(prompt, schema, timeout=timeout)

    def _remaining(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Kernel advisory deadline reached')
        return min(self.timeout, remaining)

    def _evidence(self, history):
        evidence = []
        for trial in history:
            identity = trial.get('comparison_identity')
            if identity:
                if self.identity is not None and identity != self.identity:
                    raise ValueError('Advisory comparison identity changed')
                self.identity = identity
            evidence.append({key: trial.get(key) for key in (
                'name', 'hypothesis', 'source_hash', 'status', 'scores', 'control_scores',
                'promoted', 'adjudication', 'error', 'comparison_identity')}
                | dict(source=Path(trial['source']).read_text()))
            for batch in self.rounds:
                for record in batch.get('implementations', []):
                    if record.get('source_hash') == trial.get('source_hash'):
                        record['measured_outcome'] = {key: trial.get(key) for key in (
                            'status', 'scores', 'control_scores', 'promoted', 'adjudication', 'reports',
                            'comparison_identity', 'public_correctness')}
        self._save()
        return evidence

    def _advise(self, role, folder, common, deadline):
        agent = self.factory(work_dir=folder / role, model='gpt-6-luna',
                             reasoning_effort='medium', timeout=self.timeout)
        self.advisors[role] = agent
        memory = [dict(advice=next((a for a in r['advice'] if a['role'] == role), None),
                       outcomes=[x.get('measured_outcome') for x in r.get('implementations', [])])
                  for r in self.rounds[:-1] if role in r.get('roles', [])][-4:]
        result = self._request(agent, common + '\nYou advise Sera; do not implement a complete source. '
            'Propose one distinct experiment: specify the change, hypothesis, risks, and checks. '
            'You may abstain when no legal useful change is known. Your role: ' + role + '. '
            + ADVISOR_ROLES[role] + '\nYour prior advice and joint measured outcomes:\n'
            + json.dumps(memory), ADVICE_SCHEMA, deadline)
        if (set(result) != {'advice', 'risks', 'abstain'} or
                type(result['abstain']) is not bool or
                any(not isinstance(result[key], str) for key in ('advice', 'risks'))):
            raise ValueError('Malformed advisor response')
        return dict(role=role, status='received', **result)

    def observe(self, history):
        """Save the last measured outcome even when the search budget ends."""
        self._evidence(history)

    def adjudicate(self, history, trial, *, eligible, timeout):
        """Let Astra judge the experiment; fixed gates remain non-overridable."""
        deadline = time.monotonic() + timeout
        self._remaining(deadline)
        evidence = self._evidence(history)
        if len(self.adjudications) >= self.max_rounds:
            raise RuntimeError('Coordinator experiment review budget exhausted')
        record = dict(source_hash=trial['source_hash'], eligible=eligible, status='reviewing')
        self.adjudications.append(record)
        self._save()
        try:
            agent = self.factory(work_dir=self.folder / f'review-{len(self.adjudications):03d}',
                                 model='gpt-6-astra', reasoning_effort='high', timeout=self.timeout)
            decision = self._request(agent, RULES + '\n' + self.task +
                '\nYou are Sera. Make the final decision on this measured candidate: adopt, '
                'reject, or revise. Base the decision on correctness, paired controls and '
                'repeat variation. Adopt only if the fixed evaluator gates marked it eligible. '
                'Reject discards this candidate; revise retains the incumbent and informs '
                'your next implementation. Explain the evidence.\nCandidate under review:\n' +
                json.dumps(dict(source_hash=trial['source_hash'], eligible=eligible)) +
                '\nMeasured history:\n' + json.dumps(evidence), REVIEW_SCHEMA, deadline)
            if (decision.get('decision') not in {'adopt', 'reject', 'revise'} or
                    not isinstance(decision.get('reason'), str)):
                raise ValueError('Malformed coordinator experiment review')
            record.update(status='reviewed', **decision)
            self._save()
            return decision
        except BaseException as error:
            record.update(status='failed', error=f'{type(error).__name__}: {error}')
            self._save()
            raise

    def propose(self, history, *, timeout):
        deadline = time.monotonic() + timeout
        while True:
            attempts_before = self.proposal_count
            candidate = self._propose_batch(history, deadline)
            if (candidate is not None or self.proposal_count >= self.max_rounds or
                    self.proposal_count == attempts_before):
                return candidate
            # An exhausted duplicate batch is not an exhausted search. Ask the
            # swarm for a fresh batch within the same deadline and call budget.

    def _propose_batch(self, history, deadline):
        self._remaining(deadline)
        evidence = self._evidence(history)
        if self.proposal_count >= self.max_rounds:
            return None
        common = RULES + '\n' + self.task + '\nHardware profile:\n' + json.dumps(self.profile)
        common += '\nMeasured history:\n' + json.dumps(evidence)
        dispositions = []
        for batch in self.rounds:
            proposals = {item['experiment_id']: item for item in batch.get('board', [])}
            for attempt in batch.get('implementations', []):
                dispositions.append(dict(
                    round=batch['round'], proposal=proposals.get(attempt['experiment_id']),
                    **{key: attempt[key] for key in
                       ('experiment_id', 'status', 'reason', 'error', 'source_hash')
                       if key in attempt}))
        common += ('\nPrior implementation dispositions (agent explanations are not measured '
                   'performance evidence; check against the supplied source and contract):\n'
                   + json.dumps(dispositions))
        if self.pending:
            return self._implement(common, deadline, evidence)
        folder = self.folder / f'round-{len(self.rounds)+1:03d}'
        folder.mkdir()
        record = dict(round=len(self.rounds)+1, status='planning', roles=[], advice=[],
                      ballots=[], implementations=[])
        self.rounds.append(record)
        self._save()
        try:
            coordinator = self.factory(work_dir=folder / 'coordinator', model='gpt-6-astra',
                                       reasoning_effort='high', timeout=self.timeout)
            plan = self._request(coordinator, common + '\nYou are Sera, the implementing coordinator. '
                'Select exactly 15 distinct relevant advisor IDs from this catalog. You may '
                'replace any prior advisor at each round based on evidence. Role descriptions '
                'and benchmark policies are fixed. Explain the selection.\nCatalog:\n'
                + json.dumps(ADVISOR_ROLES) + '\nDefault roster:\n' + json.dumps(DEFAULT_ADVISOR_IDS)
                + '\nPrior rosters:\n' + json.dumps([r['roles'] for r in self.rounds[:-1]]),
                PLAN_SCHEMA, deadline)
            roles = plan.get('roles')
            if (not isinstance(roles, list) or len(roles) != 15 or
                    any(not isinstance(role, str) for role in roles) or
                    len(set(roles)) != 15 or not set(roles) <= ADVISOR_ROLES.keys()):
                raise ValueError('Coordinator must select 15 distinct catalog advisor IDs')
            record.update(status='advising', roles=roles, rationale=plan.get('rationale'))
            self._save()
            with ThreadPoolExecutor(max_workers=15) as pool:
                futures = [(role, pool.submit(self._advise, role, folder, common, deadline))
                           for role in roles]
                for role, future in futures:
                    try:
                        advice = future.result()
                    except Exception as error:
                        advice = dict(role=role, status='failed', error=type(error).__name__)
                    record['advice'].append(advice)
                    self._save()
            if any(advice['status'] != 'received' for advice in record['advice']):
                raise RuntimeError('One or more Luna advisors failed; no complete advisory round')
            board = [dict(experiment_id=advice['role'], recommendation=advice['advice'],
                          risks=advice['risks']) for advice in record['advice'] if not advice['abstain']]
            if not board:
                record['status'] = 'abstained'
                self._save()
                return None
            ids = [item['experiment_id'] for item in board]
            record.update(status='ranking', board=board, board_hash=content_hash(board))
            self._save()
            vote_schema = object_schema(dict(
                ranking=dict(type='array', items=dict(type='string', enum=ids),
                             minItems=len(ids), maxItems=len(ids)), reason=dict(type='string')))
            with ThreadPoolExecutor(max_workers=15) as pool:
                votes = [(role, pool.submit(self._vote, role, common, board, record['board_hash'],
                                           vote_schema, deadline)) for role in roles]
                for role, future in votes:
                    try:
                        vote = future.result()
                        # Validate a full permutation before accepting any ranking.
                        rank_experiments(ids, [vote.get('ranking')], limit=1)
                        record['ballots'].append(dict(role=role, status='received', **vote))
                    except Exception as error:
                        record['ballots'].append(dict(role=role, status='failed', error=type(error).__name__))
                    self._save()
            if any(vote['status'] != 'received' for vote in record['ballots']):
                raise RuntimeError('One or more specialist rankings failed; batch was not selected')
            order = rank_experiments(ids, [vote['ranking'] for vote in record['ballots']],
                                     limit=min(self.batch_size, self.max_rounds-self.proposal_count))
            record.update(status='selected', experiment_order=order)
            self.pending = list(order)
            self._save()
            return self._implement(common, deadline, evidence)
        except BaseException as error:
            record.update(status='failed', error=f'{type(error).__name__}: {error}')
            self._save()
            raise

    def _vote(self, role, common, board, board_hash, schema, deadline):
        prompt = (common + '\nYou are the specialist ' + role + '. ' + ADVISOR_ROLES[role]
            + "\nReview the other specialists' proposals on the shared board. "
            'Rank EVERY experiment ID exactly once in the order the swarm should test them. '
            'Use measured evidence, expected benefit, and correctness risk. Your ranking helps '
            'select the batch; Astra does not choose the experiment order. Explain briefly. '
            '\nBoard hash: ' + board_hash + '\nImmutable shared board:\n' + json.dumps(board))
        ids = [item['experiment_id'] for item in board]
        for repair in range(2):
            vote = self._request(self.advisors[role], prompt, schema, deadline)
            try:
                if set(vote) != {'ranking', 'reason'} or not isinstance(vote['reason'], str):
                    raise ValueError('Malformed ranking response')
                rank_experiments(ids, [vote.get('ranking')], limit=1)
                return dict(vote, format_repairs=repair)
            except ValueError:
                if repair:
                    raise
                prompt += ('\nYour response was not a complete valid ranking. Repair the format '
                    'without changing the board. Include every ID once; no duplicates or omissions. '
                    '\nExact required IDs: ' + json.dumps(ids) + '\nInvalid response: ' + json.dumps(vote))

    def _implement(self, common, deadline, evidence):
        batch = self.rounds[-1]
        experiment = self.pending.pop(0)
        selected = next(item for item in batch['board'] if item['experiment_id'] == experiment)
        self.proposal_count += 1
        record = dict(experiment_id=experiment, status='implementing')
        batch['implementations'].append(record)
        self._save()
        try:
            coordinator = self.factory(work_dir=self.folder / f'implementation-{self.proposal_count:03d}',
                model='gpt-6-astra', reasoning_effort='high', timeout=self.timeout)
            response = self._request(coordinator, common + '\nYou are Sera. Implement the experiment '
                'selected by the specialist swarm below. Do not replace it with another experiment '
                'or combine unrelated changes. Use current measured history to avoid repeating '
                'a source. Check all hardware claims against the contract; return stop=true if '
                'this experiment cannot be implemented legally or has already been tested. '
                'Prefer small guarded source edits: set source to an empty string, copy the '
                'base_source_hash from measured history, and return edits with exact old/new '
                'text. Each old text must match exactly once; edits apply sequentially. '
                'Include enough surrounding text to disambiguate repeated assembly blocks. '
                'Preserve all unchanged code and license notices. For a full rewrite instead, '
                'return complete standalone C in source, an empty base_source_hash and no edits. '
                'For stop=true return empty source/base_source_hash and no edits. '
                'No unmeasured speedup claims. '
                '\nSwarm-selected experiment:\n' + json.dumps(selected), SOURCE_SCHEMA, deadline)
            if type(response.get('stop')) is not bool:
                raise ValueError('Malformed coordinator response')
            if response['stop']:
                record.update(status='abstained', reason=response.get('hypothesis'))
                self._save()
                if self.pending and self.proposal_count < self.max_rounds:
                    return self._implement(common, deadline, evidence)
                return None
            source = candidate_source(response, evidence)
            candidate = KernelCandidate(response['name'], source,
                                        response['hypothesis'], 'astra_coordinator')
            source_hash = hashlib.sha256(candidate.source.encode()).hexdigest()
            if any(item['source_hash'] == source_hash for item in evidence):
                record.update(status='abstained', source_hash=source_hash,
                              reason='Generated source duplicates an already measured source')
                self._save()
                if self.pending and self.proposal_count < self.max_rounds:
                    return self._implement(common, deadline, evidence)
                return None
            record.update(status='proposed', source_hash=source_hash,
                          name=candidate.name, hypothesis=candidate.hypothesis)
            self._save()
            return candidate
        except BaseException as error:
            record.update(status='failed', error=f'{type(error).__name__}: {error}')
            self._save()
            raise
