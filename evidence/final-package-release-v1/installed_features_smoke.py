"""Offline wheel-only checks; no repository imports, GPU, or provider calls."""

from importlib.metadata import version
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import sera
import sera_loop
from sera.ledger import Ledger


def main():
    assert 'site-packages' in str(Path(sera.__file__))
    assert 'site-packages' in str(Path(sera_loop.__file__))
    exports = ('optimize', 'place', 'optimize_placement', 'measure_placement_references',
               'optimize_on_hardware', 'inspect_recovery', 'resume')
    assert all(callable(getattr(sera, name)) for name in exports)
    with TemporaryDirectory(prefix='sera-installed-ledger-') as folder:
        ledger = Ledger(folder)
        try:
            ledger.save(dict(schema_version='sera-single-model-v1', status='running',
                             model_id='fixture/model', model_revision='a' * 40))
            checkpoint = sera.inspect_recovery(folder)
            assert checkpoint['report']['status'] == 'running'
            try:
                Ledger(folder, existing=True)
            except RuntimeError as error:
                assert 'active owner' in str(error)
            else:
                raise AssertionError('A second optimizer acquired the active ledger')
        finally:
            ledger.close()
        try:
            sera.resume(output_dir=folder, expected_run_hash=checkpoint['run_hash'],
                        agent=SimpleNamespace(), provider_check='not-used', confirm_interrupted=True)
        except ValueError as error:
            assert 'committed measured baseline' in str(error)
        else:
            raise AssertionError('An unmeasured run passed the recovery gate')
    print(json.dumps(dict(status='passed', version=version('sera-inference'),
        exports=list(exports), checks=['wheel-only imports', 'SQLite checkpoint roundtrip',
            'exclusive optimizer ownership', 'pre-baseline resume fails before GPU/provider'],
        gpu_calls=0, provider_calls=0)))


if __name__ == '__main__':
    main()
