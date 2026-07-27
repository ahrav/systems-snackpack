#!/usr/bin/env python3
"""Build, inspect, and measure the Topic 17 glibc dynamic-binding fixture."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time


SYMBOLS = 4096
# Two-sided 95% Student-t critical value for 12 blocks and 11 degrees of freedom.
T95_DF11 = 2.200985
def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    """Runs one required command and returns merged text output."""
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


def child_env(*, eager: bool) -> dict[str, str]:
    """Returns a child environment with inherited loader controls removed."""
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("LD_") or name == "GLIBC_TUNABLES":
            environment.pop(name)
    if eager:
        environment["LD_BIND_NOW"] = "1"
    return environment


def sha256(path: Path) -> str:
    """Returns the SHA-256 digest of one regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_sources(work_dir: Path) -> None:
    """Generates the fixed 4,096-import C fixture."""
    library = ["#include <stdint.h>"]
    declarations: list[str] = []
    calls: list[str] = []
    for index in range(SYMBOLS):
        name = f"probe_{index:04d}"
        library.append(
            '__attribute__((noinline,visibility("default"))) '
            f"int {name}(int x) {{ return x + {index + 1}; }}"
        )
        declarations.append(f"extern int {name}(int);")
        calls.append(f"    sum += (uint64_t){name}(x);")

    main = [
        "#define _GNU_SOURCE",
        "#include <inttypes.h>",
        "#include <stdint.h>",
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <string.h>",
        "#include <time.h>",
        *declarations,
        "",
        "__attribute__((noinline))",
        "static uint64_t touch_all(int x) {",
        "    uint64_t sum = 0;",
        *calls,
        "    return sum;",
        "}",
        "",
        "static uint64_t monotonic_raw_ns(void) {",
        "    struct timespec ts;",
        "    if (clock_gettime(CLOCK_MONOTONIC_RAW, &ts) != 0) abort();",
        "    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) +",
        "           (uint64_t)ts.tv_nsec;",
        "}",
        "",
        "int main(int argc, char **argv) {",
        '    const char *mode = argc > 1 ? argv[1] : "noop";',
        '    if (strcmp(mode, "noop") == 0) return 0;',
        '    if (strcmp(mode, "touch") == 0) {',
        "        uint64_t start = monotonic_raw_ns();",
        "        uint64_t checksum = touch_all(7);",
        "        uint64_t elapsed = monotonic_raw_ns() - start;",
        '        printf("{\\"elapsed_ns\\":%" PRIu64 ",\\"checksum\\":%" PRIu64 "}\\n",',
        "               elapsed, checksum);",
        "        return 0;",
        "    }",
        '    if (strcmp(mode, "steady") != 0 || argc != 3) return 2;',
        "    char *end = NULL;",
        "    uint64_t iterations = strtoull(argv[2], &end, 10);",
        "    if (!end || *end || iterations == 0) return 2;",
        "    uint64_t checksum = (uint64_t)probe_0000(7);",
        "    for (uint64_t i = 0; i < iterations; ++i)",
        "        checksum += (uint64_t)probe_0000((int)(i & 1023));",
        "    uint64_t start = monotonic_raw_ns();",
        "    for (uint64_t i = 0; i < iterations; ++i)",
        "        checksum += (uint64_t)probe_0000((int)(i & 1023));",
        "    uint64_t elapsed = monotonic_raw_ns() - start;",
        '    printf("{\\"elapsed_ns\\":%" PRIu64 ",\\"checksum\\":%" PRIu64 "}\\n",',
        "           elapsed, checksum);",
        "    return 0;",
        "}",
    ]
    (work_dir / "libmany.c").write_text("\n".join(library) + "\n", encoding="utf-8")
    (work_dir / "main.c").write_text("\n".join(main) + "\n", encoding="utf-8")


def build(work_dir: Path, output_dir: Path) -> None:
    """Builds the shared library and three position-independent executables."""
    generate_sources(work_dir)
    commands = [
        [
            "cc",
            "-O2",
            "-fPIC",
            "-fno-lto",
            "-shared",
            "-Wl,-z,defs",
            "-Wl,-soname,libmany.so",
            "-Wl,--hash-style=gnu",
            "-Wl,--build-id=sha1",
            "-o",
            "libmany.so",
            "libmany.c",
        ],
        [
            "cc",
            "-O2",
            "-fPIE",
            "-pie",
            "-fplt",
            "-fno-lto",
            "main.c",
            "-L.",
            "-lmany",
            "-Wl,-rpath,$ORIGIN",
            "-Wl,--hash-style=gnu",
            "-Wl,--build-id=sha1",
            "-Wl,-z,relro",
            "-Wl,-z,lazy",
            "-o",
            "lazy",
        ],
        [
            "cc",
            "-O2",
            "-fPIE",
            "-pie",
            "-fplt",
            "-fno-lto",
            "main.c",
            "-L.",
            "-lmany",
            "-Wl,-rpath,$ORIGIN",
            "-Wl,--hash-style=gnu",
            "-Wl,--build-id=sha1",
            "-Wl,-z,relro",
            "-Wl,-z,now",
            "-o",
            "now",
        ],
        [
            "cc",
            "-O2",
            "-fPIE",
            "-pie",
            "-fno-plt",
            "-fno-lto",
            "main.c",
            "-L.",
            "-lmany",
            "-Wl,-rpath,$ORIGIN",
            "-Wl,--hash-style=gnu",
            "-Wl,--build-id=sha1",
            "-Wl,-z,relro",
            "-Wl,-z,now",
            "-o",
            "noplt",
        ],
    ]
    with (output_dir / "build-commands.txt").open("w", encoding="utf-8") as receipt:
        for command in commands:
            receipt.write(" ".join(command) + "\n")
            receipt.write(run(command, cwd=work_dir))


def verify_touch(executable: Path, *, eager: bool) -> dict[str, int]:
    """Runs the all-import correctness path and validates its checksum."""
    output = subprocess.check_output(
        [str(executable), "touch"],
        env=child_env(eager=eager),
        text=True,
    )
    result = json.loads(output)
    expected = SYMBOLS * 7 + SYMBOLS * (SYMBOLS + 1) // 2
    if result["checksum"] != expected or result["elapsed_ns"] <= 0:
        raise RuntimeError(f"touch correctness failed: {result}")
    return result


def inspect(work_dir: Path, output_dir: Path) -> None:
    """Records final-image metadata and verifies the binding treatments."""
    binaries = ("libmany.so", "lazy", "now", "noplt")
    digests = {name: sha256(work_dir / name) for name in binaries}
    (output_dir / "binary-sha256.json").write_text(
        json.dumps(digests, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    relocations = run(["readelf", "-rW", "lazy"], cwd=work_dir)
    (output_dir / "lazy-relocations.txt").write_text(relocations, encoding="utf-8")
    imported = {
        match.group(1)
        for line in relocations.splitlines()
        if ("JUMP_SLOT" in line or "JUMP_SLO" in line)
        and (match := re.search(r"\b(probe_[0-9]{4})\b", line))
    }
    if len(imported) != SYMBOLS:
        raise RuntimeError(f"expected {SYMBOLS} named JUMP_SLOT imports, found {len(imported)}")

    for name in ("lazy", "now", "noplt"):
        dynamic = run(["readelf", "-dW", name], cwd=work_dir)
        program = run(["readelf", "-lW", name], cwd=work_dir)
        notes = run(["readelf", "-nW", name], cwd=work_dir)
        disassembly = run(["objdump", "-drwC", name], cwd=work_dir)
        (output_dir / f"{name}-dynamic.txt").write_text(dynamic, encoding="utf-8")
        (output_dir / f"{name}-program-headers.txt").write_text(program, encoding="utf-8")
        (output_dir / f"{name}-notes.txt").write_text(notes, encoding="utf-8")
        with gzip.open(output_dir / f"{name}-disassembly.txt.gz", "wt", encoding="utf-8") as target:
            target.write(disassembly)

    lazy_dynamic = (output_dir / "lazy-dynamic.txt").read_text(encoding="utf-8")
    now_dynamic = (output_dir / "now-dynamic.txt").read_text(encoding="utf-8")
    if "BIND_NOW" in lazy_dynamic or "BIND_NOW" not in now_dynamic:
        raise RuntimeError("linked dynamic flags do not distinguish lazy and now")

    correctness = {
        "lazy": verify_touch(work_dir / "lazy", eager=False),
        "same_image_eager": verify_touch(work_dir / "lazy", eager=True),
        "linked_now": verify_touch(work_dir / "now", eager=False),
        "noplt": verify_touch(work_dir / "noplt", eager=False),
    }
    (output_dir / "correctness.json").write_text(
        json.dumps(correctness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    diagnostics = child_env(eager=False)
    diagnostics["LD_DEBUG"] = "statistics,bindings"
    completed = subprocess.run(
        [str(work_dir / "lazy"), "touch"],
        env=diagnostics,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    (output_dir / "lazy-ld-debug.stdout").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "lazy-ld-debug.stderr").write_text(completed.stderr, encoding="utf-8")
    if not re.search(r"binding file .*probe_0000", completed.stderr):
        raise RuntimeError("LD_DEBUG did not report the expected lazy probe_0000 binding")


def timed_sample(
    executable: Path,
    *,
    outcome: str,
    eager: bool,
    iterations: int,
) -> tuple[int, int | None]:
    """Returns one elapsed interval and its optional child checksum."""
    environment = child_env(eager=eager)
    if outcome == "startup":
        started = time.perf_counter_ns()
        subprocess.run(
            [str(executable), "noop"],
            env=environment,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return time.perf_counter_ns() - started, None

    mode = "touch" if outcome == "first_use" else "steady"
    command = [str(executable), mode]
    if mode == "steady":
        command.append(str(iterations))
    result = json.loads(subprocess.check_output(command, env=environment, text=True))
    if result["elapsed_ns"] <= 0 or result["checksum"] <= 0:
        raise RuntimeError(f"invalid child result: {result}")
    return int(result["elapsed_ns"]), int(result["checksum"])


def summarize(contrasts: list[float]) -> dict[str, float | int]:
    """Summarizes the retained experiment's 12 independent block contrasts."""
    mean = statistics.mean(contrasts)
    sd = statistics.stdev(contrasts)
    half_width = T95_DF11 * sd / math.sqrt(len(contrasts))
    return {
        "blocks": len(contrasts),
        "geometric_mean_ratio": math.exp(mean),
        "log_ratio_sd": sd,
        "t95_low_ratio": math.exp(mean - half_width),
        "t95_high_ratio": math.exp(mean + half_width),
        "min_block_ratio": math.exp(min(contrasts)),
        "max_block_ratio": math.exp(max(contrasts)),
    }


def benchmark(
    work_dir: Path,
    output_dir: Path,
    *,
    blocks: int,
    iterations: int,
) -> None:
    """Runs causal A/B and A/A controls with fresh processes."""
    if blocks != 12:
        raise ValueError("the retained experiment requires exactly 12 blocks")
    fields = (
        "comparison",
        "outcome",
        "block",
        "order",
        "position",
        "label",
        "variant",
        "eager",
        "elapsed_ns",
        "checksum",
        "status",
        "error",
    )
    raw_path = output_dir / "raw.csv"
    summaries: list[dict[str, object]] = []
    templates = (("A", "B", "B", "A"), ("B", "A", "A", "B"))

    with raw_path.open("w", newline="", encoding="utf-8") as raw:
        writer = csv.DictWriter(raw, fieldnames=fields)
        writer.writeheader()
        for outcome in ("startup", "first_use", "steady"):
            for control in (False, True):
                comparison = f"{outcome}_{'aa' if control else 'eager_over_lazy'}"
                contrasts: list[float] = []
                expected_checksums: set[int] = set()
                for block in range(blocks):
                    order = templates[block % 2]
                    samples: dict[str, list[int]] = {"A": [], "B": []}
                    complete = True
                    for position, label in enumerate(order):
                        eager = label == "B" and not control
                        variant = "lazy_b" if control and label == "B" else (
                            "same_image_eager" if eager else "lazy"
                        )
                        row: dict[str, object] = {
                            "comparison": comparison,
                            "outcome": outcome,
                            "block": block,
                            "order": "".join(order),
                            "position": position,
                            "label": label,
                            "variant": variant,
                            "eager": int(eager),
                            "elapsed_ns": "",
                            "checksum": "",
                            "status": "ok",
                            "error": "",
                        }
                        try:
                            elapsed, checksum = timed_sample(
                                work_dir / "lazy",
                                outcome=outcome,
                                eager=eager,
                                iterations=iterations,
                            )
                            row["elapsed_ns"] = elapsed
                            row["checksum"] = "" if checksum is None else checksum
                            samples[label].append(elapsed)
                            if checksum is not None:
                                expected_checksums.add(checksum)
                        except Exception as error:  # retain the failed row before aborting
                            complete = False
                            row["status"] = "failed"
                            row["error"] = repr(error)
                        writer.writerow(row)
                        raw.flush()
                        if not complete:
                            break
                    if not complete:
                        raise RuntimeError(f"incomplete block retained for {comparison} block {block}")
                    if len(samples["A"]) != 2 or len(samples["B"]) != 2:
                        raise RuntimeError("balanced block did not retain two samples per label")
                    contrast = (
                        sum(math.log(value) for value in samples["B"])
                        - sum(math.log(value) for value in samples["A"])
                    ) / 2.0
                    contrasts.append(contrast)
                if outcome != "startup" and len(expected_checksums) != 1:
                    raise RuntimeError(f"{comparison} produced inconsistent checksums")
                summary = summarize(contrasts)
                summary.update(
                    {
                        "comparison": comparison,
                        "outcome": outcome,
                        "ratio": "B/A",
                        "numerator": "lazy_b" if control else "same_image_eager",
                        "denominator": "lazy",
                        "processes": blocks * 4,
                        "iterations": iterations if outcome == "steady" else 0,
                    }
                )
                summaries.append(summary)

    (output_dir / "summary.json").write_text(
        json.dumps(summaries, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=summaries[0].keys())
        writer.writeheader()
        writer.writerows(summaries)


def main() -> int:
    """Runs the complete glibc Linux experiment."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=25_000_000)
    args = parser.parse_args()

    if platform.system() != "Linux":
        parser.error("the ELF binding experiment requires Linux")
    if args.iterations <= 0:
        parser.error("--iterations must be positive")
    for tool in ("cc", "getconf", "readelf", "objdump"):
        if shutil.which(tool) is None:
            parser.error(f"required tool is unavailable: {tool}")
    libc = run(["getconf", "GNU_LIBC_VERSION"], cwd=Path.cwd()).strip()
    if not libc.startswith("glibc "):
        parser.error(f"the experiment requires glibc; found {libc!r}")
    if args.work_dir.exists() and any(args.work_dir.iterdir()):
        parser.error("--work-dir must be empty")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error("--output-dir must be empty")
    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "symbols": SYMBOLS,
        "blocks": args.blocks,
        "processes_per_outcome": args.blocks * 4,
        "iterations": args.iterations,
        "ratio": "B/A",
        "causal_a": "lazy ELF with LD_BIND_NOW absent",
        "causal_b": "the same lazy ELF with LD_BIND_NOW=1",
        "aa_a": "lazy ELF with LD_BIND_NOW absent",
        "aa_b": "lazy ELF with LD_BIND_NOW absent",
    }
    (args.output_dir / "experiment.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    build(args.work_dir, args.output_dir)
    inspect(args.work_dir, args.output_dir)
    benchmark(
        args.work_dir,
        args.output_dir,
        blocks=args.blocks,
        iterations=args.iterations,
    )
    print(f"output={args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
