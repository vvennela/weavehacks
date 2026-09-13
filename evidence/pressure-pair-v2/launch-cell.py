def launch_sera_pressure_checks():
    import subprocess
    import sys
    from pathlib import Path
    repository = Path('/marimo/sera-capacity-v1')
    console = Path('/marimo/sera-evidence/pressure-pair-v2-console.log')
    assert not console.exists()
    assert subprocess.run(['git', 'rev-parse', '--short=7', 'HEAD'], cwd=repository,
        capture_output=True, text=True, check=True).stdout.strip() == 'dd824e0'
    assert not subprocess.run(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'],
        capture_output=True, text=True, check=True).stdout.strip()
    with console.open('x') as stream:
        return subprocess.Popen([sys.executable, '-c', "import json\nfrom pathlib import Path\nfrom sera.pressure_pilot import PRESSURE_PROFILES, run_pressure_pilot\nfrom sera.storage import content_hash, save_json\nroot = Path('/marimo/sera-evidence/pressure-pair-v2')\nroot.mkdir(parents=True, exist_ok=False)\nprompts = json.loads(Path('/marimo/sera-evidence/pressure-v1/result.json').read_text())['source_prompts']\nregistration = {'profiles': {name: PRESSURE_PROFILES[name] for name in ['cache-v2', 'queue-v1']},\n    'source_revision': 'dd824e0', 'source_prompts_hash': content_hash(prompts),\n    'scope': 'Two predeclared diagnostic pilots, no retuning and no task-quality claim'}\nsave_json(root / 'registration.json', registration | {'registration_hash': content_hash(registration)})\nfor name in ['cache-v2', 'queue-v1']:\n    report = run_pressure_pilot(prompts=prompts, output_dir=root / name, profile_name=name)\n    print(name, {key: report.get(key) for key in ['status', 'scenario', 'peak_kv_percent',\n        'measured_preemptions', 'measured_queue_ms', 'request_errors']}, flush=True)\n    if report.get('runtime', {}).get('cleanup_pass') is not True:\n        raise RuntimeError('Pilot cleanup failed; no subsequent GPU work')\n"],
            cwd=repository, stdout=stream, stderr=subprocess.STDOUT)

sera_pressure_checks_process = launch_sera_pressure_checks()
print('Pressure pilot PID:', sera_pressure_checks_process.pid)
