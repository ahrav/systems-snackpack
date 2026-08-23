#!/usr/bin/env python3
"""Reject incomplete or internally inconsistent Topic 44 host evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path, PurePosixPath


REQUIRED_FILES = (
    "archive.sha256",
    "build.txt",
    "cargo-version.txt",
    "clang-version.txt",
    "codegen/library.asm",
    "codegen/library.ll",
    "codegen/library.o",
    "codegen/library.objdump.txt",
    "codegen/linked.objdump.txt",
    "codegen/linked.symbols.txt",
    "codegen/rustc-command.txt",
    "codegen/sha256sums.txt",
    "cpuinfo.txt",
    "expected.txt",
    "gcc-version.txt",
    "host-identity.txt",
    "kernel.txt",
    "native-target-cfg.txt",
    "processes/histogram_merge_probe",
    "processes/processes.jsonl",
    "run-processes.txt",
    "rust-target-features.txt",
    "rustc-version.txt",
    "source.tar.gz",
    "source-manifest-after.sha256",
    "source-manifest-before.sha256",
    "test.txt",
)

RUNNER_RELATIVE = "topics/044-tail-latency-histogram-merge-errors/experiment/run_host.sh"

EXPECTED_RELATIVE = "topics/044-tail-latency-histogram-merge-errors/experiment/expected.txt"


def digest(path: Path) -> str:
    """Return one file's Secure Hash Algorithm 256-bit digest."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_digest_manifest(path: Path) -> dict[str, str]:
    """Parse a `sha256sum` manifest and reject unsafe or duplicate paths."""

    entries = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        recorded_digest, separator, name = line.partition("  ")
        relative = PurePosixPath(name)
        if (
            not separator
            or re.fullmatch(r"[0-9a-f]{64}", recorded_digest) is None
            or not name
            or relative.is_absolute()
            or ".." in relative.parts
            or name in entries
        ):
            raise ValueError(f"invalid digest-manifest line: {line!r}")
        entries[name] = recorded_digest
    if not entries:
        raise ValueError(f"empty digest manifest: {path}")
    return entries


def manifest_from_archive(path: Path) -> tuple[str, dict[str, str]]:
    """Hash every regular archived source file under its repository path."""

    with tarfile.open(path, mode="r:gz") as archive:
        commit = archive.pax_headers.get("comment", "")
        runner_names = [
            member.name
            for member in archive.getmembers()
            if member.isfile() and member.name.endswith(RUNNER_RELATIVE)
        ]
        if len(runner_names) != 1:
            raise ValueError("source archive does not contain exactly one Topic 44 runner")
        prefix = runner_names[0][: -len(RUNNER_RELATIVE)]
        entries = {}
        for member in archive.getmembers():
            if member.isdir():
                continue
            if not member.isfile() or not member.name.startswith(prefix):
                raise ValueError(f"unsupported archive member: {member.name!r}")
            relative = member.name[len(prefix) :]
            if not relative or relative in entries:
                raise ValueError(f"invalid or duplicate archive path: {relative!r}")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"cannot read archived file: {relative!r}")
            entries[relative] = hashlib.sha256(extracted.read()).hexdigest()
    return commit, entries


def parse_identity(path: Path) -> dict[str, str]:
    """Parse nonempty `key=value` fields from a host-identity receipt."""

    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if not separator or not key or not value:
            raise ValueError(f"invalid identity line: {line!r}")
        fields[key] = value
    return fields


def main() -> int:
    """Validate source stability, host identity, process output, and codegen."""

    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--expected-label", required=True)
    parser.add_argument("--expected-resolved-host", required=True)
    arguments = parser.parse_args()
    root = arguments.root.resolve()

    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        raise SystemExit(f"missing receipts: {', '.join(missing)}")

    identity = parse_identity(root / "host-identity.txt")
    if identity.get("target_label") != arguments.expected_label:
        raise SystemExit("target label differs from the requested host")
    if identity.get("resolved_hostname") != arguments.expected_resolved_host:
        raise SystemExit("recorded alias resolution differs from the requested host")
    if identity.get("executing_hostname") != arguments.expected_resolved_host:
        raise SystemExit("executing host differs from the runtime resolution")
    architecture = identity.get("architecture")
    if arguments.expected_label == "xxl" and architecture != "x86_64":
        raise SystemExit("xxl did not execute on x86_64")
    if arguments.expected_label != "xxl" and architecture not in {"aarch64", "arm64"}:
        raise SystemExit("the fixed Arm target did not report an Arm architecture")

    archive_digest_entries = parse_digest_manifest(root / "archive.sha256")
    if set(archive_digest_entries) != {"source.tar.gz"}:
        raise SystemExit("archive digest manifest must name only source.tar.gz")
    archive_digest = digest(root / "source.tar.gz")
    if archive_digest_entries["source.tar.gz"] != archive_digest:
        raise SystemExit("retained source archive digest does not match its manifest")
    if identity.get("archive_sha256") != archive_digest:
        raise SystemExit("host identity records a different source archive digest")

    archived_commit, archived_manifest = manifest_from_archive(root / "source.tar.gz")
    if archived_commit != identity.get("source_commit"):
        raise SystemExit("retained source archive embeds a different commit")
    before_manifest = parse_digest_manifest(root / "source-manifest-before.sha256")
    after_manifest = parse_digest_manifest(root / "source-manifest-after.sha256")
    if before_manifest != archived_manifest or after_manifest != archived_manifest:
        raise SystemExit("source manifests do not match the retained Git archive")

    records = [
        json.loads(line)
        for line in (root / "processes/processes.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if len(records) != 8 or [record["run"] for record in records] != list(range(1, 9)):
        raise SystemExit("receipt does not contain exactly eight ordered process runs")
    if not all(record["passed"] and record["exit_status"] == 0 for record in records):
        raise SystemExit("at least one correctness process failed")
    executable_digest = digest(root / "processes/histogram_merge_probe")
    expected = (root / "expected.txt").read_bytes()
    if hashlib.sha256(expected).hexdigest() != archived_manifest.get(EXPECTED_RELATIVE):
        raise SystemExit("retained oracle differs from the archived expected output")
    empty_digest = hashlib.sha256(b"").hexdigest()
    for record in records:
        run = record["run"]
        stdout_path = root / "processes" / f"run-{run:02d}.stdout"
        stderr_path = root / "processes" / f"run-{run:02d}.stderr"
        if not stdout_path.is_file() or not stderr_path.is_file():
            raise SystemExit(f"process {run} output files are missing")
        if stdout_path.read_bytes() != expected or stderr_path.read_bytes():
            raise SystemExit(f"process {run} retained output differs from the oracle")
        if record["executable_sha256"] != executable_digest:
            raise SystemExit(f"process {run} records a different executable")
        if record["stdout_sha256"] != digest(stdout_path):
            raise SystemExit(f"process {run} records a different stdout digest")
        if record["stderr_sha256"] != empty_digest or digest(stderr_path) != empty_digest:
            raise SystemExit(f"process {run} records nonempty stderr")
    if "status=PASS" not in (root / "run-processes.txt").read_text(encoding="utf-8"):
        raise SystemExit("process runner did not report PASS")

    codegen_digests = parse_digest_manifest(root / "codegen/sha256sums.txt")
    expected_codegen_paths = {
        "processes/histogram_merge_probe",
        "codegen/library.o",
    }
    if set(codegen_digests) != expected_codegen_paths:
        raise SystemExit("codegen digest manifest names unexpected files")
    for relative, recorded_digest in codegen_digests.items():
        if digest(root / relative) != recorded_digest:
            raise SystemExit(f"generated file differs from its digest: {relative}")
    if "topic44_checked_merge_four" not in (
        root / "codegen/linked.symbols.txt"
    ).read_text(encoding="utf-8"):
        raise SystemExit("linked binary lacks the retained merge symbol")

    print(f"validated_target={arguments.expected_label}")
    print(f"validated_architecture={architecture}")
    print("fresh_processes=8")
    print("status=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
