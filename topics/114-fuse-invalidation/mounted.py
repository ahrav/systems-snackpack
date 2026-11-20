"""Test one held FUSE descriptor against a direct backing-file oracle."""
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import tempfile


def reply(server):
    if not select.select([server.stdout], [], [], 10)[0]:
        raise TimeoutError("daemon response timed out")
    return server.stdout.readline().strip()


def observe(fd):
    return stat.S_IMODE(os.fstat(fd).st_mode), os.pread(fd, 4, 0)


def experiment(binary, directory):
    mountpoint = directory / "mnt"
    mountpoint.mkdir()
    path = directory / "source"
    with path.open("w+b", buffering=0) as writer:
        writer.write(b"BLUE")
        os.fchmod(writer.fileno(), 0o444)
        server = subprocess.Popen([binary, path, mountpoint], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, bufsize=0)
        try:
            assert reply(server) == b"mounted"
            with (mountpoint / "palette").open("rb", buffering=0) as reader:
                fd = reader.fileno()
                assert observe(fd) == observe(writer.fileno()) == (0o444, b"BLUE")
                os.pwrite(writer.fileno(), b"GOLD", 0)
                os.fchmod(writer.fileno(), 0o400)
                oracle = observe(writer.fileno())
                assert oracle == (0o400, b"GOLD")
                for command, expected in [(None, None),
                                          (b"a", (0o400, b"BLUE")), (b"p", oracle)]:
                    if command:
                        server.stdin.write(command)
                        assert reply(server) == b"0"
                    actual = observe(fd)
                    print(command or b"none", format(actual[0], "04o"), actual[1])
                    if command is None:
                        # The kernel may already have refreshed mode on this descriptor.
                        assert actual[0] in (0o444, 0o400) and actual[1] == b"BLUE"
                    else:
                        assert actual == expected, (actual, expected)
        finally:
            server.stdin.close()
            if os.path.ismount(mountpoint):
                subprocess.run(["fusermount3", "-u", mountpoint], check=True, timeout=10)
            assert server.wait(timeout=10) == 0


if __name__ == "__main__":
    if not __debug__:
        raise RuntimeError("Run this test with Python assertions enabled")
    with tempfile.TemporaryDirectory() as tmp:
        experiment(Path(sys.argv[1]).resolve(), Path(tmp))
