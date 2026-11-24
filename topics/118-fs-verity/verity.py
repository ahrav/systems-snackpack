"""fs-verity v1, SHA-256, 4096-byte blocks, empty salt, immutable input bytes."""
from hashlib import sha256
from struct import pack

BLOCK = 4096
HASH = 32
FANOUT = BLOCK // HASH


def digest(block):
    return sha256(block).digest()


def file_digest(size, root):
    header = pack("<BBBBIQ", 1, 1, 12, 0, 0, size)
    return digest((header + root).ljust(256, b"\0"))


def build(data):
    hashes = [digest(data[i:i + BLOCK].ljust(BLOCK, b"\0"))
              for i in range(0, len(data), BLOCK)]
    levels = []
    while len(hashes) > 1:
        level = tuple(b"".join(hashes[i:i + FANOUT]).ljust(BLOCK, b"\0")
                      for i in range(0, len(hashes), FANOUT))
        levels.append(level)
        hashes = [digest(block) for block in level]
    return tuple(levels), hashes[0] if hashes else bytes(HASH)


class Reader:
    """Verify immutable data and proof bytes against a separately supplied file digest."""

    def __init__(self, data, levels, root, trusted_digest):
        if file_digest(len(data), root) != trusted_digest:
            raise ValueError("file digest mismatch")
        self.data = data
        self.levels = levels
        self.root = root
        self.verified = {}
        self.hash_reads = 0
        self.data_reads = 0

    def read(self, index):
        if not 0 <= index * BLOCK < len(self.data):
            raise IndexError(index)
        slot = index
        path = []
        count = (len(self.data) + BLOCK - 1) // BLOCK
        while count > 1:
            parent, child = divmod(slot, FANOUT)
            path.append((parent, child))
            slot = parent
            count = (count + FANOUT - 1) // FANOUT
        expected = self.root
        for level in reversed(range(len(path))):
            parent, child = path[level]
            key = (level, parent)
            block = self.verified.get(key)
            if block is None:
                block = self.levels[level][parent]
                self.hash_reads += 1
                if len(block) != BLOCK or digest(block) != expected:
                    raise ValueError("hash block mismatch")
                self.verified[key] = block
            expected = block[child * HASH:(child + 1) * HASH]
        start = index * BLOCK
        data = self.data[start:start + BLOCK]
        self.data_reads += 1
        if digest(data.ljust(BLOCK, b"\0")) != expected:
            raise ValueError("data block mismatch")
        return data


def index_bytes():
    return b"".join(i.to_bytes(4, "little") + bytes(BLOCK - 4) for i in range(16384))


if __name__ == "__main__":
    data = index_bytes()
    levels, root = build(data)
    # In production the expected value comes from an authenticated release manifest.
    reader = Reader(data, levels, root, file_digest(len(data), root))
    for index in (129, 130, 384):
        before = reader.hash_reads
        block = reader.read(index)
        assert int.from_bytes(block[:4], "little") == index
        print("block", index, "KiB read:", 4 * (1 + reader.hash_reads - before))
    a = build(b"A")[1]
    b = build(b"A\0")[1]
    print("equal raw roots:", a == b)
    print("equal file digests:", file_digest(1, a) == file_digest(2, b))
