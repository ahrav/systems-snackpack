"""Regression tests: the Topic 108 programs refuse to run with assertions disabled."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ENV = {k: v for k, v in os.environ.items() if k != "PYTHONOPTIMIZE"}
SOURCE = str(HERE / "native" / "epoll_reuse.c")
SUMMARY = "native_cases=256 stale_rejected=256 raw_reads_B=256 fresh_reads_C=256 alias_cases=64\n"


def run(*command, **env):
    return subprocess.run(command, env=dict(ENV, **env), text=True, capture_output=True,
                          timeout=120)


def reuse(*flags, **env):
    return run(sys.executable, *flags, str(HERE / "examples" / "reuse.py"), **env)


class Checks(unittest.TestCase):
    def test_reuse_reports_both_outcomes(self):
        result = reuse()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "generation check: stale callback rejected\n"
                                        "raw fd callback: consumed B\n")

    def test_reuse_refuses_optimized_python(self):
        for name, result in (("-O", reuse("-O")), ("PYTHONOPTIMIZE", reuse(PYTHONOPTIMIZE="1"))):
            self.assertNotEqual(result.returncode, 0, name)
            self.assertEqual(result.stdout, "", name)
            self.assertIn("validation uses assert", result.stderr, name)

    @unittest.skipUnless(sys.platform == "linux" and shutil.which("cc"), "needs Linux and cc")
    def test_native_build_refuses_ndebug(self):
        with tempfile.TemporaryDirectory() as scratch:
            binary = str(pathlib.Path(scratch, "epoll"))
            build = run("cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", SOURCE,
                        "-o", binary)
            self.assertEqual(build.returncode, 0, build.stderr)
            checked = run(binary)
            self.assertEqual((checked.returncode, checked.stdout), (0, SUMMARY), checked.stderr)
            stripped = run("cc", "-std=c11", "-O2", "-DNDEBUG", SOURCE, "-o", binary)
        self.assertNotEqual(stripped.returncode, 0)
        self.assertIn("build without -DNDEBUG", stripped.stderr)


if __name__ == "__main__":
    unittest.main()
