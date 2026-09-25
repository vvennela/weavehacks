import json

import pytest

from sera.codex_agent import CodexJSONAgent

SCHEMA = {
    "type": "object",
    "properties": {"decision": {"type": "string"}},
    "required": ["decision"],
    "additionalProperties": False,
}


def agent(tmp_path, **options):
    return CodexJSONAgent(
        work_dir=tmp_path / "agent",
        model=options.pop("model", "gpt-6-astra"),
        reasoning_effort=options.pop("reasoning_effort", "high"),
        **options,
    )


def test_request_uses_chatgpt_codex_with_explicit_model_and_reasoning(tmp_path, monkeypatch):
    calls = []

    def run_command(args, **kwargs):
        calls.append((args, kwargs))
        if args[1:3] == ["login", "status"]:
            return "Logged in using ChatGPT"
        response_path = args[args.index("--output-last-message") + 1]
        with open(response_path, "w") as stream:
            json.dump({"decision": "continue"}, stream)
        return ""

    monkeypatch.setattr("sera.codex_agent.run_command", run_command)
    result = agent(tmp_path).request("Choose a next step", SCHEMA, timeout=30)

    assert result == {"decision": "continue"}
    assert len(calls) == 2
    assert "log_path" not in calls[0][1]
    assert (tmp_path / "agent" / "call-001" / "login.log").read_text() == (
        "Logged in using ChatGPT"
    )
    args, kwargs = calls[1]
    assert args[1] == "exec"
    assert "--ignore-user-config" in args
    assert "--ephemeral" in args
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert 'forced_login_method="chatgpt"' in args
    assert 'model_provider="openai"' in args
    assert 'model_reasoning_effort="high"' in args
    assert args[args.index("--model") + 1] == "gpt-6-astra"
    assert "shell_tool" in args
    assert "view_image" in args
    assert "image_generation" in args
    assert 'web_search="disabled"' in args
    assert kwargs["timeout"] <= 30

    call_dir = tmp_path / "agent" / "call-001"
    assert (call_dir / "prompt.txt").read_text() == "Choose a next step"
    assert json.loads((call_dir / "schema.json").read_text()) == SCHEMA
    assert json.loads((call_dir / "response.json").read_text()) == result
    assert (call_dir / "login.log").exists()
    assert (call_dir / "codex.log").exists()


def test_request_rejects_non_chatgpt_login_without_fallback(tmp_path, monkeypatch):
    calls = []

    def run_command(args, **kwargs):
        calls.append(args)
        return "Logged in using an API key"

    monkeypatch.setattr("sera.codex_agent.run_command", run_command)
    with pytest.raises(RuntimeError, match="ChatGPT login; no API fallback"):
        agent(tmp_path).request("Choose a next step", SCHEMA, timeout=30)

    assert len(calls) == 1
    assert calls[0][1:3] == ["login", "status"]
    call_dir = tmp_path / "agent" / "call-001"
    assert (call_dir / "login.log").read_text() == "Logged in using an API key"
    assert (call_dir / "prompt.txt").exists()
    assert (call_dir / "schema.json").exists()
    assert (call_dir / "response.json").read_text() == ""
    assert (call_dir / "login.log").exists()
    assert (call_dir / "codex.log").exists()


def test_deadline_is_checked_before_first_subprocess(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("sera.codex_agent.run_command", lambda *args, **kwargs: calls.append(args))
    ticks = iter([10.0, 12.0])
    monkeypatch.setattr("sera.codex_agent.time.monotonic", lambda: next(ticks))

    with pytest.raises(TimeoutError, match="deadline"):
        agent(tmp_path).request("Choose a next step", SCHEMA, timeout=1)

    assert calls == []
    call_dir = tmp_path / "agent" / "call-001"
    assert (call_dir / "prompt.txt").exists()
    assert (call_dir / "schema.json").exists()
    assert (call_dir / "response.json").read_text() == ""
    assert (call_dir / "login.log").exists()
    assert (call_dir / "codex.log").exists()


@pytest.mark.parametrize("payload", ["not json", "[]", "null", '"text"'])
def test_request_rejects_malformed_or_non_object_responses(tmp_path, monkeypatch, payload):
    def run_command(args, **kwargs):
        if args[1:3] == ["login", "status"]:
            return "Logged in using ChatGPT"
        output = args[args.index("--output-last-message") + 1]
        with open(output, "w") as stream:
            stream.write(payload)
        return ""

    monkeypatch.setattr("sera.codex_agent.run_command", run_command)
    with pytest.raises((json.JSONDecodeError, TypeError)):
        agent(tmp_path).request("Choose a next step", SCHEMA, timeout=30)


def test_request_rejects_invalid_inputs_before_allocating_call(tmp_path):
    current = agent(tmp_path)
    with pytest.raises(ValueError, match="prompt"):
        current.request(" ", SCHEMA, timeout=30)
    with pytest.raises(TypeError, match="schema"):
        current.request("prompt", [], timeout=30)
    with pytest.raises(ValueError, match="timeout"):
        current.request("prompt", SCHEMA, timeout=0)
    assert list((tmp_path / "agent").iterdir()) == []


@pytest.mark.parametrize("reasoning_effort", ["", None])
def test_constructor_requires_reasoning_effort(tmp_path, reasoning_effort):
    with pytest.raises(ValueError, match="reasoning_effort"):
        CodexJSONAgent(work_dir=tmp_path / "agent", model="gpt-6-astra",
                       reasoning_effort=reasoning_effort)
