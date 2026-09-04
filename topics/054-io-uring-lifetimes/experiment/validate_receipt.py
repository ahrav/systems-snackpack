#!/usr/bin/env python3
"""Validate one sealed Topic 54 host receipt from an independent controller."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile


TOPIC = "topics/054-io-uring-lifetimes"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
UTC_TIMESTAMP = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 96
MAX_TOPIC_FILES = 64


def sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest of one regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_key_values(path: Path) -> dict[str, str]:
    """Parse unique nonempty `key=value` records."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if not separator or not key or key in values:
            raise ValueError(f"malformed or duplicate record in {path.name}: {line!r}")
        values[key] = value
    return values


def semantic_output(text: str) -> dict[str, object]:
    """Extract the order-independent correctness results from one probe run."""
    lines = text.splitlines()
    if len(lines) != 5:
        raise ValueError("expected exactly five semantic output lines")

    baseline, owner, deferred, cancel, result = lines
    if not re.fullmatch(
        r"baseline_setup=ok sq_entries=8 cq_entries=16 features=0x[0-9a-f]+",
        baseline,
    ):
        raise ValueError("baseline setup line has unexpected fields")

    expected_owner = (
        "single_issuer owner_cqe={user_data=0x1001,res=0} "
        "other_task_enter=-17 (File exists)"
    )
    if owner != expected_owner:
        raise ValueError("single-issuer oracle failed")

    expected_deferred = (
        "defer_taskrun cqes_before_getevents=0 "
        "terminal={user_data=0x2001,res=-62}"
    )
    if deferred != expected_deferred:
        raise ValueError("deferred-task-run oracle failed")

    cancel_match = re.fullmatch(
        r"cancel terminal_1=\{user_data=(0x[0-9a-f]+),res=(-?[0-9]+)\} "
        r"terminal_2=\{user_data=(0x[0-9a-f]+),res=(-?[0-9]+)\}",
        cancel,
    )
    if cancel_match is None:
        raise ValueError("cancel output has unexpected fields")
    groups = cancel_match.groups()
    completions = [(groups[0], groups[1]), (groups[2], groups[3])]
    if sorted(completions) != [("0x3001", "-125"), ("0x3002", "0")]:
        raise ValueError("cancel and target terminal results do not match")
    if result != "result=ok":
        raise ValueError("expected one terminal result=ok line")

    return {
        "baseline": baseline,
        "owner": owner,
        "deferred": deferred,
        "cancel_completions": sorted(completions),
        "result": "ok",
    }


def _receipt_files(receipt: Path) -> list[Path]:
    def _fail(error: OSError) -> None:
        raise ValueError(f"receipt cannot be fully traversed: {error}")

    files: list[Path] = []
    for root, directories, names in os.walk(
        receipt, onerror=_fail, followlinks=False
    ):
        root_path = Path(root)
        for name in [*directories, *names]:
            path = root_path / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f"receipt contains symlink: {path}")
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError(f"receipt contains unsupported entry: {path}")
            if mode & 0o222:
                raise ValueError(f"receipt entry retains write permission: {path}")
        files.extend(root_path / name for name in names)
    return files


def _validate_manifest(receipt: Path, files: list[Path]) -> int:
    manifest_path = receipt / "MANIFEST.sha256"
    entries: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator or not HEX64.fullmatch(digest):
            raise ValueError(f"malformed manifest line: {line!r}")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or relative in entries:
            raise ValueError(f"unsafe or duplicate manifest path: {relative!r}")
        entries[relative] = digest

    excluded = {"MANIFEST.sha256", "SEALED"}
    actual = {
        path.relative_to(receipt).as_posix()
        for path in files
        if path.relative_to(receipt).as_posix() not in excluded
    }
    if set(entries) != actual:
        raise ValueError("manifest file set does not match receipt")
    for relative, expected in entries.items():
        if sha256(receipt / relative) != expected:
            raise ValueError(f"manifest digest mismatch: {relative}")
    return len(entries)


def _parse_inventory(path: Path) -> dict[str, str]:
    """Parse a bounded sha256sum inventory rooted at the repository."""
    entries: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or len(lines) > MAX_TOPIC_FILES:
        raise ValueError(f"source inventory size is invalid: {path.name}")
    for line in lines:
        digest, separator, relative = line.partition("  ")
        pure = PurePosixPath(relative)
        if (
            not separator
            or not HEX64.fullmatch(digest)
            or not relative.startswith(TOPIC + "/")
            or pure.is_absolute()
            or ".." in pure.parts
            or relative in entries
        ):
            raise ValueError(f"unsafe or duplicate source inventory line: {line!r}")
        entries[relative] = digest
    return entries


def _validate_archive(
    receipt: Path, commit: str, runner_digest: str
) -> dict[str, str]:
    root = f"systems-snackpack-{commit}"
    prefix = root + "/"
    topic_root = prefix + TOPIC
    ancestors = {root, prefix + "topics", topic_root}
    runner_name = topic_root + "/experiment/run_host.sh"
    source_name = topic_root + "/experiment/io_uring_lifetimes.c"
    archive = receipt / "source.tar.gz"
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("archive exceeds the compressed size bound")

    names: set[str] = set()
    inventory: dict[str, str] = {}
    runner_bytes: bytes | None = None
    source_bytes: bytes | None = None
    total_size = 0
    with tarfile.open(archive, "r:gz") as bundle:
        if bundle.pax_headers.get("comment") != commit:
            raise ValueError("archive lacks the expected Git commit header")
        members = bundle.getmembers()
        if not members or len(members) > MAX_ARCHIVE_MEMBERS:
            raise ValueError("archive member count is outside the safe bound")
        for member in members:
            name = member.name.rstrip("/")
            pure = PurePosixPath(name)
            if (
                not name
                or pure.is_absolute()
                or ".." in pure.parts
                or name in names
                or (name not in ancestors and not name.startswith(topic_root + "/"))
            ):
                raise ValueError(f"unsafe or duplicate archive member: {member.name!r}")
            names.add(name)
            if member.isdir():
                continue
            if name in ancestors or not member.isfile() or member.size > MAX_FILE_BYTES:
                raise ValueError(f"unsupported or oversized archive member: {member.name!r}")
            total_size += member.size
            if total_size > MAX_ARCHIVE_BYTES:
                raise ValueError("archive expands beyond the safe size bound")
            extracted = bundle.extractfile(member)
            if extracted is None:
                raise ValueError(f"archive member cannot be read: {member.name!r}")
            content = extracted.read()
            relative = name.removeprefix(prefix)
            inventory[relative] = hashlib.sha256(content).hexdigest()
            if name == runner_name:
                runner_bytes = content
            elif name == source_name:
                source_bytes = content

    if not inventory or len(inventory) > MAX_TOPIC_FILES:
        raise ValueError("archive topic file count is outside the safe bound")
    if runner_bytes is None or source_bytes is None:
        raise ValueError("archive lacks the exact runner or source")

    if hashlib.sha256(runner_bytes).hexdigest() != runner_digest:
        raise ValueError("archived runner digest does not match identity")
    if source_bytes != (receipt / "io_uring_lifetimes.c").read_bytes():
        raise ValueError("retained source differs from archived source")
    return inventory


def validate(
    receipt: Path,
    *,
    target_label: str,
    hostname: str,
    architecture: str,
    source_commit: str,
    archive_sha256: str,
) -> dict[str, object]:
    """Validate identity, immutability, content, and every probe oracle."""
    if not HEX40.fullmatch(source_commit) or not HEX64.fullmatch(archive_sha256):
        raise ValueError("expected source identity is malformed")
    if not receipt.is_dir() or receipt.is_symlink():
        raise ValueError("receipt is not a real directory")
    # _receipt_files() walks only descendants; a writable root can replace
    # direct read-only entries after validation.
    if receipt.stat().st_mode & 0o222:
        raise ValueError("receipt root retains write permission")
    files = _receipt_files(receipt)
    if not (receipt / "SEALED").is_file() or (receipt / "SEALED").stat().st_size != 0:
        raise ValueError("receipt lacks an empty SEALED marker")
    manifest_entries = _validate_manifest(receipt, files)

    identity = parse_key_values(receipt / "identity.txt")
    expected_identity = {
        "target_label": target_label,
        "hostname": hostname,
        "architecture": architecture,
        "source_commit": source_commit,
        "source_archive_sha256": archive_sha256,
    }
    if set(identity) != {*expected_identity, "runner_sha256", "run_utc"}:
        raise ValueError("identity field set is incomplete or unexpected")
    for key, expected in expected_identity.items():
        if identity.get(key) != expected:
            raise ValueError(f"identity mismatch for {key}")
    runner_digest = identity.get("runner_sha256", "")
    if not HEX64.fullmatch(runner_digest):
        raise ValueError("identity lacks a valid runner digest")
    if not UTC_TIMESTAMP.fullmatch(identity.get("run_utc", "")):
        raise ValueError("identity lacks a UTC run timestamp")
    if sha256(receipt / "source.tar.gz") != archive_sha256:
        raise ValueError("retained archive digest does not match")
    archive_inventory = _validate_archive(receipt, source_commit, runner_digest)

    inventory_before = _parse_inventory(receipt / "source-files-before.sha256")
    inventory_after = _parse_inventory(receipt / "source-files-after.sha256")
    if inventory_before != inventory_after:
        raise ValueError("source inventory changed during execution")
    if inventory_before != archive_inventory:
        raise ValueError("host source inventory differs from the retained archive")

    status = parse_key_values(receipt / "run-status.txt")
    expected_status = {
        "run": "pass",
        "process_repetitions": "2",
        "timing_claim": "no",
        "storage_tested": "no",
        "sqpoll_tested": "no",
        "iopoll_tested": "no",
        "registered_resources_tested": "no",
        "multishot_tested": "no",
    }
    if status != expected_status:
        raise ValueError("run-status boundary is incomplete or contradicted")

    run_1 = semantic_output((receipt / "results/run-1.txt").read_text(encoding="utf-8"))
    run_2 = semantic_output((receipt / "results/run-2.txt").read_text(encoding="utf-8"))
    if run_1 != run_2:
        raise ValueError("A/A semantic outputs differ")
    if (receipt / "results/run-1-normalized.txt").read_bytes() != (
        receipt / "results/run-2-normalized.txt"
    ).read_bytes():
        raise ValueError("runner-normalized A/A outputs differ")
    if (receipt / "results/aa-control.txt").read_text(encoding="utf-8") != (
        "aa_control=pass normalized semantic outputs match\n"
    ):
        raise ValueError("A/A control record is missing")

    host_text = (receipt / "host.txt").read_text(encoding="utf-8")
    if "kernel.io_uring_disabled=" not in host_text or "memlock_kib=" not in host_text:
        raise ValueError("host policy or locked-memory identity is missing")
    retained = (receipt / "codegen/retained-paths.txt").read_text(encoding="utf-8")
    if "syscall" not in retained:
        raise ValueError("code-generation record lacks the syscall path")

    return {
        "pass": True,
        "sealed": True,
        "manifest_entries": manifest_entries,
        "target_label": target_label,
        "hostname": hostname,
        "architecture": architecture,
        "source_commit": source_commit,
        "source_archive_sha256": archive_sha256,
        "runner_sha256": runner_digest,
        "semantic_result": run_1,
    }


def main() -> int:
    """Parse command-line expectations and print one JSON validation record."""
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--expected-target-label", required=True)
    parser.add_argument("--expected-hostname", required=True)
    parser.add_argument("--expected-architecture", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-source-archive-sha256", required=True)
    arguments = parser.parse_args()

    result = validate(
        arguments.receipt,
        target_label=arguments.expected_target_label,
        hostname=arguments.expected_hostname,
        architecture=arguments.expected_architecture,
        source_commit=arguments.expected_source_commit,
        archive_sha256=arguments.expected_source_archive_sha256,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
