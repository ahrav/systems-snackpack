#!/usr/bin/env python3
"""Generate identical C leaves with build-selected function alignment."""

from pathlib import Path
import sys

NFUN = 512


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} OUTPUT_C")

    destination = Path(sys.argv[1])
    destination.parent.mkdir(parents=True, exist_ok=True)
    output = [
        r'''#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#ifndef FUNC_ALIGN
#error "compile with -DFUNC_ALIGN=<power-of-two>"
#endif

#define ATTR __attribute__((noinline, noclone, noipa, used, externally_visible, aligned(FUNC_ALIGN)))
#define VARIANT "layout"

typedef uint64_t (*leaf_fn)(uint64_t);
'''
    ]

    for index in range(NFUN):
        output.append(
            f"ATTR uint64_t leaf_{index}(uint64_t x) "
            '{ __asm__ volatile("" : "+r"(x)); return x + UINT64_C(1); }\n'
        )

    output.append("\nstatic leaf_fn const leaves[] = {\n")
    for index in range(NFUN):
        output.append(f"    leaf_{index},\n")
    output.append("};\n\n")

    output.append(
        rf'''
enum {{ NFUN = {NFUN} }};

static uint64_t parse_u64(const char *text, const char *what) {{
    char *end = NULL;
    errno = 0;
    unsigned long long value = strtoull(text, &end, 10);
    if (errno || !end || *end != '\0') {{
        fprintf(stderr, "invalid %s: %s\n", what, text);
        exit(2);
    }}
    return (uint64_t)value;
}}

static uint64_t elapsed_ns(struct timespec start, struct timespec end) {{
    return (uint64_t)(end.tv_sec - start.tv_sec) * UINT64_C(1000000000)
         + (uint64_t)(end.tv_nsec - start.tv_nsec);
}}

__attribute__((noinline, noclone, noipa))
static uint64_t run_rounds(uint64_t x, uint64_t rounds) {{
    for (uint64_t round = 0; round < rounds; ++round) {{
        for (size_t index = 0; index < NFUN; ++index) {{
            x = leaves[index](x);
        }}
    }}
    return x;
}}

int main(int argc, char **argv) {{
    if (argc != 3) {{
        fprintf(stderr, "usage: %s WARM_ROUNDS MEASURE_ROUNDS\n", argv[0]);
        return 2;
    }}

    const uint64_t warm_rounds = parse_u64(argv[1], "warm rounds");
    const uint64_t measure_rounds = parse_u64(argv[2], "measure rounds");
    const uint64_t seed = UINT64_C(0x123456789abcdef0);

    const uint64_t warmed = run_rounds(seed, warm_rounds);
    struct timespec start;
    struct timespec end;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &start) != 0) {{
        perror("clock_gettime start");
        return 2;
    }}
    const uint64_t checksum = run_rounds(warmed, measure_rounds);
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &end) != 0) {{
        perror("clock_gettime end");
        return 2;
    }}

    const uint64_t expected =
        seed + (warm_rounds + measure_rounds) * (uint64_t)NFUN;
    const uint64_t elapsed = elapsed_ns(start, end);
    const uint64_t calls = measure_rounds * (uint64_t)NFUN;
    const int ok = checksum == expected;

    printf(
        "variant=%s align=%d nfun=%d pid=%ld warm_rounds=%" PRIu64
        " measure_rounds=%" PRIu64 " calls=%" PRIu64
        " elapsed_ns=%" PRIu64 " ns_per_call=%.9f"
        " checksum=%016" PRIx64 " expected=%016" PRIx64 " ok=%d\n",
        VARIANT, FUNC_ALIGN, NFUN, (long)getpid(), warm_rounds,
        measure_rounds, calls, elapsed, (double)elapsed / (double)calls,
        checksum, expected, ok);
    return ok ? 0 : 1;
}}
'''
    )

    destination.write_text("".join(output), encoding="utf-8")


if __name__ == "__main__":
    main()
