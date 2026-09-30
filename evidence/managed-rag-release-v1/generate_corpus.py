"""Recreate the synthetic 100,000-record RAG release corpus."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8') as stream:
        for number in range(100_000):
            team = ('Amber', 'Birch', 'Cedar', 'Delta')[number % 4]
            text = (
                f'Service svc{number:06d} has a backup retention period of {7 + number % 25} days. '
                f'The service owner is Team {team}. '
                f'Its daily backup starts at {number % 24:02d}:00 UTC.'
            )
            stream.write(json.dumps({'id': f'doc-{number:06d}', 'text': text}) + '\n')


if __name__ == '__main__':
    main()
