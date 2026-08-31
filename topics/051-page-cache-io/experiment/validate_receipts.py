#!/usr/bin/env python3
"""Validate a complete Topic 51 host receipt without importing the runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import stat
import statistics
import struct
import tarfile
from typing import Any, NoReturn


FILE_BYTES = 16 * 1024 * 1024
WRITE_BYTES = 4 * 1024 * 1024
PAGE_BYTES = 4096
SCENARIOS = {
    "primary": {
        "seed": 510101,
        "templates": ("ABBA", "BAAB", "ABBA", "BAAB", "BAAB", "ABBA", "BAAB", "ABBA"),
        "treatments": {"A": ("buf_seq", "seq"), "B": ("buf_random", "random")},
        "t975": 2.364624251,
    },
    "aa": {
        "seed": 510102,
        "templates": ("XYYX", "YXXY", "XYYX", "YXXY", "YXXY", "XYYX", "YXXY", "XYYX"),
        "treatments": {"X": ("buf_seq", "aa_x"), "Y": ("buf_seq", "aa_y")},
        "t975": 2.364624251,
    },
    "direct": {
        "seed": 510103,
        "templates": ("ABBA", "BAAB", "BAAB", "ABBA"),
        "treatments": {"A": ("buf_seq", "buffered"), "B": ("direct_seq", "direct")},
        "t975": 3.182446305,
    },
}


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def reject_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            fail(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def reject_constant(token: str) -> NoReturn:
    fail(f"non-finite JSON number: {token}")


def parse_json(text: str, label: str) -> dict[str, Any]:
    value = json.loads(text, object_pairs_hook=reject_pairs, parse_constant=reject_constant)
    if not isinstance(value, dict):
        fail(f"{label}: expected one JSON object")
    return value


def read_json(path: Path) -> dict[str, Any]:
    return parse_json(path.read_text(encoding="utf-8"), str(path))


def read_json_line(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n") or len(text.splitlines()) != 1:
        fail(f"{path}: expected one newline-terminated JSON object")
    return parse_json(text, str(path))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if not line.endswith("\n") or not line.strip():
                fail(f"{path}:{number}: partial or blank JSONL record")
            rows.append(parse_json(line, f"{path}:{number}"))
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def exact_path(root: Path, relative: object) -> Path:
    require(isinstance(relative, str), "receipt path is not a string")
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and ".." not in pure.parts, f"unsafe receipt path: {relative}")
    unresolved = root / pure
    require(not unresolved.is_symlink(), f"receipt path is a symlink: {relative}")
    path = unresolved.resolve(strict=True)
    require(path.is_relative_to(root), f"receipt path escaped root: {relative}")
    require(path.is_file() and not path.is_symlink(), f"receipt path is not a regular file: {relative}")
    return path


def verify_source(
    root: Path, expected_commit: str, expected_archive_sha256: str
) -> dict[str, int]:
    archive = root / "source-archive.tar.gz"
    require(sha256(archive) == expected_archive_sha256, "source archive digest differs")
    topic_prefix = f"systems-snackpack-{expected_commit}/topics/051-page-cache-io/"
    required = {
        topic_prefix + "experiment/README.md",
        topic_prefix + "experiment/pcbench.c",
        topic_prefix + "experiment/run_processes.py",
        topic_prefix + "experiment/analyze.py",
        topic_prefix + "experiment/validate_receipts.py",
        topic_prefix + "experiment/run_host.sh",
    }
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        embedded = bundle.pax_headers.get("comment")
        if embedded is None:
            embedded = next(
                (item.pax_headers.get("comment") for item in members if item.pax_headers.get("comment")),
                None,
            )
        require(embedded == expected_commit, "archive commit marker differs")
        names: set[str] = set()
        files: set[str] = set()
        total_bytes = 0
        for member in members:
            pure = PurePosixPath(member.name)
            require(member.name not in names, f"duplicate archive member: {member.name}")
            require(not pure.is_absolute() and ".." not in pure.parts, "unsafe archive path")
            require(member.isdir() or member.isfile(), f"special archive member: {member.name}")
            names.add(member.name)
            if member.isfile():
                require(member.name.startswith(topic_prefix), "archive file escaped Topic 51")
                files.add(member.name)
                total_bytes += member.size
        require(required.issubset(files), "archive lacks required experiment files")
        require(len(files) <= 256 and total_bytes <= 32 * 1024 * 1024, "archive exceeds caps")

    before = (root / "source-manifest-before.sha256").read_bytes()
    after = (root / "source-manifest-after.sha256").read_bytes()
    frozen = (root / "source-files.sha256").read_bytes()
    require(before == after == frozen, "source manifests differ")
    require((root / "source-manifest.diff").stat().st_size == 0, "source manifest diff is not empty")
    return {"archive_file_count": len(files), "archive_uncompressed_bytes": total_bytes}


def verify_host(
    root: Path,
    expected_label: str,
    expected_hostname: str,
    expected_architecture: str,
    expected_commit: str,
    expected_archive_sha256: str,
) -> dict[str, Any]:
    host = read_json(root / "host.json")
    require(host.get("schema") == "topic51-host.v1", "host schema differs")
    expected = {
        "target_label": expected_label,
        "expected_hostname": expected_hostname,
        "expected_architecture": expected_architecture,
        "machine": expected_architecture,
        "source_commit": expected_commit,
        "source_archive_sha256": expected_archive_sha256,
        "page_size": PAGE_BYTES,
    }
    for key, wanted in expected.items():
        require(host.get(key) == wanted, f"host {key} differs")
    runtime = host.get("runtime_hostname")
    require(isinstance(runtime, dict), "runtime hostname evidence is missing")
    require(runtime.get("returncode") == 0, "hostname command failed")
    require(runtime.get("output") == expected_hostname, "runtime hostname differs")
    for command in ("uname", "lscpu", "findmnt_tmp", "findmnt_data", "df_data", "lsblk", "free", "compiler", "compiler_target", "python", "sysctl"):
        receipt = host.get(command)
        require(isinstance(receipt, dict), f"host command missing: {command}")
        require(receipt.get("returncode") == 0, f"host command failed: {command}")
        require(bool(receipt.get("output")), f"host command produced no evidence: {command}")
    findmnt = json.loads(host["findmnt_data"]["output"], object_pairs_hook=reject_pairs)
    filesystems = findmnt.get("filesystems") if isinstance(findmnt, dict) else None
    require(isinstance(filesystems, list) and filesystems, "data filesystem identity is missing")
    fstypes = {
        entry.get("fstype", "").lower()
        for entry in filesystems
        if isinstance(entry, dict) and isinstance(entry.get("fstype"), str)
    }
    require(fstypes and fstypes.isdisjoint({"tmpfs", "ramfs"}), "data filesystem is memory-backed or unknown")
    require(isinstance(host.get("allowed_affinity"), list) and host["allowed_affinity"], "CPU availability is missing")
    require(isinstance(host.get("block_queue"), dict), "block queue evidence is missing")
    return {
        "target_label": expected_label,
        "runtime_hostname": expected_hostname,
        "architecture": expected_architecture,
        "allowed_cpu_count": len(host["allowed_affinity"]),
    }


def verify_build(root: Path) -> dict[str, str]:
    status_value = read_json(root / "build/compile.status.json")
    require(status_value.get("returncode") == 0, "native compilation did not succeed")
    binary = root / "bin/pcbench"
    digest_line = (root / "bin/pcbench.sha256").read_text(encoding="utf-8").split()
    require(len(digest_line) >= 1 and digest_line[0] == sha256(binary), "binary digest differs")
    for relative in (
        "build/identity.txt",
        "bin/pcbench.file.txt",
        "bin/pcbench.ldd.txt",
        "bin/pcbench.build-id.txt",
        "codegen/pcbench.s",
        "codegen/all.asm",
        "codegen/verify_block.asm",
        "codegen/symbols.txt",
    ):
        require((root / relative).stat().st_size > 0, f"empty build evidence: {relative}")
    symbols = (root / "codegen/symbols.txt").read_text(encoding="utf-8")
    disassembly = (root / "codegen/verify_block.asm").read_text(encoding="utf-8")
    require("verify_block" in symbols and "verify_block" in disassembly, "verification codegen is missing")
    return {"binary_sha256": sha256(binary)}


def verify_control(root: Path, name: str) -> dict[str, Any]:
    base = root / "controls" / name
    stdout = base.with_suffix(".stdout")
    stderr = base.with_suffix(".stderr")
    status_value = read_json(base.with_suffix(".status.json"))
    require(status_value.get("schema") == "topic51-control-status.v1", f"{name}: status schema differs")
    require(status_value.get("name") == name and status_value.get("returncode") == 0, f"{name}: command failed")
    require(status_value.get("stdout_sha256") == sha256(stdout), f"{name}: stdout digest differs")
    require(status_value.get("stderr_sha256") == sha256(stderr), f"{name}: stderr digest differs")
    require(stderr.stat().st_size == 0, f"{name}: stderr is not empty")
    return read_json_line(stdout)


def verify_controls(root: Path) -> dict[str, Any]:
    prepare = verify_control(root, "prepare")
    require(prepare.get("kind") == "prepare", "prepare: kind differs")
    require(prepare.get("bytes") == FILE_BYTES and prepare.get("pages") == FILE_BYTES // PAGE_BYTES, "prepare: size differs")
    require(prepare.get("resident_after_sync") == FILE_BYTES // PAGE_BYTES, "prepare: pages not resident after sync")
    require(prepare.get("resident_after_dontneed") == 0, "prepare: DONTNEED did not remove residency")

    sequential = verify_control(root, "probe-sequential")
    random = verify_control(root, "probe-random")
    for name, probe, mode in (
        ("probe-sequential", sequential, "probe_seq"),
        ("probe-random", random, "probe_random"),
    ):
        require(probe.get("kind") == "probe" and probe.get("status") == "ok", f"{name}: probe failed")
        require(probe.get("mode") == mode and probe.get("cold_verified") == 1, f"{name}: setup differs")
        require(probe.get("resident_before") == 0 and probe.get("errors") == 0, f"{name}: semantic control failed")
        require(probe.get("bytes_requested") == PAGE_BYTES and probe.get("pages") == FILE_BYTES // PAGE_BYTES, f"{name}: request size differs")
    require(sequential.get("resident_after_20ms", 0) > 1, "sequential probe did not observe readahead")
    require(random.get("resident_after_20ms") == 1, "random probe populated more than its requested page")
    require(sequential.get("read_bytes_delta", 0) >= PAGE_BYTES, "sequential probe physical-read evidence is missing")
    require(random.get("read_bytes_delta") == PAGE_BYTES, "random probe physical-read count differs")

    write = verify_control(root, "writecheck")
    require(write.get("kind") == "writecheck" and write.get("status") == "ok", "writecheck failed")
    require(write.get("bytes") == WRITE_BYTES and write.get("pages") == WRITE_BYTES // PAGE_BYTES, "writecheck size differs")
    pages = WRITE_BYTES // PAGE_BYTES
    require(write.get("resident_after_write") == pages, "writecheck pages not resident after write")
    require(write.get("resident_after_fdatasync") == pages, "fdatasync unexpectedly removed page-cache residency")
    require(write.get("resident_after_dontneed") == 0, "writecheck DONTNEED did not remove residency")
    require(write.get("wchar_after_write") == WRITE_BYTES, "writecheck logical bytes differ")
    for key in ("startup_to_write_ns", "write_ns", "fdatasync_ns"):
        require(type(write.get(key)) is int and write[key] > 0, f"writecheck {key} is invalid")
    return {
        "sequential_resident_pages_after_20ms": sequential["resident_after_20ms"],
        "random_resident_pages_after_20ms": random["resident_after_20ms"],
        "write_ns": write["write_ns"],
        "fdatasync_ns": write["fdatasync_ns"],
    }


def recompute_ratio(rows: list[dict[str, Any]], templates: tuple[str, ...], t975: float) -> tuple[float, list[float]]:
    letters = sorted(set("".join(templates)))
    require(len(letters) == 2, "scenario must contain two treatments")
    contrasts: list[float] = []
    for block, template in enumerate(templates, 1):
        block_rows = sorted((row for row in rows if row.get("block") == block), key=lambda row: row["period"])
        require(len(block_rows) == 4, f"block {block} is incomplete")
        require("".join(row["letter"] for row in block_rows) == template, f"block {block} order differs")
        samples: dict[str, list[int]] = {letter: [] for letter in letters}
        for row in block_rows:
            observed = row["observed"]
            samples[row["letter"]].append(observed["measurement_ns"])
        left = statistics.mean(math.log(value) for value in samples[letters[0]])
        right = statistics.mean(math.log(value) for value in samples[letters[1]])
        contrasts.append(right - left)
    mean_log = statistics.mean(contrasts)
    standard_error = statistics.stdev(contrasts) / math.sqrt(len(contrasts))
    return math.exp(mean_log), [
        math.exp(mean_log - t975 * standard_error),
        math.exp(mean_log + t975 * standard_error),
    ]


def verify_scenario(root: Path, name: str, all_pids: set[int]) -> dict[str, Any]:
    config = SCENARIOS[name]
    scenario = root / "campaign" / name
    templates = config["templates"]
    treatments = config["treatments"]
    seed = config["seed"]
    t975 = config["t975"]
    assert isinstance(templates, tuple) and isinstance(treatments, dict)
    assert isinstance(seed, int) and isinstance(t975, float)
    schedule = read_json(scenario / "schedule.json")
    require(schedule.get("scenario") == name and schedule.get("templates") == list(templates), f"{name}: schedule differs")
    require(schedule.get("seed") == seed and schedule.get("data_file_bytes") == FILE_BYTES, f"{name}: schedule identity differs")
    rows = read_jsonl(scenario / "attempts.jsonl")
    expected_count = len(templates) * 4
    require(len(rows) == expected_count, f"{name}: attempt count differs")
    journal = read_jsonl(scenario / "attempt-journal.jsonl")
    require(len(journal) == expected_count * 2, f"{name}: journal count differs")
    expected_sequence = 0
    direct_resident_after: list[int] = []
    for block, template in enumerate(templates, 1):
        for period, letter in enumerate(template, 1):
            expected_sequence += 1
            row = rows[expected_sequence - 1]
            mode, prefix = treatments[letter]
            label = f"{prefix}_b{block:02d}_p{period}"
            run_seed = seed * 100000 + block * 100 + period
            expected = {
                "sequence": expected_sequence,
                "block": block,
                "period": period,
                "template": template,
                "letter": letter,
                "mode": mode,
                "label": label,
                "returncode": 0,
                "valid": True,
            }
            for key, wanted in expected.items():
                require(row.get(key) == wanted, f"{name} attempt {expected_sequence}: {key} differs")
            require(row.get("validation_errors") == [], f"{name} attempt {expected_sequence}: validation errors present")
            pid = row.get("pid")
            require(type(pid) is int and pid > 0 and pid not in all_pids, f"{name}: PID is invalid or reused")
            all_pids.add(pid)
            stdout = exact_path(scenario, row.get("stdout_file"))
            stderr = exact_path(scenario, row.get("stderr_file"))
            status_path = exact_path(scenario, row.get("status_file"))
            require(row.get("stdout_sha256") == sha256(stdout), f"{name}: stdout digest differs")
            require(row.get("stderr_sha256") == sha256(stderr), f"{name}: stderr digest differs")
            require(stderr.stat().st_size == 0, f"{name}: native stderr is not empty")
            observed = read_json_line(stdout)
            require(row.get("observed") == observed, f"{name}: raw and indexed observations differ")
            require(read_json(status_path) == {key: value for key, value in row.items() if not key.endswith("_file")}, f"{name}: status and attempt rows differ")
            require(observed.get("pid") == pid and observed.get("mode") == mode, f"{name}: observed identity differs")
            require(observed.get("label") == label and observed.get("seed") == run_seed, f"{name}: observed seed or label differs")
            require(observed.get("status") == "ok" and observed.get("errors") == 0, f"{name}: native semantic check failed")
            require(observed.get("resident_before") == 0 and observed.get("cold_verified") == 1, f"{name}: cache setup differs")
            require(observed.get("read_bytes_delta") == FILE_BYTES, f"{name}: physical-read byte count differs")
            require(type(observed.get("measurement_ns")) is int and observed["measurement_ns"] > 0, f"{name}: timing is invalid")
            require(type(observed.get("startup_to_measure_ns")) is int and observed["startup_to_measure_ns"] > 0, f"{name}: startup timing is invalid")
            resident_after = observed.get("resident_after")
            require(
                type(resident_after) is int and 0 <= resident_after <= FILE_BYTES // PAGE_BYTES,
                f"{name}: final residency is invalid",
            )
            if mode != "direct_seq":
                require(
                    resident_after == FILE_BYTES // PAGE_BYTES,
                    f"{name}: buffered final residency differs",
                )
            if mode == "direct_seq":
                direct_resident_after.append(resident_after)
                require(observed.get("dio_align_reported") == 1, "direct I/O lacks STATX_DIOALIGN evidence")
                memory_alignment = observed.get("dio_mem_align")
                allocation_alignment = observed.get("dio_allocation_align")
                offset_alignment = observed.get("dio_offset_align")
                require(
                    type(memory_alignment) is int
                    and memory_alignment > 0
                    and type(allocation_alignment) is int
                    and allocation_alignment >= struct.calcsize("P")
                    and (allocation_alignment & (allocation_alignment - 1)) == 0
                    and allocation_alignment % memory_alignment == 0
                    and type(offset_alignment) is int
                    and offset_alignment > 0
                    and PAGE_BYTES % offset_alignment == 0,
                    "direct I/O alignment evidence is invalid",
                )

    for index, event in enumerate(journal):
        sequence = index // 2 + 1
        expected_event = "planned" if index % 2 == 0 else "completed"
        require(event.get("event") == expected_event and event.get("sequence") == sequence, f"{name}: journal order differs")
        if expected_event == "completed":
            require(event.get("valid") is True, f"{name}: journal records an invalid attempt")
    complete = read_json(scenario / "COMPLETE.json")
    require(complete.get("attempt_count") == expected_count and complete.get("unique_pid_count") == expected_count, f"{name}: completion marker differs")
    require(not (scenario / "failures.jsonl").exists(), f"{name}: failure ledger exists")
    point, interval = recompute_ratio(rows, templates, t975)
    result: dict[str, Any] = {
        "attempt_count": expected_count,
        "point_ratio": point,
        "interval": interval,
    }
    if direct_resident_after:
        result["direct_resident_after"] = {
            "minimum": min(direct_resident_after),
            "maximum": max(direct_resident_after),
            "values": direct_resident_after,
        }
    return result


def close_enough(left: float, right: object) -> bool:
    return isinstance(right, (int, float)) and math.isclose(left, float(right), rel_tol=1e-12, abs_tol=1e-12)


def verify_campaign(root: Path) -> dict[str, Any]:
    all_pids: set[int] = set()
    recomputed = {name: verify_scenario(root, name, all_pids) for name in SCENARIOS}
    summary = read_json(root / "campaign/summary.json")
    require(summary.get("schema") == "topic51-analysis.v1", "analysis schema differs")
    scenarios = summary.get("scenarios")
    require(isinstance(scenarios, dict), "analysis scenarios are missing")
    for name, expected in recomputed.items():
        observed = scenarios.get(name)
        require(isinstance(observed, dict), f"analysis lacks {name}")
        require(close_enough(expected["point_ratio"], observed.get("point_ratio")), f"{name}: point estimate differs")
        interval = observed.get("ratio_95pct_student_t_interval")
        require(isinstance(interval, list) and len(interval) == 2, f"{name}: interval is missing")
        require(all(close_enough(expected["interval"][index], interval[index]) for index in (0, 1)), f"{name}: interval differs")
    return {"fresh_process_count": len(all_pids), "scenarios": recomputed}


def verify_cleanup(root: Path) -> None:
    cleanup = read_json(root / "cleanup.json")
    require(cleanup.get("schema") == "topic51-cleanup.v1", "cleanup schema differs")
    require(cleanup.get("removed_files") == ["data.bin", "writecheck.bin"], "cleanup file list differs")
    require(cleanup.get("data_directory_removed") is True, "data directory was not removed")


def verify_seal(root: Path) -> bool:
    manifest = root / "MANIFEST.sha256"
    seal = root / "SEALED"
    if not manifest.exists() and not seal.exists():
        return False
    require(manifest.is_file() and seal.is_file(), "partial receipt seal")
    require(seal.read_text(encoding="utf-8") == "topic51-receipt.v1\n", "seal marker differs")
    expected_paths: set[str] = set()
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        pieces = line.split("  ", 1)
        require(len(pieces) == 2 and len(pieces[0]) == 64, f"manifest line {number} is malformed")
        relative = pieces[1]
        path = exact_path(root, relative)
        require(relative not in expected_paths, f"duplicate manifest path: {relative}")
        require(sha256(path) == pieces[0], f"manifest digest differs: {relative}")
        expected_paths.add(relative)
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name not in {"MANIFEST.sha256", "SEALED"}
    }
    require(expected_paths == actual_paths, "manifest file set differs from receipt")
    for path in root.rglob("*"):
        if path.is_symlink():
            fail(f"sealed receipt contains a symlink: {path}")
        if path.is_file():
            writable = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
            require(not (path.stat().st_mode & writable), f"sealed file remains writable: {path}")
    validation = read_json(root / "receipt-validation.json")
    require(validation.get("pass") is True and validation.get("sealed") is False, "preseal validation record differs")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt_root", type=Path)
    parser.add_argument("--expected-target-label", required=True)
    parser.add_argument("--expected-hostname", required=True)
    parser.add_argument("--expected-architecture", required=True, choices=("aarch64", "x86_64"))
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-source-archive-sha256", required=True)
    parser.add_argument(
        "--allow-unsealed",
        action="store_true",
        help="accept a receipt that carries neither MANIFEST.sha256 nor SEALED; "
        "the launcher uses this for its pre-seal check only",
    )
    args = parser.parse_args()
    root = args.receipt_root.resolve(strict=True)
    require(root.is_dir(), "receipt root is not a directory")
    require(len(args.expected_source_commit) == 40, "expected commit has the wrong shape")
    require(len(args.expected_source_archive_sha256) == 64, "expected archive digest has the wrong shape")
    result = {
        "schema": "topic51-receipt-validation.v1",
        "pass": True,
        "sealed": False,
        "source": verify_source(root, args.expected_source_commit, args.expected_source_archive_sha256),
        "host": verify_host(
            root,
            args.expected_target_label,
            args.expected_hostname,
            args.expected_architecture,
            args.expected_source_commit,
            args.expected_source_archive_sha256,
        ),
        "build": verify_build(root),
        "controls": verify_controls(root),
        "campaign": verify_campaign(root),
    }
    verify_cleanup(root)
    result["sealed"] = verify_seal(root)
    if not result["sealed"] and not args.allow_unsealed:
        fail("receipt carries neither MANIFEST.sha256 nor SEALED")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
