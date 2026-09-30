import os
import signal
import subprocess
import sys
import time


def test_command_group_stops_when_controller_pipe_closes(tmp_path):
    read_fd, write_fd = os.pipe()
    ready = tmp_path / 'ready'
    delayed = tmp_path / 'delayed'
    code = ('from pathlib import Path; import time; '
            f'Path({str(ready)!r}).touch(); time.sleep(1); Path({str(delayed)!r}).touch(); time.sleep(10)')
    process = subprocess.Popen([sys.executable, '-m', 'sera.owned_command', sys.executable, '-c', code],
        env=os.environ | {'SERA_COMMAND_PARENT_FD': str(read_fd)},
        pass_fds=(read_fd,), start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.close(read_fd)
    try:
        deadline = time.monotonic() + 3
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.01)
        assert ready.exists(), process.communicate(timeout=1)
        os.close(write_fd)
        write_fd = None
        assert process.wait(timeout=3) == -signal.SIGKILL
        time.sleep(1.1)
        assert not delayed.exists()
    finally:
        if write_fd is not None:
            os.close(write_fd)
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
