def run_runtime_smoke(model_id, revision, label, quantization=None, kv_cache_dtype="auto"):
    import importlib.metadata
    import json
    import os
    from pathlib import Path
    import signal
    import socket
    import subprocess
    import sys
    import time
    import urllib.request

    evidence_dir = Path("/marimo/sera-evidence") / label
    evidence_dir.mkdir(parents=True, exist_ok=False)
    log_path = evidence_dir / "server.log"

    def gpu_memory_mib():
        sample = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return int(sample.stdout.splitlines()[0])

    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    command = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_id, "--revision", revision,
        "--tokenizer-revision", revision, "--served-model-name", "sera-smoke",
        "--host", "127.0.0.1", "--port", str(port),
        "--dtype", "bfloat16", "--kv-cache-dtype", kv_cache_dtype,
        "--tensor-parallel-size", "1", "--max-model-len", "4096",
        "--max-num-seqs", "8", "--max-num-batched-tokens", "4096",
        "--gpu-memory-utilization", "0.90", "--no-enable-prefix-caching",
        "--enable-chunked-prefill", "--enforce-eager",
        "--generation-config", "vllm", "--seed", "0",
    ]
    if quantization is not None:
        command.extend(["--quantization", quantization])
    result = {
        "label": label, "model_id": model_id, "revision": revision,
        "quantization": quantization, "kv_cache_dtype": kv_cache_dtype,
        "command": command, "status": "running", "task_quality_verified": False,
        "versions": {name: importlib.metadata.version(name) for name in ["vllm", "torch", "transformers"]},
    }
    memory_before = gpu_memory_mib()
    peak_memory = memory_before
    started = time.monotonic()
    process = None
    with log_path.open("w") as log_file:
        try:
            compiler_package = importlib.metadata.distribution("nvidia-cuda-nvcc")
            compiler = next(compiler_package.locate_file(entry) for entry in compiler_package.files if entry.name == "nvcc")
            cuda_home = str(compiler.parent.parent)
            env = dict(os.environ, CUDA_VISIBLE_DEVICES="0", OMP_NUM_THREADS="2", CUDA_HOME=cuda_home)
            env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
            cuda_library = Path(cuda_home) / "lib" / "libcudart.so.13"
            if not cuda_library.is_file():
                raise FileNotFoundError(f"CUDA runtime library is missing: {cuda_library}")
            link_dir = evidence_dir / "cuda-link"
            link_dir.mkdir(exist_ok=True)
            link = link_dir / "libcudart.so"
            if not link.exists():
                link.symlink_to(cuda_library)
            env["LIBRARY_PATH"] = str(link_dir) + os.pathsep + str(cuda_library.parent) + os.pathsep + env.get("LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = str(cuda_library.parent) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
            link_check = subprocess.run(
                ["c++", "-shared", "-x", "c++", "-", "-lcudart", "-o", "/dev/null"],
                input="int main() { return 0; }", capture_output=True, text=True, env=env, timeout=15,
            )
            if link_check.returncode != 0:
                raise RuntimeError(f"CUDA link check failed: {link_check.stderr}")
            result["cuda_link_check"] = "pass"
            result["cuda_home"] = cuda_home
            result["cuda_library"] = str(cuda_library)
            print(f"{label}: CUDA link check passed", flush=True)
            process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT, env=env, start_new_session=True)
            print(f"{label}: server started; waiting for readiness", flush=True)
            deadline = started + 240
            next_update = started
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Server exited with code {process.returncode}")
                try:
                    with urllib.request.urlopen(base_url + "/health", timeout=2) as response:
                        if response.status == 200:
                            break
                except (OSError, TimeoutError):
                    pass
                if time.monotonic() >= next_update:
                    peak_memory = max(peak_memory, gpu_memory_mib())
                    print(f"{label}: {time.monotonic() - started:.0f}s elapsed; peak {peak_memory} MiB", flush=True)
                    next_update = time.monotonic() + 15
                time.sleep(1)
            else:
                raise TimeoutError("Server did not become ready within 240 seconds")
            result["startup_seconds"] = round(time.monotonic() - started, 3)
            outputs = []
            for prompt in ["The capital of France is", "Two plus two equals", "A GPU is useful because"]:
                payload = json.dumps({"model": "sera-smoke", "prompt": prompt, "max_tokens": 32, "temperature": 0, "seed": 0}).encode()
                request = urllib.request.Request(base_url + "/v1/completions", data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=45) as response:
                    completion = json.load(response)
                text = completion["choices"][0]["text"]
                if not text.strip():
                    raise RuntimeError("Generation returned an empty output")
                outputs.append({"prompt": prompt, "text": text, "usage": completion.get("usage")})
            result["outputs"] = outputs
            with urllib.request.urlopen(base_url + "/metrics", timeout=10) as response:
                metrics = response.read().decode()
            (evidence_dir / "metrics.prom").write_text(metrics)
            if "vllm:" not in metrics:
                raise RuntimeError("Metrics endpoint returned no vLLM metrics")
            peak_memory = max(peak_memory, gpu_memory_mib())
            result["status"] = "pass"
        except Exception as error:
            result["status"] = "fail"
            result["error"] = f"{type(error).__name__}: {error}"
        finally:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
            memory_after = gpu_memory_mib()
            cleanup_deadline = time.monotonic() + 15
            while memory_after > memory_before + 128 and time.monotonic() < cleanup_deadline:
                time.sleep(1)
                memory_after = gpu_memory_mib()
            result.update(memory_before_mib=memory_before, sampled_peak_memory_mib=peak_memory, memory_after_mib=memory_after,
                          cleanup_pass=memory_after <= memory_before + 128, elapsed_seconds=round(time.monotonic() - started, 3))
            if not result["cleanup_pass"]:
                result["status"] = "fail"
                result["cleanup_error"] = "GPU memory did not return to the pretrial range"
    if result["status"] == "fail":
        result["server_log_tail"] = log_path.read_text()[-6000:]
    (evidence_dir / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)
    return result
