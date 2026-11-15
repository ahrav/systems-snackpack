#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/sched.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <sys/wait.h>
/* Linux UAPI supplies P_PIDFD when libc headers predate its wrapper support. */
#include <linux/wait.h>
#include <time.h>
#include <unistd.h>

/* The standalone single-threaded parent is the only reaper. */
static pid_t owned_child = -1;
static void cleanup(void) {
    if (owned_child > 0) {
        kill(owned_child, SIGKILL);
        while (waitpid(owned_child, NULL, 0) < 0 && errno == EINTR) {}
    }
}
#define CHECK(x) do { if (!(x)) { \
    fprintf(stderr, "line %d: %s errno=%d\n", __LINE__, #x, errno); exit(1); \
} } while (0)

static long long now_ms(void) {
    struct timespec t;
    CHECK(clock_gettime(CLOCK_MONOTONIC, &t) == 0);
    return (long long)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
static void ready(int fd) {
    long long deadline = now_ms() + 5000;
    struct pollfd p = { .fd = fd, .events = POLLIN };
    for (;;) {
        long long left = deadline - now_ms();
        CHECK(left > 0);
        int n = poll(&p, 1, (int)left);
        if (n < 0 && errno == EINTR) continue;
        CHECK(n == 1 && (p.revents & POLLIN));
        return;
    }
}
static siginfo_t status(idtype_t type, id_t id, int options) {
    siginfo_t s = {0};
    int r;
    do { r = waitid(type, id, &s, options); } while (r < 0 && errno == EINTR);
    CHECK(r == 0);
    return s;
}
static int one(int mode) {
    int pfd = -1;
    int natural = mode >= 2;
    pid_t pid;
    if (mode == 0 || mode == 3) {
        struct clone_args args = {0};
        args.flags = CLONE_PIDFD;
        args.pidfd = (uintptr_t)&pfd;
        args.exit_signal = SIGCHLD;
        pid = (pid_t)syscall(SYS_clone3, &args, sizeof(args));
        if (pid < 0 && (errno == ENOSYS || errno == EPERM)) return 0;
    } else {
        pid = fork();
    }
    CHECK(pid >= 0);
    if (pid == 0) {
        if (natural) _exit(37);
        for (;;) pause();
    }
    owned_child = pid;
    if (mode == 2) {
        /* Observe exit without reaping, then acquire the zombie's identity. */
        siginfo_t s = status(P_PID, (id_t)pid, WEXITED | WNOWAIT);
        CHECK(s.si_pid == pid && s.si_code == CLD_EXITED && s.si_status == 37);
    }
    if (pfd < 0) pfd = (int)syscall(SYS_pidfd_open, pid, 0);
    CHECK(pfd >= 0);
    CHECK(fcntl(pfd, F_GETFD) & FD_CLOEXEC);
    if (!natural) {
        struct pollfd p = { .fd = pfd, .events = POLLIN };
        CHECK(poll(&p, 1, 0) == 0);
        CHECK(syscall(SYS_pidfd_send_signal, pfd, SIGTERM, NULL, 0) == 0);
    }
    ready(pfd);
    siginfo_t peek = status(P_PIDFD, (id_t)pfd, WEXITED | WNOWAIT);
    CHECK(peek.si_pid == pid);
    CHECK(peek.si_code == (natural ? CLD_EXITED : CLD_KILLED));
    CHECK(peek.si_status == (natural ? 37 : SIGTERM));
    siginfo_t collected = status(P_PIDFD, (id_t)pfd, WEXITED);
    owned_child = -1;
    CHECK(collected.si_pid == peek.si_pid && collected.si_code == peek.si_code
          && collected.si_status == peek.si_status);
    errno = 0;
    CHECK(syscall(SYS_pidfd_send_signal, pfd, 0, NULL, 0) == -1 && errno == ESRCH);
    siginfo_t s = {0};
    errno = 0;
    CHECK(waitid(P_PIDFD, (id_t)pfd, &s, WEXITED | WNOHANG) == -1 && errno == ECHILD);
    CHECK(close(pfd) == 0);
    return 1;
}
int main(void) {
    CHECK(atexit(cleanup) == 0);
    struct sigaction sa = { .sa_handler = SIG_DFL };
    CHECK(sigemptyset(&sa.sa_mask) == 0);
    CHECK(sigaction(SIGCHLD, &sa, NULL) == 0);
    CHECK(sigaction(SIGTERM, &sa, NULL) == 0);
    sigset_t empty;
    CHECK(sigemptyset(&empty) == 0);
    CHECK(sigprocmask(SIG_SETMASK, &empty, NULL) == 0);
    int counts[4] = {0};
    for (int round = 0; round < 64; ++round)
        for (int mode = 0; mode < 4; ++mode) counts[mode] += one(mode);
    printf("clone_signal=%d fork_signal=%d zombie_open=%d clone_exit=%d PASS\n",
           counts[0], counts[1], counts[2], counts[3]);
    if (!counts[0]) puts("LIMIT: clone3 unavailable (ENOSYS or EPERM); atomic path untested");
    return 0;
}
