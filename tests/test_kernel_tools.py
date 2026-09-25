import json
import subprocess

import pytest

from sera.kernel_tools import CodexKernelProposer, HillsKernelEvaluator, research_environment


def test_agent_environment_excludes_api_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-inherit")
    monkeypatch.setenv("CODEX_API_KEY", "do-not-inherit")
    monkeypatch.setenv("WANDB_API_KEY", "do-not-inherit")
    assert not any("KEY" in key or "TOKEN" in key for key in research_environment())


def test_codex_rejects_api_login_before_request(tmp_path, monkeypatch):
    calls = []
    def command(args, **kwargs):
        calls.append(args)
        return "Logged in using an API key"
    monkeypatch.setattr("sera.kernel_tools.run_command", command)
    proposer = CodexKernelProposer(work_dir=tmp_path / "agent", task="Optimize GEMM")
    with pytest.raises(RuntimeError, match="ChatGPT"):
        proposer([])
    assert len(calls) == 1


def test_codex_uses_chatgpt_only_and_parses_complete_source(tmp_path, monkeypatch):
    calls = []
    def command(args, **kwargs):
        calls.append((args, kwargs))
        if "status" in args:
            return "Logged in using ChatGPT"
        output = args[args.index("--output-last-message") + 1]
        with open(output, "w") as stream:
            json.dump(dict(name="tile", hypothesis="reuse inputs", source="void gemm() {}", stop=False), stream)
        return ""
    monkeypatch.setattr("sera.kernel_tools.run_command", command)
    proposer = CodexKernelProposer(work_dir=tmp_path / "agent", task="Optimize GEMM")
    assert proposer([]).name == "tile"
    args = calls[1][0]
    assert "--ignore-user-config" in args
    assert 'forced_login_method="chatgpt"' in args
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert "--model" not in args


def test_hills_verifies_signature_before_returning_report(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "kernel.c").write_text("source")
    calls = []
    def command(args, **kwargs):
        calls.append(args)
        if "eval" in args:
            (tmp_path / "report.json").write_text('{"passed":true}')
        return ""
    monkeypatch.setattr("sera.kernel_tools.run_command", command)
    evaluator = HillsKernelEvaluator(workspace=tmp_path)
    assert evaluator(source, tmp_path / "report.json", final=False, timeout=10) == {"passed": True}
    assert calls[1][1] == "verify"
    assert "--force" not in calls[0]
    assert "--current" not in calls[0]


def test_hills_verification_failure_is_fatal(tmp_path, monkeypatch):
    (tmp_path / "kernel.c").write_text("source")
    def command(args, **kwargs):
        if "verify" in args:
            raise subprocess.CalledProcessError(1, args)
        (tmp_path / "report.json").write_text('{"passed":true}')
        return ""
    monkeypatch.setattr("sera.kernel_tools.run_command", command)
    with pytest.raises(subprocess.CalledProcessError):
        HillsKernelEvaluator(workspace=tmp_path)(tmp_path, tmp_path / "report.json", final=False, timeout=10)
