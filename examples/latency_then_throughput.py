"""Optimize latency, then throughput, retaining the earlier latency limit."""

import os
from getpass import getpass

import sera
from sera.demo import prepare_demo


def main():
    # Add your keys here: hidden runtime prompts, never keys saved in source.
    for name in ('OPENAI_API_KEY', 'WANDB_API_KEY'):
        if not os.environ.get(name):
            os.environ[name] = getpass(f'Add your {name} here: ')
    project = os.environ.get('SERA_PROJECT') or input('Your Weave project (entity/project): ')
    config = prepare_demo(project=project)

    with sera.optimize(
        **config,
        stages=['latency', 'throughput'],
        k=3.0,  # Throughput may improve while p95 latency becomes at most 3% worse.
        min_improvement_pct=5.0,
    ) as y:
        y.print_summary()
        if y.models:
            print(y.models[0].generate(config['prompts'][0]).text)

    replay = sera.visualize(y)
    print(replay.save(y.output_dir / 'demo.html'))


if __name__ == '__main__':
    main()
