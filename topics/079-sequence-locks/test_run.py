"""run.py rejects rows that do not match their command and publishes results.json only for a complete campaign."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent

FAKE = """#!{python}
import json, os, sys
mode, workload, readers, milliseconds = sys.argv[1:]
counter = os.environ.get("FAKE_COUNTER")
if counter:
    calls = int(open(counter).read() or 0) + 1
    open(counter, "w").write(str(calls))
    if calls > 10:
        sys.exit(3)
mode = {mode}
reads = {reads}
print(json.dumps(dict(mode=mode, workload=workload, readers=int(readers), seconds=int(milliseconds) / 1000,
      reads=reads, odd=0, changed=0, fallback=0, min_reader_reads=reads // 4,
      writes=0 if workload == "none" else 10, skipped_slots=0)))
"""


def fake_binary(directory, mode="mode", reads="4000"):
    """A stand-in for src/main.rs that echoes one row; `mode` and `reads` are Python expressions."""
    path = pathlib.Path(directory) / "fake-sequence-locks"
    path.write_text(FAKE.format(python=sys.executable, mode=mode, reads=reads))
    path.chmod(0o755)
    return path


def run_py(binary, destination, env=None):
    """Run run.py with PYTHONOPTIMIZE=1 so a validation that relied on assert would be stripped."""
    return subprocess.run(
        [sys.executable, str(ROOT / "run.py"), "--binary", str(binary), "--out", str(destination), "--milliseconds", "50"],
        cwd=ROOT, text=True, capture_output=True, timeout=300, check=False,
        env={"PYTHONOPTIMIZE": "1", "PATH": "/usr/bin:/bin", **(env or {})},
    )


class Runner(unittest.TestCase):
    def test_mislabeled_row_is_rejected_before_results_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "results.json"
            proc = run_py(fake_binary(tmp, mode='"seq"'), destination)
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse(destination.exists(), "a row whose echoed mode differs from the request must not be published")

    def test_zero_reads_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "results.json"
            proc = run_py(fake_binary(tmp, reads="0"), destination)
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse(destination.exists(), "a row with zero reads must not be published")

    def test_failed_campaign_leaves_no_results_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "results.json"
            counter = pathlib.Path(tmp) / "calls"
            counter.write_text("0")
            proc = run_py(fake_binary(tmp), destination, env={"FAKE_COUNTER": str(counter)})
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse(destination.exists(), "an interrupted campaign must not leave results.json")
            partial = json.loads(pathlib.Path(str(destination) + ".partial").read_text())
            self.assertEqual(len(partial), 10)

    def test_complete_campaign_publishes_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "results.json"
            proc = run_py(fake_binary(tmp), destination)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            results = json.loads(destination.read_text())
            self.assertEqual(len(results), 84)
            self.assertEqual(sum(1 for r in results if r["warmup"]), 12)
            self.assertFalse(pathlib.Path(str(destination) + ".partial").exists())
            self.assertEqual(len(proc.stdout.splitlines()), 12)


if __name__ == "__main__":
    unittest.main()
