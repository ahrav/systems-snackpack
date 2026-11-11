"""Regression tests for the Topic 105 runner and snapshot checks."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
# FAKE supplies synthetic native.c output to test runner validation.
FAKE = "#!" + sys.executable + '''
import json, os, sys
layout, count, passes = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
fault = os.environ.get("FAULT")
private = 4 if layout == "packed" else count * 4
base = 0 if fault == "baseline" else count * 2
def stats(pss, dirty):
    return {"rss_kib": count * 4, "pss_kib": pss, "private_dirty_kib": dirty,
            "huge_kib": 0, "swap_kib": 0}
row = {"layout": layout, "count": count, "passes": passes + (fault == "label"),
       "page_size": 4096, "parent_bytes_ok": True, "child_bytes_ok": True}
for actor in ("parent", "child"):
    row[actor + "_before"] = stats(base, 0)
    row[actor + "_after"] = stats(base + private // 2, private)
print(json.dumps(row))
'''


def run_fake(fault="", flags=()):
    with tempfile.TemporaryDirectory() as scratch:
        fake = pathlib.Path(scratch, "fake")
        fake.write_text(FAKE)
        fake.chmod(0o755)
        return subprocess.run(
            [sys.executable, *flags, str(HERE / "run.py"), str(fake)],
            env=dict(os.environ, FAULT=fault), text=True, capture_output=True)


class Runner(unittest.TestCase):
    def test_accepts_exact_accounting(self):
        result = run_fake()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_wrong_label_and_unshared_baseline(self):
        for fault in ("label", "baseline"):
            self.assertNotEqual(run_fake(fault).returncode, 0, fault)


class OptimizedPython(unittest.TestCase):
    def test_runner_and_snapshot_refuse_optimized_python(self):
        snapshot = subprocess.run([sys.executable, "-O", str(HERE / "snapshot.py")],
                                  text=True, capture_output=True)
        for name, result in (("run.py", run_fake(flags=["-O"])), ("snapshot.py", snapshot)):
            self.assertNotEqual(result.returncode, 0, name)
            self.assertIn("python3 -O", result.stderr, name)
            self.assertEqual(result.stdout, "", name)


if __name__ == "__main__":
    unittest.main()
