#include <stddef.h>
#include <stdint.h>

/* All arithmetic is modulo 2^64. No retained pointer, mutation or callback. */
static uint64_t transform(uint64_t x, uint32_t rounds) {
    for (uint32_t r = 0; r < rounds; ++r) {
        x = x * UINT64_C(6364136223846793005) + UINT64_C(1442695040888963407);
        x ^= x >> 29;
    }
    return x;
}

uint64_t topic67_one(uint64_t x, uint32_t rounds) {
    return transform(x, rounds);
}

/* For n > 0, p names n initialized, aligned, readable uint64_t elements.
   The caller owns the storage throughout this synchronous call.
   For n == 0, p may be null: no pointer arithmetic or dereference occurs. */
uint64_t topic67_batch(const uint64_t *p, size_t n, uint32_t rounds) {
    uint64_t sum = 0;
    for (size_t i = 0; i < n; ++i) sum += transform(p[i], rounds);
    return sum;
}
