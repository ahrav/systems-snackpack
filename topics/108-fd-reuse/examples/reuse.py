"""A delayed callback reads the replacement pipe through a recycled descriptor."""
import os

a, aw = os.pipe()
fd = a
generation = 1
queued = (fd, generation)
os.write(aw, b"A")
os.close(a)
os.close(aw)
b, bw = os.pipe()
if b != fd:
    os.dup2(b, fd)
    os.close(b)
generation += 1
os.write(bw, b"B")
assert queued[1] != generation
print("generation check: stale callback rejected")
wrong = os.read(queued[0], 1)
assert wrong == b"B"
print("raw fd callback: consumed B")
os.close(fd)
os.close(bw)
