"""Owned vLLM server lifecycle for the smoke-checked single-GPU runtime."""

from dataclasses import asdict, dataclass
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shlex
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from .config import GLM_MODEL_ID, GLM_MODEL_REVISION, LARGE_MODEL_ID, LARGE_MODEL_REVISION, MODEL_ID, MODEL_REVISION, RuntimeConfig
from .metrics import parse_vllm_metrics
from .storage import save_json


GENERATION = {"temperature": 0, "top_p": 1, "top_k": -1, "seed": 0, "max_tokens": 64}
SERVED_MODEL = "sera-model"
STARTUP_FAILURE_MESSAGES = {
    "cutlass-internal-error": "cutlass_gemm_caller reported Error Internal.",
    "cuda-out-of-memory": "The server log reports CUDA out of memory.",
    "unclassified": "No supported startup error signature is available.",
}


def classify_startup_failure(artifact_dir):
    """Classify fixed signatures, retaining source hashes instead of arbitrary log text."""
    result = dict(category="unclassified", stage="startup", callsite=None,
                  kernel_source=None, kernel_line=None, source=None,
                  root_cause_status="not-established")
    digest = hashlib.sha256()
    matches = []
    try:
        with (Path(artifact_dir) / "server.log").open("rb") as log:
            for number, raw in enumerate(log, 1):
                digest.update(raw)
                line = raw.decode("utf-8", errors="replace")
                category = None
                if "cutlass_gemm_caller" in line and re.search(r"Error\s*Internal", line):
                    category = "cutlass-internal-error"
                elif "CUDA out of memory" in line or "CUDA error: out of memory" in line:
                    category = "cuda-out-of-memory"
                if category is None:
                    continue
                if category != result["category"]:
                    matches = []
                result.update(category=category, callsite=None, kernel_source=None, kernel_line=None)
                if category == "cutlass-internal-error":
                    result["callsite"] = "cutlass_gemm_caller"
                    location = re.search(r"cutlass_gemm_caller\.cuh:([0-9]{1,6})\b", line)
                    if location:
                        result.update(kernel_source="cutlass_gemm_caller.cuh", kernel_line=int(location[1]))
                matches.append((number, hashlib.sha256(raw).hexdigest()))
                matches = matches[-8:]
        result["source"] = dict(path="server.log", sha256=digest.hexdigest(),
            line_numbers=[number for number, _ in matches],
            matched_line_sha256=[digest for _, digest in matches])
    except OSError:
        # Missing/unreadable source is explicit and must not mask the startup error.
        result.update(category="unclassified", callsite=None, kernel_source=None, kernel_line=None)
    result["known_message"] = STARTUP_FAILURE_MESSAGES[result["category"]]
    return result


class CleanupError(RuntimeError):
    """The owned server did not release its resources; do not start another."""


@dataclass(frozen=True)
class SeraResponse:
    text: str
    token_ids: list[int]
    prompt_token_ids: list[int]
    prompt_text: str | None
    finish_reason: str
    latency_ms: float
    usage: dict

    def to_dict(self):
        return asdict(self)


def gpu_snapshot() -> dict:
    command = ["nvidia-smi", "--id=0",
               "--query-gpu=name,uuid,compute_cap,memory.total,memory.used,driver_version",
               "--format=csv,noheader,nounits"]
    output = subprocess.run(command, capture_output=True, text=True, check=True,
                            timeout=10).stdout.strip().split(",")
    name, uuid, capability, total, used, driver = [value.strip() for value in output]
    return {"name": name, "uuid": uuid, "compute_capability": capability,
            "total_mib": int(total), "used_mib": int(used), "driver": driver}


def _cuda13_include_dirs(cuda_root: Path) -> list[Path]:
    """Find installed CUDA-13 headers, including wheels in a visible base environment."""
    include_dirs = set()
    for package in importlib.metadata.distributions():
        name = package.metadata.get("Name", "").lower().replace("_", "-")
        if not name.startswith("nvidia-"):
            continue
        for entry in package.files or []:
            if (entry.parts[:3] == ("nvidia", "cu13", "include")
                    and entry.suffix in {".h", ".hpp", ".cuh"}
                    and Path(package.locate_file(entry)).is_file()):
                include_dirs.add(Path(package.locate_file(Path("nvidia/cu13/include"))))
                break
    compiler_include = cuda_root / "include"
    ordered = ([compiler_include] if compiler_include.is_dir() else [])
    ordered.extend(sorted(include_dirs - set(ordered)))
    if not any((folder / "curand.h").is_file() for folder in ordered):
        raise RuntimeError("Installed CUDA 13 wheels contain no available curand.h")
    return ordered


def _child_environment(folder: Path, gpu_uuid: str) -> dict:
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu_uuid, OMP_NUM_THREADS="2")
    # Apply the smoke-checked CUDA wheel linker fix only when that wheel exists.
    try:
        package = importlib.metadata.distribution("nvidia-cuda-nvcc")
    except importlib.metadata.PackageNotFoundError:
        return env
    compiler = next((package.locate_file(entry) for entry in package.files or []
                     if entry.name == "nvcc"), None)
    if compiler is None:
        raise RuntimeError("Installed CUDA compiler package contains no nvcc")
    cuda_root = compiler.parent.parent
    library = cuda_root / "lib" / "libcudart.so.13"
    if not library.is_file():
        raise RuntimeError("CUDA 13 compiler/runtime libraries do not match the checked setup")
    includes = _cuda13_include_dirs(cuda_root)
    # Match vLLM's system-include flags. Mixing -I and -isystem for the compiler
    # directory discards its -I precedence and lets base-wheel headers shadow it.
    # https://docs.nvidia.com/cuda/cuda-compiler-driver-nvcc/#nvcc-environment-variables
    # https://gcc.gnu.org/onlinedocs/gcc/Directory-Options.html
    include_flags = shlex.join([flag for path in includes for flag in ("-isystem", str(path))])
    inherited_flags = env.get("NVCC_PREPEND_FLAGS", "")
    env["NVCC_PREPEND_FLAGS"] = include_flags + (" " + inherited_flags if inherited_flags else "")
    link_dir = folder / "cuda-link"
    link_dir.mkdir()
    (link_dir / "libcudart.so").symlink_to(library)
    env["CUDA_HOME"] = str(cuda_root)
    for name, paths in {"PATH": [compiler.parent],
                        "LIBRARY_PATH": [link_dir, library.parent],
                        "LD_LIBRARY_PATH": [library.parent]}.items():
        env[name] = os.pathsep.join([*(str(path) for path in paths), env.get(name, "")])
    return env


class SeraModel:
    """Start once, generate many times, then explicitly close (or use `with`)."""

    def __init__(self, *, artifact_dir, configuration=None, model_id=MODEL_ID,
                 revision=MODEL_REVISION, placement_owner=None):
        pinned = {MODEL_ID: MODEL_REVISION, LARGE_MODEL_ID: LARGE_MODEL_REVISION,
                  GLM_MODEL_ID: GLM_MODEL_REVISION}
        if pinned.get(model_id) != revision:
            raise ValueError("The runner requires a supported, pinned model revision")
        self.model_id = model_id
        self.revision = revision
        self.placement_owner = placement_owner
        self.configuration = RuntimeConfig.model_validate(
            (configuration or RuntimeConfig()).model_dump())
        if self.configuration.tensor_parallel_size != 1:
            raise ValueError("Use PortableSeraModel with an explicit hardware assignment for tensor parallelism")
        self.artifact_dir = Path(artifact_dir).resolve()
        self.process = None
        self._log = None
        self._monitor = None
        self._stop_monitor = threading.Event()
        self._started_once = False
        self._ready = False
        self._http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.record = {"model_id": model_id, "revision": revision,
                       "configuration": self.configuration.model_dump(),
                       "config_hash": self.configuration.config_hash, "status": "not-started",
                       "generation": GENERATION, "enable_thinking": False,
                       "sampled_peak_memory_mib": None, "telemetry_errors": 0}

    def _save(self):
        save_json(self.artifact_dir / "runtime.json", self.record)

    def _sample_memory(self):
        while not self._stop_monitor.is_set():
            try:
                if self.placement_owner is not None:
                    self.placement_owner.sample()
                else:
                    used = gpu_snapshot()["used_mib"]
                    self.record["sampled_peak_memory_mib"] = max(
                        self.record["sampled_peak_memory_mib"] or 0, used)
            except (OSError, ValueError, subprocess.SubprocessError):
                self.record["telemetry_errors"] += 1
            self._stop_monitor.wait(1)

    def _request(self, route, payload=None, timeout=90):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.base_url + route, data=data,
                                         headers={"Content-Type": "application/json"})
        with self._http.open(request, timeout=timeout) as response:
            body = response.read().decode()
        return json.loads(body) if body and route != "/metrics" else body

    def start(self):
        if self._started_once:
            raise RuntimeError("Create a new SeraModel for a new server launch")
        self._started_once = True
        self.artifact_dir.mkdir(parents=True, exist_ok=False)
        self.record["status"] = "starting"
        self._save()
        try:
            if sys.platform != "linux":
                raise RuntimeError("The live runner requires Linux and an NVIDIA GPU")
            versions = {name: importlib.metadata.version(name)
                        for name in ("vllm", "torch", "transformers", "flashinfer-python")}
            self.record["versions"] = versions
            if versions["vllm"] != "0.26.0":
                raise RuntimeError("The checked runtime is vLLM 0.26.0; other versions are unverified")
            gpu = gpu_snapshot()
            self.record.update(gpu=gpu, memory_before_mib=gpu["used_mib"])
            if self.placement_owner is not None:
                self.placement_owner.before_start(self, gpu)
            elif gpu["used_mib"] > 128:
                raise RuntimeError("GPU 0 is already in use; refusing an isolated trial")
            if ((self.configuration.kv_cache_dtype == "fp8" or self.configuration.quantization is not None)
                    and gpu["compute_capability"] != "12.0"):
                raise RuntimeError("FP8 paths have only been checked on the supplied sm_120 GPU")
            env = _child_environment(self.artifact_dir, gpu["uuid"])
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            self.base_url = f"http://127.0.0.1:{port}"
            config = self.configuration
            command = [sys.executable, "-m", "vllm.entrypoints.openai.api_server",
                       "--model", self.model_id, "--revision", self.revision,
                       "--tokenizer-revision", self.revision, "--served-model-name", SERVED_MODEL,
                       "--host", "127.0.0.1", "--port", str(port), "--dtype", config.dtype,
                       "--kv-cache-dtype", config.kv_cache_dtype, "--tensor-parallel-size", "1",
                       "--max-model-len", str(config.max_model_len),
                       "--max-num-seqs", str(config.max_num_seqs),
                       "--max-num-batched-tokens", str(config.max_num_batched_tokens),
                       "--gpu-memory-utilization", str(config.gpu_memory_utilization),
                       "--enable-prefix-caching" if config.enable_prefix_caching else "--no-enable-prefix-caching",
                       "--enable-chunked-prefill" if config.enable_chunked_prefill else "--no-enable-chunked-prefill",
                       "--enforce-eager" if config.enforce_eager else "--no-enforce-eager",
                       "--generation-config", "vllm", "--seed", "0", "--cpu-offload-gb", "0",
                       "--enable-tokenizer-info-endpoint", "--shutdown-timeout", "15"]
            if config.quantization is not None:
                command.extend(["--quantization", config.quantization])
            self.record["command"] = command
            self._log = (self.artifact_dir / "server.log").open("w")
            started = time.monotonic()
            self.process = subprocess.Popen(command, env=env, stdout=self._log,
                                            stderr=subprocess.STDOUT, start_new_session=True)
            self.record["pid"] = self.process.pid
            if self.placement_owner is not None:
                self.placement_owner.register(self)
            self._monitor = threading.Thread(target=self._sample_memory, daemon=True)
            self._monitor.start()
            self._save()
            while time.monotonic() - started < 240:
                if self.process.poll() is not None:
                    raise RuntimeError(f"vLLM exited with code {self.process.returncode}; see server.log")
                try:
                    self._request("/health", timeout=2)
                    break
                except (OSError, ValueError):
                    time.sleep(1)
            else:
                raise TimeoutError("vLLM startup exceeded 240 seconds")
            self._ready = True
            self.record.update(status="ready", startup_seconds=time.monotonic() - started)
            self.record["tokenizer_info"] = self._request("/tokenizer_info", timeout=10)
            self._save()
            return self
        except BaseException as error:
            self.record.update(status="startup-failed", error=f"{type(error).__name__}: {error}")
            self._save()
            try:
                self.close()
            finally:
                # Hash the final log after the owned process has stopped writing.
                self.record["startup_failure"] = classify_startup_failure(self.artifact_dir)
                self._save()
            raise

    def _require_ready(self):
        if not self._ready or self.process is None or self.process.poll() is not None:
            raise RuntimeError("The runner is not live; call start() before generate()")
        if getattr(self, 'placement_owner', None) is not None:
            self.placement_owner.ensure_healthy()

    def prepare(self, prompt):
        """Validate context length without generating or truncating any tokens."""
        self._require_ready()
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        elif isinstance(prompt, list):
            messages = prompt
        else:
            raise ValueError("Expected text or a list of text chat messages")
        if not messages or any(not isinstance(item, dict) or set(item) != {"role", "content"}
                               or item["role"] not in {"system", "user", "assistant"}
                               or not isinstance(item["content"], str) or not item["content"].strip()
                               for item in messages):
            raise ValueError("Chat messages require a role and nonempty text content")
        payload = {"model": SERVED_MODEL, "messages": messages,
                   "chat_template_kwargs": {"enable_thinking": False}}
        tokenized = self._request("/tokenize", payload)
        tokens = tokenized["tokens"]
        if not tokens or any(type(token) is not int or token < 0 for token in tokens):
            raise RuntimeError("Tokenizer returned invalid token IDs")
        if len(tokens) + GENERATION["max_tokens"] > self.configuration.max_model_len:
            raise ValueError("Prompt plus 64 output tokens exceeds the configured context; no truncation")
        return payload, tokens

    def generate(self, prompt) -> SeraResponse:
        payload, tokens = self.prepare(prompt)
        return self._generate_prepared(payload, tokens)

    def _generate_prepared(self, payload, tokens):
        self._require_ready()
        request = {**payload, **GENERATION, "return_token_ids": True, "return_prompt_text": True}
        started = time.perf_counter()
        response = self._request("/v1/chat/completions", request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        choice = response["choices"][0]
        output_tokens = choice.get("token_ids")
        if (not isinstance(output_tokens, list)
                or any(type(token) is not int or token < 0 for token in output_tokens)):
            raise RuntimeError("vLLM did not return valid generated token IDs")
        if response.get("prompt_token_ids") != tokens:
            raise RuntimeError("Generation used different input tokens from the context check")
        usage = response.get("usage")
        if not isinstance(usage, dict) or any(type(usage.get(key)) is not int
                                              for key in ("prompt_tokens", "completion_tokens")):
            raise RuntimeError("vLLM did not return token usage")
        return SeraResponse(text=choice["message"].get("content") or "",
                            token_ids=output_tokens, prompt_token_ids=tokens,
                            prompt_text=response.get("prompt_text"), finish_reason=choice["finish_reason"],
                            latency_ms=elapsed_ms, usage=usage)

    def metrics_snapshot(self):
        self._require_ready()
        raw = self._request("/metrics", timeout=10)
        return {"raw": raw, "reduced": parse_vllm_metrics(raw, SERVED_MODEL)}

    def close(self):
        if self.record.get("cleanup_pass") is True:
            return self.record
        self._ready = False
        if self.placement_owner is not None and self.record['status'] == 'ready':
            # A peer monitor must not treat this expected shutdown as missing memory.
            self.record['status'] = 'closing'
        self._stop_monitor.set()
        if self._monitor is not None:
            self._monitor.join(timeout=11)
        process = self.process
        if process is None:
            if self.artifact_dir.exists():
                self.record["cleanup_pass"] = True
                self._save()
            return self.record

        def signal_group(value):
            try:
                os.killpg(process.pid, value)
            except ProcessLookupError:
                pass

        try:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.record["forced_shutdown"] = True
                signal_group(signal.SIGKILL)
                process.wait(timeout=10)
            signal_group(signal.SIGTERM)
            if self.placement_owner is not None:
                signal_group(signal.SIGKILL)
                self.placement_owner.verify_service_cleanup(self)
                return self.record
            after = gpu_snapshot()["used_mib"]
            deadline = time.monotonic() + 15
            while after > self.record["memory_before_mib"] + 128 and time.monotonic() < deadline:
                time.sleep(1)
                after = gpu_snapshot()["used_mib"]
            # Kill any remaining owned workers, including CPU-only workers.
            signal_group(signal.SIGKILL)
            deadline = time.monotonic() + 15
            while after > self.record["memory_before_mib"] + 128 and time.monotonic() < deadline:
                time.sleep(1)
                after = gpu_snapshot()["used_mib"]
            self.record.update(memory_after_mib=after,
                               cleanup_pass=after <= self.record["memory_before_mib"] + 128)
            if not self.record["cleanup_pass"]:
                raise CleanupError("GPU memory did not return to the pre-launch range")
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.record.update(cleanup_pass=False, cleanup_error=str(error))
            raise CleanupError("Could not verify GPU cleanup") from error
        finally:
            if self._log is not None:
                self._log.close()
            if self.record["status"] != "startup-failed":
                self.record["status"] = "closed" if self.record.get("cleanup_pass") else "cleanup-failed"
            self._save()
        return self.record

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()
