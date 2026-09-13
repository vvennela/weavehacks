"""Plain-English views of saved investigation evidence; no execution or inference."""


MISSING = 'not recorded'


def _value(value):
    return MISSING if value is None else str(value)


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
    trials = {trial['trial_id']: trial for trial in report.get('search_trials', []) if 'trial_id' in trial}
    lines = ['## Agent investigation', '']
    if (report.get('provenance') or {}).get('kind') == 'synthetic':
        lines.extend(['SYNTHETIC offline rehearsal. Agents, outputs, timing, and memory are fixtures.',
                      'No LM or GPU calls ran. This is not measured model performance.', ''])
    lines.extend(['Agents propose experiments. Deterministic checks decide which results are eligible.',
                  'Trial order and access to history do not prove a causal search advantage.', ''])
    rendered = set()
    for record in search.get('rounds', []):
        lines.extend([f"### Round {record.get('round', MISSING)}", ''])
        for check in record.get('specialists', []):
            lines.extend(_proposal_lines(check) + [''])
        arbiter = record.get('arbiter') or {}
        if arbiter:
            lines.append(f"Arbiter chose: {', '.join(arbiter.get('ranked_proposal_ids', [])) or 'none'}. "
                         f"Reason: {arbiter.get('reason', MISSING)}")
        elif record.get('arbiter_error'):
            lines.append(f"Arbiter failed: {record['arbiter_error']}.")
        else:
            lines.append('Arbiter choice: not recorded.')
        for trial_id in record.get('trial_ids', []):
            lines.extend([''] + _trial_lines(trials.get(trial_id, {'trial_id': trial_id})))
            rendered.add(trial_id)
        lines.append('')
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
