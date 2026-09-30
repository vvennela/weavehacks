"""Build the public archives and rebuild an installable wheel from the sdist."""

import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from scripts.check_distribution import check_distribution

ROOT = Path(__file__).resolve().parents[1]


def test_release_archives_exclude_research_and_rebuild_from_source(tmp_path):
    uv = shutil.which('uv')
    if uv is None:
        pytest.skip('The release build check requires uv; CI installs it')
    project = tmp_path / 'project'
    project.mkdir()
    for name in ('pyproject.toml', 'README.md', 'LICENSE', 'NOTICE', '.gitignore'):
        shutil.copy2(ROOT / name, project / name)
    for name in ('sera', 'src/sera_loop'):
        shutil.copytree(ROOT / name, project / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('evidence/run.json', 'experiments/scratch.py', 'web/server.py',
                 'notebooks/demo.py', 'docs/notes.md', 'output/page.html',
                 'benchmarks/data.json', 'tests/fixture.py', 'deploy/worker.js',
                 'demos/replay.html', 'build/cache.json', '.local/credentials.json',
                 'sera-runs/result.json', 'sera/.env', '.env', 'operator.pem'):
        destination = project / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text('This development file must never ship.\n')
    subprocess.run([uv, 'build', '--out-dir', str(tmp_path / 'dist')],
                   cwd=project, check=True, capture_output=True, text=True, timeout=120)
    archives = sorted(path for path in (tmp_path / 'dist').iterdir()
                      if path.suffix == '.whl' or path.name.endswith('.tar.gz'))
    assert len(archives) == 2
    for path in archives:
        check_distribution(path)
    source = next(path for path in archives if path.name.endswith('.tar.gz'))
    with tarfile.open(source) as archive:
        archive.extractall(tmp_path / 'source', filter='data')
    extracted = next((tmp_path / 'source').iterdir())
    subprocess.run([uv, 'build', '--wheel', '--out-dir', str(tmp_path / 'rebuilt')],
                   cwd=extracted, check=True, capture_output=True, text=True, timeout=120)
    check_distribution(next((tmp_path / 'rebuilt').glob('*.whl')))
