"""Offline contract tests; these do not establish multi-GPU performance."""

import json
from types import SimpleNamespace

import pytest

from sera.config import RuntimeConfig
from sera.hardware import HardwareAssignment, ModelDescriptor, preflight_hardware, validate_model_config
from sera.portable_runtime import PortableSeraModel


UUIDS = [f"GPU-00000000-0000-0000-0000-{i:012d}" for i in range(8)]


def devices(count=2):
    return [dict(index=i, uuid=UUIDS[i], name="Test GPU", compute_capability="12.0",
                 total_mib=96000, used_mib=0, driver="580") for i in range(count)]


def descriptor():
    return ModelDescriptor(model_id="example/dense-model", revision="a" * 40)


def model_config(**changes):
    return dict(architectures=["Qwen3ForCausalLM"], num_attention_heads=32,
                num_key_value_heads=8, hidden_size=4096, intermediate_size=11008,
                max_position_embeddings=32768, **changes)


@pytest.mark.parametrize("revision", ["main", "v1", "a" * 39, "A" * 40])
def test_descriptor_requires_commit(revision):
    with pytest.raises(ValueError):
        ModelDescriptor(model_id="example/model", revision=revision)


@pytest.mark.parametrize("count", [1, 2, 4, 8])
def test_assignment_preflights_real_selected_devices(count):
    assignment = HardwareAssignment(gpu_uuids=UUIDS[:count])
    result = preflight_hardware(assignment, devices(count), visible_devices=None)
    assert [gpu["uuid"] for gpu in result] == UUIDS[:count]
    validate_model_config(model_config(), assignment, RuntimeConfig())


@pytest.mark.parametrize("uuids", [[], [UUIDS[0]] * 2, UUIDS[:3], ["0"], ["MIG-abc"]])
def test_assignment_rejects_ambiguous_or_unsupported_devices(uuids):
    with pytest.raises(ValueError):
        HardwareAssignment(gpu_uuids=uuids)


def test_missing_gpu_fails_before_model_metadata_or_process(monkeypatch, tmp_path):
    runner = PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:2]),
                               artifact_dir=tmp_path / "run")
    monkeypatch.setattr("sera.portable_runtime.sys.platform", "linux")
    monkeypatch.setattr("sera.portable_runtime.discover_gpus", lambda: devices(1))
    monkeypatch.setattr("sera.portable_runtime.load_model_config", lambda *_: pytest.fail("metadata download"))
    with pytest.raises(ValueError, match="not visible"):
        runner.start()
    assert runner.record["status"] == "startup-failed"
    assert runner.record["cleanup_pass"] is True


@pytest.mark.parametrize("visible", ["", "-1", "0", UUIDS[0], "MIG-abc"])
def test_cannot_expand_parent_cuda_visibility(visible):
    with pytest.raises(ValueError):
        preflight_hardware(HardwareAssignment(gpu_uuids=UUIDS[:2]), devices(), visible_devices=visible)


def test_visibility_accepts_uuid_order():
    assignment = HardwareAssignment(gpu_uuids=list(reversed(UUIDS[:2])))
    assert preflight_hardware(assignment, devices(), visible_devices=",".join(UUIDS[:2]))[0]["uuid"] == UUIDS[1]


def test_numeric_cuda_mask_is_not_assumed_to_match_nvidia_index_order():
    with pytest.raises(ValueError, match="UUID"):
        preflight_hardware(HardwareAssignment(gpu_uuids=UUIDS[:2]), devices(), visible_devices="1,0")


@pytest.mark.parametrize("field,value", [("used_mib", 129), ("name", "Different GPU"),
                                           ("total_mib", 48000), ("compute_capability", "7.0")])
def test_preflight_rejects_busy_mixed_or_unsupported_hardware(field, value):
    inventory = devices()
    inventory[1][field] = value
    with pytest.raises(ValueError):
        preflight_hardware(HardwareAssignment(gpu_uuids=UUIDS[:2]), inventory, visible_devices=None)


@pytest.mark.parametrize("changes", [dict(num_attention_heads=30), dict(num_key_value_heads=3),
                                      dict(hidden_size=4097), dict(intermediate_size=11009),
                                      dict(quantization_config={"quant_method": "fp8"}),
                                      dict(architectures=["UnknownModel"]), dict(num_experts=8)])
def test_model_metadata_rejects_unsupported_or_indivisible_config(changes):
    config = model_config() | changes
    with pytest.raises(ValueError):
        validate_model_config(config, HardwareAssignment(gpu_uuids=UUIDS[:4]), RuntimeConfig())


def test_replication_of_kv_heads_is_legal():
    validate_model_config(model_config() | dict(num_key_value_heads=2),
                          HardwareAssignment(gpu_uuids=UUIDS[:8]), RuntimeConfig())


@pytest.mark.parametrize("config", [RuntimeConfig(quantization="fp8_per_tensor"), RuntimeConfig(kv_cache_dtype="fp8")])
def test_new_models_do_not_inherit_fp8_compatibility(config, tmp_path):
    with pytest.raises(ValueError, match="BF16"):
        PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:2]),
                          configuration=config, artifact_dir=tmp_path)


def test_command_and_record_use_exact_model_devices_and_parallelism(tmp_path):
    runner = PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:4]),
                               artifact_dir=tmp_path)
    command = runner._command(1234)
    assert command[command.index("--model") + 1] == descriptor().model_id
    assert command[command.index("--revision") + 1] == descriptor().revision
    assert command[command.index("--tokenizer-revision") + 1] == descriptor().revision
    assert command[command.index("--tensor-parallel-size") + 1] == "4"
    assert command[command.index("--distributed-executor-backend") + 1] == "mp"
    assert "--trust-remote-code" not in command
    assert runner.record["configuration"]["tensor_parallel_size"] == 4
    assert runner.configuration.tensor_parallel_size == 4
    assert runner.configuration.config_hash == runner.record["config_hash"]
    assert runner.record["hardware_assignment"]["gpu_uuids"] == UUIDS[:4]
    assert runner.record["validation_status"] == "not-measured"


def test_cleanup_checks_each_gpu_not_only_sum(monkeypatch, tmp_path):
    runner = PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:2]),
                               artifact_dir=tmp_path)
    runner.record["gpu_memory_before_mib"] = {UUIDS[0]: 100, UUIDS[1]: 0}
    after = devices()
    after[1]["used_mib"] = 129
    monkeypatch.setattr("sera.portable_runtime.discover_gpus", lambda: after)
    assert runner._cleanup_snapshot()[1] is False
    after[1]["used_mib"] = 128
    assert runner._cleanup_snapshot()[1] is True


def test_metadata_loaded_from_exact_revision(monkeypatch, tmp_path):
    from sera.hardware import load_model_config
    source = tmp_path / "config.json"
    source.write_text(json.dumps(model_config()))
    calls = []
    monkeypatch.setitem(__import__("sys").modules, "huggingface_hub", SimpleNamespace(
        hf_hub_download=lambda **kw: calls.append(kw) or str(source)))
    assert load_model_config(descriptor())["num_attention_heads"] == 32
    assert calls == [dict(repo_id=descriptor().model_id, revision=descriptor().revision, filename="config.json")]


def fake_runtime(monkeypatch):
    from sera import portable_runtime as module
    launches, signals = [], []
    process = SimpleNamespace(pid=12345, returncode=None, poll=lambda: None,
                              terminate=lambda: None, wait=lambda **_: None)
    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr(module, "discover_gpus", lambda: devices())
    monkeypatch.setattr(module, "load_model_config", lambda _: model_config())
    monkeypatch.setattr(module.importlib.metadata, "version", lambda name: "0.26.0" if name == "vllm" else "test")
    monkeypatch.setattr(module, "_child_environment", lambda _, selected: {"CUDA_VISIBLE_DEVICES": selected})
    monkeypatch.setattr(module.subprocess, "Popen", lambda command, **kw: launches.append((command, kw)) or process)
    monkeypatch.setattr(module.threading, "Thread", lambda **_: SimpleNamespace(start=lambda: None, join=lambda **_: None))
    monkeypatch.setattr(module.os, "killpg", lambda *args: signals.append(args))
    return launches, signals


def test_full_owned_lifecycle_uses_selected_devices_and_saves_cleanup(monkeypatch, tmp_path):
    launches, signals = fake_runtime(monkeypatch)
    runner = PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:2]),
                               artifact_dir=tmp_path / "run")
    monkeypatch.setattr(runner, "_request", lambda *_, **__: {})
    with runner:
        assert runner._ready
        assert runner.record["validation_status"] == "runtime-ready-quality-unverified"
        assert launches[0][1]["env"]["CUDA_VISIBLE_DEVICES"] == ",".join(UUIDS[:2])
        assert runner.record["gpu_memory_before_mib"] == dict.fromkeys(UUIDS[:2], 0)
    saved = json.loads((tmp_path / "run/runtime.json").read_text())
    assert saved["gpu_memory_after_mib"] == dict.fromkeys(UUIDS[:2], 0)
    assert saved["cleanup_pass"] and saved["status"] == "closed"
    assert [item[0] for item in signals] == [12345, 12345]
    with pytest.raises(RuntimeError, match="new Portable"):
        runner.start()


def test_failed_readiness_cleans_owned_process(monkeypatch, tmp_path):
    launches, signals = fake_runtime(monkeypatch)
    runner = PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:2]),
                               artifact_dir=tmp_path / "run")
    monkeypatch.setattr(runner, "_request", lambda *_, **__: (_ for _ in ()).throw(RuntimeError("health failed")))
    with pytest.raises(RuntimeError, match="health failed"):
        runner.start()
    assert launches and signals
    assert runner.record["status"] == "startup-failed"
    assert runner.record["cleanup_pass"]


def test_cleanup_telemetry_error_still_kills_workers(monkeypatch, tmp_path):
    from sera.runtime import CleanupError
    _, signals = fake_runtime(monkeypatch)
    runner = PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:2]),
                               artifact_dir=tmp_path / "run")
    monkeypatch.setattr(runner, "_request", lambda *_, **__: {})
    runner.start()
    monkeypatch.setattr(runner, "_selected_snapshot", lambda: (_ for _ in ()).throw(ValueError("missing device")))
    with pytest.raises(CleanupError):
        runner.close()
    assert signals[-1][1] == __import__("signal").SIGKILL
    assert runner.record["cleanup_pass"] is False


def test_mutated_assignment_cannot_change_saved_hardware_plan(monkeypatch, tmp_path):
    fake_runtime(monkeypatch)
    runner = PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:2]),
                               artifact_dir=tmp_path / "run")
    runner.hardware.gpu_uuids.reverse()
    with pytest.raises(ValueError, match="assignment changed"):
        runner.start()


def test_closing_unused_runner_does_not_allow_an_unowned_later_start(monkeypatch, tmp_path):
    runner = PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:2]),
                               artifact_dir=tmp_path / "run")
    runner.close()
    monkeypatch.setattr("sera.portable_runtime.discover_gpus", lambda: pytest.fail("GPU lookup"))
    with pytest.raises(RuntimeError, match="new Portable"):
        runner.start()


def test_assignment_mutation_after_start_cannot_change_cleanup_targets(monkeypatch, tmp_path):
    fake_runtime(monkeypatch)
    runner = PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:2]),
                               artifact_dir=tmp_path / "run")
    monkeypatch.setattr(runner, "_request", lambda *_, **__: {})
    runner.start()
    runner.hardware.gpu_uuids.append(UUIDS[2])
    runner.close()
    assert runner.record["gpu_memory_after_mib"] == dict.fromkeys(UUIDS[:2], 0)


def test_mig_enabled_physical_gpu_is_not_an_isolated_assignment():
    inventory = devices()
    inventory[0]["mig_mode"] = "Enabled"
    with pytest.raises(ValueError, match="MIG"):
        preflight_hardware(HardwareAssignment(gpu_uuids=UUIDS[:2]), inventory, visible_devices=None)


def test_gpu_inventory_keeps_physical_identity_and_memory(monkeypatch):
    from sera.hardware import discover_gpus
    calls = []
    csv = f'0, {UUIDS[0]}, Test GPU, 12.0, 96000, 0, 580, [N/A]\n'
    monkeypatch.setattr("sera.hardware.subprocess.run", lambda command, **kwargs:
                        calls.append((command, kwargs)) or SimpleNamespace(stdout=csv))
    assert discover_gpus() == [devices(1)[0] | dict(mig_mode="[N/A]")]
    assert calls[0][1]["timeout"] == 10
    assert not any("--id=0" in argument for argument in calls[0][0])


def test_generate_reuses_pinned_inputs_and_returns_usable_response(monkeypatch, tmp_path):
    fake_runtime(monkeypatch)
    runner = PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:2]),
                               artifact_dir=tmp_path / "run")
    def request(route, payload=None, **_):
        if route == "/tokenize":
            return dict(tokens=[1, 2])
        if route == "/v1/chat/completions":
            assert payload["return_token_ids"] is True
            return dict(choices=[dict(token_ids=[3], message=dict(content="4"), finish_reason="stop")],
                        prompt_token_ids=[1, 2], prompt_text="2+2", usage=dict(prompt_tokens=2, completion_tokens=1))
        return {}
    monkeypatch.setattr(runner, "_request", request)
    with runner:
        response = runner.generate("2+2")
        assert response.text == "4" and response.token_ids == [3]
    assert runner.record["validation_status"] == "runtime-ready-quality-unverified"


def test_leaked_memory_on_one_gpu_fails_cleanup(monkeypatch, tmp_path):
    import itertools
    from sera.runtime import CleanupError
    fake_runtime(monkeypatch)
    runner = PortableSeraModel(model=descriptor(), hardware=HardwareAssignment(gpu_uuids=UUIDS[:2]),
                               artifact_dir=tmp_path / "run")
    monkeypatch.setattr(runner, "_request", lambda *_, **__: {})
    runner.start()
    leaking = devices()
    leaking[1]["used_mib"] = 200
    monkeypatch.setattr("sera.portable_runtime.discover_gpus", lambda: leaking)
    clock = itertools.count(step=20)
    monkeypatch.setattr("sera.portable_runtime.time.monotonic", lambda: next(clock))
    with pytest.raises(CleanupError, match="assigned GPU"):
        runner.close()
    assert runner.record["cleanup_pass"] is False
    assert runner.record["gpu_memory_after_mib"][UUIDS[1]] == 200


def test_single_gpu_agent_contract_stays_unchanged():
    from sera.config import CONTROL_ROLES, validate_control_value
    assert 'tensor_parallel_size' not in CONTROL_ROLES
    with pytest.raises(ValueError):
        validate_control_value('tensor_parallel_size', 2)
