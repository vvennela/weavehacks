"""Service-owned research process; credentials never enter its request file."""
import json
import sys
from pathlib import Path

from .native_optimizer import optimize_native
from .native_worker import _parent_watchdog


def main():
    _parent_watchdog()
    folder = Path(sys.argv[1])
    request = json.loads((folder / 'request.json').read_text())
    research = folder / 'research'
    optimize_native(profile=request['profile'], output_dir=research,
                    project=request['project'], resume=(research / 'ledger.sqlite3').exists())


if __name__ == '__main__':
    main()
