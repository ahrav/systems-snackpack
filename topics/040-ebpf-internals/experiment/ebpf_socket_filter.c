#define _GNU_SOURCE

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/bpf.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef SO_ATTACH_BPF
#define SO_ATTACH_BPF 50
#endif

#define RAW_INSN(CODE, DST, SRC, OFF, IMM)                                    \
    ((struct bpf_insn){                                                       \
        .code = (CODE), .dst_reg = (DST), .src_reg = (SRC), .off = (OFF),    \
        .imm = (IMM),                                                         \
    })
#define MOV64_IMM(DST, IMM)                                                    \
    RAW_INSN(BPF_ALU64 | BPF_MOV | BPF_K, (DST), 0, 0, (IMM))
#define MOV64_REG(DST, SRC)                                                    \
    RAW_INSN(BPF_ALU64 | BPF_MOV | BPF_X, (DST), (SRC), 0, 0)
#define LDX_MEM(SIZE, DST, SRC, OFF)                                           \
    RAW_INSN(BPF_LDX | BPF_MEM | (SIZE), (DST), (SRC), (OFF), 0)
#define JA(OFF) RAW_INSN(BPF_JMP | BPF_JA, 0, 0, (OFF), 0)
#define EXIT_INSN() RAW_INSN(BPF_JMP | BPF_EXIT, 0, 0, 0, 0)

static int sys_bpf(enum bpf_cmd command, union bpf_attr *attr, unsigned int size) {
    return (int)syscall(__NR_bpf, command, attr, size);
}

static int load_socket_filter(const char *name, const struct bpf_insn *insns,
                              size_t insn_count, char *log, size_t log_size) {
    static const char license[] = "GPL";
    union bpf_attr attr;
    memset(&attr, 0, sizeof(attr));
    memset(log, 0, log_size);
    attr.prog_type = BPF_PROG_TYPE_SOCKET_FILTER;
    attr.insn_cnt = (uint32_t)insn_count;
    attr.insns = (uint64_t)(uintptr_t)insns;
    attr.license = (uint64_t)(uintptr_t)license;
    attr.log_buf = (uint64_t)(uintptr_t)log;
    attr.log_size = (uint32_t)log_size;
    attr.log_level = 1;
    snprintf((char *)attr.prog_name, BPF_OBJ_NAME_LEN, "%s", name);
    return sys_bpf(BPF_PROG_LOAD, &attr, sizeof(attr));
}

static void print_log(const char *label, const char *log) {
    printf("%s_verifier_log_begin\n", label);
    if (log[0] == '\0') {
        printf("<empty>\n");
    } else {
        fputs(log, stdout);
        if (log[strlen(log) - 1] != '\n') {
            putchar('\n');
        }
    }
    printf("%s_verifier_log_end\n", label);
}

static void print_submitted_insns(const char *label,
                                  const struct bpf_insn *insns,
                                  size_t insn_count) {
    printf("%s_submitted_insns_begin\n", label);
    for (size_t i = 0; i < insn_count; ++i) {
        printf("index=%zu code=0x%02x dst=r%u src=r%u off=%d imm=%d\n", i,
               insns[i].code, insns[i].dst_reg, insns[i].src_reg,
               insns[i].off, insns[i].imm);
    }
    printf("%s_submitted_insns_end\n", label);
}

static int write_blob(const char *output_dir, const char *label,
                      const char *kind, const void *data, size_t length) {
    char path[512];
    int n = snprintf(path, sizeof(path), "%s/%s.%s.bin", output_dir, label, kind);
    if (n < 0 || (size_t)n >= sizeof(path)) {
        errno = ENAMETOOLONG;
        return -1;
    }
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    if (fd < 0) {
        return -1;
    }
    const uint8_t *cursor = data;
    size_t remaining = length;
    while (remaining > 0) {
        ssize_t written = write(fd, cursor, remaining);
        if (written < 0 && errno == EINTR) {
            continue;
        }
        if (written <= 0) {
            int saved = errno;
            close(fd);
            errno = saved ? saved : EIO;
            return -1;
        }
        cursor += written;
        remaining -= (size_t)written;
    }
    if (close(fd) != 0) {
        return -1;
    }
    printf("%s_%s_file=%s bytes=%zu\n", label, kind, path, length);
    return 0;
}

static void print_hex(const char *label, const char *kind, const uint8_t *bytes,
                      size_t length) {
    printf("%s_%s_hex=", label, kind);
    for (size_t i = 0; i < length; ++i) {
        printf("%02x", bytes[i]);
    }
    putchar('\n');
}

static int inspect_program(int fd, const char *label, const char *output_dir) {
    struct bpf_prog_info initial;
    union bpf_attr attr;
    memset(&initial, 0, sizeof(initial));
    memset(&attr, 0, sizeof(attr));
    attr.info.bpf_fd = (uint32_t)fd;
    attr.info.info_len = sizeof(initial);
    attr.info.info = (uint64_t)(uintptr_t)&initial;
    if (sys_bpf(BPF_OBJ_GET_INFO_BY_FD, &attr, sizeof(attr)) != 0) {
        printf("%s_info_error=%d:%s\n", label, errno, strerror(errno));
        return -1;
    }

    printf("%s_info_initial=id:%u type:%u xlated_len:%u jited_len:%u "
           "verified_insns:%u run_cnt:%" PRIu64 " run_time_ns:%" PRIu64 "\n",
           label, initial.id, initial.type, initial.xlated_prog_len,
           initial.jited_prog_len, initial.verified_insns,
           (uint64_t)initial.run_cnt, (uint64_t)initial.run_time_ns);

    uint8_t *xlated = calloc(initial.xlated_prog_len ? initial.xlated_prog_len : 1, 1);
    uint8_t *jited = calloc(initial.jited_prog_len ? initial.jited_prog_len : 1, 1);
    if (xlated == NULL || jited == NULL) {
        perror("calloc program info");
        free(xlated);
        free(jited);
        return -1;
    }

    struct bpf_prog_info info;
    memset(&info, 0, sizeof(info));
    info.xlated_prog_len = initial.xlated_prog_len;
    info.xlated_prog_insns = (uint64_t)(uintptr_t)xlated;
    info.jited_prog_len = initial.jited_prog_len;
    info.jited_prog_insns = (uint64_t)(uintptr_t)jited;
    memset(&attr, 0, sizeof(attr));
    attr.info.bpf_fd = (uint32_t)fd;
    attr.info.info_len = sizeof(info);
    attr.info.info = (uint64_t)(uintptr_t)&info;
    if (sys_bpf(BPF_OBJ_GET_INFO_BY_FD, &attr, sizeof(attr)) != 0) {
        printf("%s_info_bytes_error=%d:%s\n", label, errno, strerror(errno));
        free(xlated);
        free(jited);
        return -1;
    }

    printf("%s_xlated_insns_begin\n", label);
    for (uint32_t i = 0; i + sizeof(struct bpf_insn) <= info.xlated_prog_len;
         i += sizeof(struct bpf_insn)) {
        struct bpf_insn insn;
        memcpy(&insn, xlated + i, sizeof(insn));
        printf("index=%u code=0x%02x dst=r%u src=r%u off=%d imm=%d\n",
               i / (uint32_t)sizeof(struct bpf_insn), insn.code, insn.dst_reg,
               insn.src_reg, insn.off, insn.imm);
    }
    printf("%s_xlated_insns_end\n", label);
    print_hex(label, "xlated", xlated, info.xlated_prog_len);
    if (write_blob(output_dir, label, "xlated", xlated,
                   info.xlated_prog_len) != 0) {
        printf("%s_xlated_write_error=%d:%s\n", label, errno, strerror(errno));
    }

    if (info.jited_prog_len > 0) {
        print_hex(label, "jited", jited, info.jited_prog_len);
        if (write_blob(output_dir, label, "jited", jited,
                       info.jited_prog_len) != 0) {
            printf("%s_jited_write_error=%d:%s\n", label, errno,
                   strerror(errno));
        }
    } else {
        printf("%s_jited_visibility=zero_length_returned_by_kernel\n", label);
    }

    free(xlated);
    free(jited);
    return 0;
}

static int test_udp_filter(int program_fd, bool expect_receive,
                           const char *payload) {
    int rx = -1;
    int tx = -1;
    int result = -1;
    struct sockaddr_in address;
    socklen_t address_len = sizeof(address);

    rx = socket(AF_INET, SOCK_DGRAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
    tx = socket(AF_INET, SOCK_DGRAM | SOCK_CLOEXEC, 0);
    if (rx < 0 || tx < 0) {
        perror("socket");
        goto out;
    }

    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = 0;
    if (bind(rx, (struct sockaddr *)&address, sizeof(address)) != 0 ||
        getsockname(rx, (struct sockaddr *)&address, &address_len) != 0) {
        perror("bind/getsockname");
        goto out;
    }
    if (setsockopt(rx, SOL_SOCKET, SO_ATTACH_BPF, &program_fd,
                   sizeof(program_fd)) != 0) {
        perror("SO_ATTACH_BPF");
        goto out;
    }

    size_t payload_length = strlen(payload);
    ssize_t sent = sendto(tx, payload, payload_length, 0,
                          (struct sockaddr *)&address, sizeof(address));
    if (sent != (ssize_t)payload_length) {
        perror("sendto");
        goto out;
    }

    struct pollfd ready = {.fd = rx, .events = POLLIN};
    int poll_result;
    do {
        poll_result = poll(&ready, 1, 250);
    } while (poll_result < 0 && errno == EINTR);
    if (poll_result < 0) {
        perror("poll");
        goto out;
    }

    if (!expect_receive) {
        if (poll_result != 0) {
            printf("drop_filter_unexpected_poll=%d revents=0x%x\n", poll_result,
                   ready.revents);
            goto out;
        }
        printf("drop_filter_observation=send_succeeded_receive_timed_out\n");
        result = 0;
        goto out;
    }

    if (poll_result == 0) {
        printf("accept_filter_unexpected_timeout\n");
        goto out;
    }
    char received[128];
    ssize_t count = recv(rx, received, sizeof(received), 0);
    if (count < 0) {
        perror("recv");
        goto out;
    }
    if ((size_t)count != payload_length ||
        memcmp(received, payload, payload_length) != 0) {
        printf("accept_filter_payload_mismatch=count:%zd expected:%zu\n", count,
               payload_length);
        goto out;
    }
    printf("accept_filter_observation=received_exact_payload bytes=%zd\n", count);
    result = 0;

out:
    if (rx >= 0) {
        close(rx);
    }
    if (tx >= 0) {
        close(tx);
    }
    return result;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s OUTPUT_DIRECTORY\n", argv[0]);
        return 2;
    }
    if (mkdir(argv[1], 0700) != 0 && errno != EEXIST) {
        perror("mkdir output directory");
        return 2;
    }

    printf("probe_pid=%ld uid=%ld euid=%ld\n", (long)getpid(), (long)getuid(),
           (long)geteuid());
    printf("probe_boundary=raw_bpf_syscall_socket_filter_loopback_udp\n");

    const struct bpf_insn invalid_program[] = {
        JA(100),
        EXIT_INSN(),
    };
    const struct bpf_insn accept_program[] = {
        MOV64_IMM(BPF_REG_0, -1),
        EXIT_INSN(),
    };
    const struct bpf_insn drop_program[] = {
        MOV64_IMM(BPF_REG_0, 0),
        EXIT_INSN(),
    };
    char *log = calloc(65536, 1);
    if (log == NULL) {
        perror("calloc verifier log");
        return 2;
    }

    print_submitted_insns("invalid", invalid_program,
                          sizeof(invalid_program) / sizeof(invalid_program[0]));
    print_submitted_insns("accept", accept_program,
                          sizeof(accept_program) / sizeof(accept_program[0]));
    print_submitted_insns("drop", drop_program,
                          sizeof(drop_program) / sizeof(drop_program[0]));

    errno = 0;
    int invalid_fd = load_socket_filter("reject_ctx", invalid_program,
                                        sizeof(invalid_program) /
                                            sizeof(invalid_program[0]),
                                        log, 65536);
    int invalid_errno = errno;
    printf("invalid_load_result=fd:%d errno:%d:%s\n", invalid_fd,
           invalid_errno, strerror(invalid_errno));
    print_log("invalid", log);
    if (invalid_fd >= 0) {
        printf("invalid_program_unexpectedly_accepted\n");
        close(invalid_fd);
        free(log);
        return 1;
    }

    errno = 0;
    int accept_fd = load_socket_filter("accept_all", accept_program,
                                       sizeof(accept_program) /
                                           sizeof(accept_program[0]),
                                       log, 65536);
    int accept_errno = errno;
    printf("accept_load_result=fd:%d errno:%d:%s\n", accept_fd, accept_errno,
           strerror(accept_errno));
    print_log("accept", log);
    if (accept_fd < 0) {
        if (accept_errno == EPERM || accept_errno == EACCES) {
            printf("outcome=permission_boundary_prevented_verifier_demo\n");
            free(log);
            return 77;
        }
        free(log);
        return 1;
    }

    errno = 0;
    int drop_fd = load_socket_filter("drop_all", drop_program,
                                     sizeof(drop_program) /
                                         sizeof(drop_program[0]),
                                     log, 65536);
    int drop_errno = errno;
    printf("drop_load_result=fd:%d errno:%d:%s\n", drop_fd, drop_errno,
           strerror(drop_errno));
    print_log("drop", log);
    if (drop_fd < 0) {
        close(accept_fd);
        free(log);
        return 1;
    }

    int result = 0;
    if (inspect_program(accept_fd, "accept", argv[1]) != 0 ||
        inspect_program(drop_fd, "drop", argv[1]) != 0) {
        result = 1;
    }
    if (test_udp_filter(accept_fd, true, "topic40-accept") != 0 ||
        test_udp_filter(drop_fd, false, "topic40-drop") != 0) {
        result = 1;
    }
    printf("outcome=%s\n", result == 0 ? "all_correctness_checks_passed"
                                        : "correctness_check_failed");

    close(drop_fd);
    close(accept_fd);
    free(log);
    return result;
}
