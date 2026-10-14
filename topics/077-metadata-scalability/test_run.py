"""run.py refuses an existing output directory before writing identity.json, writes LF-terminated
samples.csv, and serializes integer benchmark columns as JSON numbers in calibrations.json."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
FAKE_ROW = "{variant},{workload},{iterations},64,13170488,25723.609,1048576,1536"


def fake_binary(directory, fail=False, echo_iterations="i"):
    """A stand-in for compare.rs that echoes one well-formed row (or exits 1).
    echo_iterations is a Python expression over the invocation's iteration string ``i``."""
    path = pathlib.Path(directory) / "fake-compare"
    body = "import sys; sys.exit(1)" if fail else (
        "import sys; v,w,i=sys.argv[1:4]; print(" + repr(FAKE_ROW)
        + ".format(variant=v,workload=w,iterations=" + echo_iterations + "))"
    )
    path.write_text("#!" + sys.executable + "\n" + body + "\n")
    path.chmod(0o755)
    return path


def run_py(binary, out):
    return subprocess.run(
        [sys.executable, str(ROOT / "run.py"), "--binary", str(binary), "--out", str(out), "--source-commit", "deadbeef"],
        cwd=ROOT, text=True, capture_output=True, timeout=300, check=False,
    )


class OutputDirectory(unittest.TestCase):
    def test_existing_directory_is_rejected_before_identity_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "campaign"
            out.mkdir()
            stale = out / "samples.csv"
            stale.write_text("stale\n")
            proc = run_py(fake_binary(tmp, fail=True), out)
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse((out / "identity.json").exists(), "a refused rerun must not overwrite identity.json")
            self.assertEqual(stale.read_text(), "stale\n")


class Outputs(unittest.TestCase):
    def test_echoed_arguments_must_match_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "campaign"
            proc = run_py(fake_binary(tmp, echo_iterations="str(int(i) + 1)"), out)
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse((out / "samples.csv").exists(), "a mislabeled row must stop the campaign before output")
    def test_csv_uses_lf_and_calibration_integers_are_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "campaign"
            proc = run_py(fake_binary(tmp), out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            raw = (out / "samples.csv").read_bytes()
            self.assertNotIn(b"\r", raw)
            self.assertEqual(raw.count(b"\n"), 1 + 3 * 12)
            for row in json.loads((out / "calibrations.json").read_text()):
                for key in ("iterations", "updates", "elapsed_ns", "snapshot_bytes", "delta_bytes"):
                    self.assertIsInstance(row[key], int, key)
                self.assertIsInstance(row["ns_per_batch"], float)


if __name__ == "__main__":
    unittest.main()
