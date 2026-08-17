#define _GNU_SOURCE

#include <arpa/inet.h>
#include <errno.h>
#include <inttypes.h>
#include <linux/errqueue.h>
#include <netinet/in.h>
#include <poll.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#ifndef SO_ZEROCOPY
#define SO_ZEROCOPY 60
#endif

#ifndef MSG_ZEROCOPY
#define MSG_ZEROCOPY 0x4000000
#endif

#ifndef SO_EE_ORIGIN_ZEROCOPY
#define SO_EE_ORIGIN_ZEROCOPY 5
#endif

#ifndef SO_EE_CODE_ZEROCOPY_COPIED
#define SO_EE_CODE_ZEROCOPY_COPIED 1
#endif

enum {
    SEND_COUNT = 8,
    SEND_BYTES = 64 * 1024,
    TOTAL_BYTES = SEND_COUNT * SEND_BYTES,
    COMPLETION_TIMEOUT_MS = 10000,
};

struct receiver_ctx {
    int fd;
    const unsigned char *expected;
    size_t expected_len;
    size_t received;
    size_t mismatch_offset;
    int error_number;
};

static unsigned char expected_byte(size_t offset)
{
    return (unsigned char)(((offset * 131U) + 17U) & 0xffU);
}

static int64_t monotonic_ms(void)
{
    struct timespec now;

    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {
        return -1;
    }
    return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static void *receiver_main(void *opaque)
{
    struct receiver_ctx *ctx = opaque;
    unsigned char scratch[16 * 1024];

    while (ctx->received < ctx->expected_len) {
        size_t remaining = ctx->expected_len - ctx->received;
        size_t request = remaining < sizeof(scratch) ? remaining : sizeof(scratch);
        ssize_t got = recv(ctx->fd, scratch, request, 0);

        if (got < 0) {
            if (errno == EINTR) {
                continue;
            }
            ctx->error_number = errno;
            return NULL;
        }
        if (got == 0) {
            ctx->error_number = ECONNRESET;
            return NULL;
        }

        for (ssize_t i = 0; i < got; ++i) {
            size_t offset = ctx->received + (size_t)i;
            if (scratch[i] != ctx->expected[offset]) {
                ctx->mismatch_offset = offset;
                ctx->error_number = EILSEQ;
                return NULL;
            }
        }
        ctx->received += (size_t)got;
    }

    return NULL;
}

__attribute__((noinline)) static int enable_zerocopy(int fd)
{
    const int enabled = 1;

    return setsockopt(fd, SOL_SOCKET, SO_ZEROCOPY, &enabled, sizeof(enabled));
}

__attribute__((noinline)) static int send_zerocopy_chunks(
    int fd, const unsigned char *buffer, size_t page_size)
{
    for (uint32_t send_id = 0; send_id < SEND_COUNT; ++send_id) {
        const unsigned char *base = buffer + (size_t)send_id * SEND_BYTES;
        struct iovec iov = {
            .iov_base = (void *)base,
            .iov_len = SEND_BYTES,
        };
        struct msghdr msg = {
            .msg_iov = &iov,
            .msg_iovlen = 1,
        };

        if (((uintptr_t)base % page_size) != 0) {
            fprintf(stderr, "send_id=%" PRIu32 " base is not page aligned\n", send_id);
            return -1;
        }

        ssize_t sent;
        do {
            sent = sendmsg(fd, &msg, MSG_ZEROCOPY);
        } while (sent < 0 && errno == EINTR);

        if (sent < 0) {
            perror("sendmsg(MSG_ZEROCOPY)");
            return -1;
        }
        if (sent == 0) {
            fprintf(stderr, "send_id=%" PRIu32 " unexpectedly sent zero bytes\n", send_id);
            return -1;
        }
        if ((size_t)sent != SEND_BYTES) {
            fprintf(stderr,
                    "send_id=%" PRIu32 " short send: got=%zd expected=%d\n",
                    send_id, sent, SEND_BYTES);
            return -1;
        }

        printf("send_id=%" PRIu32 " bytes=%zd aligned=yes\n", send_id, sent);
    }

    return 0;
}

static int record_completion(
    const struct sock_extended_err *extended_error,
    bool covered[SEND_COUNT],
    unsigned int *notification_count,
    unsigned int *copied_notification_count)
{
    if (extended_error->ee_origin != SO_EE_ORIGIN_ZEROCOPY) {
        return 0;
    }

    uint32_t first = extended_error->ee_info;
    uint32_t last = extended_error->ee_data;
    bool copied = extended_error->ee_code == SO_EE_CODE_ZEROCOPY_COPIED;

    printf("completion=%u first=%" PRIu32 " last=%" PRIu32
           " ee_errno=%u ee_code=%u copied=%s\n",
           *notification_count, first, last, extended_error->ee_errno,
           extended_error->ee_code, copied ? "yes" : "no");

    ++*notification_count;
    if (copied) {
        ++*copied_notification_count;
    }

    if (extended_error->ee_errno != 0 || first > last || last >= SEND_COUNT) {
        fprintf(stderr, "invalid zero-copy completion range\n");
        return -1;
    }

    for (uint32_t id = first; id <= last; ++id) {
        covered[id] = true;
    }
    return 1;
}

__attribute__((noinline)) static int drain_zerocopy_completions(int fd)
{
    bool covered[SEND_COUNT] = { false };
    unsigned int covered_count = 0;
    unsigned int notification_count = 0;
    unsigned int copied_notification_count = 0;
    int64_t deadline = monotonic_ms() + COMPLETION_TIMEOUT_MS;

    while (covered_count < SEND_COUNT) {
        unsigned char payload[1];
        unsigned char control[CMSG_SPACE(sizeof(struct sock_extended_err)) +
                              CMSG_SPACE(sizeof(struct sockaddr_in))];
        struct iovec iov = {
            .iov_base = payload,
            .iov_len = sizeof(payload),
        };
        struct msghdr msg = {
            .msg_iov = &iov,
            .msg_iovlen = 1,
            .msg_control = control,
            .msg_controllen = sizeof(control),
        };

        ssize_t got = recvmsg(fd, &msg, MSG_ERRQUEUE | MSG_DONTWAIT);
        if (got < 0) {
            if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) {
                perror("recvmsg(MSG_ERRQUEUE)");
                return -1;
            }

            int64_t now = monotonic_ms();
            if (now < 0 || now >= deadline) {
                fprintf(stderr, "timed out waiting for zero-copy completions\n");
                return -1;
            }

            struct pollfd poll_fd = {
                .fd = fd,
                .events = POLLERR,
            };
            int wait_ms = (int)(deadline - now);
            if (wait_ms > 100) {
                wait_ms = 100;
            }
            int poll_result;
            do {
                poll_result = poll(&poll_fd, 1, wait_ms);
            } while (poll_result < 0 && errno == EINTR);
            if (poll_result < 0) {
                perror("poll(POLLERR)");
                return -1;
            }
            continue;
        }

        bool found_zerocopy = false;
        for (struct cmsghdr *cmsg = CMSG_FIRSTHDR(&msg); cmsg != NULL;
             cmsg = CMSG_NXTHDR(&msg, cmsg)) {
            bool is_ip_error = cmsg->cmsg_level == SOL_IP &&
                               cmsg->cmsg_type == IP_RECVERR;
            if (!is_ip_error ||
                cmsg->cmsg_len < CMSG_LEN(sizeof(struct sock_extended_err))) {
                continue;
            }

            const struct sock_extended_err *extended_error =
                (const struct sock_extended_err *)CMSG_DATA(cmsg);
            int recorded = record_completion(extended_error, covered,
                                             &notification_count,
                                             &copied_notification_count);
            if (recorded < 0) {
                return -1;
            }
            if (recorded > 0) {
                found_zerocopy = true;
            }
        }

        if (!found_zerocopy) {
            fprintf(stderr, "error-queue record lacked a zero-copy completion\n");
            return -1;
        }

        covered_count = 0;
        for (size_t id = 0; id < SEND_COUNT; ++id) {
            covered_count += covered[id] ? 1U : 0U;
        }
    }

    printf("completion_coverage=%u/%d notifications=%u copied_notifications=%u\n",
           covered_count, SEND_COUNT, notification_count,
           copied_notification_count);
    printf("copied_fallback_observed=%s\n",
           copied_notification_count > 0 ? "yes" : "no");
    return 0;
}

static int make_loopback_pair(int *client_fd, int *server_fd)
{
    int listener = -1;
    int client = -1;
    int server = -1;
    struct sockaddr_in address = {
        .sin_family = AF_INET,
        .sin_addr.s_addr = htonl(INADDR_LOOPBACK),
        .sin_port = 0,
    };
    socklen_t address_len = sizeof(address);

    listener = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (listener < 0) {
        perror("socket(listener)");
        goto fail;
    }
    if (bind(listener, (struct sockaddr *)&address, sizeof(address)) != 0) {
        perror("bind(loopback)");
        goto fail;
    }
    if (getsockname(listener, (struct sockaddr *)&address, &address_len) != 0) {
        perror("getsockname");
        goto fail;
    }
    if (listen(listener, 1) != 0) {
        perror("listen");
        goto fail;
    }

    client = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (client < 0) {
        perror("socket(client)");
        goto fail;
    }
    if (enable_zerocopy(client) != 0) {
        perror("setsockopt(SO_ZEROCOPY)");
        goto fail;
    }
    if (connect(client, (struct sockaddr *)&address, sizeof(address)) != 0) {
        perror("connect(loopback)");
        goto fail;
    }

    server = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    if (server < 0) {
        perror("accept4");
        goto fail;
    }

    close(listener);
    *client_fd = client;
    *server_fd = server;
    return 0;

fail:
    if (server >= 0) {
        close(server);
    }
    if (client >= 0) {
        close(client);
    }
    if (listener >= 0) {
        close(listener);
    }
    return -1;
}

int main(void)
{
    long page_size_long = sysconf(_SC_PAGESIZE);
    if (page_size_long <= 0) {
        perror("sysconf(_SC_PAGESIZE)");
        return EXIT_FAILURE;
    }
    size_t page_size = (size_t)page_size_long;
    if ((SEND_BYTES % page_size) != 0) {
        fprintf(stderr, "SEND_BYTES is not a multiple of the host page size\n");
        return EXIT_FAILURE;
    }

    unsigned char *buffer = NULL;
    int allocation_result = posix_memalign((void **)&buffer, page_size, TOTAL_BYTES);
    if (allocation_result != 0) {
        errno = allocation_result;
        perror("posix_memalign");
        return EXIT_FAILURE;
    }
    for (size_t offset = 0; offset < TOTAL_BYTES; ++offset) {
        buffer[offset] = expected_byte(offset);
    }

    int client_fd = -1;
    int server_fd = -1;
    if (make_loopback_pair(&client_fd, &server_fd) != 0) {
        free(buffer);
        return EXIT_FAILURE;
    }

    struct receiver_ctx receiver = {
        .fd = server_fd,
        .expected = buffer,
        .expected_len = TOTAL_BYTES,
        .mismatch_offset = SIZE_MAX,
    };
    pthread_t receiver_thread;
    int thread_result = pthread_create(&receiver_thread, NULL, receiver_main, &receiver);
    if (thread_result != 0) {
        errno = thread_result;
        perror("pthread_create");
        close(server_fd);
        close(client_fd);
        free(buffer);
        return EXIT_FAILURE;
    }

    printf("transport=IPv4_TCP_loopback page_size=%zu buffer_aligned=yes\n", page_size);
    printf("send_count=%d bytes_per_send=%d total_bytes=%d\n",
           SEND_COUNT, SEND_BYTES, TOTAL_BYTES);
    printf("measurement=correctness_only timing_reported=no\n");

    int send_result = send_zerocopy_chunks(client_fd, buffer, page_size);
    if (shutdown(client_fd, SHUT_WR) != 0) {
        perror("shutdown(SHUT_WR)");
        send_result = -1;
    }

    thread_result = pthread_join(receiver_thread, NULL);
    if (thread_result != 0) {
        errno = thread_result;
        perror("pthread_join");
        send_result = -1;
    }

    if (receiver.error_number != 0) {
        errno = receiver.error_number;
        perror("receiver verification");
        if (receiver.mismatch_offset != SIZE_MAX) {
            fprintf(stderr, "receiver mismatch offset=%zu\n", receiver.mismatch_offset);
        }
        send_result = -1;
    }
    printf("receiver_bytes=%zu/%d receiver_content=%s\n",
           receiver.received, TOTAL_BYTES,
           receiver.error_number == 0 && receiver.received == TOTAL_BYTES
               ? "verified"
               : "failed");

    int completion_result = -1;
    if (send_result == 0 && receiver.error_number == 0 &&
        receiver.received == TOTAL_BYTES) {
        completion_result = drain_zerocopy_completions(client_fd);
    }

    close(server_fd);
    close(client_fd);
    free(buffer);

    if (send_result != 0 || completion_result != 0) {
        return EXIT_FAILURE;
    }

    printf("contract_result=PASS buffer_lifetime=held_through_all_completions\n");
    return EXIT_SUCCESS;
}
