#define _GNU_SOURCE
#include <assert.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

static uint64_t now(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &t)) { perror("clock"); exit(1); }
    return (uint64_t)t.tv_sec * 1000000000 + (uint64_t)t.tv_nsec;
}
static uint64_t random64(uint64_t *s) {
    *s ^= *s << 13; *s ^= *s >> 7; *s ^= *s << 17;
    return *s;
}
static volatile uint64_t *slot(char *p, size_t i, size_t page) {
    /* Spread offsets across cache sets while retaining one line per page. */
    return (volatile uint64_t *)(p + i * page + (i % (page / 64)) * 64);
}
static long huge_kb(char *p, size_t len) {
    FILE *f = fopen("/proc/self/smaps", "r");
    if (!f) { perror("smaps"); exit(1); }
    char line[512]; unsigned long lo, hi; int inside = 0; long total = 0, kb;
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, "%lx-%lx", &lo, &hi) == 2) {
            inside = lo >= (uintptr_t)p && hi <= (uintptr_t)p + len;
        } else if (inside && sscanf(line, "AnonHugePages: %ld kB", &kb) == 1) {
            total += kb;
        }
    }
    fclose(f); return total;
}
int main(int argc, char **argv) {
    if (argc != 3 || (strcmp(argv[1], "base") && strcmp(argv[1], "huge")) ||
        (strcmp(argv[2], "2") && strcmp(argv[2], "64"))) {
        fprintf(stderr, "usage: probe base|huge 2|64\n"); return 2;
    }
    size_t page = (size_t)sysconf(_SC_PAGESIZE);
    /* This controlled campaign requires the verified 4 KiB base-page geometry. */
    if (page != 4096) { fprintf(stderr, "requires 4096-byte base pages\n"); return 2; }
    size_t align = 2 * 1024 * 1024, bytes = (size_t)atoi(argv[2]) * 1024 * 1024;
    char *raw = mmap(NULL, bytes + 2 * align, PROT_READ | PROT_WRITE,
                     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (raw == MAP_FAILED) { perror("mmap"); return 1; }
    /* Keep a PROT_NONE guard on each side to isolate the measured smaps region. */
    char *p = (char *)(((uintptr_t)raw + align) & ~(uintptr_t)(align - 1));
    size_t prefix = (size_t)(p - raw), suffix = bytes + 2 * align - prefix - bytes;
    if (mprotect(raw, prefix, PROT_NONE) || mprotect(p + bytes, suffix, PROT_NONE)) {
        perror("mprotect"); return 1;
    }
    int advice = !strcmp(argv[1], "huge") ? MADV_HUGEPAGE : MADV_NOHUGEPAGE;
    if (madvise(p, bytes, advice)) { perror("madvise"); return 1; }
    size_t n = bytes / page;
    size_t *order = malloc(n * sizeof *order);
    if (!order) { perror("malloc"); return 1; }
    for (size_t i = 0; i < n; ++i) order[i] = i;
    uint64_t seed = 96;
    for (size_t i = n - 1; i; --i) {
        size_t j = random64(&seed) % (i + 1), tmp = order[i];
        order[i] = order[j]; order[j] = tmp;
    }
    struct rusage before, after;
    if (getrusage(RUSAGE_SELF, &before)) { perror("getrusage"); return 1; }
    uint64_t start = now();
    for (size_t i = 0; i < n; ++i) *slot(p, order[i], page) = order[(i + 1) % n];
    uint64_t touch = now() - start;
    if (getrusage(RUSAGE_SELF, &after)) { perror("getrusage"); return 1; }
    size_t index = order[0];
    for (size_t i = 0; i < n; ++i) {
        assert(index == order[i]);
        index = (size_t)*slot(p, index, page);
    }
    assert(index == order[0]);
    long huge_before = huge_kb(p, bytes);
    uint64_t sum = 0; const size_t rounds = 128;
    start = now();
    for (size_t i = 0; i < n * rounds; ++i) {
        index = (size_t)*slot(p, index, page); sum += index;
    }
    uint64_t elapsed = now() - start;
    assert(index == order[0]);
    assert(sum == (uint64_t)n * (n - 1) / 2 * rounds);
    long huge_after = huge_kb(p, bytes);
    printf("{\"mode\":\"%s\",\"mib\":%s,\"page\":%zu,\"touch_ns\":%" PRIu64
           ",\"minor_faults\":%ld,\"huge_kb_before\":%ld,\"huge_kb_after\":%ld,"
           "\"ns_per_load\":%.6f,\"checksum\":%" PRIu64 "}\n",
           argv[1], argv[2], page, touch, after.ru_minflt - before.ru_minflt,
           huge_before, huge_after, (double)elapsed / (n * rounds), sum);
    free(order);
    if (munmap(raw, bytes + 2 * align)) { perror("munmap"); return 1; }
    return 0;
}
