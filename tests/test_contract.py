"""The public contract, as executable assertions.

This is the integration boundary between the product surface and the backend.
A backend satisfies the contract when `check_result_contract` passes on what its
`run()` returns — so the engine can be developed against these tests without the
notebook, and the notebook against the fixture without the engine.

Keep assertions here about *shape and invariants*, never about the fixture's
particular numbers; those are illustrative and will change.
"""

from __future__ import annotations

import pytest

import sera_loop
from sera_loop import fixtures


def check_result_contract(result: sera_loop.SeraResult) -> None:
    """Assert a SeraResult is well-formed. Reusable by backend tests."""
    assert isinstance(result.state, sera_loop.RunState)
    assert result.mode in {"quick", "verified"}
    assert isinstance(result.report, dict)

    # A recommendation is required exactly when the run claims an improvement.
    if result.state is sera_loop.RunState.IMPROVED:
        assert result.recommended is not None, "IMPROVED runs must carry a recommendation"
    if result.state is sera_loop.RunState.NO_SAFE_IMPROVEMENT:
        assert result.recommended is None, "no-safe-improvement must not recommend a change"

    # Every model handed back must be usable and traceable to a revision.
    for model in result.models:
        assert model.model_id
        assert model.revision, "revisions are pinned so comparisons reproduce"
        assert isinstance(model.configuration, sera_loop.InferenceConfig)
        assert isinstance(model.metrics_snapshot, sera_loop.Measurement)

    # Executed trials carry measurements; paper rejections never do.
    for trial in result.trials:
        assert isinstance(trial.verdict, sera_loop.Verdict)
        assert trial.ran == trial.verdict.ran
        if trial.verdict is sera_loop.Verdict.ACCEPTED:
            assert trial.measurement is not None, f"{trial.trial_id} accepted without a measurement"
        if not trial.ran:
            assert trial.measurement is None, f"{trial.trial_id} never ran but has a measurement"

    # Deterministic rejections are separate from failed trials, and must say why.
    for rejection in result.rejected:
        assert rejection.reason, "a rejection the user cannot read is not a rejection"
        assert isinstance(rejection.configuration, sera_loop.InferenceConfig)

    # Frontier entries are viable by definition.
    for entry in result.frontier:
        assert entry.quality.passed, "a configuration that failed quality cannot be on the frontier"


class TestVocabulary:
    """The user-facing words are part of the contract, not incidental strings."""

    def test_every_verdict_has_a_user_facing_label(self):
        for verdict in sera_loop.Verdict:
            assert verdict in sera_loop.VERDICT_LABELS
            assert sera_loop.VERDICT_LABELS[verdict]

    def test_every_run_state_has_a_headline(self):
        for state in sera_loop.RunState:
            assert state in sera_loop.RUN_STATE_HEADLINES
            assert sera_loop.RUN_STATE_HEADLINES[state]

    def test_report_sections_are_ordered_and_unique(self):
        assert len(sera_loop.REPORT_SECTIONS) == len(set(sera_loop.REPORT_SECTIONS))


class TestDemoFixture:
    def test_satisfies_the_contract(self):
        check_result_contract(fixtures.demo_result())

    def test_reports_an_improvement(self):
        result = fixtures.demo_result()
        assert result.state is sera_loop.RunState.IMPROVED
        assert result.recommended is not None
        # Negative percentage means faster.
        assert result.recommended.latency_change_pct < 0

    def test_separates_paper_rejections_from_failed_trials(self):
        result = fixtures.demo_result()
        assert result.rejected, "the demo should show candidates ruled out before running"
        failed = [t for t in result.trials if t.verdict is sera_loop.Verdict.FAILED]
        assert failed, "the demo should show a trial that ran and failed"
        # The two are genuinely different categories, not the same list twice.
        assert result.trials_run < len(result.trials) + len(result.rejected)

    def test_quick_mode_does_not_claim_verified_quality(self):
        result = fixtures.demo_result()
        assert result.mode == "quick"
        assert result.recommended is not None
        assert result.recommended.quality.verified is False
        assert "not verified" in result.recommended.quality.caveat

    def test_summary_renders_every_section(self):
        text = "\n".join(fixtures.demo_result().summary_lines())
        for section in sera_loop.REPORT_SECTIONS:
            assert section in text, f"summary is missing the {section!r} section"

    def test_summary_names_the_rolled_back_trials(self):
        text = "\n".join(fixtures.demo_result().summary_lines())
        assert "Quality dropped — rolled back" in text
        assert "Too slow — rolled back" in text

    def test_print_summary_writes_output(self, capsys):
        fixtures.demo_result().print_summary()
        assert capsys.readouterr().out.strip()

    def test_as_dict_is_serializable(self):
        import json

        json.dumps(fixtures.demo_result().as_dict(), default=str)


class TestNoSafeImprovementFixture:
    """The honest-negative path is a supported outcome, not an error."""

    def test_satisfies_the_contract(self):
        check_result_contract(fixtures.no_safe_improvement_result())

    def test_returns_baseline_models_and_no_recommendation(self):
        result = fixtures.no_safe_improvement_result()
        assert result.state is sera_loop.RunState.NO_SAFE_IMPROVEMENT
        assert result.recommended is None
        assert result.models, "the user still gets a usable model back"

    def test_summary_explains_itself_without_reading_as_a_crash(self):
        result = fixtures.no_safe_improvement_result()
        text = "\n".join(result.summary_lines())
        assert "no configuration" in result.headline.lower()
        assert "What was ruled out" in text

    def test_summary_renders_every_section(self):
        """The negative path owes the user the same account as the happy path.

        This is the case where sections were previously dropped because there was
        no recommendation to hang them on.
        """
        text = "\n".join(fixtures.no_safe_improvement_result().summary_lines())
        for section in sera_loop.REPORT_SECTIONS:
            assert section in text, f"summary is missing the {section!r} section"

    def test_summary_shows_the_evidence_for_stopping(self):
        """A negative result is only credible if it says what was tried."""
        result = fixtures.no_safe_improvement_result()
        text = "\n".join(result.summary_lines())
        for trial in result.trials:
            if trial.ran:
                assert trial.trial_id in text, f"{trial.trial_id} ran but is not in the summary"
        # The quality failure must be quantified, not merely asserted.
        assert "0.948" in text
        # Baseline numbers stand in for the improvement that did not happen.
        assert "705" in text


class TestOptimizeSignature:
    def test_rejects_empty_models(self):
        with pytest.raises(ValueError, match="at least one model"):
            sera_loop.optimize(models=[], prompts=["hi"])

    def test_rejects_empty_prompts(self):
        with pytest.raises(ValueError, match="at least one representative prompt"):
            sera_loop.optimize(models=["m"], prompts=[])

    def test_verified_mode_requires_a_quality_floor(self):
        with pytest.raises(ValueError, match="quality floor"):
            sera_loop.optimize(models=["m"], prompts=["p"], evaluation=lambda *a: 1.0)

    def test_without_a_backend_it_says_so_and_points_at_the_fixture(self):
        with pytest.raises(sera_loop.SeraBackendUnavailable, match="fixtures"):
            sera_loop.optimize(models=["m"], prompts=["p"])

    def test_a_registered_backend_receives_resolved_defaults(self):
        captured = {}

        class FakeBackend:
            def run(self, **kwargs):
                captured.update(kwargs)
                return fixtures.demo_result()

        result = sera_loop.optimize(models=["m"], prompts=["p"], backend=FakeBackend())

        check_result_contract(result)
        # Defaults are resolved at the boundary so the backend never sees None.
        assert captured["workload"] == sera_loop.Workload()
        assert captured["budget"] == sera_loop.Budget()
        assert captured["models"] == ["m"]


class TestFixtureBackedModels:
    def test_generate_returns_canned_text(self):
        model = fixtures.demo_result().models[0]
        assert model.generate("anything")

    def test_a_closed_model_refuses_rather_than_pretending(self):
        model = fixtures.demo_result().models[0]
        model.close()
        with pytest.raises(sera_loop.SeraBackendUnavailable, match="fixture"):
            model.generate("anything")
