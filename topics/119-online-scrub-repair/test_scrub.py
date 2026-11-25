"""A chronological write-history oracle for the two-connection repair example."""

import itertools
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scrub_demo import SCHEMA, digest, inspect, install

BLUE, GOLD, FAIL = b"BLUE", b"GOLD", b"FAIL"
INITIAL = {
    "damaged": (BLUE, FAIL, BLUE),
    "healthy": (BLUE, BLUE, BLUE),
    "bad_mirror": (BLUE, FAIL, FAIL),
    "no_authority": (None, FAIL, BLUE),
}
ACTIONS = ("write_gold", "write_blue", "recreate", "delete", "damage_mirror", "damage_target")


def reset(db, initial):
    want, target, mirror = INITIAL[initial]
    db.execute("DELETE FROM block")
    db.execute("INSERT INTO block VALUES (1, 1, 7, ?, ?, ?)",
               (digest(want) if want else None, target, mirror))


def foreground(db, action, serial):
    if action == "delete":
        db.execute("DELETE FROM block WHERE id=1")
    elif action == "recreate":
        db.execute("INSERT OR REPLACE INTO block VALUES (1, ?, 7, ?, ?, ?)",
                   (2 + serial, digest(GOLD), GOLD, GOLD))
    elif action.startswith("write_"):
        value = GOLD if action == "write_gold" else BLUE
        db.execute("UPDATE block SET gen=gen+1, want=?, target=?, mirror=? WHERE id=1",
                   (digest(value), value, value))
    elif action == "damage_mirror":
        db.execute("UPDATE block SET mirror=? WHERE id=1", (FAIL,))
    elif action == "damage_target":
        db.execute("UPDATE block SET target=? WHERE id=1", (FAIL,))


def expected_trace(initial, sequence):
    # This oracle takes only the input events. It keeps the index of the last
    # logical mutation. It has no database, digest, incarnation or generation.
    truth, target, mirror = INITIAL[initial]
    live = True
    revision = 0
    observation = None
    trace = []
    for index, action in enumerate(sequence, start=1):
        changed = 0
        if action == "observe":
            if live and truth is not None and target != truth and mirror == truth:
                observation = (revision, mirror)
        elif action == "install":
            if live and observation and revision == observation[0]:
                target = observation[1]
                changed = 1
        elif action == "recreate" or (live and action.startswith("write_")):
            live = True
            truth = BLUE if action == "write_blue" else GOLD
            target = mirror = truth
            revision = index
        elif action == "delete":
            live = False
            revision = index
        elif live and action == "damage_target":
            target = FAIL
        elif live and action == "damage_mirror":
            mirror = FAIL
        trace.append((target if live else None, changed))
    return trace


def observed_trace(scrub, writer, sequence):
    plan = None
    trace = []
    for index, action in enumerate(sequence):
        changed = 0
        if action == "observe":
            plan = inspect(scrub)
        elif action == "install":
            if plan:
                changed = install(scrub, plan)
        else:
            foreground(writer, action, index)
        row = writer.execute("SELECT target FROM block WHERE id=1").fetchone()
        trace.append((row[0] if row else None, changed))
    return trace


class RepairTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "blocks.db"
        self.scrub = sqlite3.connect(path, isolation_level=None, timeout=0)
        self.writer = sqlite3.connect(path, isolation_level=None, timeout=0)
        self.addCleanup(self.scrub.close)
        self.addCleanup(self.writer.close)
        self.scrub.execute("PRAGMA journal_mode=WAL").fetchone()
        self.writer.execute("PRAGMA synchronous=NORMAL")
        self.scrub.execute("PRAGMA synchronous=NORMAL")
        self.scrub.execute(SCHEMA)

    def test_histories(self):
        count = 0
        for initial, pair, scrub_positions in itertools.product(
            INITIAL, itertools.product(ACTIONS, repeat=2), itertools.combinations(range(4), 2)
        ):
            fg = iter(pair)
            scrub_steps = iter(("observe", "install"))
            sequence = tuple(next(scrub_steps) if i in scrub_positions else next(fg) for i in range(4))
            with self.subTest(initial=initial, sequence=sequence):
                reset(self.scrub, initial)
                self.assertEqual(observed_trace(self.scrub, self.writer, sequence),
                                 expected_trace(initial, sequence))
            count += 1
        self.assertEqual(count, 864)
        print(f"{count} histories, {count * 4} post-event observations")

    def test_separate_check_loses_the_committed_write(self):
        reset(self.scrub, "damaged")
        plan = inspect(self.scrub)
        ok = self.scrub.execute("SELECT 1 FROM block WHERE incarnation=? AND gen=?",
                                (plan.incarnation, plan.generation)).fetchone()
        self.assertEqual(ok, (1,))
        foreground(self.writer, "write_gold", 0)
        self.scrub.execute("UPDATE block SET target=? WHERE id=1", (plan.candidate,))
        self.assertEqual(self.writer.execute("SELECT gen, target, want FROM block").fetchone(),
                         (8, BLUE, digest(GOLD)))

    def test_generation_only_loses_recreated_object(self):
        reset(self.scrub, "damaged")
        plan = inspect(self.scrub)
        foreground(self.writer, "recreate", 0)
        self.assertEqual(install(self.scrub, plan), 0)
        count = self.scrub.execute("UPDATE block SET target=? WHERE id=1 AND gen=?",
                                   (plan.candidate, plan.generation)).rowcount
        self.assertEqual(count, 1)
        self.assertEqual(self.writer.execute("SELECT gen, target, want FROM block").fetchone(),
                         (7, BLUE, digest(GOLD)))

    def test_writer_lock_covers_the_read_and_repair(self):
        reset(self.scrub, "damaged")
        self.scrub.execute("BEGIN IMMEDIATE")
        plan = inspect(self.scrub)
        with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
            foreground(self.writer, "write_gold", 0)
        self.assertEqual(install(self.scrub, plan), 1)
        self.scrub.commit()
        foreground(self.writer, "write_gold", 0)
        self.assertEqual(self.scrub.execute("SELECT gen, target FROM block").fetchone(), (8, GOLD))


if __name__ == "__main__":
    unittest.main()
