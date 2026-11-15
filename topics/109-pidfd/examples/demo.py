"""Standalone Linux parent with exclusive reaping ownership."""
import errno
import os
import select
import signal
import sys

if not __debug__:
    raise SystemExit("Run without Python optimization: assertions validate the example")
if sys.platform != "linux":
    raise SystemExit("Linux required for native pidfd operations")
signal.signal(signal.SIGCHLD, signal.SIG_DFL)
signal.signal(signal.SIGTERM, signal.SIG_DFL)
signal.pthread_sigmask(signal.SIG_SETMASK, [])
pid = os.fork()
if pid == 0:
    while True:
        signal.pause()
pfd = None
reaped = False
try:
    pfd = os.pidfd_open(pid, 0)
    poller = select.poll()
    poller.register(pfd, select.POLLIN)
    assert poller.poll(0) == []
    signal.pidfd_send_signal(pfd, signal.SIGTERM)
    assert poller.poll(5000), "child exit timeout"
    status = os.waitid(os.P_PIDFD, pfd, os.WEXITED)
    reaped = True
    assert status.si_pid == pid
    assert status.si_code == os.CLD_KILLED
    assert status.si_status == signal.SIGTERM
    try:
        signal.pidfd_send_signal(pfd, 0)
    except ProcessLookupError as error:
        assert error.errno == errno.ESRCH
    else:
        raise AssertionError("reaped child still signalable")
    print("PASS: intended child terminated; old pidfd returns ESRCH")
finally:
    if not reaped:
        # Exclusive reaping retains this child's numeric PID through cleanup.
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    if pfd is not None:
        os.close(pfd)
