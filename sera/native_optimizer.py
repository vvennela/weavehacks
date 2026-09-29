"""Operator-side native research using fixed profiles and existing quality gates."""

import json
import re
import time
from copy import deepcopy
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from .backends.mlx import MLXRecipe
from .config import Budget, Constraints, Objective
from .hardware import ModelDescriptor
from .ledger import Ledger, encode_record
from .measurement import constraint_failures, objective_value, select_candidate
from .model_artifact import verify_artifact
from .native_agent import NativeRecipeAgent
from .native_measurement import native_trial
from .native_trace import trace_native_job
from .native_worker import MeasureJob, NativeWorkerError, run_native_job
from .storage import content_hash, save_json


class NativeTask(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid', allow_inf_nan=False)
    prompt: str | list[dict[str, str]]
    expected_json: JsonValue
    response_format: dict | None = None


class NativeProfile(BaseModel):
    """An operator-owned contract; agent output cannot modify any of these fields."""

    model_config = ConfigDict(strict=True, frozen=True, extra='forbid', allow_inf_nan=False)
    profile_id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    source: ModelDescriptor
    tasks: list[NativeTask] = Field(min_length=1)
    evaluation_version: str = Field(min_length=1)
    response_format_version: str | None = None
    recipes: dict[str, MLXRecipe]
    constraints: Constraints
    objective: Objective
    budget: Budget
    max_run_seconds: float = Field(gt=0)
    job_timeout_seconds: float = Field(gt=0)
    max_tokens: int = Field(ge=1)
    seed: int
    warmup: int = Field(ge=0)
    repetitions: int = Field(ge=1)

    @model_validator(mode='after')
    def validate_contract(self):
        if self.budget.max_candidate_trials is None:
            raise ValueError('Native research requires a bounded trial budget')
        if self.objective.priority != 'memory':
            raise ValueError('The native research objective is allocator memory')
        if not self.recipes or any(not re.fullmatch(r'[a-zA-Z0-9_-]+', key)
                                  or key in {'baseline', 'stop'} for key in self.recipes):
            raise ValueError('Supply named native recipes')
        hashes = [content_hash(recipe.model_dump()) for recipe in self.recipes.values()]
        if len(set(hashes)) != len(hashes) or any(r.bits == 16 for r in self.recipes.values()):
            raise ValueError('Supply distinct quantized recipes; the reference is BF16')
        answers = {}
        for task in self.tasks:
            key = content_hash(task.prompt)
            answer = content_hash(task.expected_json)
            if key in answers and answers[key] != answer:
                raise ValueError('Identical prompts cannot have conflicting expected outputs')
            answers[key] = answer
        MeasureJob.model_validate(self.measure_job('/validation-only', 'a' * 64))
        return self

    def measure_job(self, artifact, artifact_id):
        formats = [task.response_format for task in self.tasks]
        return {'operation': 'measure', 'backend': 'mlx', 'artifact': str(artifact),
                'artifact_id': artifact_id, 'prompts': [task.prompt for task in self.tasks],
                'max_tokens': self.max_tokens, 'seed': self.seed, 'warmup': self.warmup,
                'repetitions': self.repetitions,
                'response_formats': formats if any(x is not None for x in formats) else None,
                'response_format_version': self.response_format_version}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _score(text, expected):
    if not isinstance(text, str) or not text.strip() or len(text) > 16384:
        return False
    try:
        parsed = json.loads(text, object_pairs_hook=_unique_object)
        return json.dumps(parsed, sort_keys=True, allow_nan=False) == json.dumps(
            expected, sort_keys=True, allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        return False


class NativeRunStopped(RuntimeError):
    pass


class _Research:
    def __init__(self, profile, folder, ledger, agent, cancelled):
        self.profile, self.folder, self.ledger, self.agent = profile, folder, ledger, agent
        self.cancelled = cancelled
        self.started = time.monotonic()
        self.artifacts = {}
        self.report = {'schema_version': 'sera-native-research-v1', 'status': 'running',
                       'profile_id': profile.profile_id, 'profile_hash': content_hash(profile.model_dump()),
                       'model_id': profile.source.model_id, 'model_revision': profile.source.revision,
                       'constraints': profile.constraints.model_dump(), 'objective': profile.objective.model_dump(),
                       'evaluation': {'version': profile.evaluation_version,
                                      'task_hash': content_hash([task.model_dump() for task in profile.tasks])},
                       'execution': {'backend': 'mlx', 'budget': profile.budget.model_dump(),
                                     'max_run_seconds': profile.max_run_seconds,
                                     'job_timeout_seconds': profile.job_timeout_seconds},
                       'trials': [], 'agent_calls': [], 'jobs': [], 'candidate_trials_used': 0,
                       'selected_recipe_id': None, 'selected_artifact_id': None, 'artifact_path': None}
        self.save()

    def save(self):
        self.report['elapsed_seconds'] = time.monotonic() - self.started
        self.ledger.save(self.report)
        save_json(self.folder / 'result.json', self.report)

    def remaining(self):
        if self.cancelled is not None and self.cancelled.is_set():
            raise NativeRunStopped('cancelled')
        remaining = self.profile.max_run_seconds - (time.monotonic() - self.started)
        if remaining <= 0:
            raise NativeRunStopped('budget-exhausted')
        return remaining

    def job(self, request):
        timeout = min(self.profile.job_timeout_seconds, self.remaining())
        index = len(self.report['jobs'])
        operation = {'job_id': f'job-{index:04d}', 'job_hash': content_hash(request),
                     'operation': request['operation'], 'status': 'requested'}
        self.report['jobs'].append(operation)
        self.save()  # Durable intent exists before any worker starts.
        try:
            result = run_native_job(request, output_dir=self.folder / operation['job_id'],
                                    timeout_seconds=timeout, cancelled=self.cancelled)
            self.remaining()
            operation['status'] = 'completed'
            return result
        except BaseException as error:
            operation.update(status='failed', error_type=type(error).__name__)
            if isinstance(error, NativeWorkerError):
                self.remaining()  # Classify cancellation/global deadline before a job failure.
            raise
        finally:
            self.save()

    def prepare(self, name, recipe):
        destination = self.folder / 'artifacts' / name
        result = self.job({'operation': 'prepare', 'backend': 'mlx',
                          'source': self.profile.source.model_dump(), 'destination': str(destination),
                          'recipe': recipe.model_dump()})
        manifest = verify_artifact(destination, expected_id=result['artifact']['artifact_id'], backend='mlx')
        if manifest['source'] != self.profile.source.model_dump() or manifest['recipe'] != recipe.model_dump():
            raise ValueError('Prepared artifact does not match the frozen recipe and source')
        self.artifacts[name] = {'path': str(destination), 'artifact_id': manifest['artifact_id']}
        self.report.setdefault('artifacts', {})[name] = result
        self.save()

    def measure(self, name, trial_id):
        artifact = self.artifacts[name]
        request = self.profile.measure_job(artifact['path'], artifact['artifact_id'])
        raw = self.job(request)
        controls = {key: request[key] for key in ('seed', 'max_tokens', 'warmup', 'repetitions',
                                                 'response_formats', 'response_format_version')}
        controls.update(sampling='greedy', concurrency=1)
        expected = {content_hash(task.prompt): task.expected_json for task in self.profile.tasks}
        result = native_trial(raw, prompts=request['prompts'],
            evaluator=lambda prompt, text: _score(text, expected[content_hash(prompt)]),
            evaluation_version=self.profile.evaluation_version, floor=self.profile.constraints.quality_floor,
            artifact_id=artifact['artifact_id'], controls=controls, trial_id=trial_id)
        result['recipe_id'] = name
        return result

    def decision(self, reference, candidate):
        candidate = deepcopy(candidate)
        a, b = reference['runtime'], candidate['runtime']
        if (not a.get('device') or not a.get('versions') or a['device'] != b.get('device')
                or a['versions'] != b.get('versions')):
            candidate['status'] = 'incompatible-measurement'
        return select_candidate(reference, candidate, objective=self.profile.objective,
                                constraints=self.profile.constraints)

    def select(self, name):
        artifact = self.artifacts[name]
        verify_artifact(artifact['path'], expected_id=artifact['artifact_id'], backend='mlx')
        self.report.update(selected_recipe_id=name, selected_artifact_id=artifact['artifact_id'],
                           artifact_path=artifact['path'])
        self.save()

    def evidence(self, available):
        def metrics(trial):
            return {'trial_id': trial['trial_id'], 'recipe_id': trial.get('recipe_id'),
                    'status': trial['status'], 'quality': trial.get('task_quality'),
                    'memory': trial.get('runtime', {}).get('memory'), 'performance': trial.get('reduced')}
        return {'objective': self.report['objective'], 'constraints': self.report['constraints'],
                'available_recipes': [{'recipe_id': key, 'recipe': self.profile.recipes[key].model_dump()}
                                      for key in available],
                'trials': [metrics(self.report['baseline'])] +
                          [metrics(t['measurement']) if 'measurement' in t else
                           {'trial_id': t['recipe_id'], 'status': t['status']} for t in self.report['trials']],
                'remaining_trials': self.profile.budget.max_candidate_trials - self.report['candidate_trials_used']}

    def run(self):
        try:
            self.prepare('baseline', MLXRecipe())
            baseline = self.measure('baseline', 'baseline')
            self.report['baseline'] = baseline
            if constraint_failures(baseline, self.profile.constraints) or objective_value(baseline, 'memory') is None:
                self.report['status'] = 'baseline-failed'
                return self.report
            self.select('baseline')
            best = baseline
            controls = [baseline]
            available = list(self.profile.recipes)
            while available and self.report['candidate_trials_used'] < self.profile.budget.max_candidate_trials:
                remaining = min(180, self.remaining())
                self.report['pending_agent_call'] = len(self.agent.history)
                self.save()
                try:
                    proposal = self.agent.propose(self.evidence(available), timeout_seconds=remaining,
                                                   cancelled=self.cancelled)
                finally:
                    self.report['agent_calls'] = self.agent.history
                    self.report.pop('pending_agent_call', None)
                    self.save()
                self.remaining()
                if proposal is None or proposal.recipe_id not in available + ['stop']:
                    self.report['status'] = 'agent-failed'
                    return self.report
                if proposal.recipe_id == 'stop':
                    break
                name = proposal.recipe_id
                available.remove(name)
                self.report['candidate_trials_used'] += 1
                trial = {'recipe_id': name, 'proposal': proposal.model_dump(), 'status': 'running'}
                self.report['trials'].append(trial)
                self.save()
                try:
                    self.prepare(name, self.profile.recipes[name])
                    measured = self.measure(name, name)
                    trial.update(measurement=measured, status='measured', decision=self.decision(best, measured))
                    if trial['decision']['selected'] != 'candidate':
                        continue
                    control = self.measure('baseline', f'{name}-control')
                    confirmation = self.measure(name, f'{name}-confirmation')
                    confirmed = self.decision(control, confirmation)
                    trial['confirmation'] = {'baseline': control, 'candidate': confirmation, 'decision': confirmed}
                    if constraint_failures(control, self.profile.constraints) or confirmed['selected'] != 'candidate':
                        continue
                    controls.append(control)
                    worst_candidate = max([measured, confirmation], key=lambda t: objective_value(t, 'memory'))
                    best_control = min(controls, key=lambda t: objective_value(t, 'memory'))
                    trial['repeated_decision'] = self.decision(best_control, worst_candidate)
                    if (trial['repeated_decision']['selected'] == 'candidate'
                            and self.decision(best, worst_candidate)['selected'] == 'candidate'):
                        best = min([measured, confirmation], key=lambda t: objective_value(t, 'memory'))
                        self.select(name)
                except (NativeWorkerError, ValueError, OSError) as error:
                    trial.update(status='failed', error_type=type(error).__name__)
                finally:
                    self.save()
            self.report['status'] = 'awaiting-trace'
        except NativeRunStopped as error:
            self.report['status'] = str(error)
        except BaseException as error:
            self.report.update(status='failed', error_type=type(error).__name__)
            raise
        finally:
            self.save()
        return self.report


def optimize_native(*, profile, output_dir, project, agent=None, cancelled=None):
    """Run the operator's fixed profile. This function never changes its gates."""
    profile = NativeProfile.model_validate(profile)
    encode_record(profile.model_dump())
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(folder)
    research = None
    try:
        research = _Research(profile, folder, ledger, agent or NativeRecipeAgent(project=project), cancelled)
        verified = trace_native_job(project=project, run=research.run)
        research.report['trace'] = verified['trace']
        if research.report['status'] == 'awaiting-trace':
            research.report['status'] = 'completed'
        research.save()
        return research.report
    except BaseException:
        if research is not None:
            research.report['status'] = 'failed'
            research.save()
        raise
    finally:
        ledger.close()
