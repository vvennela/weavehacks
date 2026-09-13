"""Explicit freeze / GPU collection / offline or provider-backed replay commands."""

import argparse
import json
from pathlib import Path

from sera.storage import content_hash, save_json

from .collection import audit_collection, collect, freeze_collection, render_table
from .search import StopSearch, run_comparison


def _read(path):
    return json.loads(Path(path).read_text())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freeze = commands.add_parser('freeze', help='No GPU or provider calls')
    freeze.add_argument('--plan', required=True)
    freeze.add_argument('--output-file', required=True)
    collection = commands.add_parser('collect', help='Launch the frozen GPU trials')
    collection.add_argument('--bundle', required=True)
    collection.add_argument('--output-dir', required=True)
    replay = commands.add_parser('replay', help='Audit saved sources; never launch GPU trials')
    replay.add_argument('--collection', required=True)
    replay.add_argument('--output-dir', required=True)
    replay.add_argument('--live-run', action='store_true',
                        help='Audit the closed live loop and include its recorded choices')
    replay.add_argument('--agent-provider', choices=['wandb', 'codex-relay'])
    replay.add_argument('--agent-model')
    replay.add_argument('--project')
    replay.add_argument('--provider-check')
    replay.add_argument('--relay-dir')
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        bundle = freeze_collection(_read(args.plan))
        # Exclusive creation: freeze never overwrites an earlier manifest.
        with Path(args.output_file).open('x') as stream:
            json.dump(bundle, stream, indent=2, allow_nan=False)
        print(f"Frozen {len(bundle['manifest']['candidates'])} candidates; no trials run.")
        return 0
    if args.command == 'collect':
        summary = collect(_read(args.bundle), args.output_dir)
        (Path(args.output_dir) / 'measurements.md').write_text(render_table(summary))
        print(f"Collection: {summary['stop_reason']}; complete={summary['complete']}")
        return 0 if summary['complete'] and summary['stop_reason'] == 'universe-collected' else 1
    if args.agent_provider:
        if not all((args.agent_model, args.project, args.provider_check)):
            parser.error('Agent replay needs --agent-model, --project, and --provider-check')
        if (args.agent_provider == 'codex-relay') != bool(args.relay_dir):
            parser.error('--relay-dir is required only for codex-relay')
    elif any((args.agent_model, args.project, args.provider_check, args.relay_dir)):
        parser.error('Provider settings require --agent-provider')
    live_source = None
    if args.live_run:
        from .live_comparison import _audit_import
        registration, report, bundle, artifacts, summary, imported = _audit_import(Path(args.collection))
        live_source = {'registration_hash': registration['registration_hash'],
                       'live_result_hash': content_hash(report),
                       'selected_candidate_ids': imported['selected_candidate_ids'],
                       'weave_url': report.get('weave_url'),
                       'limitations': registration['limitations']}
    else:
        bundle, artifacts, summary = audit_collection(args.collection)
    if not summary['complete']:
        raise ValueError('Incomplete universe or invalid baseline: no oracle/replay comparison')
    policies = {}
    if live_source is not None:
        choices = iter(live_source['selected_candidate_ids'])

        def recorded_choice(view):
            try:
                return next(choices)
            except StopIteration:
                raise StopSearch() from None

        policies['recorded-live-sera'] = recorded_choice
    if args.agent_provider:
        from sera.agent import WandbAgent
        from sera.relay import RelayAgent
        from .search_policies import FrozenSwarmPolicy
        for variant in ('full-evidence', 'no-history', 'round-robin'):
            if args.agent_provider == 'codex-relay':
                client = RelayAgent(project=args.project, model=args.agent_model, relay_dir=args.relay_dir)
            else:
                client = WandbAgent(project=args.project, model=args.agent_model)
            policies[variant] = FrozenSwarmPolicy(bundle['manifest'], client,
                                                  provider_check=args.provider_check, variant=variant)
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=False)
    save_json(folder / 'summary.json', summary)
    (folder / 'measurements.md').write_text(render_table(summary))
    for name, policy in policies.items():
        if hasattr(policy, 'export_audit'):
            save_json(folder / f'{name}-policy.json', policy.export_audit())
    try:
        comparison = run_comparison(bundle['manifest'], artifacts, policies=policies)
        if live_source is not None:
            comparison.update(live_source=live_source, strict_section_19_4_claim=False)
        save_json(folder / 'comparison.json', comparison)
    finally:
        for name, policy in policies.items():
            if hasattr(policy, 'export_audit'):
                save_json(folder / f'{name}-policy.json', policy.export_audit())
    print('Saved grid, 20 random seeds, and requested policy replays. Search claim: not assessed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
