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
# FAKE prints a parseable row beside wrong bytes, wrong counters and a failing status.
FAKE = """#!/bin/sh
echo wrong > snapshot.bin
echo wrong > live.bin
echo '{"page_size":4096,"events":9,"fault_copies":0,"scan_copies":0}'
exit 1
"""


def check(binary, *flags, **env):
    return subprocess.run([sys.executable, *flags, str(HERE / "check.py"), str(binary)],
                          env=dict(ENV, **env), text=True, capture_output=True, timeout=300)


class OptimizedPython(unittest.TestCase):
    def test_checker_refuses_optimized_python(self):
        with tempfile.TemporaryDirectory() as scratch:
            fake = pathlib.Path(scratch, "fake")
            fake.write_text(FAKE)
            fake.chmod(0o755)
            for name, result in (("-O", check(fake, "-O")),
                                 ("PYTHONOPTIMIZE", check(fake, PYTHONOPTIMIZE="1"))):
                with self.subTest(optimized=name):
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("python3 -O", result.stderr)
                    self.assertEqual(result.stdout, "")
            plain = check(fake)
            self.assertNotEqual(plain.returncode, 0)
            self.assertIn("AssertionError", plain.stderr)
            self.assertEqual(plain.stdout, "")


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
