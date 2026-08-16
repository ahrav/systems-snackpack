#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#if defined(__linux__)
#include <sched.h>
#endif

#include <zstd.h>

#if defined(__has_include)
#if __has_include(<lz4.h>)
#include <lz4.h>
#define TOPIC037_LZ4_DECLARATIONS "system-lz4-header"
#else
/*
 * Some authorized Amazon Linux hosts install the versioned LZ4 runtime but
 * not lz4-devel. These declarations are the stable public C ABI used by LZ4
 * 1.x. The host receipt records this shim, the runtime version, SONAME, path,
 * and digest. Prefer the checked system header whenever it is present.
 */
int LZ4_compressBound(int inputSize);
int LZ4_compress_default(const char *src, char *dst, int srcSize, int dstCapacity);
int LZ4_decompress_safe(const char *src, char *dst, int compressedSize, int dstCapacity);
const char *LZ4_versionString(void);
#define TOPIC037_LZ4_DECLARATIONS "documented-lz4-1.x-abi-shim"
#endif
#else
int LZ4_compressBound(int inputSize);
int LZ4_compress_default(const char *src, char *dst, int srcSize, int dstCapacity);
int LZ4_decompress_safe(const char *src, char *dst, int compressedSize, int dstCapacity);
const char *LZ4_versionString(void);
#define TOPIC037_LZ4_DECLARATIONS "documented-lz4-1.x-abi-shim"
#endif

#ifndef CLOCK_MONOTONIC_RAW
#define CLOCK_MONOTONIC_RAW CLOCK_MONOTONIC
#endif

#if defined(__GNUC__) || defined(__clang__)
#define TOPIC_NOINLINE __attribute__((noinline))
#else
#define TOPIC_NOINLINE
#endif

enum {
    RECORD_BYTES = 256,
    RECORD_COUNT = 1024,
    UNIT_HEADER_BYTES = 13,
    CODEC_RAW = 0,
    CODEC_LZ4 = 1,
    CODEC_ZSTD = 2
};

static const unsigned char UNIT_MAGIC[4] = {'C', '3', '7', 'U'};
static volatile uint64_t black_box_sink;

enum codec_kind {
    METHOD_IDENTITY,
    METHOD_LZ4,
    METHOD_ZSTD
};

struct encoded_stats {
    size_t candidate_payload_bytes;
    size_t payload_bytes;
    size_t framing_bytes;
    size_t stored_bytes;
    size_t compressed_units;
    size_t raw_units;
};

struct probe {
    enum codec_kind codec;
    const char *codec_name;
    const char *corpus_name;
    const char *shape_name;
    size_t input_bytes;
    size_t units;
    size_t unit_bytes;
    size_t encoded_capacity;
    unsigned char *input;
    unsigned char *encoded;
    unsigned char *decoded;
    ZSTD_CCtx *zstd_cctx;
    ZSTD_DCtx *zstd_dctx;
    struct encoded_stats stats;
};

static uint64_t now_ns(void) {
    struct timespec timestamp;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &timestamp) != 0) {
        perror("clock_gettime");
        exit(2);
    }
    return (uint64_t)timestamp.tv_sec * UINT64_C(1000000000) +
           (uint64_t)timestamp.tv_nsec;
}

static int observed_cpu(void) {
#if defined(__linux__)
    return sched_getcpu();
#else
    return -1;
#endif
}

static int observed_affinity_count(void) {
#if defined(__linux__)
    cpu_set_t set;
    if (sched_getaffinity(0, sizeof(set), &set) != 0) {
        return -1;
    }
    return CPU_COUNT(&set);
#else
    return -1;
#endif
}

static void compiler_barrier(void) {
#if defined(__GNUC__) || defined(__clang__)
    __asm__ __volatile__("" ::: "memory");
#endif
}

static int checked_add_size(size_t left, size_t right, size_t *result) {
    if (left > SIZE_MAX - right) {
        return -1;
    }
    *result = left + right;
    return 0;
}

static int checked_mul_size(size_t left, size_t right, size_t *result) {
    if (left != 0 && right > SIZE_MAX / left) {
        return -1;
    }
    *result = left * right;
    return 0;
}

static uint64_t splitmix64(uint64_t *state) {
    uint64_t value = (*state += UINT64_C(0x9e3779b97f4a7c15));
    value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}

static void store_u64_le(unsigned char *destination, uint64_t value) {
    for (unsigned int byte = 0; byte < 8; byte++) {
        destination[byte] = (unsigned char)(value >> (byte * 8));
    }
}

static void fill_random(unsigned char *destination, size_t length) {
    uint64_t state = UINT64_C(0x4d595df4d0f33173);
    size_t offset = 0;
    while (offset + 8 <= length) {
        store_u64_le(destination + offset, splitmix64(&state));
        offset += 8;
    }
    if (offset < length) {
        unsigned char tail[8];
        store_u64_le(tail, splitmix64(&state));
        memcpy(destination + offset, tail, length - offset);
    }
}

static void fill_structured(unsigned char *destination) {
    static const char pattern[] =
        " service=checkout level=INFO route=/v1/orders status=200 tenant=acme ";
    const size_t pattern_length = sizeof(pattern) - 1;
    for (size_t record = 0; record < RECORD_COUNT; record++) {
        unsigned char *unit = destination + record * RECORD_BYTES;
        for (size_t index = 0; index < RECORD_BYTES; index++) {
            unit[index] = (unsigned char)pattern[index % pattern_length];
        }
        char identifier[17];
        int written = snprintf(identifier, sizeof(identifier), "%016zx", record);
        if (written != 16) {
            fprintf(stderr, "record identifier formatting failed\n");
            exit(2);
        }
        memcpy(unit, identifier, 16);
    }
}

static uint64_t fnv1a64(const unsigned char *bytes, size_t length) {
    uint64_t hash = UINT64_C(14695981039346656037);
    for (size_t index = 0; index < length; index++) {
        hash ^= bytes[index];
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}

static void store_u32_le(unsigned char *destination, uint32_t value) {
    for (unsigned int byte = 0; byte < 4; byte++) {
        destination[byte] = (unsigned char)(value >> (byte * 8));
    }
}

static uint32_t load_u32_le(const unsigned char *source) {
    uint32_t value = 0;
    for (unsigned int byte = 0; byte < 4; byte++) {
        value |= (uint32_t)source[byte] << (byte * 8);
    }
    return value;
}

static int write_unit_header(unsigned char *destination,
                             unsigned char tag,
                             size_t encoded_length,
                             size_t decoded_length) {
    if (encoded_length > UINT32_MAX || decoded_length > UINT32_MAX) {
        return -1;
    }
    memcpy(destination, UNIT_MAGIC, sizeof(UNIT_MAGIC));
    destination[4] = tag;
    store_u32_le(destination + 5, (uint32_t)encoded_length);
    store_u32_le(destination + 9, (uint32_t)decoded_length);
    return 0;
}

static int parse_codec(const char *name, enum codec_kind *codec) {
    if (strcmp(name, "identity") == 0) {
        *codec = METHOD_IDENTITY;
    } else if (strcmp(name, "lz4") == 0) {
        *codec = METHOD_LZ4;
    } else if (strcmp(name, "zstd") == 0) {
        *codec = METHOD_ZSTD;
    } else {
        return -1;
    }
    return 0;
}

static int maximum_payload_bound(enum codec_kind codec,
                                 size_t unit_bytes,
                                 size_t *bound) {
    if (unit_bytes > (size_t)INT_MAX) {
        return -1;
    }
    size_t result = unit_bytes;
    if (codec == METHOD_LZ4) {
        int lz4_bound = LZ4_compressBound((int)unit_bytes);
        if (lz4_bound <= 0) {
            return -1;
        }
        if ((size_t)lz4_bound > result) {
            result = (size_t)lz4_bound;
        }
    } else if (codec == METHOD_ZSTD) {
        size_t zstd_bound = ZSTD_compressBound(unit_bytes);
        if (ZSTD_isError(zstd_bound)) {
            return -1;
        }
        if (zstd_bound > result) {
            result = zstd_bound;
        }
    }
    *bound = result;
    return 0;
}

static int setup_probe(struct probe *probe,
                       const char *codec_name,
                       const char *corpus_name,
                       const char *shape_name) {
    memset(probe, 0, sizeof(*probe));
    if (parse_codec(codec_name, &probe->codec) != 0) {
        return -1;
    }
    if (strcmp(corpus_name, "structured") != 0 && strcmp(corpus_name, "random") != 0) {
        return -1;
    }
    if (strcmp(shape_name, "independent") != 0 && strcmp(shape_name, "batch") != 0) {
        return -1;
    }
    probe->codec_name = codec_name;
    probe->corpus_name = corpus_name;
    probe->shape_name = shape_name;
    probe->input_bytes = (size_t)RECORD_COUNT * RECORD_BYTES;
    probe->units = strcmp(shape_name, "independent") == 0 ? RECORD_COUNT : 1;
    probe->unit_bytes = probe->input_bytes / probe->units;

    size_t payload_bound;
    size_t unit_capacity;
    if (maximum_payload_bound(probe->codec, probe->unit_bytes, &payload_bound) != 0 ||
        checked_add_size(UNIT_HEADER_BYTES, payload_bound, &unit_capacity) != 0 ||
        checked_mul_size(probe->units, unit_capacity, &probe->encoded_capacity) != 0) {
        return -1;
    }

    probe->input = malloc(probe->input_bytes);
    probe->encoded = malloc(probe->encoded_capacity);
    probe->decoded = malloc(probe->input_bytes);
    if (probe->codec == METHOD_ZSTD) {
        probe->zstd_cctx = ZSTD_createCCtx();
        probe->zstd_dctx = ZSTD_createDCtx();
    }
    if (probe->input == NULL || probe->encoded == NULL || probe->decoded == NULL ||
        (probe->codec == METHOD_ZSTD &&
         (probe->zstd_cctx == NULL || probe->zstd_dctx == NULL))) {
        return -1;
    }
    if (strcmp(corpus_name, "structured") == 0) {
        fill_structured(probe->input);
    } else {
        fill_random(probe->input, probe->input_bytes);
    }
    return 0;
}

static void destroy_probe(struct probe *probe) {
    ZSTD_freeCCtx(probe->zstd_cctx);
    ZSTD_freeDCtx(probe->zstd_dctx);
    free(probe->decoded);
    free(probe->encoded);
    free(probe->input);
    memset(probe, 0, sizeof(*probe));
}

static int encode_identity_units(struct probe *probe, struct encoded_stats *stats) {
    size_t cursor = 0;
    memset(stats, 0, sizeof(*stats));
    for (size_t unit = 0; unit < probe->units; unit++) {
        const unsigned char *source = probe->input + unit * probe->unit_bytes;
        if (cursor > probe->encoded_capacity - UNIT_HEADER_BYTES - probe->unit_bytes ||
            write_unit_header(probe->encoded + cursor,
                              CODEC_RAW,
                              probe->unit_bytes,
                              probe->unit_bytes) != 0) {
            return -1;
        }
        memcpy(probe->encoded + cursor + UNIT_HEADER_BYTES, source, probe->unit_bytes);
        cursor += UNIT_HEADER_BYTES + probe->unit_bytes;
        stats->candidate_payload_bytes += probe->unit_bytes;
        stats->payload_bytes += probe->unit_bytes;
        stats->raw_units++;
    }
    stats->framing_bytes = UNIT_HEADER_BYTES * probe->units;
    stats->stored_bytes = cursor;
    return 0;
}

static int encode_lz4_units(struct probe *probe, struct encoded_stats *stats) {
    size_t cursor = 0;
    memset(stats, 0, sizeof(*stats));
    int bound = LZ4_compressBound((int)probe->unit_bytes);
    if (bound <= 0) {
        return -1;
    }
    for (size_t unit = 0; unit < probe->units; unit++) {
        const unsigned char *source = probe->input + unit * probe->unit_bytes;
        if (cursor > probe->encoded_capacity - UNIT_HEADER_BYTES - (size_t)bound) {
            return -1;
        }
        unsigned char *payload = probe->encoded + cursor + UNIT_HEADER_BYTES;
        int produced = LZ4_compress_default((const char *)source,
                                            (char *)payload,
                                            (int)probe->unit_bytes,
                                            bound);
        if (produced <= 0) {
            return -1;
        }
        size_t candidate = (size_t)produced;
        stats->candidate_payload_bytes += candidate;
        unsigned char tag = CODEC_LZ4;
        size_t selected = candidate;
        if (candidate >= probe->unit_bytes) {
            tag = CODEC_RAW;
            selected = probe->unit_bytes;
            memcpy(payload, source, selected);
            stats->raw_units++;
        } else {
            stats->compressed_units++;
        }
        if (write_unit_header(probe->encoded + cursor, tag, selected, probe->unit_bytes) != 0) {
            return -1;
        }
        cursor += UNIT_HEADER_BYTES + selected;
        stats->payload_bytes += selected;
    }
    stats->framing_bytes = UNIT_HEADER_BYTES * probe->units;
    stats->stored_bytes = cursor;
    return 0;
}

static int encode_zstd_units(struct probe *probe, struct encoded_stats *stats) {
    size_t cursor = 0;
    memset(stats, 0, sizeof(*stats));
    size_t bound = ZSTD_compressBound(probe->unit_bytes);
    if (ZSTD_isError(bound)) {
        return -1;
    }
    for (size_t unit = 0; unit < probe->units; unit++) {
        const unsigned char *source = probe->input + unit * probe->unit_bytes;
        if (cursor > probe->encoded_capacity - UNIT_HEADER_BYTES - bound) {
            return -1;
        }
        unsigned char *payload = probe->encoded + cursor + UNIT_HEADER_BYTES;
        size_t candidate = ZSTD_compressCCtx(probe->zstd_cctx,
                                             payload,
                                             bound,
                                             source,
                                             probe->unit_bytes,
                                             1);
        if (ZSTD_isError(candidate)) {
            return -1;
        }
        stats->candidate_payload_bytes += candidate;
        unsigned char tag = CODEC_ZSTD;
        size_t selected = candidate;
        if (candidate >= probe->unit_bytes) {
            tag = CODEC_RAW;
            selected = probe->unit_bytes;
            memcpy(payload, source, selected);
            stats->raw_units++;
        } else {
            stats->compressed_units++;
        }
        if (write_unit_header(probe->encoded + cursor, tag, selected, probe->unit_bytes) != 0) {
            return -1;
        }
        cursor += UNIT_HEADER_BYTES + selected;
        stats->payload_bytes += selected;
    }
    stats->framing_bytes = UNIT_HEADER_BYTES * probe->units;
    stats->stored_bytes = cursor;
    return 0;
}

TOPIC_NOINLINE int topic037_encode_all(struct probe *probe) {
    int result;
    switch (probe->codec) {
    case METHOD_IDENTITY:
        result = encode_identity_units(probe, &probe->stats);
        break;
    case METHOD_LZ4:
        result = encode_lz4_units(probe, &probe->stats);
        break;
    case METHOD_ZSTD:
        result = encode_zstd_units(probe, &probe->stats);
        break;
    default:
        result = -1;
        break;
    }
    compiler_barrier();
    return result;
}

static int decode_identity_payload(const unsigned char *payload,
                                   size_t payload_length,
                                   unsigned char *destination,
                                   size_t decoded_length) {
    if (payload_length != decoded_length) {
        return -1;
    }
    memcpy(destination, payload, decoded_length);
    return 0;
}

TOPIC_NOINLINE int topic037_decode_all(struct probe *probe) {
    size_t input_cursor = 0;
    size_t output_cursor = 0;
    for (size_t unit = 0; unit < probe->units; unit++) {
        if (input_cursor > probe->stats.stored_bytes ||
            probe->stats.stored_bytes - input_cursor < UNIT_HEADER_BYTES) {
            return -1;
        }
        const unsigned char *header = probe->encoded + input_cursor;
        if (memcmp(header, UNIT_MAGIC, sizeof(UNIT_MAGIC)) != 0) {
            return -1;
        }
        unsigned char tag = header[4];
        size_t payload_length = load_u32_le(header + 5);
        size_t decoded_length = load_u32_le(header + 9);
        if (decoded_length != probe->unit_bytes ||
            payload_length > probe->stats.stored_bytes - input_cursor - UNIT_HEADER_BYTES ||
            decoded_length > probe->input_bytes - output_cursor) {
            return -1;
        }
        const unsigned char *payload = header + UNIT_HEADER_BYTES;
        unsigned char *destination = probe->decoded + output_cursor;
        int result = -1;
        if (tag == CODEC_RAW) {
            result = decode_identity_payload(payload, payload_length, destination, decoded_length);
        } else if (tag == CODEC_LZ4 && probe->codec == METHOD_LZ4 &&
                   payload_length <= (size_t)INT_MAX && decoded_length <= (size_t)INT_MAX) {
            int produced = LZ4_decompress_safe((const char *)payload,
                                               (char *)destination,
                                               (int)payload_length,
                                               (int)decoded_length);
            result = produced == (int)decoded_length ? 0 : -1;
        } else if (tag == CODEC_ZSTD && probe->codec == METHOD_ZSTD) {
            size_t frame_size = ZSTD_findFrameCompressedSize(payload, payload_length);
            if (!ZSTD_isError(frame_size) && frame_size == payload_length) {
                size_t produced = ZSTD_decompressDCtx(probe->zstd_dctx,
                                                      destination,
                                                      decoded_length,
                                                      payload,
                                                      payload_length);
                result = !ZSTD_isError(produced) && produced == decoded_length ? 0 : -1;
            }
        }
        if (result != 0) {
            return -1;
        }
        input_cursor += UNIT_HEADER_BYTES + payload_length;
        output_cursor += decoded_length;
    }
    compiler_barrier();
    return input_cursor == probe->stats.stored_bytes && output_cursor == probe->input_bytes ? 0 : -1;
}

static int round_trip(struct probe *probe) {
    return topic037_encode_all(probe) == 0 && topic037_decode_all(probe) == 0 &&
                   memcmp(probe->input, probe->decoded, probe->input_bytes) == 0
               ? 0
               : -1;
}

static int measure_encode(struct probe *probe, uint64_t repetitions, uint64_t *elapsed_ns) {
    uint64_t start = now_ns();
    for (uint64_t repetition = 0; repetition < repetitions; repetition++) {
        if (topic037_encode_all(probe) != 0) {
            return -1;
        }
        black_box_sink ^= (uint64_t)probe->stats.stored_bytes + repetition;
    }
    *elapsed_ns = now_ns() - start;
    return 0;
}

static int measure_decode(struct probe *probe, uint64_t repetitions, uint64_t *elapsed_ns) {
    uint64_t start = now_ns();
    for (uint64_t repetition = 0; repetition < repetitions; repetition++) {
        if (topic037_decode_all(probe) != 0) {
            return -1;
        }
        black_box_sink ^= probe->decoded[repetition % probe->input_bytes] + repetition;
    }
    *elapsed_ns = now_ns() - start;
    return 0;
}

static int parse_positive_u64(const char *text, uint64_t *value) {
    if (*text == '\0') {
        return -1;
    }
    for (const char *cursor = text; *cursor != '\0'; cursor++) {
        if (*cursor < '0' || *cursor > '9') {
            return -1;
        }
    }
    char *end = NULL;
    errno = 0;
    unsigned long long parsed = strtoull(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || parsed == 0) {
        return -1;
    }
    *value = (uint64_t)parsed;
    return 0;
}

static int calibrate_phase(struct probe *probe,
                           const char *phase,
                           uint64_t target_ms,
                           uint64_t *repetitions) {
    uint64_t count = 1;
    uint64_t elapsed = 0;
    for (;;) {
        int result = strcmp(phase, "encode") == 0
                         ? measure_encode(probe, count, &elapsed)
                         : measure_decode(probe, count, &elapsed);
        if (result != 0) {
            return -1;
        }
        if (elapsed >= UINT64_C(10000000) || count >= (UINT64_C(1) << 32)) {
            break;
        }
        count *= 2;
    }
    uint64_t target_ns = target_ms > UINT64_MAX / UINT64_C(1000000)
                             ? UINT64_MAX
                             : target_ms * UINT64_C(1000000);
    __uint128_t scaled = (__uint128_t)count * target_ns / (elapsed == 0 ? 1 : elapsed);
    if (scaled == 0) {
        scaled = 1;
    }
    if (scaled > UINT32_MAX) {
        scaled = UINT32_MAX;
    }
    *repetitions = (uint64_t)scaled;
    return 0;
}

static int load_repetitions(const char *path,
                            const char *codec,
                            const char *corpus,
                            const char *shape,
                            uint64_t *encode_reps,
                            uint64_t *decode_reps) {
    FILE *stream = fopen(path, "r");
    if (stream == NULL) {
        return -1;
    }
    char line[512];
    unsigned int matches = 0;
    while (fgets(line, sizeof(line), stream) != NULL) {
        char row_codec[32];
        char row_corpus[32];
        char row_shape[32];
        char row_phase[32];
        char repetitions_text[64];
        int consumed = 0;
        if (sscanf(line,
                   "%31[^\t]\t%31[^\t]\t%31[^\t]\t%31[^\t]\t%63s %n",
                   row_codec,
                   row_corpus,
                   row_shape,
                   row_phase,
                   repetitions_text,
                   &consumed) != 5 ||
            line[consumed] != '\0') {
            fclose(stream);
            return -1;
        }
        if (strcmp(row_codec, codec) == 0 && strcmp(row_corpus, corpus) == 0 &&
            strcmp(row_shape, shape) == 0) {
            uint64_t value;
            if (parse_positive_u64(repetitions_text, &value) != 0 || value > UINT32_MAX) {
                fclose(stream);
                return -1;
            }
            if (strcmp(row_phase, "encode") == 0 && (*encode_reps == 0)) {
                *encode_reps = value;
                matches++;
            } else if (strcmp(row_phase, "decode") == 0 && (*decode_reps == 0)) {
                *decode_reps = value;
                matches++;
            } else {
                fclose(stream);
                return -1;
            }
        }
    }
    int close_result = fclose(stream);
    return close_result == 0 && matches == 2 ? 0 : -1;
}

static int verify_contract(void) {
    static const char *codecs[] = {"identity", "lz4", "zstd"};
    static const char *corpora[] = {"structured", "random"};
    static const char *shapes[] = {"independent", "batch"};
    size_t checks = 0;
    for (size_t codec = 0; codec < 3; codec++) {
        for (size_t corpus = 0; corpus < 2; corpus++) {
            for (size_t shape = 0; shape < 2; shape++) {
                struct probe probe;
                if (setup_probe(&probe, codecs[codec], corpora[corpus], shapes[shape]) != 0 ||
                    round_trip(&probe) != 0) {
                    fprintf(stderr, "round trip failed for %s/%s/%s\n",
                            codecs[codec], corpora[corpus], shapes[shape]);
                    return 1;
                }
                if (probe.stats.framing_bytes != UNIT_HEADER_BYTES * probe.units ||
                    probe.stats.stored_bytes !=
                        probe.stats.payload_bytes + probe.stats.framing_bytes) {
                    fprintf(stderr, "framing accounting failed\n");
                    return 1;
                }
                size_t saved_length = probe.stats.stored_bytes;
                probe.stats.stored_bytes--;
                if (topic037_decode_all(&probe) == 0) {
                    fprintf(stderr, "truncated container was accepted\n");
                    return 1;
                }
                probe.stats.stored_bytes = saved_length;
                unsigned char saved_magic = probe.encoded[0];
                probe.encoded[0] ^= 1;
                if (topic037_decode_all(&probe) == 0) {
                    fprintf(stderr, "corrupt unit header was accepted\n");
                    return 1;
                }
                probe.encoded[0] = saved_magic;
                if (probe.units == 1 && probe.encoded[4] == CODEC_ZSTD &&
                    probe.stats.stored_bytes < probe.encoded_capacity) {
                    uint32_t payload_length = load_u32_le(probe.encoded + 5);
                    probe.encoded[probe.stats.stored_bytes] = 0;
                    store_u32_le(probe.encoded + 5, payload_length + 1);
                    probe.stats.stored_bytes++;
                    if (topic037_decode_all(&probe) == 0) {
                        fprintf(stderr, "zstd frame with trailing payload bytes was accepted\n");
                        return 1;
                    }
                    probe.stats.stored_bytes--;
                    store_u32_le(probe.encoded + 5, payload_length);
                }
                destroy_probe(&probe);
                checks++;
            }
        }
    }
    printf("CHECK=PASS cases=%zu unit_header_bytes=%d lz4_declarations=%s "
           "zstd_version=%s lz4_version=%s\n",
           checks,
           UNIT_HEADER_BYTES,
           TOPIC037_LZ4_DECLARATIONS,
           ZSTD_versionString(),
           LZ4_versionString());
    return 0;
}

static int run_calibration(int argc, char **argv) {
    if (argc != 7 || (strcmp(argv[5], "encode") != 0 && strcmp(argv[5], "decode") != 0)) {
        return -1;
    }
    uint64_t target_ms;
    if (parse_positive_u64(argv[6], &target_ms) != 0) {
        return -1;
    }
    struct probe probe;
    if (setup_probe(&probe, argv[2], argv[3], argv[4]) != 0 || round_trip(&probe) != 0) {
        return 1;
    }
    uint64_t repetitions;
    int result = calibrate_phase(&probe, argv[5], target_ms, &repetitions);
    destroy_probe(&probe);
    if (result != 0) {
        return 1;
    }
    printf("reps=%" PRIu64 "\n", repetitions);
    return 0;
}

static int run_process(int argc, char **argv, uint64_t main_start_ns) {
    if (argc != 6) {
        return -1;
    }
    struct probe probe;
    if (setup_probe(&probe, argv[2], argv[3], argv[4]) != 0 || round_trip(&probe) != 0) {
        return 1;
    }
    uint64_t encode_reps = 0;
    uint64_t decode_reps = 0;
    if (load_repetitions(argv[5], argv[2], argv[3], argv[4],
                         &encode_reps, &decode_reps) != 0) {
        destroy_probe(&probe);
        return 1;
    }
    uint64_t setup_ns = now_ns() - main_start_ns;
    int cpu_before = observed_cpu();
    int affinity_count_before = observed_affinity_count();
    uint64_t encode_elapsed_ns;
    uint64_t decode_elapsed_ns;
    if (measure_encode(&probe, encode_reps, &encode_elapsed_ns) != 0 ||
        measure_decode(&probe, decode_reps, &decode_elapsed_ns) != 0) {
        destroy_probe(&probe);
        return 1;
    }
    int cpu_after = observed_cpu();
    int affinity_count_after = observed_affinity_count();
    int verified = memcmp(probe.input, probe.decoded, probe.input_bytes) == 0;
    uint64_t input_checksum = fnv1a64(probe.input, probe.input_bytes);
    uint64_t decoded_checksum = fnv1a64(probe.decoded, probe.input_bytes);
    uint64_t encoded_checksum = fnv1a64(probe.encoded, probe.stats.stored_bytes);
    double encode_ns_per_byte =
        (double)encode_elapsed_ns / ((double)encode_reps * (double)probe.input_bytes);
    double decode_ns_per_byte =
        (double)decode_elapsed_ns / ((double)decode_reps * (double)probe.input_bytes);
    double encode_mib_s = 1000000000.0 / encode_ns_per_byte / 1048576.0;
    double decode_mib_s = 1000000000.0 / decode_ns_per_byte / 1048576.0;
    printf("{\"pid\":%ld,\"codec\":\"%s\",\"corpus\":\"%s\","
           "\"shape\":\"%s\",\"record_count\":%d,\"record_bytes\":%d,"
           "\"input_bytes\":%zu,\"units\":%zu,\"unit_bytes\":%zu,"
           "\"encode_reps\":%" PRIu64 ",\"decode_reps\":%" PRIu64 ","
           "\"candidate_payload_bytes\":%zu,\"payload_bytes\":%zu,"
           "\"framing_bytes\":%zu,\"stored_bytes\":%zu,"
           "\"compressed_units\":%zu,\"raw_units\":%zu,"
           "\"cpu_before\":%d,\"cpu_after\":%d,"
           "\"affinity_count_before\":%d,\"affinity_count_after\":%d,"
           "\"setup_ns\":%" PRIu64 ",\"encode_elapsed_ns\":%" PRIu64 ","
           "\"decode_elapsed_ns\":%" PRIu64 ","
           "\"encode_ns_per_input_byte\":%.12f,"
           "\"decode_ns_per_input_byte\":%.12f,"
           "\"encode_mib_s\":%.9f,\"decode_mib_s\":%.9f,"
           "\"input_checksum\":\"%016" PRIx64 "\","
           "\"decoded_checksum\":\"%016" PRIx64 "\","
           "\"encoded_checksum\":\"%016" PRIx64 "\","
           "\"verified\":%s,\"identity_kind\":\"memcpy-control\","
           "\"lz4_raw_framing\":\"13-byte-C37U-tag-encoded_len-decoded_len\","
           "\"lz4_declarations\":\"%s\",\"lz4_version\":\"%s\","
           "\"zstd_version\":\"%s\",\"zstd_level\":1,"
           "\"black_box_checksum\":%" PRIu64 "}\n",
           (long)getpid(),
           probe.codec_name,
           probe.corpus_name,
           probe.shape_name,
           RECORD_COUNT,
           RECORD_BYTES,
           probe.input_bytes,
           probe.units,
           probe.unit_bytes,
           encode_reps,
           decode_reps,
           probe.stats.candidate_payload_bytes,
           probe.stats.payload_bytes,
           probe.stats.framing_bytes,
           probe.stats.stored_bytes,
           probe.stats.compressed_units,
           probe.stats.raw_units,
           cpu_before,
           cpu_after,
           affinity_count_before,
           affinity_count_after,
           setup_ns,
           encode_elapsed_ns,
           decode_elapsed_ns,
           encode_ns_per_byte,
           decode_ns_per_byte,
           encode_mib_s,
           decode_mib_s,
           input_checksum,
           decoded_checksum,
           encoded_checksum,
           verified ? "true" : "false",
           TOPIC037_LZ4_DECLARATIONS,
           LZ4_versionString(),
           ZSTD_versionString(),
           black_box_sink);
    destroy_probe(&probe);
    return verified ? 0 : 1;
}

int main(int argc, char **argv) {
    uint64_t main_start_ns = now_ns();
    if (argc == 2 && strcmp(argv[1], "startup") == 0) {
        puts("CHECK=PASS");
        return 0;
    }
    if (argc == 2 && strcmp(argv[1], "verify") == 0) {
        return verify_contract();
    }
    if (argc >= 2 && strcmp(argv[1], "calibrate") == 0) {
        int result = run_calibration(argc, argv);
        if (result >= 0) {
            return result;
        }
    } else if (argc >= 2 && strcmp(argv[1], "process") == 0) {
        int result = run_process(argc, argv, main_start_ns);
        if (result >= 0) {
            return result;
        }
    }
    fprintf(stderr,
            "usage: %s verify | startup | calibrate CODEC CORPUS SHAPE PHASE TARGET_MS | "
            "process CODEC CORPUS SHAPE CALIBRATION_TSV\n",
            argv[0]);
    return 2;
}
