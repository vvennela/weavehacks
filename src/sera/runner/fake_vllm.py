"""A fake vLLM server, faithful enough to develop and test the real runner against.

The point is not to simulate inference. It is to present the same HTTP surface a real
vLLM server presents — the OpenAI-compatible completions endpoint with streaming, a
health endpoint, and a Prometheus `/metrics` page — so that `VllmRunner` can be written
and exercised in full without a GPU, without downloading weights, and without vLLM
installed. The specification asks for exactly this: "vLLM process manager against a
fake server" and "Metrics parser against saved vLLM output".

What it fakes:
  - startup delay and a health endpoint that 503s until ready, so the runner's wait
    loop is really exercised rather than trivially satisfied
  - streaming responses, so time-to-first-token is a real measurement of a real gap
  - a token budget shared across in-flight requests, so concurrency genuinely queues
    and the measured latency responds to load instead of being a constant
  - Prometheus counters and gauges under the real vLLM metric names

Standard library only. Nothing here may import vllm, torch, httpx, or requests — the
whole point is that it runs on a laptop with the base dependencies.
"""

from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# Metric names as vLLM actually exposes them, verified against the v0.29 source.
# Kept in one place so a rename is a single edit, and the runner's parser reads the
# same constants — the fake and the parser can never drift apart.
#
# Note the V0 -> V1 renames. Reading the old name against a V1 server returns nothing,
# the parser defaults to 0.0, and the loop then believes the KV cache is permanently
# empty — a silent corruption of the evidence every specialist reasons from. The
# runner therefore accepts either spelling (see KV_USAGE_NAMES).
METRIC_RUNNING = "vllm:num_requests_running"
METRIC_WAITING = "vllm:num_requests_waiting"
METRIC_KV_USAGE = "vllm:kv_cache_usage_perc"            # V1. V0 said gpu_cache_usage_perc
METRIC_KV_USAGE_LEGACY = "vllm:gpu_cache_usage_perc"    # V0, still seen on older servers
METRIC_PREEMPTIONS = "vllm:num_preemptions_total"
METRIC_PROMPT_TOKENS = "vllm:prompt_tokens_total"
METRIC_GENERATION_TOKENS = "vllm:generation_tokens_total"

# Counters are declared without _total; prometheus_client appends it on exposition.
# Every metric carries BOTH labels — `engine` is the engine index — and
# prometheus_client emits label pairs in alphabetical order, so `engine` precedes
# `le` precedes `model_name`.
ENGINE_LABEL = "0"


@dataclass
class FakeEngineProfile:
    """How the fake pretends to perform.

    Defaults are deliberately unremarkable. Tests that care about a specific timing
    set these explicitly rather than relying on whatever the default happens to be.
    """

    # Seconds before /health stops returning 503.
    startup_s: float = 0.05
    # Per-request fixed cost before the first token.
    base_ttft_s: float = 0.010
    # Per-output-token cost once generating.
    tpot_s: float = 0.001
    # Prompt tokens processed per second, so long prompts genuinely cost more.
    prefill_tokens_per_s: float = 200_000.0
    # How many requests the engine will genuinely run at once. Beyond this, requests
    # queue — which is what makes measured latency respond to offered load.
    max_concurrency: int = 8
    # Fraction of KV cache reported in use, per in-flight request.
    kv_per_request: float = 0.02
    # Preemptions reported after this many requests, to exercise the counter delta.
    preempt_every: int = 0
    # If set, the server fails every request with this HTTP status.
    fail_with: int | None = None


@dataclass
class _EngineState:
    started_at: float
    profile: FakeEngineProfile
    lock: threading.Lock = field(default_factory=threading.Lock)
    sem: threading.Semaphore | None = None
    running: int = 0
    waiting: int = 0
    completed: int = 0
    prompt_tokens: int = 0
    generation_tokens: int = 0
    preemptions: int = 0

    @property
    def ready(self) -> bool:
        return time.monotonic() - self.started_at >= self.profile.startup_s

    @property
    def kv_usage(self) -> float:
        return min(1.0, self.running * self.profile.kv_per_request)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # Silence per-request logging; a load test would drown the console.
    def log_message(self, *_args: Any) -> None:  # noqa: D102
        return

    @property
    def state(self) -> _EngineState:
        return self.server.state  # type: ignore[attr-defined]

    # -- helpers ------------------------------------------------------------

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json")

    # -- routes -------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            if self.state.ready:
                self._send(200, b"", "text/plain")
            else:
                self._send(503, b"not ready", "text/plain")
        elif self.path == "/v1/models":
            self._json(200, {"object": "list", "data": [
                {"id": self.server.served_model_name, "object": "model",  # type: ignore[attr-defined]
                 "owned_by": "vllm"}
            ]})
        elif self.path == "/metrics":
            self._send(200, self._render_metrics().encode(), "text/plain; version=0.0.4")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/v1/completions", "/v1/chat/completions"):
            self._send(404, b"not found", "text/plain")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        st = self.state
        prof = st.profile

        if prof.fail_with is not None:
            self._json(prof.fail_with, {"error": {"message": "fake failure",
                                                  "type": "server_error"}})
            return

        prompt = body.get("prompt", "")
        prompt_tokens = len(prompt.split()) if isinstance(prompt, str) else 0
        max_tokens = int(body.get("max_tokens", 16))
        stream = bool(body.get("stream", False))

        with st.lock:
            st.waiting += 1
        assert st.sem is not None
        st.sem.acquire()          # blocks past max_concurrency: real queueing
        with st.lock:
            st.waiting -= 1
            st.running += 1

        try:
            time.sleep(prompt_tokens / prof.prefill_tokens_per_s + prof.base_ttft_s)
            if stream:
                self._stream(max_tokens, prof)
            else:
                time.sleep(max_tokens * prof.tpot_s)
                self._json(200, self._completion_body(prompt_tokens, max_tokens))
        finally:
            with st.lock:
                st.running -= 1
                st.completed += 1
                st.prompt_tokens += prompt_tokens
                st.generation_tokens += max_tokens
                if prof.preempt_every and st.completed % prof.preempt_every == 0:
                    st.preemptions += 1
            st.sem.release()

    # -- response bodies -----------------------------------------------------

    def _completion_body(self, prompt_tokens: int, max_tokens: int) -> dict:
        return {
            "id": "cmpl-fake",
            "object": "text_completion",
            "model": self.server.served_model_name,  # type: ignore[attr-defined]
            "choices": [{"index": 0, "text": "x " * max_tokens,
                         "finish_reason": "length"}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": max_tokens,
                "total_tokens": prompt_tokens + max_tokens,
            },
        }

    def _stream(self, max_tokens: int, prof: FakeEngineProfile) -> None:
        """Server-sent events, first chunk separated from the rest.

        The gap between the first chunk and the request start IS time-to-first-token
        as the runner measures it, so it has to be a real gap rather than everything
        arriving at once.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        for i in range(max_tokens):
            if i:
                time.sleep(prof.tpot_s)
            chunk = {
                "id": "cmpl-fake",
                "object": "text_completion",
                "choices": [{"index": 0, "text": "x",
                             "finish_reason": "length" if i == max_tokens - 1 else None}],
            }
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _render_metrics(self) -> str:
        """Prometheus text exposition, in the shape vLLM v0.29 actually emits."""
        st = self.state
        model = self.server.served_model_name  # type: ignore[attr-defined]
        # Alphabetical label order, both labels present, floats with a decimal point.
        labels = f'{{engine="{ENGINE_LABEL}",model_name="{model}"}}'
        return "\n".join([
            f"# HELP {METRIC_RUNNING} Number of requests currently running on GPU.",
            f"# TYPE {METRIC_RUNNING} gauge",
            f"{METRIC_RUNNING}{labels} {st.running}.0",
            f"# HELP {METRIC_WAITING} Number of requests waiting to be processed.",
            f"# TYPE {METRIC_WAITING} gauge",
            f"{METRIC_WAITING}{labels} {st.waiting}.0",
            f"# HELP {METRIC_KV_USAGE} KV-cache usage. 1 means 100 percent usage.",
            f"# TYPE {METRIC_KV_USAGE} gauge",
            f"{METRIC_KV_USAGE}{labels} {st.kv_usage}",
            f"# HELP {METRIC_PREEMPTIONS} Cumulative number of preemptions from the engine.",
            f"# TYPE {METRIC_PREEMPTIONS} counter",
            f"{METRIC_PREEMPTIONS}{labels} {st.preemptions}.0",
            f"# HELP {METRIC_PROMPT_TOKENS} Number of prefill tokens processed.",
            f"# TYPE {METRIC_PROMPT_TOKENS} counter",
            f"{METRIC_PROMPT_TOKENS}{labels} {st.prompt_tokens}.0",
            f"# HELP {METRIC_GENERATION_TOKENS} Number of generation tokens processed.",
            f"# TYPE {METRIC_GENERATION_TOKENS} counter",
            f"{METRIC_GENERATION_TOKENS}{labels} {st.generation_tokens}.0",
            *self._ttft_histogram(model),
            "",
        ])

    def _ttft_histogram(self, model: str) -> list[str]:
        """A histogram family, with vLLM's real TTFT bucket boundaries.

        Included so the parser is exercised against `_bucket` / `_sum` / `_count`
        sample names and the `le` label, which is where a naive parser breaks.
        """
        st = self.state
        buckets = [0.001, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.1, 0.25, 0.5,
                   0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 20.0, 40.0, 80.0, 160.0, 640.0, 2560.0]
        name = "vllm:time_to_first_token_seconds"
        ttft = st.profile.base_ttft_s
        lines = [
            f"# HELP {name} Histogram of time to first token in seconds.",
            f"# TYPE {name} histogram",
        ]
        for b in buckets:
            n = float(st.completed) if ttft <= b else 0.0
            lines.append(
                f'{name}_bucket{{engine="{ENGINE_LABEL}",le="{b}",model_name="{model}"}} {n}'
            )
        lines += [
            f'{name}_bucket{{engine="{ENGINE_LABEL}",le="+Inf",model_name="{model}"}} '
            f"{float(st.completed)}",
            f'{name}_count{{engine="{ENGINE_LABEL}",model_name="{model}"}} '
            f"{float(st.completed)}",
            f'{name}_sum{{engine="{ENGINE_LABEL}",model_name="{model}"}} '
            f"{st.completed * ttft:.4f}",
        ]
        return lines


class FakeVllmServer:
    """Run a fake vLLM on a loopback port. Use as a context manager."""

    def __init__(
        self,
        served_model_name: str = "fake-model",
        profile: FakeEngineProfile | None = None,
    ):
        self.profile = profile or FakeEngineProfile()
        self.served_model_name = served_model_name
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        assert self._httpd is not None, "server is not started"
        return self._httpd.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> FakeVllmServer:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        httpd.daemon_threads = True
        httpd.state = _EngineState(  # type: ignore[attr-defined]
            started_at=time.monotonic(), profile=self.profile
        )
        httpd.state.sem = threading.Semaphore(self.profile.max_concurrency)  # type: ignore[attr-defined]
        httpd.served_model_name = self.served_model_name  # type: ignore[attr-defined]
        self._httpd = httpd
        self._thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def stats(self) -> dict[str, Any]:
        assert self._httpd is not None
        st = self._httpd.state  # type: ignore[attr-defined]
        return {
            "completed": st.completed,
            "prompt_tokens": st.prompt_tokens,
            "generation_tokens": st.generation_tokens,
            "preemptions": st.preemptions,
        }

    def __enter__(self) -> FakeVllmServer:
        return self.start()

    def __exit__(self, *_exc: Any) -> None:
        self.stop()


# --------------------------------------------------------------------------
# Wiring a fake into the real runner
# --------------------------------------------------------------------------


def profile_for_config(model: Any, cfg: Any, n_tenants: int = 1) -> FakeEngineProfile:
    """Derive a fake engine profile from a real InferenceConfig.

    The fake has to RESPOND to levers, otherwise every candidate measures the same and
    the specialists have nothing to learn from. These relationships are the same ones
    the analytic simulator models — decode cost scales with the bytes of weight read
    per step, concurrency is capped by max_num_seqs — just coarser. They are for
    exercising the runner, not for predicting hardware.
    """
    from ..config import DTYPE_BYTES

    bytes_per_param = DTYPE_BYTES.get(cfg.weight_dtype, 2.0)
    # Decode is bandwidth bound, so halving weight bytes roughly halves per-token cost.
    tpot = 0.0002 * (bytes_per_param / 2.0) * max(1.0, model.params_b)
    return FakeEngineProfile(
        startup_s=0.02,
        base_ttft_s=0.005,
        tpot_s=max(1e-5, tpot / max(1, n_tenants)),
        prefill_tokens_per_s=400_000.0 / max(1, n_tenants),
        max_concurrency=max(1, min(cfg.max_num_seqs, 32)),
        kv_per_request=0.01,
        preempt_every=0,
    )


@contextmanager
def fake_launcher(tenant: Any, gpu: Any, port: int, n_tenants: int):
    """A `Launcher` for VllmRunner that starts a fake instead of real vLLM.

    This is what lets the entire pipeline — Phase 1, Phase 2, gates, ledger — run
    through the real HTTP client path on a laptop with no GPU and no model weights.
    """
    from .vllm_runner import Endpoint

    server = FakeVllmServer(
        served_model_name=tenant.config.model,
        profile=profile_for_config(tenant.model, tenant.config, n_tenants),
    ).start()
    try:
        yield Endpoint(server.base_url, tenant.config.model)
    finally:
        server.stop()
