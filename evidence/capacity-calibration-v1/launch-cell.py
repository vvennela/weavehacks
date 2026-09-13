def launch_sera_capacity_calibration():
    import subprocess
    import sys
    from pathlib import Path
    repository=Path('/marimo/sera-capacity-v1')
    console=Path('/marimo/sera-evidence/capacity-calibration-v1-console.log')
    assert not console.exists()
    assert subprocess.run(['git','rev-parse','--short=7','HEAD'],cwd=repository,
        capture_output=True,text=True,check=True).stdout.strip() == '4f47448'
    assert not subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],
        capture_output=True,text=True,check=True).stdout.strip()
    with console.open('x') as stream:
        return subprocess.Popen([sys.executable,'-c',"import sys, subprocess, json, time\nfrom pathlib import Path\nsys.path.insert(0, '/marimo/sera-capacity-v1')\nimport sera\nassert sera.__file__.startswith('/marimo/sera-capacity-v1/sera/')\nfrom experiments.run_placement import load_manifest, run_references\nfolder=Path('/marimo/sera-evidence/capacity-calibration-v1')\nfolder.mkdir(exist_ok=False)\nstarted=time.monotonic()\ndownload=subprocess.run(['hf','download','zai-org/glm-4-9b-chat-hf','--revision','8599336fc6c125203efb2360bfaf4c80eef1d1bf','--max-workers','4'])\n(folder/'preparation.json').write_text(json.dumps(dict(model_id='zai-org/glm-4-9b-chat-hf',revision='8599336fc6c125203efb2360bfaf4c80eef1d1bf',exit_code=download.returncode,elapsed_seconds=time.monotonic()-started,source_commit='4f47448',sera_import=sera.__file__),indent=2))\ndownload.check_returncode()\nloaded=load_manifest('/marimo/sera-capacity-v1/evidence/capacity-calibration-v1/manifest.json')\nreport=run_references(loaded,folder/'references')\nprint(json.dumps(dict(status=report['status'],passing_references=report['passing_references'],rejected=report['rejected'])),flush=True)\n"],
            cwd=repository,stdout=stream,stderr=subprocess.STDOUT)

sera_capacity_calibration_process=launch_sera_capacity_calibration()
print('Approved capacity calibration PID:',sera_capacity_calibration_process.pid)
