#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/aio_abi.h>
#include <sched.h>
#include <stdarg.h>
#include <stdbool.h>
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

/* The receipt requires direct-I/O alignment evidence from Linux 6.1 headers. */
#ifndef STATX_DIOALIGN
#error "Topic 53 requires Linux UAPI headers 6.1 or newer for STATX_DIOALIGN"
#endif

enum {
    BLOCK_BYTES = 4096,
    PREP_CHUNK_BYTES = 256 * 1024,
    MAX_DEPTH = 64,
    EXIT_UNSUPPORTED = 77,
};

#define WORDS_PER_BLOCK (BLOCK_BYTES / sizeof(uint64_t))

struct slot {
    struct iocb control;
    void *buffer;
    uint64_t operation;
    bool in_flight;
};

struct loop_result {
    uint64_t checksum;
    uint64_t verified_reads;
    size_t peak_outstanding;
};

static struct timespec program_start;

static void fail(const char *format, ...)
{
    va_list arguments;

    va_start(arguments, format);
    vfprintf(stderr, format, arguments);
    va_end(arguments);
    fputc('\n', stderr);
    exit(EXIT_FAILURE);
}

static void fail_errno(const char *operation)
{
    int saved = errno;
    fail("%s: %s", operation, strerror(saved));
}

static int unsupported(const char *format, ...)
{
    va_list arguments;

    va_start(arguments, format);
    vfprintf(stderr, format, arguments);
    va_end(arguments);
    fputc('\n', stderr);
    return EXIT_UNSUPPORTED;
}

static uint64_t parse_u64(const char *text, const char *name)
{
    char *end = NULL;
    unsigned long long value;

    if (text[0] == '-')
        fail("%s must be nonnegative", name);
    errno = 0;
    value = strtoull(text, &end, 0);
    if (errno != 0 || end == text || *end != '\0')
        fail("invalid %s: %s", name, text);
    return (uint64_t)value;
}

static bool is_power_of_two(uint64_t value)
{
    return value != 0 && (value & (value - 1)) == 0;
}

static bool valid_label(const char *label)
{
    const unsigned char *cursor = (const unsigned char *)label;

    if (*cursor == '\0')
        return false;
    for (; *cursor != '\0'; ++cursor) {
        if (!(('a' <= *cursor && *cursor <= 'z') ||
              ('A' <= *cursor && *cursor <= 'Z') ||
              ('0' <= *cursor && *cursor <= '9') ||
              *cursor == '.' || *cursor == '_' || *cursor == '-'))
            return false;
    }
    return true;
}

static uint64_t mix64(uint64_t value)
{
    value += UINT64_C(0x9e3779b97f4a7c15);
    value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}

static uint64_t expected_word(uint64_t block, uint64_t word)
{
    uint64_t value = mix64(block ^ (word * UINT64_C(0xd6e8feb86659fd93)));

    /* Keep every word nonzero so sparse-zero shortcuts cannot satisfy checks. */
    return value == 0 ? UINT64_C(0x6a09e667f3bcc909) : value;
}

static void fill_block(uint64_t *buffer, uint64_t block)
{
    uint64_t word;

    for (word = 0; word < WORDS_PER_BLOCK; ++word)
        buffer[word] = expected_word(block, word);
}

static void verify_full_block(const uint64_t *buffer, uint64_t block)
{
    uint64_t word;

    for (word = 0; word < WORDS_PER_BLOCK; ++word) {
        uint64_t expected = expected_word(block, word);
        if (buffer[word] != expected) {
            fail("data mismatch: block=%" PRIu64 " word=%" PRIu64
                 " expected=%" PRIu64 " actual=%" PRIu64,
                 block, word, expected, buffer[word]);
        }
    }
}

static uint64_t verify_sample(const uint64_t *buffer, uint64_t block)
{
    static const size_t indexes[] = {
        0,
        WORDS_PER_BLOCK / 2,
        WORDS_PER_BLOCK - 1,
    };
    uint64_t checksum = mix64(block);
    size_t index;

    for (index = 0; index < sizeof(indexes) / sizeof(indexes[0]); ++index) {
        size_t word = indexes[index];
        uint64_t expected = expected_word(block, word);
        if (buffer[word] != expected) {
            fail("timed data mismatch: block=%" PRIu64 " word=%zu"
                 " expected=%" PRIu64 " actual=%" PRIu64,
                 block, word, expected, buffer[word]);
        }
        checksum ^= expected;
    }
    return checksum;
}

static struct timespec timestamp(void)
{
    struct timespec value;

    if (clock_gettime(CLOCK_MONOTONIC_RAW, &value) != 0)
        fail_errno("clock_gettime");
    return value;
}

static uint64_t elapsed_ns(struct timespec start, struct timespec end)
{
    time_t seconds = end.tv_sec - start.tv_sec;
    long nanoseconds = end.tv_nsec - start.tv_nsec;

    if (nanoseconds < 0) {
        --seconds;
        nanoseconds += 1000000000L;
    }
    if (seconds < 0)
        fail("monotonic clock moved backward");
    return (uint64_t)seconds * UINT64_C(1000000000) +
           (uint64_t)nanoseconds;
}

static void *aligned_buffer(size_t alignment, size_t bytes)
{
    void *buffer = NULL;
    int result = posix_memalign(&buffer, alignment, bytes);

    if (result != 0) {
        errno = result;
        fail_errno("posix_memalign");
    }
    return buffer;
}

static void pwrite_exact(int fd, const void *buffer, size_t length, off_t offset)
{
    size_t done = 0;

    while (done < length) {
        ssize_t result = pwrite(fd, (const char *)buffer + done,
                                length - done, offset + (off_t)done);
        if (result < 0 && errno == EINTR)
            continue;
        if (result < 0)
            fail_errno("pwrite");
        if (result == 0)
            fail("pwrite returned zero");
        done += (size_t)result;
    }
}

static void pread_exact(int fd, void *buffer, size_t length, off_t offset)
{
    size_t done = 0;

    while (done < length) {
        ssize_t result = pread(fd, (char *)buffer + done,
                               length - done, offset + (off_t)done);
        if (result < 0 && errno == EINTR)
            continue;
        if (result < 0)
            fail_errno("pread");
        if (result == 0)
            fail("unexpected end of file");
        done += (size_t)result;
    }
}

static uint64_t file_blocks(int fd, off_t *file_size)
{
    struct stat status;
    uint64_t blocks;

    if (fstat(fd, &status) != 0)
        fail_errno("fstat");
    if (!S_ISREG(status.st_mode))
        fail("data path is not a regular file");
    if (status.st_size <= 0 || status.st_size % BLOCK_BYTES != 0)
        fail("file size must be a positive multiple of %u", BLOCK_BYTES);
    blocks = (uint64_t)status.st_size / BLOCK_BYTES;
    if (!is_power_of_two(blocks))
        fail("file must contain a power-of-two number of 4 KiB blocks");
    *file_size = status.st_size;
    return blocks;
}

static uint64_t process_read_bytes(void)
{
    FILE *input = fopen("/proc/self/io", "r");
    char *line = NULL;
    size_t capacity = 0;
    uint64_t value = UINT64_MAX;

    if (input == NULL)
        fail_errno("open /proc/self/io");
    while (getline(&line, &capacity, input) >= 0) {
        if (sscanf(line, "read_bytes: %" SCNu64, &value) == 1)
            break;
    }
    free(line);
    if (fclose(input) != 0)
        fail_errno("close /proc/self/io");
    if (value == UINT64_MAX)
        fail("read_bytes missing from /proc/self/io");
    return value;
}

static unsigned process_thread_count(void)
{
    FILE *input = fopen("/proc/self/status", "r");
    char *line = NULL;
    size_t capacity = 0;
    unsigned threads = 0;

    if (input == NULL)
        fail_errno("open /proc/self/status");
    while (getline(&line, &capacity, input) >= 0) {
        if (sscanf(line, "Threads: %u", &threads) == 1)
            break;
    }
    free(line);
    if (fclose(input) != 0)
        fail_errno("close /proc/self/status");
    if (threads == 0)
        fail("Threads missing from /proc/self/status");
    return threads;
}

static size_t resident_pages(int fd, off_t file_size, size_t *total_pages)
{
    long page_size = sysconf(_SC_PAGESIZE);
    void *mapping;
    unsigned char *vector;
    size_t pages;
    size_t resident = 0;
    size_t page;

    if (page_size <= 0)
        fail("invalid page size");
    if ((uintmax_t)file_size > SIZE_MAX)
        fail("file is too large for this process");
    pages = ((size_t)file_size + (size_t)page_size - 1) /
            (size_t)page_size;
    mapping = mmap(NULL, (size_t)file_size, PROT_READ, MAP_SHARED, fd, 0);
    if (mapping == MAP_FAILED)
        fail_errno("mmap");
    vector = calloc(pages, 1);
    if (vector == NULL)
        fail_errno("calloc mincore vector");
    if (mincore(mapping, (size_t)file_size, vector) != 0)
        fail_errno("mincore");
    for (page = 0; page < pages; ++page)
        resident += (vector[page] & 1U) != 0;
    free(vector);
    if (munmap(mapping, (size_t)file_size) != 0)
        fail_errno("munmap");
    *total_pages = pages;
    return resident;
}

static uint64_t block_for_operation(uint64_t operation,
                                    uint64_t blocks,
                                    uint64_t seed)
{
    return (operation * UINT64_C(0xd1342543de82ef95) + seed) &
           (blocks - 1);
}

static void initialize_file(const char *path, uint64_t mebibytes)
{
    uint64_t bytes;
    uint64_t blocks;
    uint64_t first_block;
    uint64_t blocks_per_chunk = PREP_CHUNK_BYTES / BLOCK_BYTES;
    uint64_t *buffer;
    int fd;
    struct timespec start;
    struct timespec end;

    if (mebibytes == 0 ||
        mebibytes > (uint64_t)INT64_MAX / (UINT64_C(1024) * 1024))
        fail("invalid file size");
    bytes = mebibytes * UINT64_C(1024) * 1024;
    if (bytes % PREP_CHUNK_BYTES != 0)
        fail("size must be a multiple of %u bytes", PREP_CHUNK_BYTES);
    blocks = bytes / BLOCK_BYTES;
    if (!is_power_of_two(blocks))
        fail("size must produce a power-of-two number of 4 KiB blocks");

    fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0)
        fail_errno("create data file");
    buffer = aligned_buffer(BLOCK_BYTES, PREP_CHUNK_BYTES);
    start = timestamp();
    for (first_block = 0; first_block < blocks;
         first_block += blocks_per_chunk) {
        uint64_t local;
        for (local = 0; local < blocks_per_chunk; ++local) {
            fill_block(buffer + local * WORDS_PER_BLOCK,
                       first_block + local);
        }
        pwrite_exact(fd, buffer, PREP_CHUNK_BYTES,
                     (off_t)(first_block * BLOCK_BYTES));
    }
    if (fdatasync(fd) != 0)
        fail_errno("fdatasync");
    end = timestamp();
    free(buffer);
    if (close(fd) != 0)
        fail_errno("close data file");

    printf("{\"schema\":\"topic53-probe.v1\",\"kind\":\"init\","
           "\"status\":\"ok\",\"bytes\":%" PRIu64
           ",\"blocks\":%" PRIu64 ",\"elapsed_ns\":%" PRIu64 "}\n",
           bytes, blocks, elapsed_ns(start, end));
}

static void verify_or_warm(const char *path, const char *kind)
{
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    off_t file_size;
    uint64_t blocks;
    uint64_t block;
    uint64_t before;
    uint64_t after;
    uint64_t *buffer;
    struct timespec start;
    struct timespec end;

    if (fd < 0)
        fail_errno("open data file");
    blocks = file_blocks(fd, &file_size);
    buffer = aligned_buffer(BLOCK_BYTES, BLOCK_BYTES);
    before = process_read_bytes();
    start = timestamp();
    for (block = 0; block < blocks; ++block) {
        pread_exact(fd, buffer, BLOCK_BYTES,
                    (off_t)(block * BLOCK_BYTES));
        verify_full_block(buffer, block);
    }
    end = timestamp();
    after = process_read_bytes();
    if (after < before)
        fail("read_bytes moved backward");
    free(buffer);
    if (close(fd) != 0)
        fail_errno("close data file");

    printf("{\"schema\":\"topic53-probe.v1\",\"kind\":\"%s\","
           "\"status\":\"ok\",\"bytes\":%jd,\"blocks\":%" PRIu64
           ",\"elapsed_ns\":%" PRIu64 ",\"read_bytes_delta\":%" PRIu64
           ",\"verified_reads\":%" PRIu64 "}\n",
           kind, (intmax_t)file_size, blocks, elapsed_ns(start, end),
           after - before, blocks);
}

__attribute__((noinline, used))
uint64_t cached_read_loop(int fd,
                          uint64_t blocks,
                          uint64_t operations,
                          uint64_t seed,
                          void *buffer)
{
    uint64_t operation;
    uint64_t checksum = 0;

    for (operation = 0; operation < operations; ++operation) {
        uint64_t block = block_for_operation(operation, blocks, seed);
        ssize_t result;

        do {
            result = pread(fd, buffer, BLOCK_BYTES,
                           (off_t)(block * BLOCK_BYTES));
        } while (result < 0 && errno == EINTR);
        if (result < 0)
            fail_errno("timed pread");
        if (result != BLOCK_BYTES)
            fail("timed pread returned %zd bytes", result);
        checksum ^= verify_sample(buffer, block);
    }
    return checksum;
}

static long kernel_io_setup(unsigned events, aio_context_t *context)
{
    return syscall(SYS_io_setup, events, context);
}

static long kernel_io_destroy(aio_context_t context)
{
    return syscall(SYS_io_destroy, context);
}

static long kernel_io_submit(aio_context_t context,
                             long count,
                             struct iocb **requests)
{
    return syscall(SYS_io_submit, context, count, requests);
}

static long kernel_io_getevents(aio_context_t context,
                                long minimum,
                                long maximum,
                                struct io_event *events)
{
    return syscall(SYS_io_getevents, context, minimum, maximum, events, NULL);
}

static void prepare_request(struct slot *slot,
                            size_t slot_index,
                            int fd,
                            uint64_t blocks,
                            uint64_t operation,
                            uint64_t seed)
{
    uint64_t block = block_for_operation(operation, blocks, seed);

    if (slot->in_flight)
        fail("attempted to reuse an in-flight slot");
    memset(&slot->control, 0, sizeof(slot->control));
    slot->operation = operation;
    slot->control.aio_data = (uint64_t)slot_index;
    slot->control.aio_lio_opcode = IOCB_CMD_PREAD;
    slot->control.aio_fildes = (uint32_t)fd;
    slot->control.aio_buf = (uint64_t)(uintptr_t)slot->buffer;
    slot->control.aio_nbytes = BLOCK_BYTES;
    slot->control.aio_offset = (int64_t)(block * BLOCK_BYTES);
}

static void submit_all(aio_context_t context,
                       struct iocb **requests,
                       size_t count)
{
    size_t submitted = 0;
    unsigned retries = 0;

    while (submitted < count) {
        long result = kernel_io_submit(context, (long)(count - submitted),
                                       requests + submitted);
        if (result > 0) {
            submitted += (size_t)result;
            retries = 0;
            continue;
        }
        if (result < 0 && errno == EINTR)
            continue;
        if (result < 0 && errno == EAGAIN && retries++ < 1000000U) {
            sched_yield();
            continue;
        }
        if (result < 0)
            fail_errno("io_submit");
        fail("io_submit made no progress");
    }
}

__attribute__((noinline, used))
struct loop_result direct_aio_loop(aio_context_t context,
                                   int fd,
                                   struct slot *slots,
                                   size_t depth,
                                   uint64_t blocks,
                                   uint64_t operations,
                                   uint64_t seed,
                                   struct iocb **batch,
                                   struct io_event *events)
{
    struct loop_result result = {0, 0, 0};
    uint64_t next = 0;
    uint64_t completed = 0;
    size_t outstanding;
    size_t initial = depth;
    size_t slot_index;

    if (operations < depth)
        initial = (size_t)operations;
    for (slot_index = 0; slot_index < initial; ++slot_index) {
        prepare_request(&slots[slot_index], slot_index, fd, blocks, next++, seed);
        slots[slot_index].in_flight = true;
        batch[slot_index] = &slots[slot_index].control;
    }
    submit_all(context, batch, initial);
    outstanding = initial;
    result.peak_outstanding = initial;

    while (completed < operations) {
        long count;
        size_t resubmit = 0;
        long index;

        do {
            count = kernel_io_getevents(context, 1, (long)depth, events);
        } while (count < 0 && errno == EINTR);
        if (count < 0)
            fail_errno("io_getevents");
        if (count == 0)
            fail("io_getevents returned no events");
        if ((size_t)count > outstanding)
            fail("completion count exceeds outstanding requests");

        for (index = 0; index < count; ++index) {
            struct io_event *event = &events[index];
            size_t slot_number = (size_t)event->data;
            struct slot *slot;
            uint64_t block;

            if (slot_number >= depth)
                fail("completion returned an unknown slot");
            slot = &slots[slot_number];
            if (!slot->in_flight)
                fail("completion returned an idle slot");
            if (event->obj != (uint64_t)(uintptr_t)&slot->control)
                fail("completion object does not match its slot");
            if (event->res < 0)
                fail("asynchronous read failed: %s",
                     strerror((int)-event->res));
            if (event->res != BLOCK_BYTES || event->res2 != 0) {
                fail("asynchronous read returned res=%" PRId64
                     " res2=%" PRId64,
                     (int64_t)event->res, (int64_t)event->res2);
            }

            block = block_for_operation(slot->operation, blocks, seed);
            result.checksum ^= verify_sample(slot->buffer, block);
            ++completed;
            ++result.verified_reads;
            slot->in_flight = false;
            --outstanding;

            if (next < operations) {
                prepare_request(slot, slot_number, fd, blocks, next++, seed);
                slot->in_flight = true;
                batch[resubmit++] = &slot->control;
            }
        }
        if (resubmit != 0) {
            submit_all(context, batch, resubmit);
            outstanding += resubmit;
            if (outstanding > result.peak_outstanding)
                result.peak_outstanding = outstanding;
        }
    }
    if (outstanding != 0 || next != operations)
        fail("asynchronous loop ended with incomplete accounting");
    return result;
}

static int direct_alignment(int fd,
                            size_t *allocation_alignment,
                            uint32_t *memory_alignment,
                            uint32_t *offset_alignment)
{
    struct statx status;
    long result;

    memset(&status, 0, sizeof(status));
    result = syscall(SYS_statx, fd, "", AT_EMPTY_PATH | AT_STATX_DONT_SYNC,
                     STATX_DIOALIGN, &status);
    if (result != 0)
        return unsupported("statx(STATX_DIOALIGN) failed: %s", strerror(errno));
    if ((status.stx_mask & STATX_DIOALIGN) == 0 ||
        status.stx_dio_mem_align == 0 || status.stx_dio_offset_align == 0) {
        return unsupported("filesystem did not report STATX_DIOALIGN");
    }
    *memory_alignment = status.stx_dio_mem_align;
    *offset_alignment = status.stx_dio_offset_align;
    *allocation_alignment = *memory_alignment;
    if (*allocation_alignment < sizeof(void *))
        *allocation_alignment = sizeof(void *);
    if (!is_power_of_two(*allocation_alignment) ||
        *allocation_alignment % sizeof(void *) != 0 ||
        BLOCK_BYTES % *offset_alignment != 0) {
        return unsupported("4 KiB direct I/O violates reported alignment: mem=%" PRIu32
                           " offset=%" PRIu32,
                           *memory_alignment, *offset_alignment);
    }
    return EXIT_SUCCESS;
}

static int run_cached(const char *path,
                      uint64_t operations,
                      uint64_t seed,
                      const char *label)
{
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    off_t file_size;
    uint64_t blocks;
    size_t total_pages;
    size_t before_resident;
    size_t after_resident;
    void *buffer;
    uint64_t bytes_before;
    uint64_t bytes_after;
    uint64_t duration;
    uint64_t checksum;
    unsigned threads_before;
    unsigned threads_after;
    struct rusage usage_before;
    struct rusage usage_after;
    struct timespec start;
    struct timespec end;
    double seconds;

    if (fd < 0)
        fail_errno("open cached file");
    blocks = file_blocks(fd, &file_size);
    if (operations > blocks)
        fail("operations must not exceed the file's unique block count");
    before_resident = resident_pages(fd, file_size, &total_pages);
    if (before_resident != total_pages) {
        close(fd);
        return unsupported("cached file is not fully resident: %zu/%zu pages",
                           before_resident, total_pages);
    }
    buffer = aligned_buffer(64, BLOCK_BYTES);
    threads_before = process_thread_count();
    if (threads_before != 1)
        fail("cached process has %u userspace threads before timing",
             threads_before);
    if (getrusage(RUSAGE_SELF, &usage_before) != 0)
        fail_errno("getrusage before");
    bytes_before = process_read_bytes();
    start = timestamp();
    checksum = cached_read_loop(fd, blocks, operations, seed, buffer);
    end = timestamp();
    bytes_after = process_read_bytes();
    if (getrusage(RUSAGE_SELF, &usage_after) != 0)
        fail_errno("getrusage after");
    threads_after = process_thread_count();
    after_resident = resident_pages(fd, file_size, &total_pages);
    if (bytes_after < bytes_before)
        fail("read_bytes moved backward");
    duration = elapsed_ns(start, end);
    if (duration == 0)
        fail("cached measurement duration is zero");
    seconds = (double)duration / 1e9;

    printf("{\"schema\":\"topic53-probe.v1\",\"kind\":\"bench\","
           "\"status\":\"ok\",\"pid\":%jd,\"tid\":%jd,"
           "\"threads_before\":%u,\"threads_after\":%u,"
           "\"mode\":\"cached\",\"label\":\"%s\","
           "\"seed\":%" PRIu64 ",\"depth\":1,\"total_ops\":%" PRIu64
           ",\"bytes\":%" PRIu64 ",\"blocks\":%" PRIu64
           ",\"startup_to_measure_ns\":%" PRIu64
           ",\"setup_ns\":0,\"elapsed_ns\":%" PRIu64
           ",\"iops\":%.6f,\"mib_s\":%.6f,"
           "\"read_bytes_delta\":%" PRIu64
           ",\"verified_reads\":%" PRIu64
           ",\"errors\":0,\"checksum\":%" PRIu64
           ",\"peak_outstanding\":1,"
           "\"resident_before\":%zu,\"resident_after\":%zu,"
           "\"total_pages\":%zu,\"dioalign_known\":0,"
           "\"dio_mem_align\":0,\"dio_offset_align\":0,"
           "\"dio_allocation_align\":0,\"nvcsw\":%ld,\"nivcsw\":%ld}\n",
           (intmax_t)getpid(), (intmax_t)syscall(SYS_gettid), threads_before,
           threads_after, label, seed, operations, operations * BLOCK_BYTES,
           blocks, elapsed_ns(program_start, start), duration,
           (double)operations / seconds,
           ((double)operations * BLOCK_BYTES) / seconds / (1024.0 * 1024.0),
           bytes_after - bytes_before, operations, checksum, before_resident,
           after_resident, total_pages,
           usage_after.ru_nvcsw - usage_before.ru_nvcsw,
           usage_after.ru_nivcsw - usage_before.ru_nivcsw);

    free(buffer);
    if (close(fd) != 0)
        fail_errno("close cached file");
    if (threads_after != 1 || after_resident != total_pages ||
        bytes_after != bytes_before)
        return EXIT_FAILURE;
    return EXIT_SUCCESS;
}

static int run_direct(const char *path,
                      uint64_t operations,
                      size_t depth,
                      uint64_t seed,
                      const char *label)
{
    int fd = open(path, O_RDONLY | O_DIRECT | O_CLOEXEC);
    off_t file_size;
    uint64_t blocks;
    uint32_t memory_alignment = 0;
    uint32_t offset_alignment = 0;
    size_t allocation_alignment = 0;
    struct slot *slots;
    struct iocb **batch;
    struct io_event *events;
    aio_context_t context = 0;
    size_t slot;
    unsigned threads_before;
    unsigned threads_after;
    uint64_t bytes_before;
    uint64_t bytes_after;
    uint64_t duration;
    struct rusage usage_before;
    struct rusage usage_after;
    struct timespec setup_start;
    struct timespec setup_end;
    struct timespec start;
    struct timespec end;
    struct loop_result loop;
    double seconds;
    int alignment_result;

    if (fd < 0) {
        if (errno == EINVAL || errno == EOPNOTSUPP || errno == ENOSYS)
            return unsupported("O_DIRECT unavailable: %s", strerror(errno));
        fail_errno("open direct file");
    }
    blocks = file_blocks(fd, &file_size);
    if (operations > blocks)
        fail("operations must not exceed the file's unique block count");
    alignment_result = direct_alignment(fd, &allocation_alignment,
                                        &memory_alignment, &offset_alignment);
    if (alignment_result != EXIT_SUCCESS) {
        close(fd);
        return alignment_result;
    }

    setup_start = timestamp();
    slots = calloc(depth, sizeof(*slots));
    batch = calloc(depth, sizeof(*batch));
    events = calloc(depth, sizeof(*events));
    if (slots == NULL || batch == NULL || events == NULL)
        fail_errno("allocate asynchronous state");
    for (slot = 0; slot < depth; ++slot)
        slots[slot].buffer = aligned_buffer(allocation_alignment, BLOCK_BYTES);
    if (kernel_io_setup((unsigned)depth, &context) != 0) {
        if (errno == EAGAIN || errno == ENOSYS || errno == EINVAL)
            return unsupported("native Linux AIO unavailable: %s",
                               strerror(errno));
        fail_errno("io_setup");
    }
    setup_end = timestamp();

    threads_before = process_thread_count();
    if (threads_before != 1)
        fail("direct process has %u userspace threads before timing",
             threads_before);
    if (getrusage(RUSAGE_SELF, &usage_before) != 0)
        fail_errno("getrusage before");
    bytes_before = process_read_bytes();
    start = timestamp();
    loop = direct_aio_loop(context, fd, slots, depth, blocks, operations,
                           seed, batch, events);
    end = timestamp();
    bytes_after = process_read_bytes();
    if (getrusage(RUSAGE_SELF, &usage_after) != 0)
        fail_errno("getrusage after");
    threads_after = process_thread_count();
    if (bytes_after < bytes_before)
        fail("read_bytes moved backward");
    duration = elapsed_ns(start, end);
    if (duration == 0)
        fail("direct measurement duration is zero");
    seconds = (double)duration / 1e9;

    printf("{\"schema\":\"topic53-probe.v1\",\"kind\":\"bench\","
           "\"status\":\"ok\",\"pid\":%jd,\"tid\":%jd,"
           "\"threads_before\":%u,\"threads_after\":%u,"
           "\"mode\":\"direct\",\"label\":\"%s\","
           "\"seed\":%" PRIu64 ",\"depth\":%zu,"
           "\"total_ops\":%" PRIu64 ",\"bytes\":%" PRIu64
           ",\"blocks\":%" PRIu64
           ",\"startup_to_measure_ns\":%" PRIu64
           ",\"setup_ns\":%" PRIu64 ",\"elapsed_ns\":%" PRIu64
           ",\"iops\":%.6f,\"mib_s\":%.6f,"
           "\"read_bytes_delta\":%" PRIu64
           ",\"verified_reads\":%" PRIu64
           ",\"errors\":0,\"checksum\":%" PRIu64
           ",\"peak_outstanding\":%zu,"
           "\"resident_before\":0,\"resident_after\":0,"
           "\"total_pages\":0,\"dioalign_known\":1,"
           "\"dio_mem_align\":%" PRIu32
           ",\"dio_offset_align\":%" PRIu32
           ",\"dio_allocation_align\":%zu,\"nvcsw\":%ld,\"nivcsw\":%ld}\n",
           (intmax_t)getpid(), (intmax_t)syscall(SYS_gettid), threads_before,
           threads_after, label, seed, depth, operations,
           operations * BLOCK_BYTES, blocks, elapsed_ns(program_start, start),
           elapsed_ns(setup_start, setup_end), duration,
           (double)operations / seconds,
           ((double)operations * BLOCK_BYTES) / seconds / (1024.0 * 1024.0),
           bytes_after - bytes_before, loop.verified_reads, loop.checksum,
           loop.peak_outstanding, memory_alignment, offset_alignment,
           allocation_alignment,
           usage_after.ru_nvcsw - usage_before.ru_nvcsw,
           usage_after.ru_nivcsw - usage_before.ru_nivcsw);

    if (kernel_io_destroy(context) != 0)
        fail_errno("io_destroy");
    for (slot = 0; slot < depth; ++slot)
        free(slots[slot].buffer);
    free(events);
    free(batch);
    free(slots);
    if (close(fd) != 0)
        fail_errno("close direct file");
    if (threads_after != 1 || loop.verified_reads != operations ||
        loop.peak_outstanding != depth)
        return EXIT_FAILURE;
    return EXIT_SUCCESS;
}

static void usage(const char *program)
{
    fprintf(stderr,
            "usage:\n"
            "  %s init FILE SIZE_MIB\n"
            "  %s verify FILE\n"
            "  %s warm FILE\n"
            "  %s run FILE cached OPS 1 SEED LABEL\n"
            "  %s run FILE direct OPS DEPTH SEED LABEL\n",
            program, program, program, program, program);
}

int main(int argc, char **argv)
{
    program_start = timestamp();

    if (argc == 4 && strcmp(argv[1], "init") == 0) {
        initialize_file(argv[2], parse_u64(argv[3], "size MiB"));
        return EXIT_SUCCESS;
    }
    if (argc == 3 && strcmp(argv[1], "verify") == 0) {
        verify_or_warm(argv[2], "verify");
        return EXIT_SUCCESS;
    }
    if (argc == 3 && strcmp(argv[1], "warm") == 0) {
        verify_or_warm(argv[2], "warm");
        return EXIT_SUCCESS;
    }
    if (argc == 8 && strcmp(argv[1], "run") == 0) {
        const char *path = argv[2];
        const char *mode = argv[3];
        uint64_t operations = parse_u64(argv[4], "operations");
        uint64_t depth_value = parse_u64(argv[5], "depth");
        uint64_t seed = parse_u64(argv[6], "seed");
        const char *label = argv[7];

        if (operations == 0 || operations > UINT64_MAX / BLOCK_BYTES ||
            depth_value == 0 || depth_value > MAX_DEPTH ||
            operations < depth_value)
            fail("invalid operation count or depth");
        if (!valid_label(label))
            fail("label must contain only letters, digits, '.', '_', or '-'");
        if (strcmp(mode, "cached") == 0) {
            if (depth_value != 1)
                fail("cached mode requires depth 1");
            return run_cached(path, operations, seed, label);
        }
        if (strcmp(mode, "direct") == 0)
            return run_direct(path, operations, (size_t)depth_value,
                              seed, label);
        fail("unknown mode: %s", mode);
    }

    usage(argv[0]);
    return EXIT_FAILURE;
}
