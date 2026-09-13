"""Explicit single-host tensor-parallel runtime and fixed-hardware search adapter."""

import importlib.metadata
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request

from .config import RuntimeConfig
from .hardware import HardwareAssignment, ModelDescriptor, discover_gpus, load_model_config, preflight_hardware, validate_model_config
from .runtime import CleanupError, GENERATION, SERVED_MODEL, SeraModel, _child_environment, classify_startup_failure
from .storage import content_hash


class PortableSeraModel(SeraModel):
    """Own one explicitly configured BF16 service on 1, 2, 4, or 8 GPUs.

    Readiness is runtime compatibility, not a quality or speedup certificate.
    Automatic hardware selection and new-model precision selection are not enabled.
    """

    def __init__(self, *, model, hardware, artifact_dir, configuration=None):
        self.model = ModelDescriptor.model_validate(model.model_dump() if isinstance(model, ModelDescriptor) else model)
        self.hardware = HardwareAssignment.model_validate(
            hardware.model_dump() if isinstance(hardware, HardwareAssignment) else hardware)
        self._gpu_uuids = tuple(self.hardware.gpu_uuids)
        self.configuration = RuntimeConfig.model_validate(
            (configuration or RuntimeConfig()).model_dump())
        if self.configuration.quantization is not None or self.configuration.kv_cache_dtype != "auto":
            raise ValueError("Portable model experiments require BF16 weights and KV; FP8 is not certified")
        if self.configuration.tensor_parallel_size not in {1, len(self._gpu_uuids)}:
            raise ValueError("Configured tensor parallel size does not match the hardware assignment")
        self.configuration = RuntimeConfig.model_validate(self.configuration.model_dump() |
            {"tensor_parallel_size": len(self._gpu_uuids)})
        self.model_id, self.revision = self.model.model_id, self.model.revision
        self.artifact_dir = Path(artifact_dir).resolve()
        self.process = None
        self._log = None
        self._monitor = None
        self._stop_monitor = threading.Event()
        self._started_once = False
        self._ready = False
        self.placement_owner = None
        self._http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        resolved = self.configuration.model_dump()
        self.record = dict(model_id=self.model_id, revision=self.revision,
            configuration=resolved, config_hash=content_hash(resolved), status="not-started",
            hardware_assignment=self.hardware.model_dump(), generation=GENERATION,
            enable_thinking=False, sampled_peak_memory_mib=None, telemetry_errors=0,
            validation_status="not-measured", adapter="explicit-single-host-v1",
            limits=["BF16 dense Qwen2/Qwen3/Llama only", "No automatic hardware or precision selection",
                    "No quality or performance claim from startup", "No multi-node or MIG support"])

    def _selected_snapshot(self):
        inventory = {gpu["uuid"]: gpu for gpu in discover_gpus()}
        if any(uuid not in inventory for uuid in self._gpu_uuids):
            raise ValueError("An assigned GPU disappeared during the trial")
        return [inventory[uuid] for uuid in self._gpu_uuids]

    def _sample_memory(self):
        while not self._stop_monitor.is_set():
            try:
                snapshot = self._selected_snapshot()
                total = sum(gpu["used_mib"] for gpu in snapshot)
                self.record["sampled_peak_memory_mib"] = max(self.record["sampled_peak_memory_mib"] or 0, total)
                peaks = self.record.setdefault("gpu_sampled_peak_memory_mib", {})
                for gpu in snapshot:
                    peaks[gpu["uuid"]] = max(peaks.get(gpu["uuid"], 0), gpu["used_mib"])
            except (OSError, ValueError, subprocess.SubprocessError):
                self.record["telemetry_errors"] += 1
            self._stop_monitor.wait(1)

    def _command(self, port):
        config = self.configuration
        return [sys.executable, "-m", "vllm.entrypoints.openai.api_server",
            "--model", self.model_id, "--revision", self.revision,
            "--tokenizer-revision", self.revision, "--served-model-name", SERVED_MODEL,
            "--host", "127.0.0.1", "--port", str(port), "--dtype", "bfloat16",
            "--kv-cache-dtype", "auto", "--tensor-parallel-size", str(len(self._gpu_uuids)),
            "--distributed-executor-backend", "mp", "--pipeline-parallel-size", "1",
            "--max-model-len", str(config.max_model_len), "--max-num-seqs", str(config.max_num_seqs),
            "--max-num-batched-tokens", str(config.max_num_batched_tokens),
            "--gpu-memory-utilization", str(config.gpu_memory_utilization),
            "--enable-prefix-caching" if config.enable_prefix_caching else "--no-enable-prefix-caching",
            "--enable-chunked-prefill" if config.enable_chunked_prefill else "--no-enable-chunked-prefill",
            "--enforce-eager" if config.enforce_eager else "--no-enforce-eager",
            "--generation-config", "vllm", "--seed", "0", "--cpu-offload-gb", "0",
            "--enable-tokenizer-info-endpoint", "--shutdown-timeout", "15"]

    def start(self):
        if self._started_once or self.record.get("cleanup_pass"):
            raise RuntimeError("Create a new PortableSeraModel for a new server launch")
        self._started_once = True
        self.artifact_dir.mkdir(parents=True, exist_ok=False)
        self.record["status"] = "starting"
        self._save()
        try:
            if sys.platform != "linux":
                raise RuntimeError("The live runner requires Linux and NVIDIA GPUs")
            if self.hardware.model_dump() != self.record["hardware_assignment"]:
                raise ValueError("Hardware assignment changed after the runner was created")
            # Hardware errors stop before metadata retrieval, weight download, or launch.
            selected = preflight_hardware(self.hardware, discover_gpus(),
                visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES"))
            self.record.update(gpus=selected,
                gpu_memory_before_mib={gpu["uuid"]: gpu["used_mib"] for gpu in selected},
                memory_before_mib=sum(gpu["used_mib"] for gpu in selected),
                service_budget_mib_per_gpu={gpu["uuid"]: int(gpu["total_mib"] * self.configuration.gpu_memory_utilization)
                                           for gpu in selected})
            versions = {name: importlib.metadata.version(name)
                        for name in ("vllm", "torch", "transformers", "flashinfer-python")}
            self.record["versions"] = versions
            if versions["vllm"] != "0.26.0":
                raise RuntimeError("The adapter requires vLLM 0.26.0; other versions are unverified")
            metadata = load_model_config(self.model)
            self.record["model_config"] = metadata
            self.record["model_config_hash"] = content_hash(metadata)
            self.record["model_preflight"] = validate_model_config(metadata, self.hardware, self.configuration)
            # Explicit UUID order is CUDA's rank order. Never use an unassigned device.
            env = _child_environment(self.artifact_dir, ",".join(self._gpu_uuids))
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            self.base_url = f"http://127.0.0.1:{port}"
            command = self._command(port)
            self.record["command"] = command
            self._log = (self.artifact_dir / "server.log").open("w")
            started = time.monotonic()
            self.process = subprocess.Popen(command, env=env, stdout=self._log,
                                            stderr=subprocess.STDOUT, start_new_session=True)
            self.record["pid"] = self.process.pid
            self._monitor = threading.Thread(target=self._sample_memory, daemon=True)
            self._monitor.start()
            self._save()
            while time.monotonic() - started < 600:
                if self.process.poll() is not None:
                    raise RuntimeError(f"vLLM exited with code {self.process.returncode}; see server.log")
                try:
                    self._request("/health", timeout=2)
                    break
                except (OSError, ValueError):
                    time.sleep(1)
            else:
                raise TimeoutError("vLLM startup exceeded 600 seconds")
            self.record["tokenizer_info"] = self._request("/tokenizer_info", timeout=10)
            self.record.update(status="ready", startup_seconds=time.monotonic() - started,
                               validation_status="runtime-ready-quality-unverified")
            self._ready = True
            self._save()
            return self
        except BaseException as error:
            self.record.update(status="startup-failed", error=f"{type(error).__name__}: {error}")
            try:
                self.close()
            finally:
                self.record["startup_failure"] = classify_startup_failure(self.artifact_dir)
                self._save()
            raise

    def _cleanup_snapshot(self):
        after = {gpu["uuid"]: gpu["used_mib"] for gpu in self._selected_snapshot()}
        before = self.record["gpu_memory_before_mib"]
        return after, all(after[uuid] <= before[uuid] + 128 for uuid in self._gpu_uuids)

    def close(self):
        if self.record.get("cleanup_pass") is True:
            return self.record
        self._ready = False
        self._stop_monitor.set()
        if self._monitor is not None:
            self._monitor.join(timeout=11)

        def signal_group(value):
            try:
                os.killpg(self.process.pid, value)
            except ProcessLookupError:
                pass

        try:
            if self.process is None:
                self.record["cleanup_pass"] = True
                return self.record
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.record["forced_shutdown"] = True
                signal_group(signal.SIGKILL)
                self.process.wait(timeout=10)
            # End every owned worker even when the API server exited first.
            signal_group(signal.SIGTERM)
            after, clean = self._cleanup_snapshot()
            deadline = time.monotonic() + 15
            while not clean and time.monotonic() < deadline:
                time.sleep(1)
                after, clean = self._cleanup_snapshot()
            signal_group(signal.SIGKILL)
            deadline = time.monotonic() + 15
            while not clean and time.monotonic() < deadline:
                time.sleep(1)
                after, clean = self._cleanup_snapshot()
            self.record.update(gpu_memory_after_mib=after, memory_after_mib=sum(after.values()), cleanup_pass=clean)
            if not clean:
                raise CleanupError("An assigned GPU did not return to its own pre-launch memory range")
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            # Failure to inspect a device cannot skip termination of owned workers.
            if self.process is not None:
                signal_group(signal.SIGKILL)
            self.record.update(cleanup_pass=False, cleanup_error=type(error).__name__)
            raise CleanupError("Could not verify cleanup on every assigned GPU") from error
        finally:
            if self._log is not None:
                self._log.close()
            if self.record["status"] != "startup-failed":
                self.record["status"] = "closed" if self.record.get("cleanup_pass") else "cleanup-failed"
            if self.artifact_dir.exists():
                self._save()
        return self.record


class PortableRuntimeFactory:
    """Keep one validated model and fixed GPU assignment for an entire search."""

    def __init__(self, *, model, hardware):
        self.model = ModelDescriptor.model_validate(model.model_dump() if isinstance(model, ModelDescriptor) else model)
        self.hardware = HardwareAssignment.model_validate(
            hardware.model_dump() if isinstance(hardware, HardwareAssignment) else hardware)
        self._model_data = self.model.model_dump()
        self._hardware_data = self.hardware.model_dump()

    def validate_configuration(self, configuration):
        if self.model.model_dump() != self._model_data or self.hardware.model_dump() != self._hardware_data:
            raise ValueError("The model or hardware assignment changed during optimization")
        config = RuntimeConfig.model_validate(configuration.model_dump())
        if config.tensor_parallel_size != len(self.hardware.gpu_uuids):
            raise ValueError("Search configuration must preserve the fixed tensor parallel assignment")
        if config.quantization is not None or config.kv_cache_dtype != 'auto':
            raise ValueError("Portable optimization supports BF16 weights and KV only")
        return config

    def baseline_configuration(self, supplied):
        config = (RuntimeConfig(tensor_parallel_size=len(self.hardware.gpu_uuids))
                  if supplied is None else RuntimeConfig.model_validate(supplied))
        return self.validate_configuration(config)

    def __call__(self, *, artifact_dir, configuration, model_id, revision):
        config = self.validate_configuration(configuration)
        if (model_id, revision) != (self.model.model_id, self.model.revision):
            raise ValueError("Runtime model identity differs from the pinned search model")
        return PortableSeraModel(model=self.model, hardware=self.hardware,
                                 artifact_dir=artifact_dir, configuration=config)


def optimize_on_hardware(*, model, hardware, prompts, mode='auto', **options):
    """Use the existing measured search on an explicit model and fixed GPUs.

    Default mode uses the configured three-investigator swarm. Model weights and
    KV remain BF16; the agents cannot change the supplied GPU assignment.
    A versioned task evaluator and explicit quality floor are required.
    """
    from .api import optimize

    factory = PortableRuntimeFactory(model=model, hardware=hardware)
    return optimize(models=[factory.model.model_id], prompts=prompts, mode=mode,
                    _runtime_factory=factory, **options)
