#!/usr/bin/env python3
"""Run eight fresh correctness processes and retain every receipt."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


RUNS = 8
TIMEOUT_SECONDS = 10


def sha256(data: bytes) -> str:
    """Return the hexadecimal SHA-256 digest for ``data``."""

    return hashlib.sha256(data).hexdigest()


def write_bytes(path: Path, data: bytes) -> None:
    """Write one receipt and make its bytes durable before returning."""

    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def append_json_line(path: Path, value: dict[str, object]) -> None:
    """Append one flushed JSON record."""

    with path.open("a", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main() -> int:
    """Run the retained process set."""

    if len(sys.argv) != 3:
        print("usage: run_processes.py BINARY OUTPUT", file=sys.stderr)
        return 2

    binary = Path(sys.argv[1]).resolve(strict=True)
    output = Path(sys.argv[2]).resolve()
    if not binary.is_file():
        print(f"binary is not a file: {binary}", file=sys.stderr)
        return 2
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"output already exists: {output}", file=sys.stderr)
        return 2

    expected = (Path(__file__).resolve().parent / "expected.txt").read_bytes()
    binary_bytes = binary.read_bytes()
    binary_digest = sha256(binary_bytes)
    private_binary = output / "binary"
    shutil.copyfile(binary, private_binary)
    private_binary.chmod(0o755)
    write_bytes(output / "binary.sha256", f"{binary_digest}  binary\n".encode())
    write_bytes(output / "expected.sha256", f"{sha256(expected)}  expected.txt\n".encode())

    receipts_path = output / "receipts.jsonl"
    failures = 0
    for run_number in range(1, RUNS + 1):
        run_name = f"run-{run_number:02d}"
        timed_out = False
        try:
            completed = subprocess.run(
                [str(private_binary), "--self-check"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=TIMEOUT_SECONDS,
                env={"PATH": os.environ.get("PATH", "")},
            )
            stdout = completed.stdout
            stderr = completed.stderr
            exit_code = completed.returncode
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or b""
            stderr = error.stderr or b""
            exit_code = 124
            timed_out = True

        write_bytes(output / f"{run_name}.stdout", stdout)
        write_bytes(output / f"{run_name}.stderr", stderr)
        write_bytes(output / f"{run_name}.exit", f"{exit_code}\n".encode())
        passed = exit_code == 0 and not timed_out and stdout == expected and stderr == b""
        failures += int(not passed)
        append_json_line(
            receipts_path,
            {
                "exit_code": exit_code,
                "passed": passed,
                "run": run_number,
                "stderr_bytes": len(stderr),
                "stderr_sha256": sha256(stderr),
                "stdout_bytes": len(stdout),
                "stdout_sha256": sha256(stdout),
                "timed_out": timed_out,
            },
        )

    summary = {
        "binary_sha256": binary_digest,
        "expected_sha256": sha256(expected),
        "failed": failures,
        "passed": RUNS - failures,
        "runs": RUNS,
        "timeout_seconds": TIMEOUT_SECONDS,
    }
    write_bytes(
        output / "summary.json",
        (json.dumps(summary, sort_keys=True, indent=2) + "\n").encode(),
    )
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
