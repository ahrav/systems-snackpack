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
            sentinel = pathlib.Path(out) / 'cpuinfo.txt'
            sentinel.write_text('stale\n')
            # The timeout bounds the wait if the guard fails and run.py's unittest
            # discovery invokes this test recursively.
            result = subprocess.run([sys.executable, str(RUNNER), out, 'deadbeef'],
                                    capture_output=True, text=True, timeout=60)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('output directory must be empty', result.stderr)
            self.assertEqual([p.name for p in pathlib.Path(out).iterdir()], ['cpuinfo.txt'])
            self.assertEqual(sentinel.read_text(), 'stale\n')


if __name__ == '__main__':
    unittest.main()
