"""Explicit two-model placement: isolated gates, synchronized trial, owned pair.

This executor does not select allocations or replace the single-model swarm.
Inputs freeze the plan and task requirements before any model starts.
"""

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, field
from pathlib import Path
import threading

from pydantic import BaseModel, ConfigDict, Field

from .config import Workload
from .measurement import collect_trial
from .placement_config import validate_placement_plan
from .placement_runtime import SharedGPUOwner
from .quality import evaluate_quality
from .runtime import CleanupError, GENERATION, SeraModel
from .storage import content_hash, save_json
from .tracing import emit_event, TraceSinkError


class PlacementMemoryEstimate(BaseModel):
    """Caller-supplied byte estimates, not measured memory or a fit guarantee."""

    model_config = ConfigDict(strict=True, frozen=True, extra='forbid')
    weights_bytes: int = Field(ge=0)
    kv_bytes: int = Field(ge=0)
    workspace_bytes: int = Field(ge=0)
    process_overhead_bytes: int = Field(ge=0)
    fragmentation_bytes: int = Field(ge=0)

    @property
    def total_bytes(self):
        return sum(self.model_dump().values())


@dataclass(frozen=True)
class PlacementWorkload:
    prompts: list
    evaluator: object
    evaluator_version: str
    workload: Workload = field(default_factory=Workload)
    response_formats: list[dict] | None = None
    response_format_version: str | None = None

    def validated(self):
        from copy import deepcopy
        if not isinstance(self.prompts, list) or not self.prompts:
            raise ValueError('Each model requires nonempty prompts')
        if not callable(self.evaluator) or not isinstance(self.evaluator_version, str) or not self.evaluator_version.strip():
            raise ValueError('Each model requires a versioned absolute task evaluator')
        for prompt in self.prompts:
            messages = [{'role': 'user', 'content': prompt}] if isinstance(prompt, str) else prompt
            if (not isinstance(messages, list) or not messages or any(
                    not isinstance(message, dict) or set(message) != {'role', 'content'} or
                    message['role'] not in {'user', 'assistant', 'system'} or
                    not isinstance(message['content'], str) or not message['content'].strip()
                    for message in messages)):
                raise ValueError('Prompts must contain nonempty text chat messages')
        from .placement_decoding import validate_formats
        formats = validate_formats(self.prompts, self.response_formats, self.response_format_version)
        return PlacementWorkload(deepcopy(self.prompts), self.evaluator, self.evaluator_version,
                                 Workload.model_validate(self.workload.model_dump()), formats,
                                 self.response_format_version)

    def manifest(self):
        value = dict(prompts=self.prompts, evaluator_version=self.evaluator_version,
                     workload=self.workload.model_dump(), generation=GENERATION)
        if self.response_formats is not None:
            value.update(response_formats=self.response_formats, response_format_version=self.response_format_version)
        return value


def _gate(trial, profile, service, *, isolated_p95_ms=None, joint=False):
    quality = evaluate_quality(trial, profile.prompts, profile.evaluator,
        version=profile.evaluator_version, floor=service.constraints.quality_floor)
    trial['task_quality'] = quality
    # Also score timed outputs: correct serial answers cannot hide wrong loaded answers.
    requests = trial.get('requests', [])
    measured_prompts = [profile.prompts[item['prompt_index']] for item in requests]
    measured = dict(quality=[dict(item, prompt_index=index) for index, item in enumerate(requests)])
    measured_quality = evaluate_quality(measured, measured_prompts, profile.evaluator,
        version=profile.evaluator_version, floor=service.constraints.quality_floor)
    trial['measured_task_quality'] = measured_quality
    p95 = trial.get('reduced', {}).get('p95_latency_ms')
    import math
    limit = service.constraints.p95_latency_ms
    slowdown = service.constraints.max_p95_slowdown_fraction
    reference_valid = type(isolated_p95_ms) in (int, float) and math.isfinite(isolated_p95_ms) and isolated_p95_ms > 0
    if joint and slowdown is not None and reference_valid:
        relative_limit = isolated_p95_ms * (1 + slowdown)
        limit = relative_limit if limit is None else min(limit, relative_limit)
    latency_pass = (type(p95) in (int, float) and math.isfinite(p95) and p95 > 0
                    and (limit is None or p95 <= limit)
                    and not (joint and slowdown is not None and not reference_valid))
    errors_pass = type(trial.get('generation_errors')) is int and trial['generation_errors'] == 0
    passed = trial.get('status') == 'collected' and quality['passed'] and measured_quality['passed'] and latency_pass and errors_pass
    return dict(passed=bool(passed), quality_pass=quality['passed'],
                measured_quality_pass=measured_quality['passed'], latency_pass=bool(latency_pass),
                errors_pass=errors_pass, p95_latency_ms=p95, latency_limit_ms=limit,
                latency_limit_source='matching-isolated-reference' if joint and slowdown is not None else 'absolute-or-reference-measurement',
                isolated_p95_ms=isolated_p95_ms, max_p95_slowdown_fraction=slowdown)


def collect_joint(models, profiles, *, trial_id='joint'):
    """Synchronize each measured load and quality phase; retain unequal windows."""
    barrier = threading.Barrier(2, timeout=300)

    def collect(model):
        profile = profiles[model.model_id]
        def phase_hook(phase, concurrency):
            barrier.wait()
        try:
            trial = collect_trial(model, profile.prompts, trial_id, workload=profile.workload,
                                  phase_hook=phase_hook)
            if trial['status'] not in {'collected', 'request-errors'}:
                barrier.abort()
            return trial
        except BaseException:
            barrier.abort()
            raise

    with ThreadPoolExecutor(max_workers=2) as executor:
        # Preserve the caller's Weave root and event sink in both service threads.
        futures = {model.model_id: executor.submit(copy_context().run, collect, model) for model in models}
        trials = {model_id: future.result() for model_id, future in futures.items()}
    values = list(trials.values())
    overlap = []
    for first, second in zip(values[0].get('loads', []), values[1].get('loads', [])):
        a, b = first.get('measurement_window'), second.get('measurement_window')
        if not a or not b:
            continue
        duration = max(a['ended'], b['ended']) - min(a['started'], b['started'])
        seconds = max(0, min(a['ended'], b['ended']) - max(a['started'], b['started']))
        overlap.append(dict(concurrency=first['concurrency'], overlap_seconds=seconds,
                            coverage_fraction=seconds/duration if duration > 0 else 0,
                            windows={models[0].model_id:a, models[1].model_id:b}))
    return dict(trials=trials, overlap=overlap)


@dataclass
class PlacementResult:
    models: list
    report: dict
    output_dir: Path
    owner: object = None
    _trace_on_close: object = field(default=None, repr=False)

    def _event(self, name, payload):
        try:
            emit_event(name, payload)
        except TraceSinkError as error:
            self.report.setdefault('trace_export_failures', []).append(
                dict(event=error.event_name, error_type=error.error_type))
            self.report['trace_status'] = 'failed'

    def _save(self):
        self.report['returned_runtimes'] = [model.record for model in self.models]
        if self.owner is not None:
            self.report['shared_runtime'] = self.owner.record
        save_json(self.output_dir/'result.json', self.report)
        decision = self.report['decision']
        lines = ['# Sera two-model placement', '', f"Status: {self.report['status']}",
                 f"Outcome: {decision['outcome']}", f"Reason: {decision['reason']}", '',
                 'Memory budget constrained to represent a smaller card; execution uses the measured physical GPU.',
                 'This represents memory capacity, not another card\'s speed or bandwidth.',
                 f"Physical bytes: {self.report['plan']['physical_gpu_bytes']}",
                 f"Declared bytes: {self.report['plan']['declared_budget_bytes']}",
                 'Memory peaks are sampled, not continuous allocation enforcement.',
                 'This executor tests one explicit plan; see the search report for agent selection. No global-optimality claim.',
                 'No quantization-enabled placement claim without an unchanged-budget unquantized comparison.']
        if self.report.get('weave_url'):
            lines.extend(['', f"Weave trace: {self.report['weave_url']}",
                          f"Trace export: {self.report.get('trace_status', 'unavailable')}"])
        for service in self.report['plan']['services']:
            peak = self.report.get('shared_runtime', {}).get('service_peak_memory_mib', {}).get(service['model_id'])
            lines.append(f"{service['model_id']}: allocation={service['allocation_bytes']} bytes; "
                         f"memory fraction={service['configuration']['gpu_memory_utilization']}; "
                         f"sampled service peak={peak if peak is not None else 'unavailable'} MiB")
        peak = self.report.get('shared_runtime', {}).get('sampled_peak_memory_mib')
        lines.append(f"Sampled device peak: {peak if peak is not None else 'unavailable'} MiB")
        for model_id, gate in self.report.get('joint', {}).get('gates', {}).items():
            lines.append(f"{model_id}: passed={gate['passed']}; p95={gate['p95_latency_ms']} ms")
        (self.output_dir/'report.md').write_text('\n'.join(lines)+'\n')

    def close(self):
        try:
            if self.owner is not None:
                self.owner.close()
            self.report.update(returned_runner_closed=True, status='closed')
        except BaseException as error:
            self.report.update(returned_runner_closed=False, status='cleanup-failed',
                decision=dict(outcome='no-safe-placement', reason='cleanup-failed'),
                cleanup_error=type(error).__name__)
            raise
        finally:
            if self._trace_on_close is not None:
                self._trace_on_close(self)
            self._save()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def place(*, plan, workloads, memory_estimates, output_dir, weave_project=None, isolated_reference=None,
          trial_namespace=None):
    """Measure one caller-selected pair. Never silently return only one model.

    Failed quality returns an empty result with evidence. Cleanup errors raise and
    remain saved. The caller owns both successful runners and must close them.
    """
    arguments = dict(plan=plan, workloads=workloads, memory_estimates=memory_estimates,
                     output_dir=output_dir, _isolated_reference=isolated_reference, _trial_namespace=trial_namespace)
    return _run_placement(arguments, weave_project)


def measure_placement_references(*, plan, workloads, memory_estimates, output_dir, weave_project=None):
    """Measure and close both isolated services; never start a joint pair."""
    return _run_placement(dict(plan=plan, workloads=workloads, memory_estimates=memory_estimates,
        output_dir=output_dir, _references_only=True), weave_project)


def _run_placement(arguments, weave_project):
    if weave_project is None:
        return _place(**arguments)
    if not isinstance(weave_project, str) or not weave_project.strip():
        raise ValueError('weave_project must be an explicit nonempty project name')
    from .placement_tracing import run_traced_placement
    return run_traced_placement(_place, arguments, weave_project)


def _place(*, plan, workloads, memory_estimates, output_dir, _result_observer=None,
           _references_only=False, _isolated_reference=None, _trial_namespace=None):
    import re
    from .placement_decoding import runner_for_profile
    if _trial_namespace is not None and (not isinstance(_trial_namespace, str)
            or re.fullmatch(r'[A-Za-z0-9_-]{1,64}', _trial_namespace) is None):
        raise ValueError('trial_namespace must be a short stable identifier')
    plan = validate_placement_plan(plan)
    model_ids = {service.model_id for service in plan.services}
    if set(workloads) != model_ids or set(memory_estimates) != model_ids:
        raise ValueError('Supply exactly the approved pair\'s workloads and memory estimates')
    profiles = {model: profile.validated() for model, profile in workloads.items()}
    estimates = {model: PlacementMemoryEstimate.model_validate(
        value.model_dump() if isinstance(value, PlacementMemoryEstimate) else value)
        for model, value in memory_estimates.items()}
    if len({tuple(profile.workload.concurrency) for profile in profiles.values()}) != 1:
        raise ValueError('Both services require the same declared load levels for synchronization')
    for service in plan.services:
        if max(profiles[service.model_id].workload.concurrency) > service.configuration.max_num_seqs:
            raise ValueError('Workload concurrency exceeds a service sequence limit')
    bound = None
    if _isolated_reference is not None:
        from .placement_reference import bind_placement_reference
        bound = bind_placement_reference(_isolated_reference, plan, profiles)
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {model: profile.manifest() for model, profile in profiles.items()}
    report = dict(schema_version='sera-placement-v1', status='running', plan=plan.model_dump(),
        plan_hash=plan.plan_hash, workloads=manifest, workload_hash=content_hash(manifest),
        memory_estimates={model:value.model_dump() for model,value in estimates.items()},
        memory_estimate_scope='caller-supplied estimates; not a measured fit guarantee',
        isolated={}, isolated_gates={}, isolated_runtimes=[], decision=dict(outcome='not-attempted', reason='pending'),
        quantization_enabled_placement=False, returned_runner_closed=True)
    result = PlacementResult([], report, folder)
    if bound is not None:
        report.update(isolated=bound['isolated'], isolated_gates=bound['gates'],
                      isolated_reference=bound['provenance'],
                      isolated_runtimes=[trial['runtime'] for trial in bound['isolated'].values()])
    if _result_observer is not None:
        _result_observer(result)
    result._save()
    for service in plan.services:
        if estimates[service.model_id].total_bytes > service.allocation_bytes:
            report.update(status='rejected', decision=dict(outcome='not-attempted', reason='estimated-memory-does-not-fit'))
            result._save()
            return result

    try:
        for index, service in enumerate(plan.services if bound is None else []):
            profile = profiles[service.model_id]
            model = SeraModel(model_id=service.model_id, revision=service.revision,
                configuration=service.configuration, artifact_dir=folder/f'isolated-{index}')
            runner = runner_for_profile(model, profile)
            report['isolated_runtimes'].append(model.record)
            try:
                model.start()
                trial = collect_trial(runner, profile.prompts, 'isolated', workload=profile.workload)
                report['isolated'][service.model_id] = trial
                gate = _gate(trial, profile, service)
            finally:
                model.close()
                result._save()
            # close() stops and joins the memory monitor. Gate its final sample,
            # not a snapshot that can change while quality evaluation finishes.
            gpu = model.record.get('gpu', {})
            peak = model.record.get('sampled_peak_memory_mib')
            gate['memory_pass'] = (type(peak) is int and 0 < peak*1024**2 <= service.allocation_bytes
                and gpu.get('total_mib', 0)*1024**2 == plan.physical_gpu_bytes
                and model.record.get('telemetry_errors') == 0)
            gate['passed'] = gate['passed'] and gate['memory_pass']
            report['isolated_gates'][service.model_id] = gate
            result._event('placement_quality_gate', dict(
                plan_hash=plan.plan_hash, phase='isolated', model_id=service.model_id,
                revision=service.revision, config_hash=trial['config_hash'], gate=gate,
                task_quality=trial['task_quality'], measured_task_quality=trial['measured_task_quality']))
            if not gate['passed']:
                report.update(status='rejected', decision=dict(outcome='not-attempted', reason='isolated-requirements-failed'))
                result._save()
                return result

        if _references_only:
            report.update(status='references-ready',
                decision=dict(outcome='references-ready', reason='both-isolated-models-pass'))
            result._save()
            return result

        limits = {}
        for service in plan.services:
            trial = report['isolated'][service.model_id]
            reference_p95 = trial['reduced']['p95_latency_ms']
            ratio = service.constraints.max_p95_slowdown_fraction
            limit = service.constraints.p95_latency_ms
            if ratio is not None:
                relative = reference_p95 * (1 + ratio)
                limit = relative if limit is None else min(limit, relative)
            limits[service.model_id] = dict(p95_latency_limit_ms=limit,
                max_p95_slowdown_fraction=ratio, isolated_p95_ms=reference_p95,
                isolated_trial_sha256=content_hash(trial), config_hash=trial['config_hash'],
                workload_hash=report['workload_hash'],
                derivation='Approved contract applied to matching isolated p95 before joint startup')
        report['derived_joint_latency_limits'] = limits
        result._save()

        owner = SharedGPUOwner(plan)
        result.owner = owner
        owner.acquire()
        if any(trial['runtime'].get('gpu', {}).get('uuid') != owner.record['gpu']['uuid']
               for trial in report['isolated'].values()):
            raise RuntimeError('Joint GPU identity differs from an isolated reference')
        models = []
        for index, service in enumerate(plan.services):
            model = SeraModel(model_id=service.model_id, revision=service.revision,
                configuration=service.configuration, artifact_dir=folder/f'joint-{index}', placement_owner=owner)
            # Own a runner before start, so a partial second startup cannot leak the first.
            owner.models.append(model)
            models.append(runner_for_profile(model, profiles[service.model_id]))
            model.start()
        joint = collect_joint(models, profiles, **(dict(trial_id=_trial_namespace+'/joint') if _trial_namespace else {}))
        report['joint'] = joint
        joint['gates'] = {service.model_id:_gate(joint['trials'][service.model_id],
            profiles[service.model_id], service, joint=True,
            isolated_p95_ms=report['isolated'][service.model_id]['reduced']['p95_latency_ms'])
            for service in plan.services}
        for model_id, trial in joint['trials'].items():
            same_tokens = trial.get('input_token_ids') == report['isolated'][model_id].get('input_token_ids')
            joint['gates'][model_id]['input_tokens_match'] = same_tokens
            joint['gates'][model_id]['passed'] &= same_tokens
            before = report['isolated'][model_id].get('reduced', {}).get('p95_latency_ms')
            after = trial.get('reduced', {}).get('p95_latency_ms')
            joint.setdefault('isolated_comparison', {})[model_id] = dict(
                isolated_p95_latency_ms=before, joint_p95_latency_ms=after,
                slowdown_fraction=after/before-1 if before and after else None,
                cause='not-established')
            result._event('placement_quality_gate', dict(
                plan_hash=plan.plan_hash, phase='joint', model_id=model_id,
                revision=trial['runtime']['revision'], config_hash=trial['config_hash'],
                gate=joint['gates'][model_id], task_quality=trial['task_quality'],
                measured_task_quality=trial['measured_task_quality']))
        owner.check()
        required_windows = len(next(iter(profiles.values())).workload.concurrency)
        joint['overlap_pass'] = len(joint['overlap']) == required_windows and all(
            item['overlap_seconds'] > 0 for item in joint['overlap'])
        passed = joint['overlap_pass'] and all(gate['passed'] for gate in joint['gates'].values())
        if not passed:
            report.update(status='rejected', decision=dict(outcome='no-safe-placement', reason='joint-requirements-failed'))
            owner.close()
        else:
            result.models = models
            report.update(status='ready', returned_runner_closed=False,
                          decision=dict(outcome='safe-placement', reason='both-models-pass-measured-requirements'))
        result._save()
        return result
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__,
                      decision=dict(outcome='no-safe-placement' if result.owner else 'not-attempted', reason='execution-failed'))
        if isinstance(error, CleanupError):
            report.update(status='cleanup-failed', cleanup_error=type(error).__name__,
                          returned_runner_closed=False)
        result.models = []
        try:
            if result.owner is not None:
                result.owner.close()
        except BaseException as cleanup_error:
            report.update(status='cleanup-failed', cleanup_error=type(cleanup_error).__name__,
                          returned_runner_closed=False)
            raise
        finally:
            result._save()
        if isinstance(error, (CleanupError, KeyboardInterrupt, SystemExit)):
            raise
        return result
