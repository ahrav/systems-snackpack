#ifndef __linux__
#error "Topic 25's NUMA probe is Linux-only"
#endif

#define _GNU_SOURCE

#include <dirent.h>
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <sched.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#ifndef SYS_move_pages
#error "The target Linux architecture does not expose move_pages(2)"
#endif

/* The experiment contract fixes the VMA size rather than accepting a tunable. */
#define MAPPING_BYTES (UINT64_C(512) * 1024 * 1024)
#define DEFAULT_PASSES 4
#define MAX_NODE_ID 4095
#define LIST_BUFFER_BYTES 65536

#if defined(__GNUC__) || defined(__clang__)
#define INSPECTABLE __attribute__((noinline, used, visibility("default")))
#else
#define INSPECTABLE
#endif

struct node_info {
    int id;
    int cpu;
    bool memory_allowed;
};

struct topology {
    struct node_info nodes[MAX_NODE_ID + 1];
    size_t all_count;
    size_t eligible_count;
    int first_node;
    int first_cpu;
    int second_node;
    int second_cpu;
    int distance_forward;
    int distance_reverse;
    int control_node;
    int control_cpu;
    int control_distance;
    cpu_set_t *initial_affinity;
    size_t affinity_bytes;
    int cpu_capacity;
};

struct affinity_receipt {
    int requested_cpu;
    int effective_cpu;
    int current_cpu;
    int effective_count;
};

struct placement_receipt {
    long syscall_result;
    size_t expected_pages;
    size_t other_pages;
    size_t error_pages;
};

struct smaps_receipt {
    bool exact_vma;
    bool vmflag_nohugepage;
    long anon_huge_kib;
    long kernel_page_kib;
    long mmu_page_kib;
    long thp_eligible;
};

static void die(const char *message)
{
    fprintf(stderr, "%s: %s\n", message, strerror(errno));
    exit(2);
}

static void contract_error(const char *message)
{
    fprintf(stderr, "contract error: %s\n", message);
    exit(2);
}

static char *read_text_file(const char *path)
{
    FILE *stream = fopen(path, "re");
    if (stream == NULL) {
        return NULL;
    }
    char *buffer = malloc(LIST_BUFFER_BYTES);
    if (buffer == NULL) {
        fclose(stream);
        die("malloc");
    }
    size_t length = fread(buffer, 1, LIST_BUFFER_BYTES - 1, stream);
    if (ferror(stream)) {
        int saved = errno;
        free(buffer);
        fclose(stream);
        errno = saved;
        return NULL;
    }
    buffer[length] = '\0';
    fclose(stream);
    return buffer;
}

static bool parse_id_list_contains(const char *text, int wanted)
{
    const char *cursor = text;
    while (*cursor != '\0' && *cursor != '\n') {
        while (*cursor == ' ' || *cursor == '\t' || *cursor == ',') {
            cursor++;
        }
        if (*cursor == '\0' || *cursor == '\n') {
            break;
        }
        errno = 0;
        char *end = NULL;
        long first = strtol(cursor, &end, 10);
        if (errno != 0 || end == cursor || first < 0 || first > INT_MAX) {
            return false;
        }
        long last = first;
        cursor = end;
        if (*cursor == '-') {
            cursor++;
            errno = 0;
            last = strtol(cursor, &end, 10);
            if (errno != 0 || end == cursor || last < first || last > INT_MAX) {
                return false;
            }
            cursor = end;
        }
        if ((long)wanted >= first && (long)wanted <= last) {
            return true;
        }
        if (*cursor != ',' && *cursor != '\n' && *cursor != '\0') {
            return false;
        }
    }
    return false;
}

static char *status_list(const char *field)
{
    FILE *stream = fopen("/proc/self/status", "re");
    if (stream == NULL) {
        die("open /proc/self/status");
    }
    char *line = NULL;
    size_t capacity = 0;
    char *answer = NULL;
    while (getline(&line, &capacity, stream) >= 0) {
        size_t field_length = strlen(field);
        if (strncmp(line, field, field_length) == 0 && line[field_length] == ':') {
            char *start = line + field_length + 1;
            while (*start == ' ' || *start == '\t') {
                start++;
            }
            start[strcspn(start, "\r\n")] = '\0';
            answer = strdup(start);
            break;
        }
    }
    free(line);
    fclose(stream);
    if (answer == NULL) {
        contract_error("required affinity list is absent from /proc/self/status");
    }
    return answer;
}

static int first_effective_cpu(const char *list, const struct topology *topology)
{
    for (int cpu = 0; cpu < topology->cpu_capacity; cpu++) {
        if (CPU_ISSET_S(cpu, topology->affinity_bytes, topology->initial_affinity) &&
            parse_id_list_contains(list, cpu)) {
            return cpu;
        }
    }
    return -1;
}

static int node_position(const struct topology *topology, int node_id)
{
    int position = 0;
    for (int id = 0; id <= MAX_NODE_ID; id++) {
        if (topology->nodes[id].id < 0) {
            continue;
        }
        if (id == node_id) {
            return position;
        }
        position++;
    }
    return -1;
}

static int numa_distance(const struct topology *topology, int source, int target)
{
    char path[PATH_MAX];
    if (snprintf(path, sizeof(path), "/sys/devices/system/node/node%d/distance", source) >=
        (int)sizeof(path)) {
        contract_error("distance path overflow");
    }
    char *text = read_text_file(path);
    if (text == NULL) {
        die("read NUMA distance");
    }
    int wanted_position = node_position(topology, target);
    if (wanted_position < 0) {
        contract_error("selected target node disappeared");
    }
    char *cursor = text;
    int value = -1;
    for (int position = 0; position <= wanted_position; position++) {
        while (*cursor == ' ' || *cursor == '\t' || *cursor == '\n') {
            cursor++;
        }
        errno = 0;
        char *end = NULL;
        long parsed = strtol(cursor, &end, 10);
        if (errno != 0 || end == cursor || parsed < 0 || parsed > INT_MAX) {
            free(text);
            contract_error("malformed NUMA distance row");
        }
        value = (int)parsed;
        cursor = end;
    }
    free(text);
    return value;
}

static void discover_topology(struct topology *topology)
{
    memset(topology, 0, sizeof(*topology));
    for (int id = 0; id <= MAX_NODE_ID; id++) {
        topology->nodes[id].id = -1;
        topology->nodes[id].cpu = -1;
    }

    long configured = sysconf(_SC_NPROCESSORS_CONF);
    if (configured <= 0 || configured > INT_MAX) {
        contract_error("invalid configured CPU count");
    }
    topology->cpu_capacity = (int)configured;
    topology->affinity_bytes = CPU_ALLOC_SIZE(topology->cpu_capacity);
    topology->initial_affinity = CPU_ALLOC(topology->cpu_capacity);
    if (topology->initial_affinity == NULL) {
        die("CPU_ALLOC");
    }
    CPU_ZERO_S(topology->affinity_bytes, topology->initial_affinity);
    if (sched_getaffinity(0, topology->affinity_bytes, topology->initial_affinity) != 0) {
        die("sched_getaffinity");
    }

    char *mems_allowed = status_list("Mems_allowed_list");
    for (int node = 0; node <= MAX_NODE_ID; node++) {
        char directory[PATH_MAX];
        if (snprintf(directory, sizeof(directory), "/sys/devices/system/node/node%d", node) >=
            (int)sizeof(directory)) {
            contract_error("node path overflow");
        }
        DIR *probe = opendir(directory);
        if (probe == NULL) {
            if (errno == ENOENT || errno == ENOTDIR) {
                continue;
            }
            free(mems_allowed);
            die("open NUMA node directory");
        }
        closedir(probe);
        topology->nodes[node].id = node;
        topology->nodes[node].memory_allowed = parse_id_list_contains(mems_allowed, node);
        topology->all_count++;

        char path[PATH_MAX];
        if (snprintf(path, sizeof(path), "%s/cpulist", directory) >= (int)sizeof(path)) {
            free(mems_allowed);
            contract_error("CPU-list path overflow");
        }
        char *cpulist = read_text_file(path);
        if (cpulist == NULL) {
            free(mems_allowed);
            die("read node cpulist");
        }
        topology->nodes[node].cpu = first_effective_cpu(cpulist, topology);
        free(cpulist);
        if (topology->nodes[node].cpu >= 0 && topology->nodes[node].memory_allowed) {
            topology->eligible_count++;
        }
    }
    free(mems_allowed);

    if (topology->all_count == 0) {
        contract_error("sysfs exposes no NUMA nodes");
    }
    topology->first_node = -1;
    topology->second_node = -1;
    topology->control_node = -1;
    topology->control_cpu = -1;
    for (int node = 0; node <= MAX_NODE_ID; node++) {
        if (topology->nodes[node].cpu >= 0 && topology->nodes[node].memory_allowed) {
            topology->control_node = node;
            topology->control_cpu = topology->nodes[node].cpu;
            topology->control_distance = numa_distance(topology, node, node);
            break;
        }
    }
    long best_score = -1;
    for (int first = 0; first <= MAX_NODE_ID; first++) {
        if (topology->nodes[first].cpu < 0 || !topology->nodes[first].memory_allowed) {
            continue;
        }
        for (int second = first + 1; second <= MAX_NODE_ID; second++) {
            if (topology->nodes[second].cpu < 0 || !topology->nodes[second].memory_allowed) {
                continue;
            }
            int forward = numa_distance(topology, first, second);
            int reverse = numa_distance(topology, second, first);
            long score = (long)forward + (long)reverse;
            if (score > best_score) {
                best_score = score;
                topology->first_node = first;
                topology->first_cpu = topology->nodes[first].cpu;
                topology->second_node = second;
                topology->second_cpu = topology->nodes[second].cpu;
                topology->distance_forward = forward;
                topology->distance_reverse = reverse;
            }
        }
    }
}

static struct affinity_receipt pin_to_cpu(const struct topology *topology, int cpu)
{
    cpu_set_t *requested = CPU_ALLOC(topology->cpu_capacity);
    cpu_set_t *effective = CPU_ALLOC(topology->cpu_capacity);
    if (requested == NULL || effective == NULL) {
        die("CPU_ALLOC for pinning");
    }
    CPU_ZERO_S(topology->affinity_bytes, requested);
    CPU_SET_S(cpu, topology->affinity_bytes, requested);
    if (sched_setaffinity(0, topology->affinity_bytes, requested) != 0) {
        die("sched_setaffinity");
    }
    CPU_ZERO_S(topology->affinity_bytes, effective);
    if (sched_getaffinity(0, topology->affinity_bytes, effective) != 0) {
        die("sched_getaffinity after pin");
    }
    struct affinity_receipt receipt = {
        .requested_cpu = cpu,
        .effective_cpu = -1,
        .current_cpu = sched_getcpu(),
        .effective_count = CPU_COUNT_S(topology->affinity_bytes, effective),
    };
    for (int candidate = 0; candidate < topology->cpu_capacity; candidate++) {
        if (CPU_ISSET_S(candidate, topology->affinity_bytes, effective)) {
            receipt.effective_cpu = candidate;
            break;
        }
    }
    CPU_FREE(requested);
    CPU_FREE(effective);
    if (receipt.effective_count != 1 || receipt.effective_cpu != cpu ||
        receipt.current_cpu != cpu) {
        contract_error("effective CPU affinity differs from requested singleton");
    }
    return receipt;
}

static uint64_t mix64(uint64_t value)
{
    value ^= value >> 30;
    value *= UINT64_C(0xbf58476d1ce4e5b9);
    value ^= value >> 27;
    value *= UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}

static uint64_t greatest_common_divisor(uint64_t left, uint64_t right)
{
    while (right != 0) {
        uint64_t remainder = left % right;
        left = right;
        right = remainder;
    }
    return left;
}

static uint64_t permutation_step(size_t page_count, uint64_t seed)
{
    uint64_t step = mix64(seed) % (uint64_t)page_count;
    if (step == 0) {
        step = 1;
    }
    while (greatest_common_divisor(step, (uint64_t)page_count) != 1) {
        step++;
        if (step == (uint64_t)page_count) {
            step = 1;
        }
    }
    return step;
}

INSPECTABLE uint64_t topic25_first_touch(unsigned char *mapping, size_t bytes,
                                         size_t page_size, uint64_t seed)
{
    size_t pages = bytes / page_size;
    uint64_t step = permutation_step(pages, seed);
    for (size_t page = 0; page < pages; page++) {
        uint64_t next = ((uint64_t)page + step) % (uint64_t)pages;
        memcpy(mapping + page * page_size, &next, sizeof(next));
    }
    return step;
}

INSPECTABLE uint64_t topic25_read_mapping(const unsigned char *mapping, size_t page_size,
                                          size_t page_count, unsigned passes,
                                          uint64_t start_index)
{
    uint64_t checksum = 0;
    uint64_t index = start_index;
    for (unsigned pass = 0; pass < passes; pass++) {
        for (size_t load = 0; load < page_count; load++) {
            const volatile uint64_t *slot =
                (const volatile uint64_t *)(mapping + index * page_size);
            index = *slot;
            checksum = checksum * UINT64_C(0x9e3779b185ebca87) + index;
        }
    }
    return checksum ^ index;
}

static uint64_t expected_chase(size_t page_count, unsigned passes, uint64_t step,
                               uint64_t start_index)
{
    uint64_t checksum = 0;
    uint64_t index = start_index;
    for (unsigned pass = 0; pass < passes; pass++) {
        for (size_t load = 0; load < page_count; load++) {
            index = (index + step) % (uint64_t)page_count;
            checksum = checksum * UINT64_C(0x9e3779b185ebca87) + index;
        }
    }
    return checksum ^ index;
}

static uint64_t monotonic_ns(void)
{
    struct timespec now;
#ifdef CLOCK_MONOTONIC_RAW
    const clockid_t clock_id = CLOCK_MONOTONIC_RAW;
#else
    const clockid_t clock_id = CLOCK_MONOTONIC;
#endif
    if (clock_gettime(clock_id, &now) != 0) {
        die("clock_gettime");
    }
    return (uint64_t)now.tv_sec * UINT64_C(1000000000) + (uint64_t)now.tv_nsec;
}

static struct placement_receipt query_placement(unsigned char *mapping, size_t pages,
                                                size_t page_size, int expected_node)
{
    void **addresses = calloc(pages, sizeof(*addresses));
    int *statuses = malloc(pages * sizeof(*statuses));
    if (addresses == NULL || statuses == NULL) {
        die("allocate move_pages query arrays");
    }
    for (size_t page = 0; page < pages; page++) {
        addresses[page] = mapping + page * page_size;
        statuses[page] = INT_MIN;
    }
    errno = 0;
    long result = syscall(SYS_move_pages, 0, pages, addresses, NULL, statuses, 0);
    if (result < 0) {
        free(addresses);
        free(statuses);
        die("move_pages query");
    }
    struct placement_receipt receipt = {.syscall_result = result};
    for (size_t page = 0; page < pages; page++) {
        if (statuses[page] == expected_node) {
            receipt.expected_pages++;
        } else if (statuses[page] >= 0) {
            receipt.other_pages++;
        } else {
            receipt.error_pages++;
        }
    }
    free(addresses);
    free(statuses);
    return receipt;
}

static struct smaps_receipt inspect_smaps(uintptr_t start, uintptr_t end)
{
    FILE *stream = fopen("/proc/self/smaps", "re");
    if (stream == NULL) {
        die("open /proc/self/smaps");
    }
    struct smaps_receipt receipt = {
        .anon_huge_kib = -1,
        .kernel_page_kib = -1,
        .mmu_page_kib = -1,
        .thp_eligible = -1,
    };
    char *line = NULL;
    size_t capacity = 0;
    bool in_target = false;
    while (getline(&line, &capacity, stream) >= 0) {
        unsigned long long map_start = 0;
        unsigned long long map_end = 0;
        if (sscanf(line, "%llx-%llx", &map_start, &map_end) == 2) {
            in_target = map_start == (unsigned long long)start &&
                        map_end == (unsigned long long)end;
            if (in_target) {
                receipt.exact_vma = true;
            }
            continue;
        }
        if (!in_target) {
            continue;
        }
        if (sscanf(line, "AnonHugePages: %ld kB", &receipt.anon_huge_kib) == 1 ||
            sscanf(line, "KernelPageSize: %ld kB", &receipt.kernel_page_kib) == 1 ||
            sscanf(line, "MMUPageSize: %ld kB", &receipt.mmu_page_kib) == 1 ||
            sscanf(line, "THPeligible: %ld", &receipt.thp_eligible) == 1) {
            continue;
        }
        if (strncmp(line, "VmFlags:", 8) == 0) {
            char *copy = strdup(line + 8);
            if (copy == NULL) {
                die("strdup VmFlags");
            }
            char *save = NULL;
            for (char *token = strtok_r(copy, " \t\r\n", &save); token != NULL;
                 token = strtok_r(NULL, " \t\r\n", &save)) {
                if (strcmp(token, "nh") == 0) {
                    receipt.vmflag_nohugepage = true;
                }
            }
            free(copy);
        }
    }
    free(line);
    fclose(stream);
    return receipt;
}

static void print_topology(const struct topology *topology)
{
    printf("{\"schema\":1,\"kind\":\"topology\",\"mapping_bytes\":%" PRIu64
           ",\"all_node_count\":%zu,\"eligible_node_count\":%zu,"
           "\"control_supported\":%s,\"control_node\":%d,\"control_cpu\":%d,"
           "\"control_distance\":%d,",
           MAPPING_BYTES, topology->all_count, topology->eligible_count,
           topology->eligible_count >= 1 ? "true" : "false", topology->control_node,
           topology->control_cpu, topology->control_distance);
    if (topology->eligible_count >= 2) {
        printf("\"supported\":true,\"pair_nodes\":[%d,%d],\"pair_cpus\":[%d,%d],"
               "\"pair_distances\":[%d,%d]}\n",
               topology->first_node, topology->second_node, topology->first_cpu,
               topology->second_cpu, topology->distance_forward,
               topology->distance_reverse);
    } else {
        printf("\"supported\":false,\"reason\":\"fewer-than-two-cpu-and-memory-allowed-nodes\"}\n");
    }
}

static unsigned parse_passes(const char *text)
{
    errno = 0;
    char *end = NULL;
    unsigned long parsed = strtoul(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || parsed == 0 || parsed > 1024) {
        contract_error("--passes must be in 1..1024");
    }
    return (unsigned)parsed;
}

int main(int argc, char **argv)
{
    const char *treatment = NULL;
    int direction = -1;
    unsigned passes = DEFAULT_PASSES;
    bool describe = false;
    bool control = false;
    for (int index = 1; index < argc; index++) {
        if (strcmp(argv[index], "--describe") == 0) {
            describe = true;
        } else if (strcmp(argv[index], "--control") == 0) {
            control = true;
        } else if (strcmp(argv[index], "--treatment") == 0 && index + 1 < argc) {
            treatment = argv[++index];
        } else if (strcmp(argv[index], "--direction") == 0 && index + 1 < argc) {
            const char *value = argv[++index];
            if (strcmp(value, "0") == 0) {
                direction = 0;
            } else if (strcmp(value, "1") == 0) {
                direction = 1;
            } else {
                contract_error("--direction must be 0 or 1");
            }
        } else if (strcmp(argv[index], "--passes") == 0 && index + 1 < argc) {
            passes = parse_passes(argv[++index]);
        } else {
            contract_error("usage: probe --describe | --control [--passes N] | --treatment local|remote --direction 0|1 [--passes N]");
        }
    }

    struct topology topology;
    discover_topology(&topology);
    if (describe) {
        if (argc != 2) {
            contract_error("--describe does not accept treatment arguments");
        }
        print_topology(&topology);
        CPU_FREE(topology.initial_affinity);
        return 0;
    }
    if (control && (treatment != NULL || direction >= 0)) {
        contract_error("--control cannot be combined with a treatment or direction");
    }
    if (!control && (treatment == NULL || direction < 0 ||
        (strcmp(treatment, "local") != 0 && strcmp(treatment, "remote") != 0))) {
        contract_error("a local or remote treatment and direction are required");
    }
    if (control && topology.eligible_count < 1) {
        contract_error("the control requires one CPU-and-memory-allowed NUMA node");
    }
    if (!control && topology.eligible_count < 2) {
        contract_error("the measured treatment requires two eligible NUMA nodes");
    }
    if (control) {
        treatment = "control";
        direction = 0;
    }

    long page_size_long = sysconf(_SC_PAGESIZE);
    if (page_size_long <= 0 || MAPPING_BYTES % (uint64_t)page_size_long != 0 ||
        (uint64_t)page_size_long < sizeof(uint64_t)) {
        contract_error("unsupported base page size");
    }
    size_t page_size = (size_t)page_size_long;
    size_t mapping_bytes = (size_t)MAPPING_BYTES;
    size_t page_count = mapping_bytes / page_size;
    if (mapping_bytes > SIZE_MAX - 2 * page_size) {
        contract_error("guarded mapping size overflows size_t");
    }

    int worker_node = control ? topology.control_node
                              : (direction == 0 ? topology.first_node : topology.second_node);
    int worker_cpu = control ? topology.control_cpu
                             : (direction == 0 ? topology.first_cpu : topology.second_cpu);
    int peer_node = control ? topology.control_node
                            : (direction == 0 ? topology.second_node : topology.first_node);
    int peer_cpu = control ? topology.control_cpu
                           : (direction == 0 ? topology.second_cpu : topology.first_cpu);
    int touch_node = (control || strcmp(treatment, "local") == 0) ? worker_node : peer_node;
    int touch_cpu = (control || strcmp(treatment, "local") == 0) ? worker_cpu : peer_cpu;
    int distance = (control || strcmp(treatment, "local") == 0)
                       ? numa_distance(&topology, worker_node, worker_node)
                       : (direction == 0 ? topology.distance_forward : topology.distance_reverse);
    int report_first_node = control ? topology.control_node : topology.first_node;
    int report_second_node = control ? topology.control_node : topology.second_node;
    int report_first_cpu = control ? topology.control_cpu : topology.first_cpu;
    int report_second_cpu = control ? topology.control_cpu : topology.second_cpu;
    int report_forward = control ? topology.control_distance : topology.distance_forward;
    int report_reverse = control ? topology.control_distance : topology.distance_reverse;

    size_t reserved_bytes = mapping_bytes + 2 * page_size;
    unsigned char *reserved = mmap(NULL, reserved_bytes, PROT_NONE,
                                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (reserved == MAP_FAILED) {
        die("mmap guarded reservation");
    }
    unsigned char *mapping = reserved + page_size;
    if (mprotect(mapping, mapping_bytes, PROT_READ | PROT_WRITE) != 0) {
        die("mprotect mapping");
    }
    if (madvise(mapping, mapping_bytes, MADV_NOHUGEPAGE) != 0) {
        die("madvise MADV_NOHUGEPAGE");
    }

    struct affinity_receipt touch_affinity = pin_to_cpu(&topology, touch_cpu);
    struct rusage touch_before;
    struct rusage touch_after;
    if (getrusage(RUSAGE_SELF, &touch_before) != 0) {
        die("getrusage before first touch");
    }
    uint64_t touch_started = monotonic_ns();
    const uint64_t seed = UINT64_C(0x25d06e6674957a31);
    uint64_t step = topic25_first_touch(mapping, mapping_bytes, page_size, seed);
    uint64_t touch_ns = monotonic_ns() - touch_started;
    if (getrusage(RUSAGE_SELF, &touch_after) != 0) {
        die("getrusage after first touch");
    }

    struct smaps_receipt smaps =
        inspect_smaps((uintptr_t)mapping, (uintptr_t)mapping + mapping_bytes);
    if (!smaps.exact_vma || !smaps.vmflag_nohugepage || smaps.anon_huge_kib != 0 ||
        smaps.thp_eligible != 0) {
        contract_error("smaps did not verify the exact MADV_NOHUGEPAGE VMA");
    }
    struct placement_receipt placement_before =
        query_placement(mapping, page_count, page_size, touch_node);

    struct affinity_receipt worker_affinity = pin_to_cpu(&topology, worker_cpu);
    uint64_t start_index = mix64(seed ^ UINT64_C(0xd1b54a32d192ed03)) % page_count;
    uint64_t expected_checksum =
        expected_chase(page_count, passes, step, start_index);
    struct rusage read_before;
    struct rusage read_after;
    if (getrusage(RUSAGE_SELF, &read_before) != 0) {
        die("getrusage before timed reads");
    }
    uint64_t read_started = monotonic_ns();
    uint64_t checksum =
        topic25_read_mapping(mapping, page_size, page_count, passes, start_index);
    uint64_t read_ns = monotonic_ns() - read_started;
    if (getrusage(RUSAGE_SELF, &read_after) != 0) {
        die("getrusage after timed reads");
    }
    struct placement_receipt placement_after =
        query_placement(mapping, page_count, page_size, touch_node);

    long read_minor_faults = read_after.ru_minflt - read_before.ru_minflt;
    long read_major_faults = read_after.ru_majflt - read_before.ru_majflt;
    long touch_minor_faults = touch_after.ru_minflt - touch_before.ru_minflt;
    long touch_major_faults = touch_after.ru_majflt - touch_before.ru_majflt;
    uint64_t loads = (uint64_t)page_count * passes;

    printf("{\"schema\":1,\"kind\":\"measurement\",\"treatment\":\"%s\","
           "\"direction\":%d,\"mapping_bytes\":%" PRIu64
           ",\"page_size\":%zu,\"page_count\":%zu,\"passes\":%u,"
           "\"loads\":%" PRIu64 ",\"permutation_seed\":%" PRIu64
           ",\"permutation_start\":%" PRIu64 ",\"permutation_step\":%" PRIu64
           ",\"pair_nodes\":[%d,%d],"
           "\"pair_cpus\":[%d,%d],\"pair_distances\":[%d,%d],"
           "\"worker_node\":%d,\"worker_cpu\":%d,\"touch_node\":%d,"
           "\"touch_cpu\":%d,\"peer_node\":%d,\"peer_cpu\":%d,"
           "\"access_distance\":%d,",
           treatment, direction, MAPPING_BYTES, page_size, page_count, passes, loads,
           seed, start_index, step,
           report_first_node, report_second_node, report_first_cpu,
           report_second_cpu, report_forward, report_reverse,
           worker_node, worker_cpu, touch_node, touch_cpu, peer_node, peer_cpu, distance);
    printf("\"touch_affinity\":{\"requested_cpu\":%d,\"effective_cpu\":%d,"
           "\"current_cpu\":%d,\"effective_count\":%d},"
           "\"worker_affinity\":{\"requested_cpu\":%d,\"effective_cpu\":%d,"
           "\"current_cpu\":%d,\"effective_count\":%d},",
           touch_affinity.requested_cpu, touch_affinity.effective_cpu,
           touch_affinity.current_cpu, touch_affinity.effective_count,
           worker_affinity.requested_cpu, worker_affinity.effective_cpu,
           worker_affinity.current_cpu, worker_affinity.effective_count);
    printf("\"madv_nohugepage\":true,\"smaps\":{\"exact_vma\":%s,"
           "\"vmflag_nh\":%s,\"anon_huge_kib\":%ld,\"kernel_page_kib\":%ld,"
           "\"mmu_page_kib\":%ld,\"thp_eligible\":%ld},",
           smaps.exact_vma ? "true" : "false",
           smaps.vmflag_nohugepage ? "true" : "false", smaps.anon_huge_kib,
           smaps.kernel_page_kib, smaps.mmu_page_kib, smaps.thp_eligible);
    printf("\"placement_before\":{\"syscall_result\":%ld,"
           "\"expected_pages\":%zu,\"other_pages\":%zu,\"error_pages\":%zu},"
           "\"placement_after\":{\"syscall_result\":%ld,"
           "\"expected_pages\":%zu,\"other_pages\":%zu,\"error_pages\":%zu},",
           placement_before.syscall_result, placement_before.expected_pages,
           placement_before.other_pages, placement_before.error_pages,
           placement_after.syscall_result, placement_after.expected_pages,
           placement_after.other_pages, placement_after.error_pages);
    printf("\"touch_ns\":%" PRIu64 ",\"read_ns\":%" PRIu64
           ",\"ns_per_load\":%.12f,\"touch_minor_faults\":%ld,"
           "\"touch_major_faults\":%ld,\"read_minor_faults\":%ld,"
           "\"read_major_faults\":%ld,\"checksum\":%" PRIu64
           ",\"expected_checksum\":%" PRIu64
           ",\"checksum_ok\":%s,\"read_faults_zero\":%s}\n",
           touch_ns, read_ns, (double)read_ns / (double)loads, touch_minor_faults,
           touch_major_faults, read_minor_faults, read_major_faults, checksum,
           expected_checksum, checksum == expected_checksum ? "true" : "false",
           read_minor_faults == 0 && read_major_faults == 0 ? "true" : "false");
    fflush(stdout);

    bool valid = checksum == expected_checksum && read_minor_faults == 0 &&
                 read_major_faults == 0 && placement_before.error_pages == 0 &&
                 placement_before.other_pages == 0 && placement_after.error_pages == 0 &&
                 placement_after.other_pages == 0;
    if (munmap(reserved, reserved_bytes) != 0) {
        die("munmap");
    }
    CPU_FREE(topology.initial_affinity);
    return valid ? 0 : 3;
}
