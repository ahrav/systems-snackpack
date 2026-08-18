#define _GNU_SOURCE

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <netinet/in.h>
#include <sched.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/sendfile.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

struct transfer_stats {
    uint64_t input_calls;
    uint64_t output_calls;
    int pipe_capacity;
};

struct receiver_report {
    uint64_t bytes;
    uint64_t recv_calls;
    uint64_t mismatch_offset;
    unsigned int expected;
    unsigned int observed;
    int status;
    int rcvbuf;
};

static double seconds_between(const struct timespec *start,
                              const struct timespec *end) {
    return (double)(end->tv_sec - start->tv_sec) +
           (double)(end->tv_nsec - start->tv_nsec) / 1000000000.0;
}

static double timeval_seconds(const struct timeval *tv) {
    return (double)tv->tv_sec + (double)tv->tv_usec / 1000000.0;
}

static uint8_t pattern_byte(uint64_t offset) {
    uint64_t x = offset & ((1ULL << 20) - 1ULL);
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    x ^= x >> 31;
    return (uint8_t)(x >> 56);
}

static int write_all_fd(int fd, const void *buffer, size_t length) {
    const uint8_t *cursor = buffer;
    while (length > 0) {
        ssize_t written = write(fd, cursor, length);
        if (written < 0 && errno == EINTR) {
            continue;
        }
        if (written <= 0) {
            return -1;
        }
        cursor += (size_t)written;
        length -= (size_t)written;
    }
    return 0;
}

static int prepare_file(const char *path, uint64_t bytes) {
    const size_t block_size = 1U << 20;
    uint8_t *block = malloc(block_size);
    if (block == NULL) {
        perror("malloc");
        return 1;
    }
    for (size_t i = 0; i < block_size; i++) {
        block[i] = pattern_byte((uint64_t)i);
    }

    int fd = open(path, O_CREAT | O_TRUNC | O_WRONLY | O_CLOEXEC, 0600);
    if (fd < 0) {
        perror("open prepare");
        free(block);
        return 1;
    }
    uint64_t remaining = bytes;
    while (remaining > 0) {
        size_t amount = remaining < block_size ? (size_t)remaining : block_size;
        if (write_all_fd(fd, block, amount) != 0) {
            perror("write prepare");
            close(fd);
            free(block);
            return 1;
        }
        remaining -= amount;
    }
    if (fsync(fd) != 0) {
        perror("fsync prepare");
        close(fd);
        free(block);
        return 1;
    }
    if (close(fd) != 0) {
        perror("close prepare");
        free(block);
        return 1;
    }
    free(block);
    return 0;
}

static int warm_file(const char *path) {
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        perror("open warm");
        return 1;
    }
    const size_t block_size = 1U << 20;
    uint8_t *block = malloc(block_size);
    if (block == NULL) {
        perror("malloc warm");
        close(fd);
        return 1;
    }
    uint64_t bytes = 0;
    for (;;) {
        ssize_t got = read(fd, block, block_size);
        if (got < 0 && errno == EINTR) {
            continue;
        }
        if (got < 0) {
            perror("read warm");
            free(block);
            close(fd);
            return 1;
        }
        if (got == 0) {
            break;
        }
        bytes += (uint64_t)got;
    }
    free(block);
    close(fd);
    printf("warm bytes=%" PRIu64 "\n", bytes);
    return 0;
}

static int choose_cpus(int *sender_cpu, int *receiver_cpu) {
    cpu_set_t allowed;
    CPU_ZERO(&allowed);
    if (sched_getaffinity(0, sizeof(allowed), &allowed) != 0) {
        return -1;
    }
    *sender_cpu = -1;
    *receiver_cpu = -1;
    for (int cpu = 0; cpu < CPU_SETSIZE; cpu++) {
        if (!CPU_ISSET(cpu, &allowed)) {
            continue;
        }
        if (*sender_cpu < 0) {
            *sender_cpu = cpu;
        } else {
            *receiver_cpu = cpu;
            break;
        }
    }
    if (*sender_cpu < 0) {
        return -1;
    }
    if (*receiver_cpu < 0) {
        *receiver_cpu = *sender_cpu;
    }
    return 0;
}

static int pin_to_cpu(int cpu) {
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(cpu, &set);
    return sched_setaffinity(0, sizeof(set), &set);
}

static void receiver(int listener, int report_fd, uint64_t expected_bytes,
                     bool verify, size_t chunk, int receiver_cpu) {
    struct receiver_report report;
    memset(&report, 0, sizeof(report));
    report.mismatch_offset = UINT64_MAX;
    if (pin_to_cpu(receiver_cpu) != 0) {
        report.status = errno;
        (void)write_all_fd(report_fd, &report, sizeof(report));
        _exit(2);
    }

    int fd = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    if (fd < 0) {
        report.status = errno;
        (void)write_all_fd(report_fd, &report, sizeof(report));
        _exit(2);
    }
    socklen_t option_length = sizeof(report.rcvbuf);
    if (getsockopt(fd, SOL_SOCKET, SO_RCVBUF, &report.rcvbuf, &option_length) != 0) {
        report.rcvbuf = -1;
    }

    uint8_t *buffer = malloc(chunk);
    if (buffer == NULL) {
        report.status = ENOMEM;
        (void)write_all_fd(report_fd, &report, sizeof(report));
        _exit(2);
    }

    while (report.bytes < expected_bytes) {
        size_t wanted = expected_bytes - report.bytes < chunk
                            ? (size_t)(expected_bytes - report.bytes)
                            : chunk;
        ssize_t got = recv(fd, buffer, wanted, 0);
        if (got < 0 && errno == EINTR) {
            continue;
        }
        report.recv_calls++;
        if (got < 0) {
            report.status = errno;
            break;
        }
        if (got == 0) {
            report.status = EPIPE;
            break;
        }
        if (verify && report.mismatch_offset == UINT64_MAX) {
            for (ssize_t i = 0; i < got; i++) {
                uint8_t expected = pattern_byte(report.bytes + (uint64_t)i);
                if (buffer[i] != expected) {
                    report.mismatch_offset = report.bytes + (uint64_t)i;
                    report.expected = expected;
                    report.observed = buffer[i];
                    report.status = EILSEQ;
                    break;
                }
            }
        }
        report.bytes += (uint64_t)got;
        if (report.status != 0) {
            break;
        }
    }

    if (report.status == 0) {
        uint8_t extra;
        ssize_t got;
        do {
            got = recv(fd, &extra, 1, 0);
        } while (got < 0 && errno == EINTR);
        report.recv_calls++;
        if (got != 0) {
            report.status = got < 0 ? errno : EOVERFLOW;
        }
    }

    (void)write_all_fd(report_fd, &report, sizeof(report));
    free(buffer);
    close(fd);
    _exit(report.status == 0 ? 0 : 2);
}

__attribute__((noinline, noclone)) static int
transfer_buffered(int file_fd, int socket_fd, uint64_t bytes, size_t chunk,
                  struct transfer_stats *stats) {
    void *allocation = NULL;
    if (posix_memalign(&allocation, 4096, chunk) != 0) {
        errno = ENOMEM;
        return -1;
    }
    uint8_t *buffer = allocation;
    uint64_t offset = 0;
    while (offset < bytes) {
        size_t wanted = bytes - offset < chunk ? (size_t)(bytes - offset) : chunk;
        ssize_t got;
        do {
            got = pread(file_fd, buffer, wanted, (off_t)offset);
        } while (got < 0 && errno == EINTR);
        stats->input_calls++;
        if (got <= 0) {
            if (got == 0) {
                errno = EIO;
            }
            free(buffer);
            return -1;
        }
        size_t sent = 0;
        while (sent < (size_t)got) {
            ssize_t amount = send(socket_fd, buffer + sent, (size_t)got - sent,
                                  MSG_NOSIGNAL);
            if (amount < 0 && errno == EINTR) {
                continue;
            }
            stats->output_calls++;
            if (amount <= 0) {
                if (amount == 0) {
                    errno = EPIPE;
                }
                free(buffer);
                return -1;
            }
            sent += (size_t)amount;
        }
        offset += (uint64_t)got;
    }
    free(buffer);
    return 0;
}

__attribute__((noinline, noclone)) static int
transfer_sendfile(int file_fd, int socket_fd, uint64_t bytes, size_t chunk,
                  struct transfer_stats *stats) {
    off_t offset = 0;
    while ((uint64_t)offset < bytes) {
        size_t wanted = bytes - (uint64_t)offset < chunk
                            ? (size_t)(bytes - (uint64_t)offset)
                            : chunk;
        ssize_t amount = sendfile(socket_fd, file_fd, &offset, wanted);
        if (amount < 0 && errno == EINTR) {
            continue;
        }
        stats->output_calls++;
        if (amount <= 0) {
            if (amount == 0) {
                errno = EIO;
            }
            return -1;
        }
    }
    return 0;
}

__attribute__((noinline, noclone)) static int
transfer_splice(int file_fd, int socket_fd, uint64_t bytes, size_t chunk,
                struct transfer_stats *stats) {
    int pipe_fds[2];
    if (pipe2(pipe_fds, O_CLOEXEC) != 0) {
        return -1;
    }
    stats->pipe_capacity = fcntl(pipe_fds[0], F_GETPIPE_SZ);
    uint64_t remaining = bytes;
    off_t offset = 0;
    while (remaining > 0) {
        size_t wanted = remaining < chunk ? (size_t)remaining : chunk;
        ssize_t moved_in = splice(file_fd, &offset, pipe_fds[1], NULL, wanted,
                                  SPLICE_F_MOVE | SPLICE_F_MORE);
        if (moved_in < 0 && errno == EINTR) {
            continue;
        }
        stats->input_calls++;
        if (moved_in <= 0) {
            if (moved_in == 0) {
                errno = EIO;
            }
            close(pipe_fds[0]);
            close(pipe_fds[1]);
            return -1;
        }
        ssize_t pending = moved_in;
        while (pending > 0) {
            ssize_t moved_out = splice(pipe_fds[0], NULL, socket_fd, NULL,
                                       (size_t)pending,
                                       SPLICE_F_MOVE | SPLICE_F_MORE);
            if (moved_out < 0 && errno == EINTR) {
                continue;
            }
            stats->output_calls++;
            if (moved_out <= 0) {
                if (moved_out == 0) {
                    errno = EPIPE;
                }
                close(pipe_fds[0]);
                close(pipe_fds[1]);
                return -1;
            }
            pending -= moved_out;
        }
        remaining -= (uint64_t)moved_in;
    }
    close(pipe_fds[0]);
    close(pipe_fds[1]);
    return 0;
}

static int run_transfer(const char *method, const char *path, uint64_t bytes,
                        bool verify, size_t chunk,
                        const struct timespec *main_start) {
    int file_fd = open(path, O_RDONLY | O_CLOEXEC);
    if (file_fd < 0) {
        perror("open input");
        return 1;
    }
    struct stat file_status;
    if (fstat(file_fd, &file_status) != 0 || (uint64_t)file_status.st_size < bytes) {
        fprintf(stderr, "input file is shorter than requested transfer\n");
        close(file_fd);
        return 1;
    }

    int sender_cpu;
    int receiver_cpu;
    if (choose_cpus(&sender_cpu, &receiver_cpu) != 0) {
        perror("sched_getaffinity");
        close(file_fd);
        return 1;
    }

    int report_pipe[2];
    if (pipe2(report_pipe, O_CLOEXEC) != 0) {
        perror("report pipe");
        close(file_fd);
        return 1;
    }

    int listener = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (listener < 0) {
        perror("socket listener");
        return 1;
    }
    struct sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = 0;
    if (bind(listener, (struct sockaddr *)&address, sizeof(address)) != 0 ||
        listen(listener, 1) != 0) {
        perror("bind/listen");
        return 1;
    }
    socklen_t address_length = sizeof(address);
    if (getsockname(listener, (struct sockaddr *)&address, &address_length) != 0) {
        perror("getsockname");
        return 1;
    }

    pid_t child = fork();
    if (child < 0) {
        perror("fork");
        return 1;
    }
    if (child == 0) {
        close(report_pipe[0]);
        receiver(listener, report_pipe[1], bytes, verify, chunk, receiver_cpu);
    }

    close(report_pipe[1]);
    close(listener);
    if (pin_to_cpu(sender_cpu) != 0) {
        perror("pin sender");
        kill(child, SIGTERM);
        (void)waitpid(child, NULL, 0);
        return 1;
    }

    int socket_fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (socket_fd < 0) {
        perror("socket client");
        kill(child, SIGTERM);
        (void)waitpid(child, NULL, 0);
        return 1;
    }
    if (connect(socket_fd, (struct sockaddr *)&address, sizeof(address)) != 0) {
        perror("connect");
        kill(child, SIGTERM);
        (void)waitpid(child, NULL, 0);
        return 1;
    }
    int sndbuf = -1;
    socklen_t option_length = sizeof(sndbuf);
    (void)getsockopt(socket_fd, SOL_SOCKET, SO_SNDBUF, &sndbuf, &option_length);

    struct transfer_stats stats;
    memset(&stats, 0, sizeof(stats));
    stats.pipe_capacity = -1;
    struct rusage self_before;
    struct rusage self_after;
    struct rusage children_after;
    struct timespec transfer_start;
    struct timespec transfer_end;
    getrusage(RUSAGE_SELF, &self_before);
    clock_gettime(CLOCK_MONOTONIC_RAW, &transfer_start);

    int transfer_status;
    if (strcmp(method, "buffered") == 0) {
        transfer_status = transfer_buffered(file_fd, socket_fd, bytes, chunk, &stats);
    } else if (strcmp(method, "sendfile") == 0) {
        transfer_status = transfer_sendfile(file_fd, socket_fd, bytes, chunk, &stats);
    } else if (strcmp(method, "splice") == 0) {
        transfer_status = transfer_splice(file_fd, socket_fd, bytes, chunk, &stats);
    } else {
        fprintf(stderr, "unknown method: %s\n", method);
        transfer_status = -1;
        errno = EINVAL;
    }
    int transfer_errno = transfer_status == 0 ? 0 : errno;
    (void)shutdown(socket_fd, SHUT_WR);

    struct receiver_report report;
    memset(&report, 0, sizeof(report));
    ssize_t report_bytes;
    do {
        report_bytes = read(report_pipe[0], &report, sizeof(report));
    } while (report_bytes < 0 && errno == EINTR);
    int child_status = 0;
    (void)waitpid(child, &child_status, 0);
    clock_gettime(CLOCK_MONOTONIC_RAW, &transfer_end);
    getrusage(RUSAGE_SELF, &self_after);
    getrusage(RUSAGE_CHILDREN, &children_after);

    close(report_pipe[0]);
    close(socket_fd);
    close(file_fd);

    struct timespec main_end;
    clock_gettime(CLOCK_MONOTONIC_RAW, &main_end);
    double transfer_seconds = seconds_between(&transfer_start, &transfer_end);
    double setup_seconds = seconds_between(main_start, &transfer_start);
    double total_seconds = seconds_between(main_start, &main_end);
    double self_cpu = timeval_seconds(&self_after.ru_utime) +
                      timeval_seconds(&self_after.ru_stime) -
                      timeval_seconds(&self_before.ru_utime) -
                      timeval_seconds(&self_before.ru_stime);
    double child_cpu = timeval_seconds(&children_after.ru_utime) +
                       timeval_seconds(&children_after.ru_stime);
    double gib_per_second = ((double)bytes / (1024.0 * 1024.0 * 1024.0)) /
                            transfer_seconds;
    int ok = transfer_status == 0 && report_bytes == (ssize_t)sizeof(report) &&
             WIFEXITED(child_status) && WEXITSTATUS(child_status) == 0 &&
             report.status == 0 && report.bytes == bytes;

    printf("result method=%s bytes=%" PRIu64
           " verify=%d chunk=%zu transfer_sec=%.9f setup_sec=%.9f total_sec=%.9f"
           " gib_per_sec=%.6f sender_cpu_sec=%.9f receiver_cpu_sec=%.9f"
           " input_calls=%" PRIu64 " output_calls=%" PRIu64
           " recv_calls=%" PRIu64 " pipe_capacity=%d sndbuf=%d rcvbuf=%d"
           " sender_cpu=%d receiver_cpu=%d transfer_errno=%d receiver_status=%d"
           " received_bytes=%" PRIu64 " mismatch_offset=%" PRIu64
           " expected=%u observed=%u ok=%d\n",
           method, bytes, verify ? 1 : 0, chunk, transfer_seconds, setup_seconds,
           total_seconds, gib_per_second, self_cpu, child_cpu, stats.input_calls,
           stats.output_calls, report.recv_calls, stats.pipe_capacity, sndbuf,
           report.rcvbuf, sender_cpu, receiver_cpu, transfer_errno, report.status,
           report.bytes, report.mismatch_offset, report.expected, report.observed,
           ok);
    return ok ? 0 : 1;
}

static void usage(const char *program) {
    fprintf(stderr,
            "usage:\n"
            "  %s prepare FILE BYTES\n"
            "  %s warm FILE\n"
            "  %s run METHOD FILE BYTES VERIFY CHUNK\n",
            program, program, program);
}

int main(int argc, char **argv) {
    struct timespec main_start;
    clock_gettime(CLOCK_MONOTONIC_RAW, &main_start);
    signal(SIGPIPE, SIG_IGN);
    if (argc == 4 && strcmp(argv[1], "prepare") == 0) {
        return prepare_file(argv[2], strtoull(argv[3], NULL, 10));
    }
    if (argc == 3 && strcmp(argv[1], "warm") == 0) {
        return warm_file(argv[2]);
    }
    if (argc == 7 && strcmp(argv[1], "run") == 0) {
        return run_transfer(argv[2], argv[3], strtoull(argv[4], NULL, 10),
                            atoi(argv[5]) != 0,
                            (size_t)strtoull(argv[6], NULL, 10), &main_start);
    }
    usage(argv[0]);
    return 2;
}
