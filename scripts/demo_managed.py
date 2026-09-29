"""Live terminal demo using the installed Sera client and a registered workload."""
import argparse
import json
import os
import time
from pathlib import Path

import sera as Sera


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', default='mlx-easy-compatibility-v1')
    parser.add_argument('--endpoint', default='http://127.0.0.1:8765')
    parser.add_argument('--request-id', required=True, help='Reuse this ID to reconnect to this run')
    parser.add_argument('--key-file', type=Path, help='Private customer.env created by the operator')
    args = parser.parse_args()
    key = os.environ.get('SERA_ACCESS_KEY')
    if args.key_file is not None:
        name, separator, key = args.key_file.read_text().strip().partition('=')
        if name != 'SERA_ACCESS_KEY' or separator != '=':
            raise SystemExit('The key file must contain one SERA_ACCESS_KEY assignment')
    if not key:
        raise SystemExit('Set the customer SERA_ACCESS_KEY before the demo')
    started = time.monotonic()
    seen = set()
    latest = {}
    def say(message):
        print(f'[{time.monotonic() - started:5.1f}s] {message}', flush=True)
    def quality(value):
        return f'{value:.1%}' if isinstance(value, (int, float)) else 'unavailable'
    def update(job):
        if not seen and job['status'] == 'completed':
            say('Restored completed research. The following measurements are recorded evidence.')
        if job['status'] not in seen:
            seen.add(job['status'])
            say('Job: ' + job['status'])
        progress = job.get('progress', {})
        measurements = (job.get('result') or {}).get('measurements') or progress.get('measurements', {})
        latest.update(measurements)
        scope = measurements.get('scope')
        if scope and 'scope' not in seen:
            seen.add('scope')
            say('Measurement scope: ' + scope)
        baseline = measurements.get('baseline', {})
        if baseline.get('peak_bytes') and 'baseline' not in seen:
            seen.add('baseline')
            say(f"BF16 baseline: {baseline['peak_bytes'] / 2**30:.3f} GiB peak; quality {quality(baseline.get('quality'))}")
        for trial in measurements.get('trials', []):
            signature = json.dumps(trial, sort_keys=True)
            if signature in seen or trial['measurement']['peak_bytes'] is None:
                continue
            seen.add(signature)
            measurement = trial['measurement']
            say(f"{trial['recipe_id']}: {measurement['peak_bytes'] / 2**30:.3f} GiB peak; "
                f"quality {quality(measurement.get('quality'))}; "
                + ('confirmed' if trial['accepted'] else 'not promoted'))
    say('Sera will research smaller checkpoints and keep the fixed quality gate.')
    result = Sera.Optimize(args.profile, api_key=key, endpoint=args.endpoint,
                           request_id=args.request_id, on_update=update)
    selected = next((trial for trial in latest.get('trials', [])
                     if trial['recipe_id'] == result.selected_recipe_id), None)
    if selected is not None:
        peak = max(selected['measurement']['peak_bytes'], selected['confirmation']['peak_bytes'])
        baseline = latest['baseline']['peak_bytes']
        say(f'Measured peak memory fell {1 - peak / baseline:.2%} versus the initial baseline.')
    say(f'Selected {result.selected_recipe_id}; checking and loading its exported checkpoint.')
    with result.load() as model:
        output = model.generate([
            {'role': 'system', 'content': 'Return only a JSON object with the integer answer.'},
            {'role': 'user', 'content': 'What is 7 + 8?'}], max_tokens=64, seed=0,
            response_format={'type': 'json_schema', 'json_schema': {'name': 'answer', 'schema': {
                'type': 'object', 'properties': {'answer': {'type': 'integer'}},
                'required': ['answer'], 'additionalProperties': False}}})
    if json.loads(output['text']) != {'answer': 15}:
        raise SystemExit('The independent request failed; retain this result as failure evidence')
    say(f"Independent request: 7 + 8 → {output['text']}")
    say('W&B trace: ' + result.trace_url)
    say('This demo shows the measured workflow. It does not establish an advantage over fixed search.')


if __name__ == '__main__':
    main()
