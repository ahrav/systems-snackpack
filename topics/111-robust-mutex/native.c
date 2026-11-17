#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

typedef struct {
    pthread_mutex_t mutex;
    _Atomic int a, b, old_a, old_b, active;
} Shared;

static void check(int rc) { if (rc) { fprintf(stderr, "pthread error %d\n", rc); abort(); } }
static void reap(pid_t pid) {
    int status;
    assert(pid > 0 && waitpid(pid, &status, 0) == pid);
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
}
static void cut(int point, int target) { if (point == target) _exit(0); }

static int repair(Shared *s, int die_at) {
    if (s->active) {
        int a = s->old_a, b = s->old_b;
        if (a < 0 || a > 100 || b < 0 || b > 100 || a + b != 100) return 0;
        s->a = a;
        cut(0, die_at);
        s->b = b;
        cut(1, die_at);
        s->active = 0;
    }
    cut(2, die_at);
    return s->a >= 0 && s->a <= 100 && s->b >= 0 && s->b <= 100 && s->a + s->b == 100;
}

static void scenario(int initial, int amount, int point, int repair_cut, int mode) {
    Shared *s = mmap(NULL, sizeof(*s), PROT_READ | PROT_WRITE,
                     MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    assert(s != MAP_FAILED);
    atomic_init(&s->a, initial); atomic_init(&s->b, 100 - initial);
    atomic_init(&s->old_a, initial); atomic_init(&s->old_b, 100 - initial);
    atomic_init(&s->active, 0);
    assert(atomic_is_lock_free(&s->a) && atomic_is_lock_free(&s->active));
    pthread_mutexattr_t attr;
    check(pthread_mutexattr_init(&attr));
    check(pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED));
    check(pthread_mutexattr_setrobust(&attr, PTHREAD_MUTEX_ROBUST));
    check(pthread_mutex_init(&s->mutex, &attr));
    check(pthread_mutexattr_destroy(&attr));
    pid_t child = fork(); assert(child >= 0);
    if (!child) {
        check(pthread_mutex_lock(&s->mutex)); cut(0, point);
        s->old_a = s->a; s->old_b = s->b; cut(1, point);
        s->active = 1; cut(2, point);
        s->a -= amount; cut(3, point);
        s->b += amount; cut(4, point);
        s->active = 0; cut(5, point);
        abort();
    }
    reap(child);
    if (repair_cut >= 0) {
        child = fork(); assert(child >= 0);
        if (!child) {
            assert(pthread_mutex_lock(&s->mutex) == EOWNERDEAD);
            assert(repair(s, repair_cut));
            check(pthread_mutex_consistent(&s->mutex));
            _exit(0);
        }
        reap(child);
    }
    assert(pthread_mutex_lock(&s->mutex) == EOWNERDEAD);
    if (mode == 1) {
        s->old_a = 101; /* Invalid evidence must cause repair refusal. */
        assert(!repair(s, -1));
        check(pthread_mutex_unlock(&s->mutex));
        assert(pthread_mutex_lock(&s->mutex) == ENOTRECOVERABLE);
        printf("%d,%d,%d,%d,poison,%d,%d\n", initial, amount, point, repair_cut, s->a, s->b);
    } else {
        if (mode == 0) assert(repair(s, -1));
        check(pthread_mutex_consistent(&s->mutex));
        check(pthread_mutex_unlock(&s->mutex));
        check(pthread_mutex_lock(&s->mutex));
        printf("%d,%d,%d,%d,%s,%d,%d\n", initial, amount, point, repair_cut,
               mode == 2 ? "premature" : "repair", s->a, s->b);
        check(pthread_mutex_unlock(&s->mutex));
    }
    check(pthread_mutex_destroy(&s->mutex));
    assert(munmap(s, sizeof(*s)) == 0);
}

int main(void) {
    const int starts[] = {10, 40, 60, 100};
    puts("initial,amount,point,repair_cut,mode,a,b");
    for (unsigned i = 0; i < sizeof(starts)/sizeof(starts[0]); i++) {
        int a = starts[i];
        const int amounts[] = {1, a / 2, a};
        for (unsigned j = 0; j < sizeof(amounts)/sizeof(amounts[0]); j++) {
            for (int point = 0; point < 6; point++)
                for (int crash = -1; crash < 4; crash++)
                    scenario(a, amounts[j], point, crash, 0);
            scenario(a, amounts[j], 3, -1, 1);
            scenario(a, amounts[j], 3, -1, 2);
        }
    }
}
