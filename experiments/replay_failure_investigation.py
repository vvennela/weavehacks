"""Replay saved failures through real agents and Weave. Never run GPU inference.

python -m experiments.replay_failure_investigation --source-dir PATH --project ENTITY/PROJECT \
    --output-dir NEW_PATH --provider-check CERTIFICATE
"""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

from benchmarks.grade import SYSTEM_PROMPT, dataset_hash, load_cases
from experiments.run_investigation import TracedInvestigationAgent, traced_evidence_reader, weave_event_sink
from experiments.weave_evidence import WeaveEvidenceReader
from sera.agent import WandbAgent
from sera.config import Constraints, LARGE_MODEL_ID, LARGE_MODEL_REVISION, Objective, RuntimeConfig, Workload
from sera.diagnosis import export_trial_diagnosis, trial_diagnosis
from sera.investigation import remaining_candidates, round_evidence
from sera.pipeline import agent_evidence
from sera.provider_check import require_provider_check
from sera.runtime import classify_startup_failure
from sera.storage import content_hash, save_json
from sera.swarm import choose_swarm_experiments
from sera.tracing import use_event_sink


CASES_PATH = Path(__file__).resolve().parents[1]/'benchmarks'/'easy_cases.json'
SOURCE_FILES = ('result.json', 'weave-calls.json', 'trial-1/server.log')


def file_hashes(folder):
    return {name: hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def load_source(folder):
    """Validate the exact saved scenario before imports or calls to Weave."""
    folder = Path(folder).resolve()
    hashes = file_hashes(folder)
    report = json.loads((folder/'result.json').read_text())
    dump = json.loads((folder/'weave-calls.json').read_text())
    cases = load_cases(CASES_PATH)
    prompts = [[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': case['prompt']}]
               for case in cases]
    if (report['model_id'] != LARGE_MODEL_ID or report['model_revision'] != LARGE_MODEL_REVISION
            or report['evaluation_cases'] != cases or report['evaluation_cases_sha256'] != dataset_hash(cases)
            or report['prompts'] != prompts or report['constraints']['quality_floor'] != .99
            or report['evaluation']['version'] != 'sera-easy-strict-json-v1'):
        raise ValueError('Replay requires the unchanged pinned model, eight tasks, and .99 gate')
    base = RuntimeConfig(quantization='fp8_per_tensor')
    trials = deepcopy(report['search_trials'])
    expected = [base, base.model_copy(update={'max_model_len': 256}),
                base.model_copy(update={'max_num_batched_tokens': 2048})]
    selected = [report['baseline'], *trials]
    if len(selected) != 3:
        raise ValueError('Replay requires baseline and exactly two saved trials')
    for trial, config, name in zip(selected, expected, ('baseline', 'trial-1', 'trial-2')):
        if (trial['trial_id'] != name or trial['config_hash'] != config.config_hash
                or RuntimeConfig.model_validate(trial['runtime']['configuration']) != config):
            raise ValueError('Saved trial configuration does not match the bounded replay')
    if trials[0]['status'] != 'startup-failed' or trials[1]['status'] != 'collected':
        raise ValueError('Replay requires the saved startup failure and measured batch trial')
    calls = []
    for call in dump['calls']:
        name = call.get('op_name', '').rsplit('/op/', 1)[-1].split(':')[0]
        payload = call.get('output')
        if name not in ('recorded_model_request', 'recorded_trial_metrics') or not isinstance(payload, dict):
            continue
        if name == 'recorded_model_request' and payload.get('phase') not in ('warmup','measured','quality','self_check'):
            continue  # A later returned-runner probe must not enter the baseline's replay history.
        trial = next((t for t in (selected[0], selected[2]) if t['trial_id'] == payload.get('trial_id')), None)
        if trial is None:
            continue
        if (call['trace_id'] != dump['trace_id'] or call.get('exception') or not call.get('ended_at')
                or payload.get('model_id') != LARGE_MODEL_ID or payload.get('revision') != LARGE_MODEL_REVISION
                or payload.get('config_hash') != trial['config_hash']):
            raise ValueError('Saved request has mismatched source identity or incomplete export')
        calls.append(deepcopy(call) | {'recorded_op': name})
    scope = [dict(trial_id=t['trial_id'], model_id=LARGE_MODEL_ID, revision=LARGE_MODEL_REVISION,
                  config_hash=t['config_hash']) for t in (selected[0], selected[2])]
    WeaveEvidenceReader._check_visibility([dict(op_name=c['recorded_op'], output=c['output']) for c in calls], scope)
    trials[0]['runtime']['startup_failure'] = classify_startup_failure(folder/'trial-1')
    trials[0]['diagnosis'] = trial_diagnosis(report['baseline'], trials[0], trials[0]['decision'])
    return dict(folder=folder, hashes=hashes, report=report, trials=trials, calls=calls,
                source_trace_id=dump['trace_id'])


def run_replay(source, agent, client, weave, output_dir):
    folder = Path(output_dir).resolve()
    if folder.is_relative_to(source['folder']):
        raise ValueError('Replay output must be outside the immutable source directory')
    folder.mkdir(parents=True, exist_ok=False)
    call = weave.get_current_call()
    if call is None:
        raise ValueError('Replay must run inside its named Weave root')
    original = source['report']
    trace_id, url = json.loads(json.dumps([call.trace_id, call.ui_url]))
    report = dict(mode='saved-failure-replay', gpu_trials_executed=0, rounds=[], agent_calls=[],
        weave_url=url, trace_id=trace_id, source_trace_id=source['source_trace_id'],
        source_file_hashes=source['hashes'], mechanical_passed=False, factual_reasoning_verified=False,
        reasoning_review='Read saved reasons against cited evidence; factual prose is not automatically graded.',
        limits='Previously recorded measurements are revealed, never executed for a new proposal.')
    sink = weave_event_sink(weave)
    provenance = dict(source_trace_id=source['source_trace_id'], source_file_hashes=source['hashes'],
                      replay=True, new_gpu_measurement=False)
    def replay_sink(name, payload):
        sink(name, deepcopy(payload) | {'replay_source': provenance |
            {'derivation': ('Copied verdict; startup signature enriched from hashed server.log'
                            if payload['trial_id']=='trial-1' else 'Saved trial-2 diagnosis; no new measurement')}})
    def publish(trial_id):
        for record in source['calls']:
            if record['output']['trial_id'] == trial_id:
                sink(record['recorded_op'], deepcopy(record['output']) | {'replay_source': provenance |
                    dict(source_call_id=record['id'], source_output_sha256=content_hash(record['output']),
                         derivation='Exact saved output payload; only replay_source was added')})
    wrapped = TracedInvestigationAgent(agent, weave)
    reader = traced_evidence_reader(weave, WeaveEvidenceReader(client, trace_id,
        evaluation_cases=original['evaluation_cases']))
    initial = agent_evidence(original['baseline'], Objective.model_validate(original['objective']),
        Constraints.model_validate(original['constraints']), prompts=original['prompts'])
    initial.update(supported_changes={'max_num_batched_tokens': [2048]}, replay_source=provenance)
    initial['failure_interpretation'] = (
        'Trial-1 failed during startup: there is NO quality or latency measurement. '
        'Its missing-output gate zeros are not 0/8 model accuracy. Use the persisted CUTLASS '
        'signature as the observed error, not proof of OOM or an established root cause.')
    base = RuntimeConfig.model_validate(original['baseline_configuration'])
    try:
        publish('baseline')
        with use_event_sink(replay_sink):
            for index, remaining in enumerate((1, 0)):
                trial = source['trials'][index]
                if index:
                    publish(trial['trial_id'])
                save_json(folder/f'revealed-{trial["trial_id"]}.json', trial)
                export_trial_diagnosis(trial)
                save_json(folder/f'revealed-{trial["trial_id"]}.json', trial)
                if trial.get('diagnosis_trace_export', {}).get('status') != 'complete':
                    raise RuntimeError('Replay diagnosis export failed')
                visible = source['trials'][:index+1]
                supplied = round_evidence(initial, {'rounds':report['rounds']}, visible, remaining,
                                          prompts=original['prompts'])
                supplied['replay_revelation'] = dict(new_gpu_measurement=False,
                    revealed_saved_trial_ids=[t['trial_id'] for t in visible],
                    note=('Saved trial-2 is independent historical evidence, not execution of a replay proposal.'
                          if index else 'Only revealed saved evidence is available; replay executes no GPU trial.'))
                seen = {base.config_hash, *(t['config_hash'] for t in visible)}
                legal = remaining_candidates(supplied, base, seen,
                    Workload(concurrency=original['workload']['concurrency']), original['baseline']) if remaining else []
                record = dict(round=index+1, specialists=[], trial_ids=[], revealed_trial_ids=[trial['trial_id']])
                report['rounds'].append(record)
                chosen = choose_swarm_experiments(wrapped, supplied, legal, record, remaining, reader)
                record['proposed_config_hashes'] = [candidate.config.config_hash for _, candidate, _ in chosen]
                report['agent_calls'] = deepcopy(wrapped.history)
                save_json(folder/'result.json', report)
        report['criteria'] = dict(all_investigators_read=all(len(r['specialists']) == 3 and
            all(c.get('successful_inspections',0)>0 for c in r['specialists']) for r in report['rounds']),
            round_one_proposal=bool(report['rounds'][0]['proposed_config_hashes']),
            round_two_abstention=all(c['status']=='abstained' for c in report['rounds'][1]['specialists']),
            no_trace_errors=not getattr(wrapped,'trace_failures',[]),
            source_unchanged=file_hashes(source['folder'])==source['hashes'])
        report['mechanical_passed'] = all(report['criteria'].values())
    except Exception as error:
        report['error_type'] = type(error).__name__
        raise
    finally:
        report['agent_calls'] = deepcopy(wrapped.history)
        report['trace_failures'] = deepcopy(getattr(wrapped,'trace_failures',[]))
        report['source_unchanged'] = file_hashes(source['folder']) == source['hashes']
        save_json(folder/'result.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-dir','project','output-dir','provider-check'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args(argv)
    try:
        source = load_source(args.source_dir)
        if not args.project.strip():
            raise ValueError('Project must be nonempty')
        folder = Path(args.output_dir).resolve()
        if folder.exists() or folder.is_relative_to(source['folder']):
            raise ValueError('Use a new output directory outside the source')
        agent = WandbAgent(project=args.project)
        certificate = require_provider_check(args.provider_check, agent)
        if not os.environ.get('WANDB_API_KEY'):
            raise ValueError('WANDB_API_KEY must be set')
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    import weave  # Optional service dependency; never imported by offline tests or on module import.
    client = weave.init(args.project)
    report = None
    try:
        @weave.op(name='replay_failure_investigation')
        def replay_failure_investigation():
            return run_replay(source, agent, client, weave, folder)
        report = replay_failure_investigation()
    except Exception as error:
        report = (json.loads((folder/'result.json').read_text()) if (folder/'result.json').exists()
                  else {'mechanical_passed':False})
        report.update(mechanical_passed=False,error_type=type(error).__name__)
    finally:
        try:
            client.flush()
        except Exception as error:
            if report is not None:
                report.update(mechanical_passed=False, flush_error=type(error).__name__)
        finally:
            if report is not None:
                report['provider_validation'] = certificate
                save_json(folder/'result.json', report)
    print(json.dumps({'weave_url':report.get('weave_url'), 'criteria':report.get('criteria'),
                      'error_type':report.get('error_type'), 'mechanical_passed':report['mechanical_passed'],
                      'factual_reasoning_verified':False}, indent=2))
    return 0 if report['mechanical_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
