def launch_sera_live_grid_comparison():
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    from datetime import datetime, timezone

    repository = Path('/marimo/sera-grid-comparison-v1')
    registration = Path('/marimo/sera-evidence/grid-comparison-registration-v1.json')
    folder = Path('/marimo/sera-evidence/live-grid-comparison-v1')
    console = folder.with_name(folder.name + '-console.log')
    launch = folder.with_name(folder.name + '-launch.json')
    assert not folder.exists() and not console.exists() and not launch.exists()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repository,
                              capture_output=True, text=True, check=True).stdout.strip()
    assert revision == '6601669e47879b0492cab09130123a363ae8b91a'
    registered = json.loads(registration.read_text())
    assert registered['registration_hash'] == '2843eee593b706529bd178369ef91a529900ee6cb8412ce27ffa553e019c1eb5'
    assert not subprocess.run(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'],
                              capture_output=True, text=True, check=True).stdout.strip()
    environment = dict(os.environ, SERA_AGENT_PROVIDER='codex-relay',
        SERA_AGENT_MODEL='gpt-5.6-luna', SERA_PROJECT='vvennela-n-a/wandb_agent_default_project',
        SERA_RELAY_DIR='/tmp/sera-relay-grid-comparison-v1',
        SERA_PROVIDER_CHECK='/marimo/sera-evidence/provider-luna-expanded-v1/result.json')
    assert environment.get('WANDB_API_KEY')
    command = [sys.executable, '-m', 'benchmarks.live_comparison', 'run-live',
               '--registration', str(registration), '--output-dir', str(folder)]
    launch.write_text(json.dumps({'source_revision': revision, 'command': command,
        'cwd': str(repository), 'registration_hash': registered['registration_hash'],
        'started_at': datetime.now(timezone.utc).isoformat(), 'agent_model': 'gpt-5.6-luna',
        'scope': 'Exploratory live swarm versus frozen full grid; not full section19 certification.',
        'max_candidate_trials': None}, indent=2))
    with console.open('x') as stream:
        return subprocess.Popen(command, cwd=repository, env=environment,
                                stdout=stream, stderr=subprocess.STDOUT)

sera_live_grid_process = launch_sera_live_grid_comparison()
print('Live grid comparison PID:', sera_live_grid_process.pid)
