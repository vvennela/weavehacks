"""Test one pinned BF16 model with native JSON decoding and the unchanged eight tasks.

Run from the repository root:
  python -m experiments.run_structured_quality_pilot --model-id Qwen/Qwen3-0.6B \
    --output-dir evidence/qwen-structured-quality-v1

This is a new task-quality profile, not a regrade or a performance comparison.
No output repair, task retries, quantization, or joint placement is performed.
Native response_format reference (checked for the installed runtime):
https://docs.vllm.ai/en/v0.26.0/features/structured_outputs/
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import time
import urllib.error

from benchmarks.grade import SYSTEM_PROMPT, dataset_hash, grade_case, load_cases
from sera.config import GLM_MODEL_ID, GLM_MODEL_REVISION, MODEL_ID, MODEL_REVISION, RuntimeConfig
from sera.runtime import GENERATION, SeraModel
from sera.storage import content_hash, save_json


PROFILE_VERSION = 'sera-easy-structured-json-v1'
DATASET_HASH = '2f3c6687cf2a19bde4c3f5b60ab56cb24ac67c6755e999ad98227b04e42d95a7'
QUALITY_FLOOR = .99
PINNED_MODELS = {MODEL_ID: MODEL_REVISION, GLM_MODEL_ID: GLM_MODEL_REVISION}


def response_format():
    """One answer-independent schema for every task and both models."""
    return {'type': 'json_schema', 'json_schema': {
        'name': 'sera-answer-v1',
        'schema': {'type': 'object', 'properties': {
            'answer': {'type': ['string', 'number', 'boolean', 'null', 'array', 'object']}},
            'required': ['answer'], 'additionalProperties': False}}}


class RecordingSeraModel(SeraModel):
    """Retain the complete completion exchange without changing runtime validation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.exchanges = []

    def _request(self, route, payload=None, timeout=90):
        if route != '/v1/chat/completions':
            return super()._request(route, payload, timeout)
        exchange = {'request': payload, 'request_hash': content_hash(payload)}
        self.exchanges.append(exchange)
        started = time.perf_counter()
        try:
            body = super()._request(route, payload, timeout)
            exchange['raw_response'] = body
            return body
        except Exception as error:
            exchange['error_type'] = type(error).__name__
            if isinstance(error, urllib.error.HTTPError):
                exchange['http_status'] = error.code
                exchange['raw_error_body'] = error.read().decode('utf-8', errors='replace')
            raise
        finally:
            exchange['latency_ms'] = (time.perf_counter() - started) * 1000


def collect_case(model, case):
    prompt = [{'role': 'system', 'content': SYSTEM_PROMPT},
              {'role': 'user', 'content': case['prompt']}]
    row = {'case_id': case['id'], 'prompt': prompt, 'prompt_hash': content_hash(prompt),
           'task_pass': False, 'failure_kind': 'generation'}
    previous_exchanges = len(model.exchanges)
    try:
        payload, tokens = model.prepare(prompt)
        payload['response_format'] = response_format()
        row.update(prompt_token_ids=tokens, prompt_token_hash=content_hash(tokens))
        response = model._generate_prepared(payload, tokens)
        row['response'] = response.to_dict()
        row['grade'] = grade_case(case, response.text)
        if response.finish_reason != 'stop':
            row['error_type'] = 'IncompleteGeneration'
        else:
            row['task_pass'] = row['grade']['passed']
            row['failure_kind'] = (None if row['task_pass'] else
                                   'semantic' if row['grade']['format_valid'] else 'format')
    except Exception as error:
        row['error_type'] = type(error).__name__
    if len(model.exchanges) > previous_exchanges:
        row['exchange'] = model.exchanges[-1]
    return row


def run_pilot(*, model_id, output_dir):
    if model_id not in PINNED_MODELS:
        raise ValueError('The pilot requires one of the two specified model IDs')
    cases = load_cases(Path(__file__).resolve().parents[1] / 'benchmarks/easy_cases.json')
    if dataset_hash(cases) != DATASET_HASH:
        raise ValueError('The original eight-question dataset changed; create a new approved profile')
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    config = RuntimeConfig()
    profile = {'profile_version': PROFILE_VERSION, 'dataset_hash': DATASET_HASH,
               'system_prompt': SYSTEM_PROMPT, 'response_format': response_format(),
               'generation': GENERATION, 'enable_thinking': False,
               'configuration': config.model_dump(), 'quality_floor': QUALITY_FLOOR,
               'concurrency': 1, 'passes': 1, 'warmup_requests': 0}
    report = {**profile, 'profile_hash': content_hash(profile),
              'response_schema_hash': content_hash(response_format()['json_schema']['schema']),
              'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'running',
              'model_id': model_id, 'model_revision': PINNED_MODELS[model_id],
              'evaluation_cases': cases, 'requests': [],
              'limits': 'New decoding profile; does not replace earlier results. Eight serial requests, '
                        'no retries or warmup. Request latency includes possible first-use grammar '
                        'compilation, but excludes model startup and tokenization. '
                        'No speedup, FP8 quality, or joint-placement claim.'}
    path = folder / 'result.json'
    save_json(path, report)
    model = RecordingSeraModel(artifact_dir=folder / 'runtime', configuration=config,
                               model_id=model_id, revision=PINNED_MODELS[model_id])
    try:
        model.start()
        for case in cases:
            report['requests'].append(collect_case(model, case))
            save_json(path, report)
    except Exception as error:
        report['error_type'] = type(error).__name__
    finally:
        try:
            model.close()
        except Exception as error:
            report['cleanup_error_type'] = type(error).__name__
        report['runtime'] = model.record
        correct = sum(row['task_pass'] for row in report['requests'])
        report['task_quality'] = {'correct': correct, 'total': len(cases),
                                  'score': correct / len(cases), 'floor': QUALITY_FLOOR,
                                  'passed': correct / len(cases) >= QUALITY_FLOOR}
        report['status'] = ('pass' if report['task_quality']['passed']
                            and model.record.get('cleanup_pass') is True
                            and 'error_type' not in report and 'cleanup_error_type' not in report else 'fail')
        save_json(path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-id', required=True, choices=PINNED_MODELS)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    report = run_pilot(model_id=args.model_id, output_dir=args.output_dir)
    print(f"{report['status']}: {report['task_quality']['correct']}/8 strict tasks")
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
