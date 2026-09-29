"""Operator-only, traced compatibility check of an already exported MLX model.

This does not search for recipes, select a winner, or establish general quality.
It repeats the existing eight easy tasks using their requested JSON types.
"""

import argparse
import os
from pathlib import Path

from benchmarks.grade import SYSTEM_PROMPT, dataset_hash, grade_case, load_cases
from sera.model_artifact import verify_artifact
from sera.native_trace import trace_native_job
from sera.native_worker import run_native_job
from sera.storage import save_json


def requested_formats(cases):
    types = {
        'easy-01-add': {'type': 'integer'},
        'easy-02-larger': {'type': 'integer'},
        'easy-03-length': {'type': 'integer'},
        'easy-04-index': {'type': 'integer'},
        'easy-05-increment': {'type': 'integer'},
        'easy-06-copy': {'type': 'integer'},
        'easy-07-filter': {'type': 'array', 'items': {'type': 'string'}},
        'easy-08-upper': {'type': 'string'},
    }
    if set(types) != {case['id'] for case in cases}:
        raise ValueError('This smoke check requires the unchanged eight easy cases')
    return [{'type': 'json_schema', 'json_schema': {'name': 'answer', 'schema': {
        'type': 'object', 'properties': {'answer': types[case['id']]},
        'required': ['answer'], 'additionalProperties': False}}} for case in cases]


def check(*, artifact, output_dir, timeout_seconds, project):
    artifact = Path(artifact).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError('Use a new output directory; failed runs are retained')
    manifest = verify_artifact(artifact, backend='mlx')
    cases = load_cases(Path(__file__).resolve().parents[1] / 'benchmarks' / 'easy_cases.json')
    job = {'operation': 'measure', 'backend': 'mlx', 'artifact': str(artifact),
           'artifact_id': manifest['artifact_id'], 'max_tokens': 64, 'seed': 0,
           'warmup': 1, 'repetitions': 3, 'response_formats': requested_formats(cases),
           'response_format_version': 'easy-requested-json-types-v1',
           'prompts': [[{'role': 'system', 'content': SYSTEM_PROMPT},
                        {'role': 'user', 'content': case['prompt']}] for case in cases]}

    def run():
        result = run_native_job(job, output_dir=output_dir, timeout_seconds=timeout_seconds)
        result['quality'] = [grade_case(cases[row['prompt_index']], row['text'])
                             for row in result['requests']]
        result.update(workload_hash=dataset_hash(cases),
                      scope='Adapter compatibility smoke; not agent search or a promotion.')
        save_json(output_dir / 'graded.json', result)
        return result

    verified = trace_native_job(project=project, run=run)
    save_json(output_dir / 'verified.json', verified)
    return verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--timeout-seconds', type=float, required=True)
    args = parser.parse_args()
    verified = check(artifact=args.artifact, output_dir=args.output,
                     timeout_seconds=args.timeout_seconds, project=os.environ.get('SERA_PROJECT'))
    rows = verified['result']['quality']
    print(f"Quality: {sum(row['passed'] for row in rows)}/{len(rows)}")
    print(f"Peak allocator bytes: {verified['result']['memory']['peak_bytes']}")
    print(verified['trace']['url'])


if __name__ == '__main__':
    main()
