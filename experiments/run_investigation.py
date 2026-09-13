"""Run one explicitly bounded, live single-model agent investigation.

Run from the repository root with python -m experiments.run_investigation.
This command uses GPU time. Importing the module does not run an experiment.
Declare controls explicitly or opt in to a post-baseline pool with --auto-space.
FP8 KV is opt-in for Qwen3-0.6B only;
Qwen72B uses FP8 weights, so its combined FP8 weights/KV path stays disabled.
"""

import argparse
import os
from pathlib import Path
import sys

import sera
from sera.agent import AGENT_MODEL
from benchmarks.grade import SYSTEM_PROMPT, dataset_hash, grade_case, load_cases
from experiments.weave_evidence import QUERY_IDS, RECORDED_OPS, WeaveEvidenceReader
from sera.config import LARGE_MODEL_ID, MODEL_ID, resolve_investigation_space
from sera.provider_check import require_provider_check
from sera.storage import save_json
from sera.tracing import TraceSinkError, recorded_model_request, use_event_sink


CASES_PATH = Path(__file__).resolve().parents[1]/'benchmarks'/'easy_cases.json'


from sera.weave_integration import (TracedInvestigationAgent, weave_event_sink,
                                    traced_evidence_reader, trial_trace_failures)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, choices=[MODEL_ID, LARGE_MODEL_ID])
    stopping = parser.add_mutually_exclusive_group(required=True)
    stopping.add_argument('--budget', type=int,
                        help='Maximum candidate trials, 1 to 8; includes deployment with --fit-first')
    stopping.add_argument('--until-plateau', action='store_true',
                         help='No total trial cap; stop after an objective plateau and one confirmation round')
    parser.add_argument('--fit-first', action='store_true',
                        help='Qwen72B only: first measure FP8 deployment, then investigate within the same budget')
    parser.add_argument('--auto-space', action='store_true',
                        help='Build the bounded candidate pool after baseline measurement; conflicts with explicit controls')
    parser.add_argument('--swarm', action='store_true',
                        help='Use isolated investigators and read persisted Weave evidence; requires tracing')
    parser.add_argument('--batching-values', type=int, nargs='+',
                        help='Explicit candidate max_num_batched_tokens values; baseline is 4096')
    parser.add_argument('--sequence-values', type=int, nargs='+',
                        help='Explicit candidate max_num_seqs values; baseline is 8')
    parser.add_argument('--context-values', type=int, nargs='+',
                        help='Explicit candidate max_model_len values; baseline is 4096')
    parser.add_argument('--fp8-kv', action='store_true',
                        help='Include the FP8 KV candidate for the small Qwen BF16 baseline')
    parser.add_argument('--project', required=True)
    parser.add_argument('--agent-model', default=AGENT_MODEL,
                        help='Hosted investigator model; must match the provider certificate')
    parser.add_argument('--agent-provider', choices=['wandb', 'codex-relay'], default='wandb')
    parser.add_argument('--relay-dir', help='Shared request directory for the local Codex controller')
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
        if (args.agent_provider == 'codex-relay') != bool(args.relay_dir):
            raise ValueError('--relay-dir is required only with --agent-provider codex-relay')
        if args.swarm and args.no_weave:
            raise ValueError('--swarm requires Weave; remove --no-weave')
        if args.fit_first and args.model != LARGE_MODEL_ID:
            raise ValueError('--fit-first is supported only for Qwen72B')
        budget = sera.Budget(max_candidate_trials=None if args.until_plateau else args.budget)
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
        if args.auto_space and changes:
            raise ValueError('--auto-space cannot be combined with explicit candidate controls')
        space = None if args.auto_space else sera.InvestigationSpace(supported_changes=changes)
        frozen_space = (None if args.auto_space else resolve_investigation_space(
            space, baseline=reference, model_id=args.model, workload=workload))
        cases = load_cases(CASES_PATH)
        if args.agent_provider == 'codex-relay':
            from sera.relay import RelayAgent
            agent = RelayAgent(project=args.project, model=args.agent_model, relay_dir=args.relay_dir)
        else:
            agent = sera.WandbAgent(project=args.project, model=args.agent_model)
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
                  'agent_provider': args.agent_provider, 'agent_model': args.agent_model,
                  'model_id': args.model, 'budget': budget.model_dump(),
                  'fit_first': args.fit_first,
                  'automatic_space': args.auto_space,
                  'swarm': args.swarm,
                  'objective': objective.model_dump(), 'workload': workload.model_dump(),
                  'investigation_space': frozen_space, 'provider_validation': certificate,
                  'evaluation_cases_sha256': dataset_hash(cases),
                  'weave_url': None, 'returned_runner_closed': False,
                  'limits': 'A live investigation is not proof of search superiority.'}
    client = None
    weave = None
    sink = None

    def run_investigation():
        result = None
        try:
            trace_reader = None
            if weave is not None:
                call = weave.get_current_call()
                invocation['weave_url'] = call.ui_url if call is not None else None
                if args.swarm:
                    trace_reader = traced_evidence_reader(weave, WeaveEvidenceReader(
                        client, call.trace_id if call is not None else None, evaluation_cases=cases))
            result = sera.optimize(models=[args.model], prompts=prompts, output_dir=folder,
                evaluation=evaluate_answer, evaluation_version='sera-easy-strict-json-v1',
                constraints=sera.Constraints(quality_floor=.99), objective=objective,
                workload=workload, baseline_configuration=baseline, budget=budget,
                investigation_space=space, automatic_space=args.auto_space,
                swarm=args.swarm, trace_reader=trace_reader,
                agent=agent, provider_check=args.provider_check)
            result.report.update(workload_name='easy-json-system-v1', evaluation_cases=cases,
                evaluation_cases_sha256=dataset_hash(cases), weave_url=invocation['weave_url'],
                trace_status='disabled-explicitly' if args.no_weave else 'enabled',
                post_return_task_passed=False)
            failures = trial_trace_failures(result.report)
            if isinstance(agent, TracedInvestigationAgent):
                failures.extend(agent.trace_failures)
            if result.models:
                runner = result.models[0]
                response = runner.generate(prompts[0])
                result.report['post_return_probe'] = response.to_dict()
                result.report['post_return_task_passed'] = evaluate_answer(prompts[0], response.text)
                result._save()
                if weave is not None:
                    try:
                        recorded_model_request(trial_id=(result.report.get('decision') or {}).get('selected'),
                            model_id=runner.model_id, revision=runner.revision,
                            config_hash=runner.configuration.config_hash, phase='post-return-probe',
                            concurrency=1, prompt_index=0, prompt=prompts[0], response=response.to_dict())
                    except TraceSinkError as error:
                        failures.append({'event': error.event_name, 'error_type': error.error_type})
            if failures:
                result.report['trace_status'] = 'failed'
            invocation.update(search=result.report.get('search'), trace_export_failures=failures,
                investigation_space=result.report.get('investigation_space', frozen_space),
                candidate_policy=result.report.get('candidate_policy'),
                passed=bool(result.report.get('task_quality_verified')
                            and result.report['post_return_task_passed'] and not failures))
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
            sink = weave_event_sink(weave)
            run_investigation = weave.op(run_investigation)
        with use_event_sink(sink):
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
