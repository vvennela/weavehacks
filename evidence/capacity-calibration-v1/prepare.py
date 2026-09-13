"""Freeze the two user-approved allocations before any new GPU measurement."""

import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.grade import load_cases
from experiments.requested_answer_types import PROFILE_VERSION, response_format_for_prompt
from sera.config import MODEL_ID, MODEL_REVISION, GLM_MODEL_ID, GLM_MODEL_REVISION, RuntimeConfig
from sera.placement_config import PlacementPlan, PlacementService, PlacementConstraints


def main():
    folder = Path(__file__).parent
    gib = 1024**3
    physical = 97887 * 1024**2
    constraints = PlacementConstraints(quality_floor=.99, max_p95_slowdown_fraction=.10,
                                       max_generation_errors=0)
    plans, estimates, labels = [], {}, {}
    # Rounded-up prior startup measurements. KV is one maximum-length sequence,
    # not eight full-length sequences. Actual acceptance uses the frozen eight tasks.
    qwen = dict(weights_bytes=math.ceil(1.13*gib), kv_bytes=2*28*8*128*2*4096,
        workspace_bytes=math.ceil(.12*gib), process_overhead_bytes=gib,
        fragmentation_bytes=math.ceil(.05*gib))
    glm = dict(weights_bytes=math.ceil(10.03*gib), kv_bytes=2*40*2*128*2*4096,
        workspace_bytes=math.ceil(.42*gib), process_overhead_bytes=gib,
        fragmentation_bytes=math.ceil(.05*gib))
    for qwen_gib, glm_gib in [(3, 17), (2.5, 15)]:
        for quantized in [True, False]:
            services = []
            for model, revision, allocation in [(MODEL_ID, MODEL_REVISION, qwen_gib),
                                                (GLM_MODEL_ID, GLM_MODEL_REVISION, glm_gib)]:
                services.append(PlacementService(model_id=model, revision=revision, gpu_index=0,
                    allocation_bytes=int(allocation*gib), constraints=constraints,
                    configuration=RuntimeConfig(gpu_memory_utilization=(allocation-1)*gib/physical,
                        quantization='fp8_per_tensor' if quantized and model == GLM_MODEL_ID else None)))
            plan = PlacementPlan(physical_gpu_bytes=physical, declared_budget_bytes=24*gib,
                                 services=services)
            plans.append(plan.model_dump())
            estimates[plan.plan_hash] = {MODEL_ID:qwen, GLM_MODEL_ID:dict(glm,
                weights_bytes=math.ceil((10.03 if quantized else 17.57)*gib))}
            labels[plan.plan_hash] = f'qwen-{qwen_gib}-glm-{glm_gib}-' + ('fp8' if quantized else 'bf16-estimate-only')
    cases = load_cases(ROOT/'benchmarks/easy_cases.json')
    formats = [response_format_for_prompt(case['prompt']) for case in cases]
    manifest = dict(schema_version='sera-placement-rehearsal-v1', plans=plans,
        memory_estimates=estimates, isolated_references={}, concurrency=[1, 2, 4, 8],
        provider_check='/marimo/sera-evidence/provider-luna-expanded-v1/result.json',
        weave_project='vvennela-n-a/wandb_agent_default_project',
        response_formats={MODEL_ID:formats, GLM_MODEL_ID:formats}, response_format_version=PROFILE_VERSION)
    sources = ['evidence/glm-preparation-v1/result.json',
        'evidence/glm-bf16-v1/runtime/server.log', 'evidence/glm-fp8-weights-v1/runtime/server.log',
        'evidence/qwen-structured-quality-v3/runtime/server.log']
    registration = dict(physical_gpu_uuid='GPU-3119bd7a-a9d8-bbf2-2dc3-f5954d41e7e9',
        plan_labels=labels, source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources},
        process_reserve_basis='Prior pressure samples exceeded the requested vLLM budget by 880–894 MiB; reserve 1 GiB inside each allocation.',
        estimate_scope='Prior startup weights/workspace rounded up, plus explicit KV, process, and fragmentation estimates; not a measured fit guarantee.',
        kv_scope='One 4096-token BF16 KV sequence: 2 * layers * KV heads * head dimension * 2 bytes * 4096. This is not eight full-context requests.',
        hardware_scope='24 GiB declared budget on a physical 97887 MiB GPU; not a smaller card speed simulation.',
        counterfactual_scope='BF16 counterparts retain the same allocations and all settings except weight quantization. Reject by estimate; do not launch an unsafe BF16 pair.',
        thresholds_frozen_before_measurement=True)
    for name, value in [('manifest.json',manifest), ('registration.json',registration)]:
        with (folder/name).open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
    print(json.dumps({'plans':labels, 'manifest':str(folder/'manifest.json')}))


if __name__ == '__main__':
    main()
