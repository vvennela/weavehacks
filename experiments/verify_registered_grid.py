"""Audit a closed registered public-API swarm without rewriting its evidence."""

import argparse
import json
from pathlib import Path
import re

from benchmarks.live_comparison import _audit_import
from experiments.verify_swarm import Audit, _verify_swarm
from sera.storage import content_hash


class RegisteredGridAudit(Audit):
    root_op = 'sera_optimize'

    def __init__(self, report, dump, registration):
        super().__init__(report, dump)
        self.registration = registration

    def valid_plateau_launch(self, launch):
        command = launch.get('command') if isinstance(launch, dict) else None
        return (isinstance(command, list) and len(command) == 8
                and all(isinstance(part, str) and part for part in command)
                and command[1:5] == ['-m', 'benchmarks.live_comparison', 'run-live', '--registration']
                and command[6] == '--output-dir'
                and launch.get('registration_hash') == self.registration['registration_hash']
                and 'max_candidate_trials' in launch and launch['max_candidate_trials'] is None
                and self.registration['live_search']['max_candidate_trials'] is None
                and re.fullmatch('[0-9a-f]{40}', str(launch.get('source_revision', ''))) is not None)

    def returned(self):
        # _audit_import has independently regraded and bound the separate probe to
        # the selected runtime. This driver does not emit a post-return-probe span.
        # Keep the same strict zero-memory cleanup check as the historical verifier.
        self.returned_cleanup()


def verify_registered_grid(folder, calls_path=None):
    folder = Path(folder)
    registration, report, _, _, _, _ = _audit_import(folder)
    calls_path = Path(calls_path) if calls_path else folder / 'live/weave-calls-normalized.json'
    calls = json.loads(calls_path.read_text())
    launch = json.loads((folder / 'actual-launch.json').read_text())
    probe = json.loads((folder / 'runner-probe.json').read_text())
    audit = RegisteredGridAudit(report, calls, registration)
    audit.require(audit.valid_plateau_launch(launch), 'registered-launch',
                  'The exact registered uncapped driver and launch binding are required.')
    result = _verify_swarm(audit, report, calls, launch)
    result['source_hashes'].update(registration=content_hash(registration), runner_probe=content_hash(probe))
    result['registered_live_grid'] = {
        'registration_hash': registration['registration_hash'],
        'source_revision': launch.get('source_revision'),
        'probe_scope': 'separate-source-regraded-by-live-import',
        'strict_section_19_4_claim': False,
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--calls', type=Path)
    args = parser.parse_args(argv)
    result = verify_registered_grid(args.run_dir, args.calls)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['execution_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
