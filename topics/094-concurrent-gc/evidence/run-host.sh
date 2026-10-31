set -eu
uname -a
if command -v lscpu >/dev/null; then lscpu; else echo "CPU model unavailable: sandbox denies sysctl; architecture reported by uname"; fi
rustc +1.93.1 --version
cargo +1.93.1 test -p topic094-concurrent-gc
cargo +1.93.1 build --release -p topic094-concurrent-gc --example probe
python3 topics/094-concurrent-gc/oracle.py target/release/examples/probe
python3 topics/094-concurrent-gc/measure.py target/release/examples/probe samples.json
