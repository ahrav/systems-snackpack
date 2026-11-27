"""Compare every five-event trace to SQL constraints and guarded updates."""
import itertools
import sqlite3
import subprocess
from pathlib import Path

TOPIC = Path(__file__).resolve().parent


def oracle(db, history):
    db.execute("delete from manifest")
    observations = []
    for event in history:
        if event in "ab":
            tag = {"a": 1, "b": 2}[event]
            rows = db.execute(
                "insert or ignore into manifest values (1, ?)", (tag,)
            ).rowcount
            status = 200 if rows else 412
        elif event == "d":
            db.execute("delete from manifest")
            status = 204
        else:
            old, new = {"x": (1, 2), "y": (2, 1)}[event]
            rows = db.execute(
                "update manifest set tag=? where tag=?", (new, old)
            ).rowcount
            status = 200 if rows else 412
            if not db.execute("select count(*) from manifest").fetchone()[0]:
                status = 404
        current = db.execute("select coalesce(max(tag), 0) from manifest").fetchone()[0]
        observations.append(f"{status}/{current}")
    return " ".join(observations)


def main():
    histories = ["".join(trace) for trace in itertools.product("abxyd", repeat=5)]
    result = subprocess.run(
        ["cargo", "run", "--locked", "--offline", "--quiet", "-p", "topic121-conditional-writes"],
        cwd=TOPIC, input="\n".join(histories) + "\n", check=True,
        text=True, stdout=subprocess.PIPE,
    )
    actual = result.stdout.splitlines()
    assert len(actual) == len(histories)
    db = sqlite3.connect(":memory:")
    db.execute("create table manifest(id integer primary key, tag integer not null)")
    for history, output in zip(histories, actual):
        expected = oracle(db, history)
        if output != expected:
            raise AssertionError((history, expected, output))
    db.close()
    print(f"{len(histories)} histories, {5 * len(histories)} observations matched SQLite")


if __name__ == "__main__":
    main()
