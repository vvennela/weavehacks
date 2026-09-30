"""Keep a tool command in a process group owned by its controller pipe."""
import os
import signal
import subprocess
import sys
import threading


def main():
    descriptor = int(os.environ.pop('SERA_COMMAND_PARENT_FD'))
    def watch():
        try:
            os.read(descriptor, 1)
        finally:
            os.killpg(os.getpid(), signal.SIGKILL)
    threading.Thread(target=watch, daemon=True).start()
    # The command shares this wrapper's group. Controller loss kills both.
    return subprocess.call(sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
