"""run.py rejects mislabeled rows and publishes results.json only for a complete campaign;
select_cpus.py searches every socket and tolerates blank topology fields;
linux-run.sh refuses an existing output directory and an unknown source commit."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from select_cpus import select_cores  # noqa: E402

FAKE = """#!{python}
import json, os, sys
mode, capacity, producers, consumers, per_producer = sys.argv[1:]
counter = os.environ.get("FAKE_COUNTER")
if counter:
    calls = int(open(counter).read() or 0) + 1
    open(counter, "w").write(str(calls))
    if calls > 10:
        sys.exit(3)
consumers = {consumers}
print(json.dumps(dict(mode=mode, capacity=int(capacity), producers=int(producers), consumers=consumers,
      per_producer=int(per_producer), jobs=int(producers) * int(per_producer), elapsed_ns=1000,
      outer_retries=0, verified=True)))
"""


def fake_binary(directory, consumers="int(consumers)"):
    """A stand-in for src/main.rs that echoes one row; `consumers` is a Python expression."""
    path = pathlib.Path(directory) / "fake-queue"
    path.write_text(FAKE.format(python=sys.executable, consumers=consumers))
    path.chmod(0o755)
    return path


def run_py(binary, destination, env=None):
    return subprocess.run(
        [sys.executable, str(ROOT / "run.py"), str(binary), str(destination)],
        cwd=ROOT, text=True, capture_output=True, timeout=300, check=False, env=env,
    )


class Runner(unittest.TestCase):
    def test_mislabeled_row_is_rejected_before_results_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "results.json"
            proc = run_py(fake_binary(tmp, consumers="1"), destination)
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse(destination.exists(), "a row whose echoed consumers differ from the request must not be published")

    def test_failed_campaign_leaves_no_results_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "results.json"
            counter = pathlib.Path(tmp) / "calls"
            counter.write_text("0")
            proc = run_py(fake_binary(tmp), destination, env={"FAKE_COUNTER": str(counter), "PATH": "/usr/bin:/bin"})
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse(destination.exists(), "an interrupted campaign must not leave results.json")
            partial = json.loads(pathlib.Path(str(destination) + ".partial").read_text())
            self.assertEqual(len(partial["rows"]), 10)
            self.assertNotIn("summary", partial)

    def test_complete_campaign_publishes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "results.json"
            proc = run_py(fake_binary(tmp), destination)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            results = json.loads(destination.read_text())
            self.assertEqual(len(results["rows"]), 56)
            self.assertEqual([c["consumers"] for c in results["summary"]], [1, 1, 4, 4])
            self.assertFalse(pathlib.Path(str(destination) + ".partial").exists())


ROWS = "# CPU,Core,Socket\n" + "\n".join(
    [f"{cpu},{cpu},0" for cpu in range(4)]
    + [f"{4 + 2 * i + t},{4 + i},1" for i in range(8) for t in range(2)]
)


class CoreSelection(unittest.TestCase):
    def test_searches_every_socket_and_skips_sibling_threads(self):
        self.assertEqual(select_cores(ROWS, set(range(20))), [4, 6, 8, 10, 12, 14, 16, 18])

    def test_skips_rows_without_topology(self):
        rows = ROWS + "\n20,,\n21,-,-\n"
        self.assertEqual(select_cores(rows, set(range(22))), [4, 6, 8, 10, 12, 14, 16, 18])

    def test_returns_none_when_no_socket_has_enough_cores(self):
        self.assertIsNone(select_cores(ROWS, set(range(18))))


class Replay(unittest.TestCase):
    def linux_run(self, output, commit):
        return subprocess.run(
            ["bash", str(ROOT / "linux-run.sh"), str(output), commit],
            cwd=REPO, text=True, capture_output=True, timeout=60, check=False,
        )

    def test_existing_output_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "campaign"
            output.mkdir()
            stale = output / "results.json"
            stale.write_text("stale\n")
            proc = self.linux_run(output, "0" * 40)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertEqual(stale.read_text(), "stale\n")
            self.assertFalse((output / "host.txt").exists())

    def test_unknown_source_commit_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "campaign"
            proc = self.linux_run(output, "0" * 40)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertFalse(output.exists(), "nothing is written before the source commit is verified")


if __name__ == "__main__":
    unittest.main()
