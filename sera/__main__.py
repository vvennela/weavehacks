"""Sera's first-run setup and local workload commands."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path


def main():
    from . import onboarding
    parser = argparse.ArgumentParser(description='Sera — the autonomous auto-research harness for inference')
    commands = parser.add_subparsers(dest='command')
    setup = commands.add_parser('setup', help='Install the runtime, sign in and register workloads')
    setup.add_argument('--operator-config', type=Path)
    setup.add_argument('--no-start', action='store_true')
    setup.add_argument('--skip-install', action='store_true', help='Use an already installed hardware runtime')
    for name in ('start', 'stop', 'status'):
        commands.add_parser(name)
    serve = commands.add_parser('serve', help='Run the local service in the foreground')
    serve.add_argument('--home', type=Path, required=True)
    serve.add_argument('--instance', required=True)
    optimize = commands.add_parser('optimize', help='Describe and optimize an inference workload')
    optimize.add_argument('workload')
    optimize.add_argument('--examples', type=Path)
    optimize.add_argument('--documents')
    optimize.add_argument('--request-id')
    args = parser.parse_args()
    try:
        home = onboarding.home_path()
        if args.command in (None, 'setup'):
            onboarding.setup(operator_config=getattr(args, 'operator_config', None),
                             start=not getattr(args, 'no_start', False),
                             install=not getattr(args, 'skip_install', False))
        elif args.command == 'serve':
            onboarding.serve_local(args.home)
        elif args.command == 'start':
            onboarding.start_local(home)
        elif args.command == 'stop':
            onboarding.stop_local(home)
            print('Sera stopped.')
        elif args.command == 'status':
            print('ready' if onboarding._ready(home) else 'not running')
        elif args.command == 'optimize':
            from .managed_client import Optimize, SeraNeedsInput, SeraRequirementsNotMet
            from .workload_intake import read_examples
            examples = read_examples(args.examples) if args.examples else None
            try:
                result = Optimize(args.workload, examples=examples, documents=args.documents,
                                  request_id=args.request_id)
                print(json.dumps(asdict(result), indent=2))
            except SeraRequirementsNotMet as error:
                print(json.dumps({'status': 'requirements-not-met', 'result': asdict(error.result)}, indent=2))
                parser.exit(2)
            except SeraNeedsInput as error:
                print(json.dumps({'status': 'needs-input', 'questions': error.questions}, indent=2))
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
