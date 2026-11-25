"""Two autocommit connections to a disposable database. Python 3.9 or later."""

import hashlib
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import NamedTuple


def digest(data):
    return hashlib.sha256(data).digest()


class Repair(NamedTuple):
    incarnation: int
    generation: int
    candidate: bytes


SCHEMA = """CREATE TABLE block (
    id INTEGER PRIMARY KEY, incarnation INTEGER NOT NULL, gen INTEGER NOT NULL,
    want BLOB, target BLOB NOT NULL, mirror BLOB NOT NULL)"""


def inspect(db):
    row = db.execute("SELECT incarnation, gen, want, target, mirror FROM block WHERE id=1").fetchone()
    if row is None:
        return None
    inc, gen, want, target, candidate = row
    if want is None or digest(target) == want or digest(candidate) != want:
        return None
    return Repair(inc, gen, candidate)


def install(db, plan):
    return db.execute(
        "UPDATE block SET target=? WHERE id=1 AND incarnation=? AND gen=?",
        (plan.candidate, plan.incarnation, plan.generation),
    ).rowcount


def run(path, guard):
    with closing(sqlite3.connect(path, isolation_level=None)) as scrub, closing(
        sqlite3.connect(path, isolation_level=None)
    ) as writer:
        scrub.execute(SCHEMA)
        scrub.execute("INSERT INTO block VALUES (1, 1, 7, ?, ?, ?)",
                      (digest(b"BLUE"), b"FAIL", b"BLUE"))
        plan = inspect(scrub)
        writer.execute("UPDATE block SET gen=8, want=?, target=?, mirror=? WHERE id=1",
                       (digest(b"GOLD"), b"GOLD", b"GOLD"))
        if guard:
            changed = install(scrub, plan)
        else:
            changed = scrub.execute("UPDATE block SET target=? WHERE id=1", (plan.candidate,)).rowcount

        gen, target, want = scrub.execute("SELECT gen, target, want FROM block").fetchone()
        return changed, gen, target.decode(), digest(target) == want


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        for mode in ("unconditional", "conditional"):
            result = run(Path(directory) / mode, mode == "conditional")
            print(mode, *result)
