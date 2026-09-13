"""Read-only, dependency-free views for the recorded marimo demo."""

import json
from pathlib import Path


MISSING = 'not recorded'


def _gate(value):
    return 'passed' if value is True else 'failed' if value is False else MISSING


def _measurements(trial):
    if trial is None:
        return 'not run'
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
             'max_model_len': 'Context limit', 'kv_cache_dtype': 'KV precision'}
    lever = proposal.get('changed_lever', MISSING)
    return f"{names.get(lever, lever)} → {proposal.get('proposed_value', MISSING)}"


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
                        and (trials[trial_id].get('proposal') or {}).get('proposal_id') == proposal.get('proposal_id')
                        and (trials[trial_id].get('proposal') or {}).get('agent_role') == specialist.get('role')]
            trial = matching[0] if matching else None
            review = (trial or {}).get('review') or {}
            rows.append({'Stage': f"Round {record.get('round', MISSING)}",
                         'Specialist': specialist.get('role', MISSING), 'Proposed change': _change(proposal),
                         'Arbiter': _arbiter(record.get('arbiter')),
                         'Measured gates': _measurements(trial),
                         'Prediction review': review.get('prediction_outcome', MISSING)})
    return rows


def load_investigation_demo(root):
    """Prefer the named team record only when present; never load a synthetic fallback."""
    root = Path(root)
    sources = ['evidence/live-team-investigation-v1/result.json', 'evidence/live-investigation-v1/result.json']
    source = next((name for name in sources if (root / name).is_file()), None)
    view = {'source': source, 'rows': [], 'banner': 'No saved live investigation is available yet.',
            'scope': '', 'runner': MISSING, 'limits': '', 'trace_url': None, 'budget': MISSING}
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
    decision = report.get('decision') or {}
    selected = decision.get('selected')
    config = report.get('baseline_configuration') if selected == 'baseline' else next(
        ((trial.get('runtime') or {}).get('configuration') for trial in report.get('search_trials', [])
         if trial.get('trial_id') == selected), None)
    runner = f"Selected runner: {selected or MISSING}"
    if config:
        runner += f" · {'FP8 weights' if config.get('quantization') == 'fp8_per_tensor' else 'BF16 weights'}"
        runner += f" · batch token limit {config.get('max_num_batched_tokens', MISSING)}"
    runner += f" · fresh request {_gate(report.get('post_return_task_passed'))}"
    runner += ' · closed after the recorded run' if report.get('returned_runner_closed') is True else ' · closure not recorded'
    search = report.get('search') or {}
    limits = 'Access to earlier measurements does not prove a search advantage. No best-plan or speedup claim.'
    if report.get('deployment'):
        limits += ' The BF16 fit rejection is an estimate, not a measured BF16 comparison.'
    return view | {'rows': rows, 'banner': banner, 'scope': scope, 'runner': runner, 'limits': limits,
                   'trace_url': report.get('weave_url'),
                   'budget': f"{search.get('trials_used', MISSING)}/{(search.get('budget') or {}).get('max_candidate_trials', MISSING)}"}
