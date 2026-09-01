#!/usr/bin/env python3
"""Isolated tamper tests for the Topic 53 analyzer and receipt validator."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from typing import Any


EXPERIMENT = Path(__file__).resolve().parent


def load_module(name: str, filename: str) -> Any:
    """Load a sibling script without depending on the caller's import path."""
    spec = importlib.util.spec_from_file_location(name, EXPERIMENT / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analyze = load_module("topic53_analyze", "analyze.py")
validator = load_module("topic53_validate", "validate_receipt.py")


def digest(data: bytes) -> str:
    """Return a test SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def bench_result(
    *,
    pid: int,
    label: str,
    depth: int,
    operations: int,
    seed: int,
    elapsed_ns: int,
    exact_checksum: bool = False,
) -> dict[str, Any]:
    """Build one internally consistent native direct-I/O result."""
    blocks = validator.DATA_FILE_BYTES // validator.BLOCK_BYTES
    byte_count = operations * validator.BLOCK_BYTES
    checksum = (
        validator.expected_checksum(operations, blocks, seed)
        if exact_checksum
        else seed
    )
    return {
        "schema": "topic53-probe.v1",
        "kind": "bench",
        "status": "ok",
        "pid": pid,
        "tid": pid,
        "threads_before": 1,
        "threads_after": 1,
        "mode": "direct",
        "label": label,
        "seed": seed,
        "depth": depth,
        "total_ops": operations,
        "bytes": byte_count,
        "blocks": blocks,
        "startup_to_measure_ns": 3_000_000,
        "setup_ns": 1_000_000,
        "elapsed_ns": elapsed_ns,
        "iops": operations * 1e9 / elapsed_ns,
        "mib_s": byte_count * 1e9 / elapsed_ns / (1024**2),
        "read_bytes_delta": byte_count,
        "verified_reads": operations,
        "errors": 0,
        "checksum": checksum,
        "peak_outstanding": depth,
        "resident_before": 0,
        "resident_after": 0,
        "total_pages": 0,
        "dioalign_known": 1,
        "dio_mem_align": 512,
        "dio_offset_align": 512,
        "dio_allocation_align": 4096,
        "nvcsw": 0,
        "nivcsw": 0,
    }


def write_campaign(
    root: Path,
    scenario: str,
    *,
    noisy_aa: bool = False,
) -> None:
    """Write the minimal retained records accepted by analyze.py."""
    config = validator.SCENARIOS[scenario]
    directory = root / scenario
    directory.mkdir(parents=True)
    operations = 256
    source_sha = "1" * 64
    binary_sha = "2" * 64
    schedule = {
        "schema": "topic53-schedule.v1",
        "scenario": scenario,
        "templates": list(config["templates"]),
        "treatments": config["treatments"],
        "seed_base": config["seed_base"],
        "blocks": 8,
        "processes_per_block": 4,
        "ops_per_process": operations,
        "block_bytes": 4096,
        "data_file_bytes": 134_217_728,
        "source_sha256": source_sha,
        "binary_sha256": binary_sha,
        "devices": ["testdisk"],
        "primary_device": "testdisk",
        "treatment_application_unit": "fresh native process",
        "analysis_unit": "complete four-process block",
        "subsample_unit": "one verified 4 KiB O_DIRECT read",
        "stopping": "fixed horizon; stop after first invalid attempt",
    }
    (directory / "schedule.json").write_text(
        json.dumps(schedule, sort_keys=True) + "\n", encoding="utf-8"
    )

    rows = []
    pid = 10_000 if scenario == "depth" else 20_000
    for spec in validator.expected_specs(scenario):
        pid += 1
        letter = spec["letter"]
        if scenario == "depth":
            elapsed_ns = 2_000_000 if letter == "A" else 1_000_000
        elif noisy_aa:
            elapsed_ns = (
                2_000_000
                if letter == "Y" and spec["block"] % 2 == 1
                else 500_000
                if letter == "Y"
                else 1_000_000
            )
        else:
            elapsed_ns = 1_000_000
        observed = bench_result(
            pid=pid,
            label=spec["label"],
            depth=spec["depth"],
            operations=operations,
            seed=spec["seed"],
            elapsed_ns=elapsed_ns,
        )
        stem = (
            f"{spec['sequence']:03d}-b{spec['block']:02d}-"
            f"p{spec['period']}-{spec['label']}"
        )
        device_stat = [0] * 11
        device_stat[0] = operations
        device_stat[2] = operations * 8
        rows.append(
            {
                "schema": "topic53-attempt.v1",
                **spec,
                "ops": operations,
                "source_sha256": source_sha,
                "binary_sha256": binary_sha,
                "pid": pid,
                "returncode": 0,
                "timed_out": False,
                "wall_elapsed_ns": elapsed_ns + 1_000_000,
                "stdout_sha256": "3" * 64,
                "stderr_sha256": "4" * 64,
                "before_sha256": "5" * 64,
                "after_sha256": "6" * 64,
                "valid": True,
                "validation_errors": [],
                "observed": observed,
                "counter_deltas": {
                    "devices": {
                        "testdisk": {"stat": device_stat, "inflight": [0, 0]}
                    },
                    "psi_total_us": {"some": 0, "full": 0},
                    "vmstat": {
                        "pgpgin": 0,
                        "pgpgout": 0,
                        "nr_dirty": 0,
                        "nr_writeback": 0,
                    },
                },
                "before_file": f"raw/{stem}.before.json",
                "stdout_file": f"raw/{stem}.stdout",
                "stderr_file": f"raw/{stem}.stderr",
                "after_file": f"raw/{stem}.after.json",
                "status_file": f"raw/{stem}.status.json",
            }
        )
    (directory / "attempts.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_json(path: Path, value: object) -> None:
    """Write one deterministic newline-terminated JSON object."""
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def snapshot(
    *, phase: str, sequence: int, operations: int
) -> dict[str, Any]:
    """Return one internally consistent synthetic Linux counter snapshot."""
    before = phase == "before"
    base = sequence * 100_000
    stats = [base, 0, base * 8, base, 0, 0, 0, 0, 0, base, base]
    if not before:
        stats[0] += operations
        stats[2] += operations * 8
        stats[3] += 1
        stats[9] += 1
        stats[10] += 1
    total_some = sequence * 100 + (0 if before else 10)
    total_full = sequence * 50 + (0 if before else 5)
    vmstat = {
        "pgpgin": base + (0 if before else operations * 4),
        "pgpgout": base,
        "nr_dirty": 0,
        "nr_writeback": 0,
    }
    return {
        "schema": "topic53-snapshot.v1",
        "phase": phase,
        "wall_time_ns": base + (1 if before else 9),
        "monotonic_ns": base + (2 if before else 8),
        "proc_diskstats": "8 0 testdisk " + " ".join(map(str, stats)) + "\n",
        "proc_pressure_io": (
            f"some avg10=0.00 avg60=0.00 avg300=0.00 total={total_some}\n"
            f"full avg10=0.00 avg60=0.00 avg300=0.00 total={total_full}\n"
        ),
        "proc_vmstat": vmstat,
        "cgroup_path": "/test.slice",
        "cgroup_io_stat": "8:0 rbytes=4096\n",
        "cgroup_io_pressure": "unavailable:2\n",
        "devices": {"testdisk": {"stat": stats, "inflight": [0, 0]}},
    }


def make_campaign_validator_ready(receipt: Path, scenario: str) -> None:
    """Expand an analyzer fixture into the runner's complete raw receipt."""
    campaign = receipt / "campaign"
    write_campaign(campaign, scenario)
    directory = campaign / scenario
    raw = directory / "raw"
    raw.mkdir()
    rows = [json.loads(line) for line in (directory / "attempts.jsonl").read_text().splitlines()]
    journal: list[dict[str, Any]] = []
    operations = 256
    for row in rows:
        observed = row["observed"]
        observed["checksum"] = validator.expected_checksum(
            operations, validator.DATA_FILE_BYTES // validator.BLOCK_BYTES, row["seed"]
        )
        stem = (
            f"{row['sequence']:03d}-b{row['block']:02d}-"
            f"p{row['period']}-{row['label']}"
        )
        before_path = raw / f"{stem}.before.json"
        stdout_path = raw / f"{stem}.stdout"
        stderr_path = raw / f"{stem}.stderr"
        after_path = raw / f"{stem}.after.json"
        status_path = raw / f"{stem}.status.json"
        before = snapshot(
            phase="before", sequence=row["sequence"], operations=operations
        )
        after = snapshot(
            phase="after", sequence=row["sequence"], operations=operations
        )
        write_json(before_path, before)
        stdout_path.write_text(
            json.dumps(observed, sort_keys=True) + "\n", encoding="utf-8"
        )
        stderr_path.write_bytes(b"")
        write_json(after_path, after)
        row.update(
            {
                "stdout_sha256": validator.sha256(stdout_path),
                "stderr_sha256": validator.sha256(stderr_path),
                "before_sha256": validator.sha256(before_path),
                "after_sha256": validator.sha256(after_path),
                "counter_deltas": validator.derive_deltas(before, after),
            }
        )
        raw_status = {key: row[key] for key in validator.STATUS_KEYS}
        raw_status["schema"] = "topic53-attempt-status.v1"
        write_json(status_path, raw_status)
        spec = {
            key: row[key]
            for key in (
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
            )
        }
        journal.extend(
            [
                {"event": "planned", **spec, "ops": operations},
                {
                    "event": "completed",
                    "scenario": scenario,
                    "sequence": row["sequence"],
                    "returncode": 0,
                    "timed_out": False,
                    "valid": True,
                    "status_file": row["status_file"],
                    "status_sha256": validator.sha256(status_path),
                },
            ]
        )
    (directory / "attempts.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (directory / "attempt-journal.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in journal),
        encoding="utf-8",
    )
    write_json(
        directory / "COMPLETE.json",
        {
            "schema": "topic53-scenario-complete.v1",
            "scenario": scenario,
            "attempt_count": 32,
            "unique_pid_count": 32,
            "complete_block_count": 8,
            "invalid_attempt_count": 0,
            "source_sha256": "1" * 64,
            "binary_sha256": "2" * 64,
        },
    )


class AnalyzerTests(unittest.TestCase):
    """Exercise complete-block analysis and its A/A precision gate."""

    def test_balanced_campaign_uses_eight_whole_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_campaign(root, "depth")
            write_campaign(root, "aa")
            result = analyze.build_analysis(root)
        with tempfile.TemporaryDirectory() as temporary:
            second_root = Path(temporary)
            write_campaign(second_root, "depth")
            write_campaign(second_root, "aa")
            second_result = analyze.build_analysis(second_root)
        self.assertTrue(result["measurement_usable"])
        self.assertEqual(result["scenarios"]["depth"]["fresh_process_count"], 32)
        self.assertEqual(result["scenarios"]["depth"]["whole_block_count"], 8)
        self.assertAlmostEqual(result["scenarios"]["depth"]["point_ratio"], 2.0)
        self.assertEqual(
            result["scenarios"]["aa"]["ratio_95pct_student_t_interval"],
            [1.0, 1.0],
        )
        self.assertEqual(
            json.dumps(result, sort_keys=True, separators=(",", ":")),
            json.dumps(second_result, sort_keys=True, separators=(",", ":")),
        )

    def test_unbalanced_process_order_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_campaign(root, "depth")
            write_campaign(root, "aa")
            path = root / "depth/attempts.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[0]["letter"] = "B"
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "treatment order changed"):
                analyze.build_analysis(root)

    def test_noisy_aa_emits_all_criteria_and_is_unusable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_campaign(root, "depth")
            write_campaign(root, "aa", noisy_aa=True)
            result = analyze.build_analysis(root)
        acceptance = result["aa_acceptance"]
        self.assertEqual(
            set(acceptance),
            {
                "point_ratio_within_0_95_to_1_05",
                "interval_contains_1",
                "interval_within_0_90_to_1_10",
            },
        )
        self.assertTrue(acceptance["point_ratio_within_0_95_to_1_05"])
        self.assertTrue(acceptance["interval_contains_1"])
        self.assertFalse(acceptance["interval_within_0_90_to_1_10"])
        self.assertFalse(result["aa_control_pass"])
        self.assertFalse(result["measurement_usable"])


class IntegrityTests(unittest.TestCase):
    """Exercise independent native-result, counter, and manifest checks."""

    def test_direct_bench_requires_exact_accounting_and_depth(self) -> None:
        value = bench_result(
            pid=1234,
            label="q8-b01-p2",
            depth=8,
            operations=256,
            seed=530101,
            elapsed_ns=1_000_000,
            exact_checksum=True,
        )
        validator.validate_bench(
            value,
            pid=1234,
            label="q8-b01-p2",
            depth=8,
            operations=256,
            seed=530101,
        )
        tampered = copy.deepcopy(value)
        tampered["read_bytes_delta"] -= 4096
        with self.assertRaisesRegex(ValueError, "read_bytes_delta differs"):
            validator.validate_bench(
                tampered,
                pid=1234,
                label="q8-b01-p2",
                depth=8,
                operations=256,
                seed=530101,
            )
        tampered = copy.deepcopy(value)
        tampered["peak_outstanding"] = 1
        with self.assertRaisesRegex(ValueError, "peak_outstanding differs"):
            validator.validate_bench(
                tampered,
                pid=1234,
                label="q8-b01-p2",
                depth=8,
                operations=256,
                seed=530101,
            )

    def test_snapshot_counter_omission_is_rejected(self) -> None:
        snapshot = {
            "schema": "topic53-snapshot.v1",
            "phase": "before",
            "wall_time_ns": 1,
            "monotonic_ns": 1,
            "proc_diskstats": "1 0 testdisk 1 0 8 1 0 0 0 0 0 0 0\n",
            "proc_pressure_io": (
                "some avg10=0.00 avg60=0.00 avg300=0.00 total=10\n"
                "full avg10=0.00 avg60=0.00 avg300=0.00 total=5\n"
            ),
            "proc_vmstat": {
                "pgpgin": 1,
                "pgpgout": 1,
                "nr_dirty": 0,
                "nr_writeback": 0,
            },
            "cgroup_path": "/",
            "cgroup_io_stat": "8:0 rbytes=4096\n",
            "cgroup_io_pressure": "unavailable:2\n",
            "devices": {
                "testdisk": {
                    "stat": [1, 0, 8, 1, 0, 0, 0, 0, 0, 0, 0],
                    "inflight": [0, 0],
                }
            },
        }
        validator.validate_snapshot(snapshot, "before", ["testdisk"])
        del snapshot["proc_vmstat"]["pgpgin"]
        with self.assertRaisesRegex(ValueError, "vmstat differs"):
            validator.validate_snapshot(snapshot, "before", ["testdisk"])

    def test_manifest_rejects_duplicates_and_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "MANIFEST.sha256"
            checksum = "a" * 64
            path.write_text(
                f"{checksum}  a\n{checksum}  a\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "duplicate.*unsorted"):
                validator.parse_manifest(path)
            path.write_text(f"{checksum}  ../escape\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsafe"):
                validator.parse_manifest(path)

    def test_unsupported_q8_control_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            controls = root / "controls"
            controls.mkdir()
            stdout = b'{"schema":"topic53-probe.v1","status":"unsupported"}\n'
            (controls / "smoke-q8.stdout").write_bytes(stdout)
            (controls / "smoke-q8.stderr").write_bytes(b"")
            status = {
                "schema": "topic53-control-status.v1",
                "name": "smoke-q8",
                "argv": ["probe", "run"],
                "returncode": 77,
                "stdout_sha256": digest(stdout),
                "stderr_sha256": digest(b""),
            }
            (controls / "smoke-q8.status.json").write_text(
                json.dumps(status) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "failed or was unsupported"):
                validator.validate_control(root, "smoke-q8")

    def test_complete_raw_campaigns_and_analysis_rederive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            receipt = Path(temporary)
            (receipt / "campaign").mkdir()
            make_campaign_validator_ready(receipt, "depth")
            make_campaign_validator_ready(receipt, "aa")
            summary = analyze.build_analysis(receipt / "campaign")
            write_json(receipt / "campaign/summary.json", summary)
            host = {
                "stack_devices": ["testdisk"],
                "primary_device": "testdisk",
                "cgroup": {"path": "/test.slice"},
            }
            campaigns = {
                scenario: validator.validate_campaign(
                    receipt,
                    scenario,
                    "1" * 64,
                    "2" * 64,
                    host,
                )
                for scenario in ("depth", "aa")
            }
            rederived = validator.validate_analysis(receipt, campaigns)
            self.assertTrue(rederived["measurement_usable"])

            attempts = receipt / "campaign/depth/attempts.jsonl"
            rows = [json.loads(line) for line in attempts.read_text().splitlines()]
            rows[0]["schema"] = "topic53-attempt-status.v1"
            attempts.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "schema differs"):
                validator.validate_campaign(
                    receipt,
                    "depth",
                    "1" * 64,
                    "2" * 64,
                    host,
                )


class FailClosedCategoryTests(unittest.TestCase):
    """Check representative omission and provenance failure paths."""

    def test_provenance_mismatch_is_rejected(self) -> None:
        commit = "a" * 40
        archive = "b" * 64
        run_host = "c" * 64
        value = {
            "schema": "topic53-provenance.v1",
            "target_label": "arm",
            "expected_hostname": "arm.example",
            "expected_architecture": "aarch64",
            "runtime_hostname": "arm.example",
            "source_commit": commit,
            "source_archive_sha256": archive,
            "source_prefix": f"systems-snackpack-{commit}/",
            "topic_prefix": validator.TOPIC_PREFIX,
            "external_run_host_sha256": run_host,
            "archived_run_host_sha256": run_host,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "provenance.json").write_text(
                json.dumps(value) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "expected_hostname differs"):
                validator.validate_provenance(
                    root,
                    label="arm",
                    hostname="other.example",
                    architecture="aarch64",
                    commit=commit,
                    archive_digest=archive,
                )

    def test_exact_receipt_set_covers_all_evidence_classes(self) -> None:
        files = validator.expected_files(sealed=True)
        representatives = {
            "source/source.tar.gz",
            "source/source-files-before.sha256",
            "host/host.json",
            "build/compiler-version.txt",
            "bin/nvme_aio_depth_probe",
            "codegen/direct_aio_loop.asm",
            "controls/smoke-q8.status.json",
            "campaign/depth/schedule.json",
            "campaign/depth/COMPLETE.json",
            "campaign/aa/attempts.jsonl",
            "campaign/summary.json",
            "receipt-validation.json",
            "MANIFEST.sha256",
            "SEALED",
        }
        self.assertTrue(representatives.issubset(files))
        self.assertEqual(len(files), len(set(files)))

    def test_missing_source_binary_host_and_codegen_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(OSError):
                validator.validate_source(
                    root,
                    commit="a" * 40,
                    archive_digest="b" * 64,
                    provenance={"archived_run_host_sha256": "c" * 64},
                )
            with self.assertRaises(OSError):
                validator.validate_host(
                    root,
                    label="host",
                    hostname="host.example",
                    architecture="x86_64",
                    commit="a" * 40,
                    archive_digest="b" * 64,
                )
            with self.assertRaises(OSError):
                validator.validate_build(root, "c" * 64, "x86_64", {})


if __name__ == "__main__":
    unittest.main()
