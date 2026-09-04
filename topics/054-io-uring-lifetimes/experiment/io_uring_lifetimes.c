#define _GNU_SOURCE

#include <errno.h>
#include <linux/io_uring.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#define UD_OWNER_MAIN UINT64_C(0x1001)
#define UD_OWNER_OTHER UINT64_C(0x1002)
#define UD_DEFERRED UINT64_C(0x2001)
#define UD_TARGET UINT64_C(0x3001)
#define UD_CANCEL UINT64_C(0x3002)

struct ring {
    int fd;
    struct io_uring_params p;
    void *sq_map;
    size_t sq_map_len;
    void *cq_map;
    size_t cq_map_len;
    struct io_uring_sqe *sqes;
    size_t sqes_len;
    unsigned *sq_head;
    unsigned *sq_tail;
    unsigned *sq_mask;
    unsigned *sq_entries;
    unsigned *sq_array;
    unsigned *cq_head;
    unsigned *cq_tail;
    unsigned *cq_mask;
    struct io_uring_cqe *cqes;
};

static void ring_close(struct ring *r)
{
    if (r->sqes && r->sqes != MAP_FAILED)
        munmap(r->sqes, r->sqes_len);
    if (r->cq_map && r->cq_map != MAP_FAILED && r->cq_map != r->sq_map)
        munmap(r->cq_map, r->cq_map_len);
    if (r->sq_map && r->sq_map != MAP_FAILED)
        munmap(r->sq_map, r->sq_map_len);
    if (r->fd >= 0)
        close(r->fd);
}

static int ring_setup(struct ring *r, unsigned flags)
{
    memset(r, 0, sizeof(*r));
    r->fd = -1;
    r->p.flags = flags;
    r->fd = (int)syscall(__NR_io_uring_setup, 8U, &r->p);
    if (r->fd < 0)
        return -errno;

    size_t sq_len = r->p.sq_off.array + r->p.sq_entries * sizeof(unsigned);
    size_t cq_len = r->p.cq_off.cqes + r->p.cq_entries * sizeof(struct io_uring_cqe);

    if (r->p.features & IORING_FEAT_SINGLE_MMAP) {
        size_t both_len = sq_len > cq_len ? sq_len : cq_len;
        r->sq_map = mmap(NULL, both_len, PROT_READ | PROT_WRITE,
                         MAP_SHARED | MAP_POPULATE, r->fd, IORING_OFF_SQ_RING);
        if (r->sq_map == MAP_FAILED)
            goto fail;
        r->sq_map_len = both_len;
        r->cq_map = r->sq_map;
        r->cq_map_len = both_len;
    } else {
        r->sq_map = mmap(NULL, sq_len, PROT_READ | PROT_WRITE,
                         MAP_SHARED | MAP_POPULATE, r->fd, IORING_OFF_SQ_RING);
        if (r->sq_map == MAP_FAILED)
            goto fail;
        r->sq_map_len = sq_len;
        r->cq_map = mmap(NULL, cq_len, PROT_READ | PROT_WRITE,
                         MAP_SHARED | MAP_POPULATE, r->fd, IORING_OFF_CQ_RING);
        if (r->cq_map == MAP_FAILED)
            goto fail;
        r->cq_map_len = cq_len;
    }

    r->sqes_len = r->p.sq_entries * sizeof(struct io_uring_sqe);
    r->sqes = mmap(NULL, r->sqes_len, PROT_READ | PROT_WRITE,
                   MAP_SHARED | MAP_POPULATE, r->fd, IORING_OFF_SQES);
    if (r->sqes == MAP_FAILED)
        goto fail;

    r->sq_head = (unsigned *)((char *)r->sq_map + r->p.sq_off.head);
    r->sq_tail = (unsigned *)((char *)r->sq_map + r->p.sq_off.tail);
    r->sq_mask = (unsigned *)((char *)r->sq_map + r->p.sq_off.ring_mask);
    r->sq_entries = (unsigned *)((char *)r->sq_map + r->p.sq_off.ring_entries);
    r->sq_array = (unsigned *)((char *)r->sq_map + r->p.sq_off.array);
    r->cq_head = (unsigned *)((char *)r->cq_map + r->p.cq_off.head);
    r->cq_tail = (unsigned *)((char *)r->cq_map + r->p.cq_off.tail);
    r->cq_mask = (unsigned *)((char *)r->cq_map + r->p.cq_off.ring_mask);
    r->cqes = (struct io_uring_cqe *)((char *)r->cq_map + r->p.cq_off.cqes);
    return 0;

fail: {
        int saved = errno;
        ring_close(r);
        return -saved;
    }
}

static int ring_enter(struct ring *r, unsigned submit, unsigned wait, unsigned flags)
{
    int rc = (int)syscall(__NR_io_uring_enter, r->fd, submit, wait, flags, NULL, 0U);
    return rc < 0 ? -errno : rc;
}

static struct io_uring_sqe *ring_reserve_sqe(struct ring *r, unsigned *reserved_tail)
{
    unsigned head = __atomic_load_n(r->sq_head, __ATOMIC_ACQUIRE);
    unsigned tail = __atomic_load_n(r->sq_tail, __ATOMIC_RELAXED);
    if (tail - head >= *r->sq_entries)
        return NULL;

    unsigned index = tail & *r->sq_mask;
    struct io_uring_sqe *sqe = &r->sqes[index];
    memset(sqe, 0, sizeof(*sqe));
    *reserved_tail = tail;
    return sqe;
}

static int ring_submit_reserved(
    struct ring *r,
    unsigned reserved_tail,
    unsigned wait,
    unsigned flags)
{
    unsigned index = reserved_tail & *r->sq_mask;

    /* Publish only after every SQE field and the array index are initialized. */
    r->sq_array[index] = index;
    __atomic_store_n(r->sq_tail, reserved_tail + 1, __ATOMIC_RELEASE);
    return ring_enter(r, 1, wait, flags);
}

static unsigned ring_ready(struct ring *r)
{
    unsigned head = __atomic_load_n(r->cq_head, __ATOMIC_RELAXED);
    unsigned tail = __atomic_load_n(r->cq_tail, __ATOMIC_ACQUIRE);
    return tail - head;
}

static int ring_take_cqe(struct ring *r, struct io_uring_cqe *out)
{
    unsigned head = __atomic_load_n(r->cq_head, __ATOMIC_RELAXED);
    unsigned tail = __atomic_load_n(r->cq_tail, __ATOMIC_ACQUIRE);
    if (head == tail)
        return 0;
    *out = r->cqes[head & *r->cq_mask];
    __atomic_store_n(r->cq_head, head + 1, __ATOMIC_RELEASE);
    return 1;
}

static int ring_wait_cqe(struct ring *r, struct io_uring_cqe *out)
{
    while (!ring_take_cqe(r, out)) {
        int rc = ring_enter(r, 0, 1, IORING_ENTER_GETEVENTS);
        if (rc < 0)
            return rc;
    }
    return 0;
}

static void prep_nop(struct io_uring_sqe *sqe, uint64_t user_data)
{
    sqe->opcode = IORING_OP_NOP;
    sqe->user_data = user_data;
}

static void prep_timeout(
    struct io_uring_sqe *sqe,
    struct __kernel_timespec *duration,
    uint64_t user_data)
{
    sqe->opcode = IORING_OP_TIMEOUT;
    sqe->addr = (uintptr_t)duration;
    sqe->len = 1;
    sqe->user_data = user_data;
}

struct owner_attempt {
    struct ring *r;
    int enter_result;
};

static void *wrong_owner_submit(void *opaque)
{
    struct owner_attempt *attempt = opaque;
    unsigned tail;
    struct io_uring_sqe *sqe = ring_reserve_sqe(attempt->r, &tail);
    if (!sqe) {
        attempt->enter_result = -ENOSPC;
        return NULL;
    }
    prep_nop(sqe, UD_OWNER_OTHER);
    attempt->enter_result = ring_submit_reserved(attempt->r, tail, 0, 0);
    return NULL;
}

static int test_single_issuer(void)
{
    struct ring r;
    int rc = ring_setup(&r, IORING_SETUP_SINGLE_ISSUER);
    if (rc < 0) {
        printf("single_issuer setup=%d (%s)\n", rc, strerror(-rc));
        return rc;
    }

    unsigned tail;
    struct io_uring_sqe *sqe = ring_reserve_sqe(&r, &tail);
    if (!sqe) {
        ring_close(&r);
        return -ENOSPC;
    }
    prep_nop(sqe, UD_OWNER_MAIN);
    rc = ring_submit_reserved(&r, tail, 1, IORING_ENTER_GETEVENTS);
    struct io_uring_cqe cqe;
    if (rc >= 0)
        rc = ring_wait_cqe(&r, &cqe);
    if (rc < 0) {
        printf("single_issuer owner_submit=%d (%s)\n", rc, strerror(-rc));
        ring_close(&r);
        return rc;
    }

    struct owner_attempt attempt = {.r = &r, .enter_result = 0};
    pthread_t thread;
    int thread_error = pthread_create(&thread, NULL, wrong_owner_submit, &attempt);
    if (thread_error != 0) {
        ring_close(&r);
        return -thread_error;
    }
    pthread_join(thread, NULL);

    printf("single_issuer owner_cqe={user_data=0x%llx,res=%d} other_task_enter=%d (%s)\n",
           (unsigned long long)cqe.user_data, cqe.res, attempt.enter_result,
           attempt.enter_result < 0 ? strerror(-attempt.enter_result) : "accepted");
    ring_close(&r);
    return cqe.user_data == UD_OWNER_MAIN && cqe.res == 0 &&
                   attempt.enter_result == -EEXIST
               ? 0
               : -EPROTO;
}

static int test_deferred_progress(void)
{
    struct ring r;
    int rc = ring_setup(&r, IORING_SETUP_SINGLE_ISSUER | IORING_SETUP_DEFER_TASKRUN);
    if (rc < 0) {
        printf("defer_taskrun setup=%d (%s)\n", rc, strerror(-rc));
        return rc;
    }

    struct __kernel_timespec duration = {.tv_sec = 0, .tv_nsec = 20 * 1000 * 1000};
    unsigned tail;
    struct io_uring_sqe *sqe = ring_reserve_sqe(&r, &tail);
    if (!sqe) {
        ring_close(&r);
        return -ENOSPC;
    }
    prep_timeout(sqe, &duration, UD_DEFERRED);
    rc = ring_submit_reserved(&r, tail, 0, 0);
    if (rc < 0) {
        ring_close(&r);
        return rc;
    }

    /* The full 80 ms must elapse before sampling readiness: an
     * EINTR-interrupted sleep lets the 20 ms timeout fire during
     * ring_enter() instead, passing without proving deferred delivery.
     * Resume with the kernel-reported remainder on EINTR. */
    struct timespec pause = {.tv_sec = 0, .tv_nsec = 80 * 1000 * 1000};
    while (nanosleep(&pause, &pause) != 0) {
        if (errno != EINTR) {
            ring_close(&r);
            return -errno;
        }
    }
    unsigned before = ring_ready(&r);
    rc = ring_enter(&r, 0, 1, IORING_ENTER_GETEVENTS);
    struct io_uring_cqe cqe;
    if (rc >= 0)
        rc = ring_wait_cqe(&r, &cqe);
    if (rc < 0) {
        printf("defer_taskrun wait=%d (%s)\n", rc, strerror(-rc));
        ring_close(&r);
        return rc;
    }

    printf("defer_taskrun cqes_before_getevents=%u terminal={user_data=0x%llx,res=%d}\n",
           before, (unsigned long long)cqe.user_data, cqe.res);
    ring_close(&r);
    return before == 0 && cqe.user_data == UD_DEFERRED && cqe.res == -ETIME ? 0
                                                                            : -EPROTO;
}

static int test_cancel_completion(void)
{
    struct ring r;
    int rc = ring_setup(&r, 0);
    if (rc < 0) {
        printf("cancel setup=%d (%s)\n", rc, strerror(-rc));
        return rc;
    }

    struct __kernel_timespec duration = {.tv_sec = 5, .tv_nsec = 0};
    unsigned target_tail;
    struct io_uring_sqe *target = ring_reserve_sqe(&r, &target_tail);
    if (!target) {
        ring_close(&r);
        return -ENOSPC;
    }
    prep_timeout(target, &duration, UD_TARGET);
    rc = ring_submit_reserved(&r, target_tail, 0, 0);
    if (rc < 0) {
        ring_close(&r);
        return rc;
    }

    unsigned cancel_tail;
    struct io_uring_sqe *cancel = ring_reserve_sqe(&r, &cancel_tail);
    if (!cancel) {
        ring_close(&r);
        return -ENOSPC;
    }
    cancel->opcode = IORING_OP_ASYNC_CANCEL;
    cancel->addr = UD_TARGET;
    cancel->user_data = UD_CANCEL;
    rc = ring_submit_reserved(&r, cancel_tail, 0, 0);
    if (rc < 0) {
        ring_close(&r);
        return rc;
    }

    struct io_uring_cqe first;
    struct io_uring_cqe second;
    rc = ring_wait_cqe(&r, &first);
    if (rc >= 0)
        rc = ring_wait_cqe(&r, &second);
    if (rc < 0) {
        ring_close(&r);
        return rc;
    }

    printf("cancel terminal_1={user_data=0x%llx,res=%d} terminal_2={user_data=0x%llx,res=%d}\n",
           (unsigned long long)first.user_data, first.res,
           (unsigned long long)second.user_data, second.res);

    int target_res;
    int cancel_res;
    if (first.user_data == UD_TARGET && second.user_data == UD_CANCEL) {
        target_res = first.res;
        cancel_res = second.res;
    } else if (first.user_data == UD_CANCEL && second.user_data == UD_TARGET) {
        cancel_res = first.res;
        target_res = second.res;
    } else {
        ring_close(&r);
        return -EPROTO;
    }

    ring_close(&r);
    return target_res == -ECANCELED && cancel_res == 0 ? 0 : -EPROTO;
}

int main(void)
{
    struct ring baseline;
    int rc = ring_setup(&baseline, 0);
    if (rc < 0) {
        printf("baseline_setup=%d (%s)\n", rc, strerror(-rc));
        return 1;
    }
    printf("baseline_setup=ok sq_entries=%u cq_entries=%u features=0x%x\n",
           baseline.p.sq_entries, baseline.p.cq_entries, baseline.p.features);
    ring_close(&baseline);

    rc = test_single_issuer();
    if (rc < 0)
        return 2;
    rc = test_deferred_progress();
    if (rc < 0)
        return 3;
    rc = test_cancel_completion();
    if (rc < 0)
        return 4;
    puts("result=ok");
    return 0;
}
