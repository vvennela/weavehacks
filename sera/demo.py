"""Small, real-GPU demo setup. Importing this module starts no work."""

import importlib.metadata
import json
import os
import subprocess
import sys
import uuid
from importlib.resources import files
from pathlib import Path

from .config import LARGE_MODEL_ID, Constraints, RuntimeConfig, Workload
from .litellm_agent import LiteLLMAgent
from .provider_check import check_provider, require_provider_check

SYSTEM_PROMPT = (
    'Solve the task. Return only one JSON object with exactly one key, "answer". '
    'Use the JSON type required by the question. Do not include explanation, '
    'Markdown, or code fences. Use JSON true, false, and null, not Python literals.'
)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('Non-JSON numeric constant')


def demo_tasks():
    """The recorded eight easy tasks, with exact, type-sensitive JSON checks."""
    cases = json.loads(files('sera').joinpath('demo_cases.json').read_text())
    expected = {case['prompt']: case['expected'] for case in cases}
    prompts = [[{'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': case['prompt']}] for case in cases]

    def evaluate(prompt, output):
        if not isinstance(output, str) or not output.strip() or len(output) > 16384:
            return False
        try:
            actual = json.loads(output, object_pairs_hook=_unique_object,
                                parse_constant=_reject_constant)
            answer = {'answer': expected[prompt[-1]['content']]}
            return json.dumps(actual, sort_keys=True) == json.dumps(answer, sort_keys=True)
        except (ValueError, RecursionError):
            return False

    return prompts, evaluate


def _check_gpu():
    from .runtime import gpu_snapshot
    try:
        snapshot = gpu_snapshot()
    except (OSError, ValueError, subprocess.SubprocessError):
        raise RuntimeError('Change runtime to GPU, then run setup again') from None
    if sys.platform != 'linux':
        raise RuntimeError('Use the prepared Molab Linux GPU runtime')
    try:
        version = importlib.metadata.version('vllm')
    except importlib.metadata.PackageNotFoundError:
        version = None
    if version != '0.26.0':
        raise RuntimeError('Use the prepared GPU runtime with vLLM 0.26.0; no GPU packages were changed')
    return snapshot


def prepare_demo(*, project, certificate=None, investigator='gpt-6-astra',
                 evidence_root='sera-runs/demo-setup'):
    """Check setup once, then return explicit kwargs for sera.optimize.

    Requires the prepared Linux/vLLM GPU runtime and runtime OPENAI_API_KEY and
    WANDB_API_KEY. A missing certificate triggers real, billable provider checks,
    never a GPU trial. An explicit certificate or SERA_PROVIDER_CHECK is verified
    before reuse. Both keys stay in this dedicated notebook process.
    """
    if not isinstance(project, str) or len(project.strip().split('/')) != 2 or any(
            not part.strip() for part in project.split('/')):
        raise ValueError('Supply your Weave project as entity/project')
    gpu = _check_gpu()
    if gpu['used_mib'] != 0:
        raise RuntimeError('GPU is in use. Close the owning run before continuing')
    for name in ('OPENAI_API_KEY', 'WANDB_API_KEY'):
        if not os.environ.get(name, '').strip():
            raise ValueError(f'Add your {name} in the setup cell')
    agent = LiteLLMAgent(project=project.strip(), model=investigator)
    certificate = certificate or os.environ.get('SERA_PROVIDER_CHECK')
    if certificate is None:
        folder = Path(evidence_root) / uuid.uuid4().hex
        print('Checking the investigator provider before GPU work…')
        report = check_provider(project=agent.project, model=agent.model, agent=agent,
                                output_dir=folder, stop_on_failure=True)
        if not report['passed']:
            raise RuntimeError(f'Provider check failed; inspect {folder / "result.json"}')
        certificate = folder / 'result.json'
    require_provider_check(certificate, agent)
    prompts, evaluate = demo_tasks()
    return {'models': [LARGE_MODEL_ID], 'prompts': prompts, 'mode': 'swarm', 'agent': agent,
                'provider_check': certificate,
                'baseline_configuration': RuntimeConfig(quantization='fp8_per_tensor'),
                'evaluation': evaluate, 'evaluation_version': 'sera-molab-demo-json-v1',
                'constraints': Constraints(quality_floor=.99),
                'workload': Workload(concurrency=[1, 2, 4, 8])}
