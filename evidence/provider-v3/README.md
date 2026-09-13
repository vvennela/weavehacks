# Expanded schema provider check — failed

This is a real W&B Inference format check using `openai/gpt-oss-20b`, not GPU or search evidence.

- Source: `78c44da022cf742bb727f5d30c1b962e673bc28e`.
- 30 requests completed; 28 first responses passed schema validation.
- 29/30 passed within one retry each; two retries were used.
- 24/30 evidence-reference checks passed. Unsupported controls and unavailable metric citations were rejected.
- The sequence-control response reached the 2,048-token limit in both attempts.
- No GPU trials ran. This record cannot enable the expanded schema.

The raw responses show confusion between the input evidence and the required output fields. The schema was sent through `response_format` but not included in the prompt. The next bounded check adds the same schema to the prompt; it keeps the schema, cases, token limit, retry limit, and acceptance thresholds unchanged. This is a tested diagnosis, not a claim that the next check will pass.

[Full record](result.json). [Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09911-e732-75d6-9cb4-34c9baef983f).
