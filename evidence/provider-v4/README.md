# Expanded schema with explicit output instructions — blocked on citations

Real W&B Inference check with `openai/gpt-oss-20b`, source `064d9a4e6597b0ccc53adfd55ddffdefc6eed3f4`.

- 30/30 first responses passed schema validation; zero retries or truncations.
- Each new control was produced correctly, including a change from a nondefault parent.
- 26/30 evidence-reference checks passed. The complete check failed.
- Four responses cited a configuration field, broad labels such as `baseline metrics`, or prose instead of exact available metric names.
- No GPU trials ran. This record does not authorize agent-controlled execution in the new build.

The only change from provider-v3 was adding the output schema to the system prompt. The schema, cases, token limit, retries, and acceptance thresholds were unchanged. This establishes the observed format improvement, not a general reliability guarantee or a search advantage.

The next proposed change is to constrain citation strings to the available metric names in each request. It is not implemented or tested here; user direction is pending. No evidence rule was relaxed.

[Full record](result.json). [Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09915-9207-7a92-9846-a8a1c5129837).
