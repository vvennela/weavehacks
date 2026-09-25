"""Run experimental Sera CPU GEMM search with Codex ChatGPT login and Hills.

Requires a trusted local kernel workspace and the complete frozen kernel-opt
hill. No hosted AutoLab agent, W&B, OpenAI API key, or notebook is used.
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from sera.kernel_search import KernelCandidate, optimize_kernel
from sera.kernel_tools import DEFAULT_KERNEL_MODEL, CodexKernelProposer, HillsKernelEvaluator, research_environment
from sera.cpu_kernel_validation import validate_cpu_kernel
from sera.kernel_specialists import KernelSpecialistTeam
from sera.storage import save_json
import sera


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--hill-workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-candidates", type=int, default=6)
    parser.add_argument("--target-gflops", type=float, default=1800.0)
    parser.add_argument("--agent-timeout", type=float, default=180)
    parser.add_argument("--max-seconds", type=float, default=1800)
    parser.add_argument("--model", default=DEFAULT_KERNEL_MODEL, help="Codex model (default: gpt-6-luna)")
    parser.add_argument("--specialists", type=int, choices=[1, 2, 3], default=3)
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    save_json(folder / "controls.json", dict(
        baseline=str(args.baseline.resolve()), baseline_source=args.baseline.read_text(),
        target_gflops=args.target_gflops, max_candidates=args.max_candidates,
        max_seconds=args.max_seconds, agent_timeout=args.agent_timeout,
        scoring="Frozen Hills kernel-opt; same machine, n=512, tolerance=0.002",
        comparison="Three repeats; alternating unchanged control/candidate; separated ranges plus 5%",
        environment={key: value for key, value in research_environment().items()
                     if key.endswith("THREADS") or key == "PYTHONHASHSEED"},
        provider="Codex CLI, ChatGPT login only", model=args.model,
        implementation_hashes={name: hashlib.sha256(
            (Path(sera.__file__).parent / name).read_bytes()).hexdigest() for name in
            ("kernel_search.py", "kernel_tools.py", "kernel_specialists.py", "cpu_kernel_validation.py")},
    ))
    (folder / "journal.md").write_text(
        "# Sera CPU MatMul run\n\nStatus: running.\n\n"
        f"Goal: exceed {args.target_gflops:,.0f} GFLOP/s on this M4 Pro under the unchanged single-threaded "
        "512-square float32 hill. Three repeated official reports per source, paired "
        "with unchanged controls; one final held-out run. No best-of-repeats promotion. "
        "The hill itself retains its fixed best-of-three scoring rule.\n\n"
        "Live state: search/result.json. Signed evaluator reports and source snapshots "
        "are in search/trial-*/. Codex prompts and responses are in agent/. "
        "This is a trusted local research run, not a sandboxed production service.\n"
    )
    task = (
            "Optimize single-thread row-major float32 C=A@B on Apple M4 Pro CPU. "
            "ABI: void gemm(int n,const float *A,const float *B,float *C). "
            "The compiler is Apple clang 21 using -O3 -march=native -ffast-math -shared -fPIC -lm. "
            "SME/SME2 and NEON are allowed. All input packing/allocation is timed. "
            "No external libraries or multithreading. Correctness tolerance is 0.002 max "
            "absolute error divided by max absolute reference. Main timing shape is n=512. "
            "Keep a correct general tail path and handle n<=0. The target is over "
            f"{args.target_gflops} GFLOP/s in all repeats, not a favorable sample. "
            "Start from the strongest correct source in the history. Prefer reducing "
            "packing/transposition overhead, redundant addressing/predication, or data movement."
        )
    capabilities = ["cpu", platform.machine(), "single-thread"]
    if platform.machine() == "arm64":
        capabilities += ["neon", "simd"]
        sme = subprocess.run(["sysctl", "-n", "hw.optional.arm.FEAT_SME"],
                             capture_output=True, text=True, timeout=5)
        if sme.returncode == 0 and sme.stdout.strip() == "1":
            capabilities.append("sme")
    if args.specialists == 1:
        proposer = CodexKernelProposer(work_dir=folder / "agent", model=args.model,
                                      timeout=args.agent_timeout, task=task)
    else:
        proposer = KernelSpecialistTeam(work_dir=folder / "agent", model=args.model,
            timeout=args.agent_timeout, task=task, active=args.specialists,
            max_calls=args.max_candidates,
            profile=dict(capabilities=capabilities,
                         tags=["gemm", "sme", "packing", "registers", "memory", "simd", "reuse"]))
    try:
        report = optimize_kernel(
            baseline=KernelCandidate("existing-sme", args.baseline.read_text(), "Unchanged existing SME kernel"),
            propose=proposer, evaluate=HillsKernelEvaluator(workspace=args.hill_workspace),
            validate=validate_cpu_kernel,
            output_dir=folder / "search", max_candidates=args.max_candidates,
            target_gflops=args.target_gflops, max_seconds=args.max_seconds,
        )
    except BaseException:
        with (folder / "journal.md").open("a") as stream:
            stream.write("\nStatus: interrupted or failed. Inspect search/result.json and agent logs.\n")
        raise
    with (folder / "journal.md").open("a") as stream:
        stream.write(f"\nStatus: {report['status']}. Target met: {report['target_met']}.\n")
        for trial in report["trials"]:
            stream.write(f"\n- {trial['name']}: {trial['status']}; scores={trial['scores']}; "
                         f"controls={trial['control_scores']}\n")
        stream.write(f"\nFinal GFLOP/s: {report['final_gflops']}. Winner: {report['winner_source']}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
