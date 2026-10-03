#!/bin/sh
# Run this test from the repository root.
set -eu
root=$(pwd)
expected_rustc=$(rustc -V)
# The space and quote in the scratch path exercise the runner's handling of shell-sensitive paths.
work=$(mktemp -d "${TMPDIR:-/tmp}/topic '064.XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/topics"
cp Cargo.toml Cargo.lock rust-toolchain.toml "$work/"
cp -R topics/064-kernel-bypass "$work/topics/"
cd "$work"
runner=topics/064-kernel-bypass/scripts/run-linux.sh
host=$(rustc -vV | sed -n 's/^host: //p')

sh "$runner" > /dev/null 2>&1 || { echo "FAIL: fresh run exited non-zero"; exit 1; }
[ -s evidence/contracts.s ] || { echo "FAIL: fresh run produced no evidence/contracts.s"; exit 1; }
grep -qxF "$expected_rustc" evidence/host.txt || { echo "FAIL: scratch run used a toolchain other than the checkout ($expected_rustc)"; exit 1; }
grep -q -- '-C opt-level=3' evidence/codegen.txt || { echo "FAIL: codegen.txt does not record the effective opt-level"; exit 1; }

# The target reset removes a stale .s from an earlier build and forces a rebuild that records rustc flags.
printf 'stale\n' > target/release/deps/topic064_kernel_bypass-0000000000stale.s
sh "$runner" > /dev/null 2>&1 || { echo "FAIL: rerun with a stale .s exited non-zero"; exit 1; }
grep -q -- '-C opt-level=3' evidence/codegen.txt || { echo "FAIL: rerun codegen.txt lost the rustc invocation (Fresh unit)"; exit 1; }
! grep -q '^stale$' evidence/contracts.s || { echo "FAIL: stale assembly copied into evidence"; exit 1; }
set -- target/release/deps/topic064_kernel_bypass-*.s
[ "$#" -eq 1 ] && [ -f "$1" ] || { echo "FAIL: expected exactly one candidate .s file after the run, found $#"; exit 1; }

# The runner pins its own target directory, so the assembly it inspects comes from the build it ran.
CARGO_TARGET_DIR=$work/other sh "$runner" > /dev/null 2>&1 || { echo "FAIL: run with caller CARGO_TARGET_DIR exited non-zero"; exit 1; }
[ ! -d "$work/other" ] || { echo "FAIL: caller CARGO_TARGET_DIR was used for the build"; exit 1; }
grep -q "^CARGO_TARGET_DIR=$work/target\$" evidence/host.txt || { echo "FAIL: host.txt does not record the pinned target dir"; exit 1; }

# The runner builds for the host; a caller's CARGO_BUILD_TARGET keeps artifacts out of target/<triple>/.
rm -rf target evidence
CARGO_BUILD_TARGET=$host sh "$runner" > /dev/null 2>&1 || { echo "FAIL: run with caller CARGO_BUILD_TARGET exited non-zero"; exit 1; }
[ -s evidence/contracts.s ] || { echo "FAIL: CARGO_BUILD_TARGET run produced no evidence/contracts.s"; exit 1; }
[ ! -d "target/$host" ] || { echo "FAIL: caller CARGO_BUILD_TARGET was used for the build"; exit 1; }

# Receipts record the effective optimization level when CARGO_PROFILE_RELEASE_OPT_LEVEL overrides the default.
rm -rf target evidence
CARGO_PROFILE_RELEASE_OPT_LEVEL=1 sh "$runner" > /dev/null 2>&1 || { echo "FAIL: override run exited non-zero"; exit 1; }
grep -q -- '-C opt-level=1' evidence/codegen.txt || { echo "FAIL: codegen.txt does not record the overridden opt-level"; exit 1; }
grep -q '^CARGO_PROFILE_RELEASE_OPT_LEVEL=1$' evidence/host.txt || { echo "FAIL: host.txt does not record the Cargo override"; exit 1; }

# The runner drops a caller's RUSTFLAGS alias before the build and the receipt names the dropped variables.
rm -rf target evidence
CARGO_BUILD_RUSTFLAGS='-C opt-level=1' sh "$runner" > /dev/null 2>&1 || { echo "FAIL: run with caller CARGO_BUILD_RUSTFLAGS exited non-zero"; exit 1; }
! grep -q -- '-C opt-level=1' evidence/codegen.txt || { echo "FAIL: caller CARGO_BUILD_RUSTFLAGS reached rustc"; exit 1; }
grep -q 'CARGO_BUILD_RUSTFLAGS.* unset' evidence/host.txt || { echo "FAIL: host.txt does not name the unset flag variables"; exit 1; }

# A configured build.target moves artifacts under target/<triple>/; the runner locates the assembly there.
rm -rf target evidence
mkdir -p .cargo
printf '[build]\ntarget = "%s"\n' "$host" > .cargo/config.toml
sh "$runner" > /dev/null 2>&1 || { echo "FAIL: run with configured build.target exited non-zero"; exit 1; }
[ -s evidence/contracts.s ] || { echo "FAIL: configured build.target run produced no evidence/contracts.s"; exit 1; }
rm -rf .cargo

# Back on the host layout, the stale target/<triple>/ assembly stays outside the directory the runner inspects.
sh "$runner" > /dev/null 2>&1 || { echo "FAIL: host-layout run after a configured build.target exited non-zero"; exit 1; }

# A failed replay leaves no receipts from an earlier successful run.
printf 'fn broken(' >> topics/064-kernel-bypass/src/lib.rs
if sh "$runner" > /dev/null 2>&1; then echo "FAIL: runner exited 0 with a compile error"; exit 1; fi
[ ! -e evidence/SHA256SUMS ] || { echo "FAIL: stale SHA256SUMS survived a failed replay"; exit 1; }
echo "PASS: $root/$runner rebuilds codegen each run, pins its target dir and host target, records effective build flags, and clears stale evidence"
