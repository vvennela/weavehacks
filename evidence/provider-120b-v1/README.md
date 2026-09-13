# GPT-OSS-120B provider contract: passed

Source: `9d3c6e75beecd690adcb8df2053a9be5cb27ff35`.
Provider: W&B Serverless Inference. Model: `openai/gpt-oss-120b`.

All 30 synthetic contract cases passed on the first attempt, with zero retries.
Every parsed response also passed its context check: model/parent identity,
available metric citations, permitted settings, trial budget, or legal selection,
as applicable to its response role. Local `require_provider_check` recomputed
acceptance from the downloaded record successfully.

This is a format and scope check, not proof of factual reasoning, search quality,
GPU performance, or a production reliability rate. No GPU trial ran. The default
investigator model was not changed.

Observed agent-call latency across these 30 synthetic cases: minimum 2.28 s,
mean 8.37 s, maximum 15.62 s. This is provider-call latency, not Qwen workload
latency. The recorded total token usage is 32,159; this is not a cost estimate.

Command used in the prepared environment:

```sh
python -m sera.provider_check \
  --project vvennela-n-a/wandb_agent_default_project \
  --model openai/gpt-oss-120b \
  --output-dir /marimo/sera-evidence/provider-120b-v1
```

Both saved files match the remote byte hashes:

- `result.json`: `b05f385b3c38c8333cf111988ddd25db184e9c6930f412729c752a86b4b98ebd`
- `console.log`: `2607a0810813eb5c12f8bf363e79e5c4c06888bbad8fb3f6db2e698986ad1a12`

Use this certificate only with the matching model, project, and schema. The
separate saved-failure replay tests the investigator explanations and decisions.
