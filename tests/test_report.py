"""The presentation layer must be total.

A renderer that raises is a demo that dies on stage, so the central test here is
not that any particular string appears — it is that every rendering function
survives every shape of result, including empty and failed runs.
"""

from __future__ import annotations

import pytest

import sera
from sera import fixtures, report

# Functions that take a SeraResult and must never raise.
RENDERERS = [
    report.state_banner,
    report.progress_rows,
    report.rejection_rows,
    report.failure_rows,
    report.improvement_rows,
    report.baseline_rows,
    report.frontier_rows,
    report.recommendation_md,
    report.quality_md,
    report.run_details_md,
    report.usage_snippet,
    report.config_snippet,
    report.counts,
]


def empty_result(state: sera.RunState) -> sera.SeraResult:
    """The worst case: a run that produced nothing at all."""
    return sera.SeraResult(state=state)


ALL_RESULTS = [
    pytest.param(fixtures.demo_result(), id="improved"),
    pytest.param(fixtures.no_safe_improvement_result(), id="no-safe-improvement"),
    *[
        pytest.param(empty_result(state), id=f"empty-{state.value}")
        for state in sera.RunState
    ],
]


@pytest.mark.parametrize("result", ALL_RESULTS)
@pytest.mark.parametrize("renderer", RENDERERS, ids=lambda f: f.__name__)
def test_renderer_never_raises(renderer, result):
    renderer(result)


@pytest.mark.parametrize("result", ALL_RESULTS)
def test_every_state_has_a_callout_kind(result):
    _, kind = report.state_banner(result)
    assert kind in {"success", "info", "warn", "danger"}


class TestProgress:
    def test_excludes_candidates_that_never_ran(self):
        result = fixtures.demo_result()
        rows = report.progress_rows(result)
        assert len(rows) == result.trials_run
        # Paper rejections are reported separately, never as executed trials.
        assert len(report.rejection_rows(result)) == len(result.rejected)

    def test_missing_measurements_read_as_unavailable_not_zero(self):
        """A failed trial has no numbers. Showing 0 would read as 'instant'."""
        result = fixtures.demo_result()
        failed = [r for r in report.progress_rows(result) if r["Outcome"] == "Failed to run"]
        assert failed, "the demo fixture should contain a failed trial"
        assert failed[0]["p95 (ms)"] == "unavailable"

    def test_counts_add_up(self):
        result = fixtures.demo_result()
        c = report.counts(result)
        assert c["trials_run"] == c["accepted"] + c["rolled_back"] + c["failed"]
        assert c["ruled_out"] == len(result.rejected)


class TestFailures:
    def test_lists_rollbacks_and_crashes_but_not_successes(self):
        rows = report.failure_rows(fixtures.demo_result())
        outcomes = {r["What happened"] for r in rows}
        assert "Accepted" not in outcomes
        assert "Quality dropped — rolled back" in outcomes
        assert "Failed to run" in outcomes

    def test_every_failure_carries_a_readable_detail(self):
        for result in (fixtures.demo_result(), fixtures.no_safe_improvement_result()):
            for row in report.failure_rows(result):
                assert row["Detail"], "a failure the user cannot read is not useful"


class TestRecommendation:
    def test_names_the_levers_that_changed(self):
        md = report.recommendation_md(fixtures.demo_result())
        assert "max_num_seqs" in md
        assert "→" in md

    def test_no_recommendation_explains_itself(self):
        md = report.recommendation_md(fixtures.no_safe_improvement_result())
        assert "No change recommended" in md
        assert "baseline" in md.lower()

    def test_improvement_rows_empty_without_a_recommendation(self):
        assert report.improvement_rows(fixtures.no_safe_improvement_result()) == []
        # The caller has baselines to fall back on.
        assert report.baseline_rows(fixtures.no_safe_improvement_result())


class TestQuality:
    def test_quick_mode_never_claims_verification(self):
        md = report.quality_md(fixtures.demo_result())
        assert "not verified" in md

    def test_quality_failure_is_quantified(self):
        md = report.quality_md(fixtures.no_safe_improvement_result())
        assert "0.948" in md
        assert "0.990" in md


class TestCopyableOutput:
    """B4 win condition 4: "what model object do I use now?"."""

    def test_usage_snippet_is_valid_python(self):
        for result in (fixtures.demo_result(), fixtures.no_safe_improvement_result()):
            compile(report.usage_snippet(result), "<snippet>", "exec")

    def test_usage_snippet_names_the_real_model(self):
        snippet = report.usage_snippet(fixtures.demo_result())
        assert "Qwen/Qwen3-0.6B" in snippet
        assert "result.models[0]" in snippet

    def test_usage_snippet_works_when_nothing_was_recommended(self):
        """The baseline models still come back and are still usable."""
        snippet = report.usage_snippet(fixtures.no_safe_improvement_result())
        assert "sera.optimize(" in snippet
        assert "generate(" in snippet

    def test_config_snippet_is_valid_python_literal(self):
        import ast

        for result in (fixtures.demo_result(), fixtures.no_safe_improvement_result()):
            body = report.config_snippet(result)
            literal = "\n".join(ln for ln in body.splitlines() if not ln.startswith("#"))
            assert isinstance(ast.literal_eval(literal), dict)

    def test_config_snippet_reports_the_recommended_levers(self):
        snippet = report.config_snippet(fixtures.demo_result())
        assert "'max_num_seqs': 512" in snippet

    def test_config_snippet_labels_the_baseline_when_nothing_changed(self):
        snippet = report.config_snippet(fixtures.no_safe_improvement_result())
        assert "No change was recommended" in snippet


class TestRunDetails:
    def test_includes_the_trace_link_when_present(self):
        md = report.run_details_md(fixtures.demo_result())
        assert "wandb.ai" in md

    def test_survives_a_result_with_no_trace(self):
        result = fixtures.demo_result()
        result.weave_url = None
        assert "Mode" in report.run_details_md(result)
