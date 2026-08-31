#!/usr/bin/env python3
"""Independently validate one sealed Topic 52 host receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import stat
import sys
import tarfile

TOPIC_PREFIX = "topics/052-filesystem-crash-semantics/"
PROBE_SOURCE = TOPIC_PREFIX + "experiment/cow_crash_probe.c"
INVENTORY_LINE = re.compile(r"([0-9a-f]{64})  (.+)")
WRITE_BITS = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH


def sha256(path: pathlib.Path) -> str:
    """Return the SHA-256 digest for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_identity(path: pathlib.Path) -> dict[str, str]:
    """Parse the receipt's one-key-per-line identity file."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if not separator or key in values:
            raise ValueError(f"invalid identity line: {line!r}")
        values[key] = value
    return values


def require_line(path: pathlib.Path, pattern: str, family: str | None = None) -> None:
    """Require exactly one full-line match, rejecting a contradictory second record.

    A receipt that gains an appended or duplicated observation is ambiguous, so
    one match is required rather than at least one. When `family` is given, the
    file must also hold exactly one line of that broader kind, which rejects a
    second record that disagrees with the expected one.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    matched = sum(1 for line in lines if re.fullmatch(pattern, line))
    if matched != 1:
        raise ValueError(
            f"{path.name} needs exactly one line matching {pattern!r}, found {matched}"
        )
    if family is None:
        return
    related = sum(1 for line in lines if re.fullmatch(family, line))
    if related != 1:
        raise ValueError(
            f"{path.name} holds {related} {family!r} records; exactly one is required"
        )


def require_sealed_tree(root: pathlib.Path) -> None:
    """Require a sealed shape: only unwritable directories and regular files.

    The runner seals a receipt by removing every write bit, and the published
    evidence claims `read_only=true`. Checking the empty `SEALED` marker alone
    would certify a copy whose bits were restored, so a writable receipt or
    archive is rejected here instead of being trusted.

    Node kind is rejected here as well, because the manifest coverage check
    compares regular files only. A symbolic link, FIFO, socket, or device node
    would otherwise sit in the tree outside that comparison.
    """
    for path in [root, *sorted(root.rglob("*"))]:
        name = "." if path == root else path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"receipt holds a symbolic link: {name}")
        status = path.stat()
        if not stat.S_ISDIR(status.st_mode) and not stat.S_ISREG(status.st_mode):
            raise ValueError(f"receipt holds a non-regular entry: {name}")
        mode = stat.S_IMODE(status.st_mode)
        if mode & WRITE_BITS:
            raise ValueError(f"receipt path is writable: {name} mode={mode:04o}")


def parse_inventory(path: pathlib.Path) -> dict[str, str]:
    """Parse one `sha256sum` source inventory into a path-to-digest mapping."""
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = INVENTORY_LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid inventory line in {path.name}: {line!r}")
        digest, relative = match.groups()
        if relative in entries:
            raise ValueError(f"duplicate inventory path in {path.name}: {relative!r}")
        if relative.startswith("/") or ".." in pathlib.PurePosixPath(relative).parts:
            raise ValueError(f"unsafe inventory path in {path.name}: {relative!r}")
        if not relative.startswith(TOPIC_PREFIX):
            raise ValueError(
                f"inventory path outside {TOPIC_PREFIX} in {path.name}: {relative!r}"
            )
        entries[relative] = digest
    if not entries:
        raise ValueError(f"{path.name} lists no source file")
    return entries


def archive_inventory(archive: pathlib.Path, commit: str) -> dict[str, str]:
    """Return the topic source inventory computed from the retained archive.

    The archive digest is bound to the expected commit, so hashing its members
    yields an independent inventory. Comparing the receipt's self-reported
    inventory against this one establishes coverage of the built tree, which
    equality between the receipt's own two inventories cannot.
    """
    prefix = f"systems-snackpack-{commit}/"
    entries: dict[str, str] = {}
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle:
            if not member.isfile():
                continue
            if not member.name.startswith(prefix):
                raise ValueError(
                    f"archive member outside the commit prefix: {member.name!r}"
                )
            relative = member.name[len(prefix) :]
            if not relative.startswith(TOPIC_PREFIX):
                raise ValueError(
                    f"archive member outside {TOPIC_PREFIX}: {member.name!r}"
                )
            stream = bundle.extractfile(member)
            if stream is None:
                raise ValueError(f"archive member is not readable: {member.name!r}")
            digest = hashlib.sha256()
            with stream:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
            entries[relative] = digest.hexdigest()
    if PROBE_SOURCE not in entries:
        raise ValueError(f"retained archive lacks {PROBE_SOURCE}")
    return entries


def validate_source_inventory(root: pathlib.Path, commit: str) -> None:
    """Validate the receipt's source inventories against the retained archive."""
    before_path = root / "source-files-before.sha256"
    after_path = root / "source-files-after.sha256"
    if before_path.read_bytes() != after_path.read_bytes():
        raise ValueError("source tree changed during the host run")
    reported = parse_inventory(before_path)
    archived = archive_inventory(root / "source.tar.gz", commit)
    if reported != archived:
        missing = sorted(set(archived) - set(reported))
        extra = sorted(set(reported) - set(archived))
        changed = sorted(
            path
            for path in set(reported) & set(archived)
            if reported[path] != archived[path]
        )
        raise ValueError(
            "source inventory does not match the retained archive: "
            f"missing={missing}, extra={extra}, changed={changed}"
        )
    if sha256(root / "cow_crash_probe.c") != archived[PROBE_SOURCE]:
        raise ValueError("retained probe source does not match the archived source")


def require_retained_calls(root: pathlib.Path) -> None:
    """Require one real call instruction per synchronization syscall.

    Matching a bare symbol name across assembly and disassembly would accept a
    diagnostic string or a debug-information entry, so the call sites are read
    from the disassembly's instruction operands instead. The checksum path is
    not checked here: `fnv1a` has internal linkage and is inlined at `-O2`, so
    it has no call site. The corruption control proves that path executed, by
    distinguishing a valid record from a one-byte mutation.
    """
    disassembly = (root / "codegen" / "objdump.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    for symbol in ("openat", "fsync", "renameat"):
        pattern = re.compile(
            rf"^\s*[0-9a-f]+:\s.*\b(?:call|callq|bl|blr|jmp|jmpq|b)\s+"
            rf"[0-9a-f]+\s+<{re.escape(symbol)}(?:@plt)?[+>]",
            re.MULTILINE,
        )
        if pattern.search(disassembly) is None:
            raise ValueError(f"disassembly lacks a call instruction to {symbol}")


def validate_complete_and_reflink_controls(root: pathlib.Path) -> None:
    """Validate the A/A completion and reflink-isolation oracles."""
    expected_complete = (
        "verify current=NEW temp=absent magic=valid checksum=valid generation=42"
    )
    first_path = root / "results" / "complete-1-oracle.txt"
    second_path = root / "results" / "complete-2-oracle.txt"
    first = first_path.read_bytes()
    second = second_path.read_bytes()
    if first != second:
        raise ValueError("A/A oracle mismatch")
    for path in (first_path, second_path):
        if path.read_text(encoding="utf-8").splitlines() != [expected_complete]:
            raise ValueError(f"{path.name} is not the valid generation 42 oracle")
    require_line(
        root / "results" / "aa-control.txt",
        r"aa_control=pass complete verifier outputs match",
    )

    reflink_path = root / "results" / "reflink.txt"
    require_line(reflink_path, r"reflink_copy=success")
    require_line(
        reflink_path,
        r"reflink_clone_verify_exit=3 expected_exit=3",
        r"reflink_clone_verify_exit=.*",
    )
    # cmp exits 1 when inputs differ; exit 2 indicates an error.
    require_line(
        reflink_path,
        r"reflink_post_write_cmp_exit=1 .*",
        r"reflink_post_write_cmp_exit=.*",
    )
    require_line(
        root / "results" / "reflink-clone-verify.txt",
        r"verify current=INVALID temp=absent magic=valid checksum=invalid generation=42",
        r"verify .*",
    )
    require_line(
        root / "results" / "reflink-source-verify.txt",
        re.escape(expected_complete),
        r"verify .*",
    )


def validate(args: argparse.Namespace) -> dict[str, object]:
    """Validate the seal, manifest, source, host, code generation, and oracles."""
    root = args.receipt.resolve()
    if not root.is_dir():
        raise ValueError("receipt is not a directory")
    if not (root / "SEALED").is_file() or (root / "SEALED").stat().st_size != 0:
        raise ValueError("receipt lacks an empty SEALED marker")
    require_sealed_tree(root)

    manifest_path = root / "MANIFEST.sha256"
    manifest_lines = manifest_path.read_text(encoding="utf-8").splitlines()
    listed: set[str] = set()
    for line in manifest_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ValueError(f"invalid manifest line: {line!r}")
        expected_digest, relative = match.groups()
        if relative in listed or relative.startswith("/") or ".." in pathlib.PurePosixPath(relative).parts:
            raise ValueError(f"unsafe or duplicate manifest path: {relative!r}")
        listed.add(relative)
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"manifest entry is not a regular file: {relative}")
        if sha256(path) != expected_digest:
            raise ValueError(f"digest mismatch: {relative}")

    actual = {
        relative
        for relative in (
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        )
        if relative not in {"MANIFEST.sha256", "SEALED"}
    }
    if actual != listed:
        raise ValueError(f"manifest coverage mismatch: missing={actual - listed}, extra={listed - actual}")

    identity = parse_identity(root / "identity.txt")
    expected_identity = {
        "target_label": args.expected_target_label,
        "hostname": args.expected_hostname,
        "architecture": args.expected_architecture,
        "source_commit": args.expected_source_commit,
        "source_archive_sha256": args.expected_source_archive_sha256,
    }
    for key, expected in expected_identity.items():
        if identity.get(key) != expected:
            raise ValueError(f"identity mismatch for {key}: {identity.get(key)!r} != {expected!r}")
    if sha256(root / "source.tar.gz") != args.expected_source_archive_sha256:
        raise ValueError("retained source archive digest mismatch")
    validate_source_inventory(root, identity["source_commit"])

    expected_cuts = {
        "after_write": (101, "OLD", "present", 41),
        "after_file_fsync": (102, "OLD", "present", 41),
        "after_rename": (103, "NEW", "absent", 42),
        "after_dir_fsync": (104, "NEW", "absent", 42),
    }
    for cut, (status, state, temporary, generation) in expected_cuts.items():
        require_line(
            root / "results" / f"{cut}-status.txt",
            rf"cut={cut} update_exit={status} expected_exit={status}",
            r"cut=.*",
        )
        require_line(
            root / "results" / f"{cut}-verify.txt",
            rf"verify current={state} temp={temporary} magic=valid checksum=valid generation={generation}",
            r"verify .*",
        )

    validate_complete_and_reflink_controls(root)
    require_line(
        root / "results" / "corrupt-status.txt",
        r"corrupt_verify_exit=3 expected_exit=3",
        r"corrupt_verify_exit=.*",
    )
    require_line(
        root / "results" / "corrupt-verify.txt",
        r"verify current=INVALID temp=absent magic=valid checksum=invalid generation=42",
        r"verify .*",
    )
    require_line(root / "run-status.txt", r"run=pass")
    require_line(root / "run-status.txt", r"process_crash_only=yes")
    require_line(root / "run-status.txt", r"power_loss_tested=no")
    require_line(root / "run-status.txt", r"filesystem_replay_tested=no")
    require_line(root / "run-status.txt", r"timing_claim=no")

    require_retained_calls(root)

    return {
        "pass": True,
        "sealed": True,
        "target_label": identity["target_label"],
        "hostname": identity["hostname"],
        "architecture": identity["architecture"],
        "source_commit": identity["source_commit"],
        "source_archive_sha256": identity["source_archive_sha256"],
        "manifest_sha256": sha256(manifest_path),
        "files_verified": len(listed),
        "process_crash_only": True,
        "power_loss_tested": False,
        "timing_claim": False,
    }


def main() -> int:
    """Parse command-line arguments and print one validation result."""
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=pathlib.Path)
    parser.add_argument("--expected-target-label", required=True)
    parser.add_argument("--expected-hostname", required=True)
    parser.add_argument("--expected-architecture", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-source-archive-sha256", required=True)
    args = parser.parse_args()
    try:
        result = validate(args)
    except (OSError, ValueError) as error:
        print(json.dumps({"pass": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
