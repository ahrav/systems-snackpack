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

# The default root sits in shared /tmp. Create it atomically: mkdir(2)
# does not follow a trailing symlink, so a successful plain mkdir is a
# fresh private directory and a pre-staged symlink cannot redirect it.
# On EEXIST, validate the surviving entry with one no-follow stat that
# captures type and owner together: an entry that is a directory owned
# by this user cannot be replaced by another account in a sticky parent,
# so the validated precondition holds for every later use of the path.
parent="$(dirname -- "$root")"
mkdir -p -- "$parent"
if ! mkdir -m 0700 -- "$root" 2>/dev/null; then
    entry="$(stat -c '%F:%u' -- "$root" 2>/dev/null)" || entry="missing"
    if [ "$entry" != "directory:$(id -u)" ]; then
        echo "refusing existing unsafe workspace root: $root ($entry)" >&2
        exit 1
    fi
    chmod 0700 -- "$root"
fi
cd "$root"
# Re-verify through the working-directory handle: '.' names the resolved
# inode, so this check cannot be raced by pathname replacement.
if [ "$(stat -c '%F:%u' .)" != "directory:$(id -u)" ]; then
    echo "workspace root resolved to a directory not owned by the current user" >&2
    exit 1
fi
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
