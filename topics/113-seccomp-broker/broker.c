// Linux 5.14+, native x86-64 or AArch64. A cooperative, single-child fixture.
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <unistd.h>

#if defined(__x86_64__)
#define NATIVE_ARCH AUDIT_ARCH_X86_64
#elif defined(__aarch64__)
#define NATIVE_ARCH AUDIT_ARCH_AARCH64
#else
#error Requires a native x86-64 or AArch64 Linux process
#endif

// Reserved dirfd for this fixture's virtual catalog request.
#define CATALOG_DIR 789123

static void require(int ok, const char *step) {
    if (!ok) {
        fprintf(stderr, "%s failed (errno=%d)\n", step, errno);
        exit(EXIT_FAILURE);
    }
}

static int make_listener(void) {
    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, NATIVE_ARCH, 0, 4),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_openat, 0, 2),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[0])),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, CATALOG_DIR, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_USER_NOTIF)
    };
    struct sock_fprog program = { sizeof(filter) / sizeof(*filter), filter };
    require(prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == 0, "no_new_privs");
    int listener = syscall(SYS_seccomp, SECCOMP_SET_MODE_FILTER,
                           SECCOMP_FILTER_FLAG_NEW_LISTENER, &program);
    require(listener >= 0, "install listener");
    return listener;
}

static void worker(const struct stat *expected) {
    require(syscall(SYS_openat, CATALOG_DIR, "unknown", O_RDONLY | O_CLOEXEC, 0) == -1
            && errno == EACCES, "unknown name");
    require(syscall(SYS_openat, CATALOG_DIR, "catalog", O_RDWR, 0) == -1
            && errno == EACCES, "write access");

    int fd = syscall(SYS_openat, CATALOG_DIR, "catalog", O_RDONLY | O_CLOEXEC, 0);
    require(fd >= 0, "receive catalog");
    struct stat got;
    require(fstat(fd, &got) == 0 && got.st_dev == expected->st_dev
            && got.st_ino == expected->st_ino, "file identity");
    require(fcntl(fd, F_GETFD) == FD_CLOEXEC, "close-on-exec");
    int flags = fcntl(fd, F_GETFL);
    require(flags >= 0 && (flags & O_ACCMODE) == O_RDONLY, "read-only access");
    char bytes[8];
    require(pread(fd, bytes, sizeof(bytes), 0) == 7
            && memcmp(bytes, "item=42", 7) == 0, "catalog contents");
    close(fd);
}

static int selects_catalog(pid_t child, const struct seccomp_data *call) {
    if (call->arch != NATIVE_ARCH || call->nr != SYS_openat
        || call->args[0] != CATALOG_DIR || call->args[2] != (O_RDONLY | O_CLOEXEC))
        return 0;
    char snapshot[sizeof("catalog")];
    struct iovec local = {snapshot, sizeof(snapshot)};
    struct iovec remote = {(void *)(uintptr_t)call->args[1], sizeof(snapshot)};
    ssize_t count = process_vm_readv(child, &local, 1, &remote, 1, 0);
    return count == (ssize_t)sizeof(snapshot)
        && memcmp(snapshot, "catalog", sizeof(snapshot)) == 0;
}

int main(void) {
    // The only supervised process is our unreaped direct child.
    alarm(15);
    char path[] = "/tmp/topic113-XXXXXX";
    int writer = mkstemp(path);
    require(writer >= 0 && write(writer, "item=42", 7) == 7, "fixture");
    int catalog = open(path, O_RDONLY | O_CLOEXEC);
    require(catalog >= 0 && unlink(path) == 0, "read-only fixture");
    close(writer);
    struct stat expected;
    require(fstat(catalog, &expected) == 0, "fixture identity");
    struct seccomp_notif_sizes sizes;
    require(syscall(SYS_seccomp, SECCOMP_GET_NOTIF_SIZES, 0, &sizes) == 0,
            "notification sizes");
    struct seccomp_notif *req = calloc(1, sizes.seccomp_notif);
    require(req != NULL, "allocate");
    int listener = make_listener();
    pid_t child = fork();
    require(child >= 0, "fork");
    if (child == 0) {
        close(listener);
        close(catalog);
        alarm(12);
        worker(&expected);
        _exit(0);
    }

    for (int i = 0; i < 3; i++) {
        memset(req, 0, sizes.seccomp_notif);
        require(ioctl(listener, SECCOMP_IOCTL_NOTIF_RECV, req) == 0, "receive");
        require(req->pid == (uint32_t)child, "target identity");
        require(ioctl(listener, SECCOMP_IOCTL_NOTIF_ID_VALID, &req->id) == 0, "live ID");
        if (selects_catalog(child, &req->data)) {
            struct seccomp_notif_addfd add = {
                .id = req->id, .srcfd = (uint32_t)catalog,
                .flags = SECCOMP_ADDFD_FLAG_SEND, .newfd_flags = O_CLOEXEC
            };
            require(ioctl(listener, SECCOMP_IOCTL_NOTIF_ADDFD, &add) >= 0, "atomic delivery");
        } else {
            struct seccomp_notif_resp deny = {.id = req->id, .error = -EACCES};
            require(ioctl(listener, SECCOMP_IOCTL_NOTIF_SEND, &deny) == 0, "deny");
        }
    }
    int status;
    require(waitpid(child, &status, 0) == child && WIFEXITED(status)
            && WEXITSTATUS(status) == 0, "worker assertions");
    struct seccomp_notif_addfd stale = {
        .id = req->id, .srcfd = (uint32_t)catalog, .flags = SECCOMP_ADDFD_FLAG_SEND
    };
    require(ioctl(listener, SECCOMP_IOCTL_NOTIF_ADDFD, &stale) == -1
            && errno == ENOENT, "reject completed ID");
    free(req);
    close(listener);
    close(catalog);
    puts("2 denials, 1 verified catalog descriptor, completed ID rejected");
}
