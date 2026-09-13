"""Read-only git comparison; save retrospective source identity, not launch proof."""

import hashlib
from pathlib import Path
import subprocess

from sera.storage import save_json


REVISIONS = {
    'installed_package_source': 'd8c73042c820eddc2f90945a4cdf1f0061ab0c89',
    'live_driver_checkout': '6601669e47879b0492cab09130123a363ae8b91a',
}


def git(*args):
    return subprocess.check_output(['git', *args])


def source_tree(revision):
    paths = git('ls-tree', '-r', '--name-only', revision, '--', 'sera').decode().splitlines()
    return {path: hashlib.sha256(git('show', f'{revision}:{path}')).hexdigest() for path in paths}


def audit():
    sources = {name: source_tree(revision) for name, revision in REVISIONS.items()}
    package, checkout = sources.values()
    return {
        'schema_version': 'sera-retrospective-source-comparison-v1',
        'revisions': REVISIONS,
        'source_trees': sources,
        'sera_trees_byte_identical': package == checkout,
        'file_count': len(package),
        'different_files': [path for path in sorted(package.keys() | checkout.keys())
                            if package.get(path) != checkout.get(path)],
        'driver': {'path': 'benchmarks/live_comparison.py',
                   'revision': REVISIONS['live_driver_checkout'],
                   'sha256': hashlib.sha256(git('show',
                       f"{REVISIONS['live_driver_checkout']}:benchmarks/live_comparison.py")).hexdigest()},
        'scope': 'Retrospective comparison of immutable git source, not a launch-time import-path record.',
        'limitations': [
            'The live launch did not record Python module __file__ paths.',
            'Later inspection found PYTHONSAFEPATH=1 and site-packages before the checkout.',
            'The likely installed-library import path is an inference, not a recorded launch fact.',
            'This audit compares git source trees; it does not attest wheel bytes or the running process.',
        ],
    }


if __name__ == '__main__':
    result = audit()
    save_json(Path(__file__).with_name('source-comparison.json'), result)
    print({'sera_trees_byte_identical': result['sera_trees_byte_identical'],
           'file_count': result['file_count'], 'different_files': result['different_files']})
