"""Decode the output type requested in a task, never its correct answer."""

import json
import re


PROFILE_VERSION = 'sera-easy-requested-types-v1'


def response_format_for_prompt(prompt):
    if not isinstance(prompt, str):
        raise ValueError('A task prompt is required, not an evaluation case or answer key')
    if re.search(r'Return (?:the integer|that integer|its integer value)\b', prompt):
        answer = {'type': 'integer'}
    elif 'Return the string in a JSON object' in prompt:
        answer = {'type': 'string'}
    elif 'Return the IDs' in prompt and 'Put the array in a JSON object' in prompt:
        # The request supplies the ID field's type. Do not inspect the filter,
        # select any record, constrain array length, or enumerate possible IDs.
        try:
            records, _ = json.JSONDecoder().raw_decode(prompt[prompt.index('['):])
        except (ValueError, TypeError) as error:
            raise ValueError('ID type is not explicit in the input records') from error
        if not isinstance(records, list) or not records or not all(
                isinstance(row, dict) and isinstance(row.get('id'), str) for row in records):
            raise ValueError('This pilot requires explicitly string-valued input IDs')
        answer = {'type': 'array', 'items': {'type': 'string'}}
    else:
        raise ValueError('No supported explicit output-type request')
    return {'type': 'json_schema', 'json_schema': {
        'name': PROFILE_VERSION,
        'schema': {'type': 'object', 'properties': {'answer': answer},
                   'required': ['answer'], 'additionalProperties': False}}}
