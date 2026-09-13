"""Small recording helpers. Importing this module does not use keys or compute."""

from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import time
import uuid

from pydantic import SecretStr

import sera
from sera.config import LARGE_MODEL_ID, LARGE_MODEL_REVISION
from sera.storage import save_json


class ExampleRun:
    """One user, one notebook kernel. No credentials are inherited implicitly."""

    def __init__(self, output_root='sera-runs/example'):
        self.output_root = Path(output_root)
        self.project = None
        self._weave_key = None
        self.agent = None
        self.certificate = None
        self.weave_checked = False
        self.result = None
        self.model_id = LARGE_MODEL_ID
        self.reference = sera.RuntimeConfig(quantization='fp8_per_tensor')

    def status(self):
        return dict(weave_configured=self._weave_key is not None,
                    agent_configured=self.agent is not None,
                    provider_verified=self.certificate is not None)

    def configure_weave(self, key, *, project):
        if not isinstance(key, str) or not key.strip() or not project or '/' not in project:
            raise ValueError('Supply a nonempty W&B key and entity/project')
        if self.result is not None:
            raise ValueError('Close the returned runner before changing credentials')
        self._weave_key = SecretStr(key.strip())
        self.project = project.strip()
        self.agent = self.certificate = None
        self.weave_checked = False

    def configure_agent(self, *, provider, model, base_url=None, api_key=None, relay_dir=None):
        self._require_weave()
        if not model or not model.strip():
            raise ValueError('Choose an explicit investigator model')
        if self.result is not None:
            raise ValueError('Close the returned runner before changing providers')
        if provider == 'wandb':
            if any(value is not None for value in (base_url, api_key, relay_dir)):
                raise ValueError('W&B uses the configured W&B key, not custom endpoint fields')
            agent = sera.WandbAgent(project=self.project, model=model)
        elif provider == 'openai-compatible':
            if not api_key or not base_url or relay_dir is not None:
                raise ValueError('Supply an approved endpoint and its key')
            agent = sera.OpenAICompatibleAgent(project=self.project, model=model,
                                               base_url=base_url, api_key=api_key)
        elif provider == 'codex-relay':
            if not relay_dir or base_url is not None or api_key is not None:
                raise ValueError('Codex needs a relay directory and a running external controller')
            from sera.relay import RelayAgent
            agent = RelayAgent(project=self.project, model=model, relay_dir=relay_dir)
        else:
            raise ValueError('Choose wandb, openai-compatible, or codex-relay')
        self.agent, self.certificate = agent, None

    def _require_weave(self):
        if self._weave_key is None:
            raise ValueError('Configure Weave explicitly; ambient keys are not used')

    @contextmanager
    def _credentials(self):
        self._require_weave()
        previous = os.environ.get('WANDB_API_KEY')
        os.environ['WANDB_API_KEY'] = self._weave_key.get_secret_value()
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop('WANDB_API_KEY', None)
            else:
                os.environ['WANDB_API_KEY'] = previous

    def gpu(self):
        from sera.runtime import gpu_snapshot
        import subprocess
        try:
            snapshot = gpu_snapshot()
        except (OSError, ValueError, subprocess.SubprocessError):
            return dict(available=False, message='Change runtime to GPU')
        return dict(available=True, **snapshot,
                    message='GPU detected; runtime compatibility is checked before execution')

    def check_weave(self):
        self._require_weave()
        with self._credentials():
            import weave
            try:
                client = weave.init(self.project)
                @weave.op(name='sera_example_connection_check')
                def connection_check():
                    return {'service': 'weave', 'purpose': 'connection check; no GPU work'}
                connection_check()
                client.flush()
            except Exception as error:
                raise RuntimeError(f'Weave check failed: {type(error).__name__}') from None
        self.weave_checked = True
        return {'weave_checked': True, 'project': self.project, 'gpu_trials': 0}

    def _folder(self, label):
        return self.output_root / f'{label}-{uuid.uuid4().hex[:12]}'

    def check_agent(self):
        self._require_weave()
        if self.agent is None:
            raise ValueError('Configure an investigator provider first')
        from sera.provider_check import check_provider, require_provider_check
        folder = self._folder('provider')
        fresh = self.agent.fork()
        with self._credentials():
            report = check_provider(project=self.project, model=fresh.model,
                                    agent=fresh, output_dir=folder, stop_on_failure=True)
        if not report['passed']:
            raise RuntimeError(f'Provider check failed; inspect {folder / "result.json"}')
        certificate = folder / 'result.json'
        require_provider_check(certificate, self.agent)
        self.certificate = certificate
        return dict(provider=fresh.provider, model=fresh.model,
                    first_pass_valid=report['first_pass_valid'],
                    requests=report['completed_requests'], certificate=str(certificate), gpu_trials=0)

    def _ready(self):
        self._require_weave()
        if self.agent is None:
            raise ValueError('Configure an investigator provider first')
        if self.certificate is None:
            raise ValueError('Run the provider check before GPU work')
        if not self.weave_checked:
            raise ValueError('Run the Weave check before GPU work')
        gpu = self.gpu()
        if not gpu['available']:
            raise RuntimeError('Change runtime to GPU')
        if gpu['used_mib'] != 0:
            raise RuntimeError('GPU is in use. Close the owning run before continuing')
        from sera.provider_check import require_provider_check
        require_provider_check(self.certificate, self.agent)

    @staticmethod
    def _tasks():
        from benchmarks.grade import SYSTEM_PROMPT, grade_case, load_cases
        cases = load_cases(Path(__file__).resolve().parents[1]/'benchmarks'/'easy_cases.json')
        prompts = [[{'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': case['prompt']}] for case in cases]
        by_prompt = {case['prompt']: case for case in cases}
        def evaluate(prompt, output):
            return grade_case(by_prompt[prompt[-1]['content']], output)['passed']
        return prompts, evaluate

    def baseline(self):
        """Measure and close the preview baseline; the swarm remeasures its own baseline."""
        self._ready()
        from sera.measurement import collect_trial
        from sera.quality import evaluate_quality
        prompts, evaluate = self._tasks()
        folder = self._folder('baseline')
        folder.mkdir(parents=True)
        runner = sera.SeraModel(model_id=self.model_id, revision=LARGE_MODEL_REVISION,
                                configuration=self.reference, artifact_dir=folder)
        trial = None
        try:
            runner.start()
            trial = collect_trial(runner, prompts, 'baseline', baseline=True,
                                  workload=sera.Workload(concurrency=[1, 2, 4, 8]))
            trial['task_quality'] = evaluate_quality(trial, prompts, evaluate,
                version='sera-easy-strict-json-v1', floor=.99)
        finally:
            runner.close()
            if trial is not None:
                save_json(folder/'result.json', trial)
        if not trial['task_quality']['passed']:
            raise RuntimeError(f'Baseline quality failed; inspect {folder / "result.json"}')
        return self._metrics(trial) | {'record': str(folder/'result.json'), 'runner_closed': True}

    def optimize(self):
        self._ready()
        prompts, evaluate = self._tasks()
        started = time.monotonic()
        with self._credentials():
            self.result = sera.optimize(models=[self.model_id], prompts=prompts, mode='swarm',
                agent=self.agent.fork(), provider_check=self.certificate,
                baseline_configuration=self.reference,
                evaluation=evaluate, evaluation_version='sera-easy-strict-json-v1',
                constraints=sera.Constraints(quality_floor=.99),
                objective=sera.Objective(priority='latency', min_improvement_fraction=.05),
                workload=sera.Workload(concurrency=[1, 2, 4, 8]),
                output_dir=self._folder('swarm'))
        self.result.report['example_elapsed_seconds'] = time.monotonic() - started
        self.result._save()
        return self.result

    @staticmethod
    def _metrics(trial):
        reduced, runtime = trial.get('reduced', {}), trial.get('runtime', {})
        return dict(p95_ms=reduced.get('p95_latency_ms'),
            output_tokens_per_second=reduced.get('output_tokens_per_second'),
            sampled_peak_gpu_mib=runtime.get('sampled_peak_memory_mib'),
            startup_seconds=runtime.get('startup_seconds'),
            task_quality=trial.get('task_quality', {}).get('mean'),
            quality_pass=trial.get('task_quality', {}).get('passed'))

    def compare(self, result):
        report = result.report
        baseline = report.get('baseline', {})
        selected_id = report.get('decision', {}).get('selected')
        selected = next((trial for trial in [baseline, *report.get('search_trials', [])]
                         if trial.get('trial_id') == selected_id), None) if selected_id else None
        before = self._metrics(baseline)
        after = self._metrics(selected) if selected else None
        improvement = None
        if after and before['p95_ms'] and after['p95_ms'] is not None:
            improvement = 100 * (1 - after['p95_ms'] / before['p95_ms'])
        return dict(baseline=before, selected=selected_id, returned=after,
                    p95_improvement_pct=improvement, weave_url=report.get('weave_url'),
                    search=deepcopy(report.get('search', {}).get('stop_reason')))

    def close(self):
        if self.result is not None:
            self.result.close()
            self.result = None
        return self.gpu()

    def clear_credentials(self):
        if self.result is not None:
            raise ValueError('Close the returned runner first')
        self._weave_key = self.agent = self.certificate = self.project = None
        self.weave_checked = False
        return self.status()
