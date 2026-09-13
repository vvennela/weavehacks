"""Installed stage API contract checks. No GPU, provider, or Weave service calls."""

import inspect
import json
from pathlib import Path
from unittest.mock import patch

import sera
from sera.config import MODEL_ID, Constraints
from sera.measurement import select_candidate
from sera.stage_config import inherited_constraints, validate_stage_options


def main():
    package_path = Path(sera.__file__).resolve()
    assert 'site-packages' in package_path.parts, 'Must inspect the installed wheel'
    signature = inspect.signature(sera.optimize)
    assert {'stages', 'k', 'min_improvement_pct'} <= set(signature.parameters)
    assert 'max_latency_regression_pct' not in signature.parameters
    plan = validate_stage_options(['latency', 'quant'], 3.0)
    assert plan.stages == ('latency', 'quantization')
    assert plan.regression_fraction == .03
    assert plan.min_improvement_fraction == 0.0
    assert validate_stage_options(['latency'], 3.0, 2.0).min_improvement_fraction == .02
    checkpoints = [
        {'stage': 'latency', 'status': 'completed', 'p95_latency_ms': 100.0},
        {'stage': 'quantization', 'status': 'completed', 'sampled_peak_memory_mib': 2000},
    ]
    limits = inherited_constraints(Constraints(quality_floor=.99), checkpoints, k=3.0)
    assert limits.p95_latency_ms == 103.0
    assert limits.max_memory_mib == 2060
    assert limits.quality_floor == .99
    strict = inherited_constraints(Constraints(quality_floor=.99, p95_latency_ms=101.0,
        max_memory_mib=2010), checkpoints, k=3.0)
    assert strict.p95_latency_ms == 101.0 and strict.max_memory_mib == 2010

    def trial(latency, memory):
        return {'status': 'collected', 'task_quality': {'mean': 1.0, 'valid_outputs': True},
            'runtime': {'sampled_peak_memory_mib': memory},
            'reduced': {'p95_latency_ms': latency, 'generation_errors': 0}}

    objective = sera.Objective(priority='memory', min_improvement_fraction=0.0)
    baseline = trial(100.0, 2000)
    accepted = select_candidate(baseline, trial(101.0, 1960), objective=objective, constraints=limits)
    assert accepted['selected'] == 'candidate', '2% memory gain and 1% latency regression must pass'
    rejected = select_candidate(baseline, trial(104.0, 1960), objective=objective, constraints=limits)
    assert rejected['selected'] == 'baseline', '4% regression exceeds k=3'
    assert select_candidate(baseline, trial(100.0, 2000), objective=objective,
                            constraints=limits)['selected'] == 'baseline', 'A positive gain is required'

    captured = []
    with patch('sera.stages.run_stages', side_effect=lambda **arguments: captured.append(arguments) or 'captured'):
        assert sera.optimize(models=[MODEL_ID], prompts=['fixture'],
            stages=['latency', 'quantization'], k=3.0) == 'captured'
        assert captured[-1]['k'] == 3.0
        assert captured[-1]['min_improvement_pct'] == 0.0
        assert sera.optimize(models=[MODEL_ID], prompts=['fixture'],
            stages=['latency', 'quantization'], k=3.0, min_improvement_pct=2.0) == 'captured'
        assert captured[-1]['min_improvement_pct'] == 2.0
    try:
        sera.optimize(models=[MODEL_ID], prompts=['fixture'], k=3.0)
    except ValueError as error:
        assert 'k requires stages' in str(error)
    else:
        raise AssertionError('A regression allowance requires stages')
    print(json.dumps({'status': 'passed', 'package_path': str(package_path),
        'k_semantics': 'allowed regression in earlier measured objectives',
        'default_minimum_gain': 'strictly positive; no percentage floor',
        'checks': ['installed public API shape', 'alias and percentage validation',
                   'latency and memory ceilings preserve original hard limits',
                   '2% gain with 1% regression passes; 4% regression fails',
                   'zero gain fails', 'public API forwards independent k and minimum gain'],
        'gpu_calls': 0, 'provider_calls': 0, 'weave_service_calls': 0,
        'stage_execution_boundary': 'stubbed; pure measurement gates are real'}))


if __name__ == '__main__':
    main()
