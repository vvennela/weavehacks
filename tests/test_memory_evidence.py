"""Incomplete sampling must not teach agents or users that memory was saved."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from sera import RuntimeConfig, visualize
from sera.fit import fit_review_evidence
from sera.investigation import round_evidence
from sera.investigation_report import _trial_lines
from sera.pipeline import agent_evidence, render_summary


@pytest.mark.parametrize('errors', [None, 1, 0])
@pytest.mark.parametrize('surface', ['agent', 'history', 'fit', 'summary', 'report', 'replay'])
def test_memory_evidence_uses_verified_sampling(surface, errors):
    runtime = {'configuration': RuntimeConfig().model_dump(), 'sampled_peak_memory_mib': 1234}
    if errors is not None:
        runtime['telemetry_errors'] = errors
    trial = {'trial_id': 'baseline', 'status': 'collected', 'runtime': runtime,
             'reduced': {}, 'quality': [], 'self_check': []}
    expected = 1234 if errors == 0 else None
    if surface == 'agent':
        actual = agent_evidence(trial)['metrics']['sampled_peak_memory_mib']
    elif surface == 'history':
        actual = round_evidence({'metrics': {}}, {'rounds': []}, [trial], 1)[
            'metrics']['trial_1_sampled_peak_memory_mib']
    elif surface == 'fit':
        actual = fit_review_evidence({}, trial, {'selected': None})['candidate_peak_memory_mib']
    elif surface in ('summary', 'report'):
        rendered = (render_summary({'status': 'ready', 'baseline': trial}, Path('.'))
                    if surface == 'summary' else '\n'.join(_trial_lines(trial)))
        assert ('1234' in rendered) == (expected is not None)
        return
    else:
        replay = visualize(SimpleNamespace(report={'status': 'ready', 'baseline': trial}))
        payload = json.loads(re.search(
            r'<script id="replay-data" type="application/json">(.*?)</script>', replay.html, re.S).group(1))
        actual = payload['stages'][0]['trials'][0]['metrics']['sampled_peak_memory_mib']
    assert actual == expected
    assert trial['runtime']['sampled_peak_memory_mib'] == 1234
