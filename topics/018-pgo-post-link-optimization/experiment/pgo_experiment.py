#!/usr/bin/env python3
"""Build, inspect, and measure profile-conditioned Rust binaries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import shlex
import shutil
import socket
import statistics
import subprocess
import sys
import time


T95 = {
    1: 12.706205,
    2: 4.302653,
    3: 3.182446,
    4: 2.776445,
    5: 2.570582,
    6: 2.446912,
    7: 2.364624,
    8: 2.306004,
    9: 2.262157,
    10: 2.228139,
    11: 2.200985,
    12: 2.178813,
    13: 2.160369,
    14: 2.144787,
    15: 2.13145,
    16: 2.119905,
    17: 2.109816,
    18: 2.100922,
    19: 2.093024,
    20: 2.085963,
    21: 2.079614,
    22: 2.073873,
    23: 2.068658,
    24: 2.063899,
    25: 2.059539,
    26: 2.055529,
    27: 2.051831,
    28: 2.048407,
    29: 2.04523,
    30: 2.042272,
}
OUTPUT_LINE = re.compile(
    r"mode=(?P<mode>\w+) iterations=(?P<iterations>\d+) seed=(?P<seed>\d+) "
    r"elapsed_ns=(?P<elapsed_ns>\d+) checksum=(?P<checksum>[0-9a-f]+)"
)
SCHEDULE_SEED = 0x5047_4F18


def run(
    command: list[str],
    *,
    cwd: Path,
    commands: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """Run one required command and return merged output."""
    if commands is not None:
        # Record the assignments that differ from this process's environment, so
        # the transcript replays as written. `LLVM_PROFILE_FILE` decides where a
        # training run deposits its raw profile, and without it the recorded
        # `llvm-profdata merge` reads a directory the replay never populated.
        overrides = [
            f"{name}={value}"
            for name, value in sorted((env or {}).items())
            if os.environ.get(name) != value
        ]
        commands.append(shlex.join([*overrides, *command]))
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of one regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_empty(path: Path, name: str) -> None:
    """Create an empty directory or reject an existing non-empty directory."""
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"{name} must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def tool(name: str) -> str:
    """Resolve one required executable."""
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required executable is unavailable: {name}")
    return resolved


def rust_profdata(rustc: str, cwd: Path) -> str:
    """Resolve the llvm-profdata bundled with the active Rust toolchain."""
    verbose = run([rustc, "-vV"], cwd=cwd)
    host = next(
        line.split(": ", 1)[1]
        for line in verbose.splitlines()
        if line.startswith("host: ")
    )
    sysroot = Path(run([rustc, "--print", "sysroot"], cwd=cwd).strip())
    bundled = sysroot / "lib" / "rustlib" / host / "bin" / "llvm-profdata"
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)
    raise RuntimeError(
        "the selected Rust toolchain lacks its bundled llvm-profdata: "
        f"{bundled}"
    )


def parse_output(output: str) -> dict[str, int | str]:
    """Parse and validate one probe output line."""
    match = OUTPUT_LINE.fullmatch(output.strip())
    if match is None:
        raise RuntimeError(f"unexpected probe output: {output!r}")
    values = match.groupdict()
    return {
        "mode": values["mode"],
        "iterations": int(values["iterations"]),
        "seed": int(values["seed"]),
        "elapsed_ns": int(values["elapsed_ns"]),
        "checksum": values["checksum"],
    }


def timed_probe(binary: Path, mode: str, iterations: int, seed: int) -> dict[str, int | str]:
    """Run one fresh process and return in-process and parent wall timing."""
    started = time.perf_counter_ns()
    completed = subprocess.run(
        [str(binary), mode, str(iterations), str(seed)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    process_wall_ns = time.perf_counter_ns() - started
    parsed = parse_output(completed.stdout)
    parsed["process_wall_ns"] = process_wall_ns
    return parsed


def interval(ratios: list[float]) -> dict[str, float | int | None]:
    """Summarize independent positive ratios in log space."""
    if not 2 <= len(ratios) <= 31 or any(
        not math.isfinite(value) or value <= 0 for value in ratios
    ):
        raise ValueError("an interval requires at least two positive finite ratios")
    logs = [math.log(value) for value in ratios]
    mean = statistics.fmean(logs)
    log_ratio_sd = statistics.stdev(logs)
    critical = T95.get(len(logs) - 1, 1.959964)
    half_width = critical * log_ratio_sd / math.sqrt(len(logs))
    lag_one: float | None = None
    if len(logs) >= 3:
        leading = logs[:-1]
        trailing = logs[1:]
        leading_mean = statistics.fmean(leading)
        trailing_mean = statistics.fmean(trailing)
        numerator = sum(
            (left - leading_mean) * (right - trailing_mean)
            for left, right in zip(leading, trailing)
        )
        denominator = math.sqrt(
            sum((value - leading_mean) ** 2 for value in leading)
            * sum((value - trailing_mean) ** 2 for value in trailing)
        )
        if denominator > 0:
            lag_one = numerator / denominator
    return {
        "blocks": len(logs),
        "geometric_mean_ratio": math.exp(mean),
        "log_ratio_sd": log_ratio_sd,
        "t95_low_ratio": math.exp(mean - half_width),
        "t95_high_ratio": math.exp(mean + half_width),
        "min_block_ratio": min(ratios),
        "max_block_ratio": max(ratios),
        "lag1_log_ratio_correlation": lag_one,
    }


def build(
    source: Path,
    work_dir: Path,
    output_dir: Path,
    toolchain_cwd: Path,
) -> tuple[dict[str, Path], dict[str, str]]:
    """Build baseline, instrumented, and two profile-conditioned binaries."""
    rustc = tool("rustc")
    rustc_verbose = run([rustc, "-vV"], cwd=toolchain_cwd)
    release = next(
        line.split(": ", 1)[1]
        for line in rustc_verbose.splitlines()
        if line.startswith("release: ")
    )
    release_parts = tuple(int(part) for part in release.split(".")[:2])
    if release_parts < (1, 93):
        raise RuntimeError(f"rustc {release} is older than the workspace minimum 1.93")
    profdata = rust_profdata(rustc, toolchain_cwd)
    commands: list[str] = []
    # `-Cdebuginfo=1` records the paths rustc was given, and both roots are
    # scratch directories with random names, so without remapping the binary
    # digests describe the directory the run happened to get rather than the
    # source, toolchain, and flags. Remapping makes them comparable across runs
    # and hosts; it rewrites recorded path strings only, not generated code.
    common = [
        rustc,
        "--edition=2024",
        "-O",
        "-Ctarget-cpu=native",
        "-Ccodegen-units=1",
        "-Cdebuginfo=1",
        f"--remap-path-prefix={toolchain_cwd}=/topic18-source",
        f"--remap-path-prefix={work_dir}=/topic18-work",
        "-Clink-arg=-Wl,--emit-relocs",
        str(source),
    ]
    binaries = {
        "baseline": work_dir / "baseline",
        "baseline-copy": work_dir / "baseline-copy",
        "pgo-alpha": work_dir / "pgo-alpha",
        "pgo-beta": work_dir / "pgo-beta",
    }
    run(
        [*common, "-o", str(binaries["baseline"])],
        cwd=toolchain_cwd,
        commands=commands,
    )
    shutil.copy2(binaries["baseline"], binaries["baseline-copy"])

    retained_profiles = output_dir / "profiles"
    retained_profiles.mkdir()
    profile_artifacts: dict[str, object] = {}
    for mode in ("alpha", "beta"):
        profile_dir = work_dir / f"profile-{mode}"
        profile_dir.mkdir()
        instrumented = work_dir / f"instrumented-{mode}"
        run(
            [
                *common,
                f"-Cprofile-generate={profile_dir}",
                "-o",
                str(instrumented),
            ],
            cwd=toolchain_cwd,
            commands=commands,
        )
        training_environment = os.environ.copy()
        training_environment["LLVM_PROFILE_FILE"] = str(
            profile_dir / f"{mode}-%m-%p.profraw"
        )
        training_output = run(
            [str(instrumented), mode, str(ARGS.training_iterations), "1"],
            cwd=work_dir,
            commands=commands,
            env=training_environment,
        )
        parsed_training = parse_output(training_output)
        if parsed_training["elapsed_ns"] <= 0:
            raise RuntimeError(f"{mode} training interval was not positive")
        raw_profiles = sorted(profile_dir.glob("*.profraw"))
        if not raw_profiles:
            raise RuntimeError(f"{mode} training produced no raw profile")

        merged = work_dir / f"{mode}.profdata"
        run(
            [profdata, "merge", "-o", str(merged), str(profile_dir)],
            cwd=work_dir,
            commands=commands,
        )
        profile_summary = run(
            [profdata, "show", "--counts", "--detailed-summary", str(merged)],
            cwd=work_dir,
            commands=commands,
        )
        (output_dir / f"{mode}-profile-summary.txt").write_text(
            profile_summary,
            encoding="utf-8",
        )
        pgo_build_output = run(
            [
                *common,
                f"-Cprofile-use={merged}",
                "-Cllvm-args=-pgo-warn-missing-function",
                "-o",
                str(binaries[f"pgo-{mode}"]),
            ],
            cwd=toolchain_cwd,
            commands=commands,
        )
        (output_dir / f"{mode}-pgo-build.log").write_text(
            pgo_build_output,
            encoding="utf-8",
        )

        mode_profiles = retained_profiles / mode
        mode_profiles.mkdir()
        retained_raw: list[dict[str, int | str]] = []
        for raw_profile in raw_profiles:
            retained = mode_profiles / raw_profile.name
            shutil.copy2(raw_profile, retained)
            retained_raw.append(
                {
                    "file": str(retained.relative_to(output_dir)),
                    "sha256": sha256(retained),
                    "size_bytes": retained.stat().st_size,
                }
            )
        retained_merged = mode_profiles / f"{mode}.profdata"
        shutil.copy2(merged, retained_merged)
        profile_artifacts[mode] = {
            "training_output": parsed_training,
            "instrumented_binary_sha256": sha256(instrumented),
            "instrumented_binary_size_bytes": instrumented.stat().st_size,
            "raw_profiles": retained_raw,
            "merged_profile": {
                "file": str(retained_merged.relative_to(output_dir)),
                "sha256": sha256(retained_merged),
                "size_bytes": retained_merged.stat().st_size,
            },
        }

    (output_dir / "build-commands.txt").write_text(
        "\n".join(commands) + "\n",
        encoding="utf-8",
    )
    tools = {
        "rustc": rustc,
        "llvm_profdata": profdata,
        "cc": tool("cc"),
        "ld": tool("ld"),
        "objdump": tool("objdump"),
        "nm": tool("nm"),
    }
    tool_versions = {
        "rustc_vv": rustc_verbose,
        "llvm_profdata": run([profdata, "--version"], cwd=work_dir),
        "cc": run([tools["cc"], "--version"], cwd=work_dir),
        "cc_target": run([tools["cc"], "-dumpmachine"], cwd=work_dir),
        "ld": run([tools["ld"], "--version"], cwd=work_dir),
        "objdump": run([tools["objdump"], "--version"], cwd=work_dir),
        "nm": run([tools["nm"], "--version"], cwd=work_dir),
    }
    (output_dir / "tool-versions.json").write_text(
        json.dumps(tool_versions, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "profile-artifacts.json").write_text(
        json.dumps(profile_artifacts, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return binaries, tools


def extract_function(disassembly: str, name: str) -> str:
    """Extract one demangled function body from objdump output."""
    lines = disassembly.splitlines()
    marker = f"<{name}>:"
    for index, line in enumerate(lines):
        if marker not in line:
            continue
        body = [line]
        for candidate in lines[index + 1 :]:
            if not candidate.strip():
                break
            body.append(candidate)
        return "\n".join(body) + "\n"
    raise RuntimeError(f"objdump did not contain {name}")


def inspect_codegen(
    binaries: dict[str, Path],
    tools: dict[str, str],
    output_dir: Path,
) -> None:
    """Record symbol placement and verify guarded target promotion."""
    symbol_lines: list[str] = []
    dispatch_bodies: dict[str, str] = {}
    for name in ("baseline", "pgo-alpha", "pgo-beta"):
        symbols = run([tools["nm"], "-n", "-C", str(binaries[name])], cwd=binaries[name].parent)
        symbol_lines.append(name)
        symbol_lines.extend(
            line
            for line in symbols.splitlines()
            if re.search(r"pgo_probe::(main|alpha|beta|dispatch)$", line)
        )
        disassembly = run(
            [tools["objdump"], "-d", "-C", "--no-show-raw-insn", str(binaries[name])],
            cwd=binaries[name].parent,
        )
        body = extract_function(disassembly, "pgo_probe::dispatch")
        dispatch_bodies[name] = body
        (output_dir / f"{name}-dispatch.txt").write_text(body, encoding="utf-8")

    (output_dir / "symbol-layout.txt").write_text(
        "\n".join(symbol_lines) + "\n",
        encoding="utf-8",
    )
    indirect = re.compile(r"\b(?:callq?|jmpq?)\s+\*|\b(?:blr|br)\s+x")
    # objdump interpolates demangled symbol names into operand comments, so a
    # substring search for "cmp" is also satisfied by a neighbouring
    # `core::cmp::*` symbol with no compare instruction present. Anchoring to
    # the address-then-mnemonic column admits only a real compare.
    comparison = re.compile(r"^\s*[0-9a-f]+:\s+cmp", re.MULTILINE)

    def direct(target: str) -> re.Pattern[str]:
        return re.compile(
            rf"\b(?:callq?|jmpq?|bl|b)\s+(?!\*)[^\n]*<pgo_probe::{target}>"
        )

    baseline_has_indirect = indirect.search(dispatch_bodies["baseline"]) is not None
    if not baseline_has_indirect:
        raise RuntimeError("baseline dispatch lacks an inspected indirect call")
    verification: dict[str, object] = {"baseline_indirect": True}
    for mode in ("alpha", "beta"):
        body = dispatch_bodies[f"pgo-{mode}"]
        candidate = {
            "comparison": comparison.search(body) is not None,
            "direct_trained_target": direct(mode).search(body) is not None,
            "indirect_fallback": indirect.search(body) is not None,
        }
        if not all(candidate.values()):
            raise RuntimeError(f"pgo-{mode} dispatch lacks guarded {mode} promotion")
        verification[f"pgo_{mode}"] = candidate
    (output_dir / "codegen-verification.json").write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_correctness(
    binaries: dict[str, Path],
    output_dir: Path,
) -> None:
    """Check all measured binaries against the baseline checksum."""
    results: dict[str, dict[str, dict[str, int | str]]] = {}
    for mode in ("alpha", "beta", "noop"):
        mode_results = {
            name: timed_probe(binary, mode, 10_000, 7)
            for name, binary in binaries.items()
        }
        expected = mode_results["baseline"]["checksum"]
        if any(result["checksum"] != expected for result in mode_results.values()):
            raise RuntimeError(f"checksum mismatch for mode {mode}")
        results[mode] = mode_results
    (output_dir / "correctness.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def measure(
    binaries: dict[str, Path],
    output_dir: Path,
) -> tuple[list[dict[str, int | str]], list[dict[str, object]]]:
    """Run order-balanced fresh-process blocks and summarize their contrasts."""
    comparisons = (
        ("identity-steady", "baseline", "baseline-copy", "alpha"),
        ("identity-startup", "baseline", "baseline-copy", "noop"),
        ("alpha-trained-alpha", "baseline", "pgo-alpha", "alpha"),
        ("alpha-trained-beta", "baseline", "pgo-alpha", "beta"),
        ("profile-choice-alpha", "pgo-beta", "pgo-alpha", "alpha"),
        ("profile-choice-beta", "pgo-beta", "pgo-alpha", "beta"),
        ("alpha-trained-startup", "baseline", "pgo-alpha", "noop"),
    )

    warmups: list[dict[str, int | str]] = []
    for _, left, right, mode in comparisons:
        iterations = 0 if mode == "noop" else ARGS.iterations
        for name in (left, right):
            result = timed_probe(binaries[name], mode, iterations, 2)
            result.update({"binary": name, "comparison_mode": mode})
            warmups.append(result)
    (output_dir / "discarded-warmups.json").write_text(
        json.dumps(warmups, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    fields = (
        "run_sequence",
        "comparison",
        "left",
        "right",
        "block",
        "order",
        "position",
        "label",
        "binary",
        "mode",
        "iterations",
        "seed",
        "elapsed_ns",
        "process_wall_ns",
        "checksum",
        "status",
        "error",
    )
    records: list[dict[str, int | str]] = []
    templates = (("A", "B", "B", "A"), ("B", "A", "A", "B"))
    schedules: dict[str, list[tuple[str, str, str, str]]] = {}
    for comparison_index, (comparison, _, _, _) in enumerate(comparisons):
        schedule = [
            templates[(block + comparison_index) % len(templates)]
            for block in range(ARGS.blocks)
        ]
        random.Random(SCHEDULE_SEED + comparison_index).shuffle(schedule)
        schedules[comparison] = schedule

    raw_path = output_dir / "raw.csv"
    run_sequence = 0
    with raw_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        target.flush()
        for block in range(ARGS.blocks):
            comparison_order = list(range(len(comparisons)))
            random.Random(SCHEDULE_SEED + 10_000 + block).shuffle(comparison_order)
            for comparison_index in comparison_order:
                comparison, left, right, mode = comparisons[comparison_index]
                iterations = 0 if mode == "noop" else ARGS.iterations
                labels = schedules[comparison][block]
                order = "".join(labels)
                for position, label in enumerate(labels):
                    name = left if label == "A" else right
                    metadata: dict[str, int | str] = {
                        "run_sequence": run_sequence,
                        "comparison": comparison,
                        "left": left,
                        "right": right,
                        "block": block,
                        "order": order,
                        "position": position,
                        "label": label,
                        "binary": name,
                        "mode": mode,
                        "iterations": iterations,
                        "seed": 2,
                    }
                    try:
                        result = timed_probe(binaries[name], mode, iterations, 2)
                    except Exception as error:
                        failed = {
                            **metadata,
                            "elapsed_ns": "",
                            "process_wall_ns": "",
                            "checksum": "",
                            "status": "failed",
                            "error": f"{type(error).__name__}: {error}",
                        }
                        writer.writerow(failed)
                        target.flush()
                        raise
                    result.update(
                        {
                            **metadata,
                            "status": "ok",
                            "error": "",
                        }
                    )
                    writer.writerow(result)
                    target.flush()
                    records.append(result)
                    run_sequence += 1

    summaries: list[dict[str, object]] = []
    for comparison, left, right, mode in comparisons:
        steady_ratios: list[float] = []
        wall_ratios: list[float] = []
        block_rows: list[dict[str, object]] = []
        for block in range(ARGS.blocks):
            selected = [
                row
                for row in records
                if row["comparison"] == comparison and row["block"] == block
            ]
            if len(selected) != 4:
                raise RuntimeError(f"block {block} is incomplete in {comparison}")
            checksums = {str(row["checksum"]) for row in selected}
            if len(checksums) != 1:
                raise RuntimeError(f"block {block} checksum mismatch in {comparison}")
            left_rows = [row for row in selected if row["binary"] == left]
            right_rows = [row for row in selected if row["binary"] == right]
            if len(left_rows) != 2 or len(right_rows) != 2:
                raise RuntimeError(f"block {block} is unbalanced in {comparison}")

            def block_ratio(field: str) -> float:
                left_log_mean = statistics.fmean(
                    math.log(int(row[field])) for row in left_rows
                )
                right_log_mean = statistics.fmean(
                    math.log(int(row[field])) for row in right_rows
                )
                return math.exp(right_log_mean - left_log_mean)

            wall_ratio = block_ratio("process_wall_ns")
            wall_ratios.append(wall_ratio)
            block_result: dict[str, object] = {
                "block": block,
                "order": selected[0]["order"],
                "process_wall_ratio": wall_ratio,
            }
            if mode != "noop":
                steady_ratio = block_ratio("elapsed_ns")
                steady_ratios.append(steady_ratio)
                block_result["steady_ratio"] = steady_ratio
            block_rows.append(block_result)

        summaries.append(
            {
                "comparison": comparison,
                "left": left,
                "right": right,
                "mode": mode,
                "ratio_direction": "right_over_left",
                "steady": interval(steady_ratios) if steady_ratios else None,
                "process_wall": interval(wall_ratios),
                "blocks": block_rows,
            }
        )

    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as target:
        summary_fields = (
            "comparison",
            "left",
            "right",
            "ratio_direction",
            "mode",
            "metric",
            "blocks",
            "geometric_mean_ratio",
            "log_ratio_sd",
            "t95_low_ratio",
            "t95_high_ratio",
            "lag1_log_ratio_correlation",
        )
        writer = csv.DictWriter(target, fieldnames=summary_fields)
        writer.writeheader()
        for summary in summaries:
            for metric in ("steady", "process_wall"):
                estimate = summary[metric]
                if estimate is None:
                    continue
                writer.writerow(
                    {
                        "comparison": summary["comparison"],
                        "left": summary["left"],
                        "right": summary["right"],
                        "ratio_direction": summary["ratio_direction"],
                        "mode": summary["mode"],
                        "metric": metric,
                        **{
                            key: estimate[key]
                            for key in summary_fields
                            if key in estimate
                        },
                    }
                )
    return records, summaries


def post_link_tools(output_dir: Path) -> dict[str, dict[str, str | None]]:
    """Record availability and version output for post-link tools."""
    result: dict[str, dict[str, str | None]] = {}
    for name in ("llvm-bolt", "perf2bolt", "merge-fdata", "perf"):
        path = shutil.which(name)
        version: str | None = None
        if path is not None:
            completed = subprocess.run(
                [path, "--version"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            version = completed.stdout.splitlines()[0] if completed.stdout else None
        result[name] = {"path": path, "version": version}
    (output_dir / "post-link-tools.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def hash_binaries(binaries: dict[str, Path]) -> dict[str, str]:
    """Hash every measured binary."""
    return {name: sha256(path) for name, path in binaries.items()}


def main() -> None:
    """Run the retained Linux experiment."""
    if platform.system() != "Linux":
        raise RuntimeError("the retained experiment requires Linux ELF tooling")
    topic_dir = Path(__file__).resolve().parents[1]
    repository_root = topic_dir.parents[1]
    source = topic_dir / "examples" / "pgo_probe.rs"
    work_dir = ARGS.work_dir.resolve()
    output_dir = ARGS.output_dir.resolve()
    require_empty(work_dir, "work directory")
    require_empty(output_dir, "output directory")

    binaries, tools = build(source, work_dir, output_dir, repository_root)
    binary_hashes_before = hash_binaries(binaries)
    if binary_hashes_before["baseline"] != binary_hashes_before["baseline-copy"]:
        raise RuntimeError("the identity-control binaries are not byte-identical")
    (output_dir / "binary-sha256.before.json").write_text(
        json.dumps(binary_hashes_before, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verify_correctness(binaries, output_dir)
    inspect_codegen(binaries, tools, output_dir)
    _, summaries = measure(binaries, output_dir)
    postlink = post_link_tools(output_dir)
    binary_hashes = hash_binaries(binaries)
    if binary_hashes != binary_hashes_before:
        raise RuntimeError("a measured binary changed after inspection began")
    (output_dir / "binary-sha256.json").write_text(
        json.dumps(binary_hashes, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = {
        "host": socket.gethostname(),
        "uname": platform.uname()._asdict(),
        "source": str(source),
        "source_sha256": sha256(source),
        "blocks": ARGS.blocks,
        "iterations": ARGS.iterations,
        "training_iterations": ARGS.training_iterations,
        "training_seed": 1,
        "measurement_seed": 2,
        "schedule_seed": SCHEDULE_SEED,
        "rustup_toolchain_environment": os.environ.get("RUSTUP_TOOLCHAIN"),
        "tools": tools,
        "post_link_tools": postlink,
        "binary_sha256": binary_hashes,
        "summaries": summaries,
    }
    (output_dir / "experiment.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=20_000_000)
    parser.add_argument("--training-iterations", type=int, default=5_000_000)
    arguments = parser.parse_args()
    if arguments.blocks < 2 or arguments.blocks > 31:
        parser.error("--blocks must be between 2 and 31")
    # The schedule alternates ABBA and BAAB across `range(blocks)`, so an odd
    # count leaves one comparison order with an extra block and folds position
    # effects into the reported ratios.
    if arguments.blocks % 2 != 0:
        parser.error("--blocks must be even so each comparison is order-balanced")
    if arguments.iterations <= 0 or arguments.training_iterations <= 0:
        parser.error("iteration counts must be positive")
    return arguments


ARGS = parse_args()

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        if error.stdout:
            print(error.stdout, file=sys.stderr)
        if error.stderr:
            print(error.stderr, file=sys.stderr)
        raise
