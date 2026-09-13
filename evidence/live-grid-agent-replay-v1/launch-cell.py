def launch_sera_grid_policy_replay():
    import os
    import subprocess
    import sys
    from pathlib import Path
    repository = Path('/marimo/sera-grid-comparison-v1')
    output = Path('/marimo/sera-evidence/live-grid-agent-replay-v1')
    console = output.with_name(output.name + '-console.log')
    assert not output.exists() and not console.exists()
    assert subprocess.run(['git', 'rev-parse', '--short=7', 'HEAD'], cwd=repository,
        capture_output=True, text=True, check=True).stdout.strip() == '3a9cb31'
    command = [sys.executable, '-m', 'benchmarks.run_search', 'replay',
        '--collection', '/marimo/sera-evidence/live-grid-comparison-v1',
        '--output-dir', str(output), '--live-run', '--agent-provider', 'codex-relay',
        '--agent-model', 'gpt-5.6-luna', '--project', 'vvennela-n-a/wandb_agent_default_project',
        '--provider-check', '/marimo/sera-evidence/provider-luna-expanded-v1/result.json',
        '--relay-dir', '/tmp/sera-relay-grid-comparison-v1']
    with console.open('x') as stream:
        return subprocess.Popen(command, cwd=repository, env=dict(os.environ),
                                stdout=stream, stderr=subprocess.STDOUT)

sera_grid_policy_replay_process = launch_sera_grid_policy_replay()
print('CPU-only policy replay PID:', sera_grid_policy_replay_process.pid)
