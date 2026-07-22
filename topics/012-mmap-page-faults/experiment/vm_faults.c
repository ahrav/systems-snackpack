#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

static void fail(const char *what) {
    fprintf(stderr, "%s: %s\n", what, strerror(errno));
    exit(2);
}

static uint64_t now_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &ts) != 0) {
        fail("clock_gettime");
    }
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

static void usage(struct rusage *u) {
    if (getrusage(RUSAGE_SELF, u) != 0) {
        fail("getrusage");
    }
}

static size_t resident_pages(void *addr, size_t len, size_t page_size) {
    const size_t pages = len / page_size;
    unsigned char *vec = calloc(pages, 1);
    if (vec == NULL) {
        fail("calloc mincore vector");
    }
    if (mincore(addr, len, vec) != 0) {
        fail("mincore");
    }
    size_t resident = 0;
    for (size_t i = 0; i < pages; ++i) {
        resident += (vec[i] & 1U) != 0;
    }
    free(vec);
    return resident;
}

__attribute__((noinline)) static uint64_t touch_read_pages(
    volatile const unsigned char *p, size_t pages, size_t page_size) {
    uint64_t sum = 0;
    for (size_t i = 0; i < pages; ++i) {
        sum += p[i * page_size];
    }
    return sum;
}

__attribute__((noinline)) static uint64_t touch_write_pages(
    volatile unsigned char *p, size_t pages, size_t page_size) {
    uint64_t sum = 0;
    for (size_t i = 0; i < pages; ++i) {
        const unsigned char value = (unsigned char)(((i * 131U) + 17U) | 1U);
        p[i * page_size] = value;
        sum += value;
    }
    return sum;
}

static void write_file(int fd, size_t len) {
    const size_t chunk_len = 1U << 20;
    unsigned char *chunk = malloc(chunk_len);
    if (chunk == NULL) {
        fail("malloc file chunk");
    }
    for (size_t i = 0; i < chunk_len; ++i) {
        chunk[i] = (unsigned char)((i * 29U + 7U) & 0xffU);
    }
    size_t done = 0;
    while (done < len) {
        const size_t want = len - done < chunk_len ? len - done : chunk_len;
        ssize_t n = write(fd, chunk, want);
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            fail("write benchmark file");
        }
        if (n == 0) {
            errno = EIO;
            fail("short write benchmark file");
        }
        done += (size_t)n;
    }
    free(chunk);
    if (fdatasync(fd) != 0) {
        fail("fdatasync benchmark file");
    }
}

static void advise_mapping(void *addr, size_t len, int advice, const char *name) {
    if (madvise(addr, len, advice) != 0) {
        fail(name);
    }
}

int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s MODE MIB RUN_ID\n", argv[0]);
        return 2;
    }

    const char *mode = argv[1];
    char *end = NULL;
    errno = 0;
    unsigned long mib = strtoul(argv[2], &end, 10);
    if (errno != 0 || end == argv[2] || *end != '\0' || mib == 0) {
        fprintf(stderr, "invalid MiB value: %s\n", argv[2]);
        return 2;
    }
    const char *run_id = argv[3];
    const long page_long = sysconf(_SC_PAGESIZE);
    if (page_long <= 0) {
        fail("sysconf(_SC_PAGESIZE)");
    }
    const size_t page_size = (size_t)page_long;
    const size_t len = (size_t)mib * 1024U * 1024U;
    if (len / (1024U * 1024U) != (size_t)mib || len % page_size != 0) {
        fprintf(stderr, "size overflow or not page aligned\n");
        return 2;
    }
    const size_t pages = len / page_size;
    const uint64_t process_start = now_ns();

    void *mapping = MAP_FAILED;
    int fd = -1;
    char path[PATH_MAX];
    const char *file_dir = getenv("VM_FAULT_FILE_DIR");
    if (file_dir == NULL || *file_dir == '\0') {
        file_dir = "/tmp";
    }
    if (snprintf(path, sizeof(path), "%s/topic12-vm-faults-XXXXXX", file_dir) >=
        (int)sizeof(path)) {
        fprintf(stderr, "benchmark file path is too long\n");
        return 2;
    }
    int fadvise_rc = 0;
    bool cold_verified = false;

    if (strcmp(mode, "anon-first") == 0 || strcmp(mode, "anon-refault") == 0) {
        mapping = mmap(NULL, len, PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (mapping == MAP_FAILED) {
            fail("mmap anonymous");
        }
        advise_mapping(mapping, len, MADV_NOHUGEPAGE, "madvise(MADV_NOHUGEPAGE)");
        if (strcmp(mode, "anon-refault") == 0) {
            (void)touch_write_pages(mapping, pages, page_size);
            advise_mapping(mapping, len, MADV_DONTNEED, "madvise(MADV_DONTNEED)");
        }
    } else if (strcmp(mode, "file-warm") == 0 || strcmp(mode, "file-cold") == 0) {
        fd = mkstemp(path);
        if (fd < 0) {
            fail("mkstemp");
        }
        if (unlink(path) != 0) {
            fail("unlink benchmark file");
        }
        write_file(fd, len);
        if (strcmp(mode, "file-cold") == 0) {
            fadvise_rc = posix_fadvise(fd, 0, (off_t)len, POSIX_FADV_DONTNEED);
            if (fadvise_rc != 0) {
                fprintf(stderr, "posix_fadvise: %s\n", strerror(fadvise_rc));
                return 3;
            }
        }
        mapping = mmap(NULL, len, PROT_READ, MAP_PRIVATE, fd, 0);
        if (mapping == MAP_FAILED) {
            fail("mmap file");
        }
        advise_mapping(mapping, len, MADV_NOHUGEPAGE, "madvise(MADV_NOHUGEPAGE)");
        advise_mapping(mapping, len, MADV_RANDOM, "madvise(MADV_RANDOM)");
    } else {
        fprintf(stderr, "unknown mode: %s\n", mode);
        return 2;
    }

    const size_t resident_before = resident_pages(mapping, len, page_size);
    if (strcmp(mode, "file-cold") == 0) {
        cold_verified = resident_before == 0;
    }

    struct rusage before;
    struct rusage after;
    usage(&before);
    const uint64_t touch_start = now_ns();
    uint64_t checksum;
    if (strcmp(mode, "anon-first") == 0) {
        checksum = touch_write_pages(mapping, pages, page_size);
    } else {
        checksum = touch_read_pages(mapping, pages, page_size);
    }
    const uint64_t touch_end = now_ns();
    usage(&after);
    const size_t resident_after = resident_pages(mapping, len, page_size);

    if (strcmp(mode, "anon-refault") == 0 && checksum != 0) {
        fprintf(stderr, "MADV_DONTNEED refault checksum was not zero: %" PRIu64 "\n", checksum);
        return 4;
    }

    printf("%s,%s,%lu,%zu,%zu,%" PRIu64 ",%" PRIu64 ",%ld,%ld,%zu,%zu,%" PRIu64 ",%d,%d\n",
           run_id, mode, mib, page_size, pages,
           touch_start - process_start, touch_end - touch_start,
           after.ru_minflt - before.ru_minflt,
           after.ru_majflt - before.ru_majflt,
           resident_before, resident_after, checksum,
           fadvise_rc, cold_verified ? 1 : 0);

    if (munmap(mapping, len) != 0) {
        fail("munmap");
    }
    if (fd >= 0) {
        if (close(fd) != 0) {
            fail("close");
        }
    }
    return 0;
}
