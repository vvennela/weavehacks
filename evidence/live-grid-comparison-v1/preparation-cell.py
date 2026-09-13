def prepare_sera_grid_checkout():
    import subprocess
    from pathlib import Path

    source = Path('/marimo/sera-core-loop-17eacc9')
    destination = Path('/marimo/sera-grid-comparison-v1')
    if destination.exists():
        raise RuntimeError('Comparison checkout already exists; inspect it before reuse')
    subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(['git', 'worktree', 'add', '--detach', str(destination), 'origin/main'],
                   cwd=source, check=True, capture_output=True, text=True)
    return {'path': str(destination), 'revision': subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=destination, check=True, capture_output=True, text=True).stdout.strip()}

sera_grid_checkout = prepare_sera_grid_checkout()
print(sera_grid_checkout)
