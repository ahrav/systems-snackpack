#!/usr/bin/env python3
"""Validate Topic 40 permission, verifier, hook, and JIT evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()

# Digests of the complete expected_patterns.json contracts this validator
# accepts. The schema checks in validate_contract cannot see a weakened
# required_regex or forbidden_regex list; pinning the whole contract can.
EXPECTED_CONTRACT_SHA256S = {
    # Original measured probe retained by the checked-in receipt bundles.
    "b5f41a472a21a1f80315e3302d93384d363f5aff71c850c875f709de71d4573a",
    # Probe with directory-relative, no-follow receipt file creation.
    "e13ab9491aa6e2c3aa3a975767068ee5ed0ab8224bc517cab30ae62613725f6e",
}

# The one target label that names a specific host rather than a role; its
# receipt must record that exact hostname.
ARM_HOST = "dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com"

DISASSEMBLY_ROW = re.compile(
    r"^\s*([0-9a-f]+):\t([0-9a-f][0-9a-f ]*?)\s*\t", re.MULTILINE
)


def digest_path(path: Path) -> str:
    """Return a streaming SHA-256 digest for one file."""

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def require_patterns(text: str, contract: dict[str, object], label: str) -> None:
    """Enforce one output's required and forbidden semantic patterns."""

    for pattern in contract["required_regex"]:
        if re.search(str(pattern), text, re.MULTILINE) is None:
            raise ValueError(f"{label}: missing required pattern {pattern!r}")
    for pattern in contract["forbidden_regex"]:
        if re.search(str(pattern), text, re.MULTILINE) is not None:
            raise ValueError(f"{label}: matched forbidden pattern {pattern!r}")


def extract(text: str, pattern: str, label: str) -> re.Match[str]:
    """Extract a required dynamic field from a process transcript."""

    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        raise ValueError(f"{label}: missing field {pattern!r}")
    return match


def parse_program(text: str, label: str) -> dict[str, int | str]:
    """Parse one loaded program's ID, lengths, and returned instruction bytes."""

    info = extract(
        text,
        rf"^{label}_info_initial=id:([0-9]+) type:1 "
        r"xlated_len:([0-9]+) jited_len:([0-9]+) "
        r"verified_insns:([0-9]+) run_cnt:[0-9]+ run_time_ns:[0-9]+$",
        f"{label} program info",
    )
    return {
        "program_id": int(info.group(1)),
        "xlated_len": int(info.group(2)),
        "jited_len": int(info.group(3)),
        "verified_insns": int(info.group(4)),
        "xlated_hex": extract(
            text,
            rf"^{label}_xlated_hex=([0-9a-f]+)$",
            f"{label} translated bytes",
        ).group(1),
        "jited_hex": extract(
            text,
            rf"^{label}_jited_hex=([0-9a-f]+)$",
            f"{label} JIT bytes",
        ).group(1),
    }


def disassembled_bytes(text: str, architecture: str, label: str) -> bytes:
    """Rebuild the JIT bytes represented by an objdump transcript."""

    rows = DISASSEMBLY_ROW.findall(text)
    if not rows:
        raise ValueError(f"{label}: disassembly has no instruction rows")
    decoded = bytearray()
    for offset_text, column in rows:
        offset = int(offset_text, 16)
        if offset != len(decoded):
            raise ValueError(f"{label}: disassembly is not contiguous at 0x{offset:x}")
        if architecture in {"aarch64", "arm64"}:
            if re.fullmatch(r"[0-9a-f]{8}", column) is None:
                raise ValueError(
                    f"{label}: invalid AArch64 instruction word {column!r}"
                )
            decoded.extend(bytes.fromhex(column)[::-1])
        elif architecture == "x86_64":
            if re.fullmatch(r"[0-9a-f]{2}( [0-9a-f]{2})*", column) is None:
                raise ValueError(f"{label}: invalid x86-64 byte column {column!r}")
            decoded.extend(bytes.fromhex(column))
        else:
            raise ValueError(f"{label}: unsupported JIT architecture {architecture!r}")
    return bytes(decoded)


def validate_contract(contract: dict[str, object]) -> None:
    """Refuse a weakened or unknown semantic contract schema."""

    if set(contract) != {
        "schema",
        "boundary",
        "source_sha256",
        "ordinary",
        "privileged",
    }:
        raise ValueError("contract top-level keys changed")
    if (
        contract["schema"] != "topic40-ebpf-receipt-contract-v1"
        or contract["boundary"]
        != "correctness and generated-code inspection only; no timing claim"
        or not re.fullmatch(r"[0-9a-f]{64}", str(contract["source_sha256"]))
    ):
        raise ValueError("contract identity or boundary changed")
    ordinary = contract["ordinary"]
    privileged = contract["privileged"]
    if not isinstance(ordinary, dict) or set(ordinary) != {
        "return_code",
        "required_regex",
        "forbidden_regex",
    }:
        raise ValueError("ordinary contract schema changed")
    if not isinstance(privileged, dict) or set(privileged) != {
        "fresh_process_runs",
        "return_code",
        "required_regex",
        "forbidden_regex",
        "exact_xlated_hex",
        "required_blob_kinds",
    }:
        raise ValueError("privileged contract schema changed")
    if (
        ordinary["return_code"] != 77
        or privileged["fresh_process_runs"] != 8
        or privileged["return_code"] != 0
        or privileged["required_blob_kinds"] != ["xlated", "jited"]
        or privileged["exact_xlated_hex"]
        != {
            "accept": "b7000000ffffffff9500000000000000",
            "drop": "b7000000000000009500000000000000",
        }
    ):
        raise ValueError("receipt acceptance values changed")


def validate_ordinary(root: Path, contract: dict[str, object]) -> None:
    """Require the unprivileged policy gate to precede verifier diagnostics."""

    ordinary = root / "ordinary"
    stdout = (ordinary / "run.stdout").read_text(encoding="utf-8")
    stderr = ordinary / "run.stderr"
    if int((ordinary / "return-code.txt").read_text(encoding="utf-8")) != 77:
        raise ValueError("ordinary process did not return the permission sentinel 77")
    if stderr.read_bytes() != b"":
        raise ValueError("ordinary process wrote to stderr")
    require_patterns(stdout, contract["ordinary"], "ordinary process")
    kernel_bytes = ordinary / "kernel-bytes"
    if not kernel_bytes.is_dir() or list(kernel_bytes.iterdir()):
        raise ValueError("ordinary process unexpectedly returned program bytes")


def validate_program_blobs(
    blob_root: Path,
    program: dict[str, int | str],
    label: str,
    exact_xlated_hex: str,
) -> dict[str, str]:
    """Bind each retained file to the lengths and hex returned by the kernel."""

    if (
        program["verified_insns"] != 2
        or program["xlated_len"] != 16
        or program["jited_len"] == 0
        or program["xlated_hex"] != exact_xlated_hex
    ):
        raise ValueError(f"{label}: program-info contract changed")
    result: dict[str, str] = {}
    for kind in ("xlated", "jited"):
        blob = blob_root / f"{label}.{kind}.bin"
        expected = bytes.fromhex(str(program[f"{kind}_hex"]))
        if not blob.is_file() or blob.read_bytes() != expected:
            raise ValueError(f"{label}: retained {kind} bytes differ from stdout")
        if blob.stat().st_size != int(program[f"{kind}_len"]):
            raise ValueError(f"{label}: retained {kind} length differs from program info")
        result[kind] = digest_path(blob)
    return result


def validate_privileged(
    root: Path, contract: dict[str, object], architecture: str
) -> None:
    """Require eight fresh successful privileged program lifecycles."""

    process_root = root / "processes"
    config = json.loads((process_root / "config.json").read_text(encoding="utf-8"))
    expected_config_keys = {
        "binary",
        "binary_sha256",
        "contract",
        "contract_sha256",
        "fresh_privileged_processes",
        "measurement_kind",
        "privileged_invocation",
        "retry_policy",
        "timing_reported",
        "timeout_observation_is_latency",
    }
    if set(config) != expected_config_keys or any(
        (
            config["binary"] != "ebpf-socket-filter",
            config["contract"] != "expected_patterns.json",
            config["fresh_privileged_processes"] != 8,
            config["measurement_kind"] != "correctness and code generation only",
            config["privileged_invocation"] != "sudo -n BINARY OUTPUT_DIRECTORY",
            config["retry_policy"] != "none",
            config["timing_reported"] is not False,
            config["timeout_observation_is_latency"] is not False,
        )
    ):
        raise ValueError("privileged process configuration changed")

    retained_binary = process_root / config["binary"]
    retained_contract = process_root / config["contract"]
    if digest_path(retained_binary) != config["binary_sha256"]:
        raise ValueError("retained executable digest mismatch")
    if digest_path(retained_contract) != config["contract_sha256"]:
        raise ValueError("retained contract digest mismatch")
    if json.loads(retained_contract.read_text(encoding="utf-8")) != contract:
        raise ValueError("retained contract differs from validator input")
    artifact_binary = root / "artifacts" / "ebpf-socket-filter"
    if digest_path(artifact_binary) != config["binary_sha256"]:
        raise ValueError("artifact and executed binary differ")

    with (process_root / "runs.tsv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = [
            "sequence",
            "probe_pid",
            "binary_sha256_at_launch",
            "return_code",
            "stdout_sha256",
            "stderr_sha256",
            "accept_program_id",
            "drop_program_id",
            "accept_xlated_sha256",
            "drop_xlated_sha256",
            "accept_jited_bytes",
            "drop_jited_bytes",
            "accept_jited_sha256",
            "drop_jited_sha256",
        ]
        if reader.fieldnames != fields:
            raise ValueError("privileged process receipt schema changed")
        rows = list(reader)
    if len(rows) != 8 or [row["sequence"] for row in rows] != [
        str(value) for value in range(1, 9)
    ]:
        raise ValueError("expected exactly process sequences 1 through 8")
    probe_pids = [row["probe_pid"] for row in rows]
    if len(set(probe_pids)) != len(rows):
        raise ValueError("privileged receipts repeat a probe PID")
    program_ids = [
        row[column]
        for row in rows
        for column in ("accept_program_id", "drop_program_id")
    ]
    if len(set(program_ids)) != 2 * len(rows):
        raise ValueError("privileged receipts repeat a BPF program ID")

    privileged = contract["privileged"]
    exact_xlated = privileged["exact_xlated_hex"]
    for row in rows:
        sequence = int(row["sequence"])
        stdout_path = process_root / "raw" / f"run-{sequence:02d}.stdout"
        stderr_path = process_root / "raw" / f"run-{sequence:02d}.stderr"
        stdout = stdout_path.read_text(encoding="utf-8")
        require_patterns(stdout, privileged, f"privileged process {sequence}")
        if stderr_path.read_bytes() != b"" or row["stderr_sha256"] != EMPTY_SHA256:
            raise ValueError(f"privileged process {sequence}: stderr is not empty")
        if (
            row["return_code"] != "0"
            or row["binary_sha256_at_launch"] != config["binary_sha256"]
            or row["stdout_sha256"] != digest_path(stdout_path)
            or row["stderr_sha256"] != digest_path(stderr_path)
        ):
            raise ValueError(f"privileged process {sequence}: execution receipt mismatch")

        pid = int(
            extract(
                stdout,
                r"^probe_pid=([0-9]+) uid=0 euid=0$",
                f"privileged process {sequence}",
            ).group(1)
        )
        accept = parse_program(stdout, "accept")
        drop = parse_program(stdout, "drop")
        blob_root = process_root / "raw" / f"run-{sequence:02d}-kernel-bytes"
        if {path.name for path in blob_root.iterdir()} != {
            "accept.xlated.bin",
            "accept.jited.bin",
            "drop.xlated.bin",
            "drop.jited.bin",
        }:
            raise ValueError(f"privileged process {sequence}: unexpected blob inventory")
        accept_digests = validate_program_blobs(
            blob_root, accept, "accept", exact_xlated["accept"]
        )
        drop_digests = validate_program_blobs(
            blob_root, drop, "drop", exact_xlated["drop"]
        )
        if any(
            (
                row["probe_pid"] != str(pid),
                row["accept_program_id"] != str(accept["program_id"]),
                row["drop_program_id"] != str(drop["program_id"]),
                row["accept_xlated_sha256"] != accept_digests["xlated"],
                row["drop_xlated_sha256"] != drop_digests["xlated"],
                row["accept_jited_bytes"] != str(accept["jited_len"]),
                row["drop_jited_bytes"] != str(drop["jited_len"]),
                row["accept_jited_sha256"] != accept_digests["jited"],
                row["drop_jited_sha256"] != drop_digests["jited"],
            )
        ):
            raise ValueError(f"privileged process {sequence}: semantic row mismatch")

        for label in ("accept", "drop"):
            disassembly_path = (
                root
                / "codegen"
                / "jit"
                / f"run-{sequence:02d}-{label}.objdump.txt"
            )
            disassembly = disassembly_path.read_text(encoding="utf-8")
            evidence_label = (
                f"privileged process {sequence}: {label} JIT disassembly"
            )
            header = re.search(
                r"^(.+):\s+file format binary$", disassembly, re.MULTILINE
            )
            expected_suffix = (
                f"/run-{sequence:02d}-kernel-bytes/{label}.jited.bin"
            )
            if header is None or not header.group(1).endswith(expected_suffix):
                raise ValueError(f"{evidence_label}: header names the wrong JIT blob")
            retained_jit = (blob_root / f"{label}.jited.bin").read_bytes()
            decoded_jit = disassembled_bytes(
                disassembly, architecture, evidence_label
            )
            if decoded_jit != retained_jit:
                raise ValueError(f"{evidence_label}: bytes differ from the retained JIT blob")
            if re.search(r"\bret[q]?\b", disassembly) is None:
                raise ValueError(
                    f"{evidence_label}: return instruction is absent"
                )


def validate_host_and_source(root: Path, contract: dict[str, object]) -> str:
    """Require source binding and the advertised Linux host evidence."""

    required_files = [
        "source-identity.txt",
        "source-manifest-before.sha256",
        "source-manifest-after.sha256",
        "host.txt",
        "proc-cpuinfo.txt",
        "proc-self-status.txt",
        "gcc-version.txt",
        "gcc-target.txt",
        "gcc-target-options.txt",
        "rustc-version.txt",
        "cargo-version.txt",
        "python-version.txt",
        "objdump-version.txt",
        "kernel-bpf-config.txt",
        "bpf-policy.txt",
        "bpf-filesystems.txt",
        "build.txt",
        "rust-tests.txt",
        "rust-example.txt",
        "codegen/probe.objdump.txt",
        "codegen/probe.elf.txt",
    ]
    for relative in required_files:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"missing required source or host receipt: {relative}")
    if (root / "source-manifest-before.sha256").read_bytes() != (
        root / "source-manifest-after.sha256"
    ).read_bytes():
        raise ValueError("extracted exact source changed during execution")
    source = root / "artifacts" / "ebpf_socket_filter.c"
    if digest_path(source) != contract["source_sha256"]:
        raise ValueError("retained C source differs from the tested source digest")

    host = (root / "host.txt").read_text(encoding="utf-8")
    label = extract(host, r"^ssh_target_label=(.+)$", "host target label").group(1)
    architecture = extract(host, r"^architecture=(.+)$", "host architecture").group(1)
    hostname_fqdn = extract(host, r"^hostname_fqdn=(.+)$", "host fqdn").group(1)
    if label == "xxl" and architecture != "x86_64":
        raise ValueError("xxl receipt is not x86-64")
    if label == ARM_HOST:
        if architecture not in {"aarch64", "arm64"}:
            raise ValueError("authorized Arm receipt is not AArch64")
        if hostname_fqdn != label:
            raise ValueError("authorized Arm receipt did not run on the named host")
    if label not in {"xxl", ARM_HOST}:
        raise ValueError("receipt names an unauthorized target label")
    for marker in (
        "uname_all=",
        "kernel=",
        "cpu_count_online=",
        "cpu_count_configured=",
        "cpu_count_available=",
        "build_flags=-O2 -g -std=c11 -Wall -Wextra -Werror",
        "fresh_privileged_processes=8",
        "timing_reported=no",
    ):
        if marker not in host:
            raise ValueError(f"host receipt lacks {marker}")

    source_identity = (root / "source-identity.txt").read_text(encoding="utf-8")
    if re.search(r"^source_commit=[0-9a-f]{40}$", source_identity, re.MULTILINE) is None:
        raise ValueError("source identity lacks a full commit")
    if re.search(
        r"^source_archive_sha256=[0-9a-f]{64}$", source_identity, re.MULTILINE
    ) is None:
        raise ValueError("source identity lacks the archive digest")
    return architecture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.root.resolve(strict=True)
    contract_bytes = arguments.contract.read_bytes()
    if hashlib.sha256(contract_bytes).hexdigest() not in EXPECTED_CONTRACT_SHA256S:
        raise ValueError("contract digest differs from the pinned receipt contract")
    contract = json.loads(contract_bytes.decode("utf-8"))

    validate_contract(contract)
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"evidence bundle contains a symlink: {path}")
    architecture = validate_host_and_source(root, contract)
    validate_ordinary(root, contract)
    validate_privileged(root, contract, architecture)
    print(
        "receipt_validation=PASS ordinary_permission_processes=1 "
        "fresh_privileged_processes=8 jit_disassemblies=16 timing_reported=no"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
