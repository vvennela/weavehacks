"""Known startup signatures are observations, never inferred kernel root causes."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from sera import runtime


CUTLASS = (b'RuntimeError: cutlass_gemm_caller, /workspace/csrc/libtorch_stable/quantization/'
           b'w8a8/cutlass/c3x/cutlass_gemm_caller.cuh:62, Error Internal.\n')


def test_cutlass_signature_has_exact_source_hash_and_line_without_raw_secrets(tmp_path):
    raw = b'authorization=must-not-export\n' + CUTLASS + b'normal shutdown\n'
    (tmp_path/'server.log').write_bytes(raw)
    result = runtime.classify_startup_failure(tmp_path)
    assert result['category'] == 'cutlass-internal-error'
    assert result['stage'] == 'startup' and result['callsite'] == 'cutlass_gemm_caller'
    assert result['kernel_source'] == 'cutlass_gemm_caller.cuh' and result['kernel_line'] == 62
    assert result['source'] == {'path': 'server.log', 'sha256': hashlib.sha256(raw).hexdigest(),
        'line_numbers': [2], 'matched_line_sha256': [hashlib.sha256(CUTLASS).hexdigest()]}
    assert result['root_cause_status'] == 'not-established'
    assert 'must-not-export' not in json.dumps(result)
    assert 'out of memory' not in result['known_message'].lower()


@pytest.mark.parametrize('line', [b'torch.OutOfMemoryError: CUDA out of memory. secret=hidden\n',
                                 b'RuntimeError: CUDA error: out of memory\n'])
def test_explicit_cuda_oom_is_observed_without_copying_arbitrary_error_text(tmp_path, line):
    (tmp_path/'server.log').write_bytes(line)
    result = runtime.classify_startup_failure(tmp_path)
    assert result['category'] == 'cuda-out-of-memory'
    assert result['callsite'] is None and result['kernel_source'] is None
    assert result['source']['line_numbers'] == [1]
    assert result['root_cause_status'] == 'not-established'
    assert 'hidden' not in json.dumps(result)


@pytest.mark.parametrize('raw', [b'RuntimeError: unknown secret failure\n',
                               b'cutlass_gemm_caller\nError Internal\n',
                               b'host out of memory\n'])
def test_unrecognized_or_disconnected_text_does_not_invent_a_specific_cause(tmp_path, raw):
    (tmp_path/'server.log').write_bytes(raw)
    result = runtime.classify_startup_failure(tmp_path)
    assert result['category'] == 'unclassified' and result['source']['line_numbers'] == []
    assert result['source']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert result['callsite'] is None
    assert 'secret' not in json.dumps(result)


def test_missing_server_log_has_explicit_unavailable_evidence(tmp_path):
    result = runtime.classify_startup_failure(tmp_path)
    assert result['category'] == 'unclassified' and result['source'] is None
    assert result['root_cause_status'] == 'not-established'


def test_repeated_error_lines_are_bounded_but_full_original_log_hash_is_saved(tmp_path):
    raw = CUTLASS * 100
    (tmp_path/'server.log').write_bytes(raw)
    result = runtime.classify_startup_failure(tmp_path)
    assert len(result['source']['line_numbers']) == 8
    assert result['source']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert (tmp_path/'server.log').read_bytes() == raw


@pytest.mark.parametrize('cleanup_error', [False, True])
def test_live_start_failure_saves_classification_and_preserves_cleanup(tmp_path, monkeypatch, cleanup_error):
    monkeypatch.setattr(runtime.sys, 'platform', 'linux')
    monkeypatch.setattr(runtime.importlib.metadata, 'version', lambda name: '0.26.0')
    monkeypatch.setattr(runtime, 'gpu_snapshot', lambda: {'used_mib': 0, 'uuid': 'fixture-gpu',
                                                        'compute_capability': '12.0'})
    monkeypatch.setattr(runtime, '_child_environment', lambda *args: {})
    monkeypatch.setattr(runtime.threading, 'Thread', lambda **kwargs: SimpleNamespace(start=lambda: None))

    def launch(command, *, stdout, **kwargs):
        stdout.write(CUTLASS.decode())
        return SimpleNamespace(pid=123, poll=lambda: 1, returncode=1)

    monkeypatch.setattr(runtime.subprocess, 'Popen', launch)
    model = runtime.SeraModel(artifact_dir=tmp_path/'run')
    def close():
        model.record['cleanup_pass'] = not cleanup_error
        model._log.write('final cleanup output\n')
        model._log.close()
        model._save()
        if cleanup_error:
            raise runtime.CleanupError('fixture cleanup failure')
    monkeypatch.setattr(model, 'close', close)
    with pytest.raises(runtime.CleanupError if cleanup_error else RuntimeError,
                       match='cleanup' if cleanup_error else 'exited'):
        model.start()
    saved = json.loads((tmp_path/'run'/'runtime.json').read_text())
    assert saved['status'] == 'startup-failed' and saved['cleanup_pass'] is not cleanup_error
    assert saved['startup_failure']['category'] == 'cutlass-internal-error'
    assert saved['startup_failure']['source']['line_numbers'] == [1]
    assert saved['startup_failure']['source']['sha256'] == hashlib.sha256(
        (tmp_path/'run'/'server.log').read_bytes()).hexdigest()
