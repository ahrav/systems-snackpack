"""Exit a writer/replayer and reconstruct a missing file in a temporary directory."""
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

OLD = bytes.fromhex("3c5569")
INTENDED = {"partial": bytes.fromhex("a655f3"), "full": bytes.fromhex("a611b7")}
CHILD_EXIT = 73
SCRIPT = Path(__file__).resolve()


def save(path, data):
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def sync_dir(root):
    fd = os.open(root, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def member(root, i):
    return root / str(i)


def apply(root, changes, mask):
    for i, value in changes:
        path = member(root, i)
        if mask & (1 << i) and path.exists():
            save(path, bytes([value]))


def writer(root, kind, phase, cut):
    if phase == "before":
        os._exit(CHILD_EXIT)
    if kind == "full":
        changes = [(0, 0xa6), (1, 0x11), (2, 0xa6 ^ 0x11)]
    else:
        old_a = member(root, 0).read_bytes()[0]
        old_p = member(root, 2).read_bytes()[0]
        changes = [(0, 0xa6), (2, old_a ^ old_p ^ 0xa6)]
    if phase != "plain":
        save(root / "staging", json.dumps(changes).encode())
        os.replace(root / "staging", root / "redo")
        sync_dir(root)
    apply(root, changes, cut)
    if phase == "retired":
        (root / "redo").unlink()
        sync_dir(root)
    os._exit(CHILD_EXIT)


def replay(root, cut):
    log = root / "redo"
    if log.exists():
        apply(root, json.loads(log.read_bytes()), cut)


def child(*args):
    result = subprocess.run([sys.executable, SCRIPT, *map(str, args)], check=False)
    if result.returncode != CHILD_EXIT:
        raise RuntimeError(f"child exited {result.returncode}")


def check():
    checked = wrong = 0
    for kind, lost in itertools.product(INTENDED, range(3)):
        masks = (0, 1, 4, 5) if kind == "partial" else range(8)
        histories = [("before", 0), ("retired", 7)]
        histories.extend(itertools.product(("logged", "plain"), masks))
        for phase, cut in histories:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for i, value in enumerate(OLD):
                    save(member(root, i), bytes([value]))
                sync_dir(root)
                child("write", root, kind, phase, cut)
                member(root, lost).unlink()
                # Kill recovery after its first surviving changed member can persist.
                first = next(i for i in range(3) if i != lost and (kind == "full" or i != 1))
                child("replay", root, 1 << first)
                replay(root, 7)
                survivors = [member(root, i).read_bytes()[0] for i in range(3) if i != lost]
                recovered = survivors[0] ^ survivors[1]
                if phase == "plain":
                    if kind == "partial" and lost == 1 and recovered != OLD[1]:
                        wrong += 1
                else:
                    expected = OLD if phase == "before" else INTENDED[kind]
                    observed = [recovered if i == lost else member(root, i).read_bytes()[0]
                                for i in range(3)]
                    assert bytes(observed) == expected, (kind, lost, phase, cut, observed)
                checked += 1
    assert wrong == 2
    print(f"{checked} file histories; {wrong} wrong untouched rebuilds without the log")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        check()
    elif sys.argv[1] == "write":
        writer(Path(sys.argv[2]), sys.argv[3], sys.argv[4], int(sys.argv[5]))
    elif sys.argv[1] == "replay":
        replay(Path(sys.argv[2]), int(sys.argv[3]))
        os._exit(CHILD_EXIT)
    else:
        raise ValueError("unknown mode")
