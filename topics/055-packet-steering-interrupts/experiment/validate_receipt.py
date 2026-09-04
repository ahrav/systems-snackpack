#!/usr/bin/env python3
"""Independently validate one sealed Topic 55 host receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
from typing import NoReturn


HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
OUTPUT_NAME = re.compile(
    r"(?P<sequence>[0-9]{3})-(?P<scenario>campaign|control)-"
    r"b(?P<block>[0-9]{2})-p(?P<period>[1-4])-"
    r"(?P<label>[ABXY])-(?P<treatment>one|many)-"
    r"(?P<host>arm|x86)-(?P<role>server|client)\.out\Z"
)
WRITE_BITS = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
TOPIC_PREFIX = "topics/055-packet-steering-interrupts/"


def fail(message: str) -> NoReturn:
    """Reject a receipt with one explicit message."""
    raise ValueError(message)


def require(condition: bool, message: str) -> None:
    """Reject a false receipt condition."""
    if not condition:
        fail(message)


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Return a streaming file SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_key_values(line: str, label: str) -> dict[str, str]:
    """Parse whitespace-separated key-value fields and reject duplicates."""
    result: dict[str, str] = {}
    for token in line.strip().split():
        require("=" in token, f"{label}: field has no equals sign: {token}")
        key, value = token.split("=", 1)
        require(bool(key) and bool(value), f"{label}: empty key or value")
        require(key not in result, f"{label}: duplicate key: {key}")
        result[key] = value
    return result


def parse_key_value_file(path: Path) -> dict[str, str]:
    """Parse one newline-delimited key-value file."""
    result: dict[str, str] = {}
    text = path.read_text(encoding="utf-8")
    require(text.endswith("\n"), f"{path}: missing final newline")
    for line_number, line in enumerate(text.splitlines(), 1):
        require("=" in line, f"{path}:{line_number}: missing equals sign")
        key, value = line.split("=", 1)
        require(bool(key) and bool(value), f"{path}:{line_number}: empty key or value")
        require(key not in result, f"{path}:{line_number}: duplicate key")
        result[key] = value
    return result


def expected_plan() -> list[tuple[str, int, int, str, str, int, int]]:
    """Return the fixed order-balanced campaign and many-flow A/A plan."""
    rows: list[tuple[str, int, int, str, str, int, int]] = []
    for block, template in enumerate(("ABBA", "BAAB", "ABBA", "BAAB"), 1):
        for period, label in enumerate(template, 1):
            treatment, flows, packets = ("one", 1, 256) if label == "A" else ("many", 128, 2)
            rows.append(("campaign", block, period, label, treatment, flows, packets))
    for block, template in enumerate(("XYYX", "YXXY"), 5):
        for period, label in enumerate(template, 1):
            rows.append(("control", block, period, label, "many", 128, 2))
    return rows


def read_plan(path: Path) -> list[tuple[str, int, int, str, str, int, int]]:
    """Read and type-check the fixed campaign plan."""
    lines = path.read_text(encoding="utf-8").splitlines()
    require(
        lines[:1]
        == ["scenario\tblock\tperiod\tlabel\ttreatment\tflows\tpackets_per_flow"],
        "campaign plan header differs",
    )
    rows: list[tuple[str, int, int, str, str, int, int]] = []
    for line in lines[1:]:
        fields = line.split("\t")
        require(len(fields) == 7, "campaign plan row has the wrong field count")
        rows.append(
            (
                fields[0],
                int(fields[1]),
                int(fields[2]),
                fields[3],
                fields[4],
                int(fields[5]),
                int(fields[6]),
            )
        )
    require(rows == expected_plan(), "campaign plan differs from the fixed design")
    return rows


def validate_summary(
    summary: dict[str, str], expected_source_sha256: str
) -> tuple[str, int, set[int], set[int]]:
    """Validate one probe summary and return role, flows, CPUs, and NAPI IDs."""
    require(summary.get("status") == "ok", "probe status is not ok")
    role = summary.get("role", "")
    require(role in {"client", "server"}, "probe role is invalid")
    flows = int(summary.get("flows", "0"))
    packets_per_flow = int(summary.get("packets_per_flow", "0"))
    require((flows, packets_per_flow) in {(1, 256), (128, 2)}, "probe shape differs")
    require(int(summary.get("observations", "0")) == 256, "probe observation count differs")
    require(summary.get("peer_stable") == f"{flows}/{flows}", "peer identity was unstable")
    require(summary.get("source_sha256") == expected_source_sha256, "probe source hash differs")

    if role == "client":
        require(
            summary.get("placement_scope") == "connected_flow_socket",
            "client placement scope differs",
        )
        for key in (
            "cpu_stable",
            "napi_stable",
            "pair_stable",
            "known_cpu_flows",
            "positive_napi_flows",
        ):
            require(summary.get(key) == f"{flows}/{flows}", f"client {key} failed")
        require(int(summary.get("unique_cpus", "0")) >= 1, "client observed no CPU")
        require(int(summary.get("positive_napi_ids", "0")) >= 1, "client observed no positive NAPI ID")
    else:
        require(
            summary.get("placement_scope") == "shared_socket_only",
            "server placement scope differs",
        )
        require(
            summary.get("unique_source_endpoints") == f"{flows}/{flows}",
            "server source endpoints were not unique",
        )
    return role, flows, set(), set()


def validate_manifest(root: Path) -> tuple[int, str]:
    """Verify manifest coverage, hashes, file kinds, and read-only modes."""
    manifest = root / "MANIFEST.sha256"
    require(manifest.is_file() and not manifest.is_symlink(), "manifest is missing or linked")
    require(root.stat().st_mode & WRITE_BITS == 0, "receipt root is writable")
    declared: dict[str, str] = {}
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (\./[^\n]+)", line)
        require(match is not None, f"manifest line {line_number} is invalid")
        digest, relative = match.groups()
        pure = PurePosixPath(relative)
        require(not pure.is_absolute() and ".." not in pure.parts, "unsafe manifest path")
        require(relative not in declared, "duplicate manifest path")
        declared[relative] = digest

    observed: set[str] = set()
    for path in root.rglob("*"):
        relative = "./" + path.relative_to(root).as_posix()
        require(not path.is_symlink(), f"receipt contains a link: {relative}")
        mode = path.stat().st_mode
        require(mode & WRITE_BITS == 0, f"receipt path is writable: {relative}")
        if path.is_file() and path != manifest:
            observed.add(relative)
            require(relative in declared, f"manifest omits {relative}")
            require(sha256_file(path) == declared[relative], f"hash differs: {relative}")
        else:
            require(path.is_dir() or path == manifest, f"unsupported receipt entry: {relative}")
    require(observed == set(declared), "manifest lists absent files")
    return len(declared), sha256_file(manifest)


def validate_archive(
    archive_path: Path,
    commit: str,
    archive_sha256: str,
    probe_source_sha256: str,
    runner_sha256: str,
) -> int:
    """Validate archive identity and exact probe and runner bytes."""
    require(sha256_file(archive_path) == archive_sha256, "source archive hash differs")
    prefix = f"systems-snackpack-{commit}/"
    source_root = prefix.rstrip("/")
    files = 0
    probe_seen = False
    runner_seen = False
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            pure = PurePosixPath(member.name)
            require(not pure.is_absolute() and ".." not in pure.parts, "unsafe archive path")
            topic_prefix = prefix + TOPIC_PREFIX
            parent_directories = {source_root, prefix + "topics", topic_prefix.rstrip("/")}
            require(
                member.name in parent_directories or member.name.startswith(topic_prefix),
                "archive member escapes topic prefix",
            )
            if member.name in parent_directories:
                require(member.isdir(), "archive parent is not a directory")
            require(member.isdir() or member.isfile(), "archive contains a non-file member")
            if not member.isfile():
                continue
            files += 1
            source = archive.extractfile(member)
            require(source is not None, "archive file could not be read")
            digest = sha256_bytes(source.read())
            relative = member.name.removeprefix(prefix)
            if relative == TOPIC_PREFIX + "experiment/udp_steering_probe.rs":
                require(digest == probe_source_sha256, "archived probe source hash differs")
                probe_seen = True
            if relative == TOPIC_PREFIX + "experiment/run_host.sh":
                require(digest == runner_sha256, "archived runner hash differs")
                runner_seen = True
    require(probe_seen and runner_seen, "archive lacks the bound probe or runner")
    return files


def validate(args: argparse.Namespace) -> dict[str, object]:
    """Validate the complete receipt and return a compact result."""
    require(not args.receipt.is_symlink(), "receipt path is a symlink")
    root = args.receipt.resolve()
    require(root.is_dir(), "receipt is not a directory")
    require(HEX40.fullmatch(args.commit) is not None, "expected commit is invalid")
    require(HEX64.fullmatch(args.archive_sha256) is not None, "expected archive hash is invalid")
    receipt_files, manifest_sha256 = validate_manifest(root)
    require((root / "STATE").read_text(encoding="utf-8") == "sealed\n", "receipt is not sealed")
    require((root / "SEALED").is_file(), "seal marker is missing")

    provenance = parse_key_value_file(root / "provenance.txt")
    expected = {
        "schema": "topic55-provenance.v1",
        "target_label": args.label,
        "expected_hostname": args.hostname,
        "runtime_hostname": args.hostname,
        "expected_architecture": args.architecture,
        "runtime_architecture": args.architecture,
        "source_commit": args.commit,
        "source_archive_sha256": args.archive_sha256,
        "source_prefix": f"systems-snackpack-{args.commit}/",
        "topic_prefix": TOPIC_PREFIX,
        "compile_flags": "--edition 2024 -D warnings -C opt-level=3 -C debuginfo=1 -C target-cpu=generic -C overflow-checks=yes",
        "timing_claim": "false",
    }
    for key, value in expected.items():
        require(provenance.get(key) == value, f"provenance differs: {key}")
    probe_source_sha256 = provenance.get("probe_source_sha256", "")
    probe_binary_sha256 = provenance.get("probe_binary_sha256", "")
    runner_sha256 = provenance.get("runner_sha256", "")
    require(HEX64.fullmatch(probe_source_sha256) is not None, "probe source hash is invalid")
    require(HEX64.fullmatch(probe_binary_sha256) is not None, "probe binary hash is invalid")
    require(HEX64.fullmatch(runner_sha256) is not None, "runner hash is invalid")
    require(
        sha256_file(root / "source/udp_steering_probe.rs") == probe_source_sha256,
        "retained probe source hash differs",
    )
    require(
        sha256_file(root / "bin/udp_steering_probe") == probe_binary_sha256,
        "probe binary hash differs",
    )
    archive_files = validate_archive(
        root / "source/source.tar.gz",
        args.commit,
        args.archive_sha256,
        probe_source_sha256,
        runner_sha256,
    )

    read_plan(root / "campaign/plan.tsv")
    outputs = sorted((root / "campaign").glob("*.out"))
    errors = sorted((root / "campaign").glob("*.err"))
    require(len(outputs) == 48 and len(errors) == 48, "probe output or error count differs")
    require(
        {path.with_suffix(".err") for path in outputs} == set(errors),
        "probe output and error filenames do not pair",
    )
    require(all(path.stat().st_size == 0 for path in errors), "a probe stderr file is nonempty")
    client_outputs = 0
    server_outputs = 0
    positive_napis: set[int] = set()
    observed_sequences: dict[int, set[str]] = {}
    expected_host_tag = "arm" if args.architecture == "aarch64" else "x86"
    for output in outputs:
        name_match = OUTPUT_NAME.fullmatch(output.name)
        require(name_match is not None, f"unexpected probe output name: {output.name}")
        metadata = name_match.groupdict()
        sequence = int(metadata["sequence"])
        require(1 <= sequence <= 24, "probe sequence is out of range")
        rows = expected_plan()
        expected_row = rows[sequence - 1]
        require(metadata["host"] == expected_host_tag, "output host tag differs from receipt")
        require(metadata["scenario"] == expected_row[0], "output scenario differs from plan")
        require(int(metadata["block"]) == expected_row[1], "output block differs from plan")
        require(int(metadata["period"]) == expected_row[2], "output period differs from plan")
        require(metadata["label"] == expected_row[3], "output label differs from plan")
        require(metadata["treatment"] == expected_row[4], "output treatment differs from plan")
        observed_sequences.setdefault(sequence, set()).add(metadata["role"])

        lines = output.read_text(encoding="utf-8").splitlines()
        summary_lines = [line for line in lines if line.startswith("summary ")]
        require(len(summary_lines) == 1, f"{output.name}: expected one summary")
        summary = parse_key_values(summary_lines[0].removeprefix("summary "), output.name)
        role, flows, _, _ = validate_summary(summary, probe_source_sha256)
        require(role == metadata["role"], f"{output.name}: filename role differs")
        require(flows == expected_row[5], f"{output.name}: flow count differs from plan")
        flow_lines = [line for line in lines if line.startswith("flow ")]
        require(len(flow_lines) == flows, f"{output.name}: flow record count differs")
        flow_ids: set[int] = set()
        flow_cpus: set[int] = set()
        flow_napis: set[int] = set()
        server_peers: set[str] = set()
        if role == "client":
            client_outputs += 1
            for line in flow_lines:
                fields = parse_key_values(line.removeprefix("flow "), output.name)
                require(fields.get("role") == "client", f"{output.name}: flow role differs")
                flow_id = int(fields.get("id", "-1"))
                require(flow_id not in flow_ids, f"{output.name}: duplicate flow ID")
                flow_ids.add(flow_id)
                require(int(fields.get("packets", "0")) == expected_row[6], f"{output.name}: flow packet count differs")
                peers = fields.get("peers", "").split(",")
                cpus = fields.get("cpus", "").split(",")
                napis = fields.get("napis", "").split(",")
                require(len(peers) == 1 and bool(peers[0]), f"{output.name}: client peer differs")
                require(len(cpus) == 1 and bool(cpus[0]), f"{output.name}: client CPU is not stable")
                require(len(napis) == 1 and bool(napis[0]), f"{output.name}: client NAPI is not stable")
                cpu = int(cpus[0])
                napi = int(napis[0])
                require(cpu >= 0, f"{output.name}: client CPU is unknown")
                require(napi > 0, f"{output.name}: client NAPI ID is not positive")
                flow_cpus.add(cpu)
                flow_napis.add(napi)
                positive_napis.add(napi)
            for key, expected_count in (
                ("unique_cpus", len(flow_cpus)),
                ("unique_napi_ids", len(flow_napis)),
                ("positive_napi_ids", len(flow_napis)),
            ):
                require(key in summary, f"{output.name}: summary lacks {key}")
                require(int(summary[key]) == expected_count, f"{output.name}: {key} aggregate differs")
        else:
            server_outputs += 1
            for line in flow_lines:
                fields = parse_key_values(line.removeprefix("flow "), output.name)
                require(fields.get("role") == "server", f"{output.name}: flow role differs")
                require(
                    fields.get("placement_scope") == "peer_identity_only",
                    f"{output.name}: server flow scope differs",
                )
                flow_id = int(fields.get("id", "-1"))
                require(flow_id not in flow_ids, f"{output.name}: duplicate flow ID")
                flow_ids.add(flow_id)
                require(int(fields.get("packets", "0")) == expected_row[6], f"{output.name}: flow packet count differs")
                peer = fields.get("peer", "")
                require(bool(peer) and peer not in server_peers, f"{output.name}: duplicate or empty server peer")
                server_peers.add(peer)
            require(len(server_peers) == flows, f"{output.name}: server peer aggregate differs")
        require(flow_ids == set(range(flows)), f"{output.name}: flow IDs are incomplete")
    require(client_outputs == 24 and server_outputs == 24, "client/server output balance differs")
    require(
        all(roles == {"client", "server"} for roles in observed_sequences.values())
        and len(observed_sequences) == 24,
        "each sequence must contain one client and one server output",
    )

    route_interfaces: set[str] = set()
    for phase in ("before", "after"):
        route = (root / f"snapshots/{phase}.route.txt").read_text(encoding="utf-8")
        interface_match = re.search(r"(?:^|\s)dev\s+(\S+)", route)
        require(interface_match is not None, f"{phase} route has no device")
        interface = interface_match.group(1)
        require(interface != "lo", f"{phase} route used loopback")
        route_interfaces.add(interface)
    require(len(route_interfaces) == 1, "route interface changed during the campaign")
    require(
        (root / "host/steering.prepare.txt").read_bytes()
        == (root / "host/steering.seal.txt").read_bytes(),
        "steering configuration changed during the campaign",
    )
    require(
        (root / "host/irq-affinity.prepare.txt").read_bytes()
        == (root / "host/irq-affinity.seal.txt").read_bytes(),
        "IRQ affinity changed during the campaign",
    )
    require("test result: ok" in (root / "build/model-tests.txt").read_text(encoding="utf-8"), "model tests failed")
    require("test result: ok" in (root / "build/doctests.txt").read_text(encoding="utf-8"), "doctests failed")
    example = (root / "build/steering-costs.txt").read_text(encoding="utf-8")
    for line in (
        "balanced_queue_utilization=0.093333",
        "elephant_queue_utilization=1.248333",
        "rps_required_cores=0.222000",
        "rfs_required_cores_delta=-0.053120",
        "xps_modeled_core_savings=0.085333",
    ):
        require(line in example, f"checked model output is missing: {line}")

    queue_text = (root / "host/queues.txt").read_text(encoding="utf-8")
    route_interface = next(iter(route_interfaces))
    queue_marker = f"/net/{route_interface}/queues/"
    rx_queue_count = sum(
        1 for line in queue_text.splitlines() if queue_marker in line and "/rx-" in line
    )
    tx_queue_count = sum(
        1 for line in queue_text.splitlines() if queue_marker in line and "/tx-" in line
    )
    require(rx_queue_count >= 1 and tx_queue_count >= 1, "host queue inventory is empty")
    softnet_format = parse_key_value_file(root / "host/softnet-format.txt")
    require(int(softnet_format.get("columns", "0")) >= 3, "softnet column inventory is invalid")
    require((root / "host/irq-affinity.prepare.txt").stat().st_size > 0, "IRQ affinity inventory is empty")
    require((root / "host/net-drivers.txt").stat().st_size > 0, "driver inventory is empty")
    require(
        (root / "host/ethtool.txt").read_text(encoding="utf-8").startswith(
            ("ethtool=available\n", "ethtool=unavailable\n")
        ),
        "ethtool capability record is invalid",
    )
    return {
        "schema": "topic55-controller-validation.v1",
        "pass": True,
        "sealed": True,
        "measurement_usable": True,
        "timing_claim": False,
        "target_label": args.label,
        "hostname": args.hostname,
        "architecture": args.architecture,
        "source_commit": args.commit,
        "source_archive_sha256": args.archive_sha256,
        "probe_source_sha256": probe_source_sha256,
        "probe_binary_sha256": probe_binary_sha256,
        "manifest_sha256": manifest_sha256,
        "receipt_files": receipt_files,
        "archive_files": archive_files,
        "probe_outputs": len(outputs),
        "client_outputs": client_outputs,
        "server_outputs": server_outputs,
        "positive_client_napi_ids": sorted(positive_napis),
        "rx_queue_count": rx_queue_count,
        "tx_queue_count": tx_queue_count,
        "route_interface": route_interface,
    }


def main() -> int:
    """Parse arguments, validate the receipt, and print one JSON result."""
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("label")
    parser.add_argument("hostname")
    parser.add_argument("architecture", choices=("aarch64", "x86_64"))
    parser.add_argument("commit")
    parser.add_argument("archive_sha256")
    args = parser.parse_args()
    try:
        result = validate(args)
    except (OSError, UnicodeError, ValueError, tarfile.TarError) as error:
        print(json.dumps({"schema": "topic55-controller-validation.v1", "pass": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
