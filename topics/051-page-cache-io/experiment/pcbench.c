#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/stat.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#ifndef STATX_DIOALIGN
#define STATX_DIOALIGN 0x00002000U
#endif

enum { IO_BLOCK = 4096 };

struct io_counts {
    uint64_t rchar;
    uint64_t wchar;
    uint64_t syscr;
    uint64_t syscw;
    uint64_t read_bytes;
    uint64_t write_bytes;
};

static uint64_t clock_ns(clockid_t clock_id) {
    struct timespec value;
    if (clock_gettime(clock_id, &value) != 0) {
        perror("clock_gettime");
        exit(2);
    }
    return (uint64_t)value.tv_sec * 1000000000ULL + (uint64_t)value.tv_nsec;
}

static uint64_t monotonic_ns(void) { return clock_ns(CLOCK_MONOTONIC_RAW); }
static uint64_t realtime_ns(void) { return clock_ns(CLOCK_REALTIME); }

static void die(const char *operation) {
    perror(operation);
    exit(2);
}

static int read_io_counts(struct io_counts *result) {
    FILE *source = fopen("/proc/self/io", "r");
    char key[64];
    uint64_t value;
    if (source == NULL) return -1;
    memset(result, 0, sizeof(*result));
    while (fscanf(source, "%63[^:]: %" SCNu64 "\n", key, &value) == 2) {
        if (strcmp(key, "rchar") == 0) result->rchar = value;
        else if (strcmp(key, "wchar") == 0) result->wchar = value;
        else if (strcmp(key, "syscr") == 0) result->syscr = value;
        else if (strcmp(key, "syscw") == 0) result->syscw = value;
        else if (strcmp(key, "read_bytes") == 0) result->read_bytes = value;
        else if (strcmp(key, "write_bytes") == 0) result->write_bytes = value;
    }
    fclose(source);
    return 0;
}

static uint64_t vmstat_value(const char *wanted) {
    FILE *source = fopen("/proc/vmstat", "r");
    char key[128];
    uint64_t value;
    if (source == NULL) return UINT64_MAX;
    while (fscanf(source, "%127s %" SCNu64, key, &value) == 2) {
        if (strcmp(key, wanted) == 0) {
            fclose(source);
            return value;
        }
    }
    fclose(source);
    return UINT64_MAX;
}

static int resident_pages(int fd, size_t length, size_t *resident, size_t *pages) {
    const long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) return -1;
    const size_t count = (length + (size_t)page_size - 1) / (size_t)page_size;
    unsigned char *vector = calloc(count, 1);
    if (vector == NULL) return -1;
    void *mapping = mmap(NULL, length, PROT_NONE, MAP_SHARED, fd, 0);
    if (mapping == MAP_FAILED) {
        free(vector);
        return -1;
    }
    if (mincore(mapping, length, vector) != 0) {
        munmap(mapping, length);
        free(vector);
        return -1;
    }
    size_t total = 0;
    for (size_t index = 0; index < count; index++) {
        total += (vector[index] & 1U) != 0;
    }
    munmap(mapping, length);
    free(vector);
    *resident = total;
    *pages = count;
    return 0;
}

static int evict_clean_range(int fd, size_t length, size_t *resident, size_t *pages) {
    const int result = posix_fadvise(fd, 0, (off_t)length, POSIX_FADV_DONTNEED);
    if (result != 0) {
        errno = result;
        return -1;
    }
    return resident_pages(fd, length, resident, pages);
}

static uint64_t block_head(size_t index) {
    return 0x51a7c0de12340000ULL ^ ((uint64_t)index * 0x9e3779b97f4a7c15ULL);
}

static void fill_block(unsigned char *block, size_t index) {
    uint64_t head = block_head(index);
    for (size_t offset = 0; offset < IO_BLOCK; offset++) {
        block[offset] = (unsigned char)((head >> ((offset & 7U) * 8U)) ^
                                        (uint64_t)offset ^ (uint64_t)index);
    }
    memcpy(block, &head, sizeof(head));
    head = ~head;
    memcpy(block + IO_BLOCK - sizeof(head), &head, sizeof(head));
}

__attribute__((noinline)) static int verify_block(const unsigned char *block,
                                                   size_t index,
                                                   uint64_t *checksum) {
    uint64_t head;
    uint64_t tail;
    const uint64_t expected = block_head(index);
    memcpy(&head, block, sizeof(head));
    memcpy(&tail, block + IO_BLOCK - sizeof(tail), sizeof(tail));
    *checksum ^= head ^ tail ^ (uint64_t)index;
    return head == expected && tail == ~expected;
}

static int query_dio_alignment(const char *path,
                               unsigned *memory_alignment,
                               unsigned *offset_alignment,
                               int *reported) {
    struct statx value;
    memset(&value, 0, sizeof(value));
    *reported = 0;
    *memory_alignment = IO_BLOCK;
    *offset_alignment = IO_BLOCK;
    if (syscall(SYS_statx, AT_FDCWD, path, AT_STATX_SYNC_AS_STAT,
                STATX_DIOALIGN, &value) != 0) {
        return -1;
    }
    if ((value.stx_mask & STATX_DIOALIGN) != 0 &&
        value.stx_dio_mem_align != 0 && value.stx_dio_offset_align != 0) {
        *reported = 1;
        *memory_alignment = value.stx_dio_mem_align;
        *offset_alignment = value.stx_dio_offset_align;
    }
    return 0;
}

static void prepare_file(const char *path, size_t mebibytes) {
    const size_t length = mebibytes * 1024U * 1024U;
    const size_t blocks = length / IO_BLOCK;
    if (length == 0 || length % IO_BLOCK != 0) {
        fprintf(stderr, "file size must be a positive multiple of %d bytes\n", IO_BLOCK);
        exit(2);
    }
    unsigned char *buffer;
    if (posix_memalign((void **)&buffer, IO_BLOCK, IO_BLOCK) != 0) {
        die("posix_memalign prepare");
    }
    const int fd = open(path, O_CREAT | O_EXCL | O_RDWR, 0600);
    if (fd < 0) die("open prepare");
    const uint64_t write_start = monotonic_ns();
    for (size_t index = 0; index < blocks; index++) {
        fill_block(buffer, index);
        const ssize_t written = pwrite(fd, buffer, IO_BLOCK, (off_t)(index * IO_BLOCK));
        if (written != IO_BLOCK) die("pwrite prepare");
    }
    const uint64_t write_end = monotonic_ns();
    if (fdatasync(fd) != 0) die("fdatasync prepare");
    const uint64_t sync_end = monotonic_ns();
    size_t after_sync = 0;
    size_t after_evict = 0;
    size_t pages = 0;
    if (resident_pages(fd, length, &after_sync, &pages) != 0) die("mincore prepare");
    if (evict_clean_range(fd, length, &after_evict, &pages) != 0) die("fadvise prepare");
    printf("{\"kind\":\"prepare\",\"pid\":%ld,\"path\":\"%s\","
           "\"bytes\":%zu,\"blocks\":%zu,\"pages\":%zu,"
           "\"write_ns\":%" PRIu64 ",\"fdatasync_ns\":%" PRIu64 ","
           "\"resident_after_sync\":%zu,\"resident_after_dontneed\":%zu}\n",
           (long)getpid(), path, length, blocks, pages, write_end - write_start,
           sync_end - write_end, after_sync, after_evict);
    close(fd);
    free(buffer);
}

static void shuffle(size_t *order, size_t count, uint64_t seed) {
    uint64_t state = seed == 0 ? 1 : seed;
    for (size_t remaining = count; remaining > 1; remaining--) {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        const size_t selected = (size_t)(state % remaining);
        const size_t temporary = order[remaining - 1];
        order[remaining - 1] = order[selected];
        order[selected] = temporary;
    }
}

static void bench_file(const char *path,
                       const char *mode,
                       const char *label,
                       uint64_t seed,
                       uint64_t process_start,
                       uint64_t started_realtime) {
    const int buffered_fd = open(path, O_RDONLY);
    if (buffered_fd < 0) die("open benchmark file");
    struct stat status;
    if (fstat(buffered_fd, &status) != 0) die("fstat benchmark file");
    if (status.st_size <= 0 || status.st_size % IO_BLOCK != 0) {
        fprintf(stderr, "benchmark file size must be a positive multiple of %d\n", IO_BLOCK);
        exit(2);
    }
    const size_t length = (size_t)status.st_size;
    const size_t blocks = length / IO_BLOCK;
    size_t resident_before = 0;
    size_t resident_after = 0;
    size_t pages = 0;
    if (evict_clean_range(buffered_fd, length, &resident_before, &pages) != 0) {
        die("evict before benchmark");
    }

    const int direct = strcmp(mode, "direct_seq") == 0;
    const int random_mode = strcmp(mode, "buf_random") == 0;
    if (!direct) {
        const int advice = random_mode ? POSIX_FADV_RANDOM : POSIX_FADV_SEQUENTIAL;
        const int result = posix_fadvise(buffered_fd, 0, (off_t)length, advice);
        if (result != 0) {
            errno = result;
            die("posix_fadvise access mode");
        }
    }

    size_t *order = NULL;
    if (random_mode) {
        order = malloc(blocks * sizeof(*order));
        if (order == NULL) die("malloc order");
        for (size_t index = 0; index < blocks; index++) order[index] = index;
        shuffle(order, blocks, seed);
    }

    unsigned memory_alignment = IO_BLOCK;
    unsigned offset_alignment = IO_BLOCK;
    unsigned allocation_alignment = IO_BLOCK;
    int alignment_reported = 0;
    int direct_fd = -1;
    if (direct) {
        (void)query_dio_alignment(path, &memory_alignment, &offset_alignment,
                                  &alignment_reported);
        if (memory_alignment == 0 ||
            (memory_alignment & (memory_alignment - 1U)) != 0 ||
            offset_alignment == 0 || IO_BLOCK % offset_alignment != 0) {
            printf("{\"kind\":\"bench\",\"status\":\"unsupported\","
                   "\"pid\":%ld,\"mode\":\"%s\",\"label\":\"%s\","
                   "\"errno\":%d,\"error\":\"invalid direct-I/O alignment\","
                   "\"dio_align_reported\":%d,\"dio_mem_align\":%u,"
                   "\"dio_offset_align\":%u}\n",
                   (long)getpid(), mode, label, EINVAL, alignment_reported,
                   memory_alignment, offset_alignment);
            close(buffered_fd);
            free(order);
            return;
        }
        allocation_alignment = memory_alignment;
        if (allocation_alignment < sizeof(void *)) {
            allocation_alignment = sizeof(void *);
        }
        direct_fd = open(path, O_RDONLY | O_DIRECT);
        if (direct_fd < 0) {
            const int saved_errno = errno;
            printf("{\"kind\":\"bench\",\"status\":\"unsupported\","
                   "\"pid\":%ld,\"mode\":\"%s\",\"label\":\"%s\","
                   "\"errno\":%d,\"error\":\"%s\","
                   "\"dio_align_reported\":%d,\"dio_mem_align\":%u,"
                   "\"dio_offset_align\":%u}\n",
                   (long)getpid(), mode, label, saved_errno, strerror(saved_errno),
                   alignment_reported, memory_alignment, offset_alignment);
            close(buffered_fd);
            free(order);
            return;
        }
    }

    unsigned char *buffer;
    if (posix_memalign((void **)&buffer, allocation_alignment, IO_BLOCK) != 0) {
        die("posix_memalign benchmark");
    }
    memset(buffer, 0, IO_BLOCK);
    struct io_counts io_before;
    struct io_counts io_after;
    struct rusage usage_before;
    struct rusage usage_after;
    if (read_io_counts(&io_before) != 0) die("read /proc/self/io before");
    if (getrusage(RUSAGE_SELF, &usage_before) != 0) die("getrusage before");
    uint64_t checksum = 0;
    size_t errors = 0;
    const uint64_t measure_start = monotonic_ns();
    for (size_t index = 0; index < blocks; index++) {
        const size_t block_index = random_mode ? order[index] : index;
        const int fd = direct ? direct_fd : buffered_fd;
        const ssize_t received = pread(fd, buffer, IO_BLOCK,
                                       (off_t)(block_index * IO_BLOCK));
        if (received != IO_BLOCK) {
            if (received < 0) die("pread benchmark");
            fprintf(stderr, "short pread: %zd\n", received);
            exit(2);
        }
        if (!verify_block(buffer, block_index, &checksum)) errors++;
    }
    const uint64_t measure_end = monotonic_ns();
    if (getrusage(RUSAGE_SELF, &usage_after) != 0) die("getrusage after");
    if (read_io_counts(&io_after) != 0) die("read /proc/self/io after");
    if (resident_pages(buffered_fd, length, &resident_after, &pages) != 0) {
        die("mincore after benchmark");
    }
    printf("{\"kind\":\"bench\",\"status\":\"ok\",\"pid\":%ld,"
           "\"started_realtime_ns\":%" PRIu64 ",\"mode\":\"%s\","
           "\"label\":\"%s\",\"seed\":%" PRIu64 ",\"bytes\":%zu,"
           "\"blocks\":%zu,\"pages\":%zu,\"resident_before\":%zu,"
           "\"cold_verified\":%d,\"resident_after\":%zu,"
           "\"startup_to_measure_ns\":%" PRIu64 ","
           "\"measurement_ns\":%" PRIu64 ",\"rchar_delta\":%" PRIu64 ","
           "\"read_bytes_delta\":%" PRIu64 ",\"syscr_delta\":%" PRIu64 ","
           "\"minor_faults_delta\":%ld,\"major_faults_delta\":%ld,"
           "\"checksum\":%" PRIu64 ",\"errors\":%zu,"
           "\"dio_align_reported\":%d,\"dio_mem_align\":%u,"
           "\"dio_allocation_align\":%u,"
           "\"dio_offset_align\":%u}\n",
           (long)getpid(), started_realtime, mode, label, seed, length, blocks,
           pages, resident_before, resident_before == 0, resident_after,
           measure_start - process_start, measure_end - measure_start,
           io_after.rchar - io_before.rchar,
           io_after.read_bytes - io_before.read_bytes,
           io_after.syscr - io_before.syscr,
           usage_after.ru_minflt - usage_before.ru_minflt,
           usage_after.ru_majflt - usage_before.ru_majflt,
           checksum, errors, alignment_reported, memory_alignment,
           allocation_alignment, offset_alignment);
    if (direct_fd >= 0) close(direct_fd);
    close(buffered_fd);
    free(order);
    free(buffer);
}

static void probe_readahead(const char *path,
                            const char *mode,
                            const char *label,
                            uint64_t process_start,
                            uint64_t started_realtime) {
    const int fd = open(path, O_RDONLY);
    if (fd < 0) die("open probe file");
    struct stat status;
    if (fstat(fd, &status) != 0) die("fstat probe file");
    const size_t length = (size_t)status.st_size;
    size_t resident_before = 0;
    size_t resident_after = 0;
    size_t pages = 0;
    if (evict_clean_range(fd, length, &resident_before, &pages) != 0) {
        die("evict before probe");
    }
    const int advice = strcmp(mode, "probe_random") == 0
                           ? POSIX_FADV_RANDOM
                           : POSIX_FADV_SEQUENTIAL;
    const int advice_result = posix_fadvise(fd, 0, (off_t)length, advice);
    if (advice_result != 0) {
        errno = advice_result;
        die("fadvise probe");
    }
    unsigned char *buffer;
    if (posix_memalign((void **)&buffer, IO_BLOCK, IO_BLOCK) != 0) {
        die("posix_memalign probe");
    }
    memset(buffer, 0, IO_BLOCK);
    struct io_counts io_before;
    struct io_counts io_after;
    if (read_io_counts(&io_before) != 0) die("read /proc/self/io probe before");
    const uint64_t read_start = monotonic_ns();
    const ssize_t received = pread(fd, buffer, IO_BLOCK, 0);
    const uint64_t read_end = monotonic_ns();
    if (received != IO_BLOCK) die("pread probe");
    uint64_t checksum = 0;
    const int valid = verify_block(buffer, 0, &checksum);
    const struct timespec pause = {.tv_sec = 0, .tv_nsec = 20000000};
    nanosleep(&pause, NULL);
    if (read_io_counts(&io_after) != 0) die("read /proc/self/io probe after");
    if (resident_pages(fd, length, &resident_after, &pages) != 0) {
        die("mincore after probe");
    }
    printf("{\"kind\":\"probe\",\"status\":\"ok\",\"pid\":%ld,"
           "\"started_realtime_ns\":%" PRIu64 ",\"mode\":\"%s\","
           "\"label\":\"%s\",\"bytes_requested\":%d,\"pages\":%zu,"
           "\"resident_before\":%zu,\"cold_verified\":%d,"
           "\"resident_after_20ms\":%zu,\"startup_to_read_ns\":%" PRIu64 ","
           "\"read_ns\":%" PRIu64 ",\"rchar_delta\":%" PRIu64 ","
           "\"read_bytes_delta\":%" PRIu64 ",\"syscr_delta\":%" PRIu64 ","
           "\"checksum\":%" PRIu64 ",\"errors\":%d}\n",
           (long)getpid(), started_realtime, mode, label, IO_BLOCK, pages,
           resident_before, resident_before == 0, resident_after,
           read_start - process_start, read_end - read_start,
           io_after.rchar - io_before.rchar,
           io_after.read_bytes - io_before.read_bytes,
           io_after.syscr - io_before.syscr, checksum, valid ? 0 : 1);
    close(fd);
    free(buffer);
}

static void writecheck(const char *path,
                       size_t mebibytes,
                       uint64_t process_start,
                       uint64_t started_realtime) {
    const size_t length = mebibytes * 1024U * 1024U;
    const size_t blocks = length / IO_BLOCK;
    const int fd = open(path, O_CREAT | O_EXCL | O_RDWR, 0600);
    if (fd < 0) die("open writecheck file");
    unsigned char *buffer;
    if (posix_memalign((void **)&buffer, IO_BLOCK, IO_BLOCK) != 0) {
        die("posix_memalign writecheck");
    }
    struct io_counts io_before;
    struct io_counts io_after_write;
    struct io_counts io_after_sync;
    if (read_io_counts(&io_before) != 0) die("read /proc/self/io write before");
    const uint64_t dirty_before = vmstat_value("nr_dirty");
    const uint64_t writeback_before = vmstat_value("nr_writeback");
    const uint64_t write_start = monotonic_ns();
    for (size_t index = 0; index < blocks; index++) {
        fill_block(buffer, index);
        const ssize_t written = write(fd, buffer, IO_BLOCK);
        if (written != IO_BLOCK) die("write writecheck");
    }
    const uint64_t write_end = monotonic_ns();
    if (read_io_counts(&io_after_write) != 0) die("read /proc/self/io write after");
    size_t after_write = 0;
    size_t after_sync = 0;
    size_t after_evict = 0;
    size_t pages = 0;
    if (resident_pages(fd, length, &after_write, &pages) != 0) die("mincore write");
    const uint64_t dirty_after_write = vmstat_value("nr_dirty");
    const uint64_t writeback_after_write = vmstat_value("nr_writeback");
    if (fdatasync(fd) != 0) die("fdatasync writecheck");
    const uint64_t sync_end = monotonic_ns();
    if (read_io_counts(&io_after_sync) != 0) die("read /proc/self/io sync after");
    if (resident_pages(fd, length, &after_sync, &pages) != 0) die("mincore sync");
    const uint64_t dirty_after_sync = vmstat_value("nr_dirty");
    const uint64_t writeback_after_sync = vmstat_value("nr_writeback");
    if (evict_clean_range(fd, length, &after_evict, &pages) != 0) die("evict writecheck");
    printf("{\"kind\":\"writecheck\",\"status\":\"ok\",\"pid\":%ld,"
           "\"started_realtime_ns\":%" PRIu64 ",\"path\":\"%s\","
           "\"bytes\":%zu,\"pages\":%zu,\"startup_to_write_ns\":%" PRIu64 ","
           "\"write_ns\":%" PRIu64 ",\"fdatasync_ns\":%" PRIu64 ","
           "\"resident_after_write\":%zu,\"resident_after_fdatasync\":%zu,"
           "\"resident_after_dontneed\":%zu,\"wchar_after_write\":%" PRIu64 ","
           "\"write_bytes_after_write\":%" PRIu64 ","
           "\"write_bytes_after_fdatasync\":%" PRIu64 ","
           "\"syscw_after_write\":%" PRIu64 ",\"nr_dirty_before\":%" PRIu64 ","
           "\"nr_dirty_after_write\":%" PRIu64 ","
           "\"nr_dirty_after_fdatasync\":%" PRIu64 ","
           "\"nr_writeback_before\":%" PRIu64 ","
           "\"nr_writeback_after_write\":%" PRIu64 ","
           "\"nr_writeback_after_fdatasync\":%" PRIu64 "}\n",
           (long)getpid(), started_realtime, path, length, pages,
           write_start - process_start, write_end - write_start,
           sync_end - write_end, after_write, after_sync, after_evict,
           io_after_write.wchar - io_before.wchar,
           io_after_write.write_bytes - io_before.write_bytes,
           io_after_sync.write_bytes - io_after_write.write_bytes,
           io_after_write.syscw - io_before.syscw,
           dirty_before, dirty_after_write, dirty_after_sync,
           writeback_before, writeback_after_write, writeback_after_sync);
    close(fd);
    free(buffer);
}

static void usage(const char *program) {
    fprintf(stderr,
            "usage:\n"
            "  %s prepare FILE MIB\n"
            "  %s bench FILE buf_seq|buf_random|direct_seq LABEL SEED\n"
            "  %s probe FILE probe_seq|probe_random LABEL\n"
            "  %s writecheck FILE MIB\n",
            program, program, program, program);
}

int main(int argc, char **argv) {
    const uint64_t process_start = monotonic_ns();
    const uint64_t started_realtime = realtime_ns();
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        usage(argv[0]);
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "prepare") == 0 && argc == 4) {
        prepare_file(argv[2], (size_t)strtoull(argv[3], NULL, 10));
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "bench") == 0 && argc == 6) {
        if (strcmp(argv[3], "buf_seq") != 0 &&
            strcmp(argv[3], "buf_random") != 0 &&
            strcmp(argv[3], "direct_seq") != 0) {
            usage(argv[0]);
            return 2;
        }
        bench_file(argv[2], argv[3], argv[4], strtoull(argv[5], NULL, 10),
                   process_start, started_realtime);
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "probe") == 0 && argc == 5) {
        if (strcmp(argv[3], "probe_seq") != 0 &&
            strcmp(argv[3], "probe_random") != 0) {
            usage(argv[0]);
            return 2;
        }
        probe_readahead(argv[2], argv[3], argv[4], process_start, started_realtime);
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "writecheck") == 0 && argc == 4) {
        writecheck(argv[2], (size_t)strtoull(argv[3], NULL, 10), process_start,
                   started_realtime);
        return 0;
    }
    usage(argv[0]);
    return 2;
}
