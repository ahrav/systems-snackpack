#define _GNU_SOURCE

#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_barrier_t start_barrier;
static atomic_int holder_done;

#if defined(__GNUC__) && !defined(__clang__)
#define TOPIC50_NOINLINE __attribute__((noinline, noclone, noipa))
#elif defined(__GNUC__)
#define TOPIC50_NOINLINE __attribute__((noinline))
#else
#define TOPIC50_NOINLINE
#endif

struct thread_result {
    int requested_cpu;
    int pin_rc;
    int affinity_exact;
    int start_cpu;
    int end_cpu;
    int nice_set_rc;
    int nice_set_errno;
    int observed_nice;
    int sched_get_rc;
    int sched_policy;
    int sched_priority;
    uint64_t wall_ns;
    uint64_t cpu_ns;
    long voluntary_cs;
    long involuntary_cs;
};

struct thread_arg {
    int cpu;
    int nice_value;
    uint64_t burn_cpu_ns;
    struct thread_result *result;
};

static uint64_t ns_since(const struct timespec *start, const struct timespec *end) {
    return (uint64_t)(end->tv_sec - start->tv_sec) * 1000000000ULL +
           (uint64_t)(end->tv_nsec - start->tv_nsec);
}

static uint64_t realtime_ns(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_REALTIME, &now) != 0) {
        perror("clock_gettime(CLOCK_REALTIME)");
        exit(2);
    }
    return (uint64_t)now.tv_sec * 1000000000ULL + (uint64_t)now.tv_nsec;
}

static void barrier_wait_checked(void) {
    int rc = pthread_barrier_wait(&start_barrier);
    if (rc != 0 && rc != PTHREAD_BARRIER_SERIAL_THREAD) {
        fprintf(stderr, "pthread_barrier_wait: %s\n", strerror(rc));
        exit(2);
    }
}

static void pin_and_verify(int cpu, struct thread_result *result) {
    cpu_set_t requested;
    cpu_set_t observed;
    CPU_ZERO(&requested);
    CPU_SET(cpu, &requested);
    result->requested_cpu = cpu;
    result->pin_rc = pthread_setaffinity_np(pthread_self(), sizeof(requested), &requested);

    CPU_ZERO(&observed);
    if (sched_getaffinity(0, sizeof(observed), &observed) != 0) {
        result->affinity_exact = 0;
        return;
    }
    result->affinity_exact =
        result->pin_rc == 0 && CPU_COUNT(&observed) == 1 && CPU_ISSET(cpu, &observed);
}

static void observe_scheduling(struct thread_result *result) {
    struct sched_param parameter = {0};
    result->observed_nice = getpriority(PRIO_PROCESS, (id_t)syscall(SYS_gettid));
    result->sched_get_rc = pthread_getschedparam(pthread_self(), &result->sched_policy, &parameter);
    result->sched_priority = parameter.sched_priority;
}

static TOPIC50_NOINLINE uint64_t burn_thread_cpu(uint64_t target_ns) {
    struct timespec start;
    struct timespec now;
    volatile uint64_t x = 0x9e3779b97f4a7c15ULL;
    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &start) != 0) {
        perror("clock_gettime(CLOCK_THREAD_CPUTIME_ID)");
        exit(2);
    }
    do {
        for (unsigned i = 0; i < 4096; ++i) {
            x ^= x << 7;
            x ^= x >> 9;
            x *= 0xbf58476d1ce4e5b9ULL;
        }
        if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &now) != 0) {
            perror("clock_gettime(CLOCK_THREAD_CPUTIME_ID)");
            exit(2);
        }
    } while (ns_since(&start, &now) < target_ns);
    return x;
}

static void *holder_main(void *opaque) {
    struct thread_arg *arg = opaque;
    struct thread_result *r = arg->result;
    struct timespec wall_start;
    struct timespec wall_end;
    struct timespec cpu_start;
    struct timespec cpu_end;
    struct rusage ru_start;
    struct rusage ru_end;

    pin_and_verify(arg->cpu, r);
    errno = 0;
    r->nice_set_rc = setpriority(PRIO_PROCESS, (id_t)syscall(SYS_gettid), arg->nice_value);
    r->nice_set_errno = errno;
    observe_scheduling(r);

    if (pthread_mutex_lock(&lock) != 0) {
        abort();
    }
    barrier_wait_checked();
    r->start_cpu = sched_getcpu();
    clock_gettime(CLOCK_MONOTONIC_RAW, &wall_start);
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cpu_start);
    getrusage(RUSAGE_THREAD, &ru_start);
    (void)burn_thread_cpu(arg->burn_cpu_ns);
    getrusage(RUSAGE_THREAD, &ru_end);
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cpu_end);
    clock_gettime(CLOCK_MONOTONIC_RAW, &wall_end);
    r->end_cpu = sched_getcpu();
    r->wall_ns = ns_since(&wall_start, &wall_end);
    r->cpu_ns = ns_since(&cpu_start, &cpu_end);
    r->voluntary_cs = ru_end.ru_nvcsw - ru_start.ru_nvcsw;
    r->involuntary_cs = ru_end.ru_nivcsw - ru_start.ru_nivcsw;
    pthread_mutex_unlock(&lock);
    atomic_store_explicit(&holder_done, 1, memory_order_release);
    return NULL;
}

static void *waiter_main(void *opaque) {
    struct thread_arg *arg = opaque;
    struct thread_result *r = arg->result;
    struct timespec start;
    struct timespec end;
    struct rusage ru_start;
    struct rusage ru_end;

    pin_and_verify(arg->cpu, r);
    observe_scheduling(r);
    barrier_wait_checked();
    r->start_cpu = sched_getcpu();
    clock_gettime(CLOCK_MONOTONIC_RAW, &start);
    getrusage(RUSAGE_THREAD, &ru_start);
    pthread_mutex_lock(&lock);
    getrusage(RUSAGE_THREAD, &ru_end);
    clock_gettime(CLOCK_MONOTONIC_RAW, &end);
    r->end_cpu = sched_getcpu();
    r->wall_ns = ns_since(&start, &end);
    r->voluntary_cs = ru_end.ru_nvcsw - ru_start.ru_nvcsw;
    r->involuntary_cs = ru_end.ru_nivcsw - ru_start.ru_nivcsw;
    pthread_mutex_unlock(&lock);
    return NULL;
}

static void *hog_main(void *opaque) {
    struct thread_arg *arg = opaque;
    struct thread_result *r = arg->result;
    struct timespec start;
    struct timespec end;
    struct timespec cpu_start;
    struct timespec cpu_end;
    struct rusage ru_start;
    struct rusage ru_end;
    volatile uint64_t x = 0x94d049bb133111ebULL;

    pin_and_verify(arg->cpu, r);
    observe_scheduling(r);
    barrier_wait_checked();
    r->start_cpu = sched_getcpu();
    clock_gettime(CLOCK_MONOTONIC_RAW, &start);
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cpu_start);
    getrusage(RUSAGE_THREAD, &ru_start);
    while (!atomic_load_explicit(&holder_done, memory_order_acquire)) {
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        atomic_signal_fence(memory_order_seq_cst);
    }
    getrusage(RUSAGE_THREAD, &ru_end);
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cpu_end);
    clock_gettime(CLOCK_MONOTONIC_RAW, &end);
    r->end_cpu = sched_getcpu();
    r->wall_ns = ns_since(&start, &end);
    r->cpu_ns = ns_since(&cpu_start, &cpu_end);
    r->voluntary_cs = ru_end.ru_nvcsw - ru_start.ru_nvcsw;
    r->involuntary_cs = ru_end.ru_nivcsw - ru_start.ru_nivcsw;
    return (void *)(uintptr_t)(x & 1U);
}

static long parse_long(const char *name, const char *text) {
    char *end = NULL;
    errno = 0;
    long value = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0') {
        fprintf(stderr, "invalid %s: %s\n", name, text);
        exit(2);
    }
    return value;
}

int main(int argc, char **argv) {
    if (argc != 10) {
        fprintf(stderr,
                "usage: %s LABEL BLOCK PERIOD MODE HOLDER_CPU WAITER_CPU HOG_CPU "
                "HOLDER_NICE BURN_CPU_US\n",
                argv[0]);
        return 2;
    }

    const char *label = argv[1];
    long block = parse_long("block", argv[2]);
    long period = parse_long("period", argv[3]);
    const char *mode = argv[4];
    long holder_cpu = parse_long("holder_cpu", argv[5]);
    long waiter_cpu = parse_long("waiter_cpu", argv[6]);
    long hog_cpu = parse_long("hog_cpu", argv[7]);
    long holder_nice = parse_long("holder_nice", argv[8]);
    long burn_cpu_us = parse_long("burn_cpu_us", argv[9]);
    if (holder_cpu < 0 || waiter_cpu < 0 || hog_cpu < 0 ||
        holder_cpu > CPU_SETSIZE - 1 || waiter_cpu > CPU_SETSIZE - 1 ||
        hog_cpu > CPU_SETSIZE - 1 || holder_nice < 0 || holder_nice > 19 ||
        burn_cpu_us <= 0) {
        fprintf(stderr, "argument out of range\n");
        return 2;
    }

    struct thread_result holder = {0};
    struct thread_result waiter = {0};
    struct thread_result hog = {0};
    struct thread_arg holder_arg = {
        .cpu = (int)holder_cpu,
        .nice_value = (int)holder_nice,
        .burn_cpu_ns = (uint64_t)burn_cpu_us * 1000ULL,
        .result = &holder,
    };
    struct thread_arg waiter_arg = {.cpu = (int)waiter_cpu, .result = &waiter};
    struct thread_arg hog_arg = {.cpu = (int)hog_cpu, .result = &hog};
    pthread_t holder_thread;
    pthread_t waiter_thread;
    pthread_t hog_thread;

    atomic_init(&holder_done, 0);
    if (pthread_barrier_init(&start_barrier, NULL, 3) != 0) {
        abort();
    }
    uint64_t started_realtime_ns = realtime_ns();
    if (pthread_create(&holder_thread, NULL, holder_main, &holder_arg) != 0 ||
        pthread_create(&waiter_thread, NULL, waiter_main, &waiter_arg) != 0 ||
        pthread_create(&hog_thread, NULL, hog_main, &hog_arg) != 0) {
        abort();
    }
    pthread_join(holder_thread, NULL);
    pthread_join(waiter_thread, NULL);
    pthread_join(hog_thread, NULL);
    pthread_barrier_destroy(&start_barrier);

    printf("%s,%ld,%ld,%s,%ld,%llu,%ld,%ld,%ld,%ld,"
           "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,"
           "%llu,%llu,%ld,%ld,%llu,%ld,%ld,%llu,%llu,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld\n",
           label,
           block,
           period,
           mode,
           (long)getpid(),
           (unsigned long long)started_realtime_ns,
           holder_cpu,
           waiter_cpu,
           hog_cpu,
           holder_nice,
           holder.nice_set_rc,
           holder.nice_set_errno,
           holder.observed_nice,
           waiter.observed_nice,
           hog.observed_nice,
           holder.sched_get_rc,
           holder.sched_policy,
           holder.sched_priority,
           waiter.sched_get_rc,
           waiter.sched_policy,
           waiter.sched_priority,
           hog.sched_get_rc,
           hog.sched_policy,
           hog.sched_priority,
           holder.pin_rc,
           waiter.pin_rc,
           hog.pin_rc,
           holder.affinity_exact,
           waiter.affinity_exact,
           hog.affinity_exact,
           (unsigned long long)holder.wall_ns,
           (unsigned long long)holder.cpu_ns,
           (long)holder.start_cpu,
           (long)holder.end_cpu,
           (unsigned long long)waiter.wall_ns,
           (long)waiter.start_cpu,
           (long)waiter.end_cpu,
           (unsigned long long)hog.wall_ns,
           (unsigned long long)hog.cpu_ns,
           (long)hog.start_cpu,
           (long)hog.end_cpu,
           holder.voluntary_cs,
           holder.involuntary_cs,
           waiter.voluntary_cs,
           waiter.involuntary_cs,
           hog.voluntary_cs,
           hog.involuntary_cs);
    return 0;
}
