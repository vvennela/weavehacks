"""Read-only checks for one live Codex fit-first run with a total two-trial budget."""

import argparse
from collections import Counter
import json
from pathlib import Path

from benchmarks.grade import dataset_hash, grade_case, load_cases
from experiments.verify_swarm import Audit
from sera.config import Constraints, LARGE_MODEL_ID, LARGE_MODEL_REVISION, Objective
from sera.fit import fit_review_evidence
from sera.measurement import select_candidate
from sera.quality import evaluate_quality
from sera.storage import content_hash


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_run(folder, calls_path, model, controller_path):
    folder = Path(folder)
    report = json.loads((folder / 'result.json').read_text())
    invocation = json.loads((folder / 'invocation.json').read_text())
    require(invocation.get('agent_provider') == 'codex-relay',
            'Run is not a live codex-relay invocation')
    require(model in {'gpt-6-astra', 'gpt-5.6-luna'} and invocation.get('agent_model') == model,
            'Investigator model does not match the requested audit')
    require(invocation.get('fit_first') is True and invocation.get('swarm') is True,
            'Run must enable both fit-first and swarm')
    require(invocation.get('passed') is True and not invocation.get('trace_export_failures'),
            'Invocation did not finish with a passing return and complete tracing')
    calls = json.loads(Path(calls_path).read_text())
    audit = Audit(report, calls)
    require(report['model_id'] == LARGE_MODEL_ID and report['model_revision'] == LARGE_MODEL_REVISION,
            'Run does not use the pinned Qwen72B model')
    require(report['trace_status'] == 'enabled' and report['swarm_enabled'] is True
            and report['status'] == 'ready', 'Run is not a ready, traced swarm result')
    require(report['constraints']['quality_floor'] == .99
            and report['objective'] == {'priority': 'latency', 'min_improvement_fraction': .05}
            and report['workload']['concurrency'] == [1, 2, 4, 8], 'Workload or gates changed')
    cases = load_cases(Path(__file__).resolve().parents[1] / 'benchmarks/easy_cases.json')
    require(len(cases) == 8 and report['evaluation_cases'] == cases
            and report['evaluation_cases_sha256'] == dataset_hash(cases), 'Task cases changed')
    by_prompt = {case['prompt']: case for case in cases}

    def score(prompt, text):
        return grade_case(by_prompt[prompt[-1]['content']], text)['passed']

    objective = Objective.model_validate(report['objective'])
    constraints = Constraints.model_validate(report['constraints'])
    deployment = report['deployment']
    trial = deployment['candidate_trial']
    baseline = report['baseline']
    require(deployment['infeasible_baseline']['status'] == 'infeasible'
            and deployment['infeasible_baseline']['fit_estimate']['estimated_fit'] is False,
            'BF16 reference must be explicitly estimated infeasible')
    require(deployment['planning_specialist']['status'] == 'accepted'
            and deployment['planning_specialist']['response']['ranked_proposal_ids'] == ['weight-fp8']
            and deployment['planning_decision']['ranked_proposal_ids'] == ['weight-fp8'],
            'Advisor and arbiter did not both select FP8 deployment')
    require(trial['status'] == 'collected', 'Quantized deployment was not measured')
    config = trial['runtime']['configuration']
    require(config['quantization'] == 'fp8_per_tensor' and config['kv_cache_dtype'] == 'auto'
            and config['max_num_batched_tokens'] == 4096 and config['max_model_len'] == 4096
            and config['max_num_seqs'] == 8 and config['tensor_parallel_size'] == 1
            and config['gpu_memory_utilization'] == .9, 'Deployment configuration changed')
    require(trial['config_hash'] == content_hash(config), 'Deployment configuration hash mismatch')
    command = trial['runtime']['command']
    require('--quantization' in command
            and command[command.index('--quantization') + 1] == 'fp8_per_tensor'
            and trial['runtime']['sampled_peak_memory_mib'] > 0,
            'Missing quantized GPU launch evidence')
    require([load['concurrency'] for load in trial['loads']] == [1, 2, 4, 8]
            and all(len(load['requests']) == 24 for load in trial['loads']),
            'Deployment measured loads do not match the fixed workload')
    quality = evaluate_quality(trial, report['prompts'], score,
                               version='sera-easy-strict-json-v1', floor=.99)
    require(quality == trial['task_quality'] and quality['passed'] is True,
            'Deployment quality does not independently pass')
    require(baseline['trial_id'] == 'baseline' and baseline['source_trial_id'] == trial['trial_id']
            and all(baseline[key] == trial[key] for key in ('config_hash', 'reduced', 'task_quality'))
            and baseline['runtime']['configuration'] == config,
            'Promoted reference differs from the measured deployment')
    require(deployment['decision'] == select_candidate(deployment['infeasible_baseline'], trial,
            objective=objective, constraints=constraints)
            and deployment['decision']['selected'] == 'candidate', 'Deployment gate mismatch')
    feedback = fit_review_evidence(deployment['agent_feedback']['fit_plan'], trial,
                                  deployment['decision']) | {'diagnosis': trial['diagnosis']}
    require(feedback == deployment['agent_feedback']
            and deployment['agent_final']['selected_trial_id'] == 'candidate'
            and deployment['agent_final']['prediction_outcome'] == 'confirmed'
            and not deployment.get('agent_final_error'), 'Deployment review mismatch')

    audit.lineage()
    require(len(audit.matching_calls('fit_quantization_advisor',
            deployment['planning_specialist']['evidence'],
            deployment['planning_specialist']['response'])) == 1,
            'Missing matching traced quantization advisor call')
    require(len(audit.matching_calls('frontier_reviewer', feedback, deployment['agent_final'])) == 1,
            'Missing matching traced deployment review')
    planning_calls = [entry for entry in report['agent_calls']
                      if entry['role'] == 'arbiter' and 'fit_plan' in entry['evidence']
                      and 'specialist_role' not in entry['evidence']]
    require(len(planning_calls) == 1 and len(audit.matching_calls('arbiter',
            planning_calls[0]['evidence'], deployment['planning_decision'])) == 1,
            'Missing matching traced deployment arbiter')

    search = report['search']
    rounds = search['rounds']
    trials = {item['trial_id']: item for item in report['search_trials']}
    require(search['budget']['max_candidate_trials'] == 2 and search['initial_trials_used'] == 1
            and search['trials_used'] == 1 + len(trials) <= 2
            and len(trials) == len(report['search_trials']) and len(rounds) == 1,
            'Two-trial total budget or one post-deployment swarm round mismatch')
    scope = {(baseline['source_trial_id'], LARGE_MODEL_ID, LARGE_MODEL_REVISION, baseline['config_hash'])}
    audit.round(rounds[0], scope)
    for candidate in trials.values():
        changed = {key: value for key, value in candidate['runtime']['configuration'].items()
                   if value != config[key]}
        require(candidate['trial_id'] == 'trial-2' and changed in
                ({'max_num_batched_tokens': 2048}, {'max_num_batched_tokens': 1024}),
                'Search trial changes something outside the approved batch-token values')
        require(candidate['task_quality'] == evaluate_quality(candidate, report['prompts'], score,
                version='sera-easy-strict-json-v1', floor=.99), 'Search quality recomputation differs')
        require(candidate['decision'] == select_candidate(baseline, candidate,
                objective=objective, constraints=constraints), 'Search deterministic gate mismatch')
        review, evidence = candidate['review'], candidate['review_evidence']
        require(not candidate.get('review_error')
                and evidence['candidate_metrics'] == candidate.get('reduced')
                and evidence['candidate_status'] == candidate['status']
                and evidence['diagnosis'] == candidate['diagnosis']
                and review['selected_trial_id'] in evidence['eligible_trial_ids']
                and review['prediction_outcome'] in evidence['allowed_prediction_outcomes']
                and len(audit.matching_calls('frontier_reviewer', evidence, review)) == 1,
                'Final review does not match the actual search outcome and traced evidence')
        expected = 'trial-2' if candidate['decision']['selected'] == 'candidate' else 'baseline'
        require(report['decision']['selected'] == expected, 'Returned selection violates measured gates')
    if trials:
        audit.trials(rounds, trials)
        audit.diagnoses(rounds, trials)
    else:
        require(report['decision']['selected'] == 'baseline' and search['stop_reason'] in
                {'arbiter-declined', 'specialists-abstained'}, 'Invalid no-trial stop or returned selection')

    # A matching CLI invocation and completed output bind more than a copied model label.
    from experiments.codex_relay_controller import response_envelope
    completed = Counter()
    for path in Path(controller_path).glob('*/response.json'):
        directory = path.parent
        request = json.loads((directory / 'request.json').read_text())
        cli = json.loads((directory / 'invocation.json').read_text())
        events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines() if line]
        final = (directory / 'final.txt').read_text()
        require(request['model'] == cli['model'] == model and '--model' in cli['command']
                and cli['command'][cli['command'].index('--model') + 1] == model,
                'Local CLI investigator model mismatch')
        require(json.loads(path.read_text()) == response_envelope(model, final, events),
                'CLI response differs from completed events or verbatim final output')
        completed[(content_hash(request['payload']['messages']), final)] += 1
    for entry in report['agent_calls']:
        require(entry['provider'] == 'codex-relay' and entry['model'] == model,
                'Recorded investigator model or provider mismatch')
        for attempt in entry['attempts']:
            body = attempt.get('raw_response')
            if body is None:
                continue
            require(body['model'] == model and body['provider'] == 'codex-relay'
                    and body['synthetic'] is True and body['transport'] == 'codex-cli',
                    'Missing explicit Codex relay response identity')
            key = (content_hash(entry['messages']), body['choices'][0]['message']['content'])
            require(completed[key] > 0, 'Recorded response lacks matching completed CLI evidence')
            completed[key] -= 1

    audit.returned()
    require(grade_case(cases[0], report['post_return_probe']['text'])['passed'],
            'Returned runner probe fails independent grading')
    require(not audit.issues, json.dumps(audit.issues))
    return {'accepted': True, 'investigator': model, 'deployment_measured': True,
            'swarm_rounds': len(rounds), 'batching_trial_attempted': bool(trials),
            'full_bounded_loop_exercised': bool(trials),
            'returned_configuration': report['decision']['selected'], 'weave_url': report['weave_url'],
            'limits': ['No measured BF16 comparison or multi-GPU claim.',
                       'One post-deployment swarm round, not two.',
                       'CLI model selection verified; no independent backend attestation.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    parser.add_argument('calls', type=Path)
    parser.add_argument('model', choices=['gpt-6-astra', 'gpt-5.6-luna'])
    parser.add_argument('controller_dir', type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit_run(args.run_dir, args.calls, args.model, args.controller_dir)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        result = {'accepted': False, 'error_type': type(error).__name__, 'error': str(error)}
    print(json.dumps(result, indent=2))
    return 0 if result['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
