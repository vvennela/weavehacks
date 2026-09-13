"""Build and validate a wheel in fresh environments; print the audit as JSON."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--expected-source', required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    temporary = Path(tempfile.mkdtemp(prefix='sera-final-package-'))
    records = []

    def run(arguments, *, cwd=temporary, isolated=False):
        completed = subprocess.run([str(value) for value in arguments], cwd=cwd,
                                   text=True, capture_output=True, timeout=180)
        records.append(dict(command=[str(value) for value in arguments], cwd=str(cwd),
                            exit_code=completed.returncode, stdout=completed.stdout,
                            stderr=completed.stderr, isolated_python=isolated))
        if completed.returncode:
            raise RuntimeError(f'Check failed: {arguments[0]} (exit {completed.returncode})')
        return completed.stdout.strip()

    expected = run(['git', 'rev-parse', args.expected_source], cwd=source)
    checkout = run(['git', 'rev-parse', 'HEAD'], cwd=source)
    expected_tree = run(['git', 'rev-parse', f'{expected}^{{tree}}'], cwd=source)
    checkout_tree = run(['git', 'rev-parse', 'HEAD^{tree}'], cwd=source)
    assert expected_tree == checkout_tree, 'Checkout differs from the release source tree'
    run(['git', 'diff', '--exit-code', expected, '--', 'sera', 'src/sera_loop', 'pyproject.toml'], cwd=source)
    run(['uv', 'build', '--wheel', '--out-dir', temporary / 'dist'], cwd=source)
    wheel, = (temporary / 'dist').glob('*.whl')
    source_files = []
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.startswith(('sera/', 'sera_loop/')) and name.endswith('.py'):
                original = source / name if name.startswith('sera/') else source / 'src' / name
                assert archive.read(name) == original.read_bytes(), f'Wheel source mismatch: {name}'
                source_files.append(name)
        assert not any(name.startswith(('experiments/', 'benchmarks/', 'tests/')) for name in archive.namelist())
    for environment in ('base', 'swarm'):
        prefix = temporary / environment
        python = prefix / 'bin' / 'python'
        run(['uv', 'venv', '--python', '3.11', prefix])
        package = str(wheel) + ('[swarm]' if environment == 'swarm' else '')
        run(['uv', 'pip', 'install', '--python', python, package])
        run(['uv', 'pip', 'check', '--python', python])
        run([python, '-I', Path(__file__).resolve().parent / 'installed_features_smoke.py'], isolated=True)
        if environment == 'base':
            run([python, '-I', '-c',
                "import importlib.util; names=('weave','openai','vllm','torch','experiments','benchmarks'); "
                "assert all(importlib.util.find_spec(name) is None for name in names); "
                "print('PASS: base import requires no Weave, provider, GPU, or repository modules')"], isolated=True)
        else:
            run([python, '-I', source / 'tests/installed_package_smoke.py'], isolated=True)
            run([prefix / 'bin' / 'sera-provider-check', '--help'])
        run(['uv', 'pip', 'list', '--python', python, '--format', 'json'])
    report = dict(schema_version='sera-final-package-release-v1', status='passed',
        source_sha=expected, checkout_sha=checkout, source_tree=expected_tree,
        source_tree_equal=True, platform=platform.platform(), temporary_directory=str(temporary),
        wheel=str(wheel), wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
        wheel_size_bytes=wheel.stat().st_size, verified_python_source_files=source_files,
        checks=records, limits=['No GPU runtime installed or started.', 'No provider or Weave service calls.',
            'Installed API smoke stubs service and GPU boundaries.',
            'Dependency checks cover Python 3.11 on this macOS host, not Linux CUDA compatibility.',
            'This is package validation, not a live release rehearsal or production certification.'])
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
