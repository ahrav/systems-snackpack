#!/bin/sh
set -eu
cd "$(dirname "$0")/../../.."
selection=$(sed -n '/^cargo rustc /,/^sha256sum topics\//p' topics/061-probabilistic-filters/scripts/run-linux.sh | sed '1d;$d')
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/target/release/deps" "$tmp/evidence"
printf 'current\n' > "$tmp/target/release/deps/topic061_probabilistic_filters-new.s"
(cd "$tmp" && sh -c "$selection")
test "$(cat "$tmp/evidence/contracts.s")" = current
printf 'stale\n' > "$tmp/target/release/deps/topic061_probabilistic_filters-old.s"
if (cd "$tmp" && sh -c "$selection"); then
    echo 'assembly selection accepted two candidates' >&2
    exit 1
fi
