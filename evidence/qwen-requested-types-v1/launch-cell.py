def launch_sera_requested_type_quality():
    import subprocess
    import sys
    from pathlib import Path
    repository = Path('/marimo/sera-capacity-v1')
    console = Path('/marimo/sera-evidence/qwen-requested-types-v1-console.log')
    assert not console.exists()
    assert subprocess.run(['git', 'rev-parse', '--short=7', 'HEAD'], cwd=repository,
        capture_output=True, text=True, check=True).stdout.strip() == '3a38aa3'
    assert not subprocess.run(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'],
        capture_output=True, text=True, check=True).stdout.strip()
    with console.open('x') as stream:
        return subprocess.Popen([sys.executable, '-c', "import sys,runpy\nsys.path.insert(0, '/marimo/sera-capacity-v1')\nimport sera\nassert sera.__file__.startswith('/marimo/sera-capacity-v1/sera/')\nsys.argv = ['experiments.run_structured_quality_pilot', '--model-id', 'Qwen/Qwen3-0.6B',\n    '--requested-types', '--output-dir', '/marimo/sera-evidence/qwen-requested-types-v1']\nrunpy.run_module('experiments.run_structured_quality_pilot', run_name='__main__')\n"],
            cwd=repository, stdout=stream, stderr=subprocess.STDOUT)

sera_requested_type_quality_process = launch_sera_requested_type_quality()
print('Requested-type quality pilot PID:', sera_requested_type_quality_process.pid)
