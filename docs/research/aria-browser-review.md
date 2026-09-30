# ARIA browser review

Checked 2026-09-13. Optional advisor only; no advice executed.

## Authenticated UI test

Native Arc opened the existing signed-in W&B project. ARIA's new-chat control
and composer worked. After explicit user approval for the private trace URL,
one read-only review was submitted. The completed answer was observed within
49 seconds of clicking Send. This is visible UI automation, not headless.

The answer was captured from the rendered UI. Its JSON text was visually
complete, but W&B's Markdown renderer incorrectly extended a URL link across
several following fields. Automatic raw JSON extraction was not tested. ARIA
also emitted a progress sentence outside the requested JSON. No settings,
automations, reports, or experiments were requested or created through this test.

### Exact prompt

> Read-only Sera review feasibility check. Inspect only this completed Weave call in this project: https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09bce-654d-71f2-aaf4-3accd0872b4e . Do not launch experiments, change settings, create reports or automations, or modify project memory. Return ONLY one JSON object with keys evidence_access (readable or unavailable), evidence_refs (list), observed_result (string), unsupported_claims (list), recommendation (string), and advisory_only (true). Identify whether this evidence alone supports a performance improvement; distinguish observations from missing measurements. If you cannot read this exact call, say unavailable and do not infer its contents. No further questions.

### Completed answer

Transcribed from the rendered UI; formatting added, wording retained:

```json
{
  "evidence_access": "readable",
  "evidence_refs": [
    "https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09bce-654d-71f2-aaf4-3accd0872b4e",
    "selected_plan_id:ce12ce3d0586bf045759ce2e4e69b265cfc76e73c0fa6021a018f298d6c28a23",
    "workload_hash:a708ff95ce839715db79ef4426b9bb6a879cc92f183b8c90e6fba9b9b4f39065"
  ],
  "observed_result": "The call completed successfully and selected a quantization-enabled placement using fp8_per_tensor for GLM-4-9B. It records a measured passing peak of 20,870,856,704 bytes against a declared 25,769,803,776-byte budget, leaving 4,898,947,072 bytes of headroom, with isolated quality 1.0 and zero generation errors for both services. However, the call explicitly reports measured_memory_savings_bytes as null, joint_measurement_status as not-tested, contention_cause as not-established, and the otherwise-matching BF16 rejection as estimate-based rather than measured. Therefore, this evidence alone supports placement feasibility under the declared budget, not a measured performance improvement or the objective's minimum 5% improvement.",
  "unsupported_claims": [
    "A measured performance improvement of at least 5%",
    "Measured memory savings relative to an otherwise-matching BF16 baseline",
    "Improved throughput or latency relative to baseline",
    "Acceptable joint-service latency or contention behavior",
    "Measured joint BF16 infeasibility",
    "That configured vLLM allocations were verified as hard memory caps",
    "Global optimality of the selected placement"
  ],
  "recommendation": "Treat the selected plan as a feasible trial candidate only, not as evidence of improvement. Approval of a performance-improvement claim requires matched baseline-versus-candidate joint measurements for peak memory and relevant latency/throughput, with quality and generation-error constraints checked under the same workload.",
  "advisory_only": true
}
```

### Evidence audit

The plan ID, workload hash, peak, budget, and headroom match
`evidence/live-placement-total-v1/result.json`. The claim that measured
improvement is not established is supported: the matching BF16 alternative was
rejected by an estimate, not measured.

The joint-latency conclusion is incomplete. The exported exact root call in
`evidence/live-placement-total-v1/weave-calls-normalized.json` omits `trials`
and final joint gates. It retains historical
`rounds[0].evidence.proposals[0].joint_measurement_status = "not-tested"`.
ARIA read this real field as current outcome. The saved final result contains
passing joint p95 gates: Qwen 138.78 ms and GLM 177.93 ms. Therefore this answer
must not be accepted as a complete verdict on the experiment. It exposes an
evidence projection problem: send authoritative final results separately from
proposal history. This review concerns that older passing run only, not later
installed-wheel repetitions or the ongoing direct-API run.

## Optional advisor boundary

Sera already calls `agent.review(feedback)` and validates typed proposals and
arbiter decisions in `sera/agent.py`. This ARIA answer is neither type. Treat it
as optional evidence for the existing arbiter, never as execution permission.

A useful request contains the final outcome and timestamp, immutable evidence
IDs, plan and workload hashes, measured metrics and gate results, comparison
scope, and explicitly separate historical proposals. A response contains cited
claims, missing evidence, and advisory recommendations. Validate citations and
output shape. Timeout, login expiry, incomplete output, and rejected advice must
leave the trial budget and execution path unchanged. No adapter was implemented.

## Supported interfaces and Selenium setup

[ARIA chat](https://docs.wandb.ai/aria/chat) documents UI interaction.
[ARIA event automations](https://docs.wandb.ai/models/automations/create-automations/aria)
can start a conversation; they do not establish a typed answer retrieval API.
The [Python SDK cannot manage ARIA automations](https://docs.wandb.ai/models/automations/api).
No private endpoint was inspected or used.

[Selenium Chrome options](https://www.selenium.dev/documentation/webdriver/browsers/chrome/)
and [ChromeDriver profiles](https://developer.chrome.com/docs/chromedriver/capabilities)
support a dedicated browser setup. Use an independent profile, complete normal
login there, then verify a headless restart. Do not copy Arc cookies or attach to
an unconfigured session. Initial diagnostics found only Arc in `/Applications`,
no Selenium in the project environment, no drivers on PATH, and no running
browser debugging session. The isolated smoke below does not change project
dependencies or the existing Arc profile.

### Actual headless Selenium smoke

Passed using Selenium from an isolated `uv run --no-project --with selenium`
environment and Chrome for Testing 153.0.8010.36 downloaded by Selenium Manager.
The profile and browser cache were under `/tmp/sera-aria-selenium.tt36PR`.
Chrome ran with `--headless=new` and a separate `--user-data-dir`.

The first navigation reached `https://wandb.ai/login` in 29.96 seconds including
browser setup. Its first DOM snapshot contained the login shell. A second
read-only navigation with an explicit wait for login inputs reached the normal
W&B Auth0 login page in 3.44 seconds. The title was `Sign In with Auth0`, and the
DOM contained email and password inputs. Authentication query parameters are
intentionally omitted from this report. No credentials were entered and no
login was attempted. Each process called `driver.quit()` in `finally`.

This proves real headless browser startup and W&B login navigation. It does not
prove authenticated headless ARIA chat, login persistence, answer extraction, or
orchestrator handoff. The remaining prerequisite is normal login in the
independent browser profile, followed by a headless session check. Selenium is
a good optional advisor transport to develop; the complete integration remains
untested and must not block Sera.
