"""Independently regrade the saved eight-task typed-decoding quality pilot."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

from benchmarks.grade import SYSTEM_PROMPT, dataset_hash, grade_case, load_cases
from experiments.requested_answer_types import PROFILE_VERSION, response_format_for_prompt
from sera.config import MODEL_ID, MODEL_REVISION, RuntimeConfig
from sera.runtime import GENERATION
from sera.storage import content_hash, save_json


def audit(folder):
    paths = [folder / 'result.json', folder / 'runtime/runtime.json', folder / 'runtime/server.log']
    hashes = {str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    repository = Path(__file__).resolve().parents[2]
    code_hashes = {name: hashlib.sha256((repository / name).read_bytes()).hexdigest() for name in
                   ('benchmarks/easy_cases.json', 'benchmarks/grade.py',
                    'experiments/requested_answer_types.py', 'experiments/run_structured_quality_pilot.py')}
    report, runtime = [json.loads(path.read_text()) for path in paths[:2]]
    server_log = paths[2].read_text()
    cases = load_cases(repository / 'benchmarks/easy_cases.json')
    assert report['evaluation_cases'] == cases
    assert report['dataset_hash'] == dataset_hash(cases) == '2f3c6687cf2a19bde4c3f5b60ab56cb24ac67c6755e999ad98227b04e42d95a7'
    assert report['model_id'] == runtime['model_id'] == MODEL_ID
    assert report['model_revision'] == runtime['revision'] == MODEL_REVISION
    assert report['runtime'] == runtime
    assert runtime['configuration'] == report['configuration'] == RuntimeConfig().model_dump()
    assert report['generation'] == runtime['generation'] == GENERATION
    assert report['enable_thinking'] is runtime['enable_thinking'] is False
    assert report['quality_floor'] == .99 and report['profile_version'] == PROFILE_VERSION
    assert report['system_prompt'] == SYSTEM_PROMPT
    assert report['concurrency'] == report['passes'] == 1 and report['warmup_requests'] == 0
    formats = [response_format_for_prompt(case['prompt']) for case in cases]
    assert report['response_formats'] == formats and report['response_format'] is None
    assert report['response_schema_hash'] == content_hash([item['json_schema']['schema'] for item in formats])
    profile_keys = ('profile_version', 'dataset_hash', 'system_prompt', 'response_format', 'generation',
                    'enable_thinking', 'configuration', 'quality_floor', 'concurrency', 'passes',
                    'warmup_requests', 'response_formats', 'schema_source')
    assert report['profile_hash'] == content_hash({key: report[key] for key in profile_keys})
    assert len(report['requests']) == 8
    regraded = []
    for case, row, schema in zip(cases, report['requests'], formats):
        exchange = row['exchange']
        request, response = exchange['request'], row['response']
        raw = exchange['raw_response']
        prompt = [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': case['prompt']}]
        assert row['case_id'] == case['id'] and row['prompt'] == request['messages'] == prompt
        assert row['prompt_hash'] == content_hash(prompt)
        assert exchange['request_hash'] == content_hash(request)
        assert request['response_format'] == schema
        assert {key: request[key] for key in GENERATION} == GENERATION
        assert request['chat_template_kwargs'] == {'enable_thinking': False}
        assert not {'expected', 'rationale', 'case_id'} & request.keys()
        assert response['text'] == raw['choices'][0]['message']['content']
        assert response['token_ids'] == raw['choices'][0]['token_ids'] and response['token_ids']
        assert response['finish_reason'] == raw['choices'][0]['finish_reason'] == 'stop'
        assert row['prompt_token_ids'] == response['prompt_token_ids'] == raw['prompt_token_ids']
        assert row['prompt_token_hash'] == content_hash(row['prompt_token_ids'])
        assert not response.get('error') and not row.get('error_type') and not exchange.get('error_type')
        grade = grade_case(case, response['text'])
        assert grade == row['grade'] and row['task_pass'] is grade['passed']
        assert math.isfinite(response['latency_ms']) and response['latency_ms'] > 0
        regraded.append({'case_id': case['id'], 'raw_output': response['text'],
                         'grade': grade, 'latency_ms': response['latency_ms']})
    correct = sum(row['grade']['passed'] for row in regraded)
    assert report['task_quality'] == {'correct': correct, 'total': 8, 'score': correct / 8,
                                     'floor': .99, 'passed': correct / 8 >= .99}
    assert correct == 8 and report['status'] == 'pass'
    assert runtime['cleanup_pass'] is True and runtime['memory_after_mib'] == 0
    assert server_log.count('"POST /v1/chat/completions HTTP/1.1" 200 OK') == 8
    assert f"model='{MODEL_ID}'" in server_log and f'revision={MODEL_REVISION}' in server_log
    assert 'dtype=torch.bfloat16' in server_log and 'quantization=None' in server_log
    assert 'kv_cache_dtype=auto' in server_log and 'Application shutdown complete.' in server_log
    latencies = sorted(row['latency_ms'] for row in regraded)
    return {'schema_version': 'sera-requested-type-quality-audit-v1', 'audit_passed': True,
        'source_sha256': hashes, 'audit_code_sha256': code_hashes, 'profile_hash': report['profile_hash'],
        'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
        'task_quality': report['task_quality'], 'per_case': regraded,
        'median_request_ms': statistics.median(latencies), 'p95_request_ms': latencies[-1],
        'startup_seconds': runtime['startup_seconds'], 'cleanup_memory_mib': 0,
        'provider_calls_during_audit': 0, 'gpu_trials_during_audit': 0,
        'joint_placement_accepted': False,
        'limitations': ['A new typed-decoding quality profile, not a regrade of old failed profiles.',
            'One serial pass of eight tasks; no warmup, retry, speedup, or broad quality claim.',
            'Latency can include first-use grammar work; this is not the repeated load protocol.',
            'The schema constrains requested type, not answer value, permitted IDs, or array length.',
            'Saved-artifact consistency audit, not independent proof of GPU execution.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source_dir)
    save_json(Path(__file__).with_name('audit.json'), result)
    print(json.dumps({key: result[key] for key in ('audit_passed', 'task_quality', 'median_request_ms',
                                                   'p95_request_ms', 'startup_seconds')}, indent=2))
