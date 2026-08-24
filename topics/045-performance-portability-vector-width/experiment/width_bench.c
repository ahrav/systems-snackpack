#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#if defined(__x86_64__)
#include <immintrin.h>
#elif defined(__aarch64__)
#include <arm_neon.h>
#else
#error "This focused experiment supports x86-64 and AArch64 only"
#endif

enum { LOGICAL_CHAINS = 96, ACCUMULATORS = 12 };

static volatile double initial_values[LOGICAL_CHAINS];
static volatile double result_sink;

static uint64_t monotonic_raw_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &ts) != 0) {
        perror("clock_gettime");
        exit(2);
    }
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

static void initialize_values(void) {
    for (size_t i = 0; i < LOGICAL_CHAINS; ++i) {
        initial_values[i] = 0.25 + (double)i * 0x1p-20;
    }
}

#define UPDATE_SCALAR()          \
    do {                         \
        x0 = __builtin_fma(multiplier, addend, x0);   \
        x1 = __builtin_fma(multiplier, addend, x1);   \
        x2 = __builtin_fma(multiplier, addend, x2);   \
        x3 = __builtin_fma(multiplier, addend, x3);   \
        x4 = __builtin_fma(multiplier, addend, x4);   \
        x5 = __builtin_fma(multiplier, addend, x5);   \
        x6 = __builtin_fma(multiplier, addend, x6);   \
        x7 = __builtin_fma(multiplier, addend, x7);   \
        x8 = __builtin_fma(multiplier, addend, x8);   \
        x9 = __builtin_fma(multiplier, addend, x9);   \
        x10 = __builtin_fma(multiplier, addend, x10); \
        x11 = __builtin_fma(multiplier, addend, x11); \
    } while (0)

#if defined(__x86_64__)
__attribute__((noinline, target("fma"), optimize("no-tree-vectorize")))
#else
__attribute__((noinline, optimize("no-tree-vectorize")))
#endif
static double kernel_scalar(uint64_t steps) {
    const double multiplier = 0.99999999999;
    const double addend = 0.00000000001;
    double total = 0.0;

    for (size_t batch = 0; batch < LOGICAL_CHAINS / ACCUMULATORS; ++batch) {
        const size_t base = batch * ACCUMULATORS;
        double x0 = initial_values[base + 0];
        double x1 = initial_values[base + 1];
        double x2 = initial_values[base + 2];
        double x3 = initial_values[base + 3];
        double x4 = initial_values[base + 4];
        double x5 = initial_values[base + 5];
        double x6 = initial_values[base + 6];
        double x7 = initial_values[base + 7];
        double x8 = initial_values[base + 8];
        double x9 = initial_values[base + 9];
        double x10 = initial_values[base + 10];
        double x11 = initial_values[base + 11];

        for (uint64_t i = 0; i < steps; ++i) {
            UPDATE_SCALAR();
        }

        total += x0 + x1 + x2 + x3 + x4 + x5 + x6 + x7 + x8 + x9 + x10 + x11;
    }
    return total / (double)LOGICAL_CHAINS;
}

#if defined(__x86_64__)

#define DECLARE_X86_REGS(type, load, base) \
    type x0 = load((const double *)&initial_values[(base) + 0 * LANES]);   \
    type x1 = load((const double *)&initial_values[(base) + 1 * LANES]);   \
    type x2 = load((const double *)&initial_values[(base) + 2 * LANES]);   \
    type x3 = load((const double *)&initial_values[(base) + 3 * LANES]);   \
    type x4 = load((const double *)&initial_values[(base) + 4 * LANES]);   \
    type x5 = load((const double *)&initial_values[(base) + 5 * LANES]);   \
    type x6 = load((const double *)&initial_values[(base) + 6 * LANES]);   \
    type x7 = load((const double *)&initial_values[(base) + 7 * LANES]);   \
    type x8 = load((const double *)&initial_values[(base) + 8 * LANES]);   \
    type x9 = load((const double *)&initial_values[(base) + 9 * LANES]);   \
    type x10 = load((const double *)&initial_values[(base) + 10 * LANES]); \
    type x11 = load((const double *)&initial_values[(base) + 11 * LANES])

#define UPDATE_X86(fma, multiplier, addend) \
    do {                                      \
        x0 = fma(multiplier, addend, x0);     \
        x1 = fma(multiplier, addend, x1);     \
        x2 = fma(multiplier, addend, x2);     \
        x3 = fma(multiplier, addend, x3);     \
        x4 = fma(multiplier, addend, x4);     \
        x5 = fma(multiplier, addend, x5);     \
        x6 = fma(multiplier, addend, x6);     \
        x7 = fma(multiplier, addend, x7);     \
        x8 = fma(multiplier, addend, x8);     \
        x9 = fma(multiplier, addend, x9);     \
        x10 = fma(multiplier, addend, x10);   \
        x11 = fma(multiplier, addend, x11);   \
    } while (0)

__attribute__((noinline, target("avx,fma")))
static double kernel_v128(uint64_t steps) {
    enum { LANES = 2 };
    const __m128d multiplier = _mm_set1_pd(0.99999999999);
    const __m128d addend = _mm_set1_pd(0.00000000001);
    double total = 0.0;
    double lanes[LANES];
    for (size_t batch = 0; batch < LOGICAL_CHAINS / (ACCUMULATORS * LANES); ++batch) {
        const size_t base = batch * ACCUMULATORS * LANES;
        DECLARE_X86_REGS(__m128d, _mm_loadu_pd, base);
        for (uint64_t i = 0; i < steps; ++i) {
            UPDATE_X86(_mm_fmadd_pd, multiplier, addend);
        }
#define REDUCE_128(x) do { _mm_storeu_pd(lanes, (x)); total += lanes[0] + lanes[1]; } while (0)
        REDUCE_128(x0); REDUCE_128(x1); REDUCE_128(x2); REDUCE_128(x3);
        REDUCE_128(x4); REDUCE_128(x5); REDUCE_128(x6); REDUCE_128(x7);
        REDUCE_128(x8); REDUCE_128(x9); REDUCE_128(x10); REDUCE_128(x11);
#undef REDUCE_128
    }
    return total / (double)LOGICAL_CHAINS;
}

__attribute__((noinline, target("avx2,fma")))
static double kernel_v256(uint64_t steps) {
    enum { LANES = 4 };
    const __m256d multiplier = _mm256_set1_pd(0.99999999999);
    const __m256d addend = _mm256_set1_pd(0.00000000001);
    double total = 0.0;
    double lanes[LANES];
    for (size_t batch = 0; batch < LOGICAL_CHAINS / (ACCUMULATORS * LANES); ++batch) {
        const size_t base = batch * ACCUMULATORS * LANES;
        DECLARE_X86_REGS(__m256d, _mm256_loadu_pd, base);
        for (uint64_t i = 0; i < steps; ++i) {
            UPDATE_X86(_mm256_fmadd_pd, multiplier, addend);
        }
#define REDUCE_256(x) do { _mm256_storeu_pd(lanes, (x)); total += lanes[0] + lanes[1] + lanes[2] + lanes[3]; } while (0)
        REDUCE_256(x0); REDUCE_256(x1); REDUCE_256(x2); REDUCE_256(x3);
        REDUCE_256(x4); REDUCE_256(x5); REDUCE_256(x6); REDUCE_256(x7);
        REDUCE_256(x8); REDUCE_256(x9); REDUCE_256(x10); REDUCE_256(x11);
#undef REDUCE_256
    }
    return total / (double)LOGICAL_CHAINS;
}

__attribute__((noinline, target("avx512f,fma")))
static double kernel_v512(uint64_t steps) {
    enum { LANES = 8 };
    const __m512d multiplier = _mm512_set1_pd(0.99999999999);
    const __m512d addend = _mm512_set1_pd(0.00000000001);
    double total = 0.0;
    double lanes[LANES];
    const size_t base = 0;
    DECLARE_X86_REGS(__m512d, _mm512_loadu_pd, base);
    for (uint64_t i = 0; i < steps; ++i) {
        UPDATE_X86(_mm512_fmadd_pd, multiplier, addend);
    }
#define REDUCE_512(x) do { _mm512_storeu_pd(lanes, (x)); for (size_t k = 0; k < LANES; ++k) total += lanes[k]; } while (0)
    REDUCE_512(x0); REDUCE_512(x1); REDUCE_512(x2); REDUCE_512(x3);
    REDUCE_512(x4); REDUCE_512(x5); REDUCE_512(x6); REDUCE_512(x7);
    REDUCE_512(x8); REDUCE_512(x9); REDUCE_512(x10); REDUCE_512(x11);
#undef REDUCE_512
    return total / (double)LOGICAL_CHAINS;
}

static int mode_supported(const char *mode) {
    __builtin_cpu_init();
    if (strcmp(mode, "scalar") == 0) return __builtin_cpu_supports("fma");
    if (strcmp(mode, "v128") == 0) return __builtin_cpu_supports("avx") && __builtin_cpu_supports("fma");
    if (strcmp(mode, "v256") == 0) return __builtin_cpu_supports("avx2") && __builtin_cpu_supports("fma");
    if (strcmp(mode, "v512") == 0) return __builtin_cpu_supports("avx512f") && __builtin_cpu_supports("fma");
    return 0;
}

static double run_kernel(const char *mode, uint64_t steps) {
    if (strcmp(mode, "scalar") == 0) return kernel_scalar(steps);
    if (strcmp(mode, "v128") == 0) return kernel_v128(steps);
    if (strcmp(mode, "v256") == 0) return kernel_v256(steps);
    if (strcmp(mode, "v512") == 0) return kernel_v512(steps);
    fprintf(stderr, "unknown mode: %s\n", mode);
    exit(2);
}

#elif defined(__aarch64__)

#define DECLARE_NEON_REGS(base) \
    float64x2_t x0 = vld1q_f64((const double *)&initial_values[(base) + 0 * LANES]);   \
    float64x2_t x1 = vld1q_f64((const double *)&initial_values[(base) + 1 * LANES]);   \
    float64x2_t x2 = vld1q_f64((const double *)&initial_values[(base) + 2 * LANES]);   \
    float64x2_t x3 = vld1q_f64((const double *)&initial_values[(base) + 3 * LANES]);   \
    float64x2_t x4 = vld1q_f64((const double *)&initial_values[(base) + 4 * LANES]);   \
    float64x2_t x5 = vld1q_f64((const double *)&initial_values[(base) + 5 * LANES]);   \
    float64x2_t x6 = vld1q_f64((const double *)&initial_values[(base) + 6 * LANES]);   \
    float64x2_t x7 = vld1q_f64((const double *)&initial_values[(base) + 7 * LANES]);   \
    float64x2_t x8 = vld1q_f64((const double *)&initial_values[(base) + 8 * LANES]);   \
    float64x2_t x9 = vld1q_f64((const double *)&initial_values[(base) + 9 * LANES]);   \
    float64x2_t x10 = vld1q_f64((const double *)&initial_values[(base) + 10 * LANES]); \
    float64x2_t x11 = vld1q_f64((const double *)&initial_values[(base) + 11 * LANES])

#define UPDATE_NEON()                   \
    do {                                \
        x0 = vfmaq_f64(x0, multiplier, addend);   \
        x1 = vfmaq_f64(x1, multiplier, addend);   \
        x2 = vfmaq_f64(x2, multiplier, addend);   \
        x3 = vfmaq_f64(x3, multiplier, addend);   \
        x4 = vfmaq_f64(x4, multiplier, addend);   \
        x5 = vfmaq_f64(x5, multiplier, addend);   \
        x6 = vfmaq_f64(x6, multiplier, addend);   \
        x7 = vfmaq_f64(x7, multiplier, addend);   \
        x8 = vfmaq_f64(x8, multiplier, addend);   \
        x9 = vfmaq_f64(x9, multiplier, addend);   \
        x10 = vfmaq_f64(x10, multiplier, addend); \
        x11 = vfmaq_f64(x11, multiplier, addend); \
    } while (0)

__attribute__((noinline))
static double kernel_v128(uint64_t steps) {
    enum { LANES = 2 };
    const float64x2_t multiplier = vdupq_n_f64(0.99999999999);
    const float64x2_t addend = vdupq_n_f64(0.00000000001);
    double total = 0.0;
    double lanes[LANES];
    for (size_t batch = 0; batch < LOGICAL_CHAINS / (ACCUMULATORS * LANES); ++batch) {
        const size_t base = batch * ACCUMULATORS * LANES;
        DECLARE_NEON_REGS(base);
        for (uint64_t i = 0; i < steps; ++i) {
            UPDATE_NEON();
        }
#define REDUCE_NEON(x) do { vst1q_f64(lanes, (x)); total += lanes[0] + lanes[1]; } while (0)
        REDUCE_NEON(x0); REDUCE_NEON(x1); REDUCE_NEON(x2); REDUCE_NEON(x3);
        REDUCE_NEON(x4); REDUCE_NEON(x5); REDUCE_NEON(x6); REDUCE_NEON(x7);
        REDUCE_NEON(x8); REDUCE_NEON(x9); REDUCE_NEON(x10); REDUCE_NEON(x11);
#undef REDUCE_NEON
    }
    return total / (double)LOGICAL_CHAINS;
}

static int mode_supported(const char *mode) {
    return strcmp(mode, "scalar") == 0 || strcmp(mode, "v128") == 0;
}

static double run_kernel(const char *mode, uint64_t steps) {
    if (strcmp(mode, "scalar") == 0) return kernel_scalar(steps);
    if (strcmp(mode, "v128") == 0) return kernel_v128(steps);
    fprintf(stderr, "unknown mode: %s\n", mode);
    exit(2);
}

#endif

static uint64_t parse_u64(const char *text, const char *name) {
    char *end = NULL;
    errno = 0;
    unsigned long long value = strtoull(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0') {
        fprintf(stderr, "invalid %s: %s\n", name, text);
        exit(2);
    }
    return (uint64_t)value;
}

static int correctness_check(uint64_t steps) {
    const double reference = kernel_scalar(steps);
    const char *modes[] = {"scalar", "v128", "v256", "v512"};
    const size_t count = sizeof(modes) / sizeof(modes[0]);
    int checked = 0;

    for (size_t i = 0; i < count; ++i) {
        if (!mode_supported(modes[i])) continue;
        const double got = run_kernel(modes[i], steps);
        const double abs_error = fabs(got - reference);
        const double tolerance = 64.0 * 0x1p-52 * fmax(1.0, fabs(reference));
        printf("CHECK\t%s\t%.17g\t%.17g\t%.17g\n", modes[i], got, reference, abs_error);
        if (!isfinite(got) || abs_error > tolerance) {
            fprintf(stderr, "correctness mismatch for %s: error %.17g > tolerance %.17g\n",
                    modes[i], abs_error, tolerance);
            return 1;
        }
        ++checked;
    }
    return checked >= 2 ? 0 : 1;
}

int main(int argc, char **argv) {
    initialize_values();

    if (argc == 2 && strcmp(argv[1], "--list") == 0) {
#if defined(__x86_64__)
        const char *modes[] = {"scalar", "v128", "v256", "v512"};
#else
        const char *modes[] = {"scalar", "v128"};
#endif
        for (size_t i = 0; i < sizeof(modes) / sizeof(modes[0]); ++i) {
            if (mode_supported(modes[i])) printf("%s\n", modes[i]);
        }
        return 0;
    }
    if ((argc == 2 || argc == 3) && strcmp(argv[1], "--check") == 0) {
        const uint64_t steps = argc == 3 ? parse_u64(argv[2], "check steps") : UINT64_C(10007);
        if (steps == 0) {
            fprintf(stderr, "check steps must be positive\n");
            return 2;
        }
        return correctness_check(steps);
    }
    if (argc != 4) {
        fprintf(stderr, "usage: %s MODE STEPS WARMUP_STEPS\n", argv[0]);
        return 2;
    }

    const char *mode = argv[1];
    const uint64_t steps = parse_u64(argv[2], "steps");
    const uint64_t warmup_steps = parse_u64(argv[3], "warmup_steps");
    if (steps == 0 || !mode_supported(mode)) {
        fprintf(stderr, "unsupported mode or zero steps: %s\n", mode);
        return 2;
    }

    const uint64_t warm_start = monotonic_raw_ns();
    result_sink = run_kernel(mode, warmup_steps);
    const uint64_t warm_end = monotonic_raw_ns();
    const uint64_t main_start = monotonic_raw_ns();
    const double result = run_kernel(mode, steps);
    const uint64_t main_end = monotonic_raw_ns();
    result_sink = result;

    printf("RESULT\t%s\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%.17g\t%d\n",
           mode, steps, warm_end - warm_start, main_end - main_start, result, sched_getcpu());
    return isfinite(result) ? 0 : 1;
}
