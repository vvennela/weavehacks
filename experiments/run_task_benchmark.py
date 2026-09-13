def run_task_benchmark(cases, label, system_prompt, kv_cache_dtype="auto"):
    """Collect an ungraded, single-pass task vector on the supplied Molab GPU."""
    import hashlib
    import importlib.metadata
    import json
    import os
    from pathlib import Path
    import signal
    import socket
    import subprocess
    import sys
    import time
    import urllib.error
    import urllib.request

    if kv_cache_dtype not in {"auto", "fp8"}:
        raise ValueError("Only the two smoke-checked cache modes are supported")
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Cases must have unique IDs and cannot be empty")
    for case in cases:
        if not isinstance(case["prompt"], str) or case["max_tokens"] != 128:
            raise ValueError("This pilot requires text prompts and a 128-token limit")

    folder = Path("/marimo/sera-evidence") / label
    folder.mkdir(parents=True, exist_ok=False)
    model_id = "Qwen/Qwen3-0.6B"
    revision = "c1899de289a04d12100db370d81485cdf75e47ca"
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError("The frozen suite must provide its system instruction")
    public_cases = [{key: case[key] for key in ("id", "prompt", "max_tokens")} for case in cases]
    encoded_cases = json.dumps(public_cases, sort_keys=True, separators=(",", ":"))
    record = {
        "schema_version": "sera-task-vector-v1", "label": label,
        "model_id": model_id, "revision": revision, "kv_cache_dtype": kv_cache_dtype,
        "dataset_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
        "workload_hash": hashlib.sha256(encoded_cases.encode()).hexdigest(),
        "cases": public_cases, "system_prompt": system_prompt,
        "generation": {"temperature": 0, "top_p": 1, "top_k": -1, "seed": 0,
                       "max_tokens": 128, "enable_thinking": False},
        "concurrency": 1, "warmup_requests": 2, "measured_passes": 1,
        "versions": {name: importlib.metadata.version(name) for name in
                     ["vllm", "torch", "transformers", "flashinfer-python"]},
        "status": "running", "requests": [],
    }

    def save():
        temporary = folder / "result.pending.json"
        temporary.write_text(json.dumps(record, indent=2))
        temporary.replace(folder / "result.json")

    def memory_mib():
        output = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout
        return int(output.splitlines()[0])

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    command = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_id, "--revision", revision, "--tokenizer-revision", revision,
        "--served-model-name", "sera-tasks", "--host", "127.0.0.1", "--port", str(port),
        "--dtype", "bfloat16", "--kv-cache-dtype", kv_cache_dtype,
        "--tensor-parallel-size", "1", "--max-model-len", "4096",
        "--max-num-seqs", "8", "--max-num-batched-tokens", "4096",
        "--gpu-memory-utilization", "0.90", "--no-enable-prefix-caching",
        "--enable-chunked-prefill", "--enforce-eager", "--generation-config", "vllm",
        "--seed", "0", "--shutdown-timeout", "15",
    ]
    record["command"] = command
    record["gpu"] = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,compute_cap,memory.total,driver_version", "--format=csv"],
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()
    compiler_package = importlib.metadata.distribution("nvidia-cuda-nvcc")
    compiler = next(compiler_package.locate_file(entry) for entry in compiler_package.files if entry.name == "nvcc")
    cuda_home = compiler.parent.parent
    cuda_library = cuda_home / "lib" / "libcudart.so.13"
    if not cuda_library.is_file():
        raise FileNotFoundError(cuda_library)
    link_dir = folder / "cuda-link"
    link_dir.mkdir()
    (link_dir / "libcudart.so").symlink_to(cuda_library)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="0", OMP_NUM_THREADS="2", CUDA_HOME=str(cuda_home))
    env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
    env["LIBRARY_PATH"] = str(link_dir) + os.pathsep + str(cuda_library.parent) + os.pathsep + env.get("LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = str(cuda_library.parent) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    record["cuda_library"] = str(cuda_library)
    before_memory = memory_mib()
    peak_memory = before_memory
    if before_memory > 128:
        raise RuntimeError("GPU is already in use; refusing to start this isolated trial")

    def generate(prompt, max_tokens):
        payload = {
            "model": "sera-tasks",
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            "temperature": 0, "top_p": 1, "top_k": -1, "seed": 0,
            "max_tokens": max_tokens, "chat_template_kwargs": {"enable_thinking": False},
            "return_token_ids": True, "return_prompt_text": True,
        }
        request = urllib.request.Request(
            base_url + "/v1/chat/completions", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=90) as response:
            completion = json.load(response)
        elapsed = time.perf_counter() - started
        choice = completion["choices"][0]
        text = choice["message"].get("content") or ""
        return {
            "text": text, "latency_ms": elapsed * 1000, "usage": completion.get("usage"),
            "finish_reason": choice.get("finish_reason"), "token_ids": choice.get("token_ids"),
            "prompt_token_ids": completion.get("prompt_token_ids"),
            "prompt_text": completion.get("prompt_text"),
            "reasoning": choice["message"].get("reasoning"),
        }

    process = None
    started = time.monotonic()
    save()
    with (folder / "server.log").open("w") as server_log:
        try:
            process = subprocess.Popen(command, env=env, stdout=server_log, stderr=subprocess.STDOUT, start_new_session=True)
            next_update = started
            while time.monotonic() - started < 240:
                if process.poll() is not None:
                    raise RuntimeError(f"Server exited with code {process.returncode}")
                try:
                    with urllib.request.urlopen(base_url + "/health", timeout=2) as health:
                        if health.status == 200:
                            break
                except OSError:
                    pass
                if time.monotonic() >= next_update:
                    peak_memory = max(peak_memory, memory_mib())
                    print(f"{label}: startup {time.monotonic() - started:.0f}s", flush=True)
                    next_update = time.monotonic() + 15
                time.sleep(1)
            else:
                raise TimeoutError("Server startup exceeded 240 seconds")
            record["startup_seconds"] = time.monotonic() - started
            record["warmup_outputs"] = [generate('Return exactly {"answer":0}.', 16) for _ in range(2)]
            for index, case in enumerate(public_cases, start=1):
                try:
                    item = generate(case["prompt"], case["max_tokens"])
                    item.update(id=case["id"], request_error=None)
                except Exception as error:
                    item = {"id": case["id"], "text": "", "request_error": f"{type(error).__name__}: {error}"}
                record["requests"].append(item)
                peak_memory = max(peak_memory, memory_mib())
                save()
                print(f"{label}: {index}/{len(public_cases)} {case['id']} ({item.get('finish_reason', 'error')})", flush=True)
            with urllib.request.urlopen(base_url + "/metrics", timeout=10) as response:
                (folder / "metrics.prom").write_text(response.read().decode())
            record["status"] = "collected" if all(item["request_error"] is None for item in record["requests"]) else "request-errors"
        except Exception as error:
            record.update(status="fail", error=f"{type(error).__name__}: {error}")
        finally:
            if process is not None:
                if process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    record["forced_shutdown"] = True
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=10)
                # The API parent can exit before workers in its owned group.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            cleanup_deadline = time.monotonic() + 15
            after_memory = memory_mib()
            while after_memory > before_memory + 128 and time.monotonic() < cleanup_deadline:
                time.sleep(1)
                after_memory = memory_mib()
            if after_memory > before_memory + 128 and process is not None:
                record["forced_shutdown"] = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                cleanup_deadline = time.monotonic() + 15
                while after_memory > before_memory + 128 and time.monotonic() < cleanup_deadline:
                    time.sleep(1)
                    after_memory = memory_mib()
            record.update(memory_before_mib=before_memory, memory_after_mib=after_memory,
                          sampled_peak_memory_mib=peak_memory, cleanup_pass=after_memory <= before_memory + 128,
                          elapsed_seconds=time.monotonic() - started)
            if not record["cleanup_pass"]:
                record["status"] = "cleanup-failed"
            save()
    print(json.dumps({key: record.get(key) for key in ["label", "status", "error", "startup_seconds", "cleanup_pass"]}), flush=True)
    return record
