#!/usr/bin/env python3
"""run.py refuses an existing campaign directory and records the inherited affinity mask."""
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile

run_py = pathlib.Path(__file__).with_name('run.py')
STUB = '''#!/usr/bin/env python3
import sys
_, mode, variant, n, workers, repeats = sys.argv
n = int(n)
print(f"{variant},{n},{workers},{repeats},{n * 0.5:.3f},{(n * (n + 1) // 2) & ((1 << 64) - 1)}")
'''


def stub(directory):
    probe = directory / 'probe'
    probe.write_text(STUB)
    probe.chmod(probe.stat().st_mode | stat.S_IXUSR)
    return probe


def runner_can_pin():
    return hasattr(os, 'sched_getaffinity') and set(range(8)).issubset(os.sched_getaffinity(0))


def test_existing_directory_is_rejected_before_any_attempt():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        out = tmp / 'results'
        out.mkdir()
        log = out / 'attempts.jsonl'
        log.write_text('{"sentinel": true}\n')
        p = subprocess.run([sys.executable, str(run_py), str(stub(tmp)), str(out)],
                           text=True, capture_output=True, timeout=300, check=False)
        assert p.returncode != 0, 'run.py reused an existing campaign directory'
        assert log.read_text() == '{"sentinel": true}\n', 'run.py appended to a prior campaign log'
        assert not (out / 'raw.csv').exists(), 'run.py overwrote raw.csv in an existing directory'


def test_fresh_campaign_records_inherited_mask():
    if not runner_can_pin():
        print('CPUs 0..7 unavailable; skipping fresh-campaign check')
        return
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        out = tmp / 'results'
        p = subprocess.run([sys.executable, str(run_py), str(stub(tmp)), str(out)],
                           text=True, capture_output=True, timeout=300, check=False)
        assert p.returncode == 0, p.stderr
        runner = json.loads((out / 'runner.json').read_text())
        assert runner['affinity'] == list(range(8))
        assert set(runner['inherited_affinity']) >= set(range(8)), runner
        assert sum(1 for _ in (out / 'attempts.jsonl').open()) == 164
        assert sum(1 for _ in (out / 'raw.csv').open()) == 165


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            print(name, 'ok')
