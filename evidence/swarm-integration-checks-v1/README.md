# Swarm integration checks

These checks used the real hosted agent and read real persisted Weave records from the earlier team run. They did not run a new GPU experiment and do not prove multiple measured iterations.

The completed check used source `61aad6c9e8b08aea4de595963f3aabe3400ef00e`. [Open its trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09a30-bee0-7e4b-9b08-3c0db956c64c).

- Three isolated investigators chose inspections. All completed reads used remote Weave records.
- Initial investigations overlapped. Peer reviews also overlapped and received the same findings-board hash.
- Initial proposals included batch tokens 2048 and context 256. The arbiter selected context 256 after peer review; this replay did not execute it.
- Thirteen agent requests produced thirteen valid responses after fifteen provider attempts. Two attempts needed the existing retry.
- No inspection was marked degraded, and no trace export failure was reported.

The explanations were not uniformly sound. One response incorrectly said the baseline already met the relative improvement target. Some hypotheses treated high reserved memory or a lower context cap as evidence of less work. These statements are not measured findings. The deterministic gates remain authoritative, and this check does not establish reliable causal diagnosis.

The preceding console logs are preserved:

1. The first check was stopped after discovering that Weave's boxed values needed conversion to native JSON values.
2. The second check stalled while the reader called global `flush()` inside an unfinished trace. It was stopped.
3. The diagnostic repeat captured thread stacks showing that flush waiting for unfinished calls while the parent waited for the reader. It was stopped.
4. After removing the mid-trace flush and adding bounded visibility checks, the smoke completed normally.

The standalone script is an archived Molab replay, with the original remote paths. Its trace inspection reads the older team trace; do not confuse that source trace with this replay's trace. The JSON result hash is `2ecc4c054feac07b05eb1f6d26859138325118e36031b5b8ac2c0bda269f02dc`. Console files were copied as text.
