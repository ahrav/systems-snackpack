#!/usr/bin/env python3
"""Real Linux pipe readiness checks. All waits are bounded."""
import os
import select
import subprocess
import sys
from pathlib import Path

if sys.flags.optimize:
    sys.exit('this probe checks with assert statements; run it with Python optimization off')

for mode in ['level', 'edge', 'oneshot']:
    r, w = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    ep = select.epoll()
    flag = {'level': 0, 'edge': select.EPOLLET, 'oneshot': select.EPOLLONESHOT}[mode]
    try:
        ep.register(r, select.EPOLLIN | flag)
        assert os.write(w, b'a' * 64) == 64
        assert ep.poll(1) == [(r, select.EPOLLIN)]
        assert os.read(r, 16) == b'a' * 16
        again = ep.poll(0)
        if mode == 'level':
            assert again == [(r, select.EPOLLIN)]
        else:
            assert again == [], (mode, again)
        if mode == 'oneshot':
            ep.modify(r, select.EPOLLIN | flag)
            assert ep.poll(1) == [(r, select.EPOLLIN)]
        assert os.read(r, 64) == b'a' * 48
        try:
            os.read(r, 1)
        except BlockingIOError:
            pass
        else:
            raise AssertionError('expected EAGAIN')
        if mode == 'oneshot':
            ep.modify(r, select.EPOLLIN | flag)
        assert os.write(w, b'end') == 3
        os.close(w)
        w = -1
        events = ep.poll(1)
        assert events and events[0][1] & select.EPOLLHUP
        assert os.read(r, 64) == b'end'
        assert os.read(r, 64) == b''
        print('PASS:', mode, 'partial drain, rearm if needed, data before EOF')
    finally:
        ep.close()
        os.close(r)
        if w >= 0:
            os.close(w)
subprocess.run([sys.executable, str(Path(__file__).with_name('epoll_demo.py'))], check=True, timeout=15)
