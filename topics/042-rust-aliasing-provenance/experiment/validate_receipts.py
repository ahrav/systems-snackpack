#!/usr/bin/env python3
"""Validate Topic 42 correctness, source, host, gate, and codegen receipts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shlex
from pathlib import Path, PurePosixPath


EXPECTED_GATE_LOGS = (
    "gates/01-git-diff-check.txt",
    "gates/02-cargo-fmt.txt",
    "gates/03-cargo-test-lib-examples.txt",
    "gates/04-cargo-test-doc.txt",
    "gates/05-cargo-clippy.txt",
    "gates/06-cargo-bench-no-run.txt",
    "gates/07-cargo-doc.txt",
)

# The complete argv each recorded command must have, after its leading `env` and
# assignments are removed. "*" matches exactly one run-varying token, such as an
# absolute path. Matching the whole shape rather than testing for required
# members is what rejects an extra behaviour-changing flag: adding --no-run to the
# test gate leaves every expected argument present but stops the tests running.
EXPECTED_COMMANDS: dict[str, dict[str, object]] = {
    "gates/01-git-diff-check.txt": {
        "argv": ("git", "-C", "*", "diff", "--check"),
    },
    "gates/02-cargo-fmt.txt": {
        "argv": ("cargo", "fmt", "--manifest-path", "*", "--all", "--", "--check"),
    },
    "gates/03-cargo-test-lib-examples.txt": {
        "argv": (
            "cargo", "test", "--manifest-path", "*",
            "--locked", "--offline", "--workspace", "--lib", "--examples",
        ),
        "env": {"CARGO_TARGET_DIR": None},
    },
    "gates/04-cargo-test-doc.txt": {
        "argv": (
            "cargo", "test", "--manifest-path", "*",
            "--locked", "--offline", "--workspace", "--doc",
        ),
        "env": {"CARGO_TARGET_DIR": None},
    },
    "gates/05-cargo-clippy.txt": {
        "argv": (
            "cargo", "clippy", "--manifest-path", "*",
            "--locked", "--offline", "--workspace", "--all-targets",
            "--", "-D", "warnings",
        ),
        "env": {"CARGO_TARGET_DIR": None},
    },
    "gates/06-cargo-bench-no-run.txt": {
        "argv": (
            "cargo", "bench", "--manifest-path", "*",
            "--locked", "--offline", "--workspace", "--no-run",
        ),
        "env": {"CARGO_TARGET_DIR": None},
    },
    "gates/07-cargo-doc.txt": {
        "argv": (
            "cargo", "doc", "--manifest-path", "*",
            "--locked", "--offline", "--workspace", "--no-deps",
        ),
        "env": {"CARGO_TARGET_DIR": None, "RUSTDOCFLAGS": "-D warnings"},
    },
    "source-clean-after.txt": {
        "argv": ("git", "-C", "*", "diff", "--check"),
    },
    "build-native.txt": {
        "argv": (
            "cargo", "build", "-vv", "--manifest-path", "*",
            "--locked", "--offline", "--release",
            "--package", "rust-aliasing-provenance",
            "--example", "provenance_demo",
        ),
        "env": {
            "CARGO_TARGET_DIR": None,
            "RUSTFLAGS": "-C opt-level=3 -C target-cpu=native -C panic=abort",
        },
    },
    "codegen-command.txt": {
        "argv": (
            "rustc", "--crate-name", "rust_aliasing_provenance",
            "--edition=2024", "--crate-type=lib",
            "-C", "opt-level=3", "-C", "target-cpu=native", "-C", "panic=abort",
            "--emit=*", "*",
        ),
        "arg_suffixes": {12: "src/lib.rs"},
    },
    "run-processes.txt": {
        "argv": (
            "python3", "-I", "-B", "*",
            "--binary", "*", "--expected", "*", "--output", "*", "--runs", "8",
        ),
        "arg_suffixes": {3: "run_processes.py"},
    },
}


def parse_recorded_argv(command_line: str) -> tuple[dict[str, str], list[str]]:
    """Split a recorded COMMAND line into env assignments and argv.

    `run_record` writes the command with printf %q, so the line is shell-quoted
    and parsed as such. A leading `env` plus any NAME=VALUE assignments are
    returned separately from the program and its arguments.
    """

    if "$'" in command_line:
        raise ValueError("recorded command uses unsupported ANSI-C quoting")
    argv = shlex.split(command_line, posix=True)
    if not argv:
        raise ValueError("recorded command is empty")
    if PurePosixPath(argv[0]).name == "env":
        argv = argv[1:]
    assignments: dict[str, str] = {}
    while argv and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", argv[0]):
        name, value = argv[0].split("=", 1)
        assignments[name] = value
        argv = argv[1:]
    if not argv:
        raise ValueError("recorded command names no program")
    return assignments, argv


def require_command_receipt(root: Path, relative: str) -> None:
    """Require one recorded command and a single final zero exit status.

    A substring search accepts any nonempty file containing the expected text, and
    testing only for required members accepts extra arguments that change what
    ran. The receipt must therefore carry the shape `run_record` writes -- its
    command on the first line, then exactly one exit status as the last line --
    and its parsed argv must match the expected shape element for element.
    """

    expected = EXPECTED_COMMANDS[relative]
    lines = (root / relative).read_text(encoding="utf-8").splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        raise ValueError(f"empty command receipt: {relative}")
    if not lines[0].startswith("COMMAND="):
        raise ValueError(f"receipt does not open with its command: {relative}")

    assignments, argv = parse_recorded_argv(lines[0][len("COMMAND=") :])
    template: tuple[str, ...] = expected["argv"]  # type: ignore[assignment]
    if len(argv) != len(template):
        raise ValueError(
            f"receipt {relative} records {len(argv)} argv elements, "
            f"expected {len(template)}: {argv}"
        )
    for index, (actual, wanted) in enumerate(zip(argv, template)):
        if wanted == "*":
            continue
        if wanted.endswith("*"):
            if not actual.startswith(wanted[:-1]):
                raise ValueError(
                    f"receipt {relative} argv[{index}] {actual!r} does not start "
                    f"{wanted[:-1]!r}"
                )
            continue
        if index == 0:
            if PurePosixPath(actual).name != wanted:
                raise ValueError(
                    f"receipt {relative} records program {actual!r}, expected {wanted!r}"
                )
            continue
        if actual != wanted:
            raise ValueError(
                f"receipt {relative} argv[{index}] is {actual!r}, expected {wanted!r}"
            )
    for index, suffix in expected.get("arg_suffixes", {}).items():  # type: ignore[union-attr]
        if not argv[index].endswith(suffix):
            raise ValueError(
                f"receipt {relative} argv[{index}] does not end {suffix!r}"
            )

    wanted_env: dict[str, str | None] = expected.get("env", {})  # type: ignore[assignment]
    if set(assignments) != set(wanted_env):
        raise ValueError(
            f"receipt {relative} records environment {sorted(assignments)}, "
            f"expected {sorted(wanted_env)}"
        )
    for name, value in wanted_env.items():
        if value is not None and assignments[name] != value:
            raise ValueError(
                f"receipt {relative} records {name}={assignments[name]!r}, "
                f"expected {value!r}"
            )

    statuses = [
        index
        for index, line in enumerate(lines)
        if re.fullmatch(r"EXIT_STATUS=\d+", line)
    ]
    if len(statuses) != 1:
        raise ValueError(
            f"receipt {relative} must record exactly one exit status, "
            f"found {len(statuses)}"
        )
    if statuses[0] != len(lines) - 1:
        raise ValueError(f"receipt {relative} does not end with its exit status")
    if lines[-1] != "EXIT_STATUS=0":
        raise ValueError(f"receipt {relative} records {lines[-1]}")


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


def llvm_parameters(header: str, symbol: str) -> dict[str, str]:
    """Return each parameter declaration in one LLVM definition header by name.

    Attributes elsewhere in the header, including a `section "noalias"` clause,
    must not be mistaken for a parameter attribute, so the parameter list is
    isolated by balanced parentheses and split on its own top-level commas.
    """

    opening = header.index("(", header.index(f"@{symbol}"))
    depth = 0
    closing = -1
    for index in range(opening, len(header)):
        if header[index] == "(":
            depth += 1
        elif header[index] == ")":
            depth -= 1
            if depth == 0:
                closing = index
                break
    if closing < 0:
        raise ValueError(f"unbalanced parameter list for {symbol}")

    declarations: list[str] = []
    current = ""
    depth = 0
    for character in header[opening + 1 : closing]:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == "," and depth == 0:
            declarations.append(current)
            current = ""
        else:
            current += character
    declarations.append(current)

    parameters: dict[str, str] = {}
    for declaration in declarations:
        name = re.search(r"%([A-Za-z0-9_.]+)\s*$", declaration.strip())
        if name is not None:
            parameters[name.group(1)] = declaration
    return parameters


def validate_llvm_contract(root: Path) -> None:
    """Prove the alias-sensitive load contract in optimized LLVM IR."""

    text = (root / "codegen" / "topic42.ll").read_text(encoding="utf-8")
    reference_header, reference_body = llvm_definition(
        text, "topic42_reference_contract"
    )
    raw_header, raw_body = llvm_definition(text, "topic42_raw_contract")

    # Counting the attribute across the whole header cannot show which parameter
    # carries it, so require it on each parameter's own declaration.
    reference_parameters = llvm_parameters(reference_header, "topic42_reference_contract")
    raw_parameters = llvm_parameters(raw_header, "topic42_raw_contract")
    for name in ("destination", "source"):
        if name not in reference_parameters:
            raise ValueError(f"reference contract lacks a %{name} parameter")
        if not re.search(r"\bnoalias\b", reference_parameters[name]):
            raise ValueError(f"reference parameter %{name} does not carry LLVM noalias")
        if name not in raw_parameters:
            raise ValueError(f"raw contract lacks a %{name} parameter")
        if re.search(r"\bnoalias\b", raw_parameters[name]):
            raise ValueError(f"raw parameter %{name} unexpectedly carries LLVM noalias")

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
    root: Path,
    expected_commit: str,
    expected_archive_sha256: str,
    expected_hostname: str,
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
    for relative in EXPECTED_COMMANDS:
        require_command_receipt(root, relative)

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

    # Both hostname fields come from the bundle under test, so comparing them to
    # each other only proves internal consistency: absent fields would compare
    # equal as None, and a bundle from another host stays self-consistent.
    # Require both to be present and to equal the hostname the caller expects.
    recorded_fqdn = host.get("hostname_fqdn", "")
    recorded_resolved = host.get("ssh_resolved_hostname", "")
    if not recorded_fqdn or not recorded_resolved:
        raise ValueError("host receipt lacks a recorded resolved hostname")
    if recorded_fqdn != recorded_resolved:
        raise ValueError("recorded resolved hostname differs from the executing host")
    if recorded_fqdn != expected_hostname:
        raise ValueError(
            f"bundle records host {recorded_fqdn}, expected {expected_hostname}"
        )
    if label != "xxl" and recorded_fqdn != label:
        raise ValueError("fixed Arm label must equal the recorded hostname")
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
    parser.add_argument(
        "--expected-hostname",
        required=True,
        help="fully qualified hostname the bundle must have been produced on",
    )
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    expected = arguments.expected.read_bytes()

    validate_host_source_and_gates(
        root,
        arguments.source_commit,
        arguments.archive_sha256,
        arguments.expected_hostname,
    )
    validate_processes(root, expected)
    validate_llvm_contract(root)
    print(
        "receipt_validation=PASS fresh_processes=8 timing_reported=no "
        "reference_noalias=yes reference_source_loads=1 "
        "raw_noalias=no raw_source_loads=2 "
        f"source_commit={arguments.source_commit} "
        f"source_archive_sha256={arguments.archive_sha256} "
        f"host={arguments.expected_hostname}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
