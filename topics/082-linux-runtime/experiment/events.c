// Single-threaded Linux signal and timer correctness probes; no host policy changes.
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/signalfd.h>
#include <sys/timerfd.h>
#include <time.h>
#include <unistd.h>

static void ready(int fd) {
    struct pollfd p = {.fd = fd, .events = POLLIN};
    assert(poll(&p, 1, 1000) == 1 && (p.revents & POLLIN));
}
int main(void) {
    sigset_t mask, old;
    assert(sigemptyset(&mask) == 0);
    assert(sigaddset(&mask, SIGUSR1) == 0);
    assert(sigprocmask(SIG_BLOCK, &mask, &old) == 0);
    int s = signalfd(-1, &mask, SFD_NONBLOCK | SFD_CLOEXEC);
    assert(s >= 0);
    assert(kill(getpid(), SIGUSR1) == 0);
    assert(kill(getpid(), SIGUSR1) == 0);
    ready(s);
    struct signalfd_siginfo info;
    assert(read(s, &info, sizeof info) == sizeof info && info.ssi_signo == SIGUSR1);
    assert(read(s, &info, sizeof info) == -1 && errno == EAGAIN);
    assert(close(s) == 0);
    assert(sigprocmask(SIG_SETMASK, &old, NULL) == 0);
    puts("PASS: two blocked standard signals coalesce into one signalfd record");

    int t = timerfd_create(CLOCK_MONOTONIC, TFD_NONBLOCK | TFD_CLOEXEC);
    assert(t >= 0);
    struct timespec deadline;
    assert(clock_gettime(CLOCK_MONOTONIC, &deadline) == 0);
    deadline.tv_nsec += 2000000;
    if (deadline.tv_nsec >= 1000000000) { ++deadline.tv_sec; deadline.tv_nsec -= 1000000000; }
    struct itimerspec spec = {.it_value = deadline};
    assert(timerfd_settime(t, TFD_TIMER_ABSTIME, &spec, NULL) == 0);
    ready(t);
    uint64_t expirations;
    assert(read(t, &expirations, sizeof expirations) == sizeof expirations && expirations == 1);
    struct timespec now;
    assert(clock_gettime(CLOCK_MONOTONIC, &now) == 0);
    assert(now.tv_sec > deadline.tv_sec || (now.tv_sec == deadline.tv_sec && now.tv_nsec >= deadline.tv_nsec));
    assert(read(t, &expirations, sizeof expirations) == -1 && errno == EAGAIN);
    assert(close(t) == 0);
    puts("PASS: absolute monotonic one-shot timerfd expires and drains once; no precision claim");
}
