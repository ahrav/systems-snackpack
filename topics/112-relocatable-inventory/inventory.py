"""Read a stable INV1 inventory segment."""
import mmap
import os
import struct
import tempfile


def selected(data):
    size = len(data)
    if size < 16 or size % 8 or data[:4] != b"INV1":
        raise ValueError("invalid inventory layout")
    offset, = struct.unpack_from("<I", data, 4)
    if offset < 8 or offset > size - 8 or (offset - 8) % 8:
        raise ValueError("invalid record offset")
    return struct.unpack_from("<II", data, offset)


def demo():
    for offset in (8, 16, 12, 24, 0xffffffff):
        data = struct.pack("<4s5I", b"INV1", offset, 11, 3, 42, 7)
        try:
            print(offset, selected(data), flush=True)
        except ValueError as error:
            print(offset, error, flush=True)


def two_readers():
    with tempfile.TemporaryFile() as file:
        file.write(struct.pack("<4s5I", b"INV1", 16, 11, 3, 42, 7))
        file.flush()
        with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as first:
            assert selected(first) == (42, 7)
            child = os.fork()
            if child == 0:
                # The inherited mapping still occupies the parent's address.
                # A second, non-overlapping mapping must have a different base.
                with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as second:
                    result = selected(second)
                    print(f"child read {result} from a distinct mapping", flush=True)
                os._exit(0 if result == (42, 7) else 1)
            _, status = os.waitpid(child, 0)
            if status != 0:
                raise RuntimeError(f"child wait status {status}")


if __name__ == "__main__":
    demo()
    two_readers()
