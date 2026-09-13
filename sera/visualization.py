"""Small, offline replays of saved optimization evidence.

Only display fields are copied. Creating a replay never runs a model, closes a
runner, contacts a provider, starts a server, or opens a browser.
"""

import html
import json
import math
import os
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlsplit


_MAX_HTML_BYTES = 1_000_000
_METRICS = ('p95_latency_ms', 'output_tokens_per_second', 'sampled_peak_memory_mib')
_LIMITS = ('p95_latency_ms', 'max_memory_mib', 'min_output_tokens_per_second', 'quality_floor')
_CONFIG = ('enable_prefix_caching', 'enforce_eager', 'kv_cache_dtype', 'max_num_seqs',
           'max_num_batched_tokens', 'gpu_memory_utilization', 'max_model_len',
           'enable_chunked_prefill', 'tensor_parallel_size', 'dtype', 'quantization')


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _rows(value):
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError('Replay records must be lists of objects')
    return value


def _scalar(value):
    if isinstance(value, str):
        return value if len(value) <= 2400 else value[:2400] + ' … [text shortened]'
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    return None


def _number(value):
    return _scalar(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _pick(value, keys):
    source = _mapping(value)
    return {key: _scalar(source.get(key)) for key in keys}


def _link(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme == 'https' and parsed.hostname and not parsed.username
                and not parsed.password and not any(ord(char) < 33 for char in value)):
            return value
    except ValueError:
        pass
    return None


def _proposal(value):
    return _pick(value, ('action', 'proposal_id', 'parent_trial_id', 'changed_lever',
                         'proposed_value', 'reason'))


def _trial(value):
    reduced = _mapping(value.get('reduced'))
    runtime = _mapping(value.get('runtime'))
    metrics = {key: _number(reduced.get(key)) for key in _METRICS}
    metrics['sampled_peak_memory_mib'] = _number(runtime.get('sampled_peak_memory_mib'))
    return dict(trial_id=_scalar(value.get('trial_id')), status=_scalar(value.get('status')),
                metrics=metrics, quality=_pick(value.get('task_quality'),
                    ('passed', 'mean', 'floor', 'valid_outputs')),
                generation_errors=_number(reduced.get('generation_errors')),
                configuration=_pick(runtime.get('configuration'), _CONFIG),
                decision=_pick(value.get('decision'), ('selected', 'outcome', 'reason')))


def _round(value):
    agents = []
    for check in _rows(value.get('specialists')):
        agents.append(dict(name=_scalar(check.get('investigator_id') or check.get('role')),
            status=_scalar(check.get('status')), error=_scalar(check.get('error')),
            proposal_id=_scalar(check.get('arbiter_proposal_id')),
            initial=_proposal(check.get('initial_proposal')),
            final=_proposal(check.get('proposal'))))
    arbiter = _mapping(value.get('arbiter'))
    ranked = arbiter.get('ranked_proposal_ids', [])
    trial_ids = value.get('trial_ids', [])
    if not isinstance(ranked, list) or not isinstance(trial_ids, list):
        raise ValueError('Replay trial and proposal IDs must be lists')
    return dict(number=_scalar(value.get('round')), agents=agents,
        trial_ids=[_scalar(item) for item in trial_ids],
        arbiter={'ranked_proposal_ids': [_scalar(item) for item in ranked],
                 'reason': _scalar(arbiter.get('reason')), 'error': _scalar(value.get('arbiter_error'))},
        confirmation=value.get('confirmation_round') is True)


def _summary(report, name=None, limits=None, record_status='loaded'):
    if not isinstance(report, dict):
        raise ValueError('A replay report must be a JSON object')
    trials = []
    if isinstance(report.get('baseline'), dict):
        trials.append(_trial(report['baseline']))
    trials.extend(_trial(row) for row in _rows(report.get('search_trials')))
    if isinstance(report.get('candidate_trial'), dict):
        trials.append(_trial(report['candidate_trial']))
    search = _mapping(report.get('search'))
    rounds = [_round(row) for row in _rows(search.get('rounds'))]
    weave_reads = sum(
        inspection.get('status') == 'complete'
        and _mapping(inspection.get('result')).get('source') == 'weave'
        for row in _rows(search.get('rounds'))
        for investigator in _rows(_mapping(row.get('swarm')).get('investigators'))
        for inspection in _rows(investigator.get('inspections'))
    )
    if not rounds and isinstance(report.get('proposal'), dict):
        rounds = [_round({'round': 1, 'specialists': [{'role': 'agent',
            'proposal': report['proposal'], 'status': report.get('proposal_validation')}],
            'trial_ids': [row['trial_id'] for row in trials[1:]]})]
    return dict(name=name, record_status=record_status, model=_scalar(report.get('model_id')),
        status=_scalar(report.get('status')), objective=_scalar(_mapping(report.get('objective')).get('priority')),
        constraints=_pick(limits if limits is not None else report.get('constraints'), _LIMITS),
        trials=trials, rounds=rounds, stop_reason=_scalar(search.get('stop_reason')),
        decision=_pick(report.get('decision'), ('selected', 'outcome', 'reason')),
        rejected=[_pick(row, ('reason', 'status')) for row in _rows(report.get('rejected'))],
        returned_runner_closed=report.get('returned_runner_closed')
            if isinstance(report.get('returned_runner_closed'), bool) else None,
        cleanup_error=_scalar(report.get('cleanup_error')),
        returned_runtimes=[_pick(row, ('status', 'cleanup_pass', 'memory_after_mib'))
                           for row in _rows(report.get('returned_runtimes'))],
        task_quality_verified=_scalar(report.get('task_quality_verified')),
        weave_url=_link(report.get('weave_url')), weave_reads=weave_reads)


def _read(path):
    if path.stat().st_size > 128_000_000:
        raise ValueError('Replay source exceeds 128 MB')
    with path.open(encoding='utf-8') as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError('A replay report must be a JSON object')
    return value


def _stage_path(row, root):
    value = row.get('result_path') or row.get('output_dir')
    if value is None:
        return None
    if root is None or not isinstance(value, str) or '://' in value:
        raise ValueError('A stage path must stay inside the result folder')
    supplied = Path(value)
    path = (supplied if supplied.is_absolute() else root / supplied).resolve()
    if not path.is_relative_to(root):
        raise ValueError('A stage path must stay inside the result folder')
    path = path if row.get('result_path') else path / 'result.json'
    if not path.resolve().is_relative_to(root):
        raise ValueError('A stage path must stay inside the result folder')
    return path


@dataclass(frozen=True)
class Replay:
    """An immutable HTML snapshot, displayable in Jupyter and marimo.

    ``save(path)`` writes the standalone page and returns its resolved Path.
    """

    html: str

    def save(self, path):
        destination = Path(path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.html, encoding='utf-8')
        return destination

    def _repr_html_(self):
        return ('<iframe title="Sera recorded optimization replay" '
                'sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox" '
                'style="width:100%;height:600px;border:0;border-radius:12px" '
                f'srcdoc="{html.escape(self.html, quote=True)}"></iframe>')

    def _display_(self):
        import marimo as mo
        return mo.Html(self._repr_html_())


def visualize(result, output_path=None, speed=8):
    """Replay an optimize result or a local result.json, without running it.

    Accepts single and ordered-stage results. Child stage records must be inside
    the result's output folder. Missing measurements are shown as unknown.
    ``speed`` scales schematic playback (it is not measured execution time).
    Returns a :class:`Replay`; optionally saves it to ``output_path``.
    """
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed <= 0:
        raise ValueError('speed must be a finite positive number')
    if isinstance(result, (str, os.PathLike)):
        source = Path(result).expanduser().resolve()
        report, root = _read(source), source.parent
    elif hasattr(result, 'report'):
        report = result.report
        folder = getattr(result, 'output_dir', None)
        root = Path(folder).expanduser().resolve() if folder is not None else None
    else:
        raise TypeError('Supply an optimize result or a local result.json path')
    if not isinstance(report, dict):
        raise ValueError('A replay report must be a JSON object')
    stages = []
    if 'stages' in report:
        for row in _rows(report['stages']):
            path = _stage_path(row, root)
            present = path is not None and path.is_file()
            stage = _summary(_read(path) if present else row, name=_scalar(row.get('stage')),
                             limits=row.get('constraints'), record_status='loaded' if present else 'missing')
            stages.append(stage)
    else:
        stages.append(_summary(report))
    payload = dict(speed=speed, stages=stages, k_percent=_number(report.get('k_percent')),
                   aria_review={'status': 'not-recorded'},
                   min_improvement_percent=_number(report.get('min_improvement_percent')),
                   status=_scalar(report.get('status')),
                   returned_runner_closed=report.get('returned_runner_closed')
                       if isinstance(report.get('returned_runner_closed'), bool) else None)
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
    encoded = encoded.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = files('sera').joinpath('replay.html').read_text(encoding='utf-8')
    page = template.replace('__SERA_REPLAY_DATA__', encoded)
    if len(page.encode('utf-8')) > _MAX_HTML_BYTES:
        raise ValueError('Replay summary exceeds 1 MB; use individual stage results')
    replay = Replay(page)
    if output_path is not None:
        replay.save(output_path)
    return replay
