"""Translate native allocator measurements into the existing selection gates."""

import math
from copy import deepcopy

from .measurement import reduce_requests
from .quality import evaluate_quality


def _tokens(value):
    return isinstance(value, list) and bool(value) and all(type(x) is int and x >= 0 for x in value)


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def native_trial(raw, *, prompts, evaluator, evaluation_version, floor,
                 artifact_id, controls, trial_id):
    """Retain raw evidence; malformed or incomplete measurements cannot qualify."""
    errors = []
    rows = deepcopy(raw.get('requests', []))
    if not isinstance(rows, list):
        rows = []
        errors.append('invalid-request-list')
    repetitions = controls['repetitions']
    count = len(prompts)
    if raw.get('artifact_id') != artifact_id or raw.get('controls') != controls:
        errors.append('measurement-identity-mismatch')
    device, versions = raw.get('device'), raw.get('runtime_versions')
    if (not isinstance(device, dict) or not isinstance(device.get('device_name'), str)
            or not device['device_name'].strip() or type(device.get('memory_size')) is not int
            or device['memory_size'] <= 0):
        errors.append('missing-device-identity')
    if not isinstance(versions, dict) or any(not isinstance(versions.get(name), str)
        or not versions[name].strip() for name in ('mlx', 'mlx-lm', 'transformers', 'outlines')):
        errors.append('missing-runtime-identity')
    if len(rows) != count * repetitions:
        errors.append('incomplete-request-coverage')
    input_ids = [None] * count
    prepared = []
    for index, row in enumerate(rows):
        row = row if isinstance(row, dict) else {}
        repetition, prompt_index = divmod(index, count)
        formats = controls.get('response_formats')
        expected_format = formats[prompt_index] if formats is not None else None
        valid = (type(row.get('repetition')) is int and row['repetition'] == repetition
                 and type(row.get('prompt_index')) is int and row['prompt_index'] == prompt_index
                 and not row.get('error') and isinstance(row.get('text'), str)
                 and bool(row['text'].strip()) and _tokens(row.get('token_ids'))
                 and _tokens(row.get('prompt_token_ids')) and _positive(row.get('latency_ms'))
                 and row.get('finish_reason') in {'stop', 'length'}
                 and row.get('response_format') == expected_format)
        if input_ids[prompt_index] is None:
            input_ids[prompt_index] = row.get('prompt_token_ids')
        elif input_ids[prompt_index] != row.get('prompt_token_ids'):
            valid = False
        if not valid:
            errors.append(f'invalid-request-{index}')
        prepared.append({**row, 'prompt_index': index,
            'source_prompt_index': prompt_index, 'error': None if valid else 'invalid-native-request',
            'usage': {'prompt_tokens': len(row['prompt_token_ids']) if _tokens(row.get('prompt_token_ids')) else 0,
                      'completion_tokens': len(row['token_ids']) if _tokens(row.get('token_ids')) else 0}})
    elapsed = raw.get('request_wall_seconds')
    if not _positive(elapsed):
        errors.append('invalid-measurement-window')
    quality = evaluate_quality({'quality': prepared}, prompts * repetitions, evaluator,
                               version=evaluation_version, floor=floor)
    memory = raw.get('memory')
    memory = memory if isinstance(memory, dict) else {}
    valid_memory = (memory.get('metric') == 'mlx-active-allocator-bytes'
        and memory.get('scope') == 'MLX allocator; not system-wide unified memory or free VRAM'
        and all(type(memory.get(key)) is int and memory[key] >= 0
                for key in ('resident_bytes', 'peak_bytes', 'active_bytes', 'cache_bytes')))
    valid_memory = valid_memory and memory['peak_bytes'] >= max(
        memory['resident_bytes'], memory['active_bytes'], 1)
    runtime = {'artifact_id': artifact_id, 'memory': deepcopy(memory),
               'device': raw.get('device'), 'versions': raw.get('runtime_versions'),
               'telemetry_errors': 0 if valid_memory else 1,
               # This legacy field is an adapter value, not an external GPU sample.
               'sampled_peak_memory_mib': memory['peak_bytes'] / (1024 ** 2) if valid_memory else None,
               'memory_measurement_method': 'native-allocator-high-water-mark'}
    return {'trial_id': trial_id, 'status': 'collected' if not errors else 'request-errors',
            'native_measurement': raw, 'measurement_errors': errors, 'runtime': runtime,
            'input_token_ids': input_ids, 'quality': prepared, 'task_quality': quality,
            'generation_errors': len(errors),
            'reduced': reduce_requests(prepared, elapsed) if not errors else {}}
