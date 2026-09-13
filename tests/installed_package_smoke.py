"""Wheel-only setup smoke. All service/GPU boundaries are explicitly stubbed.

Run with the isolated install's Python using -I. This does not certify a provider,
measure latency, query Weave, or start a model. It checks the documented API wiring.
"""

from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import sera
import weave
from sera import pipeline
from sera.tracing import event_sink_enabled


def main():
    assert version('sera-inference') == '0.2.0'
    assert 'site-packages' in str(Path(sera.__file__))
    events = []

    class Result:
        def __init__(self):
            self.report = {'status': 'ready'}
            self.models = [SimpleNamespace(generate=lambda prompt: SimpleNamespace(text='fixture answer'))]

        def _save(self):
            events.append('save')

        def close(self):
            events.append('close')

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

    def run(**options):
        assert options['swarm'] and options['automatic_space']
        assert options['budget'].max_candidate_trials is None
        assert options['workload'].concurrency == [1, 2, 4, 8]
        assert options['agent'].provider == 'codex-relay'
        assert event_sink_enabled() and callable(options['trace_reader'])
        return Result()

    with TemporaryDirectory(prefix='sera-install-smoke-') as folder:
        environment = dict(SERA_AGENT_PROVIDER='codex-relay', SERA_AGENT_MODEL='gpt-5.6-luna',
                           SERA_PROJECT='fixture/project', SERA_PROVIDER_CHECK='fixture-only',
                           SERA_RELAY_DIR=folder, WANDB_API_KEY='fixture-not-a-real-key')
        with patch.dict('os.environ', environment, clear=True), \
             patch('sera.provider_check.require_provider_check', return_value={}), \
             patch.object(pipeline, 'optimize', side_effect=run), \
             patch.object(weave, 'init', return_value=SimpleNamespace(flush=lambda: events.append('flush'))), \
             patch.object(weave, 'op', side_effect=lambda fn=None, **kw: fn or (lambda actual: actual)), \
             patch.object(weave, 'get_current_call', return_value=SimpleNamespace(
                 trace_id='fixture-trace', ui_url='fixture-url')):
            with sera.optimize(models=['Qwen/Qwen3-0.6B'], prompts=['What is 1 + 1?']) as result:
                assert result.models[0].generate('question').text == 'fixture answer'
                assert result.report['weave_url'] == 'fixture-url'
        assert events == ['save', 'flush', 'close']
        assert not event_sink_enabled()
    print('PASS: installed 0.2.0 API setup, scoped tracing hooks, usable-result ownership; all service boundaries stubbed')


if __name__ == '__main__':
    main()
