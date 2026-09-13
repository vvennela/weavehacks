"""OpenAI investigators through LiteLLM, with unchanged local decision validation."""

import json
import os

from pydantic import SecretStr

from .agent import ProviderTransportError, WandbAgent, request_schema
from .config import CONTROL_ROLES
from .storage import content_hash


OPENAI_BASE_URL = 'https://api.openai.com/v1'
TRANSPORT_PROFILE = 'sera-litellm-openai-low-2048-flat-root-role-rules-v2'


class LiteLLMAgent(WandbAgent):
    """Per-instance OpenAI credentials; no configurable remote destination or tools."""

    provider = 'litellm-openai'

    def __init__(self, *, project, model='gpt-6-astra', api_key=None):
        if (not isinstance(model, str) or not model or model != model.strip()
                or '/' in model or any(character.isspace() for character in model)):
            raise ValueError('Use an explicit OpenAI model ID without a provider prefix')
        key = api_key if api_key is not None else os.environ.get('OPENAI_API_KEY')
        if not isinstance(key, str) or not key.strip():
            raise ValueError('Supply api_key or set OPENAI_API_KEY in this process')
        super().__init__(project=project, model=model)
        self._api_key = SecretStr(key)
        self.endpoint_fingerprint = content_hash({
            'base_url': OPENAI_BASE_URL, 'provider': self.provider,
            'transport_profile': TRANSPORT_PROFILE,
        })

    def fork(self):
        return LiteLLMAgent(project=self.project, model=self.model,
                           api_key=self._api_key.get_secret_value())

    def wire_schema(self, role, evidence):
        schema = request_schema(role, evidence)
        if role == 'proposal':
            # OpenAI structured outputs prohibit root anyOf. Proposal validators
            # still enforce each action/role/value/cost combination after generation.
            schema.pop('anyOf', None)
            role_rules = '; '.join(f'{lever} -> {specialist}'
                                   for lever, specialist in CONTROL_ROLES.items())
            schema['properties']['agent_role']['description'] = (
                'For action=trial, select the role required by changed_lever: '
                f'{role_rules}. For action=keep-baseline, either permitted role is valid; '
                'changed_lever and proposed_value must be null and expected_trial_cost must be 0. '
                'For action=trial, expected_trial_cost must be 1. '
                'These rules are checked after generation; a wrong role rejects the proposal.'
            )
        return schema

    def _complete(self, payload):
        import litellm

        request = {key: value for key, value in payload.items()
                   if key not in {'model', 'temperature', 'max_tokens'}}
        try:
            response = litellm.completion(
                **request, model=f'openai/{self.model}', api_base=OPENAI_BASE_URL,
                api_key=self._api_key.get_secret_value(), max_completion_tokens=2048,
                reasoning_effort='low', allowed_openai_params=['reasoning_effort'],
                num_retries=0, timeout=90,
            )
            if callable(getattr(response, 'model_dump', None)):
                response = response.model_dump(mode='json', warnings=False)
            if not isinstance(response, dict):
                raise ProviderTransportError('Provider returned an invalid completion envelope')
            encoded = json.dumps(response, allow_nan=False)
            secrets = (self._api_key.get_secret_value(), os.environ.get('OPENAI_API_KEY', ''),
                       os.environ.get('WANDB_API_KEY', ''))
            if any(secret and secret in encoded for secret in secrets):
                raise ProviderTransportError('Provider response contains a credential')
            return response
        except ProviderTransportError:
            raise
        except Exception as error:
            # LiteLLM errors can contain full bodies, headers, and credentials.
            status = getattr(error, 'status_code', None)
            if type(status) is int and 100 <= status <= 599:
                raise ProviderTransportError(f'Provider HTTP {status}', http_status=status) from None
            raise ProviderTransportError('Provider transport or response failure') from None
