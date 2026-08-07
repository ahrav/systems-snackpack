#include <arpa/inet.h>
#include <errno.h>
#include <linux/udp.h>
#include <netinet/in.h>
#include <pthread.h>
#include <sched.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#ifndef SOL_UDP
#define SOL_UDP 17
#endif

#ifndef UDP_SEGMENT
#define UDP_SEGMENT 103
#endif

#ifndef UDP_GRO
#define UDP_GRO 104
#endif

enum {
    SEGMENT_BYTES = 1200,
    SEGMENTS_PER_BATCH = 32,
    HEADER_BYTES = 12,
    BATCH_BYTES = SEGMENT_BYTES * SEGMENTS_PER_BATCH,
};

static const uint32_t MAGIC = UINT32_C(0x4e494332);

struct wire_header {
    uint32_t magic_be;
    uint32_t round_be;
    uint16_t slot_be;
    uint16_t length_be;
};

_Static_assert(sizeof(struct wire_header) == HEADER_BYTES,
               "wire header must not contain padding");

enum send_mode {
    MODE_SCALAR,
    MODE_MMSG,
    MODE_GSO,
};

struct receiver_stats {
    uint64_t measured_receive_calls;
    uint64_t measured_datagrams;
    uint64_t verified_datagrams;
    uint64_t gro_control_messages;
    uint64_t max_gro_segments_per_receive;
    uint64_t payload_checksum;
    int observed_cpu;
    int affinity_count;
};

struct receiver_args {
    int fd;
    int cpu;
    uint32_t warmup_rounds;
    uint32_t measured_rounds;
    bool gro;
    pthread_barrier_t *barrier;
    struct receiver_stats stats;
};

static void fail_errno(const char *what)
{
    fprintf(stderr, "%s: %s\n", what, strerror(errno));
    exit(2);
}

static void fail_message(const char *what)
{
    fprintf(stderr, "%s\n", what);
    exit(2);
}

static uint64_t timespec_ns(struct timespec value)
{
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) +
           (uint64_t)value.tv_nsec;
}

static uint64_t timeval_ns(struct timeval value)
{
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) +
           (uint64_t)value.tv_usec * UINT64_C(1000);
}

static uint64_t now_ns(void)
{
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &value) != 0) {
        fail_errno("clock_gettime");
    }
    return timespec_ns(value);
}

static int affinity_count(void)
{
    cpu_set_t allowed;
    if (sched_getaffinity(0, sizeof(allowed), &allowed) != 0) {
        fail_errno("sched_getaffinity");
    }
    return CPU_COUNT(&allowed);
}

static void pin_to_cpu(int cpu)
{
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(cpu, &set);
    if (sched_setaffinity(0, sizeof(set), &set) != 0) {
        fail_errno("sched_setaffinity");
    }
    if (affinity_count() != 1 || sched_getcpu() != cpu) {
        fail_message("CPU affinity did not become the requested singleton");
    }
}

static void barrier_wait(pthread_barrier_t *barrier)
{
    const int result = pthread_barrier_wait(barrier);
    if (result != 0 && result != PTHREAD_BARRIER_SERIAL_THREAD) {
        fail_message("pthread_barrier_wait failed");
    }
}

static int read_topology_id(int cpu, const char *leaf)
{
    char path[128];
    const int written = snprintf(
        path, sizeof(path),
        "/sys/devices/system/cpu/cpu%d/topology/%s", cpu, leaf);
    if (written < 0 || (size_t)written >= sizeof(path)) {
        fail_message("CPU topology path is too long");
    }
    FILE *stream = fopen(path, "re");
    if (stream == NULL) {
        fail_errno("cannot open CPU topology entry");
    }
    int value = -1;
    if (fscanf(stream, "%d", &value) != 1 || value < 0) {
        fail_message("CPU topology entry is not a nonnegative integer");
    }
    if (fclose(stream) != 0) {
        fail_errno("fclose");
    }
    return value;
}

static void choose_cpus(int *sender_cpu, int *receiver_cpu)
{
    cpu_set_t allowed;
    if (sched_getaffinity(0, sizeof(allowed), &allowed) != 0) {
        fail_errno("sched_getaffinity");
    }

    *sender_cpu = -1;
    *receiver_cpu = -1;
    int sender_package = -1;
    int sender_core = -1;
    for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
        if (!CPU_ISSET(cpu, &allowed)) {
            continue;
        }
        if (*sender_cpu < 0) {
            *sender_cpu = cpu;
            sender_package = read_topology_id(cpu, "physical_package_id");
            sender_core = read_topology_id(cpu, "core_id");
            continue;
        }
        /* Reject SMT siblings of the sender: the experiment requires two
         * distinct physical cores, not merely two logical CPU IDs. */
        if (read_topology_id(cpu, "physical_package_id") == sender_package &&
            read_topology_id(cpu, "core_id") == sender_core) {
            continue;
        }
        *receiver_cpu = cpu;
        break;
    }
    if (*sender_cpu < 0 || *receiver_cpu < 0) {
        fail_message(
            "the experiment needs two allowed CPUs on distinct physical cores");
    }
}

static uint32_t parse_u32(const char *text, const char *name, bool allow_zero)
{
    char *end = NULL;
    errno = 0;
    const unsigned long long parsed = strtoull(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || parsed > UINT32_MAX ||
        (!allow_zero && parsed == 0)) {
        fprintf(stderr, "%s is not a valid round count\n", name);
        exit(2);
    }
    return (uint32_t)parsed;
}

static void fill_segment(unsigned char *segment, uint32_t round, uint16_t slot)
{
    const struct wire_header header = {
        .magic_be = htonl(MAGIC),
        .round_be = htonl(round),
        .slot_be = htons(slot),
        .length_be = htons(SEGMENT_BYTES),
    };
    memcpy(segment, &header, sizeof(header));
    for (size_t offset = sizeof(header); offset < SEGMENT_BYTES; ++offset) {
        segment[offset] =
            (unsigned char)((slot * 17u + offset * 29u + 3u) & 0xffu);
    }
}

static uint64_t segment_receipt(uint32_t round, uint16_t slot)
{
    return ((uint64_t)round << 32) ^ ((uint64_t)slot << 16) ^ SEGMENT_BYTES;
}

static uint64_t expected_payload_checksum(uint32_t rounds)
{
    uint64_t checksum = 0;
    for (uint32_t round = 0; round < rounds; ++round) {
        for (uint16_t slot = 0; slot < SEGMENTS_PER_BATCH; ++slot) {
            checksum += segment_receipt(round, slot);
        }
    }
    return checksum;
}

static uint16_t verify_segment(const unsigned char *segment, size_t length,
                               uint32_t expected_round, uint64_t *checksum)
{
    if (length != SEGMENT_BYTES) {
        fail_message("received datagram has the wrong length");
    }

    struct wire_header header;
    memcpy(&header, segment, sizeof(header));
    const uint32_t magic = ntohl(header.magic_be);
    const uint32_t round = ntohl(header.round_be);
    const uint16_t slot = ntohs(header.slot_be);
    const uint16_t encoded_length = ntohs(header.length_be);
    if (magic != MAGIC || round != expected_round ||
        encoded_length != SEGMENT_BYTES || slot >= SEGMENTS_PER_BATCH) {
        fail_message("received datagram header is invalid or stale");
    }
    for (size_t offset = sizeof(header); offset < SEGMENT_BYTES; ++offset) {
        const unsigned char expected =
            (unsigned char)((slot * 17u + offset * 29u + 3u) & 0xffu);
        if (segment[offset] != expected) {
            fail_message("received datagram payload is corrupt");
        }
    }
    *checksum += segment_receipt(round, slot);
    return slot;
}

static void send_ack(int fd, const struct sockaddr_in *peer, socklen_t peer_len,
                     uint32_t round)
{
    const uint32_t ack = htonl(round);
    ssize_t sent;
    do {
        sent = sendto(fd, &ack, sizeof(ack), 0,
                      (const struct sockaddr *)peer, peer_len);
    } while (sent < 0 && errno == EINTR);
    if (sent != (ssize_t)sizeof(ack)) {
        fail_errno("sendto acknowledgement");
    }
}

static void receive_normal_round(struct receiver_args *args, uint32_t round,
                                 bool measured)
{
    unsigned char buffers[SEGMENTS_PER_BATCH][SEGMENT_BYTES];
    struct iovec iov[SEGMENTS_PER_BATCH];
    struct mmsghdr messages[SEGMENTS_PER_BATCH];
    struct sockaddr_in peers[SEGMENTS_PER_BATCH];
    bool seen[SEGMENTS_PER_BATCH] = {false};
    unsigned received = 0;
    struct sockaddr_in ack_peer = {0};
    socklen_t ack_peer_len = 0;

    memset(messages, 0, sizeof(messages));
    for (unsigned i = 0; i < SEGMENTS_PER_BATCH; ++i) {
        iov[i].iov_base = buffers[i];
        iov[i].iov_len = sizeof(buffers[i]);
        messages[i].msg_hdr.msg_iov = &iov[i];
        messages[i].msg_hdr.msg_iovlen = 1;
        messages[i].msg_hdr.msg_name = &peers[i];
        messages[i].msg_hdr.msg_namelen = sizeof(peers[i]);
    }

    while (received < SEGMENTS_PER_BATCH) {
        const unsigned capacity = SEGMENTS_PER_BATCH - received;
        int count;
        do {
            count = recvmmsg(args->fd, messages, capacity, MSG_WAITFORONE, NULL);
        } while (count < 0 && errno == EINTR);
        if (count <= 0) {
            fail_errno("recvmmsg");
        }
        if (measured) {
            args->stats.measured_receive_calls++;
        }
        for (int i = 0; i < count; ++i) {
            if ((messages[i].msg_hdr.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) != 0) {
                fail_message("normal receive was truncated");
            }
            const uint16_t slot =
                verify_segment(buffers[i], messages[i].msg_len, round,
                               &args->stats.payload_checksum);
            if (seen[slot]) {
                fail_message("duplicate datagram in a batch");
            }
            seen[slot] = true;
            if (received == 0) {
                ack_peer = peers[i];
                ack_peer_len = messages[i].msg_hdr.msg_namelen;
            }
            received++;
            args->stats.verified_datagrams++;
            messages[i].msg_len = 0;
            messages[i].msg_hdr.msg_namelen = sizeof(peers[i]);
            messages[i].msg_hdr.msg_flags = 0;
        }
    }
    if (measured) {
        args->stats.measured_datagrams += received;
    }
    send_ack(args->fd, &ack_peer, ack_peer_len, round);
}

static void receive_gro_round(struct receiver_args *args, uint32_t round,
                              bool measured)
{
    unsigned char buffer[SEGMENTS_PER_BATCH * SEGMENT_BYTES];
    union {
        struct cmsghdr align;
        unsigned char bytes[CMSG_SPACE(sizeof(int))];
    } control;
    bool seen[SEGMENTS_PER_BATCH] = {false};
    unsigned received = 0;
    struct sockaddr_in ack_peer = {0};
    socklen_t ack_peer_len = 0;

    while (received < SEGMENTS_PER_BATCH) {
        memset(&control, 0, sizeof(control));
        struct iovec iov = {
            .iov_base = buffer,
            .iov_len = sizeof(buffer),
        };
        struct sockaddr_in peer = {0};
        struct msghdr message = {
            .msg_name = &peer,
            .msg_namelen = sizeof(peer),
            .msg_iov = &iov,
            .msg_iovlen = 1,
            .msg_control = control.bytes,
            .msg_controllen = sizeof(control.bytes),
        };
        ssize_t bytes;
        do {
            bytes = recvmsg(args->fd, &message, 0);
        } while (bytes < 0 && errno == EINTR);
        if (bytes <= 0) {
            fail_errno("recvmsg UDP_GRO");
        }
        if ((message.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) != 0) {
            fail_message("UDP_GRO receive was truncated");
        }

        int segment_size = 0;
        for (struct cmsghdr *cm = CMSG_FIRSTHDR(&message); cm != NULL;
             cm = CMSG_NXTHDR(&message, cm)) {
            if (cm->cmsg_level == SOL_UDP && cm->cmsg_type == UDP_GRO &&
                cm->cmsg_len >= CMSG_LEN(sizeof(int))) {
                memcpy(&segment_size, CMSG_DATA(cm), sizeof(segment_size));
                if (measured) {
                    args->stats.gro_control_messages++;
                }
            }
        }
        if (segment_size == 0) {
            segment_size = (int)bytes;
        }
        if (segment_size != SEGMENT_BYTES || bytes % segment_size != 0) {
            fail_message("UDP_GRO ancillary segment size is invalid");
        }

        const unsigned segments = (unsigned)(bytes / segment_size);
        if (received + segments > SEGMENTS_PER_BATCH) {
            fail_message("UDP_GRO delivered too many logical datagrams");
        }
        if (measured && segments > args->stats.max_gro_segments_per_receive) {
            args->stats.max_gro_segments_per_receive = segments;
        }
        for (unsigned i = 0; i < segments; ++i) {
            const uint16_t slot =
                verify_segment(buffer + i * (unsigned)segment_size,
                               (size_t)segment_size, round,
                               &args->stats.payload_checksum);
            if (seen[slot]) {
                fail_message("duplicate datagram in UDP_GRO aggregate");
            }
            seen[slot] = true;
            received++;
            args->stats.verified_datagrams++;
        }
        if (ack_peer_len == 0) {
            ack_peer = peer;
            ack_peer_len = message.msg_namelen;
        }
        if (measured) {
            args->stats.measured_receive_calls++;
        }
    }
    if (received != SEGMENTS_PER_BATCH) {
        fail_message("UDP_GRO delivered the wrong logical datagram count");
    }
    if (measured) {
        args->stats.measured_datagrams += received;
    }
    send_ack(args->fd, &ack_peer, ack_peer_len, round);
}

static void *receiver_main(void *opaque)
{
    struct receiver_args *args = opaque;
    pin_to_cpu(args->cpu);
    args->stats.affinity_count = affinity_count();
    barrier_wait(args->barrier);

    const uint32_t total = args->warmup_rounds + args->measured_rounds;
    for (uint32_t round = 0; round < total; ++round) {
        const bool measured = round >= args->warmup_rounds;
        if (args->gro) {
            receive_gro_round(args, round, measured);
        } else {
            receive_normal_round(args, round, measured);
        }
    }
    args->stats.observed_cpu = sched_getcpu();
    return NULL;
}

__attribute__((noinline, used))
static uint64_t topic26_send_scalar_batch(int fd, unsigned char *arena)
{
    uint64_t calls = 0;
    for (unsigned i = 0; i < SEGMENTS_PER_BATCH; ++i) {
        ssize_t sent;
        do {
            sent = send(fd, arena + i * SEGMENT_BYTES, SEGMENT_BYTES, 0);
            calls++;
        } while (sent < 0 && errno == EINTR);
        if (sent != SEGMENT_BYTES) {
            fail_errno("scalar send");
        }
    }
    return calls;
}

__attribute__((noinline, used))
static uint64_t topic26_send_mmsg_batch(int fd, unsigned char *arena)
{
    struct iovec iov[SEGMENTS_PER_BATCH];
    struct mmsghdr messages[SEGMENTS_PER_BATCH];
    memset(messages, 0, sizeof(messages));
    for (unsigned i = 0; i < SEGMENTS_PER_BATCH; ++i) {
        iov[i].iov_base = arena + i * SEGMENT_BYTES;
        iov[i].iov_len = SEGMENT_BYTES;
        messages[i].msg_hdr.msg_iov = &iov[i];
        messages[i].msg_hdr.msg_iovlen = 1;
    }

    uint64_t calls = 0;
    unsigned offset = 0;
    while (offset < SEGMENTS_PER_BATCH) {
        int sent;
        do {
            sent =
                sendmmsg(fd, &messages[offset], SEGMENTS_PER_BATCH - offset, 0);
            calls++;
        } while (sent < 0 && errno == EINTR);
        if (sent <= 0) {
            fail_errno("sendmmsg");
        }
        for (int i = 0; i < sent; ++i) {
            if (messages[offset + (unsigned)i].msg_len != SEGMENT_BYTES) {
                fail_message("sendmmsg reported a partial datagram");
            }
        }
        offset += (unsigned)sent;
    }
    return calls;
}

__attribute__((noinline, used))
static uint64_t topic26_send_gso_batch(int fd, unsigned char *arena)
{
    union {
        struct cmsghdr align;
        unsigned char bytes[CMSG_SPACE(sizeof(uint16_t))];
    } control = {0};
    struct iovec iov = {
        .iov_base = arena,
        .iov_len = SEGMENTS_PER_BATCH * SEGMENT_BYTES,
    };
    struct msghdr message = {
        .msg_iov = &iov,
        .msg_iovlen = 1,
        .msg_control = control.bytes,
        .msg_controllen = sizeof(control.bytes),
    };
    struct cmsghdr *cm = CMSG_FIRSTHDR(&message);
    const uint16_t segment_size = SEGMENT_BYTES;
    cm->cmsg_level = SOL_UDP;
    cm->cmsg_type = UDP_SEGMENT;
    cm->cmsg_len = CMSG_LEN(sizeof(segment_size));
    memcpy(CMSG_DATA(cm), &segment_size, sizeof(segment_size));

    ssize_t sent;
    uint64_t calls = 0;
    do {
        sent = sendmsg(fd, &message, 0);
        calls++;
    } while (sent < 0 && errno == EINTR);
    if (sent != (ssize_t)iov.iov_len) {
        fail_errno("sendmsg UDP_SEGMENT");
    }
    return calls;
}

static const char *mode_name(enum send_mode mode)
{
    switch (mode) {
    case MODE_SCALAR:
        return "scalar";
    case MODE_MMSG:
        return "sendmmsg";
    case MODE_GSO:
        return "udp_segment";
    }
    fail_message("unreachable mode");
    return "invalid";
}

static enum send_mode parse_mode(const char *name)
{
    if (strcmp(name, "scalar") == 0) {
        return MODE_SCALAR;
    }
    if (strcmp(name, "sendmmsg") == 0) {
        return MODE_MMSG;
    }
    if (strcmp(name, "udp_segment") == 0) {
        return MODE_GSO;
    }
    fail_message("mode must be scalar, sendmmsg, or udp_segment");
    return MODE_SCALAR;
}

static uint64_t send_batch(enum send_mode mode, int fd, unsigned char *arena)
{
    switch (mode) {
    case MODE_SCALAR:
        return topic26_send_scalar_batch(fd, arena);
    case MODE_MMSG:
        return topic26_send_mmsg_batch(fd, arena);
    case MODE_GSO:
        return topic26_send_gso_batch(fd, arena);
    }
    fail_message("unreachable send mode");
    return 0;
}

static void receive_ack(int fd, uint32_t round)
{
    uint32_t ack = 0;
    ssize_t received;
    do {
        received = recv(fd, &ack, sizeof(ack), 0);
    } while (received < 0 && errno == EINTR);
    if (received != (ssize_t)sizeof(ack) || ntohl(ack) != round) {
        fail_message("acknowledgement is missing or stale");
    }
}

static void socket_value(int fd, int option, int *value)
{
    socklen_t length = sizeof(*value);
    if (getsockopt(fd, SOL_SOCKET, option, value, &length) != 0) {
        fail_errno("getsockopt socket buffer");
    }
}

int main(int argc, char **argv)
{
    if (argc < 2 || argc > 5) {
        fprintf(stderr,
                "usage: %s MODE [MEASURED_ROUNDS] [WARMUP_ROUNDS] [--gro]\n",
                argv[0]);
        return 2;
    }
    const enum send_mode mode = parse_mode(argv[1]);
    const uint32_t measured_rounds =
        argc >= 3 ? parse_u32(argv[2], "MEASURED_ROUNDS", false) : 2000;
    const uint32_t warmup_rounds =
        argc >= 4 ? parse_u32(argv[3], "WARMUP_ROUNDS", true) : 200;
    const bool gro = argc == 5 && strcmp(argv[4], "--gro") == 0;
    if ((argc == 5 && !gro) || (gro && mode != MODE_GSO) ||
        warmup_rounds > UINT32_MAX - measured_rounds) {
        fail_message("invalid GRO option or total round count");
    }

    const uint64_t setup_start = now_ns();
    int sender_cpu;
    int receiver_cpu;
    choose_cpus(&sender_cpu, &receiver_cpu);
    pin_to_cpu(sender_cpu);

    const int receiver_fd = socket(AF_INET, SOCK_DGRAM | SOCK_CLOEXEC, 0);
    const int sender_fd = socket(AF_INET, SOCK_DGRAM | SOCK_CLOEXEC, 0);
    if (receiver_fd < 0 || sender_fd < 0) {
        fail_errno("socket");
    }
    if (gro) {
        const int enabled = 1;
        if (setsockopt(receiver_fd, SOL_UDP, UDP_GRO, &enabled,
                       sizeof(enabled)) != 0) {
            fail_errno("setsockopt UDP_GRO");
        }
    }

    struct sockaddr_in receiver_address = {
        .sin_family = AF_INET,
        .sin_port = 0,
        .sin_addr.s_addr = htonl(INADDR_LOOPBACK),
    };
    if (bind(receiver_fd, (struct sockaddr *)&receiver_address,
             sizeof(receiver_address)) != 0) {
        fail_errno("bind receiver");
    }
    socklen_t address_length = sizeof(receiver_address);
    if (getsockname(receiver_fd, (struct sockaddr *)&receiver_address,
                    &address_length) != 0) {
        fail_errno("getsockname receiver");
    }
    if (connect(sender_fd, (struct sockaddr *)&receiver_address,
                sizeof(receiver_address)) != 0) {
        fail_errno("connect sender");
    }

    int receive_buffer = 0;
    int send_buffer = 0;
    socket_value(receiver_fd, SO_RCVBUF, &receive_buffer);
    socket_value(sender_fd, SO_SNDBUF, &send_buffer);

    const uint32_t total_rounds = warmup_rounds + measured_rounds;
    if ((size_t)BATCH_BYTES > SIZE_MAX / (size_t)total_rounds) {
        fail_message("payload arena size overflows size_t");
    }
    const size_t arena_bytes = (size_t)total_rounds * BATCH_BYTES;
    unsigned char *arena = aligned_alloc(64, arena_bytes);
    if (arena == NULL) {
        fail_errno("aligned_alloc");
    }
    for (uint32_t round = 0; round < total_rounds; ++round) {
        unsigned char *batch = arena + (size_t)round * BATCH_BYTES;
        for (uint16_t slot = 0; slot < SEGMENTS_PER_BATCH; ++slot) {
            fill_segment(batch + (size_t)slot * SEGMENT_BYTES, round, slot);
        }
    }

    pthread_barrier_t barrier;
    if (pthread_barrier_init(&barrier, NULL, 2) != 0) {
        fail_message("pthread_barrier_init failed");
    }
    struct receiver_args receiver = {
        .fd = receiver_fd,
        .cpu = receiver_cpu,
        .warmup_rounds = warmup_rounds,
        .measured_rounds = measured_rounds,
        .gro = gro,
        .barrier = &barrier,
    };
    pthread_t thread;
    if (pthread_create(&thread, NULL, receiver_main, &receiver) != 0) {
        fail_message("pthread_create failed");
    }
    const int sender_affinity_count = affinity_count();
    barrier_wait(&barrier);
    const uint64_t setup_ns = now_ns() - setup_start;

    uint64_t measured_send_calls = 0;
    uint64_t elapsed_start = 0;
    struct rusage usage_start = {0};
    for (uint32_t round = 0; round < total_rounds; ++round) {
        if (round == warmup_rounds) {
            if (getrusage(RUSAGE_SELF, &usage_start) != 0) {
                fail_errno("getrusage start");
            }
            elapsed_start = now_ns();
        }
        unsigned char *batch = arena + (size_t)round * BATCH_BYTES;
        const uint64_t calls = send_batch(mode, sender_fd, batch);
        receive_ack(sender_fd, round);
        if (round >= warmup_rounds) {
            measured_send_calls += calls;
        }
    }
    const uint64_t elapsed_ns = now_ns() - elapsed_start;
    struct rusage usage_end;
    if (getrusage(RUSAGE_SELF, &usage_end) != 0) {
        fail_errno("getrusage end");
    }
    if (pthread_join(thread, NULL) != 0) {
        fail_message("pthread_join failed");
    }

    const int sender_observed_cpu = sched_getcpu();
    const uint64_t user_cpu_ns =
        timeval_ns(usage_end.ru_utime) - timeval_ns(usage_start.ru_utime);
    const uint64_t system_cpu_ns =
        timeval_ns(usage_end.ru_stime) - timeval_ns(usage_start.ru_stime);
    const uint64_t logical_datagrams =
        (uint64_t)measured_rounds * SEGMENTS_PER_BATCH;
    const uint64_t verified_datagrams =
        (uint64_t)total_rounds * SEGMENTS_PER_BATCH;
    const uint64_t expected_checksum =
        expected_payload_checksum(total_rounds);
    const bool payload_verified =
        receiver.stats.measured_datagrams == logical_datagrams &&
        receiver.stats.verified_datagrams == verified_datagrams &&
        receiver.stats.payload_checksum == expected_checksum;
    if (!payload_verified) {
        fail_message("payload receipt differs after the completed run");
    }

    printf(
        "{\"schema\":1,\"kind\":\"measurement\",\"status\":\"pass\","
        "\"mode\":\"%s\",\"gro_enabled\":%s,"
        "\"transport\":\"udp_ipv4_loopback\","
        "\"segment_bytes\":%d,\"segments_per_batch\":%d,"
        "\"warmup_rounds\":%u,\"measured_rounds\":%u,"
        "\"logical_datagrams\":%llu,\"logical_bytes\":%llu,"
        "\"verified_datagrams\":%llu,\"setup_ns\":%llu,"
        "\"elapsed_ns\":%llu,\"ns_per_datagram\":%.6f,"
        "\"user_cpu_ns\":%llu,\"system_cpu_ns\":%llu,"
        "\"data_send_syscalls\":%llu,\"data_receive_syscalls\":%llu,"
        "\"gro_control_messages\":%llu,"
        "\"max_gro_segments_per_receive\":%llu,"
        "\"sender_cpu\":%d,\"receiver_cpu\":%d,"
        "\"sender_observed_cpu\":%d,\"receiver_observed_cpu\":%d,"
        "\"sender_affinity_count\":%d,\"receiver_affinity_count\":%d,"
        "\"actual_receive_buffer\":%d,\"actual_send_buffer\":%d,"
        "\"payload_checksum\":%llu,\"expected_payload_checksum\":%llu,"
        "\"payload_verified\":true}\n",
        mode_name(mode), gro ? "true" : "false", SEGMENT_BYTES,
        SEGMENTS_PER_BATCH, warmup_rounds, measured_rounds,
        (unsigned long long)logical_datagrams,
        (unsigned long long)(logical_datagrams * SEGMENT_BYTES),
        (unsigned long long)verified_datagrams,
        (unsigned long long)setup_ns, (unsigned long long)elapsed_ns,
        (double)elapsed_ns / (double)logical_datagrams,
        (unsigned long long)user_cpu_ns,
        (unsigned long long)system_cpu_ns,
        (unsigned long long)measured_send_calls,
        (unsigned long long)receiver.stats.measured_receive_calls,
        (unsigned long long)receiver.stats.gro_control_messages,
        (unsigned long long)receiver.stats.max_gro_segments_per_receive,
        sender_cpu, receiver_cpu, sender_observed_cpu,
        receiver.stats.observed_cpu, sender_affinity_count,
        receiver.stats.affinity_count, receive_buffer, send_buffer,
        (unsigned long long)receiver.stats.payload_checksum,
        (unsigned long long)expected_checksum);

    free(arena);
    close(sender_fd);
    close(receiver_fd);
    pthread_barrier_destroy(&barrier);
    return 0;
}
