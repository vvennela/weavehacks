"""Explicit, fail-closed model and single-host GPU assignment contracts."""

import csv
import json
from pathlib import Path
import re
import subprocess

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelDescriptor(BaseModel):
    """A model identity, not a claim that its kernels or quality have passed."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    model_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")


class HardwareAssignment(BaseModel):
    """One owned service across 1, 2, 4, or 8 explicitly selected physical GPUs."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    gpu_uuids: list[str]

    @field_validator("gpu_uuids")
    @classmethod
    def validate_devices(cls, values):
        if len(values) not in {1, 2, 4, 8} or len(set(values)) != len(values):
            raise ValueError("Select 1, 2, 4, or 8 unique GPU UUIDs")
        if any(re.fullmatch(r"GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value) is None
               for value in values):
            raise ValueError("Use full physical GPU UUIDs; indices and MIG devices are not assignments")
        return values


def discover_gpus():
    """Read physical NVIDIA device identity and memory without initializing CUDA."""
    command = ["nvidia-smi", "--query-gpu=index,uuid,name,compute_cap,memory.total,memory.used,driver_version,mig.mode.current",
               "--format=csv,noheader,nounits"]
    output = subprocess.run(command, capture_output=True, text=True, check=True, timeout=10).stdout
    result = []
    for row in csv.reader(output.splitlines(), skipinitialspace=True):
        if len(row) != 8:
            raise ValueError("Incomplete NVIDIA GPU inventory")
        index, uuid, name, capability, total, used, driver, mig_mode = [value.strip() for value in row]
        gpu = dict(index=int(index), uuid=uuid, name=name, compute_capability=capability,
                   total_mib=int(total), used_mib=int(used), driver=driver, mig_mode=mig_mode)
        if gpu["total_mib"] <= 0 or gpu["used_mib"] < 0:
            raise ValueError("Invalid GPU memory telemetry")
        result.append(gpu)
    return result


def preflight_hardware(assignment, inventory, *, visible_devices):
    assignment = HardwareAssignment.model_validate(assignment.model_dump())
    by_uuid = {gpu["uuid"]: gpu for gpu in inventory}
    if len(by_uuid) != len(inventory):
        raise ValueError("Duplicate GPU identities in inventory")
    visible = set(by_uuid)
    if visible_devices is not None:
        tokens = [value.strip() for value in visible_devices.split(",")]
        visible = set()
        for value in tokens:
            if value in by_uuid:
                visible.add(value)
            else:
                raise ValueError("CUDA_VISIBLE_DEVICES must use full visible GPU UUIDs, not ambiguous CUDA indices")
    if any(uuid not in visible for uuid in assignment.gpu_uuids):
        raise ValueError("An assigned GPU is not visible to this process")
    selected = [by_uuid[uuid] for uuid in assignment.gpu_uuids]
    identity = {(gpu["name"], gpu["compute_capability"], gpu["total_mib"], gpu["driver"]) for gpu in selected}
    if len(identity) != 1:
        raise ValueError("This tensor-parallel adapter requires matching GPUs and memory capacity")
    for gpu in selected:
        if gpu.get("mig_mode", "Disabled") not in {"Disabled", "[N/A]", "N/A", "[Not Supported]"}:
            raise ValueError("MIG-enabled physical GPUs cannot be assigned to this adapter")
        if gpu["used_mib"] > 128:
            raise ValueError("An assigned GPU is already in use; refusing an isolated trial")
        if tuple(int(part) for part in gpu["compute_capability"].split(".")) < (8, 0):
            raise ValueError("The BF16 adapter requires compute capability 8.0 or newer")
    return selected


def load_model_config(model):
    # Fetch only pinned metadata. This does not download the model weights.
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(repo_id=model.model_id, revision=model.revision, filename="config.json")
    return json.loads(Path(path).read_text())


def validate_model_config(metadata, assignment, configuration):
    """Conservative dense-model checks before vLLM can download model weights."""
    if not isinstance(metadata, dict):
        raise ValueError("Model config must be an object")
    supported = {"Qwen2ForCausalLM", "Qwen3ForCausalLM", "LlamaForCausalLM"}
    architectures = metadata.get("architectures")
    if not isinstance(architectures, list) or len(architectures) != 1 or architectures[0] not in supported:
        raise ValueError("The portable adapter supports dense Qwen2, Qwen3, and Llama metadata only")
    if metadata.get("quantization_config") is not None or any(
            metadata.get(key) for key in ("num_experts", "num_local_experts", "vision_config", "text_config")):
        raise ValueError("Prequantized, expert, and multimodal model variants are not enabled")
    dimensions = {}
    for key in ("num_attention_heads", "num_key_value_heads", "hidden_size", "intermediate_size", "max_position_embeddings"):
        value = metadata.get(key)
        if key == "num_key_value_heads" and value is None:
            value = metadata.get("num_attention_heads")
        if type(value) is not int or value <= 0:
            raise ValueError(f"Model config requires a positive integer {key}")
        dimensions[key] = value
    size = len(assignment.gpu_uuids)
    if any(dimensions[key] % size for key in ("num_attention_heads", "hidden_size", "intermediate_size")):
        raise ValueError("Model dimensions are not divisible by tensor parallel size")
    kv_heads = dimensions["num_key_value_heads"]
    if (kv_heads >= size and kv_heads % size) or (kv_heads < size and size % kv_heads):
        raise ValueError("KV heads cannot be partitioned or replicated across assigned GPUs")
    if configuration.max_model_len > dimensions["max_position_embeddings"]:
        raise ValueError("Requested context exceeds the pinned model's context limit")
    return dict(architecture=architectures[0], tensor_parallel_size=size, **dimensions)
