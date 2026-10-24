// Bounded pthread comparison for task-granularity experiments.
// This uses mutex-protected queues.  It is not a lock-free Chase-Lev deque.
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sched.h>

typedef struct { uint32_t lo, hi; } Task;
typedef struct { Task *items; uint32_t len, cap; pthread_mutex_t lock; } Queue;
typedef struct {
  Queue *queues; uint32_t workers, grain, rounds, skew;
  atomic_uint outstanding, steals;
  atomic_ullong sum;
} Scheduler;
typedef struct { Scheduler *s; uint32_t id; } StealArg;
typedef struct { uint32_t lo, hi, rounds, skew; uint64_t sum; } StaticArg;

static void *allocate(size_t count, size_t size) {
  void *p = calloc(count, size);
  if (!p) abort();
  return p;
}

static void require_pthread(int result) {
  if (result) { fprintf(stderr, "pthread error: %s\n", strerror(result)); abort(); }
}

static uint32_t number(const char *text) {
  char *end;
  unsigned long value = strtoul(text, &end, 10);
  if (!*text || *end || value > UINT32_MAX || *text == '-') exit(2);
  return (uint32_t)value;
}

static uint64_t item(uint32_t i, uint32_t rounds, uint32_t skew) {
  uint64_t x = (uint64_t)i + 0x9e3779b97f4a7c15ULL;
  uint32_t count = rounds * ((i % 19U == 0U) ? skew : 1U);
  for (uint32_t j = 0; j < count; ++j) {
    x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ULL;
    x ^= x >> 27; x *= 0x94d049bb133111ebULL;
  }
  return x ^ (x >> 31);
}

static uint64_t range_sum(uint32_t lo, uint32_t hi, uint32_t rounds, uint32_t skew) {
  uint64_t out = 0;
  for (uint32_t i = lo; i < hi; ++i) out += item(i, rounds, skew);
  return out;
}

static int push(Queue *q, Task t) {
  require_pthread(pthread_mutex_lock(&q->lock));
  if (q->len == q->cap) { require_pthread(pthread_mutex_unlock(&q->lock)); return 0; }
  q->items[q->len++] = t;
  require_pthread(pthread_mutex_unlock(&q->lock));
  return 1;
}

static int pop_newest(Queue *q, Task *out) {
  require_pthread(pthread_mutex_lock(&q->lock));
  if (!q->len) { require_pthread(pthread_mutex_unlock(&q->lock)); return 0; }
  *out = q->items[--q->len];
  require_pthread(pthread_mutex_unlock(&q->lock));
  return 1;
}

static int steal_oldest(Queue *q, Task *out) {
  require_pthread(pthread_mutex_lock(&q->lock));
  if (!q->len) { require_pthread(pthread_mutex_unlock(&q->lock)); return 0; }
  *out = q->items[0];
  memmove(q->items, q->items + 1, (q->len - 1) * sizeof(*q->items));
  --q->len;
  require_pthread(pthread_mutex_unlock(&q->lock));
  return 1;
}

static void *steal_worker(void *ptr) {
  StealArg *arg = ptr; Scheduler *s = arg->s; Task t;
  for (;;) {
    int got = pop_newest(&s->queues[arg->id], &t);
    if (!got) {
      for (uint32_t step = 1; step < s->workers && !got; ++step) {
        uint32_t victim = (arg->id + step) % s->workers;
        got = steal_oldest(&s->queues[victim], &t);
        if (got) atomic_fetch_add(&s->steals, 1);
      }
    }
    if (!got) {
      if (atomic_load(&s->outstanding) == 0) break;
      sched_yield();
      continue;
    }
    if (t.hi - t.lo > s->grain) {
      uint32_t mid = t.lo + (t.hi - t.lo) / 2;
      // Count both children before either can finish on another worker.
      atomic_fetch_add(&s->outstanding, 1);
      if (!push(&s->queues[arg->id], (Task){mid, t.hi})) abort();
      if (!push(&s->queues[arg->id], (Task){t.lo, mid})) abort();
      continue;
    }
    atomic_fetch_add(&s->sum, range_sum(t.lo, t.hi, s->rounds, s->skew));
    atomic_fetch_sub(&s->outstanding, 1);
  }
  return NULL;
}

static void *static_worker(void *ptr) {
  StaticArg *arg = ptr;
  arg->sum = range_sum(arg->lo, arg->hi, arg->rounds, arg->skew);
  return NULL;
}

static uint64_t now_ns(void) {
  struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static uint64_t run_static(uint32_t n, uint32_t workers, uint32_t rounds, uint32_t skew) {
  pthread_t *threads = allocate(workers, sizeof(*threads));
  StaticArg *args = allocate(workers, sizeof(*args)); uint64_t sum = 0;
  for (uint32_t w = 0; w < workers; ++w) {
    args[w] = (StaticArg){n * w / workers, n * (w + 1) / workers, rounds, skew, 0};
    require_pthread(pthread_create(&threads[w], NULL, static_worker, &args[w]));
  }
  for (uint32_t w = 0; w < workers; ++w) { require_pthread(pthread_join(threads[w], NULL)); sum += args[w].sum; }
  free(args); free(threads); return sum;
}

static uint64_t run_steal(uint32_t n, uint32_t workers, uint32_t grain, uint32_t rounds, uint32_t skew, unsigned *steals) {
  Scheduler s = {0}; s.workers = workers; s.grain = grain; s.rounds = rounds; s.skew = skew;
  atomic_init(&s.outstanding, 1); atomic_init(&s.steals, 0); atomic_init(&s.sum, 0);
  s.queues = allocate(workers, sizeof(*s.queues));
  uint32_t cap = n / grain + 4;
  for (uint32_t w = 0; w < workers; ++w) { s.queues[w].items = allocate(cap, sizeof(Task)); s.queues[w].cap = cap; require_pthread(pthread_mutex_init(&s.queues[w].lock, NULL)); }
  push(&s.queues[0], (Task){0, n});
  pthread_t *threads = allocate(workers, sizeof(*threads)); StealArg *args = allocate(workers, sizeof(*args));
  for (uint32_t w = 0; w < workers; ++w) { args[w] = (StealArg){&s, w}; require_pthread(pthread_create(&threads[w], NULL, steal_worker, &args[w])); }
  for (uint32_t w = 0; w < workers; ++w) require_pthread(pthread_join(threads[w], NULL));
  uint64_t sum = atomic_load(&s.sum); *steals = atomic_load(&s.steals);
  for (uint32_t w = 0; w < workers; ++w) { require_pthread(pthread_mutex_destroy(&s.queues[w].lock)); free(s.queues[w].items); }
  free(args); free(threads); free(s.queues); return sum;
}

static uint64_t run_serial(uint32_t n, uint32_t rounds, uint32_t skew) { return range_sum(0, n, rounds, skew); }

static int check(uint32_t n, uint32_t workers, uint32_t grain, uint32_t rounds, uint32_t skew) {
  unsigned steals; uint64_t serial = run_serial(n, rounds, skew);
  return serial == run_static(n, workers, rounds, skew) && serial == run_steal(n, workers, grain, rounds, skew, &steals);
}

int main(int argc, char **argv) {
  uint32_t n = 1U << 18, workers = 4, grain = 256, rounds = 8, skew = 16, reps = 5; int self_test = 0, selected = -1;
  for (int i = 1; i < argc; ++i) {
    if (!strcmp(argv[i], "--self-test")) self_test = 1;
    else if (i + 1 < argc && !strcmp(argv[i], "--mode")) {
      const char *mode = argv[++i];
      selected = !strcmp(mode, "serial") ? 0 : !strcmp(mode, "static") ? 1 : !strcmp(mode, "steal") ? 2 : -1;
      if (selected < 0) return 2;
    }
    else if (i + 1 < argc && !strcmp(argv[i], "--n")) n = number(argv[++i]);
    else if (i + 1 < argc && !strcmp(argv[i], "--workers")) workers = number(argv[++i]);
    else if (i + 1 < argc && !strcmp(argv[i], "--grain")) grain = number(argv[++i]);
    else if (i + 1 < argc && !strcmp(argv[i], "--rounds")) rounds = number(argv[++i]);
    else if (i + 1 < argc && !strcmp(argv[i], "--skew")) skew = number(argv[++i]);
    else if (i + 1 < argc && !strcmp(argv[i], "--reps")) reps = number(argv[++i]);
    else { fprintf(stderr, "bad argument: %s\n", argv[i]); return 2; }
  }
  if (!n || n > (1U << 24) || !workers || workers > 64 || !grain || !rounds || !skew || rounds > UINT32_MAX / skew || !reps || reps > 1000) return 2;
  if (self_test) {
    unsigned cases = 0;
    uint32_t ns[] = {1024, 4096}, gs[] = {1, 64, 256}, ws[] = {1, 2, 4}, rs[] = {2, 20}, ss[] = {1, 8};
    for (unsigned a=0;a<2;a++) for (unsigned b=0;b<3;b++) for (unsigned c=0;c<3;c++) for (unsigned d=0;d<2;d++) for (unsigned e=0;e<2;e++) { if (!check(ns[a],ws[c],gs[b],rs[d],ss[e])) return 1; ++cases; }
    printf("self-test: %u serial/static/work-steal checksum cases passed\n", cases); return 0;
  }
  printf("mode,rep,n,workers,grain,rounds,skew,elapsed_ns,checksum,steals\n");
  for (uint32_t rep = 0; rep < reps; ++rep) {
    for (uint32_t phase = 0; phase < 3; ++phase) {
      uint32_t mode = (rep + phase) % 3;
      if (selected >= 0 && mode != (uint32_t)selected) continue;
      unsigned steals = 0; uint64_t before = now_ns(), sum;
      if (mode == 0) sum = run_serial(n, rounds, skew);
      else if (mode == 1) sum = run_static(n, workers, rounds, skew);
      else sum = run_steal(n, workers, grain, rounds, skew, &steals);
      printf("%s,%u,%u,%u,%u,%u,%u,%llu,%llu,%u\n", mode==0?"serial":mode==1?"static":"steal", rep, n, workers, grain, rounds, skew, (unsigned long long)(now_ns()-before), (unsigned long long)sum, steals);
    }
  }
  return 0;
}
