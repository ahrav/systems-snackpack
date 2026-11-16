#!/bin/sh
set -eu
uname -a
rustc +1.93.1 --version
python3 --version
cargo +1.93.1 test -p topic110-path-resolution
python3 topics/110-path-resolution/examples/demo.py
if [ "$(uname -s)" = Linux ]; then
  lscpu
  cc --version
  build=$(mktemp -d)
  trap 'rm -rf "$build"' EXIT HUP INT TERM
  cc -std=c11 -O2 -Wall -Wextra -Werror -DLIBRARY_ONLY -fPIC -shared topics/110-path-resolution/native/open_report.c -o "$build/policy.so"
  cc -std=c11 -O2 -Wall -Wextra -Werror topics/110-path-resolution/native/open_report.c -o "$build/open_report"
  python3 - "$build" <<'PY'
import pathlib, subprocess, sys
from tempfile import TemporaryDirectory
build = pathlib.Path(sys.argv[1])
subprocess.run(['python3', 'topics/110-path-resolution/examples/native_oracle.py', str(build / 'policy.so')], check=True, timeout=45)
with TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / 'report').write_bytes(b'INSIDE\n')
    subprocess.run([str(build / 'open_report'), tmp, 'report'], check=True, timeout=5)
    (root / 'link').symlink_to('report')
    result = subprocess.run([str(build / 'open_report'), tmp, 'link'], timeout=5)
    assert result.returncode == 1
PY
else
  echo 'LIMIT: openat2 native checks require Linux; portable reproducer passed'
fi
