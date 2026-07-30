# PGO and post-link optimization

Profile-guided optimization turns observed execution frequencies into compiler
decisions; post-link optimization changes an already linked image using profiles
whose addresses match that image.

## Mental model

A profile is evidence about one binary, workload mix, host, and run window. The
optimization pipeline has five identities that must remain connected:

1. the binary that produced the observations;
2. the workload and weights that produced the profile;
3. the merged profile consumed by the optimizer;
4. the candidate binary emitted from that profile;
5. the deployed workload used to judge the candidate.

Instrumentation PGO adds counters at compiler-selected sites, merges the raw
profiles, and recompiles the program. Sample PGO attributes sampled instruction
addresses and call chains to compiler IR before recompilation. Both operate
before final linking and can change inlining, indirect-call promotion, branch
layout, and code placement.

BOLT consumes a linked ELF image and a matching execution profile, then rewrites
the image with final addresses available. Propeller instead asks the compiler to
emit relocatable basic-block sections and asks the linker to order those
sections from a profile. These techniques can complement compiler PGO, but a
compiler-PGO rebuild invalidates the address identity of a profile collected for
an earlier final image.

## Focused experiment

The fixture trains two instrumentation profiles for the same indirect call:
`alpha.profdata` observes only `alpha`, while `beta.profdata` observes only
`beta`. It builds one unprofiled binary, a byte-identical control copy, and one
candidate from each profile. Correctness checks compare checksums before any
timing result is retained.

Run the retained check from a clean x86-64 or AArch64 Linux checkout with
procfs, `taskset`, `lscpu`, GNU `objdump`, `nm`, and `sha256sum`:

```bash
for loader_variable in ${!LD_@} ${!GLIBC_@} ${!MALLOC_@}; do builtin unset "$loader_variable"; done
[ -z "${!LD_@}${!GLIBC_@}${!MALLOC_@}" ] || { echo "loader variables survived: ${!LD_@} ${!GLIBC_@} ${!MALLOC_@}" >&2; return 1 2>/dev/null || exit 1; }
mkdir -p -m 700 "$HOME/topic18-scratch"
/usr/bin/env -i \
  PATH="/usr/bin:/bin:$HOME/.cargo/bin" \
  HOME="$HOME" \
  TMPDIR="$HOME/topic18-scratch" \
  /usr/bin/bash -p \
  topics/018-pgo-post-link-optimization/experiment/run_remote.sh \
  "$(/usr/bin/pwd -P)" \
  /tmp/topic18-evidence
```

`TMPDIR` is named rather than defaulted because the immutable source snapshot is created
beneath it, and Cargo, rustfmt, and Clippy resolve their configuration by walking from that
snapshot to the filesystem root while the gates run. The run therefore requires every
directory on that chain to be writable only by its owner, so the configuration on the search
path cannot change under the gates. A default `/tmp` is mode 1777 and fails that: the sticky
bit prevents deleting another user's files, not creating new ones. A directory under `$HOME`
normally satisfies it, and the run refuses with the offending path if it does not.

Launch from a shell that never inherited the loader namespace. That is a requirement, not
a preference, and the loop above does not substitute for it: if this shell was itself
started with `LD_PRELOAD` or `LD_AUDIT`, that library's constructor has already run inside
it and the library is still mapped, so it can have altered shell state or can interpose
the very `unset` and `exec` that follow. Enumerating and clearing names cannot make such a
shell trustworthy — nothing running inside it can.

What the loop does is stop the variables propagating from a clean shell that merely has
them set — exported by a profile, say, without any library having been loaded into this
process. Without it, `env -i` would still be too late: `env` itself is executed with
whatever the caller had, so the loader would process the variable and run the constructor
inside `env`, before `-i` clears anything and before `bash -p` or any of the wrapper's
refusals exist. The wrapper cannot detect that, because the variable is gone from the
child by then.

The loop uses only shell builtins for the same reason. `${!LD_@}` expands to the names
currently set with that prefix, so no external program runs and there is no process for an
inherited library to be loaded into; discovering the names by piping `env` through `sed`
would execute two of them first. `builtin unset` rather than `unset`, because a shell
function of that name would otherwise answer and leave the variable in place — one more
reason the requirement above is a shell with no functions either, since `builtin` is
shadowable in turn and nothing inside the shell can settle it.

The line after the loop is what makes the clearing fail closed. `unset` cannot remove a
`readonly` variable, and it reports that without stopping the launch, so a readonly
exported `LD_PRELOAD` would survive into the `env` exec and be processed by the loader
before `-i` clears the child environment. Testing that the namespaces are empty catches
that and every other way an entry could persist, rather than trusting the loop's own
exit status.

`REPOSITORY_ROOT` is `$(/usr/bin/pwd -P)` rather than `$(pwd)` for the same reason: the
shell builtin can be shadowed by a function, which would hand the wrapper a different tree
to attest to and run unrecorded code while doing it. The absolute program also resolves
symlinks, so the wrapper receives the physical path its own containment checks compare
against.

Name `env` and `bash` by absolute path, and give `PATH` explicitly rather than
passing the caller's through. The launcher runs before the wrapper exists to check
anything, so resolving either program through an inherited `PATH` means a planted
`bash` earlier on it is what performs the isolation — which is to say none happens.
Adjust the two directories to wherever this host keeps its shell and its Rust
toolchain; the point is that the operator chooses them rather than inheriting them.
`$HOME/.cargo/bin` is on the list because `cargo`, `rustc`, `rustup`, `rustfmt`,
`clippy-driver`, and `rg` normally live there, and the run records the resolved path
and digest of every tool it uses in `tools.txt`.

Start from an empty environment rather than removing named variables. The wrapper
refuses the startup, loader, `GIT_*`, and exported-function namespaces it can see,
but a rejection is too late for anything the dynamic loader has already acted on: an
`LD_PRELOAD` library's constructor runs before the script's first line, and it can
remove its own entry from `environ`, so the in-script sweep neither prevents the code
nor reliably observes the variable. `env -i` means Bash is executed with none of it.
`-p` is what keeps the caller's exported functions out of the run — privileged mode
does not inherit functions from the environment — and it has to come from this
launcher rather than from the wrapper alone, because an exported `exec` function is
dispatched ahead of the builtin and would skip the wrapper's own restart.

`PATH` and `HOME` are the two the wrapper needs: `HOME` because rustup resolves
`RUSTUP_HOME` beneath it. Add `RUSTUP_HOME`, `EXPERIMENT_RUSTUP_TOOLCHAIN`, or the
`SOURCE_*` variables for an archive handoff only when that run needs them.

The driver selects the first CPU in the process affinity mask unless the command
passes a third `CPU` argument. Cargo gates use the repository-pinned toolchain.
The PGO build uses `EXPERIMENT_RUSTUP_TOOLCHAIN`, which defaults to `stable`, so
`rustc` and its bundled `llvm-profdata` share a profile format. The retained
receipts record the resolved compiler and LLVM versions; the driver fails when
that toolchain lacks its bundled profiler. The driver builds with `rustc -O`,
`-Ctarget-cpu=native`, `-Ccodegen-units=1`, debug information, and retained ELF
relocations. It trains each profile for 5,000,000 iterations, then uses a
recorded shuffle seed to schedule six `ABBA` and six `BAAB` blocks. Each
steady-state comparison contains 48 fresh processes with 20,000,000 timed
iterations per process.

Expected structural evidence has three parts:

- every measured binary returns the baseline checksum for `alpha`, `beta`, and
  `noop`;
- the baseline `dispatch` retains an indirect call;
- each trained `dispatch` guards a direct call to its observed target and
  retains an indirect fallback.

The experiment reports identity, trained-workload, held-out-workload,
profile-choice, and process-startup comparisons. It does not prescribe a timing
direction. Interpret a timing ratio only after checking the retained
disassembly, pre/post binary hashes, retained profiles, identity control, and
raw block orders.

See the [first-round decision record](rounds/01.md), [measurement
contract](measurements/README.md), and [primary sources](references.md).
