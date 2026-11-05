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
# ABORT_THEN_COMMIT persists coordinator ABORT, then both participants commit
# through participant-legal steps; a uniform abort branch keeps the Safe-mode
# completion and uniform-state requirements satisfied.
ABORT_THEN_COMMIT = ['meta\t2\tSafe',
                     'node\t0\t00\t0\t0\t0\t1\t0\t0',
                     'node\t1\t00\t0\t3\t0\t1\t0\t1',
                     'node\t2\t10\t0\t3\t0\t1\t0\t1',
                     'node\t3\t11\t0\t3\t0\t1\t0\t1',
                     'node\t4\t21\t0\t3\t0\t1\t1\t1',
                     'node\t5\t22\t0\t3\t0\t1\t2\t1',
                     'node\t6\t31\t0\t3\t0\t1\t0\t1',
                     'node\t7\t33\t0\t3\t0\t1\t0\t1',
                     'edge\t0\t1\tcoordinator_abort',
                     'edge\t1\t2\tprepare0',
                     'edge\t2\t3\tprepare1',
                     'edge\t3\t4\tcommit0',
                     'edge\t4\t5\tcommit1',
                     'edge\t3\t6\tabort0',
                     'edge\t6\t7\tabort1']
# PREPARED_ABORT lets a prepared participant abort while the coordinator is still
# undecided; both uniform outcomes stay reachable through legal steps afterwards.
PREPARED_ABORT = ['meta\t2\tSafe',
                  'node\t0\t00\t0\t0\t0\t1\t0\t0',
                  'node\t1\t10\t0\t0\t0\t1\t0\t0',
                  'node\t2\t11\t0\t0\t0\t1\t0\t0',
                  'node\t3\t13\t0\t0\t0\t1\t0\t1',
                  'node\t4\t13\t0\t3\t0\t1\t0\t1',
                  'node\t5\t33\t0\t3\t0\t1\t0\t2',
                  'node\t6\t11\t0\t2\t0\t1\t0\t0',
                  'node\t7\t21\t0\t2\t0\t1\t1\t0',
                  'node\t8\t22\t0\t2\t0\t1\t2\t0',
                  'edge\t0\t1\tprepare0',
                  'edge\t1\t2\tprepare1',
                  'edge\t2\t3\ttimeout1',
                  'edge\t3\t4\tcoordinator_abort',
                  'edge\t4\t5\tabort0',
                  'edge\t2\t6\tcoordinator_commit',
                  'edge\t6\t7\tcommit0',
                  'edge\t7\t8\tcommit1']


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

    def test_safe_mode_rejects_commit_under_durable_abort(self):
        result = run_oracle(ABORT_THEN_COMMIT)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"decision_mismatch": 2', result.stdout)

    def test_safe_mode_rejects_prepared_abort_before_decision(self):
        result = run_oracle(PREPARED_ABORT)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"abstract_step": 1', result.stdout)

    def test_gate_survives_optimized_interpreter(self):
        safe = ['meta\t2\tSafe'] + SPLIT_GRAPH[1:]
        self.assertNotEqual(run_oracle(safe).returncode, 0)
        self.assertNotEqual(run_oracle(safe, '-O').returncode, 0)


if __name__ == '__main__':
    unittest.main()
