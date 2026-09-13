# Hosted investigators

Sera can use a trusted OpenAI-compatible endpoint for its investigator agents.
This includes a compatible LiteLLM proxy. The adapter uses the existing OpenAI
client dependency; it does not require a LiteLLM SDK.

This changes the **investigator backend**, not the model under test. The agents
propose experiments. Sera still needs the supported GPU runtime to measure Qwen,
check quality and performance, and return a usable runner. Hosted investigators
do not replace that GPU runtime.

## Keys and model identity

- `SERA_AGENT_API_KEY` authenticates investigator requests to the chosen endpoint.
- `WANDB_API_KEY` authenticates Weave logging and reads. It is still required for
  the configured traced swarm, even when W&B does not host the investigators.
- `SERA_AGENT_MODEL` is the model ID or model alias accepted by that endpoint.
  It is not the Qwen model being optimized.
- `SERA_PROJECT` is the Weave project used by this Sera run.

Supply both keys through the server, notebook, or job secret facility. Do not put
keys in source files, command-line arguments, reports, browser bundles, or URLs.
Do not send the Weave key to the investigator endpoint as its API key unless that
endpoint explicitly requires the same credential.

## Configure one trusted backend

Install the package with its `swarm` extra, as described in the
[release setup](simple-release.md). Set these non-secret values in the process
that runs Sera. Replace the endpoint and model placeholders with approved values:

```sh
export SERA_AGENT_PROVIDER=openai-compatible
export SERA_AGENT_BASE_URL=https://inference.example.com/v1
export SERA_AGENT_MODEL=your-endpoint-model-id
export SERA_PROJECT=your-entity/your-project
unset SERA_RELAY_DIR
```

Inject `SERA_AGENT_API_KEY` and `WANDB_API_KEY` separately as secrets. Then certify
the exact endpoint and model:

```sh
sera-provider-check --provider openai-compatible \
  --base-url "$SERA_AGENT_BASE_URL" \
  --model "$SERA_AGENT_MODEL" --project "$SERA_PROJECT" \
  --output-dir /absolute/path/to/new-provider-check
```

The CLI reads the investigator key from `SERA_AGENT_API_KEY`; it has no key
argument. The check makes real provider requests. Use a new output directory and
wait for a passing result before setting:

```sh
export SERA_PROVIDER_CHECK=/absolute/path/to/new-provider-check/result.json
```

The certificate binds the provider, endpoint fingerprint, model, project, and
current schema checks. Changing the endpoint, model, project, or schema requires
a matching check. A W&B or Codex certificate does not certify this route. A saved
pass flag is not sufficient: Sera validates the certificate contents.

An OpenAI-compatible API is not a guarantee that every model works. The model
must reliably return Sera's strict JSON structures and pass provider validation.
Certification does not prove task quality, correct causal reasoning, or a useful
optimization. Measured task and performance gates still decide acceptance.

After setup, use the same [configured swarm API](simple-release.md) or
[ordered stages](staged-optimization.md). No local Codex controller is needed for
this hosted route.

## Per-user credentials belong on the server

For a service with separate user credentials, create an agent for each request
or job. Pass that user's key to the instance instead of changing shared process
environment variables:

```python
from sera.agent import OpenAICompatibleAgent

agent = OpenAICompatibleAgent(
    project=authorized_weave_project,
    model=approved_endpoint_model_id,
    base_url=approved_endpoint_url,
    api_key=provider_key_from_server_secret_store,
)
```

The names above are server-side values supplied by the application. An explicit
instance key takes precedence; if omitted, the agent reads `SERA_AGENT_API_KEY`.
Pass the agent and its matching certificate to `sera.optimize(..., mode="swarm",
agent=agent, provider_check=certificate_path)` with the normal model, prompts,
quality requirements, and output directory.

Do not reuse a credential-bearing agent across users. Keep each job's output
directory and evidence access separate. The hosting application must authenticate
users, authorize projects and models, enforce spending limits, and protect stored
secrets. Sera's adapter and certificate do not provide a multi-user authorization
or secret-storage system. Configure Weave credentials and project access for each
isolated worker; changing a shared `WANDB_API_KEY` during concurrent jobs is not
user isolation.

## Endpoint and evidence safety

Only the trusted server configuration should choose the HTTPS base URL. Use a
server-side allowlist of approved endpoints. Do not forward arbitrary browser
URLs to the adapter. That can create server-side request forgery: a user causes
the backend to contact an internal service or send credentials to another host.
HTTPS alone does not prevent this. Network access controls and the hosting
application must enforce the allowed destination.

Investigator requests contain experiment evidence, including model outputs and
selected trace information. Send only data authorized for that endpoint. Weave
records and local reports need the same access controls as the underlying task
data. Provider certification is not an endpoint security or privacy audit.

## Existing routes and website scope

The existing `wandb` backend remains available and unchanged. Its inference and
Weave setup uses the W&B route described in the release guide. The `codex-relay`
backend remains a separate local-controller route; naming an Astra Codex agent
does not turn it into a hosted endpoint model ID.

The current website uses the separate `sera_loop` backend. It is not wired to
this measured `sera` investigator adapter. This document does not claim browser
credential handling, website integration, or live certification of any new
hosted model. Those require their own implementation and validation.
