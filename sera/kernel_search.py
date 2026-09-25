"""Experimental, evaluator-owned CPU kernel search. No hosted model clients.

The caller supplies a proposer and a trusted evaluator. Native code execution
requires an external sandbox or an explicitly trusted local research workspace.
This module is not the vLLM swarm and does not deploy a model.
"""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from statistics import median
import time

from .storage import save_json


@dataclass(frozen=True)
class KernelCandidate:
    name: str
    source: str
    hypothesis: str

    def __post_init__(self):
        if any(not isinstance(value, str) or not value.strip()
               for value in (self.name, self.source, self.hypothesis)):
            raise ValueError("Candidate name, source, and hypothesis must be nonempty text")
        if len(self.source.encode()) > 256_000:
            raise ValueError("Kernel source exceeds 256 KB")


def _identity(report):
    config = {item["name"]: item["value"] for item in report["config"]}
    details = report.get("details", {})
    return dict(tree_hash=report["tree_hash"],
                config={key: value for key, value in config.items() if key != "mode"},
                runtime={key: details.get(key) for key in
                         ("compiler", "compiler_flags", "architecture", "platform")})


def _score(report, *, final, identity):
    if report.get("official") is not True or not report.get("tree_hash"):
        raise ValueError("Evaluator must return a frozen official report")
    if report.get("final") is not final:
        raise ValueError("Evaluator returned the wrong evaluation split")
    # Failure reports can lack machine metadata. They can never win.
    if report.get("passed") is not True:
        return None
    if identity is not None and _identity(report) != identity:
        raise ValueError("Evaluator or machine comparison identity changed")
    metrics = [item for item in report.get("metrics", []) if item.get("name") == "gflops"]
    if len(metrics) != 1 or metrics[0].get("direction") != "max":
        raise ValueError("Expected one maximizing gflops score")
    value = metrics[0].get("value")
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("Evaluator returned an invalid score")
    return float(value)


def optimize_kernel(*, baseline, propose, evaluate, output_dir, max_candidates=8,
                    repeats=3, target_gflops=1780.0, min_improvement=0.05,
                    max_seconds=1800.0, trial_timeout=120.0):
    """Search standalone gemm C sources; return source only after held-out checks.

    ``propose(history)`` returns a KernelCandidate or None. ``evaluate`` owns
    compilation, correctness, timing, and report verification. Three repeats
    are the default, with median selection and all-repeat target confirmation.
    The selected source gets exactly one final evaluation. A failed final check
    returns no deployable source. A fresh output directory is mandatory.

    The deadline bounds evaluator calls and is checked around proposer calls;
    the proposer must enforce its own timeout. Interrupted runs are inspectable
    but automatic resume is not implemented.
    """
    if type(max_candidates) is not int or not 0 <= max_candidates <= 100:
        raise ValueError("max_candidates must be an integer from 0 to 100")
    if type(repeats) is not int or not 3 <= repeats <= 10:
        raise ValueError("Use 3 to 10 validation repeats")
    for name, value in (("target_gflops", target_gflops), ("max_seconds", max_seconds),
                        ("trial_timeout", trial_timeout)):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if not 0 <= min_improvement < 1:
        raise ValueError("min_improvement must be in [0, 1)")
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    report = dict(schema_version="sera-kernel-search-v1", status="running", trials=[],
                  target_gflops=target_gflops, target_met=False, winner_source=None,
                  policy=dict(max_candidates=max_candidates, repeats=repeats,
                              min_improvement=min_improvement, max_seconds=max_seconds),
                  limits=["Experimental CPU source search; not the vLLM swarm",
                          "Trusted evaluator and proposer; no native-code sandbox",
                          "No automatic resume or model deployment"])
    deadline = time.monotonic() + max_seconds
    identity = None
    seen = set()

    def save():
        save_json(folder / "result.json", report)

    def measure(source_dir, destination, *, final=False):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Kernel search deadline reached")
        result = evaluate(source_dir, destination, final=final,
                          timeout=min(trial_timeout, remaining))
        return result, _score(result, final=final, identity=identity)

    def trial(candidate, control=None):
        nonlocal identity
        source_hash = hashlib.sha256(candidate.source.encode()).hexdigest()
        if source_hash in seen:
            return None
        seen.add(source_hash)
        trial_dir = folder / f"trial-{len(report['trials']):03d}"
        source_dir = trial_dir / "source"
        source_dir.mkdir(parents=True)
        source = source_dir / "kernel.c"
        source.write_text(candidate.source)
        record = dict(name=candidate.name, hypothesis=candidate.hypothesis,
                      source=str(source), source_hash=source_hash, status="running",
                      scores=[], reports=[], control_scores=[], control_reports=[],
                      median_gflops=None)
        report["trials"].append(record)
        save()
        for repeat in range(repeats):
            def measure_control():
                control_path = trial_dir / f"control-{repeat}.json"
                control_source = Path(control["source"])
                _, control_score = measure(control_source.parent, control_path)
                if (control_score is None or
                        hashlib.sha256(control_source.read_bytes()).hexdigest() != control["source_hash"]):
                    raise ValueError("Unchanged control failed correctness or changed source")
                record["control_scores"].append(control_score)
                record["control_reports"].append(str(control_path))
                save()

            # Fixed alternating AB/BA order reduces ordering bias and is reproducible.
            if control is not None and repeat % 2 == 0:
                measure_control()
            destination = trial_dir / f"validation-{repeat}.json"
            measured, score = measure(source_dir, destination)
            record["reports"].append(str(destination))
            if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
                raise ValueError("Kernel source changed during evaluation")
            if score is None:
                record.update(status="rejected", error=measured.get("details", {}).get("error"))
                save()
                return record
            if identity is None:
                identity = _identity(measured)
                report["comparison_identity"] = identity
            record["scores"].append(score)
            save()
            if control is not None and repeat % 2 == 1:
                measure_control()
        record.update(status="passed", median_gflops=median(record["scores"]))
        save()
        return record

    save()
    try:
        best = trial(baseline)
        if best["status"] != "passed":
            raise ValueError("Baseline failed correctness; search cannot start")
        for _ in range(max_candidates):
            if time.monotonic() >= deadline:
                raise TimeoutError("Kernel search deadline reached")
            history = deepcopy(report["trials"])
            if callable(getattr(propose, "propose", None)):
                candidate = propose.propose(history, timeout=deadline - time.monotonic())
            else:
                candidate = propose(history)
            if candidate is None:
                report["stop_reason"] = "search-exhausted"
                break
            current = trial(candidate, control=best)
            if current is None:
                report["stop_reason"] = "duplicate-source"
                break
            # Promotion requires separated observed ranges, not a lucky best sample.
            if (current["status"] == "passed" and min(current["scores"]) >
                    max(current["control_scores"]) * (1 + min_improvement)):
                best = current
            if min(best["scores"]) > target_gflops:
                report["stop_reason"] = "validation-target-reached"
                break
        else:
            report["stop_reason"] = "candidate-budget"
        report["selected_source"] = best["source"]
        save()
        final_path = folder / "final.json"
        final_report, final_score = measure(Path(best["source"]).parent, final_path, final=True)
        if hashlib.sha256(Path(best["source"]).read_bytes()).hexdigest() != best["source_hash"]:
            raise ValueError("Selected source changed during final evaluation")
        report.update(final_report=str(final_path), final_gflops=final_score,
                      status="completed" if final_score is not None else "holdout-failed")
        final_floor = min(best["scores"]) * (1 - min_improvement)
        report["final_minimum_gflops"] = final_floor
        if final_score is not None and final_score < final_floor:
            report["status"] = "final-performance-unconfirmed"
        elif final_score is not None:
            report.update(winner_source=best["source"],
                          target_met=min(best["scores"] + [final_score]) > target_gflops)
        save()
        return report
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        save()
        raise
