"""Narrow W&B replay adapters using the unchanged product proposal schemas."""

from copy import deepcopy
import time

from pydantic import ValidationError

from sera.agent import Proposal, SCHEMAS, schema_hash, validate_proposal
from sera.config import MODEL_ID
from sera.provider_check import require_provider_check
from sera.storage import content_hash

from .search import StopSearch, freeze_manifest


VARIANTS = {'full-evidence', 'no-history', 'no-reduced-telemetry', 'round-robin'}
ROLES = ('quantization', 'batching')
LEVER_ROLES = {
    'kv_cache_dtype': 'quantization', 'quantization': 'quantization',
    'max_num_batched_tokens': 'batching', 'max_num_seqs': 'batching',
    'max_model_len': 'batching',
}
SPECIALIST_INSTRUCTION = (
    'Act only as specialist_role. Propose one untested configuration from legal_candidates, '
    'using supported_changes and the supplied parent trial. Or return keep-baseline with '
    'null setting/value and zero cost. Cite exact available metrics keys in evidence_used. '
    'Do not infer unobserved outcomes. Target lower p95 latency while preserving every '
    'frozen gate; peak memory breaks latency ties. State a falsifiable prediction. '
    'No GPU trial is executed by this call.'
)
ARBITER_INSTRUCTION = (
    'Rank at most one ID from legal_proposal_ids for the remaining budget, or return an '
    'empty ranking to stop. Use only supplied observed evidence. Predictions are not '
    'measurements. Prefer expected quality-valid latency improvement, with peak memory '
    'as a tie-breaker. Do not invent candidates or unobserved outcomes.'
)


class UnsupportedPolicy(ValueError):
    """The unchanged product schemas cannot represent a faithful requested policy."""


def _metrics(record):
    return {
        'p95_latency_ms': record['p95_latency_ms'],
        'peak_memory_mib': record['peak_memory_mib'],
        **{f'telemetry.{key}': value for key, value in record.get('telemetry', {}).items()},
    }


def project_evidence(view, variant):
    """Remove ablated evidence structurally; never rely on an instruction to ignore it."""
    if variant not in VARIANTS:
        raise ValueError('Unknown policy variant')
    baseline = view['baseline']
    metrics = {} if variant == 'no-reduced-telemetry' else _metrics(baseline)
    evidence = {
        'manifest_hash': view['manifest_hash'], 'identity': deepcopy(view['identity']),
        'trial_id': baseline['candidate_id'], 'model_id': MODEL_ID,
        'configuration': deepcopy(baseline['configuration']), 'metrics': metrics,
        'remaining_trials': view['remaining_trials'],
        'remaining_candidate_ids': list(view['remaining_candidate_ids']),
        'candidates': deepcopy(view['candidates']),
        'baseline_gates': {key: baseline[key] for key in (
            'status', 'feasibility_passed', 'reliability_passed', 'quality_passed')},
    }
    if variant != 'no-history':
        history = []
        for record in view['observed']:
            item = {key: deepcopy(record[key]) for key in (
                'candidate_id', 'configuration', 'status', 'feasibility_passed',
                'reliability_passed', 'quality_passed')}
            item['metrics'] = {} if variant == 'no-reduced-telemetry' else _metrics(record)
            history.append(item)
            metrics.update({f'observed.{record["candidate_id"]}.{key}': value
                            for key, value in item['metrics'].items()})
        evidence['history'] = history
        # Prior prose can quote ablated measurements, so it is never copied into prompts.
        evidence['proposal_log'] = [{key: item.get(key) for key in ('candidate_id', 'status')}
                                    for item in view['proposal_log']]
    return evidence


def _candidate_proposal(entry, baseline):
    changed = {key: value for key, value in entry['configuration'].items()
               if value != baseline[key]}
    if len(changed) != 1:
        raise UnsupportedPolicy('Current proposal schema cannot represent combination candidates')
    lever, value = next(iter(changed.items()))
    try:
        proposal = Proposal(
            action='trial', proposal_id=entry['candidate_id'], agent_role=LEVER_ROLES.get(lever),
            parent_trial_id='schema-preflight', model_id=MODEL_ID,
            changed_lever=lever, proposed_value=value, evidence_used=['p95_latency_ms'],
            predicted_metric_change='Schema preflight; no performance prediction', confidence=0.0,
            expected_trial_cost=1, falsification_condition='Not a model proposal', reason='Schema preflight',
        )
        if proposal.to_candidate(baseline).config.config_hash != entry['config_hash']:
            raise ValueError('Schema reconstruction changed configuration')
    except (ValueError, ValidationError) as error:
        raise UnsupportedPolicy('Current proposal schema cannot represent every frozen candidate') from error
    return proposal


class WandbSearchPolicy:
    """Two-specialist subset, not the complete section 19 Sera search architecture."""

    def __init__(self, manifest, client, *, provider_check, variant='full-evidence',
                 max_provider_requests=12):
        if variant not in VARIANTS:
            raise ValueError('Unknown policy variant')
        if variant == 'no-reduced-telemetry':
            raise UnsupportedPolicy(
                'Exact no-reduced-telemetry removes metrics, but Proposal requires nonempty '
                'evidence_used and validate_proposal requires those metric names to exist')
        if type(max_provider_requests) is not int or not 1 <= max_provider_requests <= 96:
            raise ValueError('Provider request limit must be an integer in 1..96')
        expected = freeze_manifest(
            manifest['identity'], manifest['baseline']['configuration'],
            [item['configuration'] for item in manifest['candidates']], budget=manifest['budget'],
            evidence_kind=manifest['evidence_kind'], compatibility=manifest['compatibility'],
            random_seeds=manifest['random_seeds'], max_proposals=manifest['max_proposals'],
        )
        if expected != manifest:
            raise ValueError('Manifest does not match its frozen configuration')
        self.manifest = deepcopy(manifest)
        self.variant = variant
        self.client = client
        self.max_provider_requests = max_provider_requests
        self.round_robin_index = 0
        self.representable = {
            item['candidate_id']: _candidate_proposal(item, manifest['baseline']['configuration'])
            for item in manifest['candidates']
        }
        self.provider_validation = require_provider_check(provider_check, client)
        self.schema_hash = schema_hash()
        settings = {
            'adapter_version': 'sera-narrow-search-policy-v1', 'variant': variant,
            'manifest_hash': manifest['manifest_hash'], 'schema_hash': self.schema_hash,
            'provider_model': client.model, 'provider_project': client.project,
            'max_provider_requests': max_provider_requests, 'roles': list(ROLES),
            'specialist_instruction': SPECIALIST_INSTRUCTION, 'arbiter_instruction': ARBITER_INSTRUCTION,
        }
        self.audit = {
            'settings': settings, 'policy_hash': content_hash(settings),
            'provider_validation': deepcopy(self.provider_validation), 'calls': [], 'decisions': [],
            'benchmark_claim': 'not-assessed',
            'limitations': ['Only schema-representable single-setting candidates are supported.',
                           'No-history has no effect before a first selected trial.',
                           'This adapter does not implement the full section 19 Sera policy.'],
        }

    def export_audit(self):
        return deepcopy(self.audit)

    def _request(self, role, evidence, instruction):
        if len(self.audit['calls']) >= self.max_provider_requests:
            self.audit['decisions'][-1]['stop_reason'] = 'provider-request-budget'
            raise StopSearch()
        entry = {'role': role, 'evidence': deepcopy(evidence), 'evidence_hash': content_hash(evidence),
                 'instruction': instruction, 'schema_hash': content_hash(SCHEMAS[role].model_json_schema())}
        self.audit['calls'].append(entry)
        prior_calls = len(self.client.history)
        started = time.perf_counter()
        try:
            parsed = self.client.request(role, deepcopy(evidence), instruction)
            if parsed is None:
                entry['status'] = 'no-schema-valid-response'
                return None
            parsed = SCHEMAS[role].model_validate(parsed.model_dump())
            entry.update(status='schema-valid', parsed=parsed.model_dump())
            return parsed
        except Exception as error:
            entry.update(status='request-error', error_type=type(error).__name__)
            return None
        finally:
            entry['elapsed_seconds'] = time.perf_counter() - started
            entry['provider_calls'] = deepcopy(self.client.history[prior_calls:])

    def __call__(self, view):
        if (view['manifest_hash'] != self.manifest['manifest_hash']
                or view['identity'] != self.manifest['identity']
                or view['candidates'] != self.manifest['candidates']
                or schema_hash() != self.schema_hash):
            raise ValueError('Policy view or product schemas changed after adapter creation')
        evidence = project_evidence(view, self.variant)
        decision = {'call_index': len(self.audit['decisions']), 'evidence_hash': content_hash(evidence),
                    'selected_candidate_id': None, 'validations': []}
        self.audit['decisions'].append(decision)
        remaining = set(view['remaining_candidate_ids'])
        if not remaining <= self.representable.keys():
            raise ValueError('View contains a candidate outside the frozen universe')
        active = [role for role in ROLES if any(
            self.representable[key].agent_role == role for key in remaining)]
        if not active or view['remaining_trials'] <= 0:
            decision['stop_reason'] = 'no-remaining-experiment'
            raise StopSearch()
        if self.variant == 'round-robin':
            ordered = list(ROLES[self.round_robin_index:]) + list(ROLES[:self.round_robin_index])
            active = [next(role for role in ordered if role in active)]
            self.round_robin_index = (ROLES.index(active[0]) + 1) % len(ROLES)
        valid = {}
        had_invalid_response = False
        for role in active:
            legal = [item for item in view['candidates']
                     if item['candidate_id'] in remaining and self.representable[item['candidate_id']].agent_role == role]
            changes = {}
            for item in legal:
                proposal = self.representable[item['candidate_id']]
                changes.setdefault(proposal.changed_lever, []).append(proposal.proposed_value)
            specialist_evidence = {**deepcopy(evidence), 'specialist_role': role,
                                   'legal_candidates': legal, 'supported_changes': changes}
            parsed = self._request('proposal', specialist_evidence, SPECIALIST_INSTRUCTION)
            check = {'role': role, 'status': 'rejected'}
            decision['validations'].append(check)
            try:
                if parsed is None or parsed.agent_role != role:
                    raise ValueError('Missing response or wrong specialist role')
                candidate = validate_proposal(parsed, specialist_evidence)
                if candidate is None:
                    check['status'] = 'abstained'
                    continue
                key = candidate.config.config_hash
                if key not in {item['candidate_id'] for item in legal} or parsed.proposal_id in valid:
                    raise ValueError('Out-of-universe configuration or duplicate proposal ID')
                valid[parsed.proposal_id] = {'candidate_id': key, 'proposal': parsed.model_dump()}
                check.update(status='accepted', proposal_id=parsed.proposal_id, candidate_id=key)
            except (ValueError, ValidationError) as error:
                had_invalid_response = True
                check['error_type'] = type(error).__name__
        if not valid:
            if had_invalid_response:
                decision['status'] = 'invalid-specialist-output'
                return None
            decision['stop_reason'] = 'specialists-abstained'
            raise StopSearch()
        if self.variant == 'round-robin':
            selected = next(iter(valid.values()))['candidate_id']
        else:
            arbiter_evidence = {**deepcopy(evidence), 'legal_proposal_ids': list(valid),
                                'proposals': list(valid.values())}
            ranked = self._request('arbiter', arbiter_evidence, ARBITER_INSTRUCTION)
            if ranked is None or any(key not in valid for key in ranked.ranked_proposal_ids):
                decision['status'] = 'invalid-arbiter-output'
                return None
            if not ranked.ranked_proposal_ids:
                decision['stop_reason'] = 'arbiter-abstained'
                raise StopSearch()
            selected = valid[ranked.ranked_proposal_ids[0]]['candidate_id']
        decision.update(status='selected', selected_candidate_id=selected)
        return selected
