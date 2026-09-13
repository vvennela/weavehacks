# Joint placement stopped at the task gate

The specified pair is Qwen3-0.6B plus GLM-4-9B. These isolated prerequisite checks used the unchanged eight questions, existing system prompt, strict JSON evaluator, 0.99 floor, and serial measurement. They did not run two models together or choose a smaller-card memory budget.

| Configuration | Runtime requests | Strict tasks passed | Cleanup |
| --- | --- | --- | --- |
| GLM BF16 weights / BF16 KV | Completed | 0/8 | Passed |
| GLM FP8 weights / BF16 KV | Completed | 0/8 | Passed |
| Qwen0.6B FP8 weights / BF16 KV | Completed | 1/8 | Passed |

GLM BF16 returned the correct eight values inside Markdown code fences, contrary to the required raw JSON format. GLM FP8 also failed formatting on every case; its filtering output additionally had malformed closing text. Qwen FP8 returned six correct values in code fences, one correct raw JSON answer, and an incorrect filtering answer containing both records as objects. Accepting code fences alone would not make the whole pair pass.

The earlier Qwen BF16 strict check passed 2/8, so no tested configuration of the specified small-model pair satisfies the current task contract. None of these quality failures establishes that a kernel is broken or that every task is unreliable. They establish failure on this declared workload and format.

The two GLM precision paths loaded and generated through the pinned runtime on sm_120. This is compatibility evidence, not accepted deployment. GLM FP8 KV and combined FP8 weights/KV remain unverified and disabled for placement claims.

**Decision: no joint trial; verified placement is blocked.** Keep the working single-model Qwen72B demo. Do not lower the floor, discard failing questions, repair saved answers, or change the model pair without a new explicit user decision. A revised workload would be a separate experiment, not a rewrite of these results.

Implementation source: `c4a914c074ceea59564ae2053d05c217c76deca3`. The wrapper's `status: complete` means the checks finished, not that placement passed. `joint_trial_started` is false. Model-specific records and raw logs are in the sibling `glm-bf16-v1`, `glm-fp8-weights-v1`, and `qwen-fp8-placement-quality-v1` directories. Each result contains its Weave trace link. GPU memory returned to 0 MiB after every check.
