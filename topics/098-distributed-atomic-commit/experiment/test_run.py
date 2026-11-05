#!/usr/bin/env python3
"""Regression tests for the runner's output-directory precondition."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

RUNNER = pathlib.Path(__file__).resolve().with_name('run.py')


class RunnerPreconditionTest(unittest.TestCase):
    def test_rejects_nonempty_output_directory(self):
        with tempfile.TemporaryDirectory() as out:
            (pathlib.Path(out) / 'cpuinfo.txt').write_text('stale\n')
            result = subprocess.run([sys.executable, str(RUNNER), out, 'deadbeef'],
                                    capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('output directory must be empty', result.stderr)


if __name__ == '__main__':
    unittest.main()
