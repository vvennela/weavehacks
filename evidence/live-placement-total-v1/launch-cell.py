def launch_sera_total_device_placement():
    import subprocess
    import sys
    from pathlib import Path
    repository=Path('/marimo/sera-capacity-v1')
    console=Path('/marimo/sera-evidence/live-placement-total-v1-console.log')
    assert not console.exists()
    assert subprocess.run(['git','rev-parse','--short=7','HEAD'],cwd=repository,
        capture_output=True,text=True,check=True).stdout.strip() == '6130d9e'
    assert not subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],
        capture_output=True,text=True,check=True).stdout.strip()
    with console.open('x') as stream:
        return subprocess.Popen([sys.executable,'-c',"import sys,runpy,os,json\nfrom pathlib import Path\nsys.path.insert(0,'/marimo/sera-capacity-v1')\nimport sera\nassert sera.__file__.startswith('/marimo/sera-capacity-v1/sera/')\nos.environ.update(SERA_AGENT_PROVIDER='codex-relay',SERA_AGENT_MODEL='gpt-5.6-luna',\n    SERA_PROJECT='vvennela-n-a/wandb_agent_default_project',SERA_RELAY_DIR='/tmp/sera-relay-placement-total-v1')\nsys.argv=['experiments.run_placement','--manifest',\n    '/marimo/sera-capacity-v1/evidence/live-placement-total-v1/manifest.json',\n    '--phase','search','--objective','memory','--output-dir','/marimo/sera-evidence/live-placement-total-v1']\nprint(json.dumps(dict(source_commit='6130d9e',sera_import=sera.__file__,\n    memory_accounting='total-device',agent_model='gpt-5.6-luna')),flush=True)\nrunpy.run_module('experiments.run_placement',run_name='__main__')\n"],
            cwd=repository,stdout=stream,stderr=subprocess.STDOUT)

sera_total_device_placement_process=launch_sera_total_device_placement()
print('Total-device placement PID:',sera_total_device_placement_process.pid)
