#define _GNU_SOURCE

#include <errno.h>
#include <inttypes.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

typedef struct {
    uint64_t value;
    unsigned char padding[56];
} cache_line;

_Static_assert(sizeof(cache_line) == 64, "cache_line must occupy 64 bytes");

#if defined(__GNUC__)
#define NOINLINE __attribute__((noinline, noclone))
#else
#define NOINLINE
#endif

static uint64_t splitmix64(uint64_t *state) {
    uint64_t z = (*state += UINT64_C(0x9e3779b97f4a7c15));
    z = (z ^ (z >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    z = (z ^ (z >> 27)) * UINT64_C(0x94d049bb133111eb);
    return z ^ (z >> 31);
}

static double elapsed_seconds(struct timespec start, struct timespec end) {
    return (double)(end.tv_sec - start.tv_sec) +
           (double)(end.tv_nsec - start.tv_nsec) / 1.0e9;
}

NOINLINE uint64_t kernel_demand(const cache_line *restrict lines,
                                const uint32_t *restrict order,
                                size_t count,
                                size_t passes) {
    uint64_t sum = 0;
    for (size_t pass = 0; pass < passes; ++pass) {
        for (size_t i = 0; i < count; ++i) {
            sum += lines[order[i]].value;
        }
    }
    __asm__ volatile("" : "+r"(sum) : : "memory");
    return sum;
}

NOINLINE uint64_t kernel_prefetch(const cache_line *restrict lines,
                                  const uint32_t *restrict order,
                                  size_t count,
                                  size_t passes,
                                  size_t distance) {
    uint64_t sum = 0;
    const size_t main_count = distance < count ? count - distance : 0;

    for (size_t pass = 0; pass < passes; ++pass) {
        size_t i = 0;
        for (; i < main_count; ++i) {
            __builtin_prefetch(&lines[order[i + distance]], 0, 0);
            sum += lines[order[i]].value;
        }
        for (; i < count; ++i) {
            sum += lines[order[i]].value;
        }
    }
    __asm__ volatile("" : "+r"(sum) : : "memory");
    return sum;
}

static void usage(const char *program) {
    fprintf(stderr,
            "usage: %s --mode demand|prefetch --pattern random|sequential "
            "[--distance N] [--mib N] [--passes N] [--warmup-passes N] "
            "[--seed N]\n",
            program);
}

static int parse_size(const char *text, size_t *out) {
    char *end = NULL;
    /* strtoull accepts leading whitespace and a sign and wraps negatives
     * modulo 2^64, so "-1" would otherwise pass as SIZE_MAX; require the
     * argument to start with a digit. */
    if (text[0] < '0' || text[0] > '9') {
        return -1;
    }
    errno = 0;
    unsigned long long value = strtoull(text, &end, 0);
    if (errno != 0 || end == text || *end != '\0' || value > SIZE_MAX) {
        return -1;
    }
    *out = (size_t)value;
    return 0;
}

static int parse_u64(const char *text, uint64_t *out) {
    char *end = NULL;
    if (text[0] < '0' || text[0] > '9') {
        return -1;
    }
    errno = 0;
    unsigned long long value = strtoull(text, &end, 0);
    if (errno != 0 || end == text || *end != '\0') {
        return -1;
    }
    *out = (uint64_t)value;
    return 0;
}

int main(int argc, char **argv) {
    const char *mode = NULL;
    const char *pattern = NULL;
    size_t distance = 16;
    size_t mib = 512;
    size_t passes = 3;
    size_t warmup_passes = 1;
    uint64_t seed = UINT64_C(0x4800480048004800);

    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--mode") == 0 && i + 1 < argc) {
            mode = argv[++i];
        } else if (strcmp(argv[i], "--pattern") == 0 && i + 1 < argc) {
            pattern = argv[++i];
        } else if (strcmp(argv[i], "--distance") == 0 && i + 1 < argc) {
            if (parse_size(argv[++i], &distance) != 0) {
                usage(argv[0]);
                return 2;
            }
        } else if (strcmp(argv[i], "--mib") == 0 && i + 1 < argc) {
            if (parse_size(argv[++i], &mib) != 0) {
                usage(argv[0]);
                return 2;
            }
        } else if (strcmp(argv[i], "--passes") == 0 && i + 1 < argc) {
            if (parse_size(argv[++i], &passes) != 0) {
                usage(argv[0]);
                return 2;
            }
        } else if (strcmp(argv[i], "--warmup-passes") == 0 && i + 1 < argc) {
            if (parse_size(argv[++i], &warmup_passes) != 0) {
                usage(argv[0]);
                return 2;
            }
        } else if (strcmp(argv[i], "--seed") == 0 && i + 1 < argc) {
            if (parse_u64(argv[++i], &seed) != 0) {
                usage(argv[0]);
                return 2;
            }
        } else {
            usage(argv[0]);
            return 2;
        }
    }

    const int is_demand = mode != NULL && strcmp(mode, "demand") == 0;
    const int is_prefetch = mode != NULL && strcmp(mode, "prefetch") == 0;
    const int is_random = pattern != NULL && strcmp(pattern, "random") == 0;
    const int is_sequential = pattern != NULL && strcmp(pattern, "sequential") == 0;
    if ((!is_demand && !is_prefetch) || (!is_random && !is_sequential) ||
        mib == 0 || passes == 0 || (is_prefetch && distance == 0)) {
        usage(argv[0]);
        return 2;
    }

    if (mib > SIZE_MAX / (1024U * 1024U)) {
        fprintf(stderr, "mib value is too large\n");
        return 2;
    }
    const size_t data_bytes = mib * 1024U * 1024U;
    const size_t count = data_bytes / sizeof(cache_line);
    if (count == 0 || count > UINT32_MAX) {
        fprintf(stderr, "line count must be in [1, UINT32_MAX]\n");
        return 2;
    }

    struct timespec process_start;
    struct timespec init_end;
    struct timespec warmup_start;
    struct timespec warmup_end;
    struct timespec timed_start;
    struct timespec timed_end;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &process_start) != 0) {
        perror("clock_gettime");
        return 1;
    }

    const long page_size_raw = sysconf(_SC_PAGESIZE);
    const size_t alignment = page_size_raw > 0 ? (size_t)page_size_raw : 4096U;
    cache_line *lines = NULL;
    uint32_t *order = NULL;
    if (posix_memalign((void **)&lines, alignment, count * sizeof(*lines)) != 0 ||
        posix_memalign((void **)&order, alignment, count * sizeof(*order)) != 0) {
        fprintf(stderr, "allocation failed for %zu MiB workload\n", mib);
        free(lines);
        free(order);
        return 1;
    }

    errno = 0;
    const int nohuge_data_rc = madvise(lines, count * sizeof(*lines), MADV_NOHUGEPAGE);
    const int nohuge_data_errno = nohuge_data_rc == 0 ? 0 : errno;
    errno = 0;
    const int nohuge_order_rc = madvise(order, count * sizeof(*order), MADV_NOHUGEPAGE);
    const int nohuge_order_errno = nohuge_order_rc == 0 ? 0 : errno;

    uint64_t expected_one_pass = 0;
    for (size_t i = 0; i < count; ++i) {
        uint64_t state = seed ^ (uint64_t)i;
        lines[i].value = splitmix64(&state);
        expected_one_pass += lines[i].value;
        order[i] = (uint32_t)i;
    }

    if (is_random) {
        uint64_t shuffle_state = seed ^ UINT64_C(0xd1b54a32d192ed03);
        for (size_t i = count - 1; i > 0; --i) {
            const size_t j = (size_t)(splitmix64(&shuffle_state) % (i + 1));
            const uint32_t tmp = order[i];
            order[i] = order[j];
            order[j] = tmp;
        }
    }

    if (clock_gettime(CLOCK_MONOTONIC_RAW, &init_end) != 0) {
        perror("clock_gettime");
        return 1;
    }

    if (clock_gettime(CLOCK_MONOTONIC_RAW, &warmup_start) != 0) {
        perror("clock_gettime");
        return 1;
    }
    const uint64_t warmup_checksum =
        kernel_demand(lines, order, count, warmup_passes);
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &warmup_end) != 0) {
        perror("clock_gettime");
        return 1;
    }
    const uint64_t expected_warmup = expected_one_pass * (uint64_t)warmup_passes;
    if (warmup_checksum != expected_warmup) {
        fprintf(stderr, "warmup checksum mismatch\n");
        return 3;
    }

    /* Warm the sched_getcpu path before minor-fault accounting begins. */
    (void)sched_getcpu();
    struct rusage usage_before;
    struct rusage usage_after;
    if (getrusage(RUSAGE_SELF, &usage_before) != 0 ||
        clock_gettime(CLOCK_MONOTONIC_RAW, &timed_start) != 0) {
        perror("measurement setup");
        return 1;
    }
    const int cpu_start = sched_getcpu();
    const uint64_t checksum = is_demand
                                  ? kernel_demand(lines, order, count, passes)
                                  : kernel_prefetch(lines, order, count, passes, distance);
    const int cpu_end = sched_getcpu();
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &timed_end) != 0 ||
        getrusage(RUSAGE_SELF, &usage_after) != 0) {
        perror("measurement finish");
        return 1;
    }

    const uint64_t expected = expected_one_pass * (uint64_t)passes;
    const int correct = checksum == expected;
    const double init_s = elapsed_seconds(process_start, init_end);
    const double warmup_s = elapsed_seconds(warmup_start, warmup_end);
    const double timed_s = elapsed_seconds(timed_start, timed_end);
    const uint64_t accesses = (uint64_t)count * (uint64_t)passes;
    const double ns_per_access = timed_s * 1.0e9 / (double)accesses;

    printf("{\"schema\":1,\"pid\":%ld,\"mode\":\"%s\",\"pattern\":\"%s\","
           "\"distance\":%zu,\"mib\":%zu,\"passes\":%zu,"
           "\"warmup_passes\":%zu,\"lines\":%zu,\"accesses\":%" PRIu64 ","
           "\"seed\":\"0x%016" PRIx64 "\",\"init_seconds\":%.9f,"
           "\"warmup_seconds\":%.9f,\"elapsed_seconds\":%.9f,"
           "\"ns_per_access\":%.9f,\"checksum\":\"0x%016" PRIx64 "\","
           "\"expected\":\"0x%016" PRIx64 "\",\"correct\":%s,"
           "\"timed_minor_faults\":%ld,\"timed_major_faults\":%ld,"
           "\"cpu_start\":%d,\"cpu_end\":%d,"
           "\"madv_nohuge_data_rc\":%d,\"madv_nohuge_data_errno\":%d,"
           "\"madv_nohuge_order_rc\":%d,\"madv_nohuge_order_errno\":%d}\n",
           (long)getpid(), mode, pattern, is_prefetch ? distance : 0, mib, passes, warmup_passes,
           count, accesses, seed, init_s, warmup_s, timed_s, ns_per_access,
           checksum, expected, correct ? "true" : "false",
           usage_after.ru_minflt - usage_before.ru_minflt,
           usage_after.ru_majflt - usage_before.ru_majflt, cpu_start, cpu_end,
           nohuge_data_rc, nohuge_data_errno, nohuge_order_rc,
           nohuge_order_errno);

    free(order);
    free(lines);
    return correct ? 0 : 3;
}
