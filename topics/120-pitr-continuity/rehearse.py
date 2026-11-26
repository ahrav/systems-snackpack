"""Rehearse a lost WAL segment using private, temporary PostgreSQL clusters.

Run with PostgreSQL 16 binaries (including pg_verifybackup) on PATH.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time


def rehearse(root):
    archive = root / "archive"
    archive.mkdir()
    live = root / "live"
    env = dict(os.environ, PGHOST=str(root), PGPORT="5432", PGUSER="pitr",
               PGDATABASE="postgres", LC_ALL="C")
    servers = []

    def run(*args, check=True):
        result = subprocess.run(args, env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        if check and result.returncode:
            raise RuntimeError(f"{args[0]} failed ({result.returncode})\n{result.stdout}")
        return result

    def sql(query):
        return run("psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-c", query).stdout.strip()

    def config(data, settings):
        with (data / "postgresql.conf").open("a") as f:
            f.write("\n" + settings + "\n")

    def start(data, check=True):
        servers.append(data)
        return run("pg_ctl", "-w", "-t", "30", "-D", data, "-l", data / "drill.log",
                   "start", check=check)

    def stop(data):
        run("pg_ctl", "-w", "-D", data, "stop", "-m", "fast")
        servers.remove(data)

    def backup(name):
        dest = root / name
        run("pg_basebackup", "-D", dest, "-X", "stream", "-c", "fast")
        print(name, run("pg_verifybackup", dest).stdout.strip(), flush=True)
        return dest

    def restore(name, base, mark, expected, missing=None):
        data = root / name
        shutil.copytree(base, data)
        config(data, f"""archive_mode = off
hot_standby = off
restore_command = 'cp "{archive}/%f" "%p"'
recovery_target_name = '{mark}'
recovery_target_timeline = 'current'
recovery_target_action = 'promote'""")
        (data / "recovery.signal").touch()
        boot = start(data, check=False)
        log = (data / "drill.log").read_text()
        if missing:
            if boot.returncode == 0 or missing not in log or "recovery ended before configured recovery target was reached" not in log:
                raise RuntimeError(log)
            print(name, "failed before target, missing", missing)
        else:
            if boot.returncode or f'recovery stopping at restore point "{mark}"' not in log:
                raise RuntimeError(log)
            rows = sql("SELECT id FROM orders ORDER BY id")
            if rows != expected:
                raise RuntimeError(f"{name}: expected {expected!r}, got {rows!r}")
            print(name, mark, "orders =", rows)
            stop(data)

    try:
        print(run("postgres", "--version").stdout.strip(), flush=True)
        run("initdb", "-D", live, "-U", "pitr", "-A", "trust", "--no-locale",
            "--wal-segsize=1")
        config(live, f"""listen_addresses = ''
unix_socket_directories = '{root}'
archive_mode = on
archive_command = 'cp "%p" "{archive}/%f"'
logging_collector = off""")
        start(live)
        sql("CREATE TABLE orders(id int PRIMARY KEY)")
        a = backup("A")
        sql("SELECT pg_switch_wal()")
        sql("INSERT INTO orders VALUES (41)")
        gap = sql("SELECT pg_walfile_name(pg_current_wal_insert_lsn())")
        if not re.fullmatch("[0-9A-F]{24}", gap):
            raise RuntimeError(gap)
        sql("SELECT pg_switch_wal()")
        sql("INSERT INTO orders VALUES (42)")
        sql("SELECT pg_create_restore_point('before_delete')")
        sql("DELETE FROM orders WHERE id = 42")
        b = backup("B")
        sql("INSERT INTO orders VALUES (43)")
        sql("SELECT pg_create_restore_point('after_restock')")
        sql("INSERT INTO orders VALUES (99)")
        last = sql("SELECT pg_walfile_name(pg_current_wal_insert_lsn())")
        sql("SELECT pg_switch_wal()")
        for _ in range(200):
            if (live / "pg_wal" / "archive_status" / (last + ".done")).exists():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("final segment did not finish archiving")
        stop(live)
        restore("intact_A", a, "before_delete", "41\n42")
        (archive / gap).rename(root / gap)
        restore("broken_A", a, "before_delete", None, missing=gap)
        restore("later_B", b, "after_restock", "41\n43")
    finally:
        for data in servers:
            if (data / "postmaster.pid").exists():
                run("pg_ctl", "-D", data, "-w", "-m", "immediate", "stop")


if __name__ == "__main__":
    # Short path keeps the Unix socket name within the platform limit.
    with tempfile.TemporaryDirectory(prefix="pitr120-", dir="/tmp") as tmp:
        rehearse(Path(tmp))
