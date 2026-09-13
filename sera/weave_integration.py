"""Weave adapters for recorded investigator responses and bounded trace reads."""

from .weave_evidence import QUERY_IDS, RECORDED_OPS


class TracedInvestigationAgent:
    """Experiment-local tracing; the underlying agent owns requests and raw history."""

    def __init__(self, agent, weave):
        self._agent = agent
        self._weave = weave
        self._children = []
        self._trace_failures = []

        def record_agent_response(record):
            """Log an already returned provider attempt; span duration is export time, not inference time."""
            return record

        self._record_response = weave.op(record_agent_response)

        def traced_request(name):
            def request(role, evidence, instruction):
                return self._call_and_record(agent.request, role, evidence, instruction)
            return weave.op(name=name)(request)

        def review(evidence):
            # Its internal request must not re-enter this adapter.
            return self._call_and_record(agent.review, evidence)

        # Official op naming API: https://docs.wandb.ai/weave/guides/tracking/ops
        self._requests = {name: traced_request(name) for name in (
            'fit_quantization_advisor', 'quantization_specialist', 'batching_specialist',
            'search_specialist', 'arbiter', 'frontier_reviewer', 'agent_request')}
        self._review = weave.op(name='frontier_reviewer')(review)
        self._swarm_requests = {(investigator, phase): traced_request(f'swarm_{investigator}_{label}')
            for investigator in ('scheduling', 'memory_context', 'output_quality')
            for phase, label in (('inspect', 'inspection'), ('propose', 'proposal'), ('refine', 'peer_review'))}

    def fork(self):
        child = TracedInvestigationAgent(self._agent.fork(), self._weave)
        self._children.append(child)
        return child

    @property
    def trace_failures(self):
        return self._trace_failures + [failure for child in self._children for failure in child.trace_failures]

    def _call_and_record(self, function, *args):
        start = len(self.history)
        try:
            return function(*args)
        finally:
            for entry in self.history[start:]:
                for attempt in entry.get('attempts', []):
                    body = attempt.get('raw_response')
                    malformed = body is not None and not isinstance(body, dict)
                    choices = body.get('choices') if isinstance(body, dict) else None
                    malformed |= choices is not None and not isinstance(choices, list)
                    choice = choices[0] if isinstance(choices, list) and choices else None
                    malformed |= choice is not None and not isinstance(choice, dict)
                    choice = choice if isinstance(choice, dict) else {}
                    message = choice.get('message')
                    malformed |= message is not None and not isinstance(message, dict)
                    message = message if isinstance(message, dict) else {}
                    record = {'model': entry.get('model', self.model), 'role': entry.get('role'),
                              'provider': entry.get('provider', self.provider),
                              'response_envelope_synthetic': bool(body.get('synthetic')) if isinstance(body, dict) else False,
                              'attempt': attempt.get('attempt'), 'finish_reason': choice.get('finish_reason'),
                              'content': message.get('content') if isinstance(message.get('content'), str) else None,
                              'latency_ms': attempt.get('latency_ms'), 'schema_valid': attempt.get('schema_valid'),
                              'response_payload_malformed': malformed,
                              'reasoning_source': 'not returned',
                              'timing_scope': 'Recorded provider output; span measures export, not inference.'}
                    if isinstance(message.get('reasoning'), str):
                        record.update(reasoning=message['reasoning'], reasoning_source='provider-returned reasoning')
                    try:
                        self._record_response(record)
                    except Exception as error:
                        # Observability failure must not rewrite a valid recommendation or its raw evidence.
                        self._trace_failures.append({'event': 'record_agent_response', 'error_type': type(error).__name__})

    @property
    def model(self):
        return self._agent.model

    @property
    def project(self):
        return self._agent.project

    @property
    def provider(self):
        return getattr(self._agent, 'provider', 'wandb')

    @property
    def endpoint_fingerprint(self):
        return getattr(self._agent, 'endpoint_fingerprint', None)

    @property
    def history(self):
        return self._agent.history

    def request(self, role, evidence, instruction):
        swarm_key = (evidence.get('investigator_id'), evidence.get('swarm_phase'))
        if swarm_key in self._swarm_requests:
            return self._swarm_requests[swarm_key](role, evidence, instruction)
        specialist = evidence.get('specialist_role')
        if role == 'arbiter' and 'fit_plan' in evidence and specialist == 'quantization':
            name = 'fit_quantization_advisor'
        elif role == 'proposal':
            name = f'{specialist}_specialist' if specialist in {'quantization', 'batching'} else 'search_specialist'
        else:
            name = {'arbiter': 'arbiter', 'frontier': 'frontier_reviewer'}.get(role, 'agent_request')
        return self._requests[name](role, evidence, instruction)

    def review(self, evidence):
        return self._review(evidence)


def weave_event_sink(weave):
    """Trace saved records, not inference calls; do not include runtime objects."""
    def operation(name):
        def record(payload):
            return payload
        return weave.op(name=name)(record)

    operations = {name: operation(name) for name in RECORDED_OPS}

    def sink(event_name, payload):
        operations[event_name](payload)

    return sink


def traced_evidence_reader(weave, reader):
    """Trace only query evidence and the bounded result, never the client object."""
    def operation(query_id):
        def read(evidence):
            return reader(query_id, evidence)
        return weave.op(name=f'weave_inspect_{query_id}')(read)

    operations = {query_id: operation(query_id) for query_id in QUERY_IDS}

    def inspect(query_id, evidence):
        return operations[query_id](evidence)

    return inspect


def trial_trace_failures(report):
    trials = [report.get('baseline'), report.get('candidate_trial'),
              (report.get('deployment') or {}).get('candidate_trial'), *report.get('search_trials', [])]
    failures = []
    for trial in trials:
        for field in ('trace_export', 'diagnosis_trace_export'):
            exported = (trial or {}).get(field) or {}
            if exported.get('status') == 'failed':
                failures.append({'trial_id': trial.get('trial_id'), 'event': exported.get('failed_event'),
                                 'error_type': exported.get('error_type'), 'emitted_events': exported.get('emitted_events')})
    return failures
