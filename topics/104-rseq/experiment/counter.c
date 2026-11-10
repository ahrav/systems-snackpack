#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <linux/rseq.h>
#include <pthread.h>
#include <sched.h>
#include <signal.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#if defined(__x86_64__)
#define SIGNATURE 0x53053053
#elif defined(__aarch64__) && !defined(__AARCH64EB__)
#define SIGNATURE 0xd428bc00
#else
#error Unsupported architecture
#endif
_Static_assert(offsetof(struct rseq, cpu_id) == 4, "CPU ABI offset");
_Static_assert(offsetof(struct rseq, rseq_cs) == 8, "descriptor ABI offset");
extern int rseq_add(struct rseq *, uint64_t *, int, unsigned);
struct slot { _Alignas(128) uint64_t value; };
static struct slot slots[CPU_SETSIZE];
static _Thread_local volatile uint64_t local_count;
static _Thread_local struct rseq area __attribute__((aligned(32)));
static _Atomic uint64_t shared_count;
static _Atomic int stop_stress;
static pthread_barrier_t ready, launch;
static int cpus[CPU_SETSIZE], ncpu, nthreads, stress, method;
static uint64_t iterations;
struct worker { pthread_t thread; uint64_t total, retries; };
static struct worker workers[128];
static void fail(const char *what) { perror(what); exit(2); }
static void check(int code, const char *what) { if (code) { errno = code; fail(what); } }
static void pin(pthread_t thread, int cpu) {
    cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu, &set);
    check(pthread_setaffinity_np(thread, sizeof(set), &set), "affinity");
}
static void signal_handler(int sig) { (void)sig; }
static double now(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) fail("clock");
    return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}
static void *run(void *arg) {
    struct worker *w = arg;
    pin(pthread_self(), cpus[(w - workers) % ncpu]);
    if (method == 0) {
        area.cpu_id = (uint32_t)-1;
        if (syscall(SYS_rseq, &area, 32, 0, SIGNATURE)) fail("rseq registration (reserve libc rseq with GLIBC_TUNABLES)");
    }
    pthread_barrier_wait(&ready);
    pthread_barrier_wait(&launch);
    for (uint64_t i = 0; i < iterations; ++i) {
        if (method == 0) {
            for (;;) {
                int cpu = (int)*(volatile uint32_t *)&area.cpu_id;
                if (cpu < 0 || cpu >= CPU_SETSIZE) { errno = ERANGE; fail("CPU ID"); }
                if (!rseq_add(&area, &slots[cpu].value, cpu, stress ? 200 : 0)) break;
                ++w->retries;
            }
        } else if (method == 1) {
            ++local_count;
        } else {
            atomic_fetch_add_explicit(&shared_count, 1, memory_order_relaxed);
        }
    }
    w->total = local_count;
    /* Workers stay alive until the stress controller has stopped targeting them. */
    pthread_barrier_wait(&ready);
    pthread_barrier_wait(&launch);
    if (method == 0 && syscall(SYS_rseq, &area, 32, RSEQ_FLAG_UNREGISTER, SIGNATURE)) fail("rseq unregister");
    return NULL;
}
static void *disturb(void *unused) {
    (void)unused;
    unsigned round = 0;
    struct timespec pause = { .tv_sec = 0, .tv_nsec = 100000 };
    while (!atomic_load_explicit(&stop_stress, memory_order_relaxed)) {
        for (int i = 0; i < nthreads; ++i) {
            pin(workers[i].thread, cpus[(i + round) % ncpu]);
            check(pthread_kill(workers[i].thread, SIGUSR1), "signal");
        }
        ++round;
        nanosleep(&pause, NULL);
    }
    return NULL;
}
static uint64_t number(const char *s, uint64_t max) {
    char *end; errno = 0;
    unsigned long long n = strtoull(s, &end, 10);
    if (errno || !*s || *end || *s == '-' || n > max) { errno = EINVAL; fail("argument"); }
    return n;
}
int main(int argc, char **argv) {
    if (argc != 6) { fprintf(stderr, "usage: counter rseq|tls|atomic threads iterations cpus stress\n"); return 2; }
    method = strcmp(argv[1], "rseq") == 0 ? 0 : strcmp(argv[1], "tls") == 0 ? 1 : strcmp(argv[1], "atomic") == 0 ? 2 : -1;
    nthreads = (int)number(argv[2], 128); iterations = number(argv[3], 1000000000);
    ncpu = (int)number(argv[4], CPU_SETSIZE); stress = (int)number(argv[5], 1);
    if (method < 0 || !nthreads || !ncpu) { errno = EINVAL; fail("argument"); }
    cpu_set_t allowed;
    if (sched_getaffinity(0, sizeof(allowed), &allowed)) fail("getaffinity");
    int found = 0;
    for (int i = 0; i < CPU_SETSIZE && found < ncpu; ++i) if (CPU_ISSET(i, &allowed)) cpus[found++] = i;
    if (found != ncpu) { errno = EINVAL; fail("insufficient allowed CPUs"); }
    struct sigaction action = { .sa_handler = signal_handler };
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGUSR1, &action, NULL)) fail("sigaction");
    check(pthread_barrier_init(&ready, NULL, nthreads + 1), "barrier");
    check(pthread_barrier_init(&launch, NULL, nthreads + 1), "barrier");
    for (int i = 0; i < nthreads; ++i) check(pthread_create(&workers[i].thread, NULL, run, &workers[i]), "create");
    pthread_barrier_wait(&ready);
    pthread_t controller;
    if (stress) check(pthread_create(&controller, NULL, disturb, NULL), "controller");
    double start_time = now();
    pthread_barrier_wait(&launch);
    pthread_barrier_wait(&ready);
    double seconds = now() - start_time;
    atomic_store(&stop_stress, 1);
    if (stress) check(pthread_join(controller, NULL), "join controller");
    pthread_barrier_wait(&launch);
    uint64_t total = 0, retries = 0;
    for (int i = 0; i < nthreads; ++i) {
        check(pthread_join(workers[i].thread, NULL), "join");
        retries += workers[i].retries;
        if (method == 1) total += workers[i].total;
    }
    if (method == 0) for (int i = 0; i < CPU_SETSIZE; ++i) total += slots[i].value;
    if (method == 2) total = atomic_load(&shared_count);
    printf("{\"method\":\"%s\",\"threads\":%d,\"iterations\":%" PRIu64 ",\"cpus\":%d,\"stress\":%d,\"total\":%" PRIu64 ",\"retries\":%" PRIu64 ",\"seconds\":%.9f,\"cpu_ids\":[", argv[1], nthreads, iterations, ncpu, stress, total, retries, seconds);
    for (int i = 0; i < ncpu; ++i) printf("%s%d", i ? "," : "", cpus[i]);
    puts("]}");
    return total != (uint64_t)nthreads * iterations;
}
