#!/usr/bin/env bash
set -euo pipefail

root="${WASM_TOPIC5_ROOT:-/tmp/systems-snackpack-topic-005}"
version=46.0.1
case "$(uname -m)" in
    aarch64)
        arch=aarch64
        cli_sha=071c4def2a08f0ebc95c52dfd4f2886eb697ba495804217cf76e13b09d70a1be
        c_api_sha=368406db8027c361e12ad838fb53f049b992985806bfb1256abba27112dff5ae
        ;;
    x86_64)
        arch=x86_64
        cli_sha=9ae0b17ea298bcc52277a8208d6ab7fae8e1a89579672f9d82f9d86c116edb62
        c_api_sha=4b7e7acf08467de6147f11c8fb71c4db7623035064c096976aa969d54171fed4
        ;;
    *)
        echo "unsupported architecture: $(uname -m)" >&2
        exit 1
        ;;
esac

# The default root sits in shared /tmp; refuse symlinked or foreign-owned
# workspaces and keep the tree private so another account cannot swap the
# verified archives or extracted files between verification and use.
if [ -L "$root" ]; then
    echo "refusing symlinked workspace root: $root" >&2
    exit 1
fi
mkdir -p "$root"
chmod 0700 "$root"
if [ ! -O "$root" ]; then
    echo "workspace root is not owned by the current user: $root" >&2
    exit 1
fi
cd "$root"
curl -fL --retry 3 -o wasmtime.tar.xz \
    "https://github.com/bytecodealliance/wasmtime/releases/download/v${version}/wasmtime-v${version}-${arch}-linux.tar.xz"
curl -fL --retry 3 -o wasmtime-c-api.tar.xz \
    "https://github.com/bytecodealliance/wasmtime/releases/download/v${version}/wasmtime-v${version}-${arch}-linux-c-api.tar.xz"
printf '%s  %s\n' "$cli_sha" wasmtime.tar.xz | sha256sum -c -
printf '%s  %s\n' "$c_api_sha" wasmtime-c-api.tar.xz | sha256sum -c -
tar -xJf wasmtime.tar.xz
tar -xJf wasmtime-c-api.tar.xz
# -T treats the link name as the link itself: if a previous run left a
# real directory at either name, plain -n would plant the new link inside
# it and later phases would run against stale binaries or headers. With
# -T that collision fails loudly instead.
ln -sfnT "wasmtime-v${version}-${arch}-linux" wasmtime
ln -sfnT "wasmtime-v${version}-${arch}-linux-c-api" wasmtime-c-api
./wasmtime/wasmtime --version
strings wasmtime-c-api/lib/libwasmtime.so | sed -n 's/^version: /version: /p' | head -n 1
