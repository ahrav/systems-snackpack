#!/usr/bin/env python3
"""Run eight fresh privileged eBPF correctness processes without timing them."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def digest_path(path: Path) -> str:
    """Return a streaming SHA-256 digest for one file."""

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def required_match(pattern: str, text: str, label: str) -> re.Match[str]:
    """Return one required multiline match or reject the process receipt."""

    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        raise RuntimeError(f"{label}: missing output pattern {pattern!r}")
    return match


def parse_program(text: str, label: str) -> dict[str, int | str]:
    """Extract one program's dynamic identity and retained byte evidence."""

    info = required_match(
        rf"^{label}_info_initial=id:([0-9]+) type:1 "
        r"xlated_len:([0-9]+) jited_len:([0-9]+) "
        r"verified_insns:([0-9]+) run_cnt:[0-9]+ run_time_ns:[0-9]+$",
        text,
        f"{label} program info",
    )
    xlated = required_match(
        rf"^{label}_xlated_hex=([0-9a-f]+)$", text, f"{label} translated bytes"
    ).group(1)
    jited = required_match(
        rf"^{label}_jited_hex=([0-9a-f]+)$", text, f"{label} JIT bytes"
    ).group(1)
    return {
        "program_id": int(info.group(1)),
        "xlated_len": int(info.group(2)),
        "jited_len": int(info.group(3)),
        "verified_insns": int(info.group(4)),
        "xlated_hex": xlated,
        "jited_hex": jited,
    }


def validate_retained_blobs(
    kernel_output: Path,
    program: dict[str, int | str],
    label: str,
    exact_xlated_hex: str,
) -> dict[str, str]:
    """Bind program-info lengths and stdout hex to the kernel-returned blobs."""

    if program["verified_insns"] != 2:
        raise RuntimeError(f"{label}: verifier did not report exactly two instructions")
    if program["xlated_hex"] != exact_xlated_hex:
        raise RuntimeError(f"{label}: translated instructions changed")
    if program["jited_len"] == 0:
        raise RuntimeError(f"{label}: kernel returned no JIT bytes")

    digests: dict[str, str] = {}
    for kind in ("xlated", "jited"):
        blob = kernel_output / f"{label}.{kind}.bin"
        if not blob.is_file():
            raise RuntimeError(f"{label}: missing retained {kind} blob")
        expected_length = int(program[f"{kind}_len"])
        expected_bytes = bytes.fromhex(str(program[f"{kind}_hex"]))
        if blob.stat().st_size != expected_length or blob.read_bytes() != expected_bytes:
            raise RuntimeError(f"{label}: {kind} blob differs from program-info output")
        digests[kind] = digest_path(blob)
    return digests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sudo", type=Path, required=True)
    parser.add_argument("--chown", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=8)
    arguments = parser.parse_args()

    binary = arguments.binary.resolve(strict=True)
    contract_path = arguments.contract.resolve(strict=True)
    output = arguments.output.resolve()
    sudo = arguments.sudo.resolve(strict=True)
    chown = arguments.chown.resolve(strict=True)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    required_runs = contract["privileged"]["fresh_process_runs"]
    if arguments.runs != 8 or arguments.runs != required_runs:
        parser.error("this contract requires exactly eight fresh privileged processes")
    if output.exists():
        parser.error(f"output already exists: {output}")
    if not binary.is_file() or not os.access(binary, os.X_OK):
        parser.error(f"binary is not executable: {binary}")
    if not sudo.is_file() or not os.access(sudo, os.X_OK):
        parser.error(f"sudo is not executable: {sudo}")
    if not chown.is_file() or not os.access(chown, os.X_OK):
        parser.error(f"chown is not executable: {chown}")

    output.mkdir(mode=0o700)
    raw = output / "raw"
    raw.mkdir(mode=0o700)
    retained_binary = output / "ebpf-socket-filter"
    retained_contract = output / "expected_patterns.json"
    shutil.copy2(binary, retained_binary)
    shutil.copy2(contract_path, retained_contract)
    retained_binary.chmod(0o500)
    retained_contract.chmod(0o400)
    binary_digest = digest_path(retained_binary)
    contract_digest = digest_path(retained_contract)
    configuration = {
        "binary": retained_binary.name,
        "binary_sha256": binary_digest,
        "contract": retained_contract.name,
        "contract_sha256": contract_digest,
        "fresh_privileged_processes": arguments.runs,
        "measurement_kind": "correctness and code generation only",
        "privileged_invocation": "sudo -n BINARY OUTPUT_DIRECTORY",
        "retry_policy": "none",
        "timing_reported": False,
        "timeout_observation_is_latency": False,
    }
    (output / "config.json").write_text(
        json.dumps(configuration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    owner = f"{os.getuid()}:{os.getgid()}"
    rows: list[dict[str, str]] = []
    exact_xlated = contract["privileged"]["exact_xlated_hex"]
    clean_environment = {
        **os.environ,
        "LANG": "C",
        "LC_ALL": "C",
    }

    for sequence in range(1, arguments.runs + 1):
        launch_digest = digest_path(retained_binary)
        if launch_digest != binary_digest:
            raise RuntimeError(f"probe changed before process {sequence}")

        kernel_output = raw / f"run-{sequence:02d}-kernel-bytes"
        completed = subprocess.run(
            [str(sudo), "-n", "--", str(retained_binary), str(kernel_output)],
            check=False,
            capture_output=True,
            env=clean_environment,
            timeout=120,
        )
        stdout_path = raw / f"run-{sequence:02d}.stdout"
        stderr_path = raw / f"run-{sequence:02d}.stderr"
        stdout_path.write_bytes(completed.stdout)
        stderr_path.write_bytes(completed.stderr)
        if completed.returncode != contract["privileged"]["return_code"]:
            raise RuntimeError(
                f"privileged process {sequence} returned {completed.returncode}"
            )
        if completed.stderr:
            raise RuntimeError(f"privileged process {sequence} wrote to stderr")

        # The exact tested C probe creates 0600 blobs while running as root.
        # This separate direct sudo command only transfers ownership of that
        # run's evidence back to the invoking user; it does not execute a
        # shell or alter the probe's result.
        ownership = subprocess.run(
            [str(sudo), "-n", "--", str(chown), "-R", owner, str(kernel_output)],
            check=False,
            capture_output=True,
            env=clean_environment,
            timeout=30,
        )
        if ownership.returncode != 0 or ownership.stdout or ownership.stderr:
            raise RuntimeError(f"could not transfer evidence for process {sequence}")

        text = completed.stdout.decode("utf-8", errors="strict")
        pid = int(
            required_match(
                r"^probe_pid=([0-9]+) uid=0 euid=0$",
                text,
                f"privileged process {sequence}",
            ).group(1)
        )
        accept = parse_program(text, "accept")
        drop = parse_program(text, "drop")
        accept_digests = validate_retained_blobs(
            kernel_output, accept, "accept", exact_xlated["accept"]
        )
        drop_digests = validate_retained_blobs(
            kernel_output, drop, "drop", exact_xlated["drop"]
        )
        rows.append(
            {
                "sequence": str(sequence),
                "probe_pid": str(pid),
                "binary_sha256_at_launch": launch_digest,
                "return_code": str(completed.returncode),
                "stdout_sha256": digest_path(stdout_path),
                "stderr_sha256": digest_path(stderr_path),
                "accept_program_id": str(accept["program_id"]),
                "drop_program_id": str(drop["program_id"]),
                "accept_xlated_sha256": accept_digests["xlated"],
                "drop_xlated_sha256": drop_digests["xlated"],
                "accept_jited_bytes": str(accept["jited_len"]),
                "drop_jited_bytes": str(drop["jited_len"]),
                "accept_jited_sha256": accept_digests["jited"],
                "drop_jited_sha256": drop_digests["jited"],
            }
        )

    if digest_path(retained_binary) != binary_digest:
        raise RuntimeError("probe changed during the process series")
    with (output / "runs.tsv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
