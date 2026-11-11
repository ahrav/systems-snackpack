"""Portable single-threaded snapshot-isolation check."""
import mmap
import os
page = mmap.PAGESIZE
count = 4096
buf = mmap.mmap(-1, count * page, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                prot=mmap.PROT_READ | mmap.PROT_WRITE)
buf[:] = b"\x2a" * len(buf)
r, w = os.pipe()
pid = os.fork()
if pid == 0:
    os.close(w)
    token = os.read(r, 1)
    valid = token == b"x" and all(buf[i * page] == 42 for i in range(count))
    os._exit(0 if valid else 1)
os.close(r)
for i in range(count):
    buf[i * page] = 43
assert all(buf[i * page] == 43 for i in range(count))
os.write(w, b"x")
os.close(w)
_, status = os.waitpid(pid, 0)
assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
print("parent=43 child=42: snapshot preserved")
