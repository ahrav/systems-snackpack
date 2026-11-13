#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/userfaultfd.h>
#include <poll.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>

_Static_assert(sizeof(_Atomic unsigned char) == 1, "byte-sized atomics required");
static int uffd;
static size_t pages, ps, threads, passes;
static _Atomic unsigned char *live;
static unsigned char *snapshot, *saved;
static pthread_mutex_t *locks;
static atomic_int done;
static size_t events, fault_copies, scan_copies;

static void fail(const char *where) { perror(where); exit(1); }
static void check_thread(int rc) { if (rc) { errno = rc; fail("pthread"); } }
static void protect(size_t page, size_t count, int enable) {
    struct uffdio_writeprotect wp = {
        .range = { .start = (uintptr_t)(live + page * ps), .len = count * ps },
        .mode = enable ? UFFDIO_WRITEPROTECT_MODE_WP : 0
    };
    int rc;
    do { rc = ioctl(uffd, UFFDIO_WRITEPROTECT, &wp); }
    while (rc < 0 && (errno == EINTR || errno == EAGAIN));
    if (rc) fail("UFFDIO_WRITEPROTECT");
}
static void save_page(size_t page, int fault) {
    check_thread(pthread_mutex_lock(&locks[page]));
    if (!saved[page]) {
        for (size_t j = 0; j < ps; ++j)
            snapshot[page * ps + j] = atomic_load_explicit(&live[page * ps + j], memory_order_relaxed);
        saved[page] = 1;
        if (fault) ++fault_copies; else ++scan_copies;
        protect(page, 1, 0);
    }
    check_thread(pthread_mutex_unlock(&locks[page]));
}
static void *pager(void *unused) {
    (void)unused;
    while (!atomic_load(&done)) {
        struct pollfd p = { .fd = uffd, .events = POLLIN };
        int rc = poll(&p, 1, 50);
        if (rc < 0) { if (errno == EINTR) continue; fail("poll"); }
        if (p.revents & (POLLERR | POLLHUP | POLLNVAL)) { errno = EIO; fail("poll status"); }
        if (!(p.revents & POLLIN)) continue;
        struct uffd_msg msg;
        ssize_t n = read(uffd, &msg, sizeof(msg));
        if (n < 0 && (errno == EAGAIN || errno == EINTR)) continue;
        if (n != sizeof(msg) || msg.event != UFFD_EVENT_PAGEFAULT ||
            !(msg.arg.pagefault.flags & UFFD_PAGEFAULT_FLAG_WP)) {
            errno = EPROTO; fail("WP message");
        }
        uintptr_t address = msg.arg.pagefault.address;
        if (address < (uintptr_t)live || address >= (uintptr_t)live + pages * ps) {
            errno = EFAULT; fail("fault address");
        }
        ++events;
        save_page((address - (uintptr_t)live) / ps, 1);
    }
    return NULL;
}
static void *writer(void *arg) {
    size_t id = (uintptr_t)arg;
    // Writers own disjoint pages. Atomic bytes also permit defined pager reads.
    for (size_t pass = 1; pass <= passes; ++pass)
        for (size_t page = id; page < pages; page += threads) {
            for (size_t j = 0; j < ps; ++j)
                atomic_store_explicit(&live[page * ps + j],
                    (unsigned char)(page * 17 + j * 3 + pass), memory_order_relaxed);
            sched_yield();
        }
    return NULL;
}
static size_t number(const char *s, size_t max) {
    char *end;
    errno = 0;
    unsigned long n = strtoul(s, &end, 10);
    if (errno || !*s || *end || !n || n > max) { fprintf(stderr, "invalid argument\n"); exit(2); }
    return n;
}
static void output(const char *name, const unsigned char *data, size_t length) {
    FILE *f = fopen(name, "wb");
    if (!f) fail("fopen");
    if (fwrite(data, 1, length, f) != length) fail("fwrite");
    if (fclose(f)) fail("fclose");
}
int main(int argc, char **argv) {
    if (argc != 5) { fprintf(stderr, "usage: snapshot pages writers passes pre|fault|race\n"); return 2; }
    pages = number(argv[1], 4096); threads = number(argv[2], 32); passes = number(argv[3], 255);
    const char *mode = argv[4];
    if (strcmp(mode,"pre") && strcmp(mode,"fault") && strcmp(mode,"race")) return 2;
    long size = sysconf(_SC_PAGESIZE);
    if (size <= 0) fail("page size");
    ps = (size_t)size;
    uffd = (int)syscall(SYS_userfaultfd, O_CLOEXEC | O_NONBLOCK | UFFD_USER_MODE_ONLY);
    if (uffd < 0) {
        fprintf(stderr, "userfaultfd unavailable: %s\n", strerror(errno));
        // EINVAL: the kernel predates UFFD_USER_MODE_ONLY (Linux 5.11).
        return errno == EPERM || errno == ENOSYS || errno == EACCES || errno == EINVAL ? 77 : 1;
    }
    struct uffdio_api api = { .api = UFFD_API, .features = UFFD_FEATURE_PAGEFAULT_FLAG_WP };
    if (ioctl(uffd, UFFDIO_API, &api) < 0) {
        // On a fresh descriptor, EINVAL means UFFD_API or UFFD_FEATURE_PAGEFAULT_FLAG_WP exceeds kernel support.
        if (errno != EINVAL) fail("UFFDIO_API");
        fprintf(stderr, "UFFDIO_API unavailable: %s\n", strerror(EINVAL));
        return 77;
    }
    if (!(api.features & UFFD_FEATURE_PAGEFAULT_FLAG_WP)) return 77;
    live = mmap(NULL, pages * ps, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (live == MAP_FAILED) fail("mmap");
    if (!atomic_is_lock_free(live)) { fprintf(stderr, "byte atomics require locks\n"); return 77; }
    if (madvise(live, pages * ps, MADV_NOHUGEPAGE)) fail("MADV_NOHUGEPAGE");
    snapshot = malloc(pages * ps); saved = calloc(pages, 1); locks = calloc(pages, sizeof(*locks));
    if (!snapshot || !saved || !locks) fail("allocation");
    memset(snapshot, 0, pages * ps);
    for (size_t p = 0; p < pages; ++p) {
        check_thread(pthread_mutex_init(&locks[p], NULL));
        for (size_t j = 0; j < ps; ++j)
            atomic_init(&live[p * ps + j], (unsigned char)(p * 17 + j * 3));
    }
    struct uffdio_register reg = {
        .range = { .start = (uintptr_t)live, .len = pages * ps }, .mode = UFFDIO_REGISTER_MODE_WP
    };
    if (ioctl(uffd, UFFDIO_REGISTER, &reg)) fail("UFFDIO_REGISTER");
    if (!(reg.ioctls & (1ULL << _UFFDIO_WRITEPROTECT))) return 77;
    // Epoch boundary: writers start only after protection completes over all pages.
    protect(0, pages, 1);
    pthread_t handler, workers[32];
    check_thread(pthread_create(&handler, NULL, pager, NULL));
    if (!strcmp(mode,"pre")) for (size_t p = 0; p < pages; ++p) save_page(p, 0);
    for (size_t t = 0; t < threads; ++t)
        check_thread(pthread_create(&workers[t], NULL, writer, (void *)(uintptr_t)t));
    if (!strcmp(mode,"race")) for (size_t p = pages; p-- > 0;) { save_page(p, 0); sched_yield(); }
    for (size_t t = 0; t < threads; ++t) check_thread(pthread_join(workers[t], NULL));
    for (size_t p = 0; p < pages; ++p) save_page(p, 0);
    atomic_store(&done, 1);
    check_thread(pthread_join(handler, NULL));
    output("snapshot.bin", snapshot, pages * ps);
    // Writers have joined; copying live bytes now has a stable source.
    for (size_t i = 0; i < pages * ps; ++i) snapshot[i] = atomic_load(&live[i]);
    output("live.bin", snapshot, pages * ps);
    printf("{\"pages\":%zu,\"page_size\":%zu,\"writers\":%zu,\"passes\":%zu,\"events\":%zu,\"fault_copies\":%zu,\"scan_copies\":%zu}\n",
        pages, ps, threads, passes, events, fault_copies, scan_copies);
    if (close(uffd) || munmap(live, pages * ps)) fail("cleanup");
    for (size_t p = 0; p < pages; ++p) check_thread(pthread_mutex_destroy(&locks[p]));
    free(snapshot); free(saved); free(locks);
    return 0;
}
