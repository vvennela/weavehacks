"""Run trials against a real vLLM server.

This is the other half of the substrate seam. Everything above it — specialists,
arbiter, gates, both phases — is unchanged; only the source of the numbers differs,
and every ledger row records which source produced it.

Three details carry most of the correctness:

  - Arrival times come from the trace, not from when the client managed to send. If
    send-time were used, client-side lag under load would vanish from the measurement
    and a vLLM row would no longer be comparable to a simulator row at the same seed.
  - Tenants are replayed CONCURRENTLY from a single t0. Serializing them would destroy
    the contention Phase 2 exists to observe.
  - Memory bandwidth is reported as None, not zero. vLLM exposes no such metric, and
    zero would read to the quantization specialist as "bandwidth is idle".

Standard library only, so importing this module never fails on a laptop. The vLLM
process launcher is the only part that needs vLLM installed, and it is not reached
unless a trial actually runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

from ..config import DTYPE_BYTES, InferenceConfig, kv_cache_gb_per_token, weights_gb
from ..ledger import Measurement, Substrate
from ..loadgen import Request, RequestResult, generate_trace, summarize
from ..spec import GpuSpec, ModelSpec
from .base import Tenant, TrialOutcome, TrialRunner
from .fake_vllm import (
    METRIC_GENERATION_TOKENS,
    METRIC_KV_USAGE,
    METRIC_KV_USAGE_LEGACY,
    METRIC_PREEMPTIONS,
)

HEALTH_TIMEOUT_S = 300.0
REQUEST_TIMEOUT_S = 300.0
WARMUP_CAP = 16

# vLLM accepts these as --quantization. Everything else in the lever space needs a
# differently-quantized checkpoint, which is a different model repo, not a flag.
VLLM_QUANTIZATIONS = {"fp8", "awq", "gptq"}
DTYPE_FLAGS = {"bf16": "bfloat16", "fp16": "float16", "fp32": "float32"}


class UnsupportedConfig(RuntimeError):
    """The configuration is legal on paper but this backend cannot serve it."""


# --------------------------------------------------------------------------
# Configuration -> server flags. Pure, so it is testable with no server at all.
# --------------------------------------------------------------------------


def vllm_flags(
    model: ModelSpec,
    cfg: InferenceConfig,
    gpu: GpuSpec,
    port: int,
    n_tenants: int = 1,
) -> list[str]:
    """Translate an InferenceConfig into `vllm serve` arguments.

    Raises UnsupportedConfig for lever values the validator allows but vLLM cannot
    serve from a bf16 checkpoint. Failing loudly here is the point: silently serving
    bf16 when the trial asked for int4 would put a fabricated row in the ledger.
    """
    if cfg.weight_dtype not in DTYPE_FLAGS and cfg.weight_dtype not in VLLM_QUANTIZATIONS:
        raise UnsupportedConfig(
            f"weight_dtype={cfg.weight_dtype} needs a pre-quantized checkpoint; vLLM "
            f"can apply only {sorted(VLLM_QUANTIZATIONS)} to a {model.base_dtype} repo"
        )
    if cfg.kv_cache_dtype not in ("bf16", "fp16", "fp8"):
        raise UnsupportedConfig(f"kv_cache_dtype={cfg.kv_cache_dtype} is not a vLLM KV dtype")

    args = [
        "vllm", "serve", model.hf_id,
        "--served-model-name", cfg.model,
        "--revision", model.revision,
        "--port", str(port),
        "--host", "127.0.0.1",
        "--max-model-len", str(model.max_model_len),
        "--max-num-seqs", str(cfg.max_num_seqs),
        "--max-num-batched-tokens", str(cfg.max_num_batched_tokens),
        "--tensor-parallel-size", str(cfg.tensor_parallel_size),
        "--pipeline-parallel-size", str(cfg.pipeline_parallel_size),
        # NOTE: --disable-log-requests was removed from vLLM and replaced by
        # --enable-log-requests, which already defaults to False. Passing the old flag
        # makes the server fail to start, so pass neither.
    ]

    # vLLM's --gpu-memory-utilization is a fraction of the WHOLE card, not of this
    # service's share. Two co-tenants each asking for 0.9 would try to reserve 180%
    # of the device and the second would fail to start.
    args += ["--gpu-memory-utilization", f"{cfg.gpu_memory_utilization / n_tenants:.4f}"]

    if cfg.weight_dtype in DTYPE_FLAGS:
        args += ["--dtype", DTYPE_FLAGS[cfg.weight_dtype]]
    else:
        args += ["--quantization", cfg.weight_dtype]

    args += ["--kv-cache-dtype", "fp8" if cfg.kv_cache_dtype == "fp8" else "auto"]

    if cfg.enable_chunked_prefill:
        args.append("--enable-chunked-prefill")

    return args


# --------------------------------------------------------------------------
# Prometheus parsing
# --------------------------------------------------------------------------


def parse_prometheus(text: str) -> dict[str, float]:
    """Pull the last value of each metric out of Prometheus text exposition.

    Labels are discarded: a single-model server emits one series per metric, which is
    all this needs. Comment lines and unparseable values are skipped rather than
    raising, because a metrics endpoint that grew a new field should not fail a trial.

    Known limitation: repeated sample names collapse to the last one seen, so a
    histogram's `_bucket` series is not usable from this dict. `_sum` and `_count`
    are distinct names and survive, which is all the runner reads.
    """
    out: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, rest = line.partition("{")
        if rest:
            _, _, value = rest.partition("}")
        else:
            name, _, value = line.partition(" ")
        try:
            out[name.strip()] = float(value.strip())
        except ValueError:
            continue
    return out


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


def _post_stream(url: str, payload: dict, timeout: float) -> tuple[float, float, int]:
    """POST a streaming completion. Returns (first_token_monotonic, done_monotonic, tokens).

    Time-to-first-token is the gap to the first chunk carrying text, so the
    connection and header round-trip are included — which is what a client actually
    experiences.
    """
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, body, {"Content-Type": "application/json"}, method="POST"
    )
    first: float | None = None
    tokens = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or [{}]
            if choices[0].get("text") or choices[0].get("delta", {}).get("content"):
                tokens += 1
                if first is None:
                    first = time.monotonic()
    done = time.monotonic()
    return (first if first is not None else done), done, tokens


def _get(url: str, timeout: float = 5.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode()


def _wait_healthy(base_url: str, timeout_s: float) -> bool:
    """Poll /health until the server answers 200 or the deadline passes."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2.0) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            pass
        time.sleep(0.05)
    return False


# --------------------------------------------------------------------------
# Launching
# --------------------------------------------------------------------------


@dataclass
class Endpoint:
    """A reachable vLLM-compatible server for one tenant."""

    base_url: str
    served_model_name: str


Launcher = Callable[[Tenant, GpuSpec, int, int], "Iterator[Endpoint]"]


@contextmanager
def managed_vllm(tenant: Tenant, gpu: GpuSpec, port: int, n_tenants: int) -> Iterator[Endpoint]:
    """Start `vllm serve` as a child process and stop exactly that process after."""
    args = vllm_flags(tenant.model, tenant.config, gpu, port, n_tenants)
    proc = subprocess.Popen(
        args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={**os.environ, "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", "0")},
    )
    try:
        yield Endpoint(f"http://127.0.0.1:{port}", tenant.config.model)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


# --------------------------------------------------------------------------
# The runner
# --------------------------------------------------------------------------


class VllmRunner(TrialRunner):
    """Deploy, warm, load-test, measure, tear down — against real vLLM servers."""

    substrate = Substrate.VLLM

    def __init__(self, launcher: Launcher | None = None, base_port: int = 8100):
        # Deliberately inert. select_runner() catches only ImportError, so anything
        # that can fail belongs in available() or run(), never here.
        self.launcher = launcher or managed_vllm
        self.base_port = base_port
        self.host = os.environ.get("SERA_VLLM_HOST", "")

    def available(self) -> bool:
        """True when a server is reachable, or when vLLM could be launched."""
        if self.host:
            try:
                return _wait_healthy(self.host.rstrip("/"), timeout_s=3.0)
            except Exception:  # noqa: BLE001 - availability must never raise
                return False
        try:
            subprocess.run(
                ["vllm", "--version"], capture_output=True, timeout=10, check=True
            )
            return True
        except Exception:  # noqa: BLE001
            return False

    # -- load replay ---------------------------------------------------------

    def _replay(
        self, endpoint: Endpoint, trace: list[Request], t0: float
    ) -> tuple[list[RequestResult], int]:
        """Fire the trace at one endpoint on the shared clock. Returns (results, errors)."""
        results: list[RequestResult] = []
        errors = 0
        url = f"{endpoint.base_url}/v1/completions"

        def fire(req: Request) -> RequestResult | None:
            # Wait until this request's scheduled arrival. Sleeping to an absolute
            # deadline keeps the offered load honest even if earlier sends were slow.
            delay = (t0 + req.arrival_s) - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            payload = {
                "model": endpoint.served_model_name,
                "prompt": "word " * req.input_tokens,
                "max_tokens": req.output_tokens,
                # Without this the model stops at EOS and a decode-heavy workload
                # quietly becomes a prefill-heavy one.
                "ignore_eos": True,
                "min_tokens": req.output_tokens,
                "stream": True,
                "temperature": 0.0,
            }
            try:
                first, done, tokens = _post_stream(url, payload, REQUEST_TIMEOUT_S)
            except Exception:  # noqa: BLE001 - a failed request is data, not a crash
                return None
            return RequestResult(
                request_id=req.request_id,
                # Scheduled arrival, NOT send time.
                arrival_s=req.arrival_s,
                first_token_s=first - t0,
                completion_s=done - t0,
                output_tokens=tokens,
            )

        workers = max(8, min(256, len(trace)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for res in pool.map(fire, trace):
                if res is None:
                    errors += 1
                else:
                    results.append(res)
        return results, errors

    # -- entry point ---------------------------------------------------------

    def run(self, tenants: list[Tenant], gpu: GpuSpec, seed: int = 0) -> TrialOutcome:
        from .sim_runner import _stable_seed  # same trace for the same seed

        if not tenants:
            return TrialOutcome({}, self.substrate, ok=False, error="no tenants")

        try:
            for t in tenants:
                vllm_flags(t.model, t.config, gpu, 0, len(tenants))
        except UnsupportedConfig as exc:
            return TrialOutcome({}, self.substrate, ok=False, error=str(exc))

        traces = {
            t.model.name: generate_trace(t.workload, seed=seed + _stable_seed(t.model.name))
            for t in tenants
        }

        from contextlib import ExitStack

        with ExitStack() as stack:
            endpoints: dict[str, Endpoint] = {}
            for i, t in enumerate(tenants):
                try:
                    ep = stack.enter_context(
                        self.launcher(t, gpu, self.base_port + i, len(tenants))
                    )
                except Exception as exc:  # noqa: BLE001
                    return TrialOutcome(
                        {}, self.substrate, ok=False,
                        error=f"{t.model.name}: could not start server: {exc}",
                    )
                if not _wait_healthy(ep.base_url, HEALTH_TIMEOUT_S):
                    return TrialOutcome(
                        {}, self.substrate, ok=False,
                        error=f"{t.model.name}: server never became healthy",
                    )
                endpoints[t.model.name] = ep

            before = {
                n: parse_prometheus(_get(f"{ep.base_url}/metrics"))
                for n, ep in endpoints.items()
            }

            # Warm-up, per tenant, excluded from the measurement.
            for t in tenants:
                ep = endpoints[t.model.name]
                warm = traces[t.model.name][:WARMUP_CAP]
                self._replay(ep, [Request(0.0, r.input_tokens, min(r.output_tokens, 8), -1)
                                  for r in warm], time.monotonic())

            # Every tenant replays from ONE t0, concurrently. This is the only way
            # co-tenancy shows up in the numbers.
            t0 = time.monotonic()
            with ThreadPoolExecutor(max_workers=len(tenants)) as pool:
                futures = {
                    t.model.name: pool.submit(
                        self._replay, endpoints[t.model.name], traces[t.model.name], t0
                    )
                    for t in tenants
                }
                replayed = {n: f.result() for n, f in futures.items()}
            wall = time.monotonic() - t0

            after = {
                n: parse_prometheus(_get(f"{ep.base_url}/metrics"))
                for n, ep in endpoints.items()
            }

        measurements: dict[str, Measurement] = {}
        notes: dict[str, str] = {}
        for t in tenants:
            name = t.model.name
            results, errors = replayed[name]
            b, a = before[name], after[name]

            kv = _kv_usage(a)
            preempts = int(a.get(METRIC_PREEMPTIONS, 0.0) - b.get(METRIC_PREEMPTIONS, 0.0))
            gen_tokens = a.get(METRIC_GENERATION_TOKENS, 0.0) - b.get(
                METRIC_GENERATION_TOKENS, 0.0
            )

            # Footprint from the same arithmetic the validator and the fit check use,
            # because vLLM reports RESERVED memory (gpu_memory_utilization x total),
            # not used — feeding that in would make every config identical on the
            # memory axis and collapse the Pareto frontier to a single point.
            footprint = weights_gb(t.model, t.config) + kv_cache_gb_per_token(
                t.model, t.config
            ) * kv * _kv_capacity_tokens(t.model, t.config, gpu, len(tenants))

            m = summarize(
                results,
                footprint_gb=footprint,
                kv_occupancy=kv,
                # Not measurable from vLLM. None means unknown, never idle.
                mem_bandwidth_util=None,
                wall_time_s=wall,
            )
            m.preemptions = max(0, preempts)
            measurements[name] = m
            notes[name] = (
                f"errors={errors} requests={len(results)}/{len(traces[name])} "
                f"gen_tokens={gen_tokens:.0f}"
            )

        return TrialOutcome(
            measurements=measurements, substrate=self.substrate, ok=True, notes=notes
        )


def _kv_usage(metrics: dict[str, float]) -> float:
    """KV-cache occupancy, tolerating the V0/V1 rename.

    vLLM V1 renamed `vllm:gpu_cache_usage_perc` to `vllm:kv_cache_usage_perc`. Reading
    only one spelling against the other server silently yields 0.0, and the loop then
    believes the cache is permanently empty — so try both and only fall back to zero when
    neither is present.
    """
    for name in (METRIC_KV_USAGE, METRIC_KV_USAGE_LEGACY):
        if name in metrics:
            return metrics[name]
    return 0.0


def _kv_capacity_tokens(
    model: ModelSpec, cfg: InferenceConfig, gpu: GpuSpec, n_tenants: int
) -> float:
    """Tokens of KV this service could hold, for turning an occupancy ratio into GB."""
    share = gpu.usable_vram_gb / n_tenants
    budget = share * cfg.gpu_memory_utilization - weights_gb(model, cfg)
    per_token = kv_cache_gb_per_token(model, cfg)
    return max(0.0, budget / per_token) if per_token > 0 else 0.0
