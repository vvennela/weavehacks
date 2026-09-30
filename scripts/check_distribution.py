"""Check that release archives contain only the installable product."""

import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def check_distribution(path):
    path = Path(path)
    if path.suffix == '.whl':
        with zipfile.ZipFile(path) as archive:
            names = {name for name in archive.namelist() if not name.endswith('/')}
        allowed = {'sera', 'sera_loop'}
        allowed.update(PurePosixPath(name).parts[0] for name in names
                       if PurePosixPath(name).parts[0].endswith('.dist-info'))
        required = {'sera/__init__.py', 'sera_loop/__init__.py',
                    'sera/replay.html', 'sera/demo_cases.json'}
        metadata = [name for name in names if name.endswith('.dist-info/entry_points.txt')]
        if len(metadata) != 1:
            raise ValueError('Wheel must contain its console entry points')
        with zipfile.ZipFile(path) as archive:
            entries = archive.read(metadata[0]).decode()
        if 'sera = sera.__main__:main' not in entries:
            raise ValueError('Wheel is missing the sera command')
    elif path.name.endswith('.tar.gz'):
        with tarfile.open(path) as archive:
            names = {str(PurePosixPath(member.name).relative_to(
                PurePosixPath(member.name).parts[0])) for member in archive if member.isfile()}
        allowed = {'sera', 'src', 'pyproject.toml', 'README.md', 'LICENSE', 'NOTICE', 'PKG-INFO', '.gitignore'}
        required = {'sera/__init__.py', 'src/sera_loop/__init__.py',
                    'sera/replay.html', 'sera/demo_cases.json', 'pyproject.toml', 'LICENSE', 'NOTICE'}
    else:
        raise ValueError(f'Unsupported distribution: {path.name}')
    unexpected = sorted(name for name in names if PurePosixPath(name).parts[0] not in allowed
                        or any(part == '__pycache__' or part.startswith('.env')
                               or part.endswith(('.pyc', '.key', '.pem'))
                               for part in PurePosixPath(name).parts)
                        or (name.startswith('src/') and not name.startswith('src/sera_loop/')))
    if unexpected:
        raise ValueError(f'Non-product files in {path.name}: {unexpected}')
    if required - names:
        raise ValueError(f'Missing runtime files in {path.name}: {sorted(required - names)}')
    print(f'{path.name}: {len(names)} product files verified')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python scripts/check_distribution.py dist/*')
    for argument in sys.argv[1:]:
        check_distribution(argument)
