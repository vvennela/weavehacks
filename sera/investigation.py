"""Bounded live feedback loop. Agents propose; measurements and gates decide."""

from copy import deepcopy

from .agent import ArbiterDecision, Proposal, validate_proposal
from .config import CONTROL_ROLES, Candidate, RuntimeConfig, validate_candidate
from .measurement import measured_frontier, objective_value, select_candidate, token_agreement
from .quality import evaluate_quality
from .runtime import CleanupError, GENERATION


def search_frontier(baseline, trials, *, constraints):
    viable = {trial['trial_id']: trial for trial in measured_frontier(baseline, None, constraints=constraints)}
    for trial in trials:
        viable.update({item['trial_id']: item for item in measured_frontier(baseline, trial, constraints=constraints)})

    def dominates(left, right):
        before = [objective_value(left, key) for key in ('latency', 'memory', 'throughput')]
        after = [objective_value(right, key) for key in ('latency', 'memory', 'throughput')]
        if None in before or None in after:
            return False
        return (before[0] <= after[0] and before[1] <= after[1] and before[2] >= after[2]
                and before != after)

    return [trial for trial in viable.values()
            if not any(dominates(other, trial) for other in viable.values())]


def remaining_candidates(evidence, baseline_config, seen, workload, baseline):
    """Use only already-active values; schema expansion does not activate them."""
    legal = []
    considered = set(seen)
    frozen_hashes = evidence.get('frozen_candidate_hashes')
    for lever, values in evidence['supported_changes'].items():
        for value in values:
            config = RuntimeConfig.model_validate(baseline_config.model_dump() | {lever: value})
            if config.config_hash in considered:
                continue
            considered.add(config.config_hash)
            if frozen_hashes is not None and config.config_hash not in frozen_hashes:
                continue
            candidate = validate_candidate(Candidate(name=config.config_hash, reason='Active experiment', config=config),
                                           baseline=baseline_config, supported_changes=evidence['supported_changes'],
                                           frozen_candidate_hashes=frozen_hashes)
            if max(workload.concurrency) > config.max_num_seqs:
                continue
            required_length = max(map(len, baseline.get('input_token_ids', [[]]))) + GENERATION['max_tokens']
            if config.max_model_len < required_length:
                continue
            legal.append((CONTROL_ROLES[lever], lever, value, candidate))
    return legal


def round_evidence(initial, search, trials, remaining):
    from .pipeline import load_snapshot_metrics

    evidence = deepcopy(initial)
    evidence['remaining_trials'] = remaining
    evidence['history'] = [dict(trial={key: deepcopy(trial[key]) for key in
        ('trial_id', 'status', 'config_hash', 'reduced', 'task_quality', 'decision', 'error',
         'failure_stage') if key in trial},
        configuration=deepcopy(trial['runtime']['configuration']),
        proposal=deepcopy(trial.get('proposal')), review=deepcopy(trial.get('review')),
        review_error=trial.get('review_error')) for trial in trials]
    evidence['previous_rounds'] = [dict(round=record['round'], trial_ids=record['trial_ids'][:],
        arbiter=deepcopy(record.get('arbiter')), arbiter_error=record.get('arbiter_error'),
        specialist_participation=deepcopy(record.get('specialist_participation', [])),
        specialists=[{key: deepcopy(check[key]) for key in
                      ('role', 'status', 'proposal', 'error', 'arbiter_proposal_id')
                      if key in check} for check in record['specialists']]) for record in search['rounds']]
    # Exact metric names remain valid citations, including failed-trial measurements.
    for index, trial in enumerate(trials, search.get('initial_trials_used', 0) + 1):
        metrics = dict(trial.get('reduced', {}))
        metrics['sampled_peak_memory_mib'] = trial['runtime'].get('sampled_peak_memory_mib')
        metrics.update(load_snapshot_metrics(trial))
        for key, value in metrics.items():
            evidence['metrics'][f'trial_{index}_{key}'] = value
    return evidence


def specialist_participation(evidence, legal):
    """Record eligibility separately from actual requests and their outcomes."""
    participation = []
    for role in ('quantization', 'batching'):
        count = sum(entry[0] == role for entry in legal)
        enabled = any(CONTROL_ROLES.get(lever) == role and values
                      for lever, values in evidence['supported_changes'].items())
        if count:
            reason = 'Legal untested candidates are available for this specialist.'
        elif not enabled:
            reason = 'No control values are enabled for this specialist in this run.'
        else:
            reason = 'No legal untested candidate remains for this specialist.'
        participation.append(dict(role=role, status='active' if count else 'inactive',
                                  reason=reason, legal_candidate_count=count))
    participation.append(dict(role='parallelism', status='inactive', legal_candidate_count=0,
        reason='Single-GPU runtime fixes tensor_parallel_size at 1; parallelism controls are not enabled.'))
    return participation


def deployment_context(deployment):
    """Carry the measured fit decision without replaying its raw outputs as history."""
    reference = deployment['infeasible_baseline']
    trial = deployment['candidate_trial']
    feedback = deployment.get('agent_feedback', {})
    gate = trial.get('task_quality', {})
    return {
        'bf16_baseline_measured': False,
        'infeasible_baseline': {key: deepcopy(reference[key]) for key in
                               ('status', 'reason', 'fit_estimate') if key in reference},
        'selected_configuration': deepcopy(trial['runtime']['configuration']),
        'task_quality': {key: deepcopy(gate[key]) for key in
                         ('version', 'floor', 'mean', 'valid_outputs', 'passed') if key in gate},
        'feasibility_prediction': deepcopy(feedback.get('prediction')),
        'feasibility_review': deepcopy(deployment.get('agent_final')),
        'review_error': deployment.get('agent_final_error'),
        'comparison_scope': 'Search compares against the measured FP8 reference, not BF16 performance.',
    }


def choose_experiments(agent, evidence, legal, record, remaining):
    record['specialist_participation'] = specialist_participation(evidence, legal)
    proposals = {}
    for role in ('quantization', 'batching'):
        entries = [entry for entry in legal if entry[0] == role]
        if not entries:
            continue
        changes = {}
        for _, lever, value, _ in entries:
            changes.setdefault(lever, []).append(value)
        supplied = deepcopy(evidence) | dict(specialist_role=role, supported_changes=changes,
            frozen_candidate_hashes=[entry[3].config.config_hash for entry in entries])
        check = {'role': role, 'evidence': supplied, 'status': 'rejected'}
        record['specialists'].append(check)
        try:
            proposal = agent.request('proposal', supplied,
                'Act only as specialist_role. Investigate the supplied measurements and trial history. '
                'Use failures and prediction reviews to choose one untested supported experiment, '
                'or keep-baseline when none is useful. Cite exact available metric names. '
                'State the expected change and what would refute it. Do not claim an unmeasured gain.')
            if proposal is None or proposal.agent_role != role:
                raise ValueError('No valid response from the active specialist')
            check['proposal'] = proposal.model_dump()
            proposal = Proposal.model_validate(check['proposal'])
            candidate = validate_proposal(proposal, supplied)
            if candidate is None:
                check['status'] = 'abstained'
                continue
            # Specialists generate IDs independently. Keep originals in the audit,
            # but give the arbiter an unambiguous per-specialist identifier.
            key = f'{role}:{proposal.proposal_id}'
            check['arbiter_proposal_id'] = key
            proposals[key] = (proposal, candidate)
            check['status'] = 'accepted'
        except Exception as error:
            check['error'] = type(error).__name__
    if not proposals:
        return []
    arbitration = deepcopy(evidence) | dict(legal_proposal_ids=list(proposals),
        proposals=[proposal.model_dump() | {'proposal_id': key}
                   for key, (proposal, _) in proposals.items()],
        proposal_id_map={key: dict(agent_role=proposal.agent_role, original_proposal_id=proposal.proposal_id)
                         for key, (proposal, _) in proposals.items()})
    record['arbiter_evidence'] = arbitration
    try:
        ranked = agent.request('arbiter', arbitration,
            'Rank at most one legal proposal by constraint relief, expected gain, information value, '
            'confidence, and cost. Use observed failed trials. Empty means no useful experiment.')
        if ranked is None:
            raise ValueError('Arbiter returned no ranking')
        record['arbiter'] = ranked.model_dump()
        ranked = ArbiterDecision.model_validate(record['arbiter'])
        if any(key not in proposals for key in ranked.ranked_proposal_ids):
            raise ValueError('Arbiter named no valid ranking')
        chosen = [(key, 'arbiter') for key in ranked.ranked_proposal_ids]
        # Section 13: one untested exploration proposal when at least three trials remain.
        if chosen and remaining >= 3:
            other = next((key for key in proposals if key != chosen[0][0]), None)
            if other is not None:
                chosen.append((other, 'exploration'))
        return [(proposals[key][0], proposals[key][1], reason) for key, reason in chosen]
    except Exception as error:
        record['arbiter_error'] = type(error).__name__
        return []


def investigate(*, result, active, agent, history_start, budget, objective, constraints,
                evaluation, evaluation_version, workload, initial_trials_used=0):
    from . import pipeline

    report, folder = result.report, result.output_dir

    def save():
        report['agent_calls'] = agent.history[history_start:]
        result._save()

    def close_active():
        nonlocal active
        if active is not None:
            active.close()
            active = None

    def frontier_points():
        return {tuple(objective_value(trial, priority) for priority in ('latency', 'memory', 'throughput'))
                for trial in result.frontier}

    try:
        # Ownership has already transferred from optimize. Even setup failures
        # must close the running baseline.
        if (type(initial_trials_used) is not int
                or not 0 <= initial_trials_used <= budget.max_candidate_trials):
            raise ValueError('Initial trials used must be an integer within the candidate budget')
        baseline = report['baseline']
        baseline_config = RuntimeConfig.model_validate(report['baseline_configuration'])
        search = dict(budget=budget.model_dump(), initial_trials_used=initial_trials_used,
                      trials_used=initial_trials_used, rounds=[], stop_reason=None)
        report.update(mode='agent-investigation', search=search, search_trials=[],
                      limits=['single model', 'already-active single-setting controls',
                              'no combination trials', 'no live search-advantage claim'])
        initial = pipeline.agent_evidence(baseline, objective, constraints)
        if report.get('deployment'):
            initial['deployment_context'] = deployment_context(report['deployment'])
        space = report.get('investigation_space')
        if space is not None:
            initial['supported_changes'] = deepcopy(space['supported_changes'])
            if space.get('candidate_hashes') is not None:
                initial['frozen_candidate_hashes'] = list(space['candidate_hashes'])
        seen = {baseline_config.config_hash}
        best = baseline if select_candidate(baseline, None, objective=objective, constraints=constraints)['selected'] else None
        stagnant_rounds = 0
        active_trial_id = 'baseline'
        if baseline['status'] != 'collected':
            search['stop_reason'] = 'baseline-measurement-failed'
        elif evaluation is None and not token_agreement(baseline['quality'], baseline['self_check'])['passed']:
            search['stop_reason'] = 'unstable-reference'
            best = None
        while search['stop_reason'] is None:
            remaining = budget.max_candidate_trials - search['trials_used']
            if not remaining:
                search['stop_reason'] = 'budget-exhausted'
                break
            legal = remaining_candidates(initial, baseline_config, seen, workload, baseline)
            if not legal:
                search['stop_reason'] = 'no-legal-untested-candidate'
                break
            record = dict(round=len(search['rounds']) + 1, specialists=[], trial_ids=[])
            evidence = round_evidence(initial, search, report['search_trials'], remaining)
            search['rounds'].append(record)
            before_frontier = frontier_points()
            experiments = choose_experiments(agent, evidence, legal, record, remaining)
            for check in record['specialists']:
                if check['status'] == 'rejected':
                    report['rejected'].append(dict(stage='proposal-validation', round=record['round'],
                        role=check['role'], proposal=deepcopy(check.get('proposal')), error=check.get('error')))
            if record.get('arbiter_error'):
                report['rejected'].append(dict(stage='arbiter-validation', round=record['round'],
                                               error=record['arbiter_error']))
            save()
            if not experiments:
                if (not record.get('arbiter_error')
                        and record.get('arbiter', {}).get('ranked_proposal_ids') == []):
                    search['stop_reason'] = 'arbiter-declined'
                elif (record['specialists']
                      and all(check['status'] == 'abstained' for check in record['specialists'])):
                    search['stop_reason'] = 'specialists-abstained'
                else:
                    search['stop_reason'] = 'no-valid-selected-proposal'
                break
            for proposal, candidate, selection_reason in experiments:
                close_active()
                seen.add(candidate.config.config_hash)
                search['trials_used'] += 1
                trial_id = f"trial-{search['trials_used']}"
                record['trial_ids'].append(trial_id)
                active_trial_id = trial_id
                trial = dict(trial_id=trial_id, status='starting',
                             runtime=dict(configuration=candidate.config.model_dump(),
                                          model_id=report['model_id'], revision=report['model_revision']),
                             config_hash=candidate.config.config_hash, proposal=proposal.model_dump(),
                             selection_reason=selection_reason)
                report['search_trials'].append(trial)
                save()
                stage = 'constructor'
                try:
                    active = pipeline.SeraModel(artifact_dir=folder / trial_id, configuration=candidate.config,
                                                model_id=report['model_id'], revision=report['model_revision'])
                    trial['runtime'] = active.record
                    stage = 'startup'
                    active.start()
                    stage = 'measurement'
                    trial.update(pipeline.collect_trial(active, report['prompts'], trial_id, workload=workload))
                except CleanupError:
                    raise
                except Exception as error:
                    trial.update(status='measurement-failed' if stage == 'measurement' else 'startup-failed',
                                 failure_stage=stage, error=type(error).__name__)
                if evaluation is not None:
                    trial['task_quality'] = evaluate_quality(trial, report['prompts'], evaluation,
                        version=evaluation_version, floor=constraints.quality_floor)
                decision = select_candidate(baseline, trial, objective=objective, constraints=constraints)
                trial['decision'] = decision
                if decision['selected'] == 'candidate':
                    new_value = objective_value(trial, objective.priority)
                    old_value = objective_value(best, objective.priority) if best else None
                    improves_objective = (old_value is None or
                        (new_value > old_value if objective.priority == 'throughput' else new_value < old_value))
                    new_memory = objective_value(trial, 'memory')
                    old_memory = objective_value(best, 'memory') if best else None
                    breaks_tie = (new_value == old_value and new_memory is not None
                                  and (old_memory is None or new_memory < old_memory))
                    if improves_objective or breaks_tie:
                        best = trial
                feedback = dict(proposal=proposal.model_dump(), decision=decision,
                    objective=objective.model_dump(), candidate_tested=True,
                    candidate_status=trial['status'], baseline_metrics=baseline.get('reduced'),
                    candidate_metrics=trial.get('reduced'),
                    eligible_trial_ids=[trial_id if decision['selected'] == 'candidate' else
                                        ('baseline' if decision['selected'] else 'no-safe-configuration')])
                trial['review_evidence'] = feedback
                try:
                    review = agent.review(feedback)
                    trial['review_response'] = review.model_dump() if review is not None else None
                    if (review is None or review.selected_trial_id not in feedback['eligible_trial_ids']
                            or review.prediction_outcome == 'not-tested'):
                        raise ValueError('Review contradicts the executed trial or deterministic gate')
                    trial['review'] = review.model_dump()
                except Exception as error:
                    trial['review_error'] = type(error).__name__
                    report['rejected'].append(dict(stage='review-validation', trial_id=trial_id,
                                                   error=trial['review_error']))
                save()
            after_frontier = frontier_points()
            stagnant_rounds = stagnant_rounds + 1 if after_frontier == before_frontier else 0
            if stagnant_rounds >= 2:
                search['stop_reason'] = 'two-rounds-without-frontier-improvement'
        if best is None:
            close_active()
            report.update(status='no-safe-configuration', returned_runner_closed=True,
                          decision=dict(selected=None, outcome='no-safe-configuration', reason=search['stop_reason']))
        else:
            selected_id = best['trial_id']
            if active_trial_id != selected_id:
                close_active()
                config = RuntimeConfig.model_validate(best['runtime']['configuration'])
                active = pipeline.SeraModel(artifact_dir=folder / 'returned-best', configuration=config,
                                            model_id=report['model_id'], revision=report['model_revision'])
                active.start()
            active._require_ready()
            result.models = [active]
            outcome = best.get('decision', {}).get('outcome', 'no-safe-improvement')
            report.update(status='ready', returned_runner_closed=False,
                task_quality_verified=evaluation is not None,
                decision=dict(selected=selected_id, outcome=outcome, reason=search['stop_reason']))
        save()
        return result
    except BaseException as error:
        report.update(status='failed', error=type(error).__name__)
        result.models = []
        try:
            close_active()
            report['returned_runner_closed'] = True
        except BaseException as cleanup_error:
            report.update(cleanup_error=type(cleanup_error).__name__, returned_runner_closed=False)
            raise
        finally:
            try:
                save()
            except BaseException as save_error:
                # Cleanup must run even when persistence fails. Keep the original
                # controller/cleanup exception instead of replacing it with this one.
                report['save_error'] = type(save_error).__name__
        raise
