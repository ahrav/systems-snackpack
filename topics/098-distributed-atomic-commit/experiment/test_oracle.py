#!/usr/bin/env python3
"""Regression tests for the oracle's pass/fail gate on hand-built graphs."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

ORACLE = pathlib.Path(__file__).resolve().with_name('oracle.py')
# SPLIT_GRAPH prepares both participants, then splits their outcomes to violate
# agreement. TERMINAL_FLIP appends a step that moves the committed participant
# to aborted, which changes a terminal record.
SPLIT_GRAPH = ['meta\t2\tTimeout',
               'node\t0\t00\t0\t0\t0\t1\t0\t0',
               'node\t1\t11\t3\t0\t0\t1\t0\t0',
               'node\t2\t23\t3\t2\t0\t1\t1\t0',
               'edge\t0\t1\tprepare',
               'edge\t1\t2\tsplit']
TERMINAL_FLIP = ['node\t3\t33\t3\t2\t0\t1\t1\t0', 'edge\t2\t3\tuncommit']


def run_oracle(lines, *interpreter_flags):
    with tempfile.NamedTemporaryFile('w', suffix='.tsv', delete=False) as graph:
        graph.write('\n'.join(lines) + '\n')
    try:
        return subprocess.run([sys.executable, *interpreter_flags, str(ORACLE), graph.name],
                              capture_output=True, text=True)
    finally:
        pathlib.Path(graph.name).unlink()


class OracleGateTest(unittest.TestCase):
    def test_fault_mode_accepts_split_with_stable_records(self):
        self.assertEqual(run_oracle(SPLIT_GRAPH).returncode, 0)

    def test_fault_mode_rejects_terminal_record_change(self):
        result = run_oracle(SPLIT_GRAPH + TERMINAL_FLIP)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('terminal record changed', result.stderr)

    def test_gate_survives_optimized_interpreter(self):
        safe = ['meta\t2\tSafe'] + SPLIT_GRAPH[1:]
        self.assertNotEqual(run_oracle(safe).returncode, 0)
        self.assertNotEqual(run_oracle(safe, '-O').returncode, 0)


if __name__ == '__main__':
    unittest.main()
