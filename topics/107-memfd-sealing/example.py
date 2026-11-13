"""Run with Python 3.8+ on Linux."""
import errno
import fcntl
import mmap
import os

fd = os.memfd_create("routing-table", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
payload = b"route=worker-7\n"
os.ftruncate(fd, len(payload))
with mmap.mmap(fd, len(payload), access=mmap.ACCESS_WRITE) as writer:
    writer[:] = payload
required = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW
fcntl.fcntl(fd, fcntl.F_ADD_SEALS, required | fcntl.F_SEAL_SEAL)
assert fcntl.fcntl(fd, fcntl.F_GET_SEALS) & required == required
length = os.fstat(fd).st_size
assert 0 < length <= 4096
with mmap.mmap(fd, length, access=mmap.ACCESS_READ) as reader:
    assert reader[:] == payload
    print(reader[:].decode(), end="")
try:
    os.ftruncate(fd, 0)
except OSError as error:
    assert error.errno == errno.EPERM
    print("shrink blocked")
else:
    raise AssertionError("shrink unexpectedly succeeded")
os.close(fd)
