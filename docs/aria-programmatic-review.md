# ARIA programmatic access review

## Post-completion-checkpoint recheck

Rechecked the official documentation on 2026-09-13 after writing `completion.md`.
No ARIA or W&B connector is exposed in this session's tool inventory. No account
settings, conversations, automations, or remote jobs were created.

The documented automation can react to a **Weave metric crossing a threshold**
as well as run/artifact events. That supports an optional event-triggered review
after Sera records a result; it is not proof of an integrated feedback loop.
Execution history exposes a conversation identifier, not a completed typed answer.
[ARIA event and conversation documentation](https://docs.wandb.ai/models/automations/create-automations/aria).

The Python SDK still cannot create or parse ARIA automations. Setup remains in
the W&B UI, and account availability is unverified here.
[Current SDK limitation](https://docs.wandb.ai/models/automations/api).

The next optional proof remains one read-only review of a completed Sera result,
with its exact prompt, answer, citations, and elapsed time saved. Do not enable
automatic GPU execution from that review. The current joint-run blocker is
Molab's per-service memory accounting; adding ARIA does not resolve it.

## Earlier detailed review

Checked 2026-09-13 at Sera revision `71de837`. Research only: no ARIA
conversation, automation, remote job, or account setting was created or changed.

## Result

**There is a supported indirect trigger, but no verified request/response ARIA
adapter in Sera.** A W&B event can start an ARIA conversation after someone
configures the automation in the UI. That does not give Sera a documented API
for retrieving a typed recommendation and continuing its loop.

Keep ARIA optional. Do not replace the working investigators or delay the live
Sera-versus-grid comparison for it.

## What the earlier work actually contains

- Commit `8e072da` added only [ARIA integration notes](aria-integration.md).
  Those notes explicitly say researched, not implemented or account-verified.
- [The older two-phase document](two-phase-loop.md) names `aria/handoff.py`.
  This path is absent from the working tree and the reachable git object paths
  inspected. Treat that sentence as a stale design claim, not working code.
- A search of tracked source, scripts, tests, and ARIA-related git history found
  no ARIA client, browser adapter, or private-endpoint caller.
  This does not establish what happened in an unsaved earlier conversation.
- [The candidate catalog](candidate-catalog.md) proposes ARIA above Sera as a
  later research planner. It records no created ARIA or Launch connection.

## Routes and limits

| Route | What it provides | Present limit |
|---|---|---|
| W&B MCP | Agents query runs and Weave traces, or create reports | Its documented tool list has no invoke-ARIA tool |
| Weave MCP tracing | Records MCP client/server activity | Observability, not access to ARIA as a model |
| ARIA event automation | A configured event starts a chat without a person sending that message | Setup and conversation handling remain UI-based |
| Computer use | A controller operates the signed-in ARIA chat UI | Feasible design, not tested here; depends on UI state and session health |
| Private UI endpoints | An undocumented request path might exist behind the browser | No endpoint or usable contract verified; do not build the demo dependency on it |
| ARIA with W&B Launch | ARIA can submit and monitor experiments | Requires a queue, active Launch agent, and compute integration |

The [W&B MCP tool list](https://docs.wandb.ai/platform/mcp-server) exposes data
and report tools. It does not document an ARIA invocation tool or a way to register
Sera's MCP server inside ARIA. The [Weave MCP guide](https://docs.wandb.ai/weave/guides/integrations/mcp)
describes tracing MCP operations. Neither link proves the reverse connection
`Sera -> ARIA -> typed answer`.

## Best supported indirect option

Configure one narrowly filtered event automation in a team project. Sera can
then publish the matching run or artifact event through the ordinary W&B SDK;
W&B starts ARIA with the configured prompt. This is an event-driven review, not
a synchronous model call. Each execution starts a new chat, so its prompt must
identify the saved evidence. The documented limit is three conversations per
minute per automation. The execution history provides a thread identifier, not
a documented answer-retrieval API. These chats count toward organization usage.
[ARIA automations](https://docs.wandb.ai/models/automations/create-automations/aria)

The Python SDK cannot create or parse ARIA automations; its list calls omit
them. An empty SDK list therefore does not prove the account has none.
[Automation API limits](https://docs.wandb.ai/models/automations/api)

ARIA requires the supported cloud deployment, a team project, and enabled Smart
features. Account availability and ownership of Sera's current project were not
verified in this review. [ARIA overview](https://docs.wandb.ai/aria/overview)

## Smallest useful proof, if approved

1. Confirm ARIA is available in the intended team project. Do not change privacy
   settings to make it available.
2. Use one existing, sanitized experiment digest and its evidence identifiers.
   Request a read-only diagnosis, not job execution or account changes.
3. Save the exact prompt, completed answer, conversation identifier, and elapsed
   time. Check that cited facts match saved measurements.
4. Parse any proposed change with Sera's current typed validator. Reject missing
   evidence and out-of-scope settings. ARIA cannot bypass quality gates or start
   a new GPU trial merely by recommending one.

A manual handoff proves an **ARIA-assisted review**. A computer-use handoff must
be labeled **UI-automated**, with manual fallback. The [chat guide](https://docs.wandb.ai/aria/chat)
supports entering prompts, adding run references, and reopening conversations;
it does not supply an automation reliability guarantee. Do not claim an autonomous
ARIA loop until answer collection and validator handoff have actually succeeded.

Launch is a separate integration: ARIA needs a supplied compute backend, queue,
and active Launch agent. The current Molab subprocess runner is not that agent.
[ARIA autoresearch](https://docs.wandb.ai/aria/autoresearch)

## Demo recommendation

Show the measured Sera loop and its Weave evidence first. If ARIA is available,
use it as an optional closing review of one completed result. Save that response
before presenting. A missing or slow ARIA response must not stop the demo.
No latency estimate is established for ARIA: no ARIA request was made here.
