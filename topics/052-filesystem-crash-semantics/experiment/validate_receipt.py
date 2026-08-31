#!/usr/bin/env python3
"""Independently validate one sealed Topic 52 host receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys


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


def require_line(path: pathlib.Path, pattern: str) -> None:
    """Require one full-line regular-expression match in a UTF-8 file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not any(re.fullmatch(pattern, line) for line in lines):
        raise ValueError(f"{path.name} lacks required line {pattern!r}")


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
    require_line(reflink_path, r"reflink_clone_verify_exit=3 expected_exit=3")
    require_line(
        reflink_path,
        r"reflink_post_write_cmp_exit=[1-9][0-9]* expected_nonzero=yes",
    )
    require_line(
        root / "results" / "reflink-clone-verify.txt",
        r"verify current=INVALID temp=absent magic=valid checksum=invalid generation=42",
    )
    require_line(
        root / "results" / "reflink-source-verify.txt",
        re.escape(expected_complete),
    )


def validate(args: argparse.Namespace) -> dict[str, object]:
    """Validate content, manifest, source, host, and semantic oracles."""
    root = args.receipt.resolve()
    if not root.is_dir():
        raise ValueError("receipt is not a directory")
    if not (root / "SEALED").is_file() or (root / "SEALED").stat().st_size != 0:
        raise ValueError("receipt lacks an empty SEALED marker")

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
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name not in {"MANIFEST.sha256", "SEALED"}
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
    if (root / "source-files-before.sha256").read_bytes() != (root / "source-files-after.sha256").read_bytes():
        raise ValueError("source tree changed during the host run")

    expected_cuts = {
        "after_write": (101, "OLD", "present", 41),
        "after_file_fsync": (102, "OLD", "present", 41),
        "after_rename": (103, "NEW", "absent", 42),
        "after_dir_fsync": (104, "NEW", "absent", 42),
    }
    for cut, (status, state, temporary, generation) in expected_cuts.items():
        require_line(root / "results" / f"{cut}-status.txt", rf"cut={cut} update_exit={status} expected_exit={status}")
        require_line(
            root / "results" / f"{cut}-verify.txt",
            rf"verify current={state} temp={temporary} magic=valid checksum=valid generation={generation}",
        )

    validate_complete_and_reflink_controls(root)
    require_line(root / "results" / "corrupt-status.txt", r"corrupt_verify_exit=3 expected_exit=3")
    require_line(
        root / "results" / "corrupt-verify.txt",
        r"verify current=INVALID temp=absent magic=valid checksum=invalid generation=42",
    )
    require_line(root / "run-status.txt", r"run=pass")
    require_line(root / "run-status.txt", r"process_crash_only=yes")
    require_line(root / "run-status.txt", r"power_loss_tested=no")
    require_line(root / "run-status.txt", r"timing_claim=no")

    retained_paths = (root / "codegen" / "retained-paths.txt").read_text(encoding="utf-8")
    for symbol in ("openat", "fsync", "renameat", "fnv1a"):
        if symbol not in retained_paths:
            raise ValueError(f"code-generation evidence lacks {symbol}")

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
