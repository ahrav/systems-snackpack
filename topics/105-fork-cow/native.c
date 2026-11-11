#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static void check(int ok) { if (!ok) { perror("cow"); exit(1); } }
static uint64_t ns(void) {
    struct timespec t;
    check(clock_gettime(CLOCK_MONOTONIC, &t) == 0);
    return (uint64_t)t.tv_sec * 1000000000 + (uint64_t)t.tv_nsec;
}
static void send_byte(int fd) { char c = 'x'; check(write(fd, &c, 1) == 1); }
static void receive(int fd) { char c; check(read(fd, &c, 1) == 1 && c == 'x'); }
struct stats { long rss, pss, dirty, huge, swap; };
static struct stats sample(pid_t pid, const void *address, size_t size) {
    char path[64], line[512];
    snprintf(path, sizeof(path), "/proc/%ld/smaps", (long)pid);
    FILE *f = fopen(path, "r"); check(f != NULL);
    struct stats s = {0};
    int active = 0, found = 0;
    unsigned long lo, hi;
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "%lx-%lx", &lo, &hi) == 2) {
            active = lo == (uintptr_t)address && hi == (uintptr_t)address + size;
            found += active;
        } else if (active) {
            if (sscanf(line, "Rss: %ld kB", &s.rss) == 1) continue;
            if (sscanf(line, "Pss: %ld kB", &s.pss) == 1) continue;
            if (sscanf(line, "Private_Dirty: %ld kB", &s.dirty) == 1) continue;
            if (sscanf(line, "AnonHugePages: %ld kB", &s.huge) == 1) continue;
            if (sscanf(line, "Swap: %ld kB", &s.swap) == 1) continue;
        }
    }
    check(fclose(f) == 0); check(found == 1);
    return s;
}
static void print_stats(const char *name, struct stats s) {
    printf("\"%s\":{\"rss_kib\":%ld,\"pss_kib\":%ld,\"private_dirty_kib\":%ld,\"huge_kib\":%ld,\"swap_kib\":%ld}",
           name, s.rss, s.pss, s.dirty, s.huge, s.swap);
}
int main(int argc, char **argv) {
    check(argc == 4);
    int scattered = strcmp(argv[1], "scattered") == 0;
    check(scattered || strcmp(argv[1], "packed") == 0);
    char *end;
    unsigned long count = strtoul(argv[2], &end, 10);
    check(*end == 0 && count > 0 && count <= 65536);
    unsigned long passes = strtoul(argv[3], &end, 10);
    check(*end == 0 && passes > 0 && passes <= 100);
    long page_raw = sysconf(_SC_PAGESIZE); check(page_raw > 0);
    size_t page = (size_t)page_raw, size = count * page;
    unsigned char *reservation = mmap(NULL, size + 2 * page, PROT_NONE,
                                     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    check(reservation != MAP_FAILED);
    unsigned char *data = reservation + page;
    check(mprotect(data, size, PROT_READ | PROT_WRITE) == 0);
    check(madvise(data, size, MADV_NOHUGEPAGE) == 0);
    memset(data, 42, size);
    int to_child[2], to_parent[2];
    check(pipe(to_child) == 0 && pipe(to_parent) == 0);
    uint64_t start = ns();
    pid_t pid = fork(); check(pid >= 0);
    uint64_t fork_ns = ns() - start;
    if (pid == 0) {
        close(to_child[1]); close(to_parent[0]);
        send_byte(to_parent[1]);
        receive(to_child[0]);
        for (size_t i = 0; i < size; ++i) if (data[i] != 42) _exit(2);
        send_byte(to_parent[1]);
        receive(to_child[0]);
        _exit(0);
    }
    close(to_child[0]); close(to_parent[1]);
    receive(to_parent[0]);
    struct stats pb = sample(getpid(), data, size), cb = sample(pid, data, size);
    struct rusage before, after;
    // Resolve timing and rusage paths before the measured interval.
    check(getrusage(RUSAGE_SELF, &before) == 0); (void)ns();
    start = ns();
    volatile unsigned char *out = data;
    size_t stride = scattered ? page : 1;
    for (unsigned long pass = 0; pass < passes; ++pass)
        for (size_t i = 0; i < count; ++i) out[i * stride] = 43;
    uint64_t write_ns = ns() - start;
    check(getrusage(RUSAGE_SELF, &after) == 0);
    // Independent full-byte oracle, outside the timed interval.
    for (size_t i = 0; i < size; ++i) {
        int changed = scattered ? i % page == 0 : i < count;
        check(data[i] == (changed ? 43 : 42));
    }
    send_byte(to_child[1]); receive(to_parent[0]);
    struct stats pa = sample(getpid(), data, size), ca = sample(pid, data, size);
    send_byte(to_child[1]);
    int status; check(waitpid(pid, &status, 0) == pid);
    check(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    printf("{\"layout\":\"%s\",\"count\":%lu,\"passes\":%lu,\"page_size\":%zu,\"fork_ns\":%llu,\"write_ns\":%llu,\"minor_faults\":%ld,",
           argv[1], count, passes, page, (unsigned long long)fork_ns,
           (unsigned long long)write_ns, after.ru_minflt - before.ru_minflt);
    print_stats("parent_before", pb); printf(","); print_stats("child_before", cb); printf(",");
    print_stats("parent_after", pa); printf(","); print_stats("child_after", ca);
    puts(",\"parent_bytes_ok\":true,\"child_bytes_ok\":true}");
    check(munmap(reservation, size + 2 * page) == 0);
    return 0;
}
