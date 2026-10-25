// Out-of-place uint32 transpose. Fixed workloads keep allocation and launch sizes bounded.
#include <cuda_runtime.h>
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <utility>
#include <vector>

#define CHECK(call) do { cudaError_t e = (call); if (e != cudaSuccess) { \
    std::fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, cudaGetErrorString(e)); \
    std::exit(1); } } while (0)

__global__ void direct(const uint32_t* a, uint32_t* b, size_t rows, size_t cols) {
    size_t x = size_t(blockIdx.x) * 32 + threadIdx.x;
    size_t y = size_t(blockIdx.y) * 32 + threadIdx.y;
    for (unsigned j = 0; j < 32; j += 8) {
        if (x < cols && y + j < rows) b[x * rows + y + j] = a[(y + j) * cols + x];
    }
}

template<int Pitch>
__global__ void tiled(const uint32_t* a, uint32_t* b, size_t rows, size_t cols) {
    __shared__ uint32_t tile[32][Pitch];
    size_t x = size_t(blockIdx.x) * 32 + threadIdx.x;
    size_t y = size_t(blockIdx.y) * 32 + threadIdx.y;
    for (unsigned j = 0; j < 32; j += 8) {
        if (x < cols && y + j < rows) tile[threadIdx.y + j][threadIdx.x] = a[(y + j) * cols + x];
    }
    // Consumers can belong to different warps; every block thread reaches this barrier.
    __syncthreads();
    x = size_t(blockIdx.y) * 32 + threadIdx.x;
    y = size_t(blockIdx.x) * 32 + threadIdx.y;
    for (unsigned j = 0; j < 32; j += 8) {
        if (x < rows && y + j < cols) b[(y + j) * rows + x] = tile[threadIdx.x][threadIdx.y + j];
    }
}

static const char* names[] = {"direct", "tiled32", "tiled33"};
static void launch(int variant, const uint32_t* a, uint32_t* b, size_t rows, size_t cols) {
    if (rows == 0 || cols == 0) return;
    dim3 block(32, 8), grid(unsigned((cols + 31) / 32), unsigned((rows + 31) / 32));
    if (variant == 0) direct<<<grid, block>>>(a, b, rows, cols);
    if (variant == 1) tiled<32><<<grid, block>>>(a, b, rows, cols);
    if (variant == 2) tiled<33><<<grid, block>>>(a, b, rows, cols);
    CHECK(cudaGetLastError());
}

static void verify(const std::vector<uint32_t>& a, const uint32_t* device,
                   size_t rows, size_t cols) {
    std::vector<uint32_t> result(a.size());
    CHECK(cudaMemcpy(result.data(), device, a.size() * sizeof(uint32_t), cudaMemcpyDeviceToHost));
    // Output-major oracle has no block, thread, or shared-memory indexing.
    for (size_t i = 0; i < result.size(); ++i) {
        if (result[i] != a[(i % rows) * cols + i / rows]) {
            std::fprintf(stderr, "mismatch rows=%zu cols=%zu index=%zu\n", rows, cols, i);
            std::exit(2);
        }
    }
}

template<typename Kernel>
static void resources(Kernel kernel, const char* name) {
    cudaFuncAttributes attr{};
    int blocks = 0;
    CHECK(cudaFuncGetAttributes(&attr, kernel));
    CHECK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&blocks, kernel, 256, 0));
    std::printf("# %s registers=%d shared=%zu active_blocks_per_sm=%d\n",
                name, attr.numRegs, attr.sharedSizeBytes, blocks);
}

int main(int argc, char** argv) {
    bool check_only = argc == 2 && std::strcmp(argv[1], "--check") == 0;
    if (argc > 1 && !check_only) {
        std::fprintf(stderr, "usage: %s [--check]\n", argv[0]);
        return 2;
    }
    int count = 0;
    CHECK(cudaGetDeviceCount(&count));
    if (count == 0) { std::fprintf(stderr, "CUDA device unavailable\n"); return 77; }
    cudaDeviceProp prop{};
    CHECK(cudaGetDeviceProperties(&prop, 0));
    int driver = 0, runtime = 0;
    CHECK(cudaDriverGetVersion(&driver));
    CHECK(cudaRuntimeGetVersion(&runtime));
    std::printf("# device=%s cc=%d.%d SMs=%d driver=%d runtime=%d nvcc=%d.%d\n",
                prop.name, prop.major, prop.minor, prop.multiProcessorCount, driver, runtime,
                __CUDACC_VER_MAJOR__, __CUDACC_VER_MINOR__);
    resources(direct, "direct"); resources(tiled<32>, "tiled32"); resources(tiled<33>, "tiled33");
    std::puts("kind,rows,cols,variant,sample,microseconds,effective_GB_s");
    std::vector<std::pair<size_t, size_t>> shapes = {{0, 0}, {0, 33}, {33, 0}, {1, 1},
        {1, 65}, {65, 1}, {31, 33}, {32, 32}, {33, 65}, {1023, 1025}, {1024, 1024}};
    if (!check_only) shapes.emplace_back(4096, 4096);
    for (auto [rows, cols] : shapes) {
        if (rows == 0 || cols == 0) {
            for (int variant = 0; variant < 3; ++variant) launch(variant, nullptr, nullptr, rows, cols);
            continue;
        }
        std::vector<uint32_t> a(rows * cols);
        for (size_t i = 0; i < a.size(); ++i) a[i] = uint32_t(i) * 2654435761u ^ uint32_t(i >> 16);
        uint32_t *da = nullptr, *db = nullptr;
        size_t bytes = a.size() * sizeof(uint32_t);
        CHECK(cudaMalloc(reinterpret_cast<void**>(&da), bytes));
        CHECK(cudaMalloc(reinterpret_cast<void**>(&db), bytes));
        CHECK(cudaMemcpy(da, a.data(), bytes, cudaMemcpyHostToDevice));
        for (int variant = 0; variant < 3; ++variant) {
            CHECK(cudaMemset(db, 0xa5, bytes));
            launch(variant, da, db, rows, cols);
            CHECK(cudaDeviceSynchronize());
            verify(a, db, rows, cols);
        }
        if (!check_only) {
            constexpr int samples = 9, batch = 50;
            std::array<std::vector<double>, 3> times;
            cudaEvent_t begin, end;
            CHECK(cudaEventCreate(&begin)); CHECK(cudaEventCreate(&end));
            for (int sample = 0; sample < samples; ++sample) {
                for (int position = 0; position < 3; ++position) {
                    int variant = (sample + position) % 3;
                    CHECK(cudaMemset(db, 0xa5, bytes));
                    for (int w = 0; w < 5; ++w) launch(variant, da, db, rows, cols);
                    CHECK(cudaDeviceSynchronize());
                    CHECK(cudaEventRecord(begin));
                    for (int repeat = 0; repeat < batch; ++repeat) launch(variant, da, db, rows, cols);
                    CHECK(cudaEventRecord(end)); CHECK(cudaEventSynchronize(end));
                    float ms = 0;
                    CHECK(cudaEventElapsedTime(&ms, begin, end));
                    verify(a, db, rows, cols);
                    double us = double(ms) * 1000 / batch;
                    times[variant].push_back(us);
                    std::printf("sample,%zu,%zu,%s,%d,%.6f,%.6f\n", rows, cols, names[variant],
                                sample, us, 2.0 * double(bytes) / (us * 1000));
                }
            }
            for (int v = 0; v < 3; ++v) {
                std::sort(times[v].begin(), times[v].end());
                std::printf("# summary rows=%zu cols=%zu variant=%s n=%d min_us=%.6f median_us=%.6f max_us=%.6f\n",
                            rows, cols, names[v], samples, times[v].front(), times[v][samples/2], times[v].back());
            }
            CHECK(cudaEventDestroy(begin)); CHECK(cudaEventDestroy(end));
        }
        CHECK(cudaFree(da)); CHECK(cudaFree(db));
    }
    std::puts("# correctness: PASS");
}
