# Direct OpenAI through LiteLLM: first rehearsal

Source: `89030bddae4f4f4336298b1a1e20bf7c62ab96b4`.
Provider: `litellm-openai`; investigator: `gpt-6-astra`.

The separate one-request connection test passed in 3.843 seconds. Weave logging
also passed. The full rehearsal stopped before GPU work: 33 of 34 provider cases
passed, but `proposal-active-gpu_memory_utilization` failed on both attempts.

The responses assigned `gpu_memory_utilization` to `batching`. Sera assigns that
control to `quantization`; local validation correctly rejected both responses.
Removing OpenAI's unsupported root `anyOf` had also removed that role mapping
from the model-visible schema. The next revision must expose the complete role
mapping while preserving the local rules and all provider cases.

No `sera.optimize()` call or GPU trial ran in this attempt. The rehearsal exited
with failure after 167.443 seconds. Cleanup confirmed zero GPU memory in use.
This is a failed provider check, not a failed Qwen quality or performance test.

Remote records:

- `/marimo/sera-evidence/openai-example-v1/invocation.json`
- `/marimo/sera-evidence/openai-example-v1/provider-811e084f183f/result.json`
- `/marimo/sera-evidence/openai-example-v1-console.log`

The launch script contains no credentials. Credentials were supplied through
the runtime environment. Failed records remain unchanged for comparison.
