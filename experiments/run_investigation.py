"""Run one explicitly bounded, live single-model agent investigation.

Run from the repository root with python -m experiments.run_investigation.
This command uses GPU time. Importing the module does not run an experiment.
Declare at least one control explicitly. FP8 KV is opt-in for Qwen3-0.6B only;
Qwen72B uses FP8 weights, so its combined FP8 weights/KV path stays disabled.
"""

import argparse
import os
from pathlib import Path
import sys

import sera
from benchmarks.grade import SYSTEM_PROMPT, dataset_hash, grade_case, load_cases
from sera.config import LARGE_MODEL_ID, MODEL_ID, resolve_investigation_space
from sera.provider_check import require_provider_check
from sera.storage import save_json


CASES_PATH = Path(__file__).resolve().parents[1]/'benchmarks'/'easy_cases.json'


class TracedInvestigationAgent:
    """Experiment-local tracing; the underlying agent owns requests and raw history."""

    def __init__(self, agent, weave):
        self._agent = agent

        def traced_request(name):
            def request(role, evidence, instruction):
                return agent.request(role, evidence, instruction)
            return weave.op(name=name)(request)

        def review(evidence):
            # Its internal request must not re-enter this adapter.
            return agent.review(evidence)

        # Official op naming API: https://docs.wandb.ai/weave/guides/tracking/ops
        self._requests = {name: traced_request(name) for name in (
            'fit_quantization_advisor', 'quantization_specialist', 'batching_specialist',
            'search_specialist', 'arbiter', 'frontier_reviewer', 'agent_request')}
        self._review = weave.op(name='frontier_reviewer')(review)

    @property
    def model(self):
        return self._agent.model

    @property
    def project(self):
        return self._agent.project

    @property
    def history(self):
        return self._agent.history

    def request(self, role, evidence, instruction):
        specialist = evidence.get('specialist_role')
        if role == 'arbiter' and 'fit_plan' in evidence and specialist == 'quantization':
            name = 'fit_quantization_advisor'
        elif role == 'proposal':
            name = f'{specialist}_specialist' if specialist in {'quantization', 'batching'} else 'search_specialist'
        else:
            name = {'arbiter': 'arbiter', 'frontier': 'frontier_reviewer'}.get(role, 'agent_request')
        return self._requests[name](role, evidence, instruction)

    def review(self, evidence):
        return self._review(evidence)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, choices=[MODEL_ID, LARGE_MODEL_ID])
    parser.add_argument('--budget', required=True, type=int,
                        help='Maximum candidate trials, 1 to 8; includes deployment with --fit-first')
    parser.add_argument('--fit-first', action='store_true',
                        help='Qwen72B only: first measure FP8 deployment, then investigate within the same budget')
    parser.add_argument('--batching-values', type=int, nargs='+',
                        help='Explicit candidate max_num_batched_tokens values; baseline is 4096')
    parser.add_argument('--sequence-values', type=int, nargs='+',
                        help='Explicit candidate max_num_seqs values; baseline is 8')
    parser.add_argument('--context-values', type=int, nargs='+',
                        help='Explicit candidate max_model_len values; baseline is 4096')
    parser.add_argument('--fp8-kv', action='store_true',
                        help='Include the FP8 KV candidate for the small Qwen BF16 baseline')
    parser.add_argument('--project', required=True)
    parser.add_argument('--provider-check', required=True, help='Current passing 30-case certificate')
    parser.add_argument('--output-dir', required=True, help='A new evidence directory')
    parser.add_argument('--priority', choices=['latency', 'throughput', 'memory'], default='latency')
    parser.add_argument('--concurrency', type=int, nargs='+', default=[1])
    parser.add_argument('--no-weave', action='store_true', help='Save local evidence without a Weave trace')
    args = parser.parse_args(argv)

    # Validate the complete declared scope before tracing, directory creation, or GPU work.
    try:
        folder = Path(args.output_dir).resolve()
        if folder.exists():
            raise ValueError('output-dir must be a new directory')
        if not args.project.strip():
            raise ValueError('project must be nonempty')
        if args.fit_first and args.model != LARGE_MODEL_ID:
            raise ValueError('--fit-first is supported only for Qwen72B')
        budget = sera.Budget(max_candidate_trials=args.budget)
        workload = sera.Workload(concurrency=args.concurrency)
        objective = sera.Objective(priority=args.priority)
        reference = (sera.RuntimeConfig(quantization='fp8_per_tensor')
                     if args.model == LARGE_MODEL_ID else sera.RuntimeConfig())
        baseline = reference if args.model == LARGE_MODEL_ID and not args.fit_first else None
        changes = {lever: values for lever, values in (
            ('max_num_batched_tokens', args.batching_values), ('max_num_seqs', args.sequence_values),
            ('max_model_len', args.context_values)) if values is not None}
        if args.fp8_kv:
            changes['kv_cache_dtype'] = ['fp8']
        space = sera.InvestigationSpace(supported_changes=changes)
        frozen_space = resolve_investigation_space(space, baseline=reference,
                                                   model_id=args.model, workload=workload)
        cases = load_cases(CASES_PATH)
        agent = sera.WandbAgent(project=args.project)
        certificate = require_provider_check(args.provider_check, agent)
        if not os.environ.get('WANDB_API_KEY'):
            raise ValueError('WANDB_API_KEY must be set in this process')
    except (OSError, ValueError) as error:
        parser.error(str(error))

    prompts = [[{'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': case['prompt']}] for case in cases]
    by_prompt = {case['prompt']: case for case in cases}

    def evaluate_answer(prompt, output):
        return grade_case(by_prompt[prompt[-1]['content']], output)['passed']

    invocation = {'schema_version': 'sera-live-investigation-invocation-v1', 'passed': False,
                  'model_id': args.model, 'budget': budget.model_dump(),
                  'fit_first': args.fit_first,
                  'objective': objective.model_dump(), 'workload': workload.model_dump(),
                  'investigation_space': frozen_space, 'provider_validation': certificate,
                  'evaluation_cases_sha256': dataset_hash(cases),
                  'weave_url': None, 'returned_runner_closed': False,
                  'limits': 'A bounded live investigation is not proof of search superiority.'}
    client = None
    weave = None

    def run_investigation():
        result = None
        try:
            if weave is not None:
                call = weave.get_current_call()
                invocation['weave_url'] = call.ui_url if call is not None else None
            result = sera.optimize(models=[args.model], prompts=prompts, output_dir=folder,
                evaluation=evaluate_answer, evaluation_version='sera-easy-strict-json-v1',
                constraints=sera.Constraints(quality_floor=.99), objective=objective,
                workload=workload, baseline_configuration=baseline, budget=budget,
                investigation_space=space, agent=agent, provider_check=args.provider_check)
            result.report.update(workload_name='easy-json-system-v1', evaluation_cases=cases,
                evaluation_cases_sha256=dataset_hash(cases), weave_url=invocation['weave_url'],
                trace_status='disabled-explicitly' if args.no_weave else 'enabled',
                post_return_task_passed=False)
            if result.models:
                response = result.models[0].generate(prompts[0])
                result.report['post_return_probe'] = response.to_dict()
                result.report['post_return_task_passed'] = evaluate_answer(prompts[0], response.text)
            invocation.update(search=result.report.get('search'),
                passed=bool(result.report.get('task_quality_verified')
                            and result.report['post_return_task_passed']))
            result._save()
            result.print_summary()
        finally:
            if result is not None:
                try:
                    result.close()
                    invocation['returned_runner_closed'] = result.report.get('returned_runner_closed', False)
                except BaseException as error:
                    invocation.update(passed=False, cleanup_error=type(error).__name__)
                    raise
        return result.report

    try:
        if not args.no_weave:
            import weave
            client = weave.init(args.project)
            agent = TracedInvestigationAgent(agent, weave)
            run_investigation = weave.op(run_investigation)
        run_investigation()
    except Exception as error:
        invocation.update(passed=False, error=type(error).__name__)
        print(f'Investigation failed: {type(error).__name__}. Inspect saved evidence.', file=sys.stderr)
    finally:
        if client is not None:
            try:
                client.flush()
            except Exception as error:
                invocation.update(passed=False, trace_flush_error=type(error).__name__)
                print(f'Trace flush failed: {type(error).__name__}.', file=sys.stderr)
        if folder.is_dir():
            save_json(folder/'invocation.json', invocation)
    return 0 if invocation['passed'] and invocation['returned_runner_closed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
