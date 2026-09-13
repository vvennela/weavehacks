# Import the pinned checkout, not the installed older wheel.
"""Explicit live rehearsal. Keys are supplied only through the runtime environment."""

import importlib.metadata
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPOSITORY = Path('/marimo/sera-openai-example-v2')
SOURCE_COMMIT = 'f4d8fa60c6b821ac9400b6c2cacfb048d3b21338'
OUTPUT = Path('/marimo/sera-evidence/openai-example-v2')

sys.path.insert(0, str(REPOSITORY))
import litellm

import sera
from experiments.example_run import ExampleRun
from sera.storage import save_json

litellm.suppress_debug_info = True
assert subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPOSITORY,
                      capture_output=True, text=True, check=True).stdout.strip() == SOURCE_COMMIT
assert str(REPOSITORY) in sera.__file__
assert os.environ.get('OPENAI_API_KEY') and os.environ.get('WANDB_API_KEY')
OUTPUT.mkdir(exist_ok=False)
record = {'status': 'started', 'source_commit': SOURCE_COMMIT, 'sera_import': sera.__file__,
    'provider': 'litellm-openai', 'agent_model': 'gpt-6-astra', 'gpu_trials_authorized': True,
    'parameters': {'model': 'Qwen/Qwen2.5-72B-Instruct', 'quantization': 'fp8_per_tensor',
        'kv_cache_dtype': 'auto', 'quality_floor': .99, 'min_latency_improvement_fraction': .05,
        'concurrency': [1, 2, 4, 8], 'max_candidate_trials': None,
        'workload': 'unchanged eight easy strict-JSON tasks'},
    'versions': {name: importlib.metadata.version(name) for name in
              ['vllm', 'torch', 'transformers', 'litellm', 'weave', 'openai']}}
example = ExampleRun(output_root=OUTPUT)
started = time.monotonic()
result = None
try:
    assert not any(example.status().values())
    record['blank_state_passed'] = True
    example.configure_weave(os.environ['WANDB_API_KEY'],
                            project='vvennela-n-a/wandb_agent_default_project')
    record['weave_check'] = example.check_weave()
    example.configure_agent(provider='litellm-openai', model='gpt-6-astra',
                            api_key=os.environ['OPENAI_API_KEY'])
    record['provider_check'] = example.check_agent()
    record['status'] = 'provider-passed-starting-gpu'
    save_json(OUTPUT/'invocation.json', record)
    print(json.dumps(record), flush=True)
    # This calls sera.optimize with the full swarm and progress-based stopping.
    result = example.optimize()
    record['comparison'] = example.compare(result)
    record['run_directory'] = str(result.output_dir)
    record['weave_url'] = result.weave_url
    if result.models:
        prompts, evaluate = example._tasks()
        response = result.models[0].generate(prompts[0])
        record['returned_runner_probe'] = response.to_dict()
        record['returned_runner_probe_passed'] = evaluate(prompts[0], response.text)
    else:
        record['returned_runner_probe_passed'] = False
    record['status'] = 'measured'
except BaseException as error:  # noqa: BLE001 -- redact errors and clean up even on interruption.
    record.update(status='failed', error_type=type(error).__name__)
    # The error class is safe; arbitrary exception text can contain credentials.
finally:
    try:
        record['gpu_after_cleanup'] = example.close()
        record['cleanup_passed'] = (record['gpu_after_cleanup'].get('used_mib') == 0)
    except BaseException as error:  # noqa: BLE001 -- preserve a safe cleanup-failure record.
        record.update(cleanup_passed=False, cleanup_error_type=type(error).__name__)
    record['elapsed_seconds'] = time.monotonic() - started
    record['passed'] = bool(record.get('returned_runner_probe_passed') and record.get('cleanup_passed'))
    save_json(OUTPUT/'invocation.json', record)
    print(json.dumps(record), flush=True)
raise SystemExit(0 if record['passed'] else 1)
