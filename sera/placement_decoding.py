"""Versioned caller-supplied JSON decoding; no task or answer-key imports."""

from copy import deepcopy
import json
import re

from .storage import content_hash


def validate_response_format(value):
    if not isinstance(value, dict) or set(value) != {'type', 'json_schema'} or value['type'] != 'json_schema':
        raise ValueError('response_format must be an explicit json_schema format')
    definition = value['json_schema']
    if (not isinstance(definition, dict) or set(definition)-{'name', 'schema', 'strict'}
            or not isinstance(definition.get('schema'), dict)
            or not isinstance(definition.get('name'), str)
            or re.fullmatch(r'[A-Za-z0-9_-]{1,64}', definition['name']) is None
            or ('strict' in definition and type(definition['strict']) is not bool)):
        raise ValueError('response_format requires a named JSON schema')
    try:
        encoded = json.dumps(value, allow_nan=False)
        if json.loads(encoded) != value:
            raise ValueError('Non-JSON schema value')
    except (TypeError, ValueError) as error:
        raise ValueError('response_format must contain only finite JSON values') from error
    return deepcopy(value)


def validate_formats(prompts, formats, version):
    if formats is None:
        if version is not None:
            raise ValueError('response_format_version requires response_formats')
        return None
    if (not isinstance(formats, list) or len(formats) != len(prompts)
            or not isinstance(version, str) or not version.strip()):
        raise ValueError('Supply one response_format per prompt and an explicit version')
    values = [validate_response_format(value) for value in formats]
    known = {}
    for prompt, value in zip(prompts, values):
        key = content_hash(prompt)
        if key in known and known[key] != value:
            raise ValueError('The same prompt cannot have conflicting response_formats')
        known[key] = value
    return values


class PlacementRunner:
    """Add the frozen per-prompt decoding contract to an owned live runner."""

    def __init__(self, model, profile):
        self._model = model
        self._formats = {content_hash(prompt):deepcopy(value)
                         for prompt,value in zip(profile.prompts, profile.response_formats)}
        self._model.record.update(response_format_version=profile.response_format_version,
                                  response_formats_hash=content_hash(profile.response_formats))

    def __getattr__(self, name):
        return getattr(self._model, name)

    def _prepare(self, prompt, response_format):
        known = self._formats.get(content_hash(prompt))
        if response_format is None:
            if known is None:
                raise ValueError('A new prompt requires an explicit response_format; its task type is not inferred')
            selected = deepcopy(known)
        else:
            selected = validate_response_format(response_format)
            if known is not None and selected != known:
                raise ValueError('Cannot change response_format for a measured prompt')
        payload, tokens = self._model.prepare(prompt)
        return dict(payload, response_format=selected), tokens

    def prepare(self, prompt):
        return self._prepare(prompt, None)

    def generate(self, prompt, *, response_format=None):
        payload, tokens = self._prepare(prompt, response_format)
        return self._model._generate_prepared(payload, tokens)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._model.close()


def runner_for_profile(model, profile):
    return model if profile.response_formats is None else PlacementRunner(model, profile)
