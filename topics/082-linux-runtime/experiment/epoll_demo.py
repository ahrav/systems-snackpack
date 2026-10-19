#!/usr/bin/env python3
"""Linux-only, bounded ET service with three nonblocking pipes."""
import collections
import os
import select
import sys

if sys.flags.optimize:
    sys.exit('this probe checks with assert statements; run it with Python optimization off')

pipes = [os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC) for _ in range(3)]
ep = select.epoll()
ready, queued = collections.deque(), set()
received = {r: bytearray() for r, _ in pipes}
served = []

def enqueue(fd):
    if fd not in queued:
        queued.add(fd)
        ready.append(fd)

try:
    for r, _ in pipes:
        ep.register(r, select.EPOLLIN | select.EPOLLET)
    os.write(pipes[0][1], b'A' * 128)
    os.write(pipes[1][1], b'B' * 16)
    for turn in range(100):
        if turn == 2:
            os.write(pipes[2][1], b'C' * 16)
        # Discover new work even while the local queue stays nonempty.
        for fd, _ in ep.poll(0 if ready else 0.1):
            enqueue(fd)
        if not ready:
            continue
        fd = ready.popleft()
        queued.remove(fd)
        try:
            data = os.read(fd, 16)
        except BlockingIOError:
            continue
        if not data:
            ep.unregister(fd)
            continue
        received[fd].extend(data)
        served.append(fd)
        enqueue(fd)  # Budget used: preserve readiness until EAGAIN.
        if [len(received[r]) for r, _ in pipes] == [128, 16, 16]:
            break
    assert [bytes(received[r]) for r, _ in pipes] == [b'A' * 128, b'B' * 16, b'C' * 16]
    hot_done = len(served) - 1 - served[::-1].index(pipes[0][0])
    assert served.index(pipes[1][0]) < hot_done and served.index(pipes[2][0]) < hot_done, served
    print('PASS: hot=128 cold=16 late=16; no second hot-pipe write needed')
finally:
    ep.close()
    for r, w in pipes:
        os.close(r)
        os.close(w)
