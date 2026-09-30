# ARIA integration options

Status: researched, not implemented or verified in the account. Checked 2026-09-13.

## Documented capabilities

ARIA can analyze runs, recommend experiments, keep project memories, and create reports. It requires a team project in W&B Multi-tenant Cloud with the required Smart features enabled. Do not change organization privacy settings automatically. [Overview](https://docs.wandb.ai/aria/overview)

Multiple ARIA chats can run in parallel. This supports separate specialist conversations in the UI, but does not establish a callable three-agent API. [Chat guide](https://docs.wandb.ai/aria/chat)

W&B can trigger a new ARIA conversation from an event and a configured prompt. Each execution starts a new conversation rather than continuing the previous one. The Python SDK does not support ARIA automations; manage them in the UI. [ARIA automations](https://docs.wandb.ai/models/automations/create-automations/aria), [API limits](https://docs.wandb.ai/models/automations/api)

ARIA can submit experiments through W&B Launch after a queue and active Launch agent exist. A team member must supply the compute backend and credentials. The current direct Molab subprocess runner is not a Launch integration. [Autoresearch setup](https://docs.wandb.ai/aria/autoresearch)

## Proposed bounded first use

Use ARIA to review one saved Sera investigation and propose one next experiment. Keep the existing GPU executor, typed candidate validation, trial budget, task gate, and rollback. Save the exact ARIA prompt, answer, cited evidence, and any subsequent measured outcome. Label a manually transferred recommendation as human-assisted, not an autonomous API integration.

Draft review prompt:

> Review the attached Sera experiment evidence. Do not execute code, launch jobs, change settings, create automations, or modify project memory. Identify which hypothesis was tested, whether the measurements support it, and one useful next experiment within the supplied legal candidate set. State what would refute your recommendation. Keep the model, questions, quality floor, and declared workload unchanged. Missing measurements are unknown; do not invent a speedup or claim that cumulative queue metrics describe one measurement window. Return a recommendation or explicitly say that no useful legal experiment remains.

The next experiment is not authorized by ARIA's answer. Sera must validate it and retain the original experiment budget. A claim of an ARIA-driven improvement requires a real ARIA recommendation and a subsequent measured result, not this plan.
