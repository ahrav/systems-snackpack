"""Two physical histories with identical observations at controller A."""
import sqlite3


def history(a_commits):
    db = sqlite3.connect(":memory:")
    db.execute("create table manifest(release integer)")
    db.execute("insert into manifest values (10)")

    def publish(expected, release):
        return db.execute(
            "update manifest set release=? where release=?",
            (release, expected),
        ).rowcount

    if a_commits:
        assert publish(10, 11) == 1  # Drop A's reply.
    current, = db.execute("select release from manifest").fetchone()
    assert publish(current, 12) == 1
    retry = publish(10, 11)
    observed, = db.execute("select release from manifest").fetchone()
    db.close()
    return observed, retry


if __name__ == "__main__":
    for committed in (False, True):
        observed, retry = history(committed)
        assert (observed, retry) == (12, 0)
        print(committed, observed, retry)
