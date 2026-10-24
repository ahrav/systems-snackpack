#!/usr/bin/env python3
"""run.py refuses an existing campaign directory, records the inherited mask, and validates affinity and probe output under -O."""
import json
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
SWAPPED_STUB = STUB.replace('print(f"{variant},', 'variant = {"local": "rescan", "rescan": "local"}.get(variant, variant)\nprint(f"{variant},')
# A cpuset-restricted kernel answers sched_setaffinity with the intersection, which can be narrower than requested.
FAKE_KERNEL = (
    "import os, runpy, sys; state = {{'cpus': {before}}}; "
    "os.sched_getaffinity = lambda pid: set(state['cpus']); "
    "os.sched_setaffinity = lambda pid, mask: state.update(cpus={after}); "
    "sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')"
)
EIGHT = 'set(range(8))'


def stub(directory, text=STUB):
    probe = directory / 'probe'
    probe.write_text(text)
    probe.chmod(probe.stat().st_mode | stat.S_IXUSR)
    return probe


def run(out, probe, *, before=EIGHT, after=EIGHT, flags=('-O',)):
    code = FAKE_KERNEL.format(before=before, after=after)
    return subprocess.run([sys.executable, *flags, '-c', code, str(run_py), str(probe), str(out)],
                          text=True, capture_output=True, timeout=300, check=False)


def test_reduced_inherited_cpuset_is_rejected_without_asserts():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        out = tmp / 'results'
        p = run(out, stub(tmp), before='{0, 1, 2, 3}', after='{0, 1, 2, 3}')
        assert p.returncode != 0, 'run.py measured on four CPUs while the design declares eight'
        assert 'CPUs 0..7 must all be allowed' in p.stderr, p.stderr
        assert not (out / 'raw.csv').exists(), 'run.py collected measurements under a reduced CPU set'


def test_intersected_pinning_is_rejected_without_asserts():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        out = tmp / 'results'
        p = run(out, stub(tmp), before=EIGHT, after='{0, 1, 2, 3}')
        assert p.returncode != 0, 'run.py measured after the kernel narrowed the requested mask'
        assert 'pinning left affinity' in p.stderr, p.stderr
        assert not (out / 'raw.csv').exists()


def test_mislabeled_probe_output_is_rejected_without_asserts():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        out = tmp / 'results'
        p = run(out, stub(tmp, SWAPPED_STUB))
        assert p.returncode != 0, 'run.py accepted probe output labeled with another variant'
        failure = json.loads((out / 'failure.json').read_text())
        assert 'does not describe' in failure['error'], failure


def test_existing_directory_is_rejected_before_any_attempt():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        out = tmp / 'results'
        out.mkdir()
        log = out / 'attempts.jsonl'
        log.write_text('{"sentinel": true}\n')
        p = run(out, stub(tmp), flags=())
        assert p.returncode != 0, 'run.py reused an existing campaign directory'
        assert 'FileExistsError' in p.stderr, p.stderr
        assert log.read_text() == '{"sentinel": true}\n', 'run.py appended to a prior campaign log'
        assert not (out / 'raw.csv').exists(), 'run.py overwrote raw.csv in an existing directory'


def test_fresh_campaign_records_inherited_mask():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        out = tmp / 'results'
        p = run(out, stub(tmp), before='set(range(16))', flags=())
        assert p.returncode == 0, p.stderr
        runner = json.loads((out / 'runner.json').read_text())
        assert runner['inherited_affinity'] == list(range(16)), runner
        assert runner['affinity'] == list(range(8)), runner
        assert sum(1 for _ in (out / 'attempts.jsonl').open()) == 164
        assert sum(1 for _ in (out / 'raw.csv').open()) == 165


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            print(name, 'ok')
