"""Codex ChatGPT-only proposals and signed local Hills evaluations.

These adapters are for trusted local research. The Hills evaluator executes C
as the current user. A process timeout is not a native-code security sandbox.
"""

import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile
import time

from .kernel_search import KernelCandidate
from .storage import save_json


def research_environment():
    """Pass local tool/auth locations, never API-key provider credentials."""
    environment = {name: os.environ[name] for name in (
        "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "CODEX_HOME", "HILLS_HOME"
    ) if name in os.environ}
    environment.update(PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                       MKL_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1", BLIS_NUM_THREADS="1")
    return environment


def run_command(args, *, cwd, timeout, input_text=None, log_path=None):
    """Bound the whole process group, including compiler/agent descendants."""
    log = Path(log_path).open("w") if log_path is not None else None
    try:
        return _communicate(args, cwd=cwd, timeout=timeout, input_text=input_text, log=log)
    finally:
        if log is not None:
            log.close()


def _communicate(args, *, cwd, timeout, input_text, log):
    with subprocess.Popen(args, cwd=cwd, env=research_environment(),
                          stdin=subprocess.PIPE, stdout=log if log is not None else subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, start_new_session=True) as process:
        try:
            output, _ = process.communicate(input_text, timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            output, _ = process.communicate()
            raise
        if log is not None:
            log.flush()
            output = "See saved command log"
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, args, output=output)
        return output


class HillsKernelEvaluator:
    """Run the existing frozen evaluator; never inspect its private inputs."""

    def __init__(self, *, workspace, hill="kernel-opt", executable="hills"):
        self.workspace = Path(workspace).resolve()
        self.hill = hill
        self.executable = executable

    def __call__(self, source_dir, report_path, *, final, timeout):
        report_path = Path(report_path).resolve()
        if report_path.exists():
            raise FileExistsError("Refusing to reuse an evaluator report")
        # Submit only the source artifact, outside the user's Git tree. This
        # avoids unrelated worktree status/file hydration changing trial setup.
        with tempfile.TemporaryDirectory(prefix="sera-kernel-") as scratch:
            shutil.copyfile(Path(source_dir) / "kernel.c", Path(scratch) / "kernel.c")
            args = [self.executable, "eval", scratch, "-H", self.hill, "-o", str(report_path)]
            if final:
                args.append("--final")
            try:
                run_command(args, cwd=self.workspace, timeout=timeout,
                            log_path=report_path.with_suffix(".log"))
            except subprocess.CalledProcessError:
                # Correctness/compiler failures can return a signed failed report.
                if not report_path.is_file():
                    raise
        run_command([self.executable, "verify", str(report_path)],
                    cwd=self.workspace, timeout=min(timeout, 10))
        return json.loads(report_path.read_text())


class CodexKernelProposer:
    """Ask a Codex agent for a complete source replacement using ChatGPT login.

    There is no API-key or provider fallback. User config is excluded so it
    cannot add another model provider, MCP server, or hook to this invocation.
    The agent returns JSON under a read-only tool policy; Sera writes the source.
    """

    def __init__(self, *, work_dir, task, model=None, timeout=180, executable="codex"):
        self.work_dir = Path(work_dir).resolve()
        self.work_dir.mkdir(parents=True, exist_ok=False)
        self.task = task
        self.model = model
        self.timeout = timeout
        self.executable = executable
        self.calls = 0
        self.schema = self.work_dir / "response-schema.json"
        save_json(self.schema, dict(type="object", additionalProperties=False,
            properties={"name": {"type": "string"}, "hypothesis": {"type": "string"},
                        "source": {"type": "string"}, "stop": {"type": "boolean"}},
            required=["name", "hypothesis", "source", "stop"]))

    def propose(self, history, *, timeout):
        deadline = time.monotonic() + min(timeout, self.timeout)
        login = run_command([self.executable, "login", "status"],
                            cwd=self.work_dir, timeout=min(10, timeout))
        if "Logged in using ChatGPT" not in login:
            raise RuntimeError("Sera kernel proposals require Codex ChatGPT login; no API fallback")
        self.calls += 1
        call_dir = self.work_dir / f"call-{self.calls:03d}"
        call_dir.mkdir()
        # Share measurements and source, never evaluator paths or private inputs.
        evidence = [{key: trial.get(key) for key in
                     ("name", "hypothesis", "status", "scores", "control_scores",
                      "median_gflops", "promoted", "error")}
                    | {"source": Path(trial["source"]).read_text()} for trial in history]
        prompt = (
            "You are Sera's CPU kernel engineer. Produce one complete standalone C kernel. "
            "Use only the supplied source and measurements. Do not use tools, inspect other "
            "files, execute code, contact services, or read private evaluator inputs. "
            "Do not change the benchmark, cache answers across calls, create threads, call "
            "BLAS/external libraries, or hardcode outputs. Preserve the gemm ABI and compute "
            "the full product for all positive n, including tails. Explain one concrete "
            "performance hypothesis; return the whole C source in the schema. Set stop=true "
            "only if no useful legal change remains. Failed trials and timing variation are "
            "evidence; do not repeat the same source under a new name.\n\n"
            + self.task + "\n\nMeasured history:\n" + json.dumps(evidence)
        )
        (call_dir / "prompt.txt").write_text(prompt)
        response = call_dir / "response.json"
        args = [self.executable, "exec", "--ignore-user-config", "--ephemeral",
                "--skip-git-repo-check", "--sandbox", "read-only",
                "-c", 'forced_login_method="chatgpt"', "-c", 'model_provider="openai"',
                "--disable", "shell_tool", "--disable", "view_image",
                "--disable", "image_generation", "-c", 'web_search="disabled"',
                "--output-schema", str(self.schema), "--output-last-message", str(response),
                "--color", "never"]
        if self.model is not None:
            args += ["--model", self.model]
        args.append("-")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Codex proposal deadline reached during preparation")
        run_command(args, cwd=self.work_dir, timeout=remaining, input_text=prompt,
                    log_path=call_dir / "codex.log")
        data = json.loads(response.read_text())
        if set(data) != {"name", "hypothesis", "source", "stop"} or type(data["stop"]) is not bool:
            raise ValueError("Codex returned an invalid kernel proposal")
        if data["stop"]:
            return None
        return KernelCandidate(data["name"], data["source"], data["hypothesis"])

    def __call__(self, history):
        return self.propose(history, timeout=self.timeout)
