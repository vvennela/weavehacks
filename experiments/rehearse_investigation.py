"""Offline controller rehearsal. All model, agent, and metric values are synthetic.

Run from the repository root:
    python -m experiments.rehearse_investigation --output-dir /tmp/sera-loop-rehearsal

The output directory must not exist. This command never contacts an LM or GPU.
Fixtures are injected only within this command; they are not a live fallback.
"""

import argparse
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import sera
from sera import pipeline
from sera.agent import ArbiterDecision, FrontierDecision, Proposal
from sera.config import MODEL_ID
from sera.investigation_report import render_investigation


class SyntheticRunner:
    """A fixture with an explicit ready/closed lifecycle, not model inference."""

    def __init__(self, *, artifact_dir, configuration, model_id, revision):
        self.configuration = configuration
        self.artifact_dir = artifact_dir
        self.ready = False
        self.record = dict(configuration=configuration.model_dump(), model_id=model_id,
                           revision=revision, sampled_peak_memory_mib=2000,
                           provenance='synthetic', closed=True)

    def start(self):
        self.ready = True
        self.record['closed'] = False

    def close(self):
        self.ready = False
        self.record['closed'] = True

    def _require_ready(self):
        if not self.ready:
            raise RuntimeError('Synthetic runner is closed')

    def generate(self, prompt):
        self._require_ready()
        if prompt != 'What is 7 + 8?':
            raise ValueError('The synthetic runner supports only its declared fresh probe')
        return '{"answer": 15}'


def synthetic_collect(model, prompts, trial_id, *, baseline=False, workload):
    """Declare fixture outcomes; do not claim to measure elapsed time."""
    model._require_ready()
    cache_trial = model.configuration.kv_cache_dtype == 'fp8'
    latency = 100.0 if baseline else 10.0 if cache_trial else 80.0
    output = dict(prompt_index=0, text='{"answer": 0}' if cache_trial else '{"answer": 5}',
                  token_ids=[0] if cache_trial else [5], prompt_token_ids=[1], error=None)
    return dict(trial_id=trial_id, status='collected', runtime=model.record,
                config_hash=model.configuration.config_hash, input_token_ids=[[1]],
                quality=[output], self_check=[deepcopy(output)] if baseline else [], metrics={},
                provenance='synthetic', reduced=dict(p95_latency_ms=latency,
                    output_tokens_per_second=100.0, generation_errors=0, request_count=3))


class SyntheticAgent:
    """A scripted policy that requires saved rejection evidence for its second choice."""

    model, project = 'synthetic-agent', 'offline/rehearsal'

    def __init__(self):
        self.history = []

    def _record(self, role, evidence, response):
        self.history.append(dict(role=role, evidence=deepcopy(evidence),
                                 raw_response=response.model_dump(), provenance='synthetic'))
        return response

    def request(self, role, evidence, instruction):
        if role == 'arbiter':
            return self._record(role, evidence, ArbiterDecision(
                ranked_proposal_ids=evidence['legal_proposal_ids'][:1],
                reason='Choose the only active proposal in this scripted rehearsal'))
        history = evidence.get('history', [])
        after_failure = bool(history and not history[0]['trial']['task_quality']['passed']
                             and history[0]['review']['prediction_outcome'] == 'refuted')
        specialist = evidence['specialist_role']
        abstain = specialist == 'batching' and not after_failure
        lever, values = next(iter(evidence['supported_changes'].items()))
        reason = ('The earlier cache trial was fast but failed quality; test batching with baseline precision'
                  if after_failure else 'Wait for the cache experiment' if abstain else
                  'Test the declared cache-precision experiment')
        return self._record(role, evidence, Proposal(
            action='keep-baseline' if abstain else 'trial',
            proposal_id=f'{specialist}-{len(history) + 1}', agent_role=specialist,
            parent_trial_id=evidence['trial_id'], model_id=evidence['model_id'],
            changed_lever=None if abstain else lever, proposed_value=None if abstain else values[0],
            evidence_used=['trial_1_p95_latency_ms'] if after_failure else ['p95_latency_ms'],
            predicted_metric_change=('No change until the cache result is available' if abstain else
                                     'Reduce p95 by at least 5% while preserving task correctness'),
            confidence=.5, expected_trial_cost=0 if abstain else 1,
            falsification_condition='Quality fails or p95 improves by less than 5%', reason=reason))

    def review(self, evidence):
        accepted = evidence['decision']['selected'] == 'candidate'
        return self._record('frontier', evidence, FrontierDecision(
            selected_trial_id=evidence['eligible_trial_ids'][0],
            prediction_outcome='confirmed' if accepted else 'refuted',
            reason='The deterministic task and performance gates ' + ('passed' if accepted else 'rejected this trial')))


def run_rehearsal(output_dir):
    """Run the production bounded controller with isolated, labeled fixtures."""
    # Only this offline process uses these test boundaries. Real provider certification
    # and GPU startup remain unchanged outside the context, including after an error.
    with patch.object(pipeline, 'SeraModel', SyntheticRunner), \
         patch.object(pipeline, 'collect_trial', synthetic_collect), \
         patch('sera.provider_check.require_provider_check',
               return_value={'provenance': 'synthetic', 'provider_verified': False}):
        result = sera.optimize(models=[MODEL_ID], prompts=['What is 2 + 3?'],
            output_dir=output_dir, agent=SyntheticAgent(), provider_check='synthetic-only',
            budget=sera.Budget(max_candidate_trials=2),
            evaluation=lambda prompt, text: text == '{"answer": 5}',
            evaluation_version='synthetic-rehearsal-v1', constraints=sera.Constraints(quality_floor=.99))
        result.report['provenance'] = dict(kind='synthetic', gpu_trials=0, provider_calls=0,
            claim='Controller behavior only; no model quality, speedup, or search advantage claim')
        try:
            response = result.models[0].generate('What is 7 + 8?')
            result.report['rehearsal'] = dict(fresh_prompt='What is 7 + 8?', fresh_response=response,
                                             fresh_probe_passed=response == '{"answer": 15}')
        finally:
            result.close()
        summary = render_investigation(result.report)
        (result.output_dir / 'investigation.md').write_text(summary)
        # Keep the default entry-point report honest even before renderer integration.
        (result.output_dir / 'report.md').write_text(summary)
        return result.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    report = run_rehearsal(args.output_dir)
    print(render_investigation(report))


if __name__ == '__main__':
    main()
