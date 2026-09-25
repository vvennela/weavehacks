"""Astra implementation with fifteen independent Luna advisory calls per round."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time

from .codex_agent import CodexJSONAgent
from .kernel_advisor_roles import ADVISOR_ROLES, DEFAULT_ADVISOR_IDS
from .kernel_search import KernelCandidate
from .storage import save_json


def object_schema(properties):
    return dict(type='object', additionalProperties=False,
                properties=properties, required=list(properties))


PLAN_SCHEMA = object_schema(dict(
    roles=dict(type='array', items=dict(type='string', enum=list(ADVISOR_ROLES)),
               minItems=15, maxItems=15), rationale=dict(type='string')))
ADVICE_SCHEMA = object_schema(dict(advice=dict(type='string'), risks=dict(type='string'),
                                  abstain=dict(type='boolean')))
SOURCE_SCHEMA = object_schema(dict(name=dict(type='string'), hypothesis=dict(type='string'),
                                  source=dict(type='string'), stop=dict(type='boolean')))
RULES = (
    'Use only supplied evidence. No tools, file reads, commands, services or private evaluator inputs. '
    'Preserve the fixed benchmark, FP32 arithmetic, general gemm ABI, thread count and error tolerance. '
    'No external libraries, answer caching, input-specific outputs, or evaluator changes. '
    'All packing and allocation stays inside gemm. Advice is unverified, not a measured fact. '
    'Do not infer causality from noisy scores or attribute joint outcomes to one advisor. '
)


class KernelAdvisoryTeam:
    """Caller owns budgets and evaluation; Astra chooses roles and implements.

    Each round makes two Astra-high calls and fifteen Luna calls. Independent
    advice goes only to the coordinator, avoiding all-to-all communication.
    Evaluated history is supplied by kernel_search, never by an agent.
    """

    def __init__(self, *, work_dir, task, profile, max_rounds=6, timeout=180,
                 agent_factory=None):
        if type(max_rounds) is not int or not 0 <= max_rounds <= 100:
            raise ValueError('max_rounds must be an integer from 0 to 100')
        self.folder = Path(work_dir).resolve()
        self.folder.mkdir(parents=True, exist_ok=False)
        self.task, self.profile = task, json.loads(json.dumps(profile))
        self.max_rounds, self.timeout = max_rounds, timeout
        self.factory = agent_factory or CodexJSONAgent
        self.rounds, self.identity = [], None
        self._save()

    def _save(self):
        save_json(self.folder / 'state.json', dict(
            schema_version='sera-kernel-advisory-v1', coordinator='gpt-6-astra',
            coordinator_reasoning='high', advisor_model='gpt-6-luna', advisor_count=15,
            max_rounds=self.max_rounds, max_model_calls=self.max_rounds * 17,
            profile=self.profile, rounds=self.rounds))

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
                'promoted', 'error', 'comparison_identity')}
                | dict(source=Path(trial['source']).read_text()))
            for record in self.rounds:
                if record.get('source_hash') == trial.get('source_hash'):
                    record['measured_outcome'] = {key: trial.get(key) for key in (
                        'status', 'scores', 'control_scores', 'promoted', 'reports',
                        'comparison_identity', 'public_correctness')}
        self._save()
        return evidence

    def _advise(self, role, folder, common, deadline):
        agent = self.factory(work_dir=folder / role, model='gpt-6-luna',
                             reasoning_effort='medium', timeout=self.timeout)
        memory = [dict(advice=next((a for a in r['advice'] if a['role'] == role), None),
                       outcome=r.get('measured_outcome'))
                  for r in self.rounds[:-1] if role in r.get('roles', [])][-4:]
        result = agent.request(common + '\nYou advise Sera; do not implement a complete source. '
            'Give one concrete, technically supported change, risks, and checks. '
            'You may abstain when no legal useful change is known. Your role: ' + role + '. '
            + ADVISOR_ROLES[role] + '\nYour prior advice and joint measured outcomes:\n'
            + json.dumps(memory), ADVICE_SCHEMA, timeout=self._remaining(deadline))
        if (set(result) != {'advice', 'risks', 'abstain'} or
                type(result['abstain']) is not bool or
                any(not isinstance(result[key], str) for key in ('advice', 'risks'))):
            raise ValueError('Malformed advisor response')
        return dict(role=role, status='received', **result)

    def observe(self, history):
        """Save the last measured outcome even when the search budget ends."""
        self._evidence(history)

    def propose(self, history, *, timeout):
        deadline = time.monotonic() + timeout
        self._remaining(deadline)
        evidence = self._evidence(history)
        if len(self.rounds) >= self.max_rounds:
            return None
        folder = self.folder / f'round-{len(self.rounds)+1:03d}'
        folder.mkdir()
        record = dict(round=len(self.rounds)+1, status='planning', roles=[], advice=[])
        self.rounds.append(record)
        self._save()
        common = RULES + '\n' + self.task + '\nHardware profile:\n' + json.dumps(self.profile)
        common += '\nMeasured history:\n' + json.dumps(evidence)
        coordinator = self.factory(work_dir=folder / 'coordinator', model='gpt-6-astra',
                                   reasoning_effort='high', timeout=self.timeout)
        try:
            plan = coordinator.request(common + '\nYou are Sera, the implementing coordinator. '
                'Select exactly 15 distinct relevant advisor IDs from this catalog. You may '
                'replace any prior advisor at each round based on evidence. Role descriptions '
                'and benchmark policies are fixed. Explain the selection.\nCatalog:\n'
                + json.dumps(ADVISOR_ROLES) + '\nDefault roster:\n' + json.dumps(DEFAULT_ADVISOR_IDS)
                + '\nPrior rosters:\n' + json.dumps([r['roles'] for r in self.rounds[:-1]]),
                PLAN_SCHEMA, timeout=self._remaining(deadline))
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
            record['status'] = 'implementing'
            self._save()
            response = coordinator.request(common + '\nYou are Sera. Critically review the '
                '15 independent advisories below; they may be wrong or contradictory. Choose '
                'one coherent improvement and implement the complete standalone C source. '
                'Preserve all invariants. Do not claim a speedup before measurement. '
                'Return stop=true only when no useful legal improvement remains.\nAdvisories:\n'
                + json.dumps(record['advice']), SOURCE_SCHEMA, timeout=self._remaining(deadline))
            if type(response.get('stop')) is not bool:
                raise ValueError('Malformed coordinator response')
            if response['stop']:
                record['status'] = 'abstained'
                self._save()
                return None
            candidate = KernelCandidate(response['name'], response['source'],
                                        response['hypothesis'], 'astra_coordinator')
            record.update(status='proposed', source_hash=hashlib.sha256(candidate.source.encode()).hexdigest(),
                          name=candidate.name, hypothesis=candidate.hypothesis)
            self._save()
            return candidate
        except BaseException as error:
            record.update(status='failed', error=f'{type(error).__name__}: {error}')
            self._save()
            raise
