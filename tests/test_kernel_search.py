import json
from pathlib import Path

import pytest

from sera.kernel_search import KernelCandidate, optimize_kernel


def scored(value, *, passed=True, tree="frozen", machine="test-cpu", final=False):
    return dict(passed=passed, official=True, tree_hash=tree, final=final,
                config=[dict(name="machine", value=machine),
                        dict(name="mode", value="test" if final else "validation"),
                        dict(name="n", value=512), dict(name="tolerance", value=0.002)],
                metrics=[dict(name="gflops", value=value, direction="max")])


class Evaluator:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def __call__(self, source_dir, report_path, *, final, timeout):
        source = (source_dir / "kernel.c").read_text()
        self.calls.append((source, final))
        value = self.values[source]
        report = value(final) if callable(value) else scored(value, final=final)
        report_path.write_text(json.dumps(report))
        return report


def run(tmp_path, values, **options):
    evaluator = Evaluator(values)
    result = optimize_kernel(
        baseline=KernelCandidate("baseline", "base", "reference"),
        propose=options.pop("propose", lambda history: KernelCandidate("candidate", "new", "test")),
        evaluate=evaluator, output_dir=tmp_path / "run", max_candidates=1,
        **options,
    )
    return result, evaluator


def test_retains_correct_faster_source_and_tests_it_once_on_holdout(tmp_path):
    report, evaluator = run(tmp_path, {"base": 1000, "new": 1900})
    assert report["target_met"] is True
    assert Path(report["winner_source"]).read_text() == "new"
    assert evaluator.calls == [("base", False)] * 3 + [
        ("base", False), ("new", False), ("new", False), ("base", False),
        ("base", False), ("new", False), ("new", True)]
    assert json.loads((tmp_path / "run/result.json").read_text()) == report


def test_fast_incorrect_candidate_cannot_replace_baseline(tmp_path):
    report, _ = run(tmp_path, {"base": 1000, "new": lambda final: scored(9999, passed=False, final=final)})
    assert report["target_met"] is False
    assert Path(report["winner_source"]).read_text() == "base"


@pytest.mark.parametrize("override", [{"tree": "changed"}, {"machine": "other"}])
def test_changed_evaluator_or_machine_stops_comparison(tmp_path, override):
    with pytest.raises(ValueError, match="comparison"):
        run(tmp_path, {"base": 1000, "new": lambda final: scored(1900, final=final, **override)})
    report = json.loads((tmp_path / "run/result.json").read_text())
    assert report["status"] == "failed"
    assert not report["target_met"]


def test_duplicate_source_is_not_measured_twice(tmp_path):
    report, evaluator = run(tmp_path, {"base": 1000},
                            propose=lambda history: KernelCandidate("renamed", "base", "duplicate"))
    assert report["stop_reason"] == "duplicate-source"
    assert len(evaluator.calls) == 4


def test_target_requires_all_validation_repeats_and_holdout(tmp_path):
    scores = iter([2000, 1500, 2000])
    report, _ = run(tmp_path, {"base": 1000,
        "new": lambda final: scored(2000 if final else next(scores), final=final)})
    assert report["trials"][1]["median_gflops"] == 2000
    assert report["target_met"] is False


def test_timing_ranges_must_separate_before_promotion(tmp_path):
    values = iter([1600, 1600, 1600, 1600, 1850, 1600])
    report, _ = run(tmp_path, {"base": lambda final: scored(1600 if final else next(values), final=final),
                              "new": 1900})
    assert Path(report["winner_source"]).read_text() == "base"
    assert report["trials"][1]["control_scores"] == [1600, 1850, 1600]


def test_holdout_failure_does_not_deliver_candidate(tmp_path):
    report, _ = run(tmp_path, {"base": 1000,
        "new": lambda final: scored(1900, passed=not final, final=final)})
    assert report["winner_source"] is None
    assert report["target_met"] is False
    assert report["status"] == "holdout-failed"


def test_final_timing_regression_does_not_deliver_candidate(tmp_path):
    report, _ = run(tmp_path, {"base": 1000,
        "new": lambda final: scored(500 if final else 1900, final=final)})
    assert report["winner_source"] is None
    assert report["status"] == "final-performance-unconfirmed"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True])
def test_invalid_scores_are_rejected(tmp_path, value):
    with pytest.raises(ValueError, match="score"):
        run(tmp_path, {"base": value, "new": 1900})


def test_existing_output_directory_is_never_overwritten(tmp_path):
    (tmp_path / "run").mkdir()
    with pytest.raises(FileExistsError):
        run(tmp_path, {"base": 1000, "new": 1900})


def test_proposer_receives_measured_history(tmp_path):
    def propose(history):
        assert history[0]["median_gflops"] == 1000
        return None
    report, _ = run(tmp_path, {"base": 1000}, propose=propose)
    assert report["stop_reason"] == "search-exhausted"
