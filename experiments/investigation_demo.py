"""Read-only, dependency-free views for the recorded marimo demo."""

import json
from pathlib import Path


MISSING = 'not recorded'


def _gate(value):
    return 'passed' if value is True else 'failed' if value is False else MISSING


def _measurements(trial):
    if trial is None:
        return 'not run'
    if trial.get('status') == 'startup-failed':
        return 'startup-failed; no quality or latency measurement'
    metrics = trial.get('reduced') or {}
    quality = trial.get('task_quality') or {}
    latency = metrics.get('p95_latency_ms')
    latency_text = f'{latency:.2f} ms' if latency is not None else MISSING
    text = (f"quality {_gate(quality.get('passed'))}; p95 {latency_text}; "
            f"errors {metrics.get('generation_errors', MISSING)}")
    decision = trial.get('decision') or {}
    gain = decision.get('objective_improvement_fraction')
    required = (decision.get('objective') or {}).get('min_improvement_fraction')
    if gain is not None and required is not None:
        text += f'; gain {100 * gain:.3f}%, needs {100 * required:g}%'
    return text


def _arbiter(value):
    if value is None:
        return MISSING
    return ', '.join(value.get('ranked_proposal_ids', [])) or 'declined'


def _change(proposal):
    if not proposal:
        return MISSING
    if proposal.get('action') == 'keep-baseline':
        return 'no change'
    names = {'max_num_batched_tokens': 'Batch token limit', 'max_num_seqs': 'Sequence limit',
             'max_model_len': 'Context limit', 'kv_cache_dtype': 'KV precision',
             'enable_prefix_caching': 'Prefix caching', 'enable_chunked_prefill': 'Chunked prefill',
             'enforce_eager': 'Force eager execution', 'gpu_memory_utilization': 'GPU memory fraction'}
    lever = proposal.get('changed_lever', MISSING)
    return f"{names.get(lever, lever)} → {proposal.get('proposed_value', MISSING)}"


def _matches_trial(trial, specialist):
    if specialist.get('investigator_id'):
        identity = specialist.get('arbiter_proposal_id')
        return bool(identity) and trial.get('arbiter_proposal_id') == identity
    proposal = specialist.get('proposal') or {}
    measured = trial.get('proposal') or {}
    return (measured.get('proposal_id') == proposal.get('proposal_id')
            and measured.get('agent_role') == specialist.get('role'))


def _rows(report):
    rows = []
    deployment = report.get('deployment') or {}
    if deployment:
        config = (deployment.get('candidate') or {}).get('config') or {}
        rows.append({'Stage': 'Deployment', 'Specialist': 'quantization',
                     'Proposed change': 'FP8 weights' if config.get('quantization') == 'fp8_per_tensor' else MISSING,
                     'Arbiter': _arbiter(deployment.get('planning_decision')),
                     'Measured gates': _measurements(deployment.get('candidate_trial')),
                     'Prediction review': (deployment.get('agent_final') or {}).get('prediction_outcome', MISSING)})
    trials = {trial['trial_id']: trial for trial in report.get('search_trials', []) if 'trial_id' in trial}
    for record in (report.get('search') or {}).get('rounds', []):
        for specialist in record.get('specialists', []):
            proposal = specialist.get('proposal') or {}
            matching = [trials[trial_id] for trial_id in record.get('trial_ids', []) if trial_id in trials
                        and _matches_trial(trials[trial_id], specialist)]
            trial = matching[0] if matching else None
            review = (trial or {}).get('review') or {}
            rows.append({'Stage': f"Round {record.get('round', MISSING)}",
                         'Specialist': specialist.get('investigator_id') or specialist.get('role', MISSING),
                         'Proposed change': _change(proposal),
                         'Agent explanation': proposal.get('reason') or MISSING,
                         'Arbiter': _arbiter(record.get('arbiter')),
                         'Measured gates': _measurements(trial),
                         'Parent trial': (trial or {}).get('parent_trial_id', MISSING),
                         'Component trials': ', '.join((trial or {}).get('component_trial_ids', [])) or MISSING,
                         'Prediction review': review.get('prediction_outcome', MISSING)})
            if specialist.get('investigator_id'):
                inspections = specialist.get('inspections', [])
                rows[-1].update({'Control role': specialist.get('role', MISSING),
                    'Proposal status': specialist.get('status', MISSING),
                    'Inspection status': specialist.get('inspection_status', MISSING),
                    'Initial proposal': _change(specialist.get('initial_proposal')),
                    'Inspections': ', '.join(f"{item.get('query_id', MISSING)} ({item.get('status', MISSING)})"
                                             for item in inspections) or MISSING,
                    'Trace calls': ', '.join(str(row['call_id']) for item in inspections
                                            for row in (item.get('result') or {}).get('records', [])
                                            if row.get('call_id')) or MISSING})
    return rows


def load_investigation_demo(root):
    """Prefer the expanded swarm record; never load a synthetic fallback."""
    root = Path(root)
    sources = ['evidence/live-astra-expanded-v1/result.json',
               'evidence/live-core-loop-v1/result.json', 'evidence/live-swarm-investigation-v1/result.json',
               'evidence/live-team-investigation-v1/result.json', 'evidence/live-investigation-v1/result.json']
    source = next((name for name in sources if (root / name).is_file()), None)
    view = {'source': source, 'rows': [], 'banner': 'No saved live investigation is available yet.',
            'scope': '', 'runner': MISSING, 'limits': '', 'trace_url': None, 'budget': MISSING,
            'stop_reason': MISSING}
    if source is None:
        return view
    try:
        report = json.loads((root / source).read_text())
        if not isinstance(report, dict):
            raise ValueError('Expected a report object')
    except (OSError, ValueError):
        return view | {'banner': 'The selected saved investigation could not be read. No result is inferred.'}
    synthetic = ((report.get('provenance') or {}).get('kind') == 'synthetic'
                 or (report.get('provider_validation') or {}).get('provenance') == 'synthetic')
    status = report.get('status', MISSING)
    banner = ('SYNTHETIC record — not measured LM or GPU performance.' if synthetic else
              f'Recorded real run — status: {status}. This notebook does not run live inference.')
    if status not in {'closed', 'no-safe-configuration', 'failed'}:
        banner += ' Saved in-progress record: not a completed result.'
    rows = _rows(report)
    roles = {row['Specialist'] for row in rows}
    scope = ('This run is batching-only: a batching specialist, arbiter, and reviewer. No quantization specialist ran.'
             if roles == {'batching'} else
             'Quantization and batching act in separate stages, not competing proposals in one round.'
             if report.get('deployment') and roles == {'batching', 'quantization'} else
             f"Saved specialist roles: {', '.join(sorted(roles)) or MISSING}.")
    if report.get('swarm_enabled'):
        scope = (f"Investigators recorded: {', '.join(sorted(roles)) or MISSING}. "
                 'Read the initial findings, peer-reviewed proposals, and measured outcome separately. '
                 'Investigator roles do not enable multi-GPU parallelism; GPU trials remain sequential.')
    decision = report.get('decision') or {}
    selected = decision.get('selected')
    selected_trial = report.get('baseline') if selected == 'baseline' else next(
        (trial for trial in report.get('search_trials', []) if trial.get('trial_id') == selected), None)
    config = report.get('baseline_configuration') if selected == 'baseline' else (
        ((selected_trial or {}).get('runtime') or {}).get('configuration'))
    runner = f"Selected runner: {selected or MISSING}"
    if config:
        runner += f" · {'FP8 weights' if config.get('quantization') == 'fp8_per_tensor' else 'BF16 weights'}"
        runner += f" · batch token limit {config.get('max_num_batched_tokens', MISSING)}"
        if type(config.get('enable_prefix_caching')) is bool:
            runner += ' · prefix caching ' + ('on' if config['enable_prefix_caching'] else 'off')
        if type(config.get('enforce_eager')) is bool:
            runner += ' · ' + ('eager execution' if config['enforce_eager'] else 'graph execution enabled')
    latency = ((selected_trial or {}).get('reduced') or {}).get('p95_latency_ms')
    gain = ((selected_trial or {}).get('decision') or {}).get('objective_improvement_fraction')
    if latency is not None:
        runner += f' · measured p95 {latency:.2f} ms'
    if gain is not None:
        runner += f' · measured objective gain {100 * gain:.2f}% versus baseline'
    runner += f" · fresh request {_gate(report.get('post_return_task_passed'))}"
    runner += ' · closed after the recorded run' if report.get('returned_runner_closed') is True else ' · closure not recorded'
    search = report.get('search') or {}
    limits = ('Agent explanations are claims, not measured facts. '
              'Access to earlier measurements does not prove a search advantage. '
              'Measured gains apply only to the saved workload, not a globally optimal plan.')
    cache_scope = (((report.get('baseline') or {}).get('workload') or {}).get('cache_evaluation') or {})
    if cache_scope.get('measured_scope') == 'repeated-prompts-after-per-load-warmup':
        limits += ' Repeated prompts after warmup; not cold or unseen traffic. Startup is separate from request latency.'
    if report.get('deployment'):
        limits += ' The BF16 fit rejection is an estimate, not a measured BF16 comparison.'
    cap = (search.get('budget') or {}).get('max_candidate_trials', MISSING)
    used = search.get('trials_used', MISSING)
    return view | {'rows': rows, 'banner': banner, 'scope': scope, 'runner': runner, 'limits': limits,
                   'trace_url': report.get('weave_url'),
                   'stop_reason': search.get('stop_reason') or MISSING,
                   'budget': f'{used}; no total cap' if cap is None else f'{used}/{cap}'}
