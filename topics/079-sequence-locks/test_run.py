"""run.py rejects rows that do not match their command and publishes results.json only for a complete campaign;
linux-run.sh refuses an existing output directory and modified build inputs."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parents[1]

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
writes = {writes}
seconds = {seconds}
fallback = {fallback}
print(json.dumps(dict(mode=mode, workload=workload, readers=int(readers), seconds=seconds,
      reads=reads, odd=0, changed=0, fallback=fallback, min_reader_reads=reads // 4,
      writes=writes, skipped_slots=0)))
"""


def fake_binary(directory, mode="mode", reads="4000", writes='0 if workload == "none" else 10', seconds="int(milliseconds) / 1000", fallback="0"):
    """A stand-in for src/main.rs that echoes one row; `mode`, `reads`, `writes`, `seconds` and `fallback` are Python expressions."""
    path = pathlib.Path(directory) / "fake-sequence-locks"
    path.write_text(FAKE.format(python=sys.executable, mode=mode, reads=reads, writes=writes, seconds=seconds, fallback=fallback))
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

    def test_writes_in_no_writer_workload_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "results.json"
            proc = run_py(fake_binary(tmp, writes="10"), destination)
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse(destination.exists(), "a `none` row reporting writes must not be published")

    def test_nonfinite_seconds_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "results.json"
            proc = run_py(fake_binary(tmp, seconds='float("nan")'), destination)
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse(destination.exists(), "a row with NaN seconds must not be published")

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

    def test_counters_impossible_for_the_mode_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "results.json"
            proc = run_py(fake_binary(tmp, fallback="5"), destination)
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse(destination.exists(), "a `seq` row reporting fallback acquisitions must not be published")

    def test_existing_results_file_is_rejected_before_any_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "results.json"
            destination.write_text("stale\n")
            proc = run_py(fake_binary(tmp), destination)
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertEqual(destination.read_text(), "stale\n")
            self.assertFalse(pathlib.Path(str(destination) + ".partial").exists(), "nothing runs while a results file occupies --out")

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
            self.assertTrue(all("skipped slots 0-0" in line for line in proc.stdout.splitlines()), proc.stdout)


class Replay(unittest.TestCase):
    def linux_run(self, script, output):
        return subprocess.run(
            ["bash", str(script), str(output)],
            cwd=REPO, text=True, capture_output=True, timeout=60, check=False,
        )

    def test_existing_output_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "campaign"
            output.mkdir()
            stale = output / "results.json"
            stale.write_text("stale\n")
            proc = self.linux_run(ROOT / "linux-run.sh", output)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertEqual(stale.read_text(), "stale\n")
            self.assertFalse((output / "host.txt").exists())

    def test_modified_build_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone = pathlib.Path(tmp) / "clone"
            subprocess.run(["git", "clone", "--quiet", "--shared", str(REPO), str(clone)], check=True, timeout=120)
            topic = clone / "topics" / "079-sequence-locks"
            (topic / "linux-run.sh").write_text((ROOT / "linux-run.sh").read_text())  # the script under test, in a clone it may dirty
            (topic / "build.rs").write_text("fn main() {}\n")
            output = pathlib.Path(tmp) / "campaign"
            proc = self.linux_run(topic / "linux-run.sh", output)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn("build.rs", proc.stderr)
            self.assertFalse(output.exists(), "nothing is written before the build inputs are verified")


if __name__ == "__main__":
    unittest.main()
