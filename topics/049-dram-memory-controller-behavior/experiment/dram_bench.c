#define _GNU_SOURCE

#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <linux/mempolicy.h>
#include <pthread.h>
#include <sched.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

/*
 * One invocation is one fresh-process period.  External orchestration assigns
 * idle/loaded order across processes; this program keeps the within-period
 * setup and measurement boundary identical between those treatments.
 */

enum {
    CACHE_LINE_BYTES = 64,
    SMALL_BYTES = 8 * 1024,
    WORKER_CHUNK_BYTES = 256 * 1024,
    DEFAULT_LARGE_MIB = 512,
    DEFAULT_WORKER_MIB = 128,
    DEFAULT_WARMUP_MS = 750,
};

static const uint64_t SMALL_TARGET_LOADS = UINT64_C(1) << 20;

#if defined(__GNUC__) && !defined(__clang__)
#define GCC_NOIPA __attribute__((noipa))
#else
#define GCC_NOIPA
#endif

/*
 * Keep the measured kernels as distinct, directly called symbols.  GCC's
 * noipa attribute disables interprocedural cloning, folding, and call-edge
 * rewriting in addition to the explicit noinline/used requirements.
 */
#define EXPORTED_NOINLINE                                                   \
    __attribute__((noinline, visibility("default"), used)) GCC_NOIPA

typedef struct __attribute__((aligned(CACHE_LINE_BYTES))) {
    uint64_t next;
    uint64_t value;
    uint8_t padding[CACHE_LINE_BYTES - 2 * sizeof(uint64_t)];
} topic49_node;

_Static_assert(sizeof(topic49_node) == CACHE_LINE_BYTES,
               "one dependent node must occupy exactly one cache line");
_Static_assert(_Alignof(topic49_node) == CACHE_LINE_BYTES,
               "dependent nodes must be cache-line aligned");

enum treatment {
    TREATMENT_UNSET = 0,
    TREATMENT_IDLE,
    TREATMENT_LOADED,
};

enum phase {
    PHASE_INIT = 0,
    PHASE_WARMUP,
    PHASE_ARM,
    PHASE_RUN,
    PHASE_STOP,
};

struct config {
    enum treatment treatment;
    int probe_cpu;
    int *worker_cpus;
    size_t worker_count;
    int numa_node;
    uint64_t large_mib;
    uint64_t worker_mib;
    uint64_t warmup_ms;
};

struct cycle {
    topic49_node *nodes;
    size_t bytes;
    uint64_t node_count;
    uint64_t start;
    uint64_t checksum_per_cycle;
    bool nohugepage;
};

struct map_evidence {
    bool found;
    uint64_t kernel_page_kib;
    uint64_t mmu_page_kib;
    uint64_t anon_huge_kib;
    int thpeligible;
    bool vmflag_nh;
};

struct shared_state {
    pthread_mutex_t mutex;
    pthread_cond_t cond;
    _Atomic int phase;
    _Atomic bool stop;
    size_t ready_count;
    size_t armed_count;
    size_t run_ack_count;
    size_t run_error_count;
    size_t worker_count;
    enum treatment treatment;
};

struct worker_state {
    struct shared_state *shared;
    int requested_cpu;
    int numa_node;
    int start_cpu;
    int end_cpu;
    bool affinity_ok;
    bool nohugepage;
    int error_code;
    int error_number;
    void *buffer;
    size_t buffer_bytes;
    uint64_t *expected_chunk_checksums;
    size_t chunk_count;
    uint64_t completed_chunks;
    bool run_acknowledged;
    bool run_failure_reported;
    uint64_t checksum;
    struct map_evidence mapping;
};

static void usage(const char *program) {
    fprintf(stderr,
            "usage: %s --treatment idle|loaded --probe-cpu N "
            "--worker-cpus N[,N...] --numa-node N [--large-mib N] "
            "[--worker-mib N] "
            "[--warmup-ms N]\n",
            program);
}

static void failf(const char *format, ...) {
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);
    fputc('\n', stderr);
    exit(2);
}

static uint64_t now_ns(void) {
    struct timespec timestamp;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &timestamp) != 0) {
        failf("clock_gettime(CLOCK_MONOTONIC_RAW): %s", strerror(errno));
    }
    return (uint64_t)timestamp.tv_sec * UINT64_C(1000000000) +
           (uint64_t)timestamp.tv_nsec;
}

static void read_usage(int who, const char *scope, struct rusage *result) {
    if (getrusage(who, result) != 0) {
        failf("getrusage(%s): %s", scope, strerror(errno));
    }
}

static uint64_t parse_u64(const char *text, const char *name) {
    char *end = NULL;
    errno = 0;
    unsigned long long value = strtoull(text, &end, 10);
    if (text[0] < '0' || text[0] > '9' || errno != 0 || end == text ||
        *end != '\0') {
        failf("invalid %s: %s", name, text);
    }
    return (uint64_t)value;
}

static int parse_cpu(const char *text, const char *name) {
    uint64_t value = parse_u64(text, name);
    if (value >= CPU_SETSIZE || value > INT_MAX) {
        failf("%s is outside the supported CPU set: %s", name, text);
    }
    return (int)value;
}

static int parse_numa_node(const char *text) {
    uint64_t value = parse_u64(text, "NUMA node");
    if (value > INT_MAX) {
        failf("NUMA node is too large: %s", text);
    }
    return (int)value;
}

static void parse_worker_cpus(struct config *config, const char *text) {
    char *copy = strdup(text);
    if (copy == NULL) {
        failf("strdup worker CPU list: %s", strerror(errno));
    }

    size_t capacity = 4;
    int *cpus = malloc(capacity * sizeof(*cpus));
    if (cpus == NULL) {
        free(copy);
        failf("malloc worker CPU list: %s", strerror(errno));
    }

    size_t count = 0;
    char *save = NULL;
    for (char *token = strtok_r(copy, ",", &save); token != NULL;
         token = strtok_r(NULL, ",", &save)) {
        if (*token == '\0') {
            free(cpus);
            free(copy);
            failf("worker CPU list contains an empty element: %s", text);
        }
        int cpu = parse_cpu(token, "worker CPU");
        for (size_t i = 0; i < count; ++i) {
            if (cpus[i] == cpu) {
                free(cpus);
                free(copy);
                failf("worker CPU list contains duplicate CPU %d", cpu);
            }
        }
        if (count == capacity) {
            if (capacity > SIZE_MAX / (2 * sizeof(*cpus))) {
                free(cpus);
                free(copy);
                failf("worker CPU list is too large");
            }
            capacity *= 2;
            int *larger = realloc(cpus, capacity * sizeof(*cpus));
            if (larger == NULL) {
                free(cpus);
                free(copy);
                failf("realloc worker CPU list: %s", strerror(errno));
            }
            cpus = larger;
        }
        cpus[count++] = cpu;
    }
    free(copy);

    if (count == 0) {
        free(cpus);
        failf("worker CPU list must contain at least one CPU");
    }
    config->worker_cpus = cpus;
    config->worker_count = count;
}

static struct config parse_args(int argc, char **argv) {
    struct config config = {
        .treatment = TREATMENT_UNSET,
        .probe_cpu = -1,
        .worker_cpus = NULL,
        .worker_count = 0,
        .numa_node = -1,
        .large_mib = DEFAULT_LARGE_MIB,
        .worker_mib = DEFAULT_WORKER_MIB,
        .warmup_ms = DEFAULT_WARMUP_MS,
    };

    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--help") == 0) {
            usage(argv[0]);
            exit(0);
        }
        if (i + 1 >= argc) {
            usage(argv[0]);
            failf("missing value for %s", argv[i]);
        }
        const char *value = argv[++i];
        if (strcmp(argv[i - 1], "--treatment") == 0) {
            if (strcmp(value, "idle") == 0) {
                config.treatment = TREATMENT_IDLE;
            } else if (strcmp(value, "loaded") == 0) {
                config.treatment = TREATMENT_LOADED;
            } else {
                failf("unknown treatment: %s", value);
            }
        } else if (strcmp(argv[i - 1], "--probe-cpu") == 0) {
            config.probe_cpu = parse_cpu(value, "probe CPU");
        } else if (strcmp(argv[i - 1], "--worker-cpus") == 0) {
            if (config.worker_cpus != NULL) {
                failf("--worker-cpus may be specified only once");
            }
            parse_worker_cpus(&config, value);
        } else if (strcmp(argv[i - 1], "--numa-node") == 0) {
            config.numa_node = parse_numa_node(value);
        } else if (strcmp(argv[i - 1], "--large-mib") == 0) {
            config.large_mib = parse_u64(value, "large MiB");
        } else if (strcmp(argv[i - 1], "--worker-mib") == 0) {
            config.worker_mib = parse_u64(value, "worker MiB");
        } else if (strcmp(argv[i - 1], "--warmup-ms") == 0) {
            config.warmup_ms = parse_u64(value, "warmup milliseconds");
        } else {
            usage(argv[0]);
            failf("unknown option: %s", argv[i - 1]);
        }
    }

    if (config.treatment == TREATMENT_UNSET || config.probe_cpu < 0 ||
        config.worker_cpus == NULL || config.numa_node < 0) {
        usage(argv[0]);
        failf("--treatment, --probe-cpu, --worker-cpus, and --numa-node are required");
    }
    if (config.large_mib == 0 || config.worker_mib == 0) {
        failf("large and worker mappings must be non-empty");
    }
    if (config.large_mib > SIZE_MAX / (UINT64_C(1024) * UINT64_C(1024)) ||
        config.worker_mib > SIZE_MAX / (UINT64_C(1024) * UINT64_C(1024))) {
        failf("mapping size does not fit size_t");
    }
    for (size_t i = 0; i < config.worker_count; ++i) {
        if (config.worker_cpus[i] == config.probe_cpu) {
            failf("probe CPU %d must be distinct from every worker CPU",
                  config.probe_cpu);
        }
    }
    return config;
}

static uint64_t mix64(uint64_t value) {
    value ^= value >> 30;
    value *= UINT64_C(0xbf58476d1ce4e5b9);
    value ^= value >> 27;
    value *= UINT64_C(0x94d049bb133111eb);
    value ^= value >> 31;
    return value;
}

static uint64_t next_random(uint64_t *state) {
    *state += UINT64_C(0x9e3779b97f4a7c15);
    return mix64(*state);
}

static uint64_t uniform_below(uint64_t *state, uint64_t bound) {
    /* Rejection avoids modulo bias in the deterministic Fisher-Yates shuffle. */
    const uint64_t threshold = (uint64_t)(-bound) % bound;
    for (;;) {
        uint64_t candidate = next_random(state);
        if (candidate >= threshold) {
            return candidate % bound;
        }
    }
}

EXPORTED_NOINLINE void topic49_page_prepare(uint64_t *words, size_t word_count,
                                            uint64_t seed) {
    uint64_t state = seed;
    for (size_t i = 0; i < word_count; ++i) {
        words[i] = next_random(&state);
    }
}

EXPORTED_NOINLINE uint64_t
topic49_walk_dependent(const topic49_node *nodes, uint64_t start,
                       uint64_t load_count, uint64_t *final_index) {
    uint64_t index = start;
    uint64_t checksum = 0;
    for (uint64_t i = 0; i < load_count; ++i) {
        const topic49_node *node = &nodes[index];
        checksum += node->value;
        index = node->next;
    }
    *final_index = index;
    return checksum;
}

EXPORTED_NOINLINE uint64_t topic49_stream_scan(const uint64_t *words,
                                               size_t word_count) {
    uint64_t checksum = 0;
    for (size_t i = 0; i < word_count; ++i) {
        checksum += words[i];
    }
    return checksum;
}

EXPORTED_NOINLINE uint64_t
topic49_run_timed(const topic49_node *nodes, uint64_t start,
                  uint64_t load_count, uint64_t *elapsed_ns,
                  uint64_t *final_index) {
    uint64_t begin = now_ns();
    uint64_t checksum =
        topic49_walk_dependent(nodes, start, load_count, final_index);
    uint64_t end = now_ns();
    *elapsed_ns = end - begin;
    return checksum;
}

static void *map_nohuge(size_t bytes, bool *advice_recorded) {
    void *mapping = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                         MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping == MAP_FAILED) {
        return MAP_FAILED;
    }
    if (madvise(mapping, bytes, MADV_NOHUGEPAGE) != 0) {
        int saved = errno;
        (void)munmap(mapping, bytes);
        errno = saved;
        return MAP_FAILED;
    }
    *advice_recorded = true;
    return mapping;
}

static struct cycle make_cycle(size_t bytes, uint64_t seed) {
    if (bytes < CACHE_LINE_BYTES || bytes % CACHE_LINE_BYTES != 0) {
        failf("cycle size %zu is not a non-zero multiple of %d", bytes,
              CACHE_LINE_BYTES);
    }

    struct cycle cycle = {
        .nodes = NULL,
        .bytes = bytes,
        .node_count = bytes / CACHE_LINE_BYTES,
        .start = 0,
        .checksum_per_cycle = 0,
        .nohugepage = false,
    };
    cycle.nodes = map_nohuge(bytes, &cycle.nohugepage);
    if (cycle.nodes == MAP_FAILED) {
        failf("mmap/madvise cycle (%zu bytes): %s", bytes, strerror(errno));
    }

    topic49_page_prepare((uint64_t *)cycle.nodes, bytes / sizeof(uint64_t),
                         seed ^ UINT64_C(0x6a09e667f3bcc909));

    if (cycle.node_count > SIZE_MAX / sizeof(uint64_t)) {
        failf("cycle permutation is too large");
    }
    uint64_t *order = malloc((size_t)cycle.node_count * sizeof(*order));
    if (order == NULL) {
        failf("malloc cycle permutation: %s", strerror(errno));
    }
    for (uint64_t i = 0; i < cycle.node_count; ++i) {
        order[i] = i;
        cycle.checksum_per_cycle += cycle.nodes[i].value;
    }

    uint64_t random_state = seed;
    for (uint64_t i = cycle.node_count - 1; i > 0; --i) {
        uint64_t j = uniform_below(&random_state, i + 1);
        uint64_t temporary = order[i];
        order[i] = order[j];
        order[j] = temporary;
    }
    for (uint64_t i = 0; i < cycle.node_count; ++i) {
        uint64_t current = order[i];
        uint64_t next = order[(i + 1) % cycle.node_count];
        cycle.nodes[current].next = next;
    }
    cycle.start = order[0];
    free(order);

    /* A full untimed traversal both prefaults reads and proves one closed cycle. */
    uint64_t final_index = UINT64_MAX;
    uint64_t checksum = topic49_walk_dependent(
        cycle.nodes, cycle.start, cycle.node_count, &final_index);
    if (final_index != cycle.start || checksum != cycle.checksum_per_cycle) {
        failf("constructed mapping is not one correct dependent cycle");
    }
    return cycle;
}

static bool current_affinity_is_single_cpu(int cpu, int *error_number) {
    cpu_set_t observed;
    CPU_ZERO(&observed);
    int rc =
        pthread_getaffinity_np(pthread_self(), sizeof(observed), &observed);
    if (rc != 0) {
        *error_number = rc;
        return false;
    }
    if (!CPU_ISSET(cpu, &observed) || CPU_COUNT(&observed) != 1) {
        *error_number = EINVAL;
        return false;
    }
    return true;
}

static bool pin_current_thread(int cpu, int *error_number) {
    cpu_set_t requested;
    CPU_ZERO(&requested);
    CPU_SET(cpu, &requested);
    int rc = pthread_setaffinity_np(pthread_self(), sizeof(requested), &requested);
    if (rc != 0) {
        *error_number = rc;
        return false;
    }
    return current_affinity_is_single_cpu(cpu, error_number);
}

static bool bind_current_thread_memory_to_node(int node, int *error_number) {
    const size_t bits_per_word = sizeof(unsigned long) * CHAR_BIT;
    const size_t word_index = (size_t)node / bits_per_word;
    if (word_index == SIZE_MAX ||
        word_index + 1 > SIZE_MAX / sizeof(unsigned long)) {
        *error_number = EOVERFLOW;
        return false;
    }
    const size_t word_count = word_index + 1;
    unsigned long *mask = calloc(word_count, sizeof(*mask));
    if (mask == NULL) {
        *error_number = errno == 0 ? ENOMEM : errno;
        return false;
    }
    mask[word_index] = 1UL << ((size_t)node % bits_per_word);
    const unsigned long maxnode = (unsigned long)(word_count * bits_per_word);
    if (syscall(SYS_set_mempolicy, MPOL_BIND, mask, maxnode) != 0) {
        *error_number = errno;
        free(mask);
        return false;
    }
    free(mask);
    return true;
}

static struct map_evidence read_map_evidence(const void *address) {
    struct map_evidence result = {
        .found = false,
        .kernel_page_kib = 0,
        .mmu_page_kib = 0,
        .anon_huge_kib = 0,
        .thpeligible = -1,
        .vmflag_nh = false,
    };
    FILE *smaps = fopen("/proc/self/smaps", "r");
    if (smaps == NULL) {
        return result;
    }

    uintptr_t target = (uintptr_t)address;
    bool in_target = false;
    char *line = NULL;
    size_t capacity = 0;
    while (getline(&line, &capacity, smaps) >= 0) {
        unsigned long long begin = 0;
        unsigned long long end = 0;
        if (sscanf(line, "%llx-%llx", &begin, &end) == 2) {
            if (in_target) {
                break;
            }
            in_target = target >= (uintptr_t)begin && target < (uintptr_t)end;
            if (in_target) {
                result.found = true;
            }
            continue;
        }
        if (!in_target) {
            continue;
        }
        unsigned long long value = 0;
        int integer_value = 0;
        if (sscanf(line, "KernelPageSize: %llu kB", &value) == 1) {
            result.kernel_page_kib = (uint64_t)value;
        } else if (sscanf(line, "MMUPageSize: %llu kB", &value) == 1) {
            result.mmu_page_kib = (uint64_t)value;
        } else if (sscanf(line, "AnonHugePages: %llu kB", &value) == 1) {
            result.anon_huge_kib = (uint64_t)value;
        } else if (sscanf(line, "THPeligible: %d", &integer_value) == 1) {
            result.thpeligible = integer_value;
        } else if (strncmp(line, "VmFlags:", 8) == 0) {
            result.vmflag_nh = strstr(line, " nh") != NULL;
        }
    }
    free(line);
    (void)fclose(smaps);
    return result;
}

static void set_worker_error(struct worker_state *worker, int code,
                             int error_number) {
    if (worker->error_code == 0) {
        worker->error_code = code;
        worker->error_number = error_number;
    }
}

static void worker_wait_for_phase(struct worker_state *worker, int phase) {
    struct shared_state *shared = worker->shared;
    int rc = pthread_mutex_lock(&shared->mutex);
    if (rc != 0) {
        set_worker_error(worker, 20, rc);
        return;
    }
    while (atomic_load_explicit(&shared->phase, memory_order_acquire) == phase) {
        rc = pthread_cond_wait(&shared->cond, &shared->mutex);
        if (rc != 0) {
            set_worker_error(worker, 21, rc);
            break;
        }
    }
    rc = pthread_mutex_unlock(&shared->mutex);
    if (rc != 0) {
        set_worker_error(worker, 22, rc);
    }
}

static void worker_scan_one_chunk(struct worker_state *worker, size_t chunk_index,
                                  uint64_t *result) {
    const size_t words_per_chunk = WORKER_CHUNK_BYTES / sizeof(uint64_t);
    const uint64_t *words =
        (const uint64_t *)worker->buffer + chunk_index * words_per_chunk;
    uint64_t checksum = topic49_stream_scan(words, words_per_chunk);
    if (checksum != worker->expected_chunk_checksums[chunk_index]) {
        set_worker_error(worker, 30, 0);
    }
    *result = checksum;
}

static bool worker_acknowledge_run(struct worker_state *worker) {
    struct shared_state *shared = worker->shared;
    int rc = pthread_mutex_lock(&shared->mutex);
    if (rc != 0) {
        set_worker_error(worker, 31, rc);
        return false;
    }

    if (worker->run_acknowledged || worker->completed_chunks == 0 ||
        shared->run_ack_count >= shared->worker_count) {
        set_worker_error(worker, 32, 0);
        if (!worker->run_failure_reported) {
            worker->run_failure_reported = true;
            shared->run_error_count++;
        }
    } else {
        worker->run_acknowledged = true;
        shared->run_ack_count++;
    }
    rc = pthread_cond_broadcast(&shared->cond);
    if (rc != 0) {
        set_worker_error(worker, 33, rc);
    }
    int unlock_rc = pthread_mutex_unlock(&shared->mutex);
    if (unlock_rc != 0) {
        set_worker_error(worker, 34, unlock_rc);
    }
    return worker->error_code == 0;
}

static void worker_report_run_failure(struct worker_state *worker) {
    struct shared_state *shared = worker->shared;
    int rc = pthread_mutex_lock(&shared->mutex);
    if (rc != 0) {
        set_worker_error(worker, 35, rc);
        return;
    }
    if (!worker->run_failure_reported) {
        worker->run_failure_reported = true;
        shared->run_error_count++;
    }
    rc = pthread_cond_broadcast(&shared->cond);
    if (rc != 0) {
        set_worker_error(worker, 36, rc);
    }
    rc = pthread_mutex_unlock(&shared->mutex);
    if (rc != 0) {
        set_worker_error(worker, 37, rc);
    }
}

static void *worker_main(void *argument) {
    struct worker_state *worker = argument;
    struct shared_state *shared = worker->shared;
    int affinity_errno = 0;
    worker->affinity_ok =
        pin_current_thread(worker->requested_cpu, &affinity_errno);
    if (!worker->affinity_ok) {
        set_worker_error(worker, 1, affinity_errno);
    }
    worker->start_cpu = sched_getcpu();
    if (worker->start_cpu != worker->requested_cpu) {
        set_worker_error(worker, 2, 0);
    }

    int memory_policy_errno = 0;
    if (worker->error_code == 0 &&
        !bind_current_thread_memory_to_node(worker->numa_node,
                                            &memory_policy_errno)) {
        set_worker_error(worker, 38, memory_policy_errno);
    }

    if (worker->error_code == 0) {
        worker->buffer = map_nohuge(worker->buffer_bytes, &worker->nohugepage);
        if (worker->buffer == MAP_FAILED) {
            worker->buffer = NULL;
            set_worker_error(worker, 3, errno);
        }
    }
    if (worker->error_code == 0) {
        topic49_page_prepare((uint64_t *)worker->buffer,
                             worker->buffer_bytes / sizeof(uint64_t),
                             UINT64_C(0x510e527fade682d1) ^
                                 (uint64_t)worker->requested_cpu);
        worker->chunk_count = worker->buffer_bytes / WORKER_CHUNK_BYTES;
        worker->expected_chunk_checksums =
            malloc(worker->chunk_count * sizeof(uint64_t));
        if (worker->expected_chunk_checksums == NULL) {
            set_worker_error(worker, 4, errno);
        }
    }
    if (worker->error_code == 0) {
        const size_t words_per_chunk = WORKER_CHUNK_BYTES / sizeof(uint64_t);
        for (size_t i = 0; i < worker->chunk_count; ++i) {
            const uint64_t *words =
                (const uint64_t *)worker->buffer + i * words_per_chunk;
            worker->expected_chunk_checksums[i] =
                topic49_stream_scan(words, words_per_chunk);
        }
    }

    int rc = pthread_mutex_lock(&shared->mutex);
    if (rc != 0) {
        set_worker_error(worker, 5, rc);
        return NULL;
    }
    shared->ready_count++;
    (void)pthread_cond_broadcast(&shared->cond);
    while (atomic_load_explicit(&shared->phase, memory_order_acquire) ==
           PHASE_INIT) {
        rc = pthread_cond_wait(&shared->cond, &shared->mutex);
        if (rc != 0) {
            set_worker_error(worker, 6, rc);
            break;
        }
    }
    rc = pthread_mutex_unlock(&shared->mutex);
    if (rc != 0) {
        set_worker_error(worker, 7, rc);
    }

    size_t chunk_index = 0;
    uint64_t warmup_sink = 0;
    if (worker->error_code == 0 && shared->treatment == TREATMENT_LOADED) {
        while (atomic_load_explicit(&shared->phase, memory_order_acquire) ==
               PHASE_WARMUP) {
            uint64_t checksum = 0;
            worker_scan_one_chunk(worker, chunk_index, &checksum);
            warmup_sink += checksum;
            chunk_index = (chunk_index + 1) % worker->chunk_count;
            if (worker->error_code != 0) {
                break;
            }
        }
    } else if (worker->error_code == 0) {
        worker_wait_for_phase(worker, PHASE_WARMUP);
    }

    /* Finish the current chunk, then erase warmup accounting before arming. */
    worker->completed_chunks = 0;
    worker->checksum = warmup_sink ^ warmup_sink;
    chunk_index = 0;

    rc = pthread_mutex_lock(&shared->mutex);
    if (rc != 0) {
        set_worker_error(worker, 8, rc);
        return NULL;
    }
    shared->armed_count++;
    (void)pthread_cond_broadcast(&shared->cond);
    while (atomic_load_explicit(&shared->phase, memory_order_acquire) ==
           PHASE_ARM) {
        rc = pthread_cond_wait(&shared->cond, &shared->mutex);
        if (rc != 0) {
            set_worker_error(worker, 9, rc);
            break;
        }
    }
    rc = pthread_mutex_unlock(&shared->mutex);
    if (rc != 0) {
        set_worker_error(worker, 10, rc);
    }

    if (worker->error_code == 0 && shared->treatment == TREATMENT_LOADED &&
        atomic_load_explicit(&shared->phase, memory_order_acquire) == PHASE_RUN) {
        for (;;) {
            if (atomic_load_explicit(&shared->stop, memory_order_seq_cst)) {
                break;
            }
            uint64_t checksum = 0;
            worker_scan_one_chunk(worker, chunk_index, &checksum);
            if (worker->error_code != 0) {
                break;
            }
            /*
             * Publish only a whole chunk whose completion precedes the stop
             * epoch.  At most one uncounted partial/just-finished chunk per
             * worker remains, giving the reported W*chunk upper slack.
             */
            if (atomic_load_explicit(&shared->stop, memory_order_seq_cst)) {
                break;
            }
            worker->completed_chunks++;
            worker->checksum += checksum ^ mix64((uint64_t)chunk_index);
            if (!worker->run_acknowledged &&
                !worker_acknowledge_run(worker)) {
                break;
            }
            chunk_index = (chunk_index + 1) % worker->chunk_count;
        }
        if (!worker->run_acknowledged) {
            worker_report_run_failure(worker);
        }
    } else if (worker->error_code == 0) {
        worker_wait_for_phase(worker, PHASE_RUN);
    }

    worker->end_cpu = sched_getcpu();
    if (worker->end_cpu != worker->requested_cpu) {
        set_worker_error(worker, 11, 0);
    }
    int final_affinity_errno = 0;
    if (!current_affinity_is_single_cpu(worker->requested_cpu,
                                        &final_affinity_errno)) {
        worker->affinity_ok = false;
        set_worker_error(worker, 12, final_affinity_errno);
    }

    free(worker->expected_chunk_checksums);
    worker->expected_chunk_checksums = NULL;
    if (worker->buffer != NULL) {
        if (munmap(worker->buffer, worker->buffer_bytes) != 0) {
            set_worker_error(worker, 13, errno);
        }
        worker->buffer = NULL;
    }
    return NULL;
}

static void sleep_milliseconds(uint64_t milliseconds) {
    if (milliseconds > UINT64_MAX / UINT64_C(1000000)) {
        failf("warmup duration is too large");
    }
    uint64_t nanoseconds = milliseconds * UINT64_C(1000000);
    struct timespec remaining = {
        .tv_sec = (time_t)(nanoseconds / UINT64_C(1000000000)),
        .tv_nsec = (long)(nanoseconds % UINT64_C(1000000000)),
    };
    while (nanosleep(&remaining, &remaining) != 0) {
        if (errno != EINTR) {
            failf("nanosleep: %s", strerror(errno));
        }
    }
}

static void broadcast_phase(struct shared_state *shared, int phase) {
    int rc = pthread_mutex_lock(&shared->mutex);
    if (rc != 0) {
        failf("pthread_mutex_lock: %s", strerror(rc));
    }
    atomic_store_explicit(&shared->phase, phase, memory_order_release);
    rc = pthread_cond_broadcast(&shared->cond);
    if (rc != 0) {
        failf("pthread_cond_broadcast: %s", strerror(rc));
    }
    rc = pthread_mutex_unlock(&shared->mutex);
    if (rc != 0) {
        failf("pthread_mutex_unlock: %s", strerror(rc));
    }
}

static void stop_workers(struct shared_state *shared) {
    atomic_store_explicit(&shared->stop, true, memory_order_seq_cst);
    broadcast_phase(shared, PHASE_STOP);
}

static void join_workers(pthread_t *threads, size_t count) {
    for (size_t i = 0; i < count; ++i) {
        int rc = pthread_join(threads[i], NULL);
        if (rc != 0) {
            failf("pthread_join: %s", strerror(rc));
        }
    }
}

static void fail_if_worker_error(const struct worker_state *workers,
                                 size_t count) {
    for (size_t i = 0; i < count; ++i) {
        if (workers[i].error_code != 0) {
            if (workers[i].error_number != 0) {
                failf("worker %zu failed at stage %d: %s", i,
                      workers[i].error_code,
                      strerror(workers[i].error_number));
            }
            failf("worker %zu failed correctness/affinity stage %d", i,
                  workers[i].error_code);
        }
    }
}

static void print_json_string(const char *text) {
    putchar('"');
    for (const unsigned char *cursor = (const unsigned char *)text; *cursor != 0;
         ++cursor) {
        switch (*cursor) {
        case '"':
            fputs("\\\"", stdout);
            break;
        case '\\':
            fputs("\\\\", stdout);
            break;
        case '\b':
            fputs("\\b", stdout);
            break;
        case '\f':
            fputs("\\f", stdout);
            break;
        case '\n':
            fputs("\\n", stdout);
            break;
        case '\r':
            fputs("\\r", stdout);
            break;
        case '\t':
            fputs("\\t", stdout);
            break;
        default:
            if (*cursor < 0x20) {
                printf("\\u%04x", (unsigned int)*cursor);
            } else {
                putchar((int)*cursor);
            }
            break;
        }
    }
    putchar('"');
}

static void print_cpu_array(const int *cpus, size_t count) {
    putchar('[');
    for (size_t i = 0; i < count; ++i) {
        if (i != 0) {
            putchar(',');
        }
        printf("%d", cpus[i]);
    }
    putchar(']');
}

static void print_u64_array(const uint64_t *values, size_t count) {
    putchar('[');
    for (size_t i = 0; i < count; ++i) {
        if (i != 0) {
            putchar(',');
        }
        printf("%" PRIu64, values[i]);
    }
    putchar(']');
}

static long usage_delta(long after, long before) {
    return after - before;
}

int main(int argc, char **argv) {
    const uint64_t process_start_ns = now_ns();
    struct rusage process_usage_start;
    read_usage(RUSAGE_SELF, "RUSAGE_SELF", &process_usage_start);
    struct config config = parse_args(argc, argv);
    const long page_size_bytes = sysconf(_SC_PAGESIZE);
    if (page_size_bytes <= 0) {
        failf("sysconf(_SC_PAGESIZE): %s", strerror(errno));
    }

    int affinity_errno = 0;
    if (!pin_current_thread(config.probe_cpu, &affinity_errno)) {
        failf("cannot pin probe to CPU %d: %s", config.probe_cpu,
              strerror(affinity_errno));
    }
    if (sched_getcpu() != config.probe_cpu) {
        failf("probe did not begin on requested CPU %d", config.probe_cpu);
    }
    int memory_policy_errno = 0;
    if (!bind_current_thread_memory_to_node(config.numa_node,
                                            &memory_policy_errno)) {
        failf("cannot bind probe memory policy to NUMA node %d: %s",
              config.numa_node, strerror(memory_policy_errno));
    }

    const size_t large_bytes =
        (size_t)config.large_mib * (size_t)1024 * (size_t)1024;
    const size_t worker_bytes_each =
        (size_t)config.worker_mib * (size_t)1024 * (size_t)1024;
    if (worker_bytes_each < WORKER_CHUNK_BYTES ||
        worker_bytes_each % WORKER_CHUNK_BYTES != 0) {
        failf("worker mapping must be a positive multiple of %d bytes",
              WORKER_CHUNK_BYTES);
    }

    struct cycle large =
        make_cycle(large_bytes, UINT64_C(0x243f6a8885a308d3));
    struct cycle small =
        make_cycle(SMALL_BYTES, UINT64_C(0x13198a2e03707344));

    struct map_evidence large_mapping = read_map_evidence(large.nodes);
    struct map_evidence small_mapping = read_map_evidence(small.nodes);

    struct shared_state shared = {
        .phase = ATOMIC_VAR_INIT(PHASE_INIT),
        .stop = ATOMIC_VAR_INIT(false),
        .ready_count = 0,
        .armed_count = 0,
        .run_ack_count = 0,
        .run_error_count = 0,
        .worker_count = config.worker_count,
        .treatment = config.treatment,
    };
    int rc = pthread_mutex_init(&shared.mutex, NULL);
    if (rc != 0) {
        failf("pthread_mutex_init: %s", strerror(rc));
    }
    rc = pthread_cond_init(&shared.cond, NULL);
    if (rc != 0) {
        failf("pthread_cond_init: %s", strerror(rc));
    }

    struct worker_state *workers =
        calloc(config.worker_count, sizeof(*workers));
    pthread_t *threads = calloc(config.worker_count, sizeof(*threads));
    if (workers == NULL || threads == NULL) {
        failf("allocate worker metadata: %s", strerror(errno));
    }
    for (size_t i = 0; i < config.worker_count; ++i) {
        workers[i].shared = &shared;
        workers[i].requested_cpu = config.worker_cpus[i];
        workers[i].numa_node = config.numa_node;
        workers[i].start_cpu = -1;
        workers[i].end_cpu = -1;
        workers[i].buffer_bytes = worker_bytes_each;
        rc = pthread_create(&threads[i], NULL, worker_main, &workers[i]);
        if (rc != 0) {
            failf("pthread_create worker %zu: %s", i, strerror(rc));
        }
    }

    rc = pthread_mutex_lock(&shared.mutex);
    if (rc != 0) {
        failf("pthread_mutex_lock ready: %s", strerror(rc));
    }
    while (shared.ready_count != config.worker_count) {
        rc = pthread_cond_wait(&shared.cond, &shared.mutex);
        if (rc != 0) {
            failf("pthread_cond_wait ready: %s", strerror(rc));
        }
    }
    rc = pthread_mutex_unlock(&shared.mutex);
    if (rc != 0) {
        failf("pthread_mutex_unlock ready: %s", strerror(rc));
    }

    bool setup_worker_error = false;
    for (size_t i = 0; i < config.worker_count; ++i) {
        if (workers[i].error_code != 0) {
            setup_worker_error = true;
        }
        if (workers[i].buffer != NULL) {
            workers[i].mapping = read_map_evidence(workers[i].buffer);
        }
    }
    if (setup_worker_error) {
        stop_workers(&shared);
        join_workers(threads, config.worker_count);
        fail_if_worker_error(workers, config.worker_count);
    }

    const uint64_t warmup_begin_ns = now_ns();
    broadcast_phase(&shared, PHASE_WARMUP);
    sleep_milliseconds(config.warmup_ms);
    const uint64_t arm_request_ns = now_ns();

    rc = pthread_mutex_lock(&shared.mutex);
    if (rc != 0) {
        failf("pthread_mutex_lock arm: %s", strerror(rc));
    }
    atomic_store_explicit(&shared.phase, PHASE_ARM, memory_order_release);
    rc = pthread_cond_broadcast(&shared.cond);
    if (rc != 0) {
        failf("pthread_cond_broadcast arm: %s", strerror(rc));
    }
    while (shared.armed_count != config.worker_count) {
        rc = pthread_cond_wait(&shared.cond, &shared.mutex);
        if (rc != 0) {
            failf("pthread_cond_wait arm: %s", strerror(rc));
        }
    }
    rc = pthread_mutex_unlock(&shared.mutex);
    if (rc != 0) {
        failf("pthread_mutex_unlock arm: %s", strerror(rc));
    }
    for (size_t i = 0; i < config.worker_count; ++i) {
        if (workers[i].error_code != 0) {
            stop_workers(&shared);
            join_workers(threads, config.worker_count);
            fail_if_worker_error(workers, config.worker_count);
        }
    }

    /* Record the epoch first, then release every reset worker from one barrier. */
    rc = pthread_mutex_lock(&shared.mutex);
    if (rc != 0) {
        failf("pthread_mutex_lock run: %s", strerror(rc));
    }
    const uint64_t run_epoch_begin_ns = now_ns();
    atomic_store_explicit(&shared.phase, PHASE_RUN, memory_order_release);
    rc = pthread_cond_broadcast(&shared.cond);
    if (rc != 0) {
        failf("pthread_cond_broadcast run: %s", strerror(rc));
    }
    rc = pthread_mutex_unlock(&shared.mutex);
    if (rc != 0) {
        failf("pthread_mutex_unlock run: %s", strerror(rc));
    }

    /*
     * A loaded measurement cannot begin until every worker has completed and
     * published at least one full RUN chunk.  Workers keep scanning after
     * publishing, so this wait establishes participation without inserting a
     * quiet gap before either dependent traversal.
     */
    if (config.treatment == TREATMENT_LOADED) {
        rc = pthread_mutex_lock(&shared.mutex);
        if (rc != 0) {
            failf("pthread_mutex_lock run acknowledgement: %s", strerror(rc));
        }
        while (shared.run_ack_count != config.worker_count &&
               shared.run_error_count == 0) {
            rc = pthread_cond_wait(&shared.cond, &shared.mutex);
            if (rc != 0) {
                failf("pthread_cond_wait run acknowledgement: %s",
                      strerror(rc));
            }
        }
        const bool run_ack_failed = shared.run_error_count != 0;
        rc = pthread_mutex_unlock(&shared.mutex);
        if (rc != 0) {
            failf("pthread_mutex_unlock run acknowledgement: %s",
                  strerror(rc));
        }
        if (run_ack_failed) {
            stop_workers(&shared);
            join_workers(threads, config.worker_count);
            fail_if_worker_error(workers, config.worker_count);
            failf("a loaded worker failed before RUN participation");
        }
    }

    uint64_t small_loads = SMALL_TARGET_LOADS;
    if (small_loads % small.node_count != 0) {
        small_loads =
            ((small_loads / small.node_count) + 1) * small.node_count;
    }
    uint64_t small_elapsed_ns = 0;
    uint64_t small_final_index = UINT64_MAX;
    uint64_t small_checksum =
        topic49_run_timed(small.nodes, small.start, small_loads,
                          &small_elapsed_ns, &small_final_index);
    uint64_t small_expected =
        small.checksum_per_cycle * (small_loads / small.node_count);

    const int probe_start_cpu = sched_getcpu();
    struct rusage process_large_window_usage_before;
    struct rusage process_large_window_usage_after;
    struct rusage probe_thread_large_window_usage_before;
    struct rusage probe_thread_large_window_usage_after;
    read_usage(RUSAGE_THREAD, "RUSAGE_THREAD",
               &probe_thread_large_window_usage_before);
    read_usage(RUSAGE_SELF, "RUSAGE_SELF",
               &process_large_window_usage_before);
    if (large.node_count > UINT64_MAX / UINT64_C(4)) {
        failf("large traversal load count overflows uint64_t");
    }
    const uint64_t probe_loads = large.node_count * UINT64_C(4);
    uint64_t probe_elapsed_ns = 0;
    uint64_t probe_final_index = UINT64_MAX;
    uint64_t probe_checksum =
        topic49_run_timed(large.nodes, large.start, probe_loads,
                          &probe_elapsed_ns, &probe_final_index);
    read_usage(RUSAGE_SELF, "RUSAGE_SELF", &process_large_window_usage_after);
    read_usage(RUSAGE_THREAD, "RUSAGE_THREAD",
               &probe_thread_large_window_usage_after);
    const int probe_end_cpu = sched_getcpu();

    atomic_store_explicit(&shared.stop, true, memory_order_seq_cst);
    broadcast_phase(&shared, PHASE_STOP);
    join_workers(threads, config.worker_count);
    /*
     * End the RUN epoch only after every worker has terminated.  A worker may
     * have observed stop=false just before the main thread published stop and
     * may therefore finish one last chunk.  Including termination in the
     * epoch keeps every source read inside the reported wall-clock interval;
     * the one-chunk-per-worker inclusive upper slack covers that final chunk.
     */
    const uint64_t run_epoch_end_ns = now_ns();

    const uint64_t probe_expected = large.checksum_per_cycle * UINT64_C(4);
    if (small_final_index != small.start || small_checksum != small_expected ||
        probe_final_index != large.start || probe_checksum != probe_expected) {
        failf("dependent traversal correctness check failed");
    }
    if (probe_start_cpu != config.probe_cpu ||
        probe_end_cpu != config.probe_cpu) {
        failf("probe migrated: requested=%d start=%d end=%d", config.probe_cpu,
              probe_start_cpu, probe_end_cpu);
    }
    int final_probe_affinity_errno = 0;
    if (!current_affinity_is_single_cpu(config.probe_cpu,
                                        &final_probe_affinity_errno)) {
        failf("probe affinity changed: %s", strerror(final_probe_affinity_errno));
    }
    fail_if_worker_error(workers, config.worker_count);

    const long process_large_window_minor_faults = usage_delta(
        process_large_window_usage_after.ru_minflt,
        process_large_window_usage_before.ru_minflt);
    const long process_large_window_major_faults = usage_delta(
        process_large_window_usage_after.ru_majflt,
        process_large_window_usage_before.ru_majflt);
    const long process_large_window_voluntary_context_switches = usage_delta(
        process_large_window_usage_after.ru_nvcsw,
        process_large_window_usage_before.ru_nvcsw);
    const long process_large_window_involuntary_context_switches = usage_delta(
        process_large_window_usage_after.ru_nivcsw,
        process_large_window_usage_before.ru_nivcsw);
    const long probe_thread_large_window_minor_faults = usage_delta(
        probe_thread_large_window_usage_after.ru_minflt,
        probe_thread_large_window_usage_before.ru_minflt);
    const long probe_thread_large_window_major_faults = usage_delta(
        probe_thread_large_window_usage_after.ru_majflt,
        probe_thread_large_window_usage_before.ru_majflt);
    const long probe_thread_large_window_voluntary_context_switches =
        usage_delta(probe_thread_large_window_usage_after.ru_nvcsw,
                    probe_thread_large_window_usage_before.ru_nvcsw);
    const long probe_thread_large_window_involuntary_context_switches =
        usage_delta(probe_thread_large_window_usage_after.ru_nivcsw,
                    probe_thread_large_window_usage_before.ru_nivcsw);
    if (process_large_window_major_faults != 0) {
        failf("process-wide large window incurred %ld major page faults",
              process_large_window_major_faults);
    }

    uint64_t worker_chunks = 0;
    uint64_t worker_checksum = 0;
    uint64_t worker_anon_huge_kib = 0;
    bool worker_vmflag_nh_all = true;
    bool affinity_ok = true;
    bool madv_nohugepage = large.nohugepage && small.nohugepage;
    bool smaps_available = large_mapping.found && small_mapping.found;
    int *worker_start_cpus = malloc(config.worker_count * sizeof(int));
    int *worker_end_cpus = malloc(config.worker_count * sizeof(int));
    uint64_t *worker_chunks_by_thread =
        malloc(config.worker_count * sizeof(uint64_t));
    if (worker_start_cpus == NULL || worker_end_cpus == NULL ||
        worker_chunks_by_thread == NULL) {
        failf("allocate observed CPU arrays: %s", strerror(errno));
    }
    for (size_t i = 0; i < config.worker_count; ++i) {
        worker_chunks_by_thread[i] = workers[i].completed_chunks;
        if (config.treatment == TREATMENT_LOADED) {
            if (!workers[i].run_acknowledged ||
                worker_chunks_by_thread[i] == 0) {
                failf("loaded worker %zu did not publish RUN participation",
                      i);
            }
        } else if (workers[i].run_acknowledged ||
                   worker_chunks_by_thread[i] != 0) {
            failf("idle worker %zu unexpectedly participated in RUN", i);
        }
        worker_checksum += workers[i].checksum;
        worker_anon_huge_kib += workers[i].mapping.anon_huge_kib;
        worker_vmflag_nh_all =
            worker_vmflag_nh_all && workers[i].mapping.found &&
            workers[i].mapping.vmflag_nh;
        smaps_available = smaps_available && workers[i].mapping.found;
        affinity_ok = affinity_ok && workers[i].affinity_ok &&
                      workers[i].start_cpu == workers[i].requested_cpu &&
                      workers[i].end_cpu == workers[i].requested_cpu;
        madv_nohugepage = madv_nohugepage && workers[i].nohugepage;
        worker_start_cpus[i] = workers[i].start_cpu;
        worker_end_cpus[i] = workers[i].end_cpu;
    }
    for (size_t i = 0; i < config.worker_count; ++i) {
        if (UINT64_MAX - worker_chunks < worker_chunks_by_thread[i]) {
            failf("worker chunk count overflow");
        }
        worker_chunks += worker_chunks_by_thread[i];
    }
    if (shared.run_error_count != 0) {
        failf("%zu workers reported a RUN participation failure",
              shared.run_error_count);
    }
    if (config.treatment == TREATMENT_LOADED) {
        if (shared.run_ack_count != config.worker_count ||
            worker_chunks < config.worker_count) {
            failf("loaded RUN participation/count invariant failed");
        }
    } else if (shared.run_ack_count != 0 || worker_chunks != 0) {
        failf("idle RUN participation/count invariant failed");
    }
    if (!affinity_ok) {
        failf("one or more workers violated requested affinity");
    }
    if (worker_chunks > UINT64_MAX / WORKER_CHUNK_BYTES) {
        failf("worker byte count overflow");
    }
    const uint64_t worker_bytes_lower =
        worker_chunks * (uint64_t)WORKER_CHUNK_BYTES;
    uint64_t worker_bytes_upper_inclusive = 0;
    if (config.treatment == TREATMENT_LOADED) {
        if (config.worker_count >
            (UINT64_MAX - worker_bytes_lower) / WORKER_CHUNK_BYTES) {
            failf("worker upper byte bound overflow");
        }
        worker_bytes_upper_inclusive =
            worker_bytes_lower +
            (uint64_t)config.worker_count * (uint64_t)WORKER_CHUNK_BYTES;
    }
    if (worker_bytes_lower > worker_bytes_upper_inclusive ||
        (config.treatment == TREATMENT_IDLE &&
         (worker_bytes_lower != 0 || worker_bytes_upper_inclusive != 0))) {
        failf("worker byte interval invariant failed");
    }

    if (probe_loads > UINT64_MAX / CACHE_LINE_BYTES) {
        failf("probe byte count overflow");
    }
    const uint64_t probe_bytes = probe_loads * CACHE_LINE_BYTES;

    struct rusage process_usage_end;
    read_usage(RUSAGE_SELF, "RUSAGE_SELF", &process_usage_end);
    const long total_major_faults = usage_delta(process_usage_end.ru_majflt,
                                                process_usage_start.ru_majflt);
    if (total_major_faults != 0) {
        failf("process incurred %ld total major page faults", total_major_faults);
    }

    if (munmap(large.nodes, large.bytes) != 0) {
        failf("munmap large cycle: %s", strerror(errno));
    }
    if (munmap(small.nodes, small.bytes) != 0) {
        failf("munmap small cycle: %s", strerror(errno));
    }
    rc = pthread_cond_destroy(&shared.cond);
    if (rc != 0) {
        failf("pthread_cond_destroy: %s", strerror(rc));
    }
    rc = pthread_mutex_destroy(&shared.mutex);
    if (rc != 0) {
        failf("pthread_mutex_destroy: %s", strerror(rc));
    }

    const uint64_t total_end_ns = now_ns();
    const uint64_t startup_ns = warmup_begin_ns - process_start_ns;
    const uint64_t warmup_ns = arm_request_ns - warmup_begin_ns;
    /* Keep phase intervals contiguous so their exact sum equals total_ns. */
    const uint64_t arm_wait_ns = run_epoch_begin_ns - arm_request_ns;
    const uint64_t run_epoch_ns = run_epoch_end_ns - run_epoch_begin_ns;
    const uint64_t teardown_ns = total_end_ns - run_epoch_end_ns;
    const uint64_t total_ns = total_end_ns - process_start_ns;
    if (small_elapsed_ns == 0 || probe_elapsed_ns == 0 || run_epoch_ns == 0) {
        failf("clock resolution produced a zero-duration interval");
    }

    const double small_ns_per_load =
        (double)small_elapsed_ns / (double)small_loads;
    const double probe_ns_per_load =
        (double)probe_elapsed_ns / (double)probe_loads;
    const double run_epoch_seconds = (double)run_epoch_ns / 1.0e9;
    const double worker_gib_per_s_lower =
        ((double)worker_bytes_lower / 1073741824.0) / run_epoch_seconds;
    const double worker_gib_per_s_upper_inclusive =
        ((double)worker_bytes_upper_inclusive / 1073741824.0) /
        run_epoch_seconds;
    if (config.treatment == TREATMENT_IDLE &&
        (worker_gib_per_s_lower != 0.0 ||
         worker_gib_per_s_upper_inclusive != 0.0)) {
        failf("idle worker-rate interval invariant failed");
    }

    const char *label = getenv("BENCH_LABEL");
    if (label == NULL) {
        label = "";
    }
    const char *treatment =
        config.treatment == TREATMENT_LOADED ? "loaded" : "idle";

    fputs("{\"schema\":\"dram-memory-controller.v1\",\"label\":", stdout);
    print_json_string(label);
    fputs(",\"treatment\":", stdout);
    print_json_string(treatment);
    printf(",\"probe_cpu\":%d,\"worker_cpus\":", config.probe_cpu);
    print_cpu_array(config.worker_cpus, config.worker_count);
    printf(",\"numa_node\":%d,\"memory_policy\":\"MPOL_BIND\","
           "\"memory_policy_bound\":true,"
           "\"probe_start_cpu\":%d,\"probe_end_cpu\":%d,"
           "\"worker_start_cpus\":",
           config.numa_node, probe_start_cpu, probe_end_cpu);
    print_cpu_array(worker_start_cpus, config.worker_count);
    fputs(",\"worker_end_cpus\":", stdout);
    print_cpu_array(worker_end_cpus, config.worker_count);
    printf(",\"large_mib\":%" PRIu64 ",\"worker_mib\":%" PRIu64
           ",\"warmup_ms\":%" PRIu64 ",\"chunk_bytes\":%d,"
           "\"correct\":true,\"affinity_ok\":true,"
           "\"prefetch_state\":\"production-default-unmodified\","
           "\"madv_nohugepage\":%s,\"page_size_bytes\":%ld,"
           "\"smaps_available\":%s,\"large_kernel_page_kib\":%" PRIu64
           ",\"large_mmu_page_kib\":%" PRIu64
           ",\"large_anon_huge_kib\":%" PRIu64
           ",\"large_thpeligible\":%d,\"large_vmflag_nh\":%s,"
           "\"small_kernel_page_kib\":%" PRIu64
           ",\"small_anon_huge_kib\":%" PRIu64
           ",\"small_vmflag_nh\":%s,\"worker_anon_huge_kib\":%" PRIu64
           ",\"worker_vmflag_nh_all\":%s,"
           "\"startup_ns\":%" PRIu64 ",\"warmup_ns\":%" PRIu64
           ",\"arm_wait_ns\":%" PRIu64 ",\"run_epoch_ns\":%" PRIu64
           ",\"teardown_ns\":%" PRIu64 ",\"total_ns\":%" PRIu64
           ",\"small_loads\":%" PRIu64 ",\"small_elapsed_ns\":%" PRIu64
           ",\"small_ns_per_load\":%.9f,\"small_checksum\":%" PRIu64
           ",\"probe_loads\":%" PRIu64 ",\"probe_elapsed_ns\":%" PRIu64
           ",\"probe_ns_per_load\":%.9f,\"probe_bytes\":%" PRIu64
           ",\"probe_checksum\":%" PRIu64 ",\"worker_chunks\":%" PRIu64,
           config.large_mib, config.worker_mib, config.warmup_ms,
           WORKER_CHUNK_BYTES, madv_nohugepage ? "true" : "false",
           page_size_bytes, smaps_available ? "true" : "false",
           large_mapping.kernel_page_kib, large_mapping.mmu_page_kib,
           large_mapping.anon_huge_kib, large_mapping.thpeligible,
           large_mapping.vmflag_nh ? "true" : "false",
           small_mapping.kernel_page_kib, small_mapping.anon_huge_kib,
           small_mapping.vmflag_nh ? "true" : "false",
           worker_anon_huge_kib, worker_vmflag_nh_all ? "true" : "false",
           startup_ns, warmup_ns, arm_wait_ns, run_epoch_ns, teardown_ns,
           total_ns, small_loads, small_elapsed_ns, small_ns_per_load,
           small_checksum, probe_loads, probe_elapsed_ns, probe_ns_per_load,
           probe_bytes, probe_checksum, worker_chunks);
    fputs(",\"worker_chunks_by_thread\":", stdout);
    print_u64_array(worker_chunks_by_thread, config.worker_count);
    printf(",\"worker_bytes\":%" PRIu64
           ",\"worker_bytes_lower\":%" PRIu64
           ",\"worker_bytes_upper_inclusive\":%" PRIu64
           ",\"worker_gib_per_s_lower\":%.9f,"
           "\"worker_gib_per_s_upper_inclusive\":%.9f,"
           "\"worker_checksum\":%" PRIu64
           ",\"process_large_window_minor_faults\":%ld,"
           "\"process_large_window_major_faults\":%ld,"
           "\"process_large_window_voluntary_context_switches\":%ld,"
           "\"process_large_window_involuntary_context_switches\":%ld,"
           "\"probe_thread_large_window_minor_faults\":%ld,"
           "\"probe_thread_large_window_major_faults\":%ld,"
           "\"probe_thread_large_window_voluntary_context_switches\":%ld,"
           "\"probe_thread_large_window_involuntary_context_switches\":%ld,"
           "\"total_major_faults\":%ld}\n",
           worker_bytes_lower, worker_bytes_lower,
           worker_bytes_upper_inclusive, worker_gib_per_s_lower,
           worker_gib_per_s_upper_inclusive, worker_checksum,
           process_large_window_minor_faults,
           process_large_window_major_faults,
           process_large_window_voluntary_context_switches,
           process_large_window_involuntary_context_switches,
           probe_thread_large_window_minor_faults,
           probe_thread_large_window_major_faults,
           probe_thread_large_window_voluntary_context_switches,
           probe_thread_large_window_involuntary_context_switches,
           total_major_faults);

    free(worker_start_cpus);
    free(worker_end_cpus);
    free(worker_chunks_by_thread);
    free(workers);
    free(threads);
    free(config.worker_cpus);
    return 0;
}
