"""Ordered, measured stages with frozen checkpoints and one live owner at a time."""

import inspect
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from .config import LARGE_MODEL_ID, MODEL_ID, Constraints, Objective, RuntimeConfig, Workload
from .measurement import constraint_failures, objective_value
from .stage_config import inherited_constraints, validate_stage_options
from .storage import content_hash, save_json


@dataclass
class StagedResult:
    report: dict
    output_dir: Path
    _current: object = field(default=None, repr=False)

    @property
    def models(self):
        return self._current.models if self._current is not None else []

    @property
    def checkpoints(self):
        return deepcopy(self.report['checkpoints'])

    @property
    def weave_url(self):
        return self._current.weave_url if self._current is not None else None

    @property
    def recommended(self):
        return self.report['status']

    def _save(self):
        save_json(self.output_dir / 'result.json', self.report)
        rows = ['# Sera ordered stages', '', f"Status: {self.report['status']}",
                f"Allowed regression in earlier objectives: {self.report['k_percent']}%",
                f"Minimum improvement per stage: {self.report['min_improvement_percent']}% (strictly positive)", '',
                'Each stage remeasures its starting configuration. Quality and inherited limits remain hard gates.', '']
        for stage in self.report['stages']:
            rows.append(f"Stage {stage['index']}: {stage['stage']}; {stage['status']}; "
                        f"record: {stage['output_dir']}/result.json")
            if stage.get('weave_url'):
                rows.append(f"Weave: {stage['weave_url']}")
        rows += ['', 'Checkpoints are measured configurations, not saved model weights or proof of a global optimum.',
                 'Quantization stages search supported precision controls only; no new weight format is enabled.',
                 'Whole-sequence outage resume is not implemented. Each stage retains its own run records.', '']
        (self.output_dir / 'report.md').write_text('\n'.join(rows))

    def print_summary(self):
        print((self.output_dir / 'report.md').read_text())

    def close(self):
        try:
            if self._current is not None:
                self._current.close()
            self.report.update(status='closed', returned_runner_closed=True)
        except BaseException as error:
            self.report.update(status='cleanup-failed', cleanup_error=type(error).__name__,
                               returned_runner_closed=False)
            raise
        finally:
            self._save()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _validate_call(models, prompts, mode, options):
    from . import pipeline
    inspect.signature(pipeline.optimize).bind(models=models, prompts=prompts, **options)
    if mode not in ('auto', 'swarm'):
        raise ValueError('Ordered stages require the swarm, not fixed mode')
    if models not in ([MODEL_ID], [LARGE_MODEL_ID]):
        raise ValueError('Ordered stages require one supported pinned Qwen model')
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 32 or any(
            not isinstance(prompt, (str, list)) or not prompt for prompt in prompts):
        raise ValueError('Supply 1 to 32 nonempty prompts')
    if not callable(options.get('evaluation')) or not isinstance(options.get('evaluation_version'), str) or not options['evaluation_version'].strip():
        raise ValueError('Ordered stages require a versioned task evaluation')
    if options.get('constraints') is None:
        raise ValueError('Ordered stages require explicit quality constraints')
    constraints = Constraints.model_validate(options['constraints'])
    forbidden = ('candidate', 'objective', 'investigation_space', 'investigation_controls',
                 'trace_reader', '_runtime_factory')
    if any(options.get(name) is not None for name in forbidden):
        raise ValueError('Ordered stages own objectives, automatic search, filters, and per-stage trace readers')
    if options.get('automatic_space', True) is not True or options.get('swarm', True) is not True:
        raise ValueError('Ordered stages require automatic swarm search')
    # Resolve the whole workload before allocating an output directory or starting a provider.
    workload = Workload.model_validate(options.get('workload') or Workload(concurrency=[1, 2, 4, 8]))
    return constraints, workload


def _checkpoint(current, row, constraints, previous, models):
    selected = current.report['decision'].get('selected')
    matches = [trial for trial in current.trials if trial['trial_id'] == selected]
    if len(matches) != 1 or len(current.models) != 1:
        raise RuntimeError('Stage returned no unique measured winner')
    trial = deepcopy(matches[0])
    if current.report.get('task_quality_verified') is not True or constraint_failures(trial, constraints):
        raise RuntimeError('Stage winner violates verified constraints')
    if trial.get('reduced', {}).get('generation_errors', 0) != 0:
        raise RuntimeError('Stage winner has generation errors')
    config = RuntimeConfig.model_validate(trial['runtime']['configuration'])
    if config.config_hash != trial['config_hash'] or current.models[0].configuration != config:
        raise RuntimeError('Stage runner differs from its measured configuration')
    runtime = trial['runtime']
    if type(runtime.get('telemetry_errors')) is not int or runtime['telemetry_errors'] != 0:
        raise RuntimeError('Stage memory telemetry is incomplete or failed')
    if runtime.get('model_id') != models[0]:
        raise RuntimeError('Stage model identity changed')
    tokens = trial.get('input_token_ids')
    if not isinstance(tokens, list) or not tokens or any(not row for row in tokens):
        raise RuntimeError('Stage input token evidence is missing')
    identity = {'model_id': runtime['model_id'], 'revision': runtime.get('revision'),
                    'gpu_uuid': runtime.get('gpu', {}).get('uuid'), 'versions': runtime.get('versions')}
    if not all(identity.values()):
        raise RuntimeError('Stage runtime identity is incomplete')
    if previous and (identity != previous[0]['runtime_identity'] or
                     content_hash(tokens) != previous[0]['input_token_ids_hash']):
        raise RuntimeError('Stage workload or runtime identity changed')
    latency, memory = objective_value(trial, 'latency'), objective_value(trial, 'memory')
    if latency is None or type(memory) is not int or memory <= 0:
        raise RuntimeError('Stage winner is missing measured latency or memory')
    throughput = objective_value(trial, 'throughput')
    if row['stage'] == 'throughput' and throughput is None:
        raise RuntimeError('Stage winner is missing positive finite measured throughput')
    record = {'stage': row['stage'], 'status': 'completed', 'index': row['index'],
        'configuration': config.model_dump(), 'config_hash': config.config_hash,
        'p95_latency_ms': latency, 'sampled_peak_memory_mib': memory,
        'output_tokens_per_second': throughput,
        'source_trial_id': selected, 'source_trial_hash': content_hash(trial),
        'source_trial_snapshot_path': f"checkpoints/{row['index']:03d}-trial.json",
        'input_token_ids_hash': content_hash(tokens), 'runtime_identity': identity,
        'output_dir': str(current.output_dir), 'weave_url': current.weave_url,
        'constraints': constraints.model_dump()}
    record['checkpoint_hash'] = content_hash(record)
    return record, trial


def run_stages(*, models, prompts, stages, k, min_improvement_pct, mode, options, run_stage):
    plan = validate_stage_options(stages, k, min_improvement_pct)
    original, workload = _validate_call(models, prompts, mode, options)
    options = dict(options)
    folder = Path(options.pop('output_dir', None) or Path('sera-runs') / uuid.uuid4().hex).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    result = StagedResult({'schema_version': 'sera-ordered-stages-v1', 'status': 'running',
        'requested_stages': list(plan.stages), 'k_percent': plan.regression_fraction * 100,
        'min_improvement_percent': plan.min_improvement_fraction * 100, 'original_constraints': original.model_dump(),
        'prompts': deepcopy(prompts), 'workload': workload.model_dump(),
        'checkpoints': [], 'stages': [], 'returned_runner_closed': True}, folder)
    options.update(workload=workload, automatic_space=True, swarm=True)
    baseline = options.pop('baseline_configuration', None)
    if baseline is not None:
        baseline = RuntimeConfig.model_validate(
            baseline.model_dump() if isinstance(baseline, RuntimeConfig) else baseline)
    try:
        (folder / 'checkpoints').mkdir()
        result._save()
        for index, stage in enumerate(plan.stages, 1):
            limits = inherited_constraints(original, result.report['checkpoints'], k)
            if result._current is not None:
                # Do not start another server if release of the prior owner fails.
                result._current.close()
                result._current = None
                result.report['returned_runner_closed'] = True
            stage_folder = folder / f'{index:03d}-{stage}'
            row = {'index': index, 'stage': stage, 'status': 'running', 'output_dir': str(stage_folder),
                       'constraints': limits.model_dump()}
            result.report['stages'].append(row)
            result._save()
            arguments = dict(options, models=deepcopy(models), prompts=deepcopy(prompts),
                mode='swarm', output_dir=stage_folder, constraints=limits,
                objective=Objective(priority='memory' if stage == 'quantization' else stage,
                                    min_improvement_fraction=plan.min_improvement_fraction))
            if baseline is not None:
                arguments['baseline_configuration'] = baseline
            if stage == 'quantization':
                arguments['investigation_controls'] = ['kv_cache_dtype']
            current = run_stage(**arguments)
            result._current = current
            result.report['returned_runner_closed'] = not bool(current.models)
            row.update(status=current.report['status'], weave_url=current.weave_url,
                       decision=deepcopy(current.report.get('decision')))
            if not current.models:
                result.report.update(status='no-safe-configuration', stopped_at_stage=index)
                result._save()
                return result
            if baseline is not None and current.report.get('baseline_configuration') != baseline.model_dump():
                raise RuntimeError('Stage did not start from the saved configuration')
            checkpoint, source = _checkpoint(current, row, limits, result.report['checkpoints'], models)
            save_json(folder / checkpoint['source_trial_snapshot_path'], source)
            save_json(folder / 'checkpoints' / f'{index:03d}.json', checkpoint)
            result.report['checkpoints'].append(checkpoint)
            row.update(status='completed', checkpoint_hash=checkpoint['checkpoint_hash'])
            baseline = RuntimeConfig.model_validate(checkpoint['configuration'])
            result._save()
        result.report['status'] = 'ready'
        result._save()
        return result
    except BaseException as error:
        result.report.update(status='failed', error_type=type(error).__name__)
        if result.report['stages'] and result.report['stages'][-1]['status'] != 'completed':
            result.report['stages'][-1]['status'] = 'failed'
        try:
            if result._current is not None:
                result._current.close()
            result.report['returned_runner_closed'] = True
        except BaseException as cleanup_error:  # noqa: BLE001 -- cleanup must also handle interruption
            result.report.update(cleanup_error=type(cleanup_error).__name__, returned_runner_closed=False)
            error.add_note('Stage cleanup failed: ' + type(cleanup_error).__name__)
        finally:
            result._save()
        raise
