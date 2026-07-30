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
from typing import NamedTuple


class GuardShape(NamedTuple):
    """What the dispatch control flow says about one promoted call.

    Both fields come from the same successor graph and the same guard branch, so they
    describe one shape rather than two independent searches that happen to agree.
    """

    guarded: bool
    fallback_reachable: bool



# Variables every recorded command must carry, whether or not the driver set
# them itself. `RUSTUP_TOOLCHAIN` selects the compiler and is inherited from the
# wrapper, and the snapshot carries a `rust-toolchain.toml` pin that a rustup
# proxy applies in its absence, so a replay without it builds with the workspace
# toolchain rather than the experiment toolchain.
ALWAYS_RECORDED_ENVIRONMENT = ("RUSTUP_TOOLCHAIN",)

# Timed probes run with this environment rather than the driver's. `execve`
# copies the environment into the new process and the loader walks it, so an
# inherited `PATH` makes `process_wall_ns` and the `noop` startup comparison
# depend on how long the caller's environment happens to be. The probe reads its
# arguments only, so an empty environment removes that term and fixes it across
# hosts; `experiment.json` records it.
PROBE_ENVIRONMENT: dict[str, str] = {}


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
        # Record the assignments a replay needs. `LLVM_PROFILE_FILE` decides
        # where a training run deposits its raw profile, and without it the
        # recorded `llvm-profdata merge` reads a directory the replay never
        # populated. Only per-command differences would be recorded otherwise,
        # which is why ALWAYS_RECORDED_ENVIRONMENT exists.
        effective = {**os.environ, **(env or {})}
        overrides = {
            name: value
            for name, value in (env or {}).items()
            if os.environ.get(name) != value
        }
        for name in ALWAYS_RECORDED_ENVIRONMENT:
            if name in effective:
                overrides[name] = effective[name]
        recorded = [f"{name}={value}" for name, value in sorted(overrides.items())]
        commands.append(shlex.join([*recorded, *command]))
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


def bound_tool(name: str) -> str | None:
    """Return the wrapper-bound path for one executable, or None.

    The wrapper resolves and digests its tools before any of them runs, then
    prepends the selected toolchain to `PATH` for this driver. A `shutil.which`
    lookup therefore searches a different `PATH` than the one those digests
    describe, and a toolchain `bin` holding a `cc`, `nm`, or `objdump` would
    supply a program that no receipt names. Prefer the path the wrapper bound.
    """
    bound = os.environ.get("TOPIC18_TOOL_" + name.replace("-", "_"))
    if bound is None:
        return None
    if not os.path.isabs(bound) or not os.access(bound, os.X_OK):
        raise RuntimeError(f"bound tool path is not an executable: {name}={bound}")
    return bound


def tool(name: str) -> str:
    """Resolve one required executable."""
    resolved = bound_tool(name) or shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required executable is unavailable: {name}")
    return resolved


def rust_profdata(rustc: str, cwd: Path) -> str:
    """Resolve the llvm-profdata bundled with the active Rust toolchain.

    Prefer the path the wrapper bound: it requires this program and digests it before
    anything runs, so using its answer keeps the profiler that merges the training
    profiles the one the receipt names.
    """
    bound = bound_tool("llvm-profdata")
    if bound is not None:
        return bound
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


def rust_lld(rustc: str, cwd: Path) -> Path | None:
    """Locate the linker bundled with the active Rust toolchain, if it ships one."""
    verbose = run([rustc, "-vV"], cwd=cwd)
    host = next(
        line.split(": ", 1)[1]
        for line in verbose.splitlines()
        if line.startswith("host: ")
    )
    sysroot = Path(run([rustc, "--print", "sysroot"], cwd=cwd).strip())
    bundled = sysroot / "lib" / "rustlib" / host / "bin" / "rust-lld"
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return bundled
    return None


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
        env=PROBE_ENVIRONMENT,
    )
    process_wall_ns = time.perf_counter_ns() - started
    parsed = parse_output(completed.stdout)
    # The child reports its own mode, iteration count, and seed, and the caller later
    # overwrites those fields with the requested metadata, so a binary that ran a
    # different workload than it was asked for would be recorded under the requested
    # label. Checksum comparison does not catch it either: the checksums agree whenever
    # every binary is wrong the same way. Compare what it reports with what it was
    # given.
    # `noop` performs no work and reports `iterations=0` whatever it was asked for, so
    # the expected count comes from the probe's contract rather than from the argument.
    # Keeping that rule here means no caller has to remember it.
    expected = {
        "mode": mode,
        "iterations": 0 if mode == "noop" else iterations,
        "seed": seed,
    }
    reported = {field: parsed[field] for field in expected}
    if reported != expected:
        raise RuntimeError(
            f"probe {binary} reported {reported} for an invocation of {expected}"
        )
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
    # The `gcc` linker flavor invokes `cc` from `PATH`, and the wrapper prepends the
    # selected toolchain's directory, so a toolchain-local `cc` would link the
    # measured binaries while the receipt named the one the wrapper resolved.
    # Recording `cc` for the version probe does not constrain what rustc links with,
    # so name it. When the wrapper did not bind one, leave the flag off and let rustc
    # resolve as before rather than guessing a path.
    # `cc` resolves its own child `ld` through `PATH`, and the wrapper prepends the
    # selected toolchain directory, so pinning the driver alone still let a
    # toolchain-local `ld` link the measured binaries. `-B<dir>/` makes `cc` look for
    # its subprograms there first, which pins the linker the receipt names.
    bound_cc = bound_tool("cc")
    # The wrapper builds a directory it owns holding one program named `ld`, verified
    # against the digest taken before anything ran. Pointing `-B` at the recorded linker's
    # own directory would only reorder gcc's search — prefix, standard prefixes, then
    # `PATH` — and hiding that file would still let another `ld` link the binaries.
    linker_directory = os.environ.get("TOPIC18_LINKER_DIR")
    bound_ld = bound_tool("ld")
    linker_options: list[str] = []
    if bound_cc is not None:
        linker_options.append(f"-Clinker={bound_cc}")
        if linker_directory is not None:
            if not os.path.isdir(linker_directory):
                raise RuntimeError(
                    f"bound linker directory is not a directory: {linker_directory}"
                )
            linker_options.append(f"-Clink-arg=-B{linker_directory}/")
        elif bound_ld is not None:
            linker_options.append(f"-Clink-arg=-B{os.path.dirname(bound_ld)}/")
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
        *linker_options,
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
        # The training run is parsed directly rather than through `timed_probe`, so it
        # needs the same identity check: the merged profile builds `pgo-{mode}` and the
        # retained labels describe the requested training identity, so a run that
        # executed a different workload would be recorded as this one.
        expected_training = {"mode": mode, "iterations": ARGS.training_iterations, "seed": 1}
        reported_training = {field: parsed_training[field] for field in expected_training}
        if reported_training != expected_training:
            raise RuntimeError(
                f"training probe reported {reported_training} for an invocation of "
                f"{expected_training}"
            )
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
        # `-pgo-warn-missing-function` is passed above precisely so this is
        # observable: LLVM is otherwise silent when it finds no profile data for a
        # function it is compiling. A warning here means the merged profile did not
        # cover code this candidate is about to be measured as profile-conditioned, so
        # retaining the text and continuing would report a claim the profile does not
        # support. Refuse before the candidate is measured or kept.
        missing_profile = [
            line
            for line in pgo_build_output.splitlines()
            if "no profile data available for function" in line
        ]
        if missing_profile:
            raise RuntimeError(
                f"{mode} profile-use build reports functions with no profile data, so "
                "the candidate is not profile-conditioned: "
                + "; ".join(missing_profile[:5])
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
    # `cc` is the linker driver, and rustc may hand the link to the toolchain's
    # bundled `rust-lld` rather than the `ld` on `PATH` — on x86-64 Linux it does
    # by default. Recording only the `PATH` linker names a tool that never ran,
    # so name what each entry is and record the bundled linker when present.
    bundled_lld = rust_lld(rustc, toolchain_cwd)
    bound_lld = bound_tool("rust-lld")
    tool_versions = {
        "rustc_vv": rustc_verbose,
        "llvm_profdata": run([profdata, "--version"], cwd=work_dir),
        "cc": run([tools["cc"], "--version"], cwd=work_dir),
        "cc_target": run([tools["cc"], "-dumpmachine"], cwd=work_dir),
        "ld_on_path": run([tools["ld"], "--version"], cwd=work_dir),
        # Probe only a path the wrapper bound. `rust-lld` is optional, so the
        # wrapper does not fail when the toolchain ships none; that means a file
        # appearing after the binding would otherwise be executed here — after the
        # timings, before the manifest — with no digest covering it.
        "rust_lld_path": (bound_lld or (str(bundled_lld) if bundled_lld else "unavailable")),
        "rust_lld": (
            run([bound_lld, "-flavor", "gnu", "--version"], cwd=work_dir)
            if bound_lld
            else "not-recorded: linker is not bound by the wrapper"
        ),
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

    def direct(target: str) -> re.Pattern[str]:
        return re.compile(
            rf"\b(?:callq?|jmpq?|bl|b)\s+(?!\*)[^\n]*<pgo_probe::{target}>"
        )

    instruction = re.compile(r"^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$")
    # x86 is handled by excluding a prefix rather than enumerating: `jmp` and its `jmpq`,
    # `jmpl`, and `jmpw` spellings are the only unconditional jumps, and every conditional
    # form — Jcc plus `jcxz`/`jecxz`/`jrcxz` — begins with something else. `j(?!mp$)`
    # would exclude only the bare spelling and let `jmpq` through as a conditional branch.
    #
    # AArch64 has to be enumerated, because `al` and `nv` are conditions in the same
    # `b.<cond>` syntax as the real ones and both execute unconditionally, so a suffix
    # wildcard would treat `b.al` as a branch with two edges. `bc.<cond>` is the FEAT_HBC
    # hinted form of the same branch and takes the same condition set.
    conditional_mnemonic = re.compile(
        r"^(?:"
        r"j(?!mp)[a-z]+"
        r"|bc?\.(?:eq|ne|cs|hs|cc|lo|mi|pl|vs|vc|hi|ls|ge|lt|gt|le)"
        r"|cbz|cbnz|tbz|tbnz"
        r")$"
    )
    # Instructions after which control does not continue to the next address and which
    # name no destination in this function. The trap forms matter as much as `ret`: objdump
    # leaves `int3`, `ud0`, `ud1`, and `ud2` as inter-block padding, and treating one as an
    # ordinary instruction invents a fall-through edge into whatever bytes follow it — which
    # could make a call the code would never reach look like the guarded one.
    path_terminator = re.compile(r"^(?:ret[q]?|hlt|int3|ud0|ud1|ud2|brk|udf)$")
    # Unconditional transfers. `call`, `bl`, and `blr` are absent because they return to
    # the following instruction, so they do continue. `b.al` and `b.nv` belong here rather
    # than with the conditional branches: they use the conditional encoding but always
    # execute, so modelling them as fall-through would give the following instruction an
    # edge it does not have and could make an unreachable call look guarded.
    jump_transfer = re.compile(r"^(?:jmp[qlw]?|b|br|bc?\.(?:al|nv))$")

    def branch_destination(operands: str) -> int | None:
        """Return a transfer's destination address, or None when it is not concrete."""
        # objdump appends a `<symbol+offset>` comment; the destination is the last
        # bare hex operand before it. An indirect operand such as `*%rax` or `x8`
        # parses as nothing, which is how an unknown target is reported.
        for token in reversed(operands.split("<")[0].replace(",", " ").split()):
            try:
                return int(token, 16)
            except ValueError:
                continue
        return None

    def guarded_promotion(body: str, target: str) -> GuardShape:
        """Describe the promoted call's position in the dispatch control flow.

        This is a reachability question and is answered as one. Comparing addresses
        cannot decide it: a transfer that leaves before the call can land past the call
        and come back to it, a conditional branch's two edges can rejoin ahead of it,
        and either makes both outcomes execute the call while every ordering test says
        otherwise. So build the successor graph the disassembly describes and ask
        directly whether some conditional branch has one edge that reaches the call and
        one that does not.

        No separate compare is required. A conditional branch tests something by
        construction, and demanding a particular compare mnemonic rejects the flag
        producers that are not on the list — `cbz` and friends carry their own test, and
        `adds`, `ands`, `tst`, and `fcmp` set flags without being a compare. What the
        claim rests on is the edge asymmetry, which is what this measures.

        The fallback is answered on the same graph: the guard edge that does not reach
        the promoted call must reach an indirect transfer, so the shape recorded is one
        the candidate actually has rather than one assembled from separate searches.

        What it does not establish is that the branch tests the trained target's
        address. That operand is usually materialised into a register first, so the
        disassembly does not carry it; `no_direct_untrained_target` and the baseline
        check cover that ground instead.
        """
        decoded = [
            match
            for match in (instruction.match(line) for line in body.splitlines())
            if match is not None
        ]
        if not decoded:
            return GuardShape(False, False)
        index_of_address = {
            int(match.group(1), 16): position for position, match in enumerate(decoded)
        }

        def target_index(operands: str) -> int | None:
            """Resolve a transfer's destination to an index in this listing."""
            # A destination outside the listing — an indirect operand, or a branch out
            # of this function — is an edge that leaves, reported as None.
            destination = branch_destination(operands)
            if destination is None:
                return None
            return index_of_address.get(destination)

        def edges(position: int) -> tuple[int | None, ...]:
            """Return the successors of one instruction, `None` for an edge that leaves."""
            mnemonic = decoded[position].group(2)
            operands = decoded[position].group(3)
            following = position + 1 if position + 1 < len(decoded) else None
            if path_terminator.match(mnemonic):
                return ()
            if conditional_mnemonic.match(mnemonic):
                return (following, target_index(operands))
            if jump_transfer.match(mnemonic):
                return (target_index(operands),)
            return (following,)

        def reaches(start: int | None, goal: int, blocked: int | None = None) -> bool:
            """Report whether `goal` is reachable from `start` along those successors.

            `blocked` removes one instruction from the graph, which is how the guard's
            position relative to the entry is established: if deleting a branch makes the
            call unreachable from the entry, every path to the call runs through it.
            """
            if start is None or start == blocked:
                return False
            seen = set()
            pending = [start]
            while pending:
                position = pending.pop()
                if position == goal:
                    return True
                if position in seen or position == blocked:
                    continue
                seen.add(position)
                pending.extend(
                    successor for successor in edges(position) if successor is not None
                )
            return False

        def reaches_indirect(start: int | None, avoid: int) -> bool:
            """Report whether an indirect transfer is reachable without reaching `avoid`."""
            if start is None:
                return False
            seen = set()
            pending = [start]
            while pending:
                position = pending.pop()
                if position == avoid or position in seen:
                    continue
                seen.add(position)
                if indirect.search(decoded[position].group(0)):
                    return True
                pending.extend(
                    successor for successor in edges(position) if successor is not None
                )
            return False

        direct_pattern = direct(target)
        promoted = [
            position
            for position, match in enumerate(decoded)
            if direct_pattern.search(match.group(0))
        ]
        # The listing starts at the function entry, so index 0 is where every invocation
        # begins.
        entry = 0
        # An outer branch can dominate the promoted call and split on it without being the
        # branch that chooses between the direct call and the indirect fallback — an early
        # return on a null pointer, say. Returning that branch's shape would report
        # `guarded` with no reachable fallback and abort the run over a layout that is
        # correct. So keep looking, take the first complete shape, and fall back to the best
        # partial one so the failure still says which half was missing.
        best = GuardShape(False, False)
        for call_index in promoted:
            # A call the entry cannot reach is not the one being measured, and asymmetry
            # around it says nothing about the shape that runs.
            if not reaches(entry, call_index):
                continue
            for position, match in enumerate(decoded):
                if not conditional_mnemonic.match(match.group(2)):
                    continue
                # Successor asymmetry on its own is satisfied by branches that no
                # invocation consults before the call — an unreachable one, or one placed
                # after it whose taken edge is a back edge to it. Require the branch to
                # sit on every path from the entry to the call, so that whether the call
                # runs is actually this branch's decision.
                if reaches(entry, call_index, blocked=position):
                    continue
                not_taken, taken = edges(position)
                promoted_edge_reaches = reaches(not_taken, call_index)
                if promoted_edge_reaches == reaches(taken, call_index):
                    continue
                # The other edge has to arrive somewhere that dispatches indirectly.
                # Searching the whole body for an indirect instruction instead would count
                # one sitting in a block this guard never reaches, and then the retained
                # shape claims a fallback the candidate does not have.
                other_edge = taken if promoted_edge_reaches else not_taken
                shape = GuardShape(True, reaches_indirect(other_edge, call_index))
                if shape.fallback_reachable:
                    return shape
                best = shape
        return best

    baseline_body = dispatch_bodies["baseline"]
    baseline_has_indirect = indirect.search(baseline_body) is not None
    if not baseline_has_indirect:
        raise RuntimeError("baseline dispatch lacks an inspected indirect call")
    # Requiring only that an indirect call survives is not enough to call the
    # promotion profile-conditioned: a toolchain that emits a guarded direct call in
    # the unprofiled build keeps its indirect fallback too, so the candidate check
    # below would pass on a shape the control already has. Reject a direct call to
    # either target in the baseline, so the comparison rests on a difference.
    baseline_direct = [
        target for target in ("alpha", "beta") if direct(target).search(baseline_body)
    ]
    if baseline_direct:
        raise RuntimeError(
            "baseline dispatch already contains a direct call to "
            f"{', '.join(baseline_direct)}, so promotion is not profile-conditioned"
        )
    verification: dict[str, object] = {
        "baseline_indirect": True,
        "baseline_direct_targets": [],
    }
    for mode in ("alpha", "beta"):
        body = dispatch_bodies[f"pgo-{mode}"]
        other_mode = "beta" if mode == "alpha" else "alpha"
        # Requiring the trained target admits a toolchain that direct-calls both, and
        # then the dispatch shape is not evidence that this profile chose this target.
        # The untrained target must stay behind the indirect call.
        #
        # `guarded_trained_target` subsumes a standalone "a compare exists" predicate:
        # it requires a compare before the branch that makes this call conditional. A
        # separate compare test would also disagree with it, because the guard forms it
        # accepts include `test`, `subs`, and `cmn`, so a promotion guarded by `subs`
        # plus `cbz` would satisfy the guard and fail the compare test.
        shape = guarded_promotion(body, mode)
        candidate = {
            "direct_trained_target": direct(mode).search(body) is not None,
            "guarded_trained_target": shape.guarded,
            "indirect_fallback": shape.fallback_reachable,
            "no_direct_untrained_target": direct(other_mode).search(body) is None,
        }
        if not all(candidate.values()):
            raise RuntimeError(
                f"pgo-{mode} dispatch lacks guarded {mode} promotion: {candidate}"
            )
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
    """Record availability and version output for post-link tools.

    These are optional, so a missing one is recorded rather than fatal. Running
    one is still an execution: the version probe happens after the timings but
    before `binary-sha256.json` and `evidence.sha256` are written, so a program
    taken from a caller-writable `PATH` entry could mutate retained files here.
    Only execute a path the wrapper bound and digested; when it did not bind one,
    record availability from the lookup without running it.
    """
    result: dict[str, dict[str, str | None]] = {}
    for name in ("llvm-bolt", "perf2bolt", "merge-fdata", "perf"):
        bound = bound_tool(name)
        path = bound or shutil.which(name)
        version: str | None = None
        if bound is not None:
            completed = subprocess.run(
                [bound, "--version"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            version = completed.stdout.splitlines()[0] if completed.stdout else None
        elif path is not None:
            version = "not-recorded: tool is not bound by the wrapper"
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
        "probe_environment": PROBE_ENVIRONMENT,
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
