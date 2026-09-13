# Updated final wheel: cleanup safety fix

Clean installation passes after source `9fb085116aae3e9e29d250308834a061b0adcb6d`
adds the GPU-process ownership safety fix. An unresolved GPU PID can no longer
be treated as proof that cleanup finished. This record does not replace v1.

- Package: `sera-inference` **0.2.0**.
- Wheel SHA-256: `27d3abc04afe55423538f93aa41104e6085ffe1b49cdd7a86534daed1b4f348f`.
- Validation checkout: `4593281c81def8b066fa043952f511fc175005d7`, with the same
  source tree as `9fb0851`: `551cd7d609c628ee9223fa63279405bafcbde9ba`.
- All **66 packaged Python files** match the source bytes.
- Fresh Python **3.11.15**, macOS base and swarm installs pass dependency checks.
  They resolve **9** and **68** packages, respectively.
- Isolated base import needs no Weave, OpenAI, vLLM, Torch, or repository modules.
- Both installed environments pass SQLite roundtrip, exclusive ownership, and
  pre-baseline recovery rejection checks.
- Installed swarm API smoke and provider-check CLI help pass outside the checkout.
- The focused source suite, including the cleanup safety tests, passes **108 tests**.

[result.json](result.json) records exact commands, outputs, dependencies, source
identity, wheel identity, and temporary paths. The checks reuse the unchanged
[v1 audit script](../final-package-release-v1/audit.py):

```sh
python /path/to/final-package-release-v1/audit.py \
  --source /path/to/clean-9fb0851-checkout \
  --expected-source 9fb085116aae3e9e29d250308834a061b0adcb6d
```

No GPU, provider, or Weave service calls occurred. Service boundaries are stubbed
in the installed API smoke. This is not a passing joint-placement run, live
outage recovery, CUDA compatibility test, or production certification. The
gVisor GPU-accounting issue still requires an explicit accounting contract.
