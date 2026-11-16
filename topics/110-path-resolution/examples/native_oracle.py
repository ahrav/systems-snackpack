"""Linux fixture identities are obtained before invoking the candidate wrapper."""
import ctypes
import errno
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading

lib = ctypes.CDLL(str(Path(sys.argv[1]).resolve()), use_errno=True)
lib.open_policy.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_ulonglong]
lib.open_policy.restype = ctypes.c_int
# Linux UAPI include/uapi/linux/openat2.h values.
NO_XDEV, NO_MAGIC, NO_SYMLINKS, BENEATH, IN_ROOT = 1, 2, 4, 8, 16
strict = BENEATH | NO_SYMLINKS
beneath = BENEATH | NO_MAGIC
rooted = IN_ROOT | NO_MAGIC
counts = {"matrix": 0, "replacement": 0, "stress_ok": 0, "stress_rejected": 0}

def identity(fd):
    st = os.fstat(fd)
    return st.st_dev, st.st_ino

def opened(root, path, policy):
    fd = lib.open_policy(root, os.fsencode(path), policy)
    err = ctypes.get_errno() if fd < 0 else 0
    return fd, err

def check(root, path, policy, expected):
    fd, err = opened(root, path, policy)
    if isinstance(expected, int):
        if fd >= 0:
            os.close(fd)
        assert fd < 0 and err == expected, (path, policy, expected, fd, err)
    else:
        assert fd >= 0, (path, policy, err)
        try:
            assert identity(fd) == expected, (path, policy, identity(fd), expected)
        finally:
            os.close(fd)

for trial in range(16):
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        root, outside = base / "root", base / "outside"
        (root / "job").mkdir(parents=True)
        outside.mkdir()
        (root / "job" / "report").write_bytes(b"INSIDE\n")
        (outside / "report").write_bytes(b"OUTSIDE\n")
        safe = os.open(root / "job" / "report", os.O_RDONLY)
        unsafe = os.open(outside / "report", os.O_RDONLY)
        rootfd = os.open(root, os.O_PATH | os.O_DIRECTORY)
        try:
            good, bad = identity(safe), identity(unsafe)
            assert good != bad
            (root / "inside").symlink_to("job")
            (root / "escape").symlink_to("../outside")
            (root / "abs").symlink_to("/job")
            (root / "leaf").symlink_to("job/report")
            (root / "magic").symlink_to(f"/proc/self/fd/{unsafe}")
            os.link(outside / "report", root / "hard")
            os.mkfifo(root / "fifo")
            cases = [
                ("job/report", strict, good),
                ("job//./report", strict, good),
                ("job/../job/report", strict, good),
                ("../outside/report", beneath, errno.EXDEV),
                (str(outside / "report"), beneath, errno.EXDEV),
                ("inside/report", beneath, good),
                ("inside/report", strict, errno.ELOOP),
                ("leaf", beneath, good),
                ("leaf", strict, errno.ELOOP),
                ("escape/report", beneath, errno.EXDEV),
                ("escape/report", strict, errno.ELOOP),
                ("abs/report", beneath, errno.EXDEV),
                ("abs/report", rooted, good),
                ("/job/report", rooted, good),
                ("../job/report", rooted, good),
                ("../../job/report", rooted, good),
                ("missing", strict, errno.ENOENT),
                ("job/report/", strict, errno.ENOTDIR),
                ("", strict, errno.ENOENT),
                ("magic", NO_MAGIC, errno.ELOOP),
                ("magic", 0, bad),
                ("hard", strict, bad),
                ("job/report", BENEATH | IN_ROOT, errno.EINVAL),
                ("job/report", strict | NO_XDEV, good),
            ]
            for args in cases:
                check(rootfd, *args)
                counts["matrix"] += 1
            # Type policy remains necessary after successful containment.
            fd, err = opened(rootfd, "fifo", strict)
            assert fd >= 0, err
            import stat
            assert stat.S_ISFIFO(os.fstat(fd).st_mode)
            os.close(fd)
            counts["matrix"] += 1
            # Exercise an existing mount boundary without mounting anything.
            slash = os.open("/", os.O_PATH | os.O_DIRECTORY)
            try:
                check(slash, "proc/version", BENEATH | NO_XDEV, errno.EXDEV)
                counts["matrix"] += 1
            finally:
                os.close(slash)
            # Deterministic check-use gap, then compare retained identities.
            assert root.resolve() in (root / "job/report").resolve().parents
            (root / "job").rename(root / "saved")
            (root / "job").symlink_to("../outside")
            raw = os.open("job/report", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=rootfd)
            assert identity(raw) == bad
            os.close(raw)
            check(rootfd, "job/report", strict, errno.ELOOP)
            check(rootfd, "job/report", beneath, errno.EXDEV)
            assert identity(safe) == good
            counts["replacement"] += 1
            # Replacing the configured root name leaves rootfd attached to it.
            root.rename(base / "moved")
            root.mkdir()
            (root / "saved").mkdir()
            (root / "saved/report").write_bytes(b"REPLACEMENT\n")
            check(rootfd, "saved/report", strict, good)
            counts["replacement"] += 1
        finally:
            os.close(rootfd)
            os.close(safe)
            os.close(unsafe)

# Concurrent link replacement: success must identify the safe fixture object.
with TemporaryDirectory() as tmp:
    base = Path(tmp)
    root, outside = base / "root", base / "outside"
    (root / "safe").mkdir(parents=True)
    outside.mkdir()
    (root / "safe/report").write_bytes(b"INSIDE\n")
    (outside / "report").write_bytes(b"OUTSIDE\n")
    safe = os.open(root / "safe/report", os.O_RDONLY)
    rootfd = os.open(root, os.O_PATH | os.O_DIRECTORY)
    expected = identity(safe)
    (root / "job").symlink_to("safe")
    stop = threading.Event()
    started = threading.Event()
    failures = []
    swaps = [0]
    def mutate():
        try:
            while not stop.is_set():
                for target in ("safe", "../outside"):
                    (root / "next").symlink_to(target)
                    os.replace(root / "next", root / "job")
                    swaps[0] += 1
                    started.set()
        except BaseException as exc:
            failures.append(repr(exc))
            started.set()
    worker = threading.Thread(target=mutate)
    worker.start()
    try:
        assert started.wait(5)
        for _ in range(4000):
            fd, err = opened(rootfd, "job/report", beneath)
            if fd >= 0:
                try:
                    assert identity(fd) == expected
                    counts["stress_ok"] += 1
                finally:
                    os.close(fd)
            else:
                assert err in (errno.EXDEV, errno.EAGAIN, errno.ENOENT), err
                counts["stress_rejected"] += 1
    finally:
        stop.set()
        worker.join(timeout=5)
        os.close(rootfd)
        os.close(safe)
    assert not worker.is_alive() and not failures, failures
    assert swaps[0] > 0
    counts["swaps"] = swaps[0]
print(json.dumps({"passed": True, **counts}, sort_keys=True))
