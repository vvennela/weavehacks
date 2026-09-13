"""Measured latency/throughput baseline against a LIVE vLLM server.

Every number this writes is measured on real hardware. Nothing here is simulated.
Each request carries a unique uuid prefix so vLLM prefix caching cannot turn a
repeat measurement into a cache hit -- the conservative, honest choice.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

BASE = "http://127.0.0.1:8000"
MODEL = "Qwen/Qwen3-8B"
OUT = os.environ.get("BENCH_OUT", "/tmp/live_bench_result.json")
TARGET_INPUT_TOKENS = 1024
MAX_TOKENS = 128
LEVELS = [1, 2, 4, 8]
REQS_PER_LEVEL = 16


def post(path: str, payload: dict, timeout: int = 300):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def ntokens(text: str) -> int:
    return post("/tokenize", {"model": MODEL, "prompt": text})["count"]


def scrape_metrics() -> dict:
    try:
        raw = urllib.request.urlopen(BASE + "/metrics", timeout=15).read().decode()
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)}
    out = {}
    for line in raw.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        name, _, val = line.rpartition(" ")
        key = name.split("{")[0]
        if key in (
            "vllm:gpu_cache_usage_perc",
            "vllm:num_requests_running",
            "vllm:num_requests_waiting",
            "vllm:num_preemptions_total",
            "vllm:prompt_tokens_total",
            "vllm:generation_tokens_total",
        ):
            try:
                out.setdefault(key, 0.0)
                out[key] = max(out[key], float(val))
            except ValueError:
                pass
    return out


def build_prompt() -> str:
    unit = (
        "A distributed inference service receives bursts of user traffic across many "
        "tenants, and the scheduler must decide how to batch decode steps without "
        "letting tail latency drift past the service objective. "
    )
    text = unit
    while ntokens(text) < TARGET_INPUT_TOKENS:
        text += unit
    return text


def one_request(body_prompt: str) -> dict:
    """Streamed completion. Returns measured TTFT and end-to-end latency in ms."""
    payload = {
        "model": MODEL,
        "prompt": body_prompt,
        "max_tokens": MAX_TOKENS,
        "min_tokens": MAX_TOKENS,
        "ignore_eos": True,
        "temperature": 0.0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    req = urllib.request.Request(
        BASE + "/v1/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    ttft = None
    completion_tokens = 0
    prompt_tokens = None
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line.startswith("data: "):
                continue
            chunk = line[6:]
            if chunk == "[DONE]":
                break
            obj = json.loads(chunk)
            if obj.get("choices") and obj["choices"][0].get("text"):
                if ttft is None:
                    ttft = (time.perf_counter() - t0) * 1000.0
                completion_tokens += 1
            if obj.get("usage"):
                prompt_tokens = obj["usage"].get("prompt_tokens")
                if obj["usage"].get("completion_tokens"):
                    completion_tokens = obj["usage"]["completion_tokens"]
    e2e = (time.perf_counter() - t0) * 1000.0
    return {
        "ttft_ms": ttft,
        "e2e_ms": e2e,
        "completion_tokens": completion_tokens,
        "prompt_tokens": prompt_tokens,
    }


def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def run_level(conc: int, base_prompt: str) -> dict:
    prompts = [f"[req {uuid.uuid4().hex}] " + base_prompt for _ in range(REQS_PER_LEVEL)]
    before = scrape_metrics()
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=conc) as ex:
        results = list(ex.map(one_request, prompts))
    wall = time.perf_counter() - t0
    after = scrape_metrics()
    e2e = [r["e2e_ms"] for r in results]
    ttft = [r["ttft_ms"] for r in results if r["ttft_ms"] is not None]
    gen = sum(r["completion_tokens"] for r in results)
    pro = sum(r["prompt_tokens"] or 0 for r in results)
    return {
        "concurrency": conc,
        "requests": len(results),
        "wall_s": round(wall, 4),
        "e2e_p50_ms": round(pct(e2e, 50), 2),
        "e2e_p95_ms": round(pct(e2e, 95), 2),
        "e2e_p99_ms": round(pct(e2e, 99), 2),
        "e2e_mean_ms": round(statistics.fmean(e2e), 2),
        "e2e_min_ms": round(min(e2e), 2),
        "e2e_max_ms": round(max(e2e), 2),
        "ttft_p50_ms": round(pct(ttft, 50), 2) if ttft else None,
        "ttft_p95_ms": round(pct(ttft, 95), 2) if ttft else None,
        "throughput_rps": round(len(results) / wall, 4),
        "output_tokens_per_s": round(gen / wall, 2),
        "total_tokens_per_s": round((gen + pro) / wall, 2),
        "generated_tokens": gen,
        "prompt_tokens": pro,
        "kv_cache_usage_perc_after": after.get("vllm:gpu_cache_usage_perc"),
        "preemptions_total_after": after.get("vllm:num_preemptions_total"),
        "metrics_before": before,
        "metrics_after": after,
        "raw_e2e_ms": [round(v, 2) for v in e2e],
        "raw_ttft_ms": [round(v, 2) for v in ttft],
    }


def main() -> None:
    nvsmi = subprocess.run(
        ["nvidia-smi"], capture_output=True, text=True
    ).stdout
    nvsmi_csv = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,driver_version,compute_cap,"
            "utilization.gpu,temperature.gpu,power.draw",
            "--format=csv,noheader",
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()

    started = time.time()
    base_prompt = build_prompt()
    input_tokens = ntokens(base_prompt)

    # Warmup, excluded from all reported numbers.
    one_request("[warmup " + uuid.uuid4().hex + "] " + base_prompt)

    levels = []
    for c in LEVELS:
        levels.append(run_level(c, base_prompt))
        with open(OUT, "w") as fh:
            json.dump({"status": "running", "levels": levels}, fh, indent=2)

    result = {
        "status": "complete",
        "substrate": "vllm",
        "measured": True,
        "note": (
            "All latency and throughput figures are measured end-to-end over HTTP "
            "against a live vLLM server on a physical GPU. No simulation."
        ),
        "started_unix": started,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "finished_unix": time.time(),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": MODEL,
        "engine": "vLLM 0.29.0",
        "vllm_flags": {
            "--max-model-len": 4096,
            "--gpu-memory-utilization": 0.85,
            "--dtype": "bfloat16",
            "env": {"VLLM_USE_FLASHINFER_SAMPLER": "0"},
        },
        "gpu": "NVIDIA RTX PRO 6000 Blackwell Server Edition",
        "nvidia_smi_csv": nvsmi_csv,
        "nvidia_smi": nvsmi,
        "workload": {
            "input_tokens_per_request": input_tokens,
            "target_input_tokens": TARGET_INPUT_TOKENS,
            "max_tokens": MAX_TOKENS,
            "min_tokens": MAX_TOKENS,
            "ignore_eos": True,
            "temperature": 0.0,
            "requests_per_level": REQS_PER_LEVEL,
            "concurrency_levels": LEVELS,
            "unique_uuid_prefix_per_request": True,
            "prefix_cache_note": (
                "Each request is prefixed with a fresh uuid so vLLM prefix caching "
                "cannot serve it from cache; these are cold-prefill numbers."
            ),
            "warmup_requests_excluded": 1,
        },
        "levels": levels,
    }
    with open(OUT, "w") as fh:
        json.dump(result, fh, indent=2)
    print("DONE", OUT)


if __name__ == "__main__":
    main()
