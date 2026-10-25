set -eu
cd /tmp/codex-topic088-20261025-7a8cc9e9def1
printf '%s  source.tar\n' 'd5a97492e3c1f800825a4581973c7966d9c58582b4e756f0ed6ebd2ba4e29c6e' | sha256sum -c -
tar -xf source.tar
printf 'source_commit: 7a8cc9e9def1c03788fa9197abd20e52827b7b08\n'
date -u +%FT%TZ
hostname
uname -sm
rustc --version
python3 --version
printf 'CUDA discovery: '
if command -v nvcc; then nvcc --version; else printf 'nvcc absent from PATH\n'; fi
if command -v nvidia-smi; then nvidia-smi -L; else printf 'nvidia-smi absent from PATH\n'; fi
for candidate in /usr/local/cuda/bin/nvcc /opt/cuda/bin/nvcc /dev/nvidiactl; do
 if test -e "$candidate"; then printf '%s present\n' "$candidate"; else printf '%s absent\n' "$candidate"; fi
done
cd topics/088-gpu-execution
sha256sum src/lib.rs examples/model.rs model.py cuda/transpose.cu
rustc --edition 2024 -D warnings --test src/lib.rs -o model-tests
./model-tests
rustc --edition 2024 -D warnings -O --crate-name gpu_execution_mechanics --crate-type rlib src/lib.rs -o libgpu_execution_mechanics.rlib
rustc --edition 2024 -D warnings -O examples/model.rs --extern gpu_execution_mechanics=libgpu_execution_mechanics.rlib -o model
./model
rustdoc --edition 2024 --test src/lib.rs --extern gpu_execution_mechanics=libgpu_execution_mechanics.rlib
python3 model.py
