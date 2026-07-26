# Run-context receipts, 2026-07-26

These receipts were captured outside the hashed host bundles. The Git commit
that adds this file preserves them with the measurement records.

## Pushed source

Command:

```bash
git ls-remote origin \
  refs/heads/curriculum/topic-016-compiler-optimization-boundaries
```

Output:

```text
8b1d2d65f188a0329937789a310dca5b379e3d8f	refs/heads/curriculum/topic-016-compiler-optimization-boundaries
```

Each host cloned the repository and checked out this 40-character commit. The
collector recorded `source_commit_verification=git-checkout`. Before building,
the checked-in collector verifies `HEAD`, rejects a nonempty
`git status --porcelain`, and exits on failure. The completed bundles therefore
record a passed collector cleanliness gate, although they do not contain the
literal status output.

## x86 target resolution

The requested literal target was reprobed:

```bash
ssh -o ConnectTimeout=10 \
  dev-dsk-ahrav-2c-b89a08b3.us-west-2.amazon.com true
```

It exited 255. The substantive proxy response was:

```text
WSSH Proxy returned an error with code 403: WSSH is unable to resolve the
specified host.
```

The established replacement alias resolved before the run:

```bash
ssh -G xlg | rg '^hostname '
```

```text
hostname dev-dsk-ahrav-2c-a9191cb6.us-west-2.amazon.com
```

The host bundle redacts the hostname but records the x86 architecture, CPU,
kernel, toolchain, features, and run window from that session.
