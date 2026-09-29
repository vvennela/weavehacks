"""Keep a durable ownership lock alive across an entire managed process tree."""
import fcntl
import os
import signal

LIFETIME_FD = 'SERA_LIFETIME_FD'


def inherit_lifetime(env, descriptors):
    """Extend the service's lock lifetime to a child without exposing credentials."""
    descriptor = os.environ.get(LIFETIME_FD)
    if descriptor is not None:
        fd = int(descriptor)
        os.fstat(fd)  # Fail before launching if the inherited descriptor is invalid.
        env[LIFETIME_FD] = descriptor
        return (*descriptors, fd)
    return tuple(descriptors)


def tree_is_alive(folder):
    with (folder / 'process-tree.lock').open('a+') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def terminate_group(process):
    """Stop an owned process group, tolerating an already-reaped group on macOS."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        if process.poll() is None:
            raise
    process.wait()
