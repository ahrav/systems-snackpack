#!/usr/bin/env python3
"""Validate Topic 42 correctness, source, host, gate, and codegen receipts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


EXPECTED_GATE_LOGS = (
    "gates/01-git-diff-check.txt",
    "gates/02-cargo-fmt.txt",
    "gates/03-cargo-test-lib-examples.txt",
    "gates/04-cargo-test-doc.txt",
    "gates/05-cargo-clippy.txt",
    "gates/06-cargo-bench-no-run.txt",
    "gates/07-cargo-doc.txt",
)


def digest_path(path: Path) -> str:
    """Return a streaming SHA-256 digest for one file."""

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def require_nonempty(root: Path, relatives: tuple[str, ...]) -> None:
    """Require each relative path to name a nonempty regular file."""

    for relative in relatives:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"missing or empty receipt: {relative}")


def parse_key_values(path: Path) -> dict[str, str]:
    """Parse the leading key-value section of a receipt."""

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"[a-z][a-z0-9_]*", key):
            values[key] = value
    return values


def validate_processes(root: Path, expected: bytes) -> None:
    """Require eight exact-output, fresh-process receipts."""

    process_root = root / "processes"
    config = json.loads((process_root / "config.json").read_text(encoding="utf-8"))
    expected_digest = hashlib.sha256(expected).hexdigest()
    required_config = {
        "binary",
        "binary_sha256",
        "expected",
        "expected_sha256",
        "fresh_process_runs",
        "measurement_kind",
        "retry_policy",
        "timing_reported",
    }
    if set(config) != required_config or any(
        (
            config["binary"] != "provenance-demo",
            config["expected"] != "expected.txt",
            config["expected_sha256"] != expected_digest,
            config["fresh_process_runs"] != 8,
            config["measurement_kind"]
            != "deterministic correctness and codegen only",
            config["retry_policy"] != "none",
            config["timing_reported"] is not False,
        )
    ):
        raise ValueError("process configuration contract changed")

    binary = process_root / str(config["binary"])
    retained_expected = process_root / str(config["expected"])
    if digest_path(binary) != config["binary_sha256"]:
        raise ValueError("retained process binary digest mismatch")
    if retained_expected.read_bytes() != expected:
        raise ValueError("retained expected output differs from the supplied contract")

    with (process_root / "runs.tsv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        expected_fields = [
            "sequence",
            "binary_sha256_at_launch",
            "return_code",
            "stdout_matches_expected",
            "stdout_sha256",
            "stderr_sha256",
            "stderr_bytes",
        ]
        if reader.fieldnames != expected_fields:
            raise ValueError("process receipt schema changed")
        rows = list(reader)
    if len(rows) != 8:
        raise ValueError(f"expected eight fresh processes, found {len(rows)}")
    if [row["sequence"] for row in rows] != [str(value) for value in range(1, 9)]:
        raise ValueError("process sequence is not exactly 1..8")

    empty_digest = hashlib.sha256(b"").hexdigest()
    for row in rows:
        sequence = int(row["sequence"])
        stdout = process_root / "raw" / f"run-{sequence:02d}.stdout"
        stderr = process_root / "raw" / f"run-{sequence:02d}.stderr"
        if any(
            (
                row["binary_sha256_at_launch"] != config["binary_sha256"],
                row["return_code"] != "0",
                row["stdout_matches_expected"] != "yes",
                row["stderr_bytes"] != "0",
                stdout.read_bytes() != expected,
                digest_path(stdout) != row["stdout_sha256"],
                stderr.read_bytes() != b"",
                digest_path(stderr) != empty_digest,
                row["stderr_sha256"] != empty_digest,
            )
        ):
            raise ValueError(f"failed deterministic receipt for process {sequence}")


def llvm_definition(text: str, symbol: str) -> tuple[str, str]:
    """Return one LLVM definition header and body for an exact symbol."""

    match = re.search(
        rf"^(define\b[^\n]*@{re.escape(symbol)}\([^\n]*\)[^\n]*\{{)\n(.*?)^\}}$",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise ValueError(f"LLVM IR lacks a definition for {symbol}")
    if len(re.findall(rf"^define\b[^\n]*@{re.escape(symbol)}\(", text, re.MULTILINE)) != 1:
        raise ValueError(f"LLVM IR does not contain exactly one definition for {symbol}")
    return match.group(1), match.group(2)


def validate_llvm_contract(root: Path) -> None:
    """Prove the alias-sensitive load contract in optimized LLVM IR."""

    text = (root / "codegen" / "topic42.ll").read_text(encoding="utf-8")
    reference_header, reference_body = llvm_definition(
        text, "topic42_reference_contract"
    )
    raw_header, raw_body = llvm_definition(text, "topic42_raw_contract")

    if len(re.findall(r"\bnoalias\b", reference_header)) < 2:
        raise ValueError("reference parameters do not both carry LLVM noalias")
    if re.search(r"\bnoalias\b", raw_header):
        raise ValueError("raw-pointer parameters unexpectedly carry LLVM noalias")

    source_load = re.compile(r"^\s*%[^=]+ = load i64, ptr %source(?:,|\s)", re.MULTILINE)
    reference_loads = list(source_load.finditer(reference_body))
    raw_loads = list(source_load.finditer(raw_body))
    if len(reference_loads) != 1:
        raise ValueError(
            f"reference contract needs one source load, found {len(reference_loads)}"
        )
    if len(raw_loads) != 2:
        raise ValueError(f"raw contract needs two source loads, found {len(raw_loads)}")

    reference_stores = list(
        re.finditer(r"^\s*store i64 .*ptr %destination(?:,|\s)", reference_body, re.MULTILINE)
    )
    raw_stores = list(
        re.finditer(r"^\s*store i64 .*ptr %destination(?:,|\s)", raw_body, re.MULTILINE)
    )
    if len(reference_stores) != 1 or len(raw_stores) != 1:
        raise ValueError("each LLVM contract must retain one destination store")
    if not (raw_loads[0].start() < raw_stores[0].start() < raw_loads[1].start()):
        raise ValueError("raw source loads do not surround the destination store")

    disassembly = (root / "codegen" / "linked.objdump.txt").read_text(
        encoding="utf-8"
    )
    symbols = (root / "codegen" / "linked.symbols.txt").read_text(encoding="utf-8")
    for symbol in ("topic42_reference_contract", "topic42_raw_contract"):
        if re.search(rf"<{symbol}>:", disassembly) is None:
            raise ValueError(f"linked disassembly lacks {symbol}")
        if re.search(rf"\b{symbol}$", symbols, re.MULTILINE) is None:
            raise ValueError(f"linked symbol table lacks {symbol}")


def validate_host_source_and_gates(
    root: Path, expected_commit: str, expected_archive_sha256: str
) -> None:
    """Require current host metadata, exact source identity, and seven gates."""

    required = (
        "host.txt",
        "source-identity.txt",
        "source-manifest-before.sha256",
        "source-manifest-after.sha256",
        "source-clean-after.txt",
        "rustc-version.txt",
        "cargo-version.txt",
        "python-version.txt",
        "git-version.txt",
        "objdump-version.txt",
        "readelf-version.txt",
        "rust-target-cfg.txt",
        "rust-native-target-cfg.txt",
        "rust-target-features.txt",
        "proc-cpuinfo.txt",
        "build-native.txt",
        "codegen-command.txt",
        "codegen/topic42.ll",
        "codegen/topic42.s",
        "codegen/topic42.o",
        "codegen/linked.objdump.txt",
        "codegen/linked.symbols.txt",
        "codegen/linked.elf.txt",
        "run-processes.txt",
    ) + EXPECTED_GATE_LOGS
    require_nonempty(root, required)
    if (root / "source-manifest-before.sha256").read_bytes() != (
        root / "source-manifest-after.sha256"
    ).read_bytes():
        raise ValueError("source manifest changed during the host run")
    if "EXIT_STATUS=0" not in (root / "source-clean-after.txt").read_text(
        encoding="utf-8"
    ):
        raise ValueError("final source-clean check lacks a zero exit status")
    for relative in EXPECTED_GATE_LOGS:
        if "EXIT_STATUS=0" not in (root / relative).read_text(encoding="utf-8"):
            raise ValueError(f"gate lacks a zero exit status: {relative}")

    source = parse_key_values(root / "source-identity.txt")
    recorded_commit = source.get("source_commit", "")
    recorded_archive_sha256 = source.get("source_archive_sha256", "")
    if re.fullmatch(r"[0-9a-f]{40}", recorded_commit) is None:
        raise ValueError("source commit is not a full Git object ID")
    if re.fullmatch(r"[0-9a-f]{64}", recorded_archive_sha256) is None:
        raise ValueError("source archive digest is not SHA-256")
    if recorded_commit != expected_commit:
        raise ValueError(
            f"bundle records source commit {recorded_commit}, expected {expected_commit}"
        )
    if recorded_archive_sha256 != expected_archive_sha256:
        raise ValueError(
            f"bundle records archive SHA-256 {recorded_archive_sha256}, "
            f"expected {expected_archive_sha256}"
        )
    if source.get("archive_embedded_commit") != expected_commit:
        raise ValueError(
            "archive-embedded commit differs from the expected source commit"
        )

    host = parse_key_values(root / "host.txt")
    label = host.get("ssh_target_label")
    architecture = host.get("architecture")
    if label == "xxl":
        if architecture != "x86_64":
            raise ValueError("xxl receipt is not x86-64")
    elif label == "dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com":
        if architecture not in {"aarch64", "arm64"}:
            raise ValueError("authorized Arm receipt is not AArch64")
    else:
        raise ValueError(f"unauthorized SSH target label: {label!r}")
    if host.get("hostname_fqdn") != host.get("ssh_resolved_hostname"):
        raise ValueError("recorded resolved hostname differs from the executing host")
    if any(
        (
            host.get("measurement_kind")
            != "deterministic correctness and codegen only",
            host.get("fresh_process_runs") != "8",
            host.get("timing_reported") != "no",
            host.get("build_flags")
            != "--release -C opt-level=3 -C target-cpu=native -C panic=abort",
        )
    ):
        raise ValueError("host measurement boundary or build flags changed")


def hex_field(length: int, label: str):
    """Return an argparse type that accepts one fixed-length lowercase hex field."""

    def parse(value: str) -> str:
        normalized = value.strip().lower()
        if re.fullmatch(rf"[0-9a-f]{{{length}}}", normalized) is None:
            raise argparse.ArgumentTypeError(
                f"{label} must be {length} hexadecimal digits"
            )
        return normalized

    return parse


def main() -> int:
    """Validate one host's complete Topic 42 receipt bundle."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument(
        "--source-commit",
        required=True,
        type=hex_field(40, "--source-commit"),
        help="full Git object ID the bundle must have been produced from",
    )
    parser.add_argument(
        "--archive-sha256",
        required=True,
        type=hex_field(64, "--archive-sha256"),
        help="SHA-256 of the git archive the bundle must have been produced from",
    )
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    expected = arguments.expected.read_bytes()

    validate_host_source_and_gates(
        root, arguments.source_commit, arguments.archive_sha256
    )
    validate_processes(root, expected)
    validate_llvm_contract(root)
    print(
        "receipt_validation=PASS fresh_processes=8 timing_reported=no "
        "reference_noalias=yes reference_source_loads=1 "
        "raw_noalias=no raw_source_loads=2 "
        f"source_commit={arguments.source_commit} "
        f"source_archive_sha256={arguments.archive_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
