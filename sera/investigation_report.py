"""Plain-English views of saved investigation evidence; no execution or inference."""


MISSING = 'not recorded'


def _value(value):
    return MISSING if value is None else str(value)


def _gate_label(value):
    return 'passed' if value is True else 'failed' if value is False else MISSING


def _specialist_scope(rounds, deployment):
    roles = {check.get('role') for record in rounds for check in record.get('specialists', [])
             if check.get('role') and check.get('status') != 'inactive'}
    advisor = deployment.get('planning_specialist') or {}
    if advisor.get('role'):
        roles.add(advisor['role'])
    if roles == {'batching'}:
        return 'This run is batching-only, not a full specialist swarm. Arbiter and review calls are separate roles.'
    if roles == {'quantization', 'batching'}:
        return ('Recorded specialist calls: quantization and batching. '
                'This covers two specialists, not the full product agent team.')
    return f"Recorded specialist roles: {', '.join(sorted(roles)) or MISSING}."


def _deployment_lines(deployment, search):
    if not deployment:
        return []
    baseline = deployment.get('infeasible_baseline') or {}
    estimate = baseline.get('fit_estimate') or {}
    specialist = deployment.get('planning_specialist') or {}
    response = specialist.get('response') or {}
    arbiter = deployment.get('planning_decision') or {}
    decision = deployment.get('decision') or {}
    review = deployment.get('agent_final') or {}
    lines = ['### Deployment stage', '',
             f"Original BF16 baseline: {baseline.get('status', MISSING)} "
             '(estimate only; not a measured BF16 run).',
             f"Fit reason: {baseline.get('reason', MISSING)}.",
             f"Estimated BF16 runtime bytes: {_value(estimate.get('estimated_peak_bytes'))}.",
             f"Quantization specialist status: {specialist.get('status', MISSING)}.",
             f"Quantization specialist recommends: {', '.join(response.get('ranked_proposal_ids', [])) or 'none'}. "
             f"Reason: {response.get('reason', MISSING)}",
             f"Deployment arbiter chose: {', '.join(arbiter.get('ranked_proposal_ids', [])) or 'none'}. "
             f"Reason: {arbiter.get('reason', MISSING)}"]
    if specialist.get('error'):
        lines.append(f"Quantization specialist error: {specialist['error']}.")
    if deployment.get('candidate_trial'):
        trial = deployment['candidate_trial']
        lines.extend(_trial_lines({**trial, 'decision': trial.get('decision', decision),
                                   'review': trial.get('review', review)}))
    lines.extend([
        f"Deployment outcome: {decision.get('outcome', MISSING)}; selected={_value(decision.get('selected'))}.",
        f"Deployment prediction review: {review.get('prediction_outcome', MISSING)}. "
        f"{review.get('reason', MISSING)}",
        f"Deployment trials included in budget: {_value(search.get('initial_trials_used'))}.",
        'No BF16 speedup comparison is available: the BF16 baseline was not measured.',
        'The measured deployment becomes the reference for later batching trials. '
        'Specialists act in separate stages; this does not show competing proposals in one round.', ''])
    return lines


def _proposal_lines(check):
    proposal = check.get('proposal') or {}
    evidence = check.get('evidence') or {}
    history = evidence.get('history')
    history_ids = [item.get('trial', {}).get('trial_id', MISSING) for item in history or []]
    history_text = ', '.join(history_ids) if history_ids else ('none' if history is not None else MISSING)
    lines = [f"Specialist {check.get('role', MISSING)}: {check.get('status', MISSING)}.",
             f"History supplied: {history_text}."]
    if proposal:
        change = ('no setting change' if proposal.get('action') == 'keep-baseline' else
                  f"{_value(proposal.get('changed_lever'))} = {_value(proposal.get('proposed_value'))}")
        lines.extend([
            f"Proposal {proposal.get('proposal_id', MISSING)}: {proposal.get('action', MISSING)}; {change}.",
            f"Parent trial: {proposal.get('parent_trial_id', MISSING)}.",
            f"Reason: {proposal.get('reason', MISSING)}",
            f"Prediction: {proposal.get('predicted_metric_change', MISSING)}",
            f"Would refute it: {proposal.get('falsification_condition', MISSING)}",
            f"Cited metrics: {', '.join(proposal.get('evidence_used', [])) or MISSING}."])
        metrics = evidence.get('metrics') or {}
        for name in proposal.get('evidence_used', []):
            lines.append(f"Cited value: {name}={_value(metrics.get(name))}.")
    for item in history or []:
        trial, review = item.get('trial') or {}, item.get('review') or {}
        quality = (trial.get('task_quality') or {}).get('passed')
        lines.append(f"Prior feedback: {trial.get('trial_id', MISSING)}: quality={_gate_label(quality)}; "
                     f"prediction={review.get('prediction_outcome', MISSING)}.")
    if check.get('arbiter_proposal_id'):
        lines.append(f"Arbitration ID: {check['arbiter_proposal_id']}.")
    if check.get('error'):
        lines.append(f"Validation error: {check['error']}.")
    if history is None:
        lines.append('The saved evidence does not establish that this choice received prior results.')
    return lines


def _trial_lines(trial):
    metrics = trial.get('reduced') or {}
    decision = trial.get('decision') or {}
    gate = trial.get('task_quality') or decision.get('candidate_quality') or {}
    passed = gate.get('passed')
    quality = 'passed' if passed is True else 'failed' if passed is False else MISSING
    lines = [f"Trial {trial.get('trial_id', MISSING)}: {trial.get('status', MISSING)}.",
             f"Scheduled by: {trial.get('selection_reason', MISSING)}.",
             f"Quality gate: {quality}; score={_value(gate.get('mean'))}; floor={_value(gate.get('floor'))}.",
             f"p95: {_value(metrics.get('p95_latency_ms'))} ms; "
             f"throughput: {_value(metrics.get('output_tokens_per_second'))} output tokens/s; "
             f"peak memory: {_value((trial.get('runtime') or {}).get('sampled_peak_memory_mib'))} MiB.",
             f"Gate selection: {_value(decision.get('selected'))}; reason: {decision.get('reason', MISSING)}."]
    if decision.get('constraint_failures'):
        lines.append(f"Constraint failures: {decision['constraint_failures']}.")
    review = trial.get('review') or {}
    if review:
        lines.append(f"Prediction review: {review.get('prediction_outcome', MISSING)}. "
                     f"{review.get('reason', MISSING)}")
    else:
        lines.append(f"Prediction review: {trial.get('review_error', MISSING)}.")
    if trial.get('error'):
        lines.append(f"Trial error: {trial['error']}.")
    return lines


def render_investigation(report):
    """Render saved facts only. Missing history is not evidence of learning."""
    if 'search' not in report:
        return ''
    search = report.get('search') or {}
    deployment = report.get('deployment') or {}
    trials = {trial['trial_id']: trial for trial in report.get('search_trials', []) if 'trial_id' in trial}
    lines = ['## Agent investigation', '']
    if ((report.get('provenance') or {}).get('kind') == 'synthetic'
            or (report.get('provider_validation') or {}).get('provenance') == 'synthetic'):
        lines.extend(['SYNTHETIC offline rehearsal. Agents, outputs, timing, and memory are fixtures.',
                      'No LM or GPU calls ran. This is not measured model performance.', ''])
    lines.extend(['Agents propose experiments. Deterministic checks decide which results are eligible.',
                  'Trial order and access to history do not prove a causal search advantage.',
                  _specialist_scope(search.get('rounds', []), deployment), ''])
    lines.extend(_deployment_lines(deployment, search))
    rendered = set()
    previous = None
    for record in search.get('rounds', []):
        lines.extend([f"### Round {record.get('round', MISSING)}", ''])
        for role in record.get('specialist_participation', []):
            lines.append(f"Participation {role.get('role', MISSING)}: {role.get('status', MISSING)}; "
                         f"legal candidates={_value(role.get('legal_candidate_count'))}; "
                         f"{role.get('reason', MISSING)}.")
        if record.get('specialist_participation'):
            lines.append('Inactive roles were not called. Active means a legal untested setting was available.')
            lines.append('')
        for check in record.get('specialists', []):
            lines.extend(_proposal_lines(check) + [''])
        arbiter = record.get('arbiter') or {}
        proposals = (record.get('arbiter_evidence') or {}).get('proposals', [])
        if len(proposals) == 2 and len({proposal.get('agent_role') for proposal in proposals}) == 2:
            lines.append('Two specialist proposals competed for the next trial.')
        if arbiter:
            lines.append(f"Arbiter chose: {', '.join(arbiter.get('ranked_proposal_ids', [])) or 'none'}. "
                         f"Reason: {arbiter.get('reason', MISSING)}")
        elif record.get('arbiter_error'):
            lines.append(f"Arbiter failed: {record['arbiter_error']}.")
        else:
            lines.append('Arbiter choice: not recorded.')
        if (previous and (previous.get('arbiter') or {}).get('ranked_proposal_ids')
                and arbiter.get('ranked_proposal_ids') == []):
            lines.append('Arbiter changed from selecting an experiment to declining one. '
                         'Its saved reason is shown above; this is not proof of a search advantage.')
        lines.append(f"Trials executed in this round: {', '.join(record.get('trial_ids', [])) or 'none'}.")
        for trial_id in record.get('trial_ids', []):
            lines.extend([''] + _trial_lines(trials.get(trial_id, {'trial_id': trial_id})))
            rendered.add(trial_id)
        lines.append('')
        previous = record
    for trial_id, trial in trials.items():
        if trial_id not in rendered:
            lines.extend([f"Trial has no saved round link: {trial_id}."] + _trial_lines(trial) + [''])
    decision = report.get('decision') or {}
    lines.extend([f"Final selection: {_value(decision.get('selected'))}.",
                  f"Stop reason: {search.get('stop_reason') or MISSING}.",
                  f"Trials used: {_value(search.get('trials_used'))}/"
                  f"{_value((search.get('budget') or {}).get('max_candidate_trials'))}.",
                  f"Runner status: {report.get('status', MISSING)}; "
                  f"closed={_value(report.get('returned_runner_closed'))}.",
                  'Raw evidence: result.json — search.rounds, search_trials, and agent_calls.', ''])
    if report.get('rehearsal'):
        probe = report['rehearsal']
        lines.extend([f"Synthetic fresh-runner probe passed: {_value(probe.get('fresh_probe_passed'))}.",
                      f"Synthetic fresh response: {probe.get('fresh_response', MISSING)}", ''])
    return '\n'.join(lines)
