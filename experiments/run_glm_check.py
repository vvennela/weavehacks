"""Check one pinned GLM precision path; no search or joint-placement claim."""

import argparse
from pathlib import Path

import sera
from benchmarks.grade import SYSTEM_PROMPT, grade_case, load_cases
from sera.config import GLM_MODEL_ID, GLM_MODEL_REVISION
from sera.measurement import collect_trial
from sera.quality import evaluate_quality
from sera.storage import save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--quantization', choices=['fp8_per_tensor'])
    parser.add_argument('--kv-cache-dtype', choices=['auto', 'fp8'], default='auto')
    args = parser.parse_args()
    import weave

    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=False)
    cases = load_cases(Path(__file__).resolve().parents[1]/'benchmarks'/'easy_cases.json')
    prompts = [[{'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': case['prompt']}] for case in cases]
    by_prompt = {case['prompt']: case for case in cases}

    def evaluate(prompt, output):
        return grade_case(by_prompt[prompt[-1]['content']], output)['passed']

    client = weave.init(args.project)

    @weave.op
    def check():
        report = {'status': 'running', 'mode': 'isolated-compatibility-and-task-check',
                  'model_id': GLM_MODEL_ID, 'model_revision': GLM_MODEL_REVISION,
                  'evaluation_cases': cases, 'prompts': prompts,
                  'weave_url': weave.get_current_call().ui_url}
        model = sera.SeraModel(artifact_dir=folder/'runtime', model_id=GLM_MODEL_ID,
                               revision=GLM_MODEL_REVISION,
                               configuration=sera.RuntimeConfig(quantization=args.quantization,
                                   kv_cache_dtype=args.kv_cache_dtype))
        save_json(folder/'result.json', report)
        try:
            model.start()
            trial = collect_trial(model, prompts, 'glm-check')
            trial['task_quality'] = evaluate_quality(trial, prompts, evaluate,
                version='sera-easy-strict-json-v1', floor=.99)
            report['trial'] = trial
            report['status'] = ('pass' if trial['status'] == 'collected'
                                and trial['task_quality']['passed'] else 'fail')
        except Exception as error:
            report.update(status='fail', error=f'{type(error).__name__}: {error}')
        finally:
            try:
                model.close()
            finally:
                report['runtime'] = model.record
                if not model.record.get('cleanup_pass'):
                    report['status'] = 'fail'
                save_json(folder/'result.json', report)
        return report

    try:
        report = check()
    finally:
        client.flush()
    print(report['status'])
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
