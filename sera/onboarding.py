"""Guided local installation and private operator configuration."""
import fcntl
import getpass
import hashlib
import importlib.metadata
import json
import os
import platform
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import time
import venv
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .native_optimizer import validate_native_profile

DEFAULT_MODEL = 'Qwen/Qwen3-0.6B'
DEFAULT_REVISION = 'c1899de289a04d12100db370d81485cdf75e47ca'


def home_path():
    return Path(os.environ.get('SERA_HOME', Path.home() / '.local/share/sera')).expanduser().resolve()


def private_json(path, value):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refusing to write credentials through a symlink')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temporary = path.with_name(path.name + '.' + secrets.token_hex(8))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def detect_backend():
    if platform.system() == 'Darwin' and platform.machine() == 'arm64':
        return 'mlx', None
    if platform.system() == 'Linux' and shutil.which('nvidia-smi'):
        from .hardware import discover_gpus
        devices = discover_gpus()
        if devices:
            if tuple(map(int, devices[0]['compute_capability'].split('.'))) < (8, 9):
                raise RuntimeError('The configured CUDA FP8 path requires compute capability 8.9 or newer.')
            return 'cuda', devices[0]['uuid']
    raise RuntimeError('Automatic setup currently supports Apple Silicon MLX or Linux NVIDIA CUDA. '
                       'ROCm requires a separately configured and verified PyTorch runtime.')


def package_source(extras):
    root = Path(__file__).resolve().parent.parent
    if (root / 'pyproject.toml').exists():
        return f'{root}[{extras}]'
    distribution = importlib.metadata.distribution('sera-inference')
    direct = json.loads(distribution.read_text('direct_url.json') or '{}')
    if direct.get('url', '').startswith('file:'):
        path = Path(unquote(urlsplit(direct['url']).path))
        if path.exists():
            return f'{path}[{extras}]'
    if direct.get('vcs_info', {}).get('commit_id'):
        return f"sera-inference[{extras}] @ git+{direct['url']}@{direct['vcs_info']['commit_id']}"
    return f'sera-inference[{extras}]=={distribution.version}'


def install_runtime(home, backend):
    # Reuse an activated virtual environment so result.load() works in the caller.
    if sys.prefix != sys.base_prefix:
        python = Path(sys.executable)
    else:
        environment = home / 'runtime'
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / 'bin/python'
    command = [str(python), '-m', 'pip', 'install', package_source(f'{backend},swarm')]
    if shutil.which('uv'):
        command = ['uv', 'pip', 'install', '--python', str(python), package_source(f'{backend},swarm')]
    print(f'Installing the {backend.upper()} runtime and Sera tracing dependencies…', flush=True)
    subprocess.run(command, check=True)
    probe = 'import weave; ' + ('import mlx.core, mlx_lm' if backend == 'mlx' else
                               'import vllm, modelopt.torch.quantization, torch; assert torch.cuda.is_available()')
    subprocess.run([str(python), '-c', probe], check=True, timeout=90)
    return str(python)


def ensure_codex(home):
    tools = home / 'tools/node_modules/.bin'
    if tools.exists():
        os.environ['PATH'] = str(tools) + os.pathsep + os.environ.get('PATH', os.defpath)
    if not shutil.which('codex'):
        if not shutil.which('npm'):
            raise RuntimeError('Install Node.js to let Sera install Codex, or install Codex CLI and rerun sera setup.')
        subprocess.run(['npm', 'install', '--prefix', str(home / 'tools'), '@openai/codex'], check=True)
        os.environ['PATH'] = str(tools) + os.pathsep + os.environ.get('PATH', os.defpath)
    status = subprocess.run(['codex', 'login', 'status'], capture_output=True, text=True, timeout=15, check=False)
    if status.returncode == 0 and 'Logged in using ChatGPT' in status.stdout + status.stderr:
        return
    print('Sign in to Codex with your ChatGPT account.', flush=True)
    subprocess.run(['codex', '-c', 'forced_login_method="chatgpt"', 'login'], check=True)
    status = subprocess.run(['codex', 'login', 'status'], capture_output=True, text=True, timeout=15, check=False)
    if status.returncode or 'Logged in using ChatGPT' not in status.stdout + status.stderr:
        raise RuntimeError('Sera requires Codex ChatGPT login; API-key login is not supported.')


def model_profile(*, backend, model_id, revision, profile_id, seconds, trials,
                  quality_floor, max_tokens, tasks=None, gpu_uuid=None):
    value = {'profile_id': profile_id, 'source': {'model_id': model_id, 'revision': revision},
        'tasks': tasks or [], 'requires_examples': not bool(tasks),
        'evaluation_version': 'sera-setup-examples-v1',
        'recipes': {'int4': {'bits': 4, 'group_size': 64}, 'int8': {'bits': 8, 'group_size': 64}},
        'constraints': {'quality_floor': quality_floor}, 'objective': {'priority': 'memory'},
        'budget': {'max_candidate_trials': trials}, 'max_run_seconds': seconds,
        'job_timeout_seconds': min(180.0, seconds), 'max_tokens': max_tokens,
        'seed': 0, 'warmup': 1, 'repetitions': 3}
    if tasks and any(t.get('response_format') for t in tasks):
        value['response_format_version'] = 'sera-setup-formats-v1'
    if backend == 'cuda':
        if not tasks:
            raise ValueError('CUDA registration needs quality examples to freeze representative calibration prompts')
        prompts = [t['prompt'] if isinstance(t['prompt'], str) else
                   '\n'.join(message['content'] for message in t['prompt']) for t in tasks]
        value.update(backend='cuda', recipes={'fp8': {'format': 'fp8',
                     'calibration': {'prompts': prompts, 'seed': 0, 'max_length': 512}}},
                     runtime={'gpu_uuid': gpu_uuid, 'max_model_len': 2048,
                              'kv_cache_memory_bytes': 256 * 1024 * 1024,
                              'memory_sample_interval_seconds': .01})
    elif backend != 'mlx':
        raise ValueError('Use a separately verified profile for this backend')
    return validate_native_profile(value).model_dump()


def register_local(home, *, profiles, project, wandb_key, runtime_python, collections=None, port=8765):
    home = Path(home).resolve()
    profiles = [validate_native_profile(p).model_dump() for p in profiles]
    if not profiles or len({p['profile_id'] for p in profiles}) != len(profiles):
        raise ValueError('Register distinct models')
    if not isinstance(wandb_key, str) or not wandb_key.strip() or any(c.isspace() for c in wandb_key):
        raise ValueError('Supply the operator W&B credential')
    if len(project.split('/')) != 2 or any(not part.strip() for part in project.split('/')):
        raise ValueError('Supply the operator W&B entity/project')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Supply a valid local port')
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    client_path = home / 'client.json'
    key = json.loads(client_path.read_text())['api_key'] if client_path.exists() else secrets.token_urlsafe(32)
    profile_ids = [p['profile_id'] for p in profiles]
    config = {'profiles': profiles, 'project': project, 'collections': collections or {},
              'clients': {hashlib.sha256(key.encode()).hexdigest(): {'id': 'local', 'profiles': profile_ids}}}
    connection = {'api_key': key, 'endpoint': f'http://127.0.0.1:{port}'}
    # Secrets never enter service.json, command arguments, or printed setup output.
    private_json(home / 'credentials.json', {'WANDB_API_KEY': wandb_key})
    private_json(home / 'service.json', config)
    private_json(home / 'runtime.json', {'python': str(Path(runtime_python).absolute()), 'port': port})
    private_json(client_path, connection)
    return connection


def _operator_settings(home, operator_config=None):
    values = {}
    credentials = home / 'credentials.json'
    if credentials.exists():
        values.update(json.loads(credentials.read_text()))
    if operator_config:
        path = Path(operator_config).expanduser()
        if path.stat().st_size > 16384:
            raise ValueError('Operator settings exceed 16 KiB')
        values.update(json.loads(path.read_text()))
    env_file = Path.cwd() / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, separator, value = line.partition('=')
            key = key.strip().removeprefix('export ')
            if separator and key in {'WANDB_API_KEY', 'SERA_PROJECT'}:
                parsed = shlex.split(value, comments=True)
                if parsed:
                    values.setdefault(key, parsed[0])
    for key in ('WANDB_API_KEY', 'SERA_PROJECT'):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def _ask(label, default=None):
    answer = input(label + (f' [{default}]' if default is not None else '') + ': ').strip()
    return answer or default


def _model_examples(backend):
    from .workload_intake import read_examples
    required = backend == 'cuda'
    label = ('Quality examples JSON path (required for CUDA calibration)' if required else
             'Quality examples JSON path (Enter to supply examples per workload)')
    while True:
        path = _ask(label, '')
        if path:
            return read_examples(Path(path).expanduser())
        if not required:
            return None
        print('CUDA needs representative examples to calibrate quantization.', flush=True)


def setup(*, home=None, operator_config=None, start=True, install=True):
    home = Path(home or home_path()).resolve()
    print('Sera — the autonomous auto-research harness for inference', flush=True)
    backend, gpu_uuid = detect_backend()
    print(f'Detected {backend.upper()}. Models and quality checks will be registered locally.', flush=True)
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    if (home / 'process.json').exists():
        stop_local(home)
    python = install_runtime(home, backend) if install else sys.executable
    ensure_codex(home)
    prior = json.loads((home / 'service.json').read_text()) if (home / 'service.json').exists() else {}
    settings = _operator_settings(home, operator_config)
    project = _ask('Operator W&B entity/project', settings.get('SERA_PROJECT', prior.get('project')))
    key = settings.get('WANDB_API_KEY') or getpass.getpass('Operator W&B key (hidden): ').strip()
    profiles = list(prior.get('profiles', []))
    if profiles:
        print('Registered models: ' + ', '.join(p['profile_id'] for p in profiles))
    while not profiles or _ask('Register another model? y/n', 'n').lower() == 'y':
        model = _ask('Model repository', DEFAULT_MODEL)
        revision = _ask('Pinned model revision', DEFAULT_REVISION if model == DEFAULT_MODEL else None)
        name = _ask('Local model name', f'model-{len(profiles)+1}')
        tasks = _model_examples(backend)
        seconds = float(_ask('Maximum seconds per research job', '300'))
        trials = int(_ask('Maximum candidate experiments', '2'))
        floor = float(_ask('Minimum fraction of quality checks passed', '0.99'))
        max_tokens = int(_ask('Maximum generated tokens per request', '128'))
        profiles.append(model_profile(backend=backend, model_id=model, revision=revision, profile_id=name,
            seconds=seconds, trials=trials, quality_floor=floor, max_tokens=max_tokens, tasks=tasks, gpu_uuid=gpu_uuid))
    collections = dict(prior.get('collections', {}))
    while True:
        documents = _ask('Document directory or JSONL file (Enter to skip)', '')
        if not documents:
            break
        source = Path(documents).expanduser().resolve()
        from .rag import Corpus
        inventory = Corpus(source).inspect()
        name = _ask('Collection name', f'documents-{len(collections)+1}')
        evaluation = _ask('RAG question/answer evaluation JSON path (optional)', '')
        entry = {'source': str(source), 'owners': ['local'], 'profiles': [p['profile_id'] for p in profiles]}
        if evaluation:
            from .rag_intake import read_evaluation
            path = Path(evaluation).expanduser().resolve()
            read_evaluation(path)
            entry['evaluation'] = str(path)
        collections[name] = entry
        print(f'Registered {inventory["document_count"]} documents.', flush=True)
    register_local(home, profiles=profiles, collections=collections, project=project, wandb_key=key,
                   runtime_python=python)
    if start:
        start_local(home)
    print('Setup complete. Run: sera optimize "Describe your workload" --examples checks.json', flush=True)
    print(f'Python runtime: {python}', flush=True)
    return json.loads((home / 'client.json').read_text())


def local_connection():
    home = home_path()
    if not (home / 'client.json').exists():
        if not sys.stdin.isatty():
            raise RuntimeError('Run `sera setup` once in a terminal, then call sera.Optimize again.')
        setup(home=home)
    else:
        start_local(home)
    return json.loads((home / 'client.json').read_text())


def _client(home):
    from .managed_client import SeraClient
    return SeraClient(**json.loads((home / 'client.json').read_text()))


def _ready(home):
    from .managed_client import SeraServiceError
    try:
        return _client(home)._request('GET', '/v1/health').get('status') == 'ready'
    except (SeraServiceError, OSError, ValueError):
        return False


def start_local(home):
    home = Path(home).resolve()
    if not (home / 'client.json').exists():
        raise RuntimeError('Run `sera setup` before starting the service.')
    with (home / 'control.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return _start_local(home)


def _start_local(home):
    home = Path(home).resolve()
    if _ready(home):
        return
    runtime = json.loads((home / 'runtime.json').read_text())
    instance = secrets.token_hex(16)
    command = [runtime['python'], '-m', 'sera', 'serve', '--home', str(home), '--instance', instance]
    descriptor = os.open(home / 'service.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, 'a') as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=True, cwd=home)
    private_json(home / 'process.json', {'pid': process.pid, 'instance': instance})
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Sera could not start. Inspect {home / "service.log"}')
        if _ready(home):
            print('Sera is ready at ' + json.loads((home / 'client.json').read_text())['endpoint'], flush=True)
            return
        time.sleep(.1)
    from .process_ownership import terminate_group
    terminate_group(process)
    (home / 'process.json').unlink(missing_ok=True)
    raise RuntimeError(f'Sera startup timed out. Inspect {home / "service.log"}')


def stop_local(home):
    home = Path(home).resolve()
    if not (home / 'process.json').exists():
        return
    with (home / 'control.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return _stop_local(home)


def _stop_local(home):
    home = Path(home).resolve()
    path = home / 'process.json'
    if not path.exists():
        return
    saved = json.loads(path.read_text())
    process = subprocess.run(['ps', '-p', str(saved['pid']), '-o', 'command='],
                             capture_output=True, text=True, timeout=5, check=False)
    if process.returncode:
        path.unlink(missing_ok=True)
        return
    if '-m sera serve' not in process.stdout or f'--instance {saved["instance"]}' not in process.stdout:
        raise RuntimeError('The saved PID no longer belongs to this Sera service')
    os.kill(saved['pid'], signal.SIGINT)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            if os.waitpid(saved['pid'], os.WNOHANG)[0] == saved['pid']:
                path.unlink(missing_ok=True)
                return
        except ChildProcessError:
            pass
        try:
            os.kill(saved['pid'], 0)
        except ProcessLookupError:
            path.unlink(missing_ok=True)
            return
        time.sleep(.1)
    raise RuntimeError('Service shutdown is still in progress; do not start another worker yet')


def serve_local(home):
    from .managed_service import ManagedService, make_server
    home = Path(home).resolve()
    settings = json.loads((home / 'credentials.json').read_text())
    os.environ['WANDB_API_KEY'] = settings['WANDB_API_KEY']
    local_tools = home / 'tools/node_modules/.bin'
    if local_tools.exists():
        os.environ['PATH'] = str(local_tools) + os.pathsep + os.environ.get('PATH', os.defpath)
    config = json.loads((home / 'service.json').read_text())
    runtime = json.loads((home / 'runtime.json').read_text())
    service = ManagedService(folder=home / 'jobs', **config)
    try:
        server = make_server(service, port=runtime['port'])
        try:
            server.serve_forever()
        finally:
            server.server_close()
    except KeyboardInterrupt:
        pass
    finally:
        service.close()
