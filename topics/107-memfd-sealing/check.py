"""Linux syscall contract checks; independent byte/length oracle, no timings."""
import errno
import fcntl as f
import itertools
import json
import mmap
import os
import platform
import sys

FUTURE = 0x10  # Linux UAPI F_SEAL_FUTURE_WRITE, available since Linux 5.1.
W, S, G = f.F_SEAL_WRITE, f.F_SEAL_SHRINK, f.F_SEAL_GROW
REQUIRED = W | S | G


def create(payload):
    fd = os.memfd_create("seal-check", os.MFD_ALLOW_SEALING | os.MFD_CLOEXEC)
    os.ftruncate(fd, len(payload))
    assert os.pwrite(fd, payload, 0) == len(payload)
    return fd


def expect_error(code, call):
    try:
        value = call()
    except OSError as error:
        assert error.errno == code, (error.errno, code)
    else:
        if hasattr(value, 'close'):
            value.close()
        raise AssertionError("operation unexpectedly succeeded")


def matrix():
    records = []
    # Specifications list the restrictions each operation needs to respect.
    blocks = {'overwrite': W | FUTURE, 'shrink': S, 'grow': G,
              'shared_write': W | FUTURE, 'private_write': 0}
    for selected in itertools.product([False, True], repeat=4):
        mask = sum(bit for bit, enabled in zip([W, S, G, FUTURE], selected) if enabled)
        for name, forbidden in blocks.items():
            payload = bytes(range(256)) * 16
            fd = create(payload)
            f.fcntl(fd, f.F_ADD_SEALS, mask)
            assert f.fcntl(fd, f.F_GET_SEALS) & mask == mask
            expected = payload
            def operation():
                if name == 'overwrite':
                    assert os.pwrite(fd, b'Z', 0) == 1
                elif name == 'shrink':
                    os.ftruncate(fd, len(payload) // 2)
                elif name == 'grow':
                    os.ftruncate(fd, len(payload) * 2)
                else:
                    access = mmap.ACCESS_WRITE if name == 'shared_write' else mmap.ACCESS_COPY
                    with mmap.mmap(fd, len(payload), access=access) as view:
                        view[0] = 90
                        assert view[0] == 90
            blocked = bool(mask & forbidden)
            if blocked:
                expect_error(errno.EPERM, operation)
            else:
                operation()
                if name in ('overwrite', 'shared_write'):
                    expected = b'Z' + payload[1:]
                elif name == 'shrink':
                    expected = payload[:len(payload)//2]
                elif name == 'grow':
                    expected = payload + bytes(len(payload))
            assert os.fstat(fd).st_size == len(expected)
            assert os.pread(fd, len(expected) + 1, 0) == expected
            os.close(fd)
            records.append(dict(mask=mask, operation=name, blocked=blocked))
    return records


def inherited_writer():
    fd = create(b'A' * 4096)
    writer = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    cmd_r, cmd_w = os.pipe()
    ack_r, ack_w = os.pipe()
    child = os.fork()
    if child == 0:
        try:
            os.close(cmd_w); os.close(ack_r)
            assert os.read(cmd_r, 1) == b'w'
            writer[0] = ord('B')
            os.write(ack_w, b'w')
            assert os.read(cmd_r, 1) == b'u'
            writer.close()
            os.write(ack_w, b'u')
            os.close(fd)
            os._exit(0)
        except BaseException:
            os._exit(1)
    os.close(cmd_r); os.close(ack_w)
    writer.close()
    f.fcntl(fd, f.F_ADD_SEALS, FUTURE | S | G)
    expect_error(errno.EBUSY, lambda: f.fcntl(fd, f.F_ADD_SEALS, W))
    os.write(cmd_w, b'w'); assert os.read(ack_r, 1) == b'w'
    assert os.pread(fd, 4096, 0) == b'B' + b'A' * 4095
    expect_error(errno.EPERM, lambda: os.pwrite(fd, b'C', 0))
    os.write(cmd_w, b'u'); assert os.read(ack_r, 1) == b'u'
    assert os.waitpid(child, 0)[1] == 0
    f.fcntl(fd, f.F_ADD_SEALS, W | f.F_SEAL_SEAL)
    assert f.fcntl(fd, f.F_GET_SEALS) & REQUIRED == REQUIRED
    expect_error(errno.EPERM, lambda: f.fcntl(fd, f.F_ADD_SEALS, S))
    os.close(cmd_w); os.close(ack_r); os.close(fd)


def publication(size):
    # Producer recurrence and receiver algebra generate the same expected bytes
    # independently. The receiver compares every byte, not only a checksum.
    data = bytearray(size)
    value = 19
    for index in range(size):
        data[index] = value
        value = (value + 73) % 256
    fd = create(data)
    f.fcntl(fd, f.F_ADD_SEALS, REQUIRED | f.F_SEAL_SEAL)
    child = os.fork()  # Publication by descriptor inheritance after sealing.
    if child == 0:
        try:
            assert f.fcntl(fd, f.F_GET_SEALS) & REQUIRED == REQUIRED
            length = os.fstat(fd).st_size
            assert length == size and 0 < length <= 1024 * 1024
            with mmap.mmap(fd, length, access=mmap.ACCESS_READ) as view:
                assert view[:] == bytes((19 + 73 * i) % 256 for i in range(length))
                expect_error(errno.EPERM, lambda: os.ftruncate(fd, 0))
                expect_error(errno.EPERM, lambda: os.ftruncate(fd, length + 1))
                expect_error(errno.EPERM, lambda: os.pwrite(fd, b'X', 0))
                assert view[:] == bytes((19 + 73 * i) % 256 for i in range(length))
            os._exit(0)
        except BaseException:
            os._exit(1)
    assert os.waitpid(child, 0)[1] == 0
    os.close(fd)


def main():
    if platform.system() != 'Linux':
        print(json.dumps({'status': 'SKIP', 'reason': 'Linux memfd required'}))
        return
    fd = os.memfd_create('no-sealing', os.MFD_CLOEXEC)
    assert f.fcntl(fd, f.F_GET_SEALS) & f.F_SEAL_SEAL
    expect_error(errno.EPERM, lambda: f.fcntl(fd, f.F_ADD_SEALS, W))
    os.close(fd)
    records = matrix()
    inherited_writer()
    sizes = [1, 4095, 4096, 4097, 65536, 1048576]
    for size in sizes:
        publication(size)
    print(json.dumps(dict(status='PASS', host=platform.uname()._asdict(),
                         python=sys.version, matrix=records,
                         inherited_writer='PASS', published_sizes=sizes), indent=2))


if __name__ == '__main__':
    main()
