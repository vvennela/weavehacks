"""Reusable JSON requests through the user's Codex ChatGPT login."""

import json
import math
import time
from pathlib import Path

from .kernel_tools import run_command


class CodexJSONAgent:
    """Run bounded, schema-guided Codex requests without API-key fallback."""

    def __init__(self, *, work_dir, model, reasoning_effort, timeout=180,
                 executable="codex"):
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be non-empty text")
        if not isinstance(reasoning_effort, str) or not reasoning_effort.strip():
            raise ValueError("reasoning_effort must be non-empty text")
        if (type(timeout) not in (int, float) or not math.isfinite(timeout)
                or timeout <= 0):
            raise ValueError("timeout must be finite and positive")

        self.work_dir = Path(work_dir).resolve()
        self.work_dir.mkdir(parents=True, exist_ok=False)
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.timeout = float(timeout)
        self.executable = executable
        self.calls = 0

    def request(self, prompt, schema, *, timeout):
        """Return one JSON object, using one deadline for login and execution."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be non-empty text")
        if not isinstance(schema, dict):
            raise TypeError("schema must be a JSON object")
        try:
            schema_text = json.dumps(schema, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as error:
            raise ValueError("schema must be JSON serializable") from error
        if (type(timeout) not in (int, float) or not math.isfinite(timeout)
                or timeout <= 0):
            raise ValueError("timeout must be finite and positive")

        self.calls += 1
        call_dir = self.work_dir / f"call-{self.calls:03d}"
        call_dir.mkdir()
        prompt_path = call_dir / "prompt.txt"
        schema_path = call_dir / "schema.json"
        response_path = call_dir / "response.json"
        login_log = call_dir / "login.log"
        codex_log = call_dir / "codex.log"
        prompt_path.write_text(prompt)
        schema_path.write_text(schema_text + "\n")

        deadline = time.monotonic() + min(float(timeout), self.timeout)

        def remaining_time():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Codex request deadline reached")
            return remaining

        try:
            login = run_command(
                [self.executable, "login", "status"],
                cwd=self.work_dir,
                timeout=min(10.0, remaining_time()),
            )
            login_log.write_text(login)
            if "Logged in using ChatGPT" not in login:
                raise RuntimeError(
                    "CodexJSONAgent requires Codex ChatGPT login; no API fallback"
                )

            args = [
                self.executable, "exec", "--ignore-user-config", "--ephemeral",
                "--skip-git-repo-check", "--sandbox", "read-only",
                "-c", 'forced_login_method="chatgpt"',
                "-c", 'model_provider="openai"',
                "-c", "model_reasoning_effort=" + json.dumps(self.reasoning_effort),
                "--disable", "shell_tool",
                "--disable", "view_image",
                "--disable", "image_generation",
                "-c", 'web_search="disabled"',
                "--model", self.model,
                "--output-schema", str(schema_path),
                "--output-last-message", str(response_path),
                "--color", "never",
                "-",
            ]
            run_command(
                args,
                cwd=self.work_dir,
                timeout=remaining_time(),
                input_text=prompt,
                log_path=codex_log,
            )
            data = json.loads(response_path.read_text())
            if not isinstance(data, dict):
                raise TypeError("Codex response must be a JSON object")
            return data
        finally:
            # Keep a complete per-call artifact set, including failed calls.
            if not login_log.exists():
                login_log.write_text("")
            if not codex_log.exists():
                codex_log.write_text("")
            if not response_path.exists():
                response_path.write_text("")
