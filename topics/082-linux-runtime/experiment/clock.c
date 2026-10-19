// Linux clock paths. Compile with cc -O3 -std=c11 -Wall -Wextra -Werror.
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

typedef int (*reader)(clockid_t, struct timespec *);
static int forced(clockid_t id, struct timespec *out) {
    return (int)syscall(SYS_clock_gettime, id, out);
}
static uint64_t ns(struct timespec t) {
    assert(t.tv_sec >= 0 && t.tv_nsec >= 0 && t.tv_nsec < 1000000000);
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static uint64_t get(reader read_clock, clockid_t id) {
    struct timespec out;
    if (read_clock(id, &out) != 0) { perror("clock_gettime"); exit(1); }
    return ns(out);
}
int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "check") == 0) {
        clockid_t ids[] = {CLOCK_MONOTONIC, CLOCK_PROCESS_CPUTIME_ID};
        for (int k = 0; k < 2; ++k) {
            for (int i = 0; i < 1000; ++i) {
                uint64_t before = get(forced, ids[k]);
                uint64_t middle = get(clock_gettime, ids[k]);
                uint64_t after = get(forced, ids[k]);
                assert(before <= middle && middle <= after);
            }
        }
        puts("PASS: 2000 syscall/libc/syscall clock brackets");
        return 0;
    }
    if (argc != 4 || (strcmp(argv[1], "libc") && strcmp(argv[1], "syscall")) ||
        (strcmp(argv[2], "monotonic") && strcmp(argv[2], "cpu"))) {
        fprintf(stderr, "usage: clock check | clock libc|syscall monotonic|cpu N\n");
        return 2;
    }
    errno = 0;
    char *end;
    uint64_t n = strtoull(argv[3], &end, 10);
    if (errno || *end || n == 0 || n > 1000000000) return 2;
    reader read_clock = strcmp(argv[1], "libc") == 0 ? clock_gettime : forced;
    clockid_t id = strcmp(argv[2], "cpu") == 0 ? CLOCK_PROCESS_CPUTIME_ID : CLOCK_MONOTONIC;
    uint64_t sum = 0;
    uint64_t start = get(clock_gettime, CLOCK_MONOTONIC_RAW);
    for (uint64_t i = 0; i < n; ++i) sum ^= get(read_clock, id);
    uint64_t elapsed = get(clock_gettime, CLOCK_MONOTONIC_RAW) - start;
    printf("{\"mode\":\"%s\",\"clock\":\"%s\",\"n\":%" PRIu64
           ",\"ns_per_call\":%.6f,\"checksum\":%" PRIu64 "}\n",
           argv[1], argv[2], n, (double)elapsed / (double)n, sum);
    return 0;
}
