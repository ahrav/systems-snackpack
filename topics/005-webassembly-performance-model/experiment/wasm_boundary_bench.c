#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include <wasm.h>
#include <wasmtime.h>

static const uint64_t MULTIPLIER = UINT64_C(6364136223846793005);
static const uint64_t INCREMENT = UINT64_C(1442695040888963407);

static uint64_t monotonic_ns(void) {
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC_RAW, &ts) != 0) {
    perror("clock_gettime");
    exit(1);
  }
  return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

static void fail_wasmtime(const char *where, wasmtime_error_t *error,
                          wasm_trap_t *trap) {
  fprintf(stderr, "failure=%s\n", where);
  wasm_byte_vec_t message;
  if (error != NULL) {
    wasmtime_error_message(error, &message);
    wasmtime_error_delete(error);
  } else if (trap != NULL) {
    wasm_trap_message(trap, &message);
    wasm_trap_delete(trap);
  } else {
    fprintf(stderr, "no Wasmtime error or trap object\n");
    exit(1);
  }
  fprintf(stderr, "%.*s\n", (int)message.size, message.data);
  wasm_byte_vec_delete(&message);
  exit(1);
}

static wasm_byte_vec_t read_file(const char *path) {
  FILE *file = fopen(path, "rb");
  if (file == NULL) {
    perror(path);
    exit(1);
  }
  if (fseek(file, 0, SEEK_END) != 0) {
    perror("fseek");
    exit(1);
  }
  long end = ftell(file);
  if (end < 0) {
    perror("ftell");
    exit(1);
  }
  rewind(file);
  wasm_byte_vec_t bytes;
  wasm_byte_vec_new_uninitialized(&bytes, (size_t)end);
  if (bytes.size != 0 && fread(bytes.data, bytes.size, 1, file) != 1) {
    perror("fread");
    exit(1);
  }
  fclose(file);
  return bytes;
}

static void write_bytes(const char *path, const char *data, size_t size) {
  FILE *file = fopen(path, "wb");
  if (file == NULL) {
    perror(path);
    exit(1);
  }
  if (size != 0 && fwrite(data, size, 1, file) != 1) {
    perror("fwrite");
    exit(1);
  }
  if (fclose(file) != 0) {
    perror("fclose");
    exit(1);
  }
}

struct callback_state {
  uint64_t calls;
};

static wasm_trap_t *host_step(void *env, wasmtime_caller_t *caller,
                              const wasmtime_val_t *args, size_t nargs,
                              wasmtime_val_t *results, size_t nresults) {
  (void)caller;
  // Wasmtime enforces the wasm_functype_new_1_1(i64, i64) signature before
  // dispatch; these unconditional checks guard the contract even in builds
  // that define NDEBUG, where assert() would compile away.
  if (nargs != 1 || nresults != 1 || args[0].kind != WASMTIME_I64) {
    static const char message[] = "host_step signature contract violated";
    return wasmtime_trap_new(message, sizeof(message) - 1);
  }
  struct callback_state *state = env;
  state->calls++;
  uint64_t x = (uint64_t)args[0].of.i64;
  results[0].kind = WASMTIME_I64;
  results[0].of.i64 = (int64_t)(x * MULTIPLIER + INCREMENT);
  return NULL;
}

static uint64_t expected_result(uint64_t iterations, uint64_t x) {
  for (uint64_t i = 0; i < iterations; i++) {
    x = x * MULTIPLIER + INCREMENT;
  }
  return x;
}

static uint64_t invoke_loop(wasmtime_context_t *context,
                            const wasmtime_func_t *function,
                            uint64_t iterations, uint64_t seed,
                            uint64_t *elapsed_ns) {
  wasmtime_val_t args[2];
  args[0].kind = WASMTIME_I64;
  args[0].of.i64 = (int64_t)iterations;
  args[1].kind = WASMTIME_I64;
  args[1].of.i64 = (int64_t)seed;
  wasmtime_val_t result;
  wasm_trap_t *trap = NULL;
  uint64_t start = monotonic_ns();
  wasmtime_error_t *error = wasmtime_func_call(context, function, args, 2,
                                               &result, 1, &trap);
  uint64_t end = monotonic_ns();
  if (error != NULL || trap != NULL) {
    fail_wasmtime("wasmtime_func_call", error, trap);
  }
  if (result.kind != WASMTIME_I64) {
    fprintf(stderr, "unexpected result kind from wasmtime_func_call\n");
    exit(1);
  }
  *elapsed_ns = end - start;
  return (uint64_t)result.of.i64;
}

static uint64_t parse_u64(const char *text, const char *name) {
  errno = 0;
  char *end = NULL;
  unsigned long long value = strtoull(text, &end, 10);
  if (errno != 0 || end == text || *end != '\0') {
    fprintf(stderr, "invalid %s: %s\n", name, text);
    exit(2);
  }
  return (uint64_t)value;
}

int main(int argc, char **argv) {
  uint64_t process_start_ns = monotonic_ns();
  if (argc < 4 || argc > 5 ||
      (strcmp(argv[3], "GH") != 0 && strcmp(argv[3], "HG") != 0)) {
    fprintf(stderr,
            "usage: %s MODULE.wat ITERATIONS GH|HG [ARTIFACT_PREFIX]\n",
            argv[0]);
    return 2;
  }
  const char *wat_path = argv[1];
  uint64_t iterations = parse_u64(argv[2], "iterations");
  const char *order = argv[3];
  const char *artifact_prefix = argc == 5 ? argv[4] : NULL;
  const uint64_t seed = UINT64_C(0x0123456789abcdef);
  const uint64_t warmup_iterations = UINT64_C(100000);
  const unsigned warmup_rounds = 3;

  uint64_t t0 = monotonic_ns();
  wasm_byte_vec_t wat = read_file(wat_path);
  uint64_t wat_load_ns = monotonic_ns() - t0;

  t0 = monotonic_ns();
  wasm_byte_vec_t wasm;
  wasmtime_error_t *error =
      wasmtime_wat2wasm(wat.data, wat.size, &wasm);
  uint64_t wat_decode_ns = monotonic_ns() - t0;
  wasm_byte_vec_delete(&wat);
  if (error != NULL) {
    fail_wasmtime("wasmtime_wat2wasm", error, NULL);
  }

  wasm_config_t *config = wasm_config_new();
  if (config == NULL) {
    fprintf(stderr, "wasm_config_new returned NULL\n");
    return 1;
  }
  wasmtime_config_strategy_set(config, WASMTIME_STRATEGY_CRANELIFT);
  wasmtime_config_cranelift_opt_level_set(config, WASMTIME_OPT_LEVEL_SPEED);
  wasmtime_config_parallel_compilation_set(config, false);
  t0 = monotonic_ns();
  wasm_engine_t *engine = wasm_engine_new_with_config(config);
  uint64_t engine_create_ns = monotonic_ns() - t0;
  if (engine == NULL) {
    fprintf(stderr, "wasm_engine_new_with_config returned NULL\n");
    return 1;
  }

  // wasmtime_module_new validates the raw bytes again as part of
  // compilation; it cannot reuse this standalone pass. validate_ns
  // measures validation in isolation, compile_ns includes a second
  // validation, and cold_ready_ns includes both passes.
  t0 = monotonic_ns();
  error = wasmtime_module_validate(engine, (const uint8_t *)wasm.data,
                                   wasm.size);
  uint64_t validate_ns = monotonic_ns() - t0;
  if (error != NULL) {
    fail_wasmtime("wasmtime_module_validate", error, NULL);
  }

  t0 = monotonic_ns();
  wasmtime_module_t *module = NULL;
  error = wasmtime_module_new(engine, (const uint8_t *)wasm.data, wasm.size,
                              &module);
  uint64_t compile_ns = monotonic_ns() - t0;
  if (error != NULL) {
    fail_wasmtime("wasmtime_module_new", error, NULL);
  }

  if (artifact_prefix != NULL) {
    char wasm_path[1024];
    char cwasm_path[1024];
    if (snprintf(wasm_path, sizeof(wasm_path), "%s.wasm", artifact_prefix) >=
            (int)sizeof(wasm_path) ||
        snprintf(cwasm_path, sizeof(cwasm_path), "%s.cwasm",
                 artifact_prefix) >= (int)sizeof(cwasm_path)) {
      fprintf(stderr, "artifact path is too long\n");
      return 2;
    }
    write_bytes(wasm_path, wasm.data, wasm.size);
    wasm_byte_vec_t serialized;
    error = wasmtime_module_serialize(module, &serialized);
    if (error != NULL) {
      fail_wasmtime("wasmtime_module_serialize", error, NULL);
    }
    write_bytes(cwasm_path, serialized.data, serialized.size);
    wasm_byte_vec_delete(&serialized);
  }
  wasm_byte_vec_delete(&wasm);

  t0 = monotonic_ns();
  wasmtime_store_t *store = wasmtime_store_new(engine, NULL, NULL);
  if (store == NULL) {
    fprintf(stderr, "wasmtime_store_new returned NULL\n");
    return 1;
  }
  wasmtime_context_t *context = wasmtime_store_context(store);
  struct callback_state callback = {0};
  wasm_functype_t *host_type = wasm_functype_new_1_1(
      wasm_valtype_new_i64(), wasm_valtype_new_i64());
  wasmtime_func_t host_function;
  wasmtime_func_new(context, host_type, host_step, &callback, NULL,
                    &host_function);
  wasm_functype_delete(host_type);
  uint64_t store_import_setup_ns = monotonic_ns() - t0;

  wasmtime_extern_t import;
  import.kind = WASMTIME_EXTERN_FUNC;
  import.of.func = host_function;
  wasmtime_instance_t instance;
  wasm_trap_t *trap = NULL;
  t0 = monotonic_ns();
  error = wasmtime_instance_new(context, module, &import, 1, &instance, &trap);
  uint64_t instantiate_ns = monotonic_ns() - t0;
  if (error != NULL || trap != NULL) {
    fail_wasmtime("wasmtime_instance_new", error, trap);
  }

  t0 = monotonic_ns();
  wasmtime_extern_t guest_export;
  wasmtime_extern_t host_export;
  bool guest_ok = wasmtime_instance_export_get(
      context, &instance, "guest_loop", strlen("guest_loop"), &guest_export);
  bool host_ok = wasmtime_instance_export_get(
      context, &instance, "host_loop", strlen("host_loop"), &host_export);
  // Export lookup failure is a runtime condition, not a programmer
  // invariant; guard it unconditionally so an NDEBUG build cannot hand
  // invoke_loop an uninitialized function handle.
  if (!guest_ok || guest_export.kind != WASMTIME_EXTERN_FUNC) {
    fprintf(stderr, "guest_loop export missing or not a function\n");
    return 1;
  }
  if (!host_ok || host_export.kind != WASMTIME_EXTERN_FUNC) {
    fprintf(stderr, "host_loop export missing or not a function\n");
    return 1;
  }
  uint64_t export_lookup_ns = monotonic_ns() - t0;
  uint64_t cold_ready_ns = monotonic_ns() - process_start_ns;

  t0 = monotonic_ns();
  for (unsigned round = 0; round < warmup_rounds; round++) {
    uint64_t ignored_ns;
    uint64_t guest = invoke_loop(context, &guest_export.of.func,
                                 warmup_iterations, seed, &ignored_ns);
    uint64_t host = invoke_loop(context, &host_export.of.func,
                                warmup_iterations, seed, &ignored_ns);
    if (guest != host || guest != expected_result(warmup_iterations, seed)) {
      fprintf(stderr, "warmup correctness mismatch\n");
      return 1;
    }
  }
  uint64_t warmup_ns = monotonic_ns() - t0;
  callback.calls = 0;

  uint64_t guest_ns = 0;
  uint64_t host_ns = 0;
  uint64_t guest_result = 0;
  uint64_t host_result = 0;
  if (strcmp(order, "GH") == 0) {
    guest_result = invoke_loop(context, &guest_export.of.func, iterations, seed,
                               &guest_ns);
    host_result = invoke_loop(context, &host_export.of.func, iterations, seed,
                              &host_ns);
  } else {
    host_result = invoke_loop(context, &host_export.of.func, iterations, seed,
                              &host_ns);
    guest_result = invoke_loop(context, &guest_export.of.func, iterations, seed,
                               &guest_ns);
  }

  t0 = monotonic_ns();
  uint64_t expected = expected_result(iterations, seed);
  uint64_t native_check_ns = monotonic_ns() - t0;
  bool correct = guest_result == host_result && guest_result == expected &&
                 callback.calls == iterations;
  uint64_t process_internal_ns = monotonic_ns() - process_start_ns;

  printf("{\"schema\":1,\"order\":\"%s\",\"iterations\":%" PRIu64
         ",\"warmup_rounds\":%u,\"warmup_iterations\":%" PRIu64
         ",\"wat_load_ns\":%" PRIu64 ",\"wat_decode_ns\":%" PRIu64
         ",\"engine_create_ns\":%" PRIu64 ",\"validate_ns\":%" PRIu64
         ",\"compile_ns\":%" PRIu64
         ",\"store_import_setup_ns\":%" PRIu64
         ",\"instantiate_ns\":%" PRIu64
         ",\"export_lookup_ns\":%" PRIu64
         ",\"cold_ready_ns\":%" PRIu64 ",\"warmup_ns\":%" PRIu64
         ",\"guest_ns\":%" PRIu64 ",\"host_ns\":%" PRIu64
         ",\"native_check_ns\":%" PRIu64
         ",\"process_internal_ns\":%" PRIu64
         ",\"guest_result\":\"0x%016" PRIx64
         "\",\"host_result\":\"0x%016" PRIx64
         "\",\"expected\":\"0x%016" PRIx64
         "\",\"callback_calls\":%" PRIu64 ",\"correct\":%s}\n",
         order, iterations, warmup_rounds, warmup_iterations, wat_load_ns,
         wat_decode_ns, engine_create_ns, validate_ns, compile_ns,
         store_import_setup_ns, instantiate_ns, export_lookup_ns, cold_ready_ns,
         warmup_ns, guest_ns, host_ns, native_check_ns, process_internal_ns,
         guest_result, host_result, expected, callback.calls,
         correct ? "true" : "false");

  wasmtime_module_delete(module);
  wasmtime_store_delete(store);
  wasm_engine_delete(engine);
  return correct ? 0 : 1;
}
