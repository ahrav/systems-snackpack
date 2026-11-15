#!/bin/sh
set -eu
uname -a
rustc +1.93.1 --version
python3 --version
cargo +1.93.1 test -p topic109-pidfd
cargo +1.93.1 run --release -p topic109-pidfd --example oracle
if [ "$(uname -s)" = Linux ]; then
  lscpu
  cc --version
  cc -std=c11 -O2 -Wall -Wextra -Werror topics/109-pidfd/native/supervise.c -o topic109-supervise
  python3 - <<'PY'
import subprocess
subprocess.run(['./topic109-supervise'], check=True, timeout=30)
subprocess.run(['python3', 'topics/109-pidfd/examples/demo.py'], check=True, timeout=10)
PY
  rm topic109-supervise
else
  echo 'LIMIT: native pidfd checks require Linux'
fi
