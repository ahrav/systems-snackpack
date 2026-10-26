# Primary sources

Accessed 2026-10-26. NVIDIA pages reported CUDA 13.4 or the current programming guide.

- [CUDA Best Practices, data transfers](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html#data-transfer-between-host-and-device): application cost, residency, batching and pinned-memory tradeoffs.
- [CUDA Runtime API synchronization](https://docs.nvidia.com/cuda/cuda-runtime-api/api-sync-behavior.html): asynchronous launch, pageable staging and completion boundaries.
- [CUDA asynchronous execution](https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/asynchronous-execution.html): streams, dependencies and hardware-dependent concurrency.
- [CUDA graphs](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html): definition, instantiation and repeated execution.
- [Triton batchers](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/batcher.html): batch formation delay, queue policy and request timeout controls.

The linear crossover example and fixed-duration schedule are teaching models.
Their coefficients are explicit assumptions. The CPU transform is a controlled
workload chosen for exact arithmetic and two valid execution orders.
