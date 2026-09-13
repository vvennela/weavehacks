"""Transactional local execution records. JSON files are readable mirrors."""

from datetime import datetime, timezone
from contextlib import closing, contextmanager
import fcntl
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import threading
import uuid

from .storage import content_hash


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def environment_fingerprint():
    versions = {}
    for name in ('vllm', 'torch', 'transformers', 'pydantic'):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    source = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(Path(__file__).parent.glob('*.py'))}
    return dict(python=platform.python_version(), system=platform.system(),
                machine=platform.machine(), packages=versions, source_hash=content_hash(source))


def run_specification(report):
    keys = ('schema_version', 'created_at', 'model_id', 'model_revision', 'prompts',
            'workload_hash', 'generation', 'workload', 'objective', 'constraints',
            'evaluation', 'execution')
    return {key: report.get(key) for key in keys}


def encode_record(record):
    encoded = json.dumps(record, ensure_ascii=False, allow_nan=False)
    keys = [os.environ.get(name, '') for name in ('WANDB_API_KEY', 'OPENAI_API_KEY', 'HF_TOKEN')]
    if (any(len(key) >= 8 and key in encoded for key in keys)
            or re.search(r'wandb_v1_[A-Za-z0-9_-]{20,}|Bearer [A-Za-z0-9_.-]{16,}', encoded)):
        raise ValueError('Refusing to persist a credential in optimizer evidence')
    return encoded


class Ledger:
    """One optimizer owns a run. A killed process releases the OS lock."""

    def __init__(self, folder, *, existing=False):
        self.folder = Path(folder)
        self.path = self.folder / 'ledger.sqlite3'
        if existing and not self.path.is_file():
            raise ValueError('No durable ledger exists; legacy JSON records cannot be resumed')
        self._lock = (self.folder / 'optimizer.lock').open('a+')
        self._mutex = threading.RLock()
        self.closed = False
        self.pid = os.getpid()
        try:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock.close()
            raise RuntimeError('This optimizer run has an active owner') from None
        try:
            with self.connect() as database:
                database.executescript('''
                    CREATE TABLE IF NOT EXISTS checkpoint (
                        id INTEGER PRIMARY KEY CHECK (id = 1), revision INTEGER NOT NULL,
                        updated_at TEXT NOT NULL, report_json TEXT NOT NULL, report_hash TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS trials (
                        trial_id TEXT PRIMARY KEY, identity_hash TEXT UNIQUE,
                        status TEXT NOT NULL, updated_at TEXT NOT NULL, record_json TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS agent_operations (
                        operation_id TEXT PRIMARY KEY, status TEXT NOT NULL,
                        updated_at TEXT NOT NULL, record_json TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS events (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT NOT NULL,
                        kind TEXT NOT NULL, record_json TEXT NOT NULL);
                ''')
        except BaseException:
            self.close()
            raise

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('PRAGMA synchronous=FULL')
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, report):
        if self.closed or self.pid != os.getpid():
            raise RuntimeError('Cannot write without the optimizer ownership lock')
        with self._mutex, self.connect() as database:
            if 'durability' not in report:
                specification = run_specification(report)
                report['durability'] = dict(schema_version='sera-ledger-v1',
                    run_specification=specification, run_hash=content_hash(specification),
                    environment=environment_fingerprint())
            encoded = encode_record(report)
            prior = database.execute('SELECT revision FROM checkpoint WHERE id=1').fetchone()
            revision = prior[0] + 1 if prior else 1
            database.execute('INSERT OR REPLACE INTO checkpoint VALUES (1, ?, ?, ?, ?)',
                             (revision, timestamp(), encoded, content_hash(report)))
            trials = [report.get('baseline'), report.get('candidate_trial')]
            trials += report.get('search_trials', [])
            # Fit-first promotes its candidate to the measured baseline. Keep
            # the deployment under report.deployment, not as a second trial.
            current_ids = {trial['trial_id'] for trial in filter(None, trials)}
            for (trial_id,) in database.execute('SELECT trial_id FROM trials').fetchall():
                if trial_id not in current_ids:
                    database.execute('DELETE FROM trials WHERE trial_id=?', (trial_id,))
            for trial in filter(None, trials):
                identity = content_hash(dict(model=report.get('model_id'),
                    revision=report.get('model_revision'), workload=report.get('workload_hash'),
                    configuration=trial['config_hash'])) if trial.get('config_hash') else None
                database.execute('''INSERT INTO trials VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(trial_id) DO UPDATE SET identity_hash=excluded.identity_hash,
                    status=excluded.status, updated_at=excluded.updated_at, record_json=excluded.record_json''',
                    (trial['trial_id'], identity, trial['status'], timestamp(), json.dumps(trial)))
            for index, operation in enumerate(report.get('agent_calls', [])):
                database.execute('INSERT OR REPLACE INTO agent_operations VALUES (?, ?, ?, ?)',
                    (f'call-{index}', 'recorded', timestamp(), json.dumps(operation)))
            database.execute('INSERT INTO events(time, kind, record_json) VALUES (?, ?, ?)',
                (timestamp(), 'checkpoint', json.dumps(dict(revision=revision,
                    status=report.get('status'), checkpoint=report.get('recovery_checkpoint')))))

    def close(self):
        if not self.closed:
            self.closed = True
            self._lock.close()

    def record_operation(self, operation_id, record):
        if self.closed or self.pid != os.getpid():
            raise RuntimeError('Cannot journal an agent call without optimizer ownership')
        with self._mutex, self.connect() as database:
            database.execute('INSERT OR REPLACE INTO agent_operations VALUES (?, ?, ?, ?)',
                (operation_id, record['status'], timestamp(), encode_record(record)))

    def resolve_interrupted_calls(self):
        """An old request may have reached its provider; never pretend it completed."""
        with self._mutex, self.connect() as database:
            pending = database.execute(
                "SELECT operation_id, record_json FROM agent_operations WHERE status='requested'").fetchall()
            for operation_id, encoded in pending:
                record = json.loads(encoded)
                record.update(status='interrupted', resolved_at=timestamp(),
                    resolution='Provider completion is unknown; this response is not used')
                database.execute('UPDATE agent_operations SET status=?, updated_at=?, record_json=? WHERE operation_id=?',
                    ('interrupted', timestamp(), encode_record(record), operation_id))
            return len(pending)


class JournalAgent:
    """Write call intent before contacting an agent, including parallel forks."""

    def __init__(self, agent, ledger):
        self.agent, self.ledger = agent, ledger

    def __getattr__(self, name):
        return getattr(self.agent, name)

    def fork(self):
        return JournalAgent(self.agent.fork(), self.ledger)

    def _invoke(self, method, arguments):
        operation_id = uuid.uuid4().hex
        record = dict(operation_id=operation_id, method=method, arguments=arguments,
                      status='requested', requested_at=timestamp())
        self.ledger.record_operation(operation_id, record)
        try:
            response = getattr(self.agent, method)(*arguments)
            record.update(status='completed', completed_at=timestamp(),
                response=response.model_dump() if response is not None else None)
            self.ledger.record_operation(operation_id, record)
            return response
        except BaseException as error:
            record.pop('response', None)
            record.update(status='failed', completed_at=timestamp(), error=type(error).__name__)
            self.ledger.record_operation(operation_id, record)
            raise

    def request(self, role, evidence, instruction):
        return self._invoke('request', [role, evidence, instruction])

    def review(self, evidence):
        return self._invoke('review', [evidence])


def read_checkpoint(folder):
    path = Path(folder) / 'ledger.sqlite3'
    if not path.is_file():
        raise ValueError('No durable ledger exists; legacy JSON records cannot be resumed')
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as database:
        row = database.execute('SELECT revision, report_json, report_hash FROM checkpoint WHERE id=1').fetchone()
    if row is None:
        raise ValueError('The ledger has no committed checkpoint')
    report = json.loads(row[1])
    if content_hash(report) != row[2]:
        raise ValueError('Ledger checkpoint checksum mismatch')
    durability = report.get('durability', {})
    if (durability.get('schema_version') != 'sera-ledger-v1'
            or content_hash(durability.get('run_specification')) != durability.get('run_hash')
            or run_specification(report) != durability['run_specification']):
        raise ValueError('Ledger run specification checksum mismatch')
    return report, row[0]
