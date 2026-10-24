#!/usr/bin/env python3
"""oracle.py fails on probes that answer nothing or emit malformed fields, with or without -O."""
import os
import pathlib
import stat
import subprocess
import sys
import tempfile

oracle = pathlib.Path(__file__).with_name('oracle.py')
TRAILING_COMMA_PROBE = '''#!/usr/bin/env python3
import sys
mask = (1 << 64) - 1
for line in sys.stdin:
    parts = line.split()
    xs = [int(x) for x in parts[2:]]
    prefixes = [str(sum(xs[:i]) & mask) for i in range(len(xs))]
    print(f"{sum(xs) & mask};" + ",".join(prefixes) + ",")
'''


def run_oracle(probe, *flags):
    return subprocess.run([sys.executable, *flags, str(oracle), probe],
                          text=True, capture_output=True, timeout=120, check=False)


def test_silent_probe_is_rejected_without_asserts():
    p = run_oracle('/bin/true', '-O')
    assert p.returncode != 0, p.stdout
    assert '"status": "pass"' not in p.stdout


def test_trailing_empty_field_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        probe = pathlib.Path(tmp) / 'probe'
        probe.write_text(TRAILING_COMMA_PROBE)
        probe.chmod(probe.stat().st_mode | stat.S_IXUSR)
        p = run_oracle(str(probe))
        assert p.returncode != 0, p.stdout
        assert '"status": "pass"' not in p.stdout


def test_real_probe_passes():
    probe = os.environ.get('PROBE')
    if probe is None:
        print('PROBE unset; skipping real probe check')
        return
    p = run_oracle(probe)
    assert p.returncode == 0, p.stderr
    assert '"status": "pass"' in p.stdout
    p = run_oracle(probe, '-O')
    assert p.returncode == 0, p.stderr


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            print(name, 'ok')
