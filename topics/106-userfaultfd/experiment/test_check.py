"""Regression tests for the Topic 106 checker and unavailable-facility exits."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ENV = {k: v for k, v in os.environ.items() if k != "PYTHONOPTIMIZE"}
ENV["LC_ALL"] = "C"
CC = ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror"]
# FAILING prints a parseable row beside wrong bytes, wrong counters and a failing status.
FAILING = """#!/bin/sh
echo wrong > snapshot.bin
echo wrong > live.bin
echo '{"page_size":4096,"events":9,"fault_copies":0,"scan_copies":0}'
exit 1
"""
# CORRECT satisfies every checker rule. FAULT selects one deviation: page_size halves the
# reported page size and both images to match; writers misreports the writer count.
CORRECT = "#!" + sys.executable + '''
import json, os, sys
pages, writers, passes, mode = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
fault = os.environ.get("FAULT")
size = os.sysconf("SC_PAGESIZE") // (2 if fault == "page_size" else 1)
initial = bytes((p * 17 + j * 3) % 256 for p in range(pages) for j in range(size))
with open("snapshot.bin", "wb") as f:
    f.write(initial)
with open("live.bin", "wb") as f:
    f.write(bytes((b + passes) % 256 for b in initial))
faulted = pages if mode == "fault" else 0
print(json.dumps({"pages": pages, "page_size": size, "writers": writers + (fault == "writers"),
                  "passes": passes, "events": faulted, "fault_copies": faulted,
                  "scan_copies": pages - faulted}))
'''


def check(binary, *flags, **env):
    return subprocess.run([sys.executable, *flags, str(HERE / "check.py"), str(binary)],
                          env=dict(ENV, **env), text=True, capture_output=True, timeout=300)


def check_fake(source, *flags, **env):
    with tempfile.TemporaryDirectory() as scratch:
        fake = pathlib.Path(scratch, "fake")
        fake.write_text(source)
        fake.chmod(0o755)
        return check(fake, *flags, **env)


class OptimizedPython(unittest.TestCase):
    def test_checker_refuses_optimized_python(self):
        for name, result in (("-O", check_fake(FAILING, "-O")),
                             ("PYTHONOPTIMIZE", check_fake(FAILING, PYTHONOPTIMIZE="1"))):
            with self.subTest(optimized=name):
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("python3 -O", result.stderr)
                self.assertEqual(result.stdout, "")
        plain = check_fake(FAILING)
        self.assertNotEqual(plain.returncode, 0)
        self.assertIn("AssertionError", plain.stderr)
        self.assertEqual(plain.stdout, "")


class Oracle(unittest.TestCase):
    def test_accepts_correct_binary(self):
        result = check_fake(CORRECT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual((report["status"], report["processes"]), ("pass", 36))

    def test_rejects_reported_page_size_and_writer_count(self):
        for fault in ("page_size", "writers"):
            with self.subTest(fault=fault):
                result = check_fake(CORRECT, FAULT=fault)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("AssertionError", result.stderr)
                self.assertEqual(result.stdout, "")


@unittest.skipUnless(sys.platform == "linux" and shutil.which("cc"), "requires Linux and cc")
class UnavailableFacility(unittest.TestCase):
    """Run snapshot.c under uffd_shim.c, which answers as a kernel without one facility."""

    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.binary = pathlib.Path(cls.scratch.name, "snapshot")
        cls.shim = pathlib.Path(cls.scratch.name, "uffd_shim.so")
        subprocess.run([*CC, "-pthread", str(HERE / "snapshot.c"), "-o", str(cls.binary)], check=True)
        subprocess.run([*CC, "-shared", "-fPIC", str(HERE / "uffd_shim.c"), "-o", str(cls.shim), "-ldl"],
                       check=True)
        # Control: with the shim loaded and every call forwarded, the host runs the experiment.
        control = cls.snapshot("")
        if control.returncode == 77:
            raise unittest.SkipTest("host lacks userfaultfd WP: " + control.stderr)
        assert control.returncode == 0, (control.returncode, control.stderr)

    @classmethod
    def shim_env(cls, answer):
        return {"LD_PRELOAD": str(cls.shim), "UFFD_SHIM": answer}

    @classmethod
    def snapshot(cls, answer):
        return subprocess.run([str(cls.binary), "4", "2", "2", "race"], cwd=cls.scratch.name,
                              env=dict(ENV, **cls.shim_env(answer)), text=True, capture_output=True, timeout=20)

    def test_missing_facility_exits_77(self):
        for answer, message in (("no_wp", "UFFDIO_API unavailable: Invalid argument"),
                                ("no_user_mode_only", "userfaultfd unavailable: Invalid argument")):
            with self.subTest(answer=answer):
                result = self.snapshot(answer)
                self.assertEqual(result.returncode, 77, result.stderr)
                self.assertIn(message, result.stderr)
                checked = check(self.binary, **self.shim_env(answer))
                self.assertEqual(checked.returncode, 77, checked.stderr)
                self.assertEqual(json.loads(checked.stdout)["status"], "unavailable")

    def test_other_api_error_fails(self):
        result = self.snapshot("api_eio")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("UFFDIO_API: Input/output error", result.stderr)


if __name__ == "__main__":
    unittest.main()
