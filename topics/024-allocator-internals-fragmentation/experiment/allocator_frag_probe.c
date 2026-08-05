#define _GNU_SOURCE

#include <errno.h>
#include <inttypes.h>
#include <malloc.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

struct rss_sample {
    long rss_kb;
    long pss_kb;
    long private_dirty_kb;
    long anonymous_kb;
    long anon_huge_kb;
};

static void die(const char *what)
{
    perror(what);
    exit(2);
}

static uint64_t now_ns(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &ts) != 0) {
        die("clock_gettime");
    }
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

static struct rss_sample read_smaps_rollup(void)
{
    FILE *f = fopen("/proc/self/smaps_rollup", "re");
    if (f == NULL) {
        die("fopen smaps_rollup");
    }

    struct rss_sample out = {0};
    /* A missing field must not masquerade as a measured zero. */
    int seen = 0;
    char line[256];
    while (fgets(line, sizeof(line), f) != NULL) {
        if (sscanf(line, "Rss: %ld kB", &out.rss_kb) == 1) {
            seen |= 1 << 0;
        }
        if (sscanf(line, "Pss: %ld kB", &out.pss_kb) == 1) {
            seen |= 1 << 1;
        }
        if (sscanf(line, "Private_Dirty: %ld kB", &out.private_dirty_kb) == 1) {
            seen |= 1 << 2;
        }
        if (sscanf(line, "Anonymous: %ld kB", &out.anonymous_kb) == 1) {
            seen |= 1 << 3;
        }
        if (sscanf(line, "AnonHugePages: %ld kB", &out.anon_huge_kb) == 1) {
            seen |= 1 << 4;
        }
    }
    if (ferror(f)) {
        die("fgets smaps_rollup");
    }
    if (fclose(f) != 0) {
        die("fclose smaps_rollup");
    }
    if (seen != 0x1f) {
        fprintf(stderr, "smaps_rollup lacked a required field: mask=%d\n", seen);
        exit(2);
    }
    return out;
}

static size_t parse_size(const char *s, const char *name)
{
    errno = 0;
    char *end = NULL;
    unsigned long long value = strtoull(s, &end, 10);
    if (errno != 0 || end == s || *end != '\0' || value == 0 || value > SIZE_MAX) {
        fprintf(stderr, "invalid %s: %s\n", name, s);
        exit(2);
    }
    return (size_t)value;
}

enum pattern_kind { PATTERN_COMPACT, PATTERN_SCATTERED };

/* The survivor decision runs inside the timed free loop; it must not do
 * treatment-dependent string work there. */
static int is_survivor(enum pattern_kind pattern, size_t index,
                       size_t survivor_count, size_t group)
{
    if (pattern == PATTERN_COMPACT) {
        return index < survivor_count;
    }
    return index % group == 0;
}

int main(int argc, char **argv)
{
    if (argc != 7) {
        fprintf(stderr,
                "usage: %s PATTERN LABEL BLOCK PERIOD COUNT BLOCK_SIZE\n",
                argv[0]);
        return 2;
    }

    const char *pattern = argv[1];
    const char *label = argv[2];
    enum pattern_kind pattern_kind;
    if (strcmp(pattern, "compact") == 0) {
        pattern_kind = PATTERN_COMPACT;
    } else if (strcmp(pattern, "scattered") == 0) {
        pattern_kind = PATTERN_SCATTERED;
    } else {
        fprintf(stderr, "pattern must be compact or scattered\n");
        return 2;
    }
    size_t block_id = parse_size(argv[3], "block");
    size_t period = parse_size(argv[4], "period");
    size_t count = parse_size(argv[5], "count");
    size_t block_size = parse_size(argv[6], "block size");
    const size_t group = 16;
    if (count % group != 0 || block_size < 2 || count > SIZE_MAX / sizeof(void *)) {
        fprintf(stderr, "count must be divisible by 16 and sizes must not overflow\n");
        return 2;
    }
    const size_t survivor_count = count / group;

    int arena_control = mallopt(M_ARENA_MAX, 1);
    int mmap_control = mallopt(M_MMAP_MAX, 0);
    int trim_control = mallopt(M_TRIM_THRESHOLD, -1);
    if (arena_control == 0 || mmap_control == 0 || trim_control == 0) {
        fprintf(stderr,
                "mallopt rejected controls: arena=%d mmap=%d trim=%d\n",
                arena_control, mmap_control, trim_control);
        return 2;
    }

    /* The pointer table lives outside the measured arena: an in-arena table
     * would sit inside every RSS, arena, and uordblks sample as a constant
     * additive term in both arms, diluting the ratio estimand toward one. */
    void **ptrs = mmap(NULL, count * sizeof(*ptrs), PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (ptrs == MAP_FAILED) {
        die("mmap pointer table");
    }

    struct rss_sample start = read_smaps_rollup();
    uint64_t t0 = now_ns();
    for (size_t i = 0; i < count; ++i) {
        unsigned char *p = malloc(block_size);
        if (p == NULL) {
            die("malloc block");
        }
        memset(p, (int)((i * 131U + 17U) & 0xffU), block_size);
        ptrs[i] = p;
    }
    uint64_t t1 = now_ns();
    struct rss_sample full = read_smaps_rollup();
    struct mallinfo2 mi_full = mallinfo2();

    uint64_t free_start = now_ns();
    for (size_t i = 0; i < count; ++i) {
        if (!is_survivor(pattern_kind, i, survivor_count, group)) {
            free(ptrs[i]);
            ptrs[i] = NULL;
        }
    }
    uint64_t free_end = now_ns();
    struct rss_sample freed = read_smaps_rollup();
    struct mallinfo2 mi_freed = mallinfo2();

    uint64_t trim_start = now_ns();
    int trim_result = malloc_trim(0);
    uint64_t trim_end = now_ns();
    struct rss_sample trimmed = read_smaps_rollup();
    struct mallinfo2 mi_trimmed = mallinfo2();

    uint64_t checksum = 0;
    uint64_t expected_checksum = 0;
    size_t seen = 0;
    size_t live_usable = 0;
    for (size_t i = 0; i < count; ++i) {
        if (ptrs[i] != NULL) {
            unsigned char expected = (unsigned char)((i * 131U + 17U) & 0xffU);
            unsigned char *p = ptrs[i];
            /* Sum every byte; the expected value comes from the fill formula
             * alone, so interior corruption cannot cancel out. */
            uint64_t block_sum = 0;
            for (size_t j = 0; j < block_size; ++j) {
                block_sum += (uint64_t)p[j];
            }
            checksum += block_sum;
            expected_checksum += (uint64_t)expected * (uint64_t)block_size;
            live_usable += malloc_usable_size(p);
            ++seen;
        }
    }
    if (seen != survivor_count) {
        fprintf(stderr, "survivor count mismatch: got %zu expected %zu\n", seen,
                survivor_count);
        return 3;
    }
    if (checksum != expected_checksum) {
        fprintf(stderr, "checksum mismatch: got %" PRIu64 " expected %" PRIu64 "\n",
                checksum, expected_checksum);
        return 3;
    }

    printf("{\"pattern\":\"%s\",\"label\":\"%s\",\"block\":%zu,"
           "\"period\":%zu,\"pid\":%ld,\"count\":%zu,"
           "\"block_size\":%zu,\"survivors\":%zu,"
           "\"live_requested\":%zu,\"live_usable\":%zu,"
           "\"checksum\":%" PRIu64 ",\"expected_checksum\":%" PRIu64 ","
           "\"trim_result\":%d,"
           "\"alloc_ns\":%" PRIu64 ",\"free_ns\":%" PRIu64 ","
           "\"trim_ns\":%" PRIu64 ","
           "\"rss_start_kb\":%ld,\"rss_full_kb\":%ld,"
           "\"rss_freed_kb\":%ld,\"rss_trimmed_kb\":%ld,"
           "\"pss_trimmed_kb\":%ld,\"anonymous_trimmed_kb\":%ld,"
           "\"private_dirty_trimmed_kb\":%ld,\"anon_huge_trimmed_kb\":%ld,"
           "\"arena_full\":%zu,\"uord_full\":%zu,\"ford_full\":%zu,"
           "\"arena_freed\":%zu,\"uord_freed\":%zu,\"ford_freed\":%zu,"
           "\"arena_trimmed\":%zu,\"uord_trimmed\":%zu,"
           "\"ford_trimmed\":%zu,\"keepcost_trimmed\":%zu}\n",
           pattern, label, block_id, period, (long)getpid(), count, block_size,
           seen, seen * block_size, live_usable, checksum, expected_checksum,
           trim_result, t1 - t0, free_end - free_start,
           trim_end - trim_start, start.rss_kb, full.rss_kb, freed.rss_kb,
           trimmed.rss_kb, trimmed.pss_kb, trimmed.anonymous_kb,
           trimmed.private_dirty_kb, trimmed.anon_huge_kb,
           mi_full.arena, mi_full.uordblks, mi_full.fordblks,
           mi_freed.arena, mi_freed.uordblks, mi_freed.fordblks,
           mi_trimmed.arena, mi_trimmed.uordblks, mi_trimmed.fordblks,
           mi_trimmed.keepcost);

    for (size_t i = 0; i < count; ++i) {
        free(ptrs[i]);
    }
    if (munmap(ptrs, count * sizeof(*ptrs)) != 0) {
        die("munmap pointer table");
    }
    return 0;
}
