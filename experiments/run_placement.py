"""Rehearse the real placement API from a frozen manifest, without editing the demo.

`check` performs no GPU or provider calls. `references` measures only isolated
models. `search` runs the certified arbiter and real joint executor. No default
allocations are supplied. The eight questions and strict grader are unchanged.
"""

import argparse
import json
from pathlib import Path

from benchmarks.grade import BENCHMARK_VERSION, SYSTEM_PROMPT, dataset_hash, grade_case, load_cases
from sera import (Budget, Objective, PlacementMemoryEstimate, PlacementWorkload, Workload,
                  measure_placement_references, optimize_placement)
from sera.api import _configured_agent
from sera.placement_config import validate_placement_plan
from sera.storage import content_hash, save_json


DATASET_HASH = '2f3c6687cf2a19bde4c3f5b60ab56cb24ac67c6755e999ad98227b04e42d95a7'


def load_manifest(path):
    path = Path(path).resolve()
    manifest = json.loads(path.read_text())
    allowed = {'schema_version', 'plans', 'memory_estimates', 'isolated_references',
               'concurrency', 'provider_check', 'weave_project'}
    if set(manifest) - allowed or manifest.get('schema_version') != 'sera-placement-rehearsal-v1':
        raise ValueError('Use the explicit sera-placement-rehearsal-v1 manifest')
    plans = [validate_placement_plan(plan) for plan in manifest['plans']]
    if not plans or len({plan.plan_hash for plan in plans}) != len(plans):
        raise ValueError('Supply unique explicit plans')
    for plan in plans:
        for service in plan.services:
            limits = service.constraints
            if (limits.quality_floor != .99 or limits.max_p95_slowdown_fraction != .10
                    or limits.max_generation_errors != 0):
                raise ValueError('Rehearsal requires the approved 0.99 task floor, 10% slowdown, and zero errors')
    estimates = {plan_id:{model:PlacementMemoryEstimate.model_validate(value) for model,value in services.items()}
                 for plan_id,services in manifest['memory_estimates'].items()}
    if set(estimates) != {plan.plan_hash for plan in plans}:
        raise ValueError('Memory estimates must match the exact plan hashes')
    for plan in plans:
        if set(estimates[plan.plan_hash]) != {service.model_id for service in plan.services}:
            raise ValueError('Each plan requires both models\' explicit memory components')
    workload = Workload.model_validate({'concurrency':manifest['concurrency']})
    cases = load_cases(Path(__file__).resolve().parents[1]/'benchmarks/easy_cases.json')
    if dataset_hash(cases) != DATASET_HASH or len(cases) != 8:
        raise ValueError('The approved eight-question dataset changed')
    prompts = [[dict(role='system', content=SYSTEM_PROMPT), dict(role='user', content=case['prompt'])] for case in cases]
    by_prompt = {content_hash(prompt):case for prompt,case in zip(prompts, cases)}
    def evaluate(prompt, output):
        return grade_case(by_prompt[content_hash(prompt)], output)['passed']
    profiles = {service.model_id:PlacementWorkload(prompts, evaluate, BENCHMARK_VERSION, workload)
                for service in plans[0].services}
    def resolve(value):
        candidate = Path(value)
        return candidate if candidate.is_absolute() else path.parent/candidate
    references = {plan_id:resolve(value) for plan_id,value in manifest.get('isolated_references', {}).items()}
    certificate = resolve(manifest['provider_check']) if manifest.get('provider_check') else None
    return dict(manifest=manifest, plans=plans, workloads=profiles, memory_estimates=estimates,
                isolated_references=references, provider_check=certificate,
                weave_project=manifest.get('weave_project'), cases=cases)


def run_references(loaded, output_dir):
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    record = dict(schema_version='sera-placement-reference-index-v1', dataset_hash=DATASET_HASH,
                  manifest=loaded['manifest'], references={}, status='running')
    save_json(folder/'result.json', record)
    for plan in loaded['plans']:
        result = measure_placement_references(plan=plan, workloads=loaded['workloads'],
            memory_estimates=loaded['memory_estimates'][plan.plan_hash],
            output_dir=folder/plan.plan_hash, weave_project=loaded['weave_project'])
        if result.report['status'] != 'references-ready':
            record.update(status='blocked', failed_plan_id=plan.plan_hash, reason=result.report['decision'])
            save_json(folder/'result.json', record)
            return record
        record['references'][plan.plan_hash] = str(result.output_dir/'result.json')
        save_json(folder/'result.json', record)
    record['status'] = 'references-ready'
    save_json(folder/'result.json', record)
    return record


def run_search(loaded, output_dir, *, objective, budget):
    if loaded['provider_check'] is None:
        raise ValueError('Search requires a matching existing provider certificate')
    if set(loaded['isolated_references']) != {plan.plan_hash for plan in loaded['plans']}:
        raise ValueError('Search requires a saved isolated reference for each plan')
    result = optimize_placement(plans=loaded['plans'], workloads=loaded['workloads'],
        memory_estimates=loaded['memory_estimates'], isolated_references=loaded['isolated_references'],
        provider_check=loaded['provider_check'], agent=_configured_agent(), output_dir=output_dir,
        objective=objective, budget=budget, weave_project=loaded['weave_project'])
    probes = []
    with result:
        for model in result.models:
            prompt = loaded['workloads'][model.model_id].prompts[0]
            response = model.generate(prompt)
            probes.append(dict(model_id=model.model_id, scope='post-return request, first unchanged task',
                               response=response.to_dict(), grade=grade_case(loaded['cases'][0], response.text)))
        result.report['returned_runner_probes'] = probes
        result._save()
    result.report['rehearsal_passed'] = (len(probes) == 2 and all(probe['grade']['passed'] for probe in probes)
                                       and result.report['returned_runner_closed'])
    result._save()
    return result.report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--phase', choices=['check', 'references', 'search'], default='check')
    parser.add_argument('--output-dir')
    parser.add_argument('--objective', choices=['latency', 'throughput', 'memory'], default='latency')
    parser.add_argument('--max-candidate-trials', type=int)
    args = parser.parse_args(argv)
    loaded = load_manifest(args.manifest)
    if args.phase == 'check':
        print(json.dumps(dict(status='manifest-valid-not-live-tested', plans=len(loaded['plans']),
                              dataset_hash=DATASET_HASH, quality_floor=.99, slowdown_fraction=.10)))
        return 0
    if not args.output_dir:
        parser.error('--output-dir is required for GPU execution')
    if args.phase == 'references':
        record = run_references(loaded, args.output_dir)
        print(json.dumps(dict(status=record['status'], passing_references=len(record['references']))))
        return 0 if record['status'] == 'references-ready' else 1
    record = run_search(loaded, args.output_dir, objective=Objective(priority=args.objective),
                        budget=Budget(max_candidate_trials=args.max_candidate_trials))
    print(json.dumps({key:record.get(key) for key in ('status', 'stop_reason', 'selected_plan_id', 'rehearsal_passed')}))
    return 0 if record.get('rehearsal_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
