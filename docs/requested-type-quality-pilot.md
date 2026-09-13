# One requested-type decoding pilot

Hypothesis: a schema that follows each task's requested output type can prevent
the observed array-of-objects error without supplying an answer. The previous
Qwen3-0.6B structured run passed 7/8 tasks. Its filtering response returned objects
instead of the requested IDs. That failure remains unchanged in saved evidence.

Run exactly one new BF16 profile, all eight original tasks, one request per task:

```bash
python -m experiments.run_structured_quality_pilot \
  --model-id Qwen/Qwen3-0.6B --requested-types --output-dir NEW_DIRECTORY
```

Profile: `sera-easy-requested-types-v1`. The six integer requests use an integer
schema; the string request uses a string schema. The ID-array request uses an
array of strings because the input records explicitly supply string IDs.
The decoder receives only the prompt, never `expected`, rationale, or case ID.
It does not evaluate the filter, list permitted IDs, or constrain array length.

Tasks, system prompt, BF16 weights/KV, generation settings, 64-token limit, and
99% quality floor remain unchanged. No examples, answer repair, or retries are
added. Every payload, raw response, schema, latency, and grade is saved. The old
untyped profile remains the default and retains its original schema/version.

Success requires 8/8 strict task passes, nonempty tokens, normal stop, and successful
cleanup. A well-formed but wrong answer such as `["a","b"]` still fails. A pass
would establish this decoding profile only, not a performance or placement win.
There is no automatic second candidate if it fails and no automatic promotion.
