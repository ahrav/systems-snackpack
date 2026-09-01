#!/usr/bin/env python3
"""Independently validate one exact-source Topic 53 host receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics
import tarfile
from typing import Any, NoReturn


TOPIC_PREFIX = "topics/053-nvme-blk-mq/"
EXPERIMENT_PREFIX = TOPIC_PREFIX + "experiment/"
PROBE_RELATIVE = EXPERIMENT_PREFIX + "nvme_aio_depth_probe.c"
RUN_HOST_RELATIVE = EXPERIMENT_PREFIX + "run_host.sh"
BLOCK_BYTES = 4096
DATA_FILE_BYTES = 128 * 1024 * 1024
T975_DF7 = 2.364624251
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
DEVICE = re.compile(r"[A-Za-z0-9_.-]+\Z")
WRITE_BITS = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
VMSTAT_KEYS = ("pgpgin", "pgpgout", "nr_dirty", "nr_writeback")
RESULT_KEYS = {
    "schema",
    "kind",
    "status",
    "pid",
    "tid",
    "threads_before",
    "threads_after",
    "mode",
    "label",
    "seed",
    "depth",
    "total_ops",
    "bytes",
    "blocks",
    "startup_to_measure_ns",
    "setup_ns",
    "elapsed_ns",
    "iops",
    "mib_s",
    "read_bytes_delta",
    "verified_reads",
    "errors",
    "checksum",
    "peak_outstanding",
    "resident_before",
    "resident_after",
    "total_pages",
    "dioalign_known",
    "dio_mem_align",
    "dio_offset_align",
    "dio_allocation_align",
    "nvcsw",
    "nivcsw",
}
SNAPSHOT_KEYS = {
    "schema",
    "phase",
    "wall_time_ns",
    "monotonic_ns",
    "proc_diskstats",
    "proc_pressure_io",
    "proc_vmstat",
    "cgroup_path",
    "cgroup_io_stat",
    "cgroup_io_pressure",
    "devices",
}
STATUS_KEYS = {
    "schema",
    "scenario",
    "sequence",
    "block",
    "period",
    "template",
    "letter",
    "mode",
    "depth",
    "seed",
    "label",
    "ops",
    "source_sha256",
    "binary_sha256",
    "pid",
    "returncode",
    "timed_out",
    "wall_elapsed_ns",
    "stdout_sha256",
    "stderr_sha256",
    "before_sha256",
    "after_sha256",
    "valid",
    "validation_errors",
    "observed",
    "counter_deltas",
}
ATTEMPT_PATH_KEYS = {
    "before_file",
    "stdout_file",
    "stderr_file",
    "after_file",
    "status_file",
}
SCENARIOS: dict[str, dict[str, Any]] = {
    "depth": {
        "templates": (
            "ABBA",
            "BAAB",
            "ABBA",
            "BAAB",
            "BAAB",
            "ABBA",
            "BAAB",
            "ABBA",
        ),
        "seed_base": 530100,
        "treatments": {
            "A": {"mode": "direct", "depth": 1, "label_prefix": "q1"},
            "B": {"mode": "direct", "depth": 8, "label_prefix": "q8"},
        },
        "ratio": "direct_q8_over_direct_q1_iops",
        "left": "A",
        "right": "B",
    },
    "aa": {
        "templates": (
            "XYYX",
            "YXXY",
            "XYYX",
            "YXXY",
            "YXXY",
            "XYYX",
            "YXXY",
            "XYYX",
        ),
        "seed_base": 530200,
        "treatments": {
            "X": {"mode": "direct", "depth": 1, "label_prefix": "aa-x"},
            "Y": {"mode": "direct", "depth": 1, "label_prefix": "aa-y"},
        },
        "ratio": "aa_y_over_aa_x_iops",
        "left": "X",
        "right": "Y",
    },
}


def fail(message: str) -> NoReturn:
    """Reject the receipt with one explicit error."""
    raise ValueError(message)


def require(condition: bool, message: str) -> None:
    """Reject a false receipt condition."""
    if not condition:
        fail(message)


def is_int(value: object) -> bool:
    """Return true only for a JSON integer, excluding booleans."""
    return type(value) is int


def is_number(value: object) -> bool:
    """Return true only for a finite JSON number, excluding booleans."""
    return type(value) in (int, float) and math.isfinite(float(value))


def reject_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(token: str) -> NoReturn:
    """Reject non-finite JSON extensions."""
    fail(f"non-finite JSON number: {token}")


def strict_json(text: str, label: str) -> object:
    """Parse strict JSON with duplicate-key and finite-number checks."""
    try:
        return json.loads(
            text,
            object_pairs_hook=reject_pairs,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, UnicodeError) as error:
        fail(f"{label}: invalid JSON: {error}")


def read_json(path: Path) -> dict[str, Any]:
    """Read one strict JSON object."""
    value = strict_json(path.read_text(encoding="utf-8"), str(path))
    require(isinstance(value, dict), f"{path}: expected one JSON object")
    return value


def read_json_line(path: Path) -> dict[str, Any]:
    """Read one newline-terminated strict JSON object."""
    text = path.read_text(encoding="utf-8")
    require(
        text.endswith("\n") and len(text.splitlines()) == 1,
        f"{path}: expected one newline-terminated JSON object",
    )
    value = strict_json(text, str(path))
    require(isinstance(value, dict), f"{path}: expected one JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a nonempty strict JSONL file."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            require(
                line.endswith("\n") and bool(line.strip()),
                f"{path}:{line_number}: partial or blank JSONL record",
            )
            value = strict_json(line, f"{path}:{line_number}")
            require(isinstance(value, dict), f"{path}:{line_number}: expected object")
            rows.append(value)
    require(bool(rows), f"{path}: no records")
    return rows


def sha256(path: Path) -> str:
    """Return a streaming SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def same(left: object, right: object) -> bool:
    """Compare JSON values with strict types and close finite floats."""
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if type(left) in (int, float) and type(right) in (int, float):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(same(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return type(left) is type(right) and left == right


def safe_file(root: Path, relative: object) -> Path:
    """Resolve one receipt-relative regular file without following links."""
    root = root.resolve(strict=True)
    require(isinstance(relative, str), "receipt path must be text")
    pure = PurePosixPath(relative)
    require(
        not pure.is_absolute() and ".." not in pure.parts,
        f"unsafe receipt path: {relative}",
    )
    unresolved = root / pure
    require(not unresolved.is_symlink(), f"receipt path is a symlink: {relative}")
    path = unresolved.resolve(strict=True)
    require(path.is_relative_to(root), f"receipt path escaped root: {relative}")
    require(path.is_file() and not path.is_symlink(), f"not a regular file: {relative}")
    return path


def parse_digest_sidecar(path: Path, expected_name: str) -> str:
    """Parse one GNU-style or digest-only SHA-256 sidecar."""
    lines = path.read_text(encoding="utf-8").splitlines()
    require(len(lines) == 1, f"{path}: expected one digest line")
    fields = lines[0].split()
    require(fields and HEX64.fullmatch(fields[0]) is not None, f"{path}: bad digest")
    if len(fields) > 1:
        require(fields[1].lstrip("*") == expected_name, f"{path}: filename differs")
    require(len(fields) <= 2, f"{path}: malformed digest line")
    return fields[0]


def parse_inventory(path: Path) -> dict[str, str]:
    """Parse a sorted GNU SHA-256 source inventory."""
    result: dict[str, str] = {}
    previous = ""
    text = path.read_text(encoding="utf-8")
    require(bool(text) and text.endswith("\n"), f"{path}: partial or empty inventory")
    for line in text.splitlines():
        require(not line.startswith("\\"), f"{path}: escaped filename")
        digest, separator, relative = line.partition("  ")
        pure = PurePosixPath(relative)
        require(
            bool(separator)
            and HEX64.fullmatch(digest) is not None
            and relative.startswith(TOPIC_PREFIX)
            and not pure.is_absolute()
            and ".." not in pure.parts
            and relative not in result
            and relative > previous,
            f"{path}: malformed, unsafe, duplicate, or unsorted line: {line}",
        )
        result[relative] = digest
        previous = relative
    require(bool(result), f"{path}: empty source inventory")
    return result


def archive_inventory(archive: Path, commit: str) -> dict[str, str]:
    """Hash regular Topic 53 members from a commit-bound Git archive."""
    prefix = f"systems-snackpack-{commit}/"
    result: dict[str, str] = {}
    with tarfile.open(archive, "r:gz") as bundle:
        embedded = bundle.pax_headers.get("comment", "").strip()
        members = bundle.getmembers()
        if not embedded:
            embedded = next(
                (
                    member.pax_headers.get("comment", "").strip()
                    for member in members
                    if member.pax_headers.get("comment")
                ),
                "",
            )
        require(embedded == commit, "source archive commit marker differs")
        seen: set[str] = set()
        total_bytes = 0
        for member in members:
            pure = PurePosixPath(member.name)
            require(
                not pure.is_absolute() and ".." not in pure.parts,
                f"unsafe archive member: {member.name}",
            )
            require(member.name not in seen, f"duplicate archive member: {member.name}")
            seen.add(member.name)
            require(member.isdir() or member.isfile(), f"special archive member: {member.name}")
            if not member.isfile():
                continue
            require(member.name.startswith(prefix), f"archive prefix differs: {member.name}")
            relative = member.name[len(prefix) :]
            require(relative.startswith(TOPIC_PREFIX), f"archive file escaped Topic 53: {relative}")
            stream = bundle.extractfile(member)
            require(stream is not None, f"archive file unreadable: {relative}")
            digest = hashlib.sha256()
            with stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            result[relative] = digest.hexdigest()
            total_bytes += member.size
        require(len(result) <= 512 and total_bytes <= 64 * 1024 * 1024, "archive exceeds caps")
    required = {
        PROBE_RELATIVE,
        RUN_HOST_RELATIVE,
        EXPERIMENT_PREFIX + "run_processes.py",
        EXPERIMENT_PREFIX + "analyze.py",
        EXPERIMENT_PREFIX + "validate_receipt.py",
        EXPERIMENT_PREFIX + "test_validate_receipt.py",
        EXPERIMENT_PREFIX + "README.md",
    }
    require(required.issubset(result), "source archive lacks required experiment files")
    return result


def expected_specs(scenario: str) -> list[dict[str, Any]]:
    """Return the frozen fresh-process specification for one scenario."""
    config = SCENARIOS[scenario]
    specs: list[dict[str, Any]] = []
    sequence = 0
    for block, template in enumerate(config["templates"], 1):
        seed = config["seed_base"] + block
        for period, letter in enumerate(template, 1):
            sequence += 1
            treatment = config["treatments"][letter]
            prefix = treatment["label_prefix"]
            specs.append(
                {
                    "scenario": scenario,
                    "sequence": sequence,
                    "block": block,
                    "period": period,
                    "template": template,
                    "letter": letter,
                    "mode": treatment["mode"],
                    "depth": treatment["depth"],
                    "seed": seed,
                    "label": f"{prefix}-b{block:02d}-p{period}",
                }
            )
    return specs


def expected_files(*, sealed: bool) -> set[str]:
    """Return the exact successful receipt file set."""
    files = {
        "provenance.json",
        "source/source.tar.gz",
        "source/source-archive.sha256",
        "source/source-files-before.sha256",
        "source/source-files-after.sha256",
        "source/run-host-match.txt",
        "host/host.json",
        "build/compile.stdout",
        "build/compile.stderr",
        "build/compile.status.json",
        "build/compiler-version.txt",
        "build/identity.txt",
        "bin/nvme_aio_depth_probe",
        "bin/nvme_aio_depth_probe.sha256",
        "bin/file.txt",
        "bin/ldd.txt",
        "bin/readelf.txt",
        "codegen/probe.s",
        "codegen/all.asm",
        "codegen/cached_read_loop.asm",
        "codegen/direct_aio_loop.asm",
        "codegen/symbols.txt",
        "campaign/summary.json",
        "cleanup.json",
    }
    for control in ("init", "verify", "smoke-q1", "smoke-q8"):
        for suffix in ("stdout", "stderr", "status.json"):
            files.add(f"controls/{control}.{suffix}")
    for scenario in SCENARIOS:
        base = f"campaign/{scenario}"
        files.update(
            {
                f"{base}/schedule.json",
                f"{base}/attempt-journal.jsonl",
                f"{base}/attempts.jsonl",
                f"{base}/COMPLETE.json",
            }
        )
        for spec in expected_specs(scenario):
            stem = (
                f"{spec['sequence']:03d}-b{spec['block']:02d}-"
                f"p{spec['period']}-{spec['label']}"
            )
            for suffix in ("before.json", "stdout", "stderr", "after.json", "status.json"):
                files.add(f"{base}/raw/{stem}.{suffix}")
    if sealed:
        files.update({"receipt-validation.json", "MANIFEST.sha256", "SEALED"})
    return files


def validate_tree(root: Path, *, sealed: bool) -> None:
    """Reject links, special files, wrong modes, and file-set drift."""
    require(root.is_dir() and not root.is_symlink(), "receipt root is not a real directory")
    found_files: set[str] = set()
    found_directories: set[str] = set()
    stack = [root]
    while stack:
        directory = stack.pop()
        mode = directory.lstat().st_mode
        if sealed:
            require(mode & WRITE_BITS == 0, f"sealed directory remains writable: {directory}")
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                entry_mode = entry.stat(follow_symlinks=False).st_mode
                require(not stat.S_ISLNK(entry_mode), f"receipt contains symlink: {relative}")
                if stat.S_ISDIR(entry_mode):
                    found_directories.add(relative)
                    stack.append(path)
                elif stat.S_ISREG(entry_mode):
                    if sealed:
                        require(entry_mode & WRITE_BITS == 0, f"sealed file remains writable: {relative}")
                    found_files.add(relative)
                else:
                    fail(f"receipt contains special entry: {relative}")
    expected = expected_files(sealed=sealed)
    require(
        found_files == expected,
        f"receipt file set differs; missing={sorted(expected-found_files)}, "
        f"unexpected={sorted(found_files-expected)}",
    )
    expected_directories = {
        str(parent)
        for relative in expected
        for parent in PurePosixPath(relative).parents
        if str(parent) != "."
    }
    require(
        found_directories == expected_directories,
        "receipt directory set differs",
    )


def validate_provenance(
    root: Path,
    *,
    label: str,
    hostname: str,
    architecture: str,
    commit: str,
    archive_digest: str,
) -> dict[str, Any]:
    """Validate caller, runtime, source, and run-host identities."""
    value = read_json(root / "provenance.json")
    keys = {
        "schema",
        "target_label",
        "expected_hostname",
        "expected_architecture",
        "runtime_hostname",
        "source_commit",
        "source_archive_sha256",
        "source_prefix",
        "topic_prefix",
        "external_run_host_sha256",
        "archived_run_host_sha256",
    }
    require(set(value) == keys, "provenance key set differs")
    expected = {
        "schema": "topic53-provenance.v1",
        "target_label": label,
        "expected_hostname": hostname,
        "expected_architecture": architecture,
        "runtime_hostname": hostname,
        "source_commit": commit,
        "source_archive_sha256": archive_digest,
        "source_prefix": f"systems-snackpack-{commit}/",
        "topic_prefix": TOPIC_PREFIX,
    }
    for key, wanted in expected.items():
        require(value.get(key) == wanted, f"provenance {key} differs")
    external = value["external_run_host_sha256"]
    archived = value["archived_run_host_sha256"]
    require(
        isinstance(external, str)
        and HEX64.fullmatch(external) is not None
        and external == archived,
        "run-host provenance differs",
    )
    return value


def validate_source(
    root: Path,
    *,
    commit: str,
    archive_digest: str,
    provenance: dict[str, Any],
) -> dict[str, str]:
    """Bind both source inventories and run-host copy to the Git archive."""
    source = root / "source"
    archive = source / "source.tar.gz"
    require(sha256(archive) == archive_digest, "retained source archive digest differs")
    require(
        parse_digest_sidecar(source / "source-archive.sha256", "source.tar.gz")
        == archive_digest,
        "source archive sidecar differs",
    )
    archived = archive_inventory(archive, commit)
    before = parse_inventory(source / "source-files-before.sha256")
    after = parse_inventory(source / "source-files-after.sha256")
    require(before == after == archived, "source inventory differs from retained archive")
    require((source / "run-host-match.txt").stat().st_size == 0, "run-host cmp receipt is not empty")
    require(
        archived[RUN_HOST_RELATIVE] == provenance["archived_run_host_sha256"],
        "archived run-host digest differs from provenance",
    )
    return archived


def command_receipt(value: object, name: str) -> dict[str, Any]:
    """Validate one retained host command."""
    require(isinstance(value, dict), f"host command missing: {name}")
    require(set(value) == {"argv", "returncode", "output", "stderr"}, f"{name}: command keys differ")
    require(
        isinstance(value["argv"], list)
        and value["argv"]
        and all(isinstance(item, str) and item for item in value["argv"]),
        f"{name}: argv is invalid",
    )
    require(is_int(value["returncode"]), f"{name}: return code is invalid")
    require(isinstance(value["output"], str) and isinstance(value["stderr"], str), f"{name}: output is invalid")
    return value


def validate_host(
    root: Path,
    *,
    label: str,
    hostname: str,
    architecture: str,
    commit: str,
    archive_digest: str,
) -> dict[str, Any]:
    """Validate live Linux, filesystem, block-stack, and sysfs evidence."""
    host = read_json(root / "host/host.json")
    keys = {
        "schema",
        "target_label",
        "expected_hostname",
        "expected_architecture",
        "runtime_hostname",
        "runtime_architecture",
        "source_commit",
        "source_archive_sha256",
        "page_size",
        "allowed_affinity",
        "data_parent",
        "filesystem_source",
        "filesystem_fstype",
        "filesystem_major_minor",
        "stack_devices",
        "primary_device",
        "commands",
        "files",
        "sysfs",
        "nvme",
        "cgroup",
    }
    require(set(host) == keys, "host key set differs")
    expected = {
        "schema": "topic53-host.v1",
        "target_label": label,
        "expected_hostname": hostname,
        "expected_architecture": architecture,
        "runtime_hostname": hostname,
        "runtime_architecture": architecture,
        "source_commit": commit,
        "source_archive_sha256": archive_digest,
    }
    for key, wanted in expected.items():
        require(host.get(key) == wanted, f"host {key} differs")
    page_size = host["page_size"]
    require(page_size == BLOCK_BYTES, "host page size is not 4096 bytes")
    affinity = host["allowed_affinity"]
    require(
        isinstance(affinity, list)
        and affinity
        and all(is_int(cpu) and cpu >= 0 for cpu in affinity)
        and len(set(affinity)) == len(affinity),
        "host affinity evidence is invalid",
    )
    for key in ("data_parent", "filesystem_source", "filesystem_fstype", "filesystem_major_minor"):
        require(isinstance(host[key], str) and host[key], f"host {key} is missing")
    filesystem_type = host["filesystem_fstype"].lower()
    bad_filesystems = {
        "tmpfs",
        "ramfs",
        "overlay",
        "overlayfs",
        "nfs",
        "nfs4",
        "cifs",
        "9p",
        "virtiofs",
        "fuse",
        "fuseblk",
    }
    require(
        filesystem_type not in bad_filesystems
        and not filesystem_type.startswith("fuse."),
        "data filesystem is not a local block filesystem",
    )
    require(host["filesystem_source"].startswith("/dev/"), "filesystem source is not a block path")
    require(re.fullmatch(r"[0-9]+:[0-9]+", host["filesystem_major_minor"]) is not None, "filesystem major:minor is invalid")

    devices = host["stack_devices"]
    primary = host["primary_device"]
    require(
        isinstance(devices, list)
        and devices
        and len(set(devices)) == len(devices)
        and all(isinstance(device, str) and DEVICE.fullmatch(device) for device in devices)
        and primary in devices,
        "block stack is invalid",
    )
    commands = host["commands"]
    require(isinstance(commands, dict), "host commands are missing")
    command_argv: dict[str, list[str] | None] = {
        "hostname_f": ["hostname", "-f"],
        "uname": ["uname", "-a"],
        "uname_m": ["uname", "-m"],
        "nproc": ["nproc", "--all"],
        "lscpu": ["lscpu"],
        "compiler": ["cc", "--version"],
        "compiler_target": ["cc", "-dumpmachine"],
        "ldd": ["ldd", "--version"],
        "findmnt_data": None,
        "findmnt_tmp": ["findmnt", "-J", "-T", "/tmp"],
        "lsblk_all": [
            "lsblk",
            "-J",
            "-o",
            "NAME,KNAME,TYPE,MAJ:MIN,PKNAME,SIZE,ROTA,SCHED,MODEL,SERIAL,FSTYPE,MOUNTPOINTS",
        ],
        "lsblk_stack": None,
        "virtualization": ["systemd-detect-virt"],
    }
    require(set(commands) == set(command_argv), "host command set differs")
    for name, wanted_argv in command_argv.items():
        receipt = command_receipt(commands[name], name)
        if wanted_argv is not None:
            require(receipt["argv"] == wanted_argv, f"{name}: command argv differs")
        require(receipt["stderr"] == "", f"{name}: command wrote stderr")
        if name == "virtualization":
            require(
                receipt["returncode"] in (0, 1) and bool(receipt["output"]),
                "virtualization command did not report a result",
            )
        else:
            require(
                receipt["returncode"] == 0 and bool(receipt["output"]),
                f"host command failed: {name}",
            )
    data_argv = commands["findmnt_data"]["argv"]
    require(
        data_argv[:3] == ["findmnt", "-J", "-T"]
        and len(data_argv) == 4
        and data_argv[3].startswith(host["data_parent"].rstrip("/") + "/topic53-data."),
        "findmnt data target differs",
    )
    require(
        commands["lsblk_stack"]["argv"]
        == [
            "lsblk",
            "-J",
            "-s",
            "-o",
            "NAME,KNAME,TYPE,MAJ:MIN,PKNAME,SIZE,ROTA,SCHED,MODEL,SERIAL",
            "/dev/" + devices[0],
        ],
        "lsblk stack argv differs",
    )
    require(commands["hostname_f"]["output"].strip() == hostname, "hostname command output differs")
    require(commands["uname_m"]["output"].strip() == architecture, "uname architecture differs")
    require("Linux" in commands["uname"]["output"], "uname does not identify Linux")
    require(commands["compiler_target"]["output"].strip(), "compiler target is empty")
    require(commands["nproc"]["output"].strip().isdigit(), "nproc output is invalid")
    for name in ("findmnt_data", "lsblk_all", "lsblk_stack"):
        parsed = strict_json(commands[name]["output"], f"host command {name}")
        require(isinstance(parsed, dict), f"{name}: output is not a JSON object")
    require(
        host["filesystem_source"] in commands["findmnt_data"]["output"]
        and host["filesystem_fstype"] in commands["findmnt_data"]["output"],
        "findmnt output does not bind the retained filesystem",
    )
    for device in devices:
        require(
            f'"kname":"{device}"' in commands["lsblk_stack"]["output"].replace(" ", ""),
            f"lsblk stack output omits {device}",
        )

    files = host["files"]
    required_files = {
        "proc_cmdline",
        "proc_pressure_io",
        "proc_diskstats",
        "proc_self_cgroup",
        "proc_aio_max_nr",
        "proc_aio_nr",
        "proc_meminfo_selected",
        "proc_vmstat_selected",
        "dmi_product_name",
        "device_tree_model",
    }
    require(isinstance(files, dict) and set(files) == required_files, "host raw file set differs")
    for name, value in files.items():
        require(isinstance(value, str) and bool(value), f"host raw file is empty: {name}")
    require(not files["proc_cmdline"].startswith("unavailable:"), "kernel command line is unavailable")
    require(not files["proc_diskstats"].startswith("unavailable:"), "diskstats is unavailable")
    require(not files["proc_self_cgroup"].startswith("unavailable:"), "process cgroup is unavailable")
    psi_totals(files["proc_pressure_io"])
    for name in ("proc_aio_max_nr", "proc_aio_nr"):
        require(files[name].strip().isdigit(), f"{name}: value is invalid")
    require(int(files["proc_aio_max_nr"].strip()) > 0, "Linux AIO capacity is zero")
    for token in ("MemTotal:", "MemAvailable:", "Cached:", "Dirty:", "Writeback:"):
        require(token in files["proc_meminfo_selected"], f"meminfo omits {token}")
    for token in ("nr_dirty ", "nr_writeback ", "pgpgin ", "pgpgout "):
        require(token in files["proc_vmstat_selected"], f"vmstat omits {token.strip()}")

    sysfs = host["sysfs"]
    require(isinstance(sysfs, dict) and set(sysfs) == set(devices), "sysfs device set differs")
    required_sysfs = {
        "dev",
        "stat",
        "inflight",
        "device/model",
        "device/vendor",
        "device/queue_depth",
        "device_driver",
        "queue/scheduler",
        "queue/nr_requests",
        "queue/logical_block_size",
        "queue/physical_block_size",
        "queue/max_sectors_kb",
        "queue/max_hw_sectors_kb",
        "queue/read_ahead_kb",
        "queue/nomerges",
        "queue/rq_affinity",
        "queue/rotational",
        "queue/write_cache",
        "queue/fua",
        "queue/wbt_lat_usec",
        "queue/io_poll",
    }
    mq_device_count = 0
    for device in devices:
        values = sysfs[device]
        require(isinstance(values, dict), f"{device}: sysfs evidence is missing")
        mq_fields = set(values) - required_sysfs
        require(
            set(values) == required_sysfs | mq_fields
            and all(re.fullmatch(r"mq/[^/]+/(cpu_list|nr_tags|nr_reserved_tags)", key) for key in mq_fields),
            f"{device}: sysfs key set differs",
        )
        for relative in (
            "dev",
            "stat",
            "inflight",
            "queue/scheduler",
            "queue/nr_requests",
            "queue/logical_block_size",
            "queue/physical_block_size",
            "queue/max_sectors_kb",
            "queue/max_hw_sectors_kb",
            "queue/rotational",
        ):
            value = values[relative]
            require(isinstance(value, str) and value and not value.startswith("unavailable:"), f"{device}: {relative} unavailable")
        require(
            all(isinstance(values[key], str) and bool(values[key]) for key in required_sysfs),
            f"{device}: sysfs value is not retained text",
        )
        queues = {key.split("/")[1] for key in mq_fields}
        if queues:
            mq_device_count += 1
        for queue in queues:
            wanted = {
                f"mq/{queue}/cpu_list",
                f"mq/{queue}/nr_tags",
                f"mq/{queue}/nr_reserved_tags",
            }
            require(wanted.issubset(mq_fields), f"{device}: blk-mq queue fields are incomplete")
            for key in wanted:
                require(
                    bool(values[key]) and not values[key].startswith("unavailable:"),
                    f"{device}: {key} unavailable",
                )
    require(mq_device_count > 0, "block stack exposes no retained blk-mq queue")

    nvme = host["nvme"]
    require(isinstance(nvme, dict), "NVMe evidence is not an object")
    nvme_base = {"model", "serial", "firmware_rev", "state", "transport", "address"}
    for controller, values in nvme.items():
        require(
            isinstance(controller, str)
            and re.fullmatch(r"nvme[0-9]+", controller) is not None
            and isinstance(values, dict),
            "NVMe controller evidence is invalid",
        )
        irq_fields = set(values) - nvme_base
        require(
            set(values) == nvme_base | irq_fields
            and all(re.fullmatch(r"msi_irq/[0-9]+/smp_affinity_list", key) for key in irq_fields),
            f"{controller}: NVMe key set differs",
        )
        for key in nvme_base | irq_fields:
            require(isinstance(values[key], str) and bool(values[key]), f"{controller}: {key} is empty")
        for key in ("model", "state", "transport"):
            require(not values[key].startswith("unavailable:"), f"{controller}: NVMe {key} is unavailable")
    primary_match = re.match(r"(nvme[0-9]+)n[0-9]+", str(primary))
    if primary_match is not None:
        require(primary_match.group(1) in nvme, "NVMe primary device lacks its controller evidence")

    cgroup = host["cgroup"]
    require(isinstance(cgroup, dict) and set(cgroup) == {"path", "files"}, "cgroup evidence differs")
    require(isinstance(cgroup["path"], str) and cgroup["path"], "cgroup path is missing")
    cgroup_files = {
        "io.stat",
        "io.max",
        "io.weight",
        "io.pressure",
        "io.cost.qos",
        "io.cost.model",
        "io.latency",
    }
    require(
        isinstance(cgroup["files"], dict) and set(cgroup["files"]) == cgroup_files,
        "cgroup file set differs",
    )
    require(
        all(isinstance(value, str) and bool(value) for value in cgroup["files"].values()),
        "cgroup evidence is not retained text",
    )
    return host


def parse_identity(path: Path) -> dict[str, str]:
    """Parse an exact key=value build identity."""
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        require(bool(separator) and key not in result and bool(value), f"invalid identity line: {line!r}")
        result[key] = value
    return result


def validate_build(
    root: Path,
    source_digest: str,
    architecture: str,
    host: dict[str, Any],
) -> str:
    """Bind compiler, source, binary, and generated-code evidence."""
    compile_stdout = root / "build/compile.stdout"
    compile_stderr = root / "build/compile.stderr"
    status_value = read_json(root / "build/compile.status.json")
    require(
        set(status_value) == {"schema", "argv", "returncode", "stdout_sha256", "stderr_sha256"},
        "compile status key set differs",
    )
    require(status_value["schema"] == "topic53-command-status.v1", "compile status schema differs")
    require(status_value["returncode"] == 0, "compile command failed")
    require(status_value["stdout_sha256"] == sha256(compile_stdout), "compile stdout digest differs")
    require(status_value["stderr_sha256"] == sha256(compile_stderr), "compile stderr digest differs")
    require(compile_stderr.stat().st_size == 0, "compiler emitted stderr")
    require(isinstance(status_value["argv"], list) and "-Werror" in status_value["argv"], "compile command lacks -Werror")

    binary = root / "bin/nvme_aio_depth_probe"
    binary_digest = sha256(binary)
    require(
        parse_digest_sidecar(
            root / "bin/nvme_aio_depth_probe.sha256", "nvme_aio_depth_probe"
        )
        == binary_digest,
        "binary sidecar differs",
    )
    identity = parse_identity(root / "build/identity.txt")
    expected_keys = {
        "source_sha256",
        "binary_sha256",
        "compiler_path",
        "compiler_version_sha256",
        "compiler_target",
        "compile_argv_json",
    }
    require(set(identity) == expected_keys, "build identity key set differs")
    require(identity["source_sha256"] == source_digest, "build source digest differs")
    require(identity["binary_sha256"] == binary_digest, "build binary digest differs")
    compiler_version = root / "build/compiler-version.txt"
    require(
        identity["compiler_version_sha256"] == sha256(compiler_version),
        "compiler version digest differs",
    )
    require(
        compiler_version.read_text(encoding="utf-8")
        == host["commands"]["compiler"]["output"],
        "retained compiler version differs from host capture",
    )
    argv = strict_json(identity["compile_argv_json"], "compile_argv_json")
    require(argv == status_value["argv"], "identity compile argv differs")
    target = identity["compiler_target"]
    if architecture == "x86_64":
        require("x86_64" in target, "compiler target is not x86-64")
    else:
        require(architecture in {"aarch64", "arm64"} and ("aarch64" in target or "arm64" in target), "compiler target is not AArch64")

    require(
        isinstance(identity["compiler_path"], str)
        and identity["compiler_path"].startswith("/")
        and identity["compiler_path"].strip() == identity["compiler_path"],
        "compiler path is invalid",
    )
    require(
        target == host["commands"]["compiler_target"]["output"].strip(),
        "compiler target differs from host capture",
    )
    require(
        status_value["argv"][:8]
        == [
            "cc",
            "-O3",
            "-g",
            "-fno-omit-frame-pointer",
            "-march=native",
            "-std=gnu11",
            "-Wall",
            "-Wextra",
        ]
        and status_value["argv"][8] == "-Werror"
        and len(status_value["argv"]) == 12
        and status_value["argv"][9].endswith("/" + PROBE_RELATIVE)
        and status_value["argv"][10] == "-o"
        and status_value["argv"][11].endswith("/bin/nvme_aio_depth_probe"),
        "compile argv differs from the frozen build",
    )

    for relative in ("bin/file.txt", "bin/ldd.txt", "bin/readelf.txt"):
        require((root / relative).stat().st_size > 0, f"empty binary identity: {relative}")
    require(os.access(binary, os.X_OK), "retained probe is not executable")
    file_text = (root / "bin/file.txt").read_text(encoding="utf-8", errors="replace")
    ldd_text = (root / "bin/ldd.txt").read_text(encoding="utf-8", errors="replace")
    require("ELF" in file_text, "file output does not identify an ELF binary")
    require("not found" not in ldd_text, "binary has an unresolved dynamic dependency")
    readelf = (root / "bin/readelf.txt").read_text(encoding="utf-8", errors="replace")
    if architecture == "x86_64":
        require("X86-64" in readelf or "x86-64" in readelf, "ELF machine is not x86-64")
    else:
        require("AArch64" in readelf, "ELF machine is not AArch64")

    symbols = (root / "codegen/symbols.txt").read_text(encoding="utf-8", errors="replace")
    all_assembly = (root / "codegen/all.asm").read_text(encoding="utf-8", errors="replace")
    source_assembly = (root / "codegen/probe.s").read_text(encoding="utf-8", errors="replace")
    for symbol in ("cached_read_loop", "direct_aio_loop"):
        focused = (root / f"codegen/{symbol}.asm").read_text(encoding="utf-8", errors="replace")
        require(symbol in symbols and symbol in all_assembly and symbol in focused and symbol in source_assembly, f"codegen lacks {symbol}")
    require("io_submit" in source_assembly or "SYS_io_submit" in source_assembly or "syscall" in all_assembly, "codegen lacks syscall submission path")
    return binary_digest


def mix64(value: int) -> int:
    """Mirror the fixed 64-bit content generator."""
    mask = (1 << 64) - 1
    value = (value + 0x9E3779B97F4A7C15) & mask
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
    return (value ^ (value >> 31)) & mask


def expected_word(block: int, word: int) -> int:
    """Return one expected nonzero file word."""
    mask = (1 << 64) - 1
    value = mix64(block ^ ((word * 0xD6E8FEB86659FD93) & mask))
    return 0x6A09E667F3BCC909 if value == 0 else value


def expected_checksum(operations: int, blocks: int, seed: int) -> int:
    """Recompute the probe's order-independent sampled checksum."""
    checksum = 0
    for operation in range(operations):
        block = ((operation * 0xD1342543DE82EF95) + seed) & (blocks - 1)
        sample = mix64(block)
        for word in (0, BLOCK_BYTES // 16, BLOCK_BYTES // 8 - 1):
            sample ^= expected_word(block, word)
        checksum ^= sample
    return checksum


def validate_bench(
    value: dict[str, Any],
    *,
    pid: int | None,
    label: str,
    depth: int,
    operations: int,
    seed: int,
) -> None:
    """Validate one native direct-AIO measurement independently."""
    require(set(value) == RESULT_KEYS, f"{label}: probe result key set differs")
    blocks = DATA_FILE_BYTES // BLOCK_BYTES
    expected = {
        "schema": "topic53-probe.v1",
        "kind": "bench",
        "status": "ok",
        "mode": "direct",
        "label": label,
        "seed": seed,
        "depth": depth,
        "total_ops": operations,
        "bytes": operations * BLOCK_BYTES,
        "blocks": blocks,
        "read_bytes_delta": operations * BLOCK_BYTES,
        "verified_reads": operations,
        "errors": 0,
        "checksum": expected_checksum(operations, blocks, seed),
        "peak_outstanding": depth,
        "resident_before": 0,
        "resident_after": 0,
        "total_pages": 0,
        "dioalign_known": 1,
        "threads_before": 1,
        "threads_after": 1,
    }
    if pid is not None:
        expected.update({"pid": pid, "tid": pid})
    else:
        require(is_int(value["pid"]) and value["pid"] > 0 and value["tid"] == value["pid"], f"{label}: pid/tid differs")
    for key, wanted in expected.items():
        require(value.get(key) == wanted, f"{label}: {key} differs")
    for key in ("startup_to_measure_ns", "setup_ns", "elapsed_ns"):
        require(is_int(value[key]) and value[key] > 0, f"{label}: {key} is invalid")
    require(value["startup_to_measure_ns"] >= value["setup_ns"], f"{label}: setup exceeds startup")
    expected_iops = operations * 1e9 / value["elapsed_ns"]
    expected_mib = operations * BLOCK_BYTES * 1e9 / value["elapsed_ns"] / (1024**2)
    require(is_number(value["iops"]) and math.isclose(value["iops"], expected_iops, rel_tol=1e-8, abs_tol=5.1e-7), f"{label}: IOPS does not rederive")
    require(is_number(value["mib_s"]) and math.isclose(value["mib_s"], expected_mib, rel_tol=1e-8, abs_tol=5.1e-7), f"{label}: MiB/s does not rederive")
    memory = value["dio_mem_align"]
    offset = value["dio_offset_align"]
    allocation = value["dio_allocation_align"]
    require(
        is_int(memory)
        and memory > 0
        and is_int(offset)
        and offset > 0
        and is_int(allocation)
        and allocation >= memory
        and allocation & (allocation - 1) == 0
        and BLOCK_BYTES % offset == 0,
        f"{label}: direct-I/O alignment is invalid",
    )
    for key in ("nvcsw", "nivcsw"):
        require(is_int(value[key]) and value[key] >= 0, f"{label}: {key} is invalid")


def validate_control(root: Path, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate one hashed control invocation and its native output."""
    stdout = root / f"controls/{name}.stdout"
    stderr = root / f"controls/{name}.stderr"
    status_value = read_json(root / f"controls/{name}.status.json")
    require(
        set(status_value) == {"schema", "name", "argv", "returncode", "stdout_sha256", "stderr_sha256"},
        f"{name}: control status key set differs",
    )
    require(status_value["schema"] == "topic53-control-status.v1" and status_value["name"] == name, f"{name}: control identity differs")
    require(status_value["returncode"] == 0, f"{name}: control failed or was unsupported")
    require(status_value["stdout_sha256"] == sha256(stdout), f"{name}: stdout digest differs")
    require(status_value["stderr_sha256"] == sha256(stderr), f"{name}: stderr digest differs")
    require(stderr.stat().st_size == 0, f"{name}: stderr is not empty")
    require(isinstance(status_value["argv"], list) and status_value["argv"], f"{name}: argv is invalid")
    return status_value, read_json_line(stdout)


def validate_controls(root: Path) -> None:
    """Require file integrity and direct q1/q8 capability controls."""
    init_status, init = validate_control(root, "init")
    require(
        set(init) == {"schema", "kind", "status", "bytes", "blocks", "elapsed_ns"}
        and init["schema"] == "topic53-probe.v1"
        and init["kind"] == "init"
        and init["status"] == "ok"
        and init["bytes"] == DATA_FILE_BYTES
        and init["blocks"] == DATA_FILE_BYTES // BLOCK_BYTES
        and is_int(init["elapsed_ns"])
        and init["elapsed_ns"] > 0,
        "init control differs",
    )
    verify_status, verify = validate_control(root, "verify")
    require(
        set(verify)
        == {"schema", "kind", "status", "bytes", "blocks", "elapsed_ns", "read_bytes_delta", "verified_reads"}
        and verify["schema"] == "topic53-probe.v1"
        and verify["kind"] == "verify"
        and verify["status"] == "ok"
        and verify["bytes"] == DATA_FILE_BYTES
        and verify["blocks"] == DATA_FILE_BYTES // BLOCK_BYTES
        and verify["verified_reads"] == DATA_FILE_BYTES // BLOCK_BYTES
        and is_int(verify["elapsed_ns"])
        and verify["elapsed_ns"] > 0
        and is_int(verify["read_bytes_delta"])
        and verify["read_bytes_delta"] >= 0,
        "full-file verification control differs",
    )
    init_argv = init_status["argv"]
    verify_argv = verify_status["argv"]
    require(
        len(init_argv) == 4
        and init_argv[1] == "init"
        and init_argv[3] == "128"
        and len(verify_argv) == 3
        and verify_argv[1] == "verify"
        and init_argv[0] == verify_argv[0]
        and init_argv[2] == verify_argv[2]
        and init_argv[0].endswith("/bin/nvme_aio_depth_probe")
        and init_argv[2].endswith("/data.bin"),
        "init/verify control argv differs",
    )
    for name, depth in (("smoke-q1", 1), ("smoke-q8", 8)):
        status_value, observed = validate_control(root, name)
        validate_bench(
            observed,
            pid=None,
            label=name,
            depth=depth,
            operations=256,
            seed=530001,
        )
        argv = status_value["argv"]
        require(
            len(argv) == 8
            and argv[0] == init_argv[0]
            and argv[1] == "run"
            and argv[2] == init_argv[2]
            and argv[3:] == ["direct", "256", str(depth), "530001", name],
            f"{name}: control argv differs",
        )


def psi_totals(text: str) -> dict[str, int]:
    """Parse PSI some/full cumulative microseconds."""
    result: dict[str, int] = {}
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        total = next((field[6:] for field in fields[1:] if field.startswith("total=")), None)
        require(total is not None and total.isdigit(), "pressure line lacks a valid total")
        result[fields[0]] = int(total)
    require(set(result) == {"some", "full"}, "pressure data lacks some/full")
    return result


def diskstats(text: str) -> dict[str, list[int]]:
    """Parse retained /proc/diskstats device counters."""
    result: dict[str, list[int]] = {}
    for line in text.splitlines():
        fields = line.split()
        require(len(fields) >= 14, "diskstats line has too few fields")
        device = fields[2]
        require(
            DEVICE.fullmatch(device) is not None and device not in result,
            "diskstats device name is invalid or duplicated",
        )
        try:
            counters = [int(field) for field in fields[3:]]
        except ValueError as error:
            fail(f"diskstats counter is invalid: {error}")
        require(all(value >= 0 for value in counters), "diskstats counter is negative")
        result[device] = counters
    require(bool(result), "diskstats is empty")
    return result


def validate_snapshot(value: dict[str, Any], phase: str, devices: list[str]) -> None:
    """Validate one exact counter snapshot."""
    require(set(value) == SNAPSHOT_KEYS, f"{phase}: snapshot key set differs")
    require(value["schema"] == "topic53-snapshot.v1" and value["phase"] == phase, f"{phase}: snapshot identity differs")
    for key in ("wall_time_ns", "monotonic_ns"):
        require(is_int(value[key]) and value[key] > 0, f"{phase}: {key} is invalid")
    for key in ("proc_diskstats", "proc_pressure_io", "cgroup_path", "cgroup_io_stat", "cgroup_io_pressure"):
        require(isinstance(value[key], str) and bool(value[key]), f"{phase}: {key} is empty")
    require(value["proc_diskstats"].endswith("\n") and value["proc_pressure_io"].endswith("\n"), f"{phase}: raw proc capture is partial")
    psi_totals(value["proc_pressure_io"])
    proc_devices = diskstats(value["proc_diskstats"])
    require(isinstance(value["proc_vmstat"], dict) and set(value["proc_vmstat"]) == set(VMSTAT_KEYS), f"{phase}: vmstat differs")
    require(all(is_int(item) and item >= 0 for item in value["proc_vmstat"].values()), f"{phase}: vmstat value is invalid")
    observed_devices = value["devices"]
    require(isinstance(observed_devices, dict) and set(observed_devices) == set(devices), f"{phase}: device set differs")
    for device in devices:
        evidence = observed_devices[device]
        require(isinstance(evidence, dict) and set(evidence) == {"stat", "inflight"}, f"{phase}/{device}: counter keys differ")
        require(isinstance(evidence["stat"], list) and len(evidence["stat"]) >= 11 and all(is_int(item) and item >= 0 for item in evidence["stat"]), f"{phase}/{device}: stat counters are invalid")
        require(isinstance(evidence["inflight"], list) and len(evidence["inflight"]) == 2 and all(is_int(item) and item >= 0 for item in evidence["inflight"]), f"{phase}/{device}: inflight counters are invalid")
        require(
            device in proc_devices
            and len(proc_devices[device]) == len(evidence["stat"])
            and all(
                field == 8 or sysfs_value >= proc_value
                for field, (proc_value, sysfs_value) in enumerate(
                    zip(proc_devices[device], evidence["stat"])
                )
            ),
            f"{phase}/{device}: sysfs stat predates or differs from /proc/diskstats",
        )


def derive_deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Independently derive retained device, PSI, and VM deltas."""
    devices: dict[str, Any] = {}
    for device in before["devices"]:
        before_device = before["devices"][device]
        after_device = after["devices"][device]
        require(len(before_device["stat"]) == len(after_device["stat"]), f"{device}: stat field count changed")
        devices[device] = {
            "stat": [right - left for left, right in zip(before_device["stat"], after_device["stat"])],
            "inflight": [right - left for left, right in zip(before_device["inflight"], after_device["inflight"])],
        }
    before_psi = psi_totals(before["proc_pressure_io"])
    after_psi = psi_totals(after["proc_pressure_io"])
    return {
        "devices": devices,
        "psi_total_us": {key: after_psi[key] - before_psi[key] for key in ("some", "full")},
        "vmstat": {key: after["proc_vmstat"][key] - before["proc_vmstat"][key] for key in VMSTAT_KEYS},
    }


def validate_schedule(
    path: Path,
    scenario: str,
    source_digest: str,
    binary_digest: str,
    host: dict[str, Any],
) -> dict[str, Any]:
    """Validate one fixed campaign schedule."""
    schedule = read_json(path)
    keys = {
        "schema",
        "scenario",
        "templates",
        "treatments",
        "seed_base",
        "blocks",
        "processes_per_block",
        "ops_per_process",
        "block_bytes",
        "data_file_bytes",
        "source_sha256",
        "binary_sha256",
        "devices",
        "primary_device",
        "treatment_application_unit",
        "analysis_unit",
        "subsample_unit",
        "stopping",
    }
    require(set(schedule) == keys, f"{scenario}: schedule key set differs")
    config = SCENARIOS[scenario]
    expected = {
        "schema": "topic53-schedule.v1",
        "scenario": scenario,
        "templates": list(config["templates"]),
        "treatments": config["treatments"],
        "seed_base": config["seed_base"],
        "blocks": 8,
        "processes_per_block": 4,
        "block_bytes": BLOCK_BYTES,
        "data_file_bytes": DATA_FILE_BYTES,
        "source_sha256": source_digest,
        "binary_sha256": binary_digest,
        "devices": host["stack_devices"],
        "primary_device": host["primary_device"],
        "treatment_application_unit": "fresh native process",
        "analysis_unit": "complete four-process block",
        "subsample_unit": "one verified 4 KiB O_DIRECT read",
        "stopping": "fixed horizon; stop after first invalid attempt",
    }
    for key, wanted in expected.items():
        require(schedule.get(key) == wanted, f"{scenario}: schedule {key} differs")
    operations = schedule["ops_per_process"]
    require(is_int(operations) and 256 <= operations <= DATA_FILE_BYTES // BLOCK_BYTES, f"{scenario}: operation count is invalid")
    return schedule


def validate_campaign(
    root: Path,
    scenario: str,
    source_digest: str,
    binary_digest: str,
    host: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Validate all raw processes, counters, journals, and completion proof."""
    directory = root / "campaign" / scenario
    schedule = validate_schedule(
        directory / "schedule.json", scenario, source_digest, binary_digest, host
    )
    operations = schedule["ops_per_process"]
    attempts = read_jsonl(directory / "attempts.jsonl")
    specs = expected_specs(scenario)
    require(len(attempts) == len(specs) == 32, f"{scenario}: process count differs")
    journal = read_jsonl(directory / "attempt-journal.jsonl")
    require(len(journal) == 64, f"{scenario}: journal record count differs")
    pids: set[int] = set()

    for index, (row, spec) in enumerate(zip(attempts, specs)):
        require(set(row) == STATUS_KEYS | ATTEMPT_PATH_KEYS, f"{scenario}: attempt key set differs")
        expected_status = {
            "schema": "topic53-attempt.v1",
            **spec,
            "ops": operations,
            "source_sha256": source_digest,
            "binary_sha256": binary_digest,
            "returncode": 0,
            "timed_out": False,
            "valid": True,
            "validation_errors": [],
        }
        for key, wanted in expected_status.items():
            require(row.get(key) == wanted, f"{scenario} attempt {spec['sequence']}: {key} differs")
        pid = row["pid"]
        require(is_int(pid) and pid > 0 and pid not in pids, f"{scenario}: invalid or reused pid")
        pids.add(pid)
        require(is_int(row["wall_elapsed_ns"]) and row["wall_elapsed_ns"] > 0, f"{scenario}: wall duration is invalid")

        stem = f"{spec['sequence']:03d}-b{spec['block']:02d}-p{spec['period']}-{spec['label']}"
        expected_paths = {
            "before_file": f"raw/{stem}.before.json",
            "stdout_file": f"raw/{stem}.stdout",
            "stderr_file": f"raw/{stem}.stderr",
            "after_file": f"raw/{stem}.after.json",
            "status_file": f"raw/{stem}.status.json",
        }
        for key, wanted in expected_paths.items():
            require(row[key] == wanted, f"{scenario} attempt {spec['sequence']}: {key} differs")
        before_path = safe_file(directory, row["before_file"])
        stdout_path = safe_file(directory, row["stdout_file"])
        stderr_path = safe_file(directory, row["stderr_file"])
        after_path = safe_file(directory, row["after_file"])
        status_path = safe_file(directory, row["status_file"])
        require(row["before_sha256"] == sha256(before_path), f"{scenario}: before digest differs")
        require(row["stdout_sha256"] == sha256(stdout_path), f"{scenario}: stdout digest differs")
        require(row["stderr_sha256"] == sha256(stderr_path), f"{scenario}: stderr digest differs")
        require(row["after_sha256"] == sha256(after_path), f"{scenario}: after digest differs")
        require(stderr_path.stat().st_size == 0, f"{scenario}: native stderr is not empty")

        status_value = read_json(status_path)
        require(set(status_value) == STATUS_KEYS, f"{scenario}: raw status key set differs")
        expected_raw_status = {key: row[key] for key in STATUS_KEYS}
        expected_raw_status["schema"] = "topic53-attempt-status.v1"
        require(same(status_value, expected_raw_status), f"{scenario}: status differs from attempt row")
        observed = read_json_line(stdout_path)
        require(same(observed, row["observed"]), f"{scenario}: parsed observation differs from stdout")
        validate_bench(
            observed,
            pid=pid,
            label=spec["label"],
            depth=spec["depth"],
            operations=operations,
            seed=spec["seed"],
        )
        require(row["wall_elapsed_ns"] >= observed["elapsed_ns"], f"{scenario}: process wall time is shorter than measurement")

        before = read_json(before_path)
        after = read_json(after_path)
        validate_snapshot(before, "before", schedule["devices"])
        validate_snapshot(after, "after", schedule["devices"])
        require(
            before["cgroup_path"] == after["cgroup_path"] == host["cgroup"]["path"],
            f"{scenario}: cgroup path changed or differs from host metadata",
        )
        require(after["monotonic_ns"] > before["monotonic_ns"], f"{scenario}: snapshot monotonic time did not advance")
        require(after["wall_time_ns"] > before["wall_time_ns"], f"{scenario}: snapshot wall time did not advance")
        deltas = derive_deltas(before, after)
        require(same(deltas, row["counter_deltas"]), f"{scenario}: retained counter deltas do not rederive")
        for device, evidence in deltas["devices"].items():
            for field, delta in enumerate(evidence["stat"]):
                if field != 8:
                    require(delta >= 0, f"{scenario}/{device}: cumulative counter moved backward")
        for key in ("some", "full"):
            require(deltas["psi_total_us"][key] >= 0, f"{scenario}: PSI moved backward")
        primary_delta = deltas["devices"][schedule["primary_device"]]["stat"]
        require(primary_delta[0] > 0, f"{scenario}: primary device completed no reads")
        require(
            primary_delta[2] >= observed["bytes"] // 512,
            f"{scenario}: primary-device sector accounting is below requested direct reads",
        )

        planned = journal[index * 2]
        completed = journal[index * 2 + 1]
        require(
            set(planned)
            == {"event", "scenario", "sequence", "block", "period", "template", "letter", "mode", "depth", "seed", "label", "ops"},
            f"{scenario}: planned journal keys differ",
        )
        require(planned == {"event": "planned", **spec, "ops": operations}, f"{scenario}: planned journal differs")
        require(
            set(completed)
            == {"event", "scenario", "sequence", "returncode", "timed_out", "valid", "status_file", "status_sha256"},
            f"{scenario}: completed journal keys differ",
        )
        expected_completed = {
            "event": "completed",
            "scenario": scenario,
            "sequence": spec["sequence"],
            "returncode": 0,
            "timed_out": False,
            "valid": True,
            "status_file": row["status_file"],
            "status_sha256": sha256(status_path),
        }
        require(completed == expected_completed, f"{scenario}: completed journal differs")

    complete = read_json(directory / "COMPLETE.json")
    expected_complete = {
        "schema": "topic53-scenario-complete.v1",
        "scenario": scenario,
        "attempt_count": 32,
        "unique_pid_count": 32,
        "complete_block_count": 8,
        "invalid_attempt_count": 0,
        "source_sha256": source_digest,
        "binary_sha256": binary_digest,
    }
    require(complete == expected_complete, f"{scenario}: completion receipt differs")
    return schedule, attempts


def distribution(values: list[float]) -> dict[str, float | int]:
    """Mirror the compact analyzer distribution."""
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "max": ordered[-1],
    }


def independent_scenario_analysis(
    scenario: str, schedule: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Recompute the block-level estimate without importing analyze.py."""
    config = SCENARIOS[scenario]
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["block"], []).append(row)
    left_rates: list[float] = []
    right_rates: list[float] = []
    contrasts: list[dict[str, Any]] = []
    for block, template in enumerate(config["templates"], 1):
        block_rows = sorted(grouped[block], key=lambda row: row["period"])
        left: list[float] = []
        right: list[float] = []
        for row in block_rows:
            rate = float(row["observed"]["iops"])
            if row["letter"] == config["left"]:
                left.append(rate)
                left_rates.append(rate)
            else:
                right.append(rate)
                right_rates.append(rate)
        left_geomean = math.exp(statistics.mean(math.log(value) for value in left))
        right_geomean = math.exp(statistics.mean(math.log(value) for value in right))
        log_ratio = math.log(right_geomean) - math.log(left_geomean)
        contrasts.append(
            {
                "block": block,
                "template": template,
                "left_geomean_iops": left_geomean,
                "right_geomean_iops": right_geomean,
                "log_ratio": log_ratio,
                "right_over_left": math.exp(log_ratio),
            }
        )
    logs = [item["log_ratio"] for item in contrasts]
    mean_log = statistics.mean(logs)
    log_sd = statistics.stdev(logs)
    half = T975_DF7 * log_sd / math.sqrt(len(logs))
    return {
        "scenario": scenario,
        "ratio_name": config["ratio"],
        "fresh_process_count": 32,
        "whole_block_count": 8,
        "total_ops_per_process": schedule["ops_per_process"],
        "bytes_per_process": schedule["ops_per_process"] * BLOCK_BYTES,
        "point_ratio": math.exp(mean_log),
        "ratio_95pct_student_t_interval": [
            math.exp(mean_log - half),
            math.exp(mean_log + half),
        ],
        "log_contrast_sd": log_sd,
        "left_iops": distribution(left_rates),
        "right_iops": distribution(right_rates),
        "block_contrasts": contrasts,
    }


def validate_analysis(
    root: Path,
    campaigns: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]],
) -> dict[str, Any]:
    """Independently recompute and validate the retained analysis."""
    scenarios = {
        name: independent_scenario_analysis(name, schedule, rows)
        for name, (schedule, rows) in campaigns.items()
    }
    interval = scenarios["aa"]["ratio_95pct_student_t_interval"]
    point = scenarios["aa"]["point_ratio"]
    acceptance = {
        "point_ratio_within_0_95_to_1_05": 0.95 <= point <= 1.05,
        "interval_contains_1": interval[0] <= 1.0 <= interval[1],
        "interval_within_0_90_to_1_10": 0.90 <= interval[0] and interval[1] <= 1.10,
    }
    expected = {
        "schema": "topic53-analysis.v1",
        "method": (
            "mean complete-block log IOPS ratio with a two-sided 95% "
            "Student-t interval across eight whole-process blocks"
        ),
        "interval_scope": (
            "between-block process variation on one host, source, binary, kernel, "
            "filesystem, block stack, and run window; excludes host-population and "
            "device-population variation"
        ),
        "analysis_unit": "whole four-process block; inner reads are not samples",
        "aa_acceptance": acceptance,
        "aa_control_pass": all(acceptance.values()),
        "measurement_usable": all(acceptance.values()),
        "scenarios": scenarios,
    }
    retained = read_json(root / "campaign/summary.json")
    require(same(retained, expected), "retained analysis does not independently rederive")
    require(expected["measurement_usable"] is True, "A/A precision or centering control failed")
    return expected


def validate_cleanup(root: Path) -> None:
    """Require deletion of only the task-owned data file and directory."""
    cleanup = read_json(root / "cleanup.json")
    require(
        cleanup
        == {
            "schema": "topic53-cleanup.v1",
            "removed_files": ["data.bin"],
            "data_directory_removed": True,
        },
        "cleanup receipt differs",
    )


def parse_manifest(path: Path) -> dict[str, str]:
    """Parse the sorted sealed-receipt manifest."""
    result: dict[str, str] = {}
    previous = ""
    text = path.read_text(encoding="utf-8")
    require(bool(text) and text.endswith("\n"), "manifest is empty or partial")
    for line in text.splitlines():
        digest, separator, relative = line.partition("  ")
        pure = PurePosixPath(relative)
        require(
            bool(separator)
            and HEX64.fullmatch(digest) is not None
            and not pure.is_absolute()
            and ".." not in pure.parts
            and relative not in result
            and relative > previous,
            f"malformed, unsafe, duplicate, or unsorted manifest line: {line}",
        )
        result[relative] = digest
        previous = relative
    require(bool(result), "manifest is empty")
    return result


def validate_manifest(root: Path) -> str:
    """Require manifest coverage and hashes for every non-self regular file."""
    manifest_path = root / "MANIFEST.sha256"
    manifest = parse_manifest(manifest_path)
    expected = expected_files(sealed=True) - {"MANIFEST.sha256", "SEALED"}
    require(set(manifest) == expected, "manifest coverage differs")
    for relative, digest in manifest.items():
        require(sha256(safe_file(root, relative)) == digest, f"manifest digest differs: {relative}")
    require((root / "SEALED").read_text(encoding="utf-8") == "topic53-receipt.v1\n", "SEALED marker differs")
    return sha256(manifest_path)


def validation_summary(
    *,
    sealed: bool,
    label: str,
    hostname: str,
    architecture: str,
    commit: str,
    archive_digest: str,
    source_digest: str,
    binary_digest: str,
    host: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    """Return the stable unsealed validation certificate."""
    return {
        "schema": "topic53-receipt-validation.v1",
        "pass": True,
        "sealed": sealed,
        "target_label": label,
        "runtime_hostname": hostname,
        "architecture": architecture,
        "source_commit": commit,
        "source_archive_sha256": archive_digest,
        "probe_source_sha256": source_digest,
        "binary_sha256": binary_digest,
        "filesystem_source": host["filesystem_source"],
        "filesystem_fstype": host["filesystem_fstype"],
        "stack_devices": host["stack_devices"],
        "primary_device": host["primary_device"],
        "depth_process_count": 32,
        "aa_process_count": 32,
        "complete_block_count_per_scenario": 8,
        "aa_acceptance": analysis["aa_acceptance"],
        "measurement_usable": analysis["measurement_usable"],
    }


def validate(
    root: Path,
    *,
    expected_label: str,
    expected_hostname: str,
    expected_architecture: str,
    expected_commit: str,
    expected_archive_sha256: str,
    allow_unsealed: bool,
) -> dict[str, Any]:
    """Validate one complete unsealed or sealed Topic 53 receipt."""
    root = root.resolve(strict=True)
    require(HEX40.fullmatch(expected_commit) is not None, "expected commit is invalid")
    require(HEX64.fullmatch(expected_archive_sha256) is not None, "expected archive digest is invalid")
    validate_tree(root, sealed=not allow_unsealed)
    provenance = validate_provenance(
        root,
        label=expected_label,
        hostname=expected_hostname,
        architecture=expected_architecture,
        commit=expected_commit,
        archive_digest=expected_archive_sha256,
    )
    sources = validate_source(
        root,
        commit=expected_commit,
        archive_digest=expected_archive_sha256,
        provenance=provenance,
    )
    source_digest = sources[PROBE_RELATIVE]
    host = validate_host(
        root,
        label=expected_label,
        hostname=expected_hostname,
        architecture=expected_architecture,
        commit=expected_commit,
        archive_digest=expected_archive_sha256,
    )
    binary_digest = validate_build(
        root, source_digest, expected_architecture, host
    )
    validate_controls(root)
    campaigns = {
        scenario: validate_campaign(
            root, scenario, source_digest, binary_digest, host
        )
        for scenario in ("depth", "aa")
    }
    analysis = validate_analysis(root, campaigns)
    validate_cleanup(root)
    unsealed_summary = validation_summary(
        sealed=False,
        label=expected_label,
        hostname=expected_hostname,
        architecture=expected_architecture,
        commit=expected_commit,
        archive_digest=expected_archive_sha256,
        source_digest=source_digest,
        binary_digest=binary_digest,
        host=host,
        analysis=analysis,
    )
    if allow_unsealed:
        return unsealed_summary
    retained_validation = read_json(root / "receipt-validation.json")
    require(same(retained_validation, unsealed_summary), "retained unsealed validation certificate differs")
    manifest_digest = validate_manifest(root)
    return {
        **unsealed_summary,
        "sealed": True,
        "manifest_sha256": manifest_digest,
    }


def main() -> int:
    """Parse command-line identities and validate one receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--expected-label", required=True)
    parser.add_argument("--expected-hostname", required=True)
    parser.add_argument("--expected-architecture", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument("--allow-unsealed", action="store_true")
    arguments = parser.parse_args()
    result = validate(
        arguments.receipt,
        expected_label=arguments.expected_label,
        expected_hostname=arguments.expected_hostname,
        expected_architecture=arguments.expected_architecture,
        expected_commit=arguments.expected_commit,
        expected_archive_sha256=arguments.expected_archive_sha256,
        allow_unsealed=arguments.allow_unsealed,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, tarfile.TarError) as error:
        print(f"validate_receipt.py: {error}", file=os.sys.stderr)
        raise SystemExit(1) from error
