#define _GNU_SOURCE
#include <assert.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/epoll.h>
#include <unistd.h>

static void run(int alias, int delete_first) {
    int a[2], b[2];
    assert(pipe2(a, O_NONBLOCK | O_CLOEXEC) == 0);
    assert(pipe2(b, O_NONBLOCK | O_CLOEXEC) == 0);
    int fd = a[0];
    int duplicate = alias ? dup(fd) : -1;
    assert(!alias || duplicate >= 0);
    int ep = epoll_create1(EPOLL_CLOEXEC);
    assert(ep >= 0);
    struct epoll_event reg = {.events = EPOLLIN, .data.u64 = UINT64_C(1) << 32};
    assert(epoll_ctl(ep, EPOLL_CTL_ADD, fd, &reg) == 0);
    assert(write(a[1], "A", 1) == 1);
    struct epoll_event saved;
    assert(epoll_wait(ep, &saved, 1, 1000) == 1);
    assert(saved.data.u64 == reg.data.u64);

    /* The owner marks A dead before deregistration and close. */
    int live = 0;
    if (delete_first) assert(epoll_ctl(ep, EPOLL_CTL_DEL, fd, NULL) == 0);
    assert(close(fd) == 0);
    assert(dup2(b[0], fd) == fd);
    assert(close(b[0]) == 0);
    uint64_t current = UINT64_C(2) << 32;
    live = 1;
    assert(write(b[1], "B", 1) == 1);
    assert(!(live && saved.data.u64 == current));
    char byte = 0;
    /* Deliberately faulty dispatch proves which object the raw fd now names. */
    assert(read(fd, &byte, 1) == 1 && byte == 'B');

    struct epoll_event event;
    int n = epoll_wait(ep, &event, 1, 0);
    assert(n == (alias && !delete_first));
    if (n) assert(event.data.u64 == saved.data.u64);
    if (alias) assert(close(duplicate) == 0);
    assert(close(a[1]) == 0);

    reg.data.u64 = current;
    assert(epoll_ctl(ep, EPOLL_CTL_ADD, fd, &reg) == 0);
    assert(write(b[1], "C", 1) == 1);
    assert(epoll_wait(ep, &event, 1, 1000) == 1);
    assert(event.data.u64 == current);
    assert(read(fd, &byte, 1) == 1 && byte == 'C');
    assert(epoll_ctl(ep, EPOLL_CTL_DEL, fd, NULL) == 0);
    assert(close(fd) == 0);
    assert(close(b[1]) == 0);
    assert(close(ep) == 0);
}

int main(void) {
    for (int i = 0; i < 64; ++i)
        for (int alias = 0; alias < 2; ++alias)
            for (int del = 0; del < 2; ++del) run(alias, del);
    puts("native_cases=256 stale_rejected=256 raw_reads_B=256 fresh_reads_C=256 alias_cases=64");
}
