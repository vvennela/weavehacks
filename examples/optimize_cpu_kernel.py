"""Run experimental Sera CPU GEMM search with Codex ChatGPT login and Hills.

Requires a trusted local kernel workspace and the complete frozen kernel-opt
hill. No hosted AutoLab agent, W&B, OpenAI API key, or notebook is used.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from sera.kernel_search import KernelCandidate, optimize_kernel
from sera.kernel_tools import HillsKernelEvaluator, research_environment
from sera.cpu_kernel_validation import validate_cpu_kernel
from sera.kernel_advisory import KernelAdvisoryTeam
from sera.storage import save_json
import sera


def host_observation():
    observation = dict(timestamp_utc=datetime.now(timezone.utc).isoformat())
    for key, command in dict(battery=['pmset', '-g', 'batt'],
                             power_settings=['pmset', '-g', 'custom'],
                             thermal=['pmset', '-g', 'therm']).items():
        observation[key] = subprocess.check_output(command, text=True, timeout=10)
    return observation


def require_ac(observation):
    if "Now drawing from 'AC Power'" not in observation['battery']:
        raise RuntimeError('AC power is required for this approved benchmark run')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--hill-workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-candidates", type=int, default=6)
    parser.add_argument("--target-gflops", type=float, default=1800.0)
    parser.add_argument("--agent-timeout", type=float, default=180)
    parser.add_argument("--max-seconds", type=float, default=1800)
    args = parser.parse_args()
    initial_host = host_observation()
    require_ac(initial_host)
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
        provider="Codex CLI, ChatGPT login only", coordinator="gpt-6-astra",
        coordinator_reasoning="high", advisor_model="gpt-6-luna", advisor_count=15,
        max_model_calls=args.max_candidates * 17, host=initial_host,
        implementation_hashes={name: hashlib.sha256(
            (Path(sera.__file__).parent / name).read_bytes()).hexdigest() for name in
            ("kernel_search.py", "kernel_tools.py", "kernel_advisory.py", "kernel_advisor_roles.py",
             "codex_agent.py", "cpu_kernel_validation.py")},
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
            "SME/SME2 and NEON are allowed. Keep FP32 arithmetic; no mixed precision. "
            "Apple clang accepts only FP32 ZA tile selectors 0..3 for svmopa_za32_f32_m. "
            "All input packing/allocation is timed. "
            "No external libraries or multithreading. Correctness tolerance is 0.002 max "
            "absolute error divided by max absolute reference. Main timing shape is n=512. "
            "Keep a correct general tail path and handle n<=0. The target is over "
            f"{args.target_gflops} GFLOP/s in all repeats, not a favorable sample. "
            "Start from the strongest correct source in the history. Prefer reducing "
            "packing/transposition overhead, redundant addressing/predication, or data movement. "
            "Consider a fixed-loop n==512 fast path with a general-size fallback. "
            "All arithmetic must compute the real full product for each fresh input."
        )
    capabilities = ["cpu", platform.machine(), "single-thread"]
    if platform.machine() == "arm64":
        capabilities += ["neon", "simd"]
        sme = subprocess.run(["sysctl", "-n", "hw.optional.arm.FEAT_SME"],
                             capture_output=True, text=True, timeout=5)
        if sme.returncode == 0 and sme.stdout.strip() == "1":
            capabilities.append("sme")
    proposer = KernelAdvisoryTeam(work_dir=folder / "agent", task=task,
        timeout=args.agent_timeout, max_rounds=args.max_candidates,
        profile=dict(capabilities=capabilities))
    evaluator = HillsKernelEvaluator(workspace=args.hill_workspace)

    def evaluate(source_dir, report_path, *, final, timeout):
        before = host_observation()
        require_ac(before)
        if before['power_settings'] != initial_host['power_settings']:
            raise RuntimeError('Power settings changed from the AC baseline')
        observations = dict(before=before)
        host_path = Path(report_path).with_suffix('.host.json')
        save_json(host_path, observations)
        try:
            return evaluator(source_dir, report_path, final=final, timeout=timeout)
        finally:
            after = host_observation()
            observations['after'] = after
            save_json(host_path, observations)
            require_ac(after)
            if after['power_settings'] != initial_host['power_settings']:
                raise RuntimeError('Power settings changed during measurement')

    try:
        report = optimize_kernel(
            baseline=KernelCandidate("existing-sme", args.baseline.read_text(), "Unchanged existing SME kernel"),
            propose=proposer, evaluate=evaluate,
            validate=validate_cpu_kernel,
            output_dir=folder / "search", max_candidates=args.max_candidates,
            target_gflops=args.target_gflops, max_seconds=args.max_seconds,
        )
    except BaseException:
        with (folder / "journal.md").open("a") as stream:
            stream.write("\nStatus: interrupted or failed. Inspect search/result.json and agent logs.\n")
        raise
    proposer.observe(report["trials"])
    with (folder / "journal.md").open("a") as stream:
        stream.write(f"\nStatus: {report['status']}. Target met: {report['target_met']}.\n")
        for trial in report["trials"]:
            stream.write(f"\n- {trial['name']}: {trial['status']}; scores={trial['scores']}; "
                         f"controls={trial['control_scores']}\n")
        stream.write(f"\nFinal GFLOP/s: {report['final_gflops']}. Winner: {report['winner_source']}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
