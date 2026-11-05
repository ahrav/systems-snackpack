#!/usr/bin/env python3
"""Regression tests for the oracle's pass/fail gate on hand-built graphs."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

ORACLE = pathlib.Path(__file__).resolve().with_name('oracle.py')

# Node fields: participants, votes, decision, volatile, alive, commits, aborts.
# SAFE_GRAPH prepares two participants, then branches into durable COMMIT followed
# by both commits and durable ABORT followed by both aborts.
SAFE_GRAPH = ['meta\t2\tSafe',
              'node\t0\t00\t0\t0\t0\t1\t0\t0',
              'node\t1\t10\t0\t0\t0\t1\t0\t0',
              'node\t2\t11\t0\t0\t0\t1\t0\t0',
              'node\t3\t11\t0\t2\t0\t1\t0\t0',
              'node\t4\t21\t0\t2\t0\t1\t1\t0',
              'node\t5\t22\t0\t2\t0\t1\t2\t0',
              'node\t6\t11\t0\t3\t0\t1\t0\t0',
              'node\t7\t31\t0\t3\t0\t1\t0\t1',
              'node\t8\t33\t0\t3\t0\t1\t0\t2',
              'edge\t0\t1\tprepare0',
              'edge\t1\t2\tprepare1',
              'edge\t2\t3\tpersist_commit',
              'edge\t3\t4\tcommit0',
              'edge\t4\t5\tcommit1',
              'edge\t2\t6\tpersist_abort',
              'edge\t6\t7\tabort0',
              'edge\t7\t8\tabort1']
# A prepared participant aborts while the coordinator is undecided.
PREPARED_ABORT = SAFE_GRAPH + ['node\t9\t13\t0\t0\t0\t1\t0\t1',
                               'node\t10\t13\t0\t3\t0\t1\t0\t1',
                               'edge\t2\t9\ttimeout1',
                               'edge\t9\t10\tpersist_abort',
                               'edge\t10\t8\tabort0']
# One step persists COMMIT and commits a participant.
COMMIT_WITH_DECISION = SAFE_GRAPH + ['node\t9\t21\t0\t2\t0\t1\t1\t0',
                                     'edge\t2\t9\tcommit0_with_decision',
                                     'edge\t9\t5\tcommit1']
# The coordinator persists COMMIT while one participant is still working.
COMMIT_BEFORE_PREPARE = SAFE_GRAPH + ['node\t9\t10\t0\t2\t0\t1\t0\t0',
                                      'edge\t1\t9\tpersist_commit',
                                      'edge\t9\t3\tprepare1']
# A durable COMMIT turns into ABORT.
DECISION_FLIP = SAFE_GRAPH + ['node\t9\t11\t0\t3\t0\t1\t0\t0',
                              'edge\t3\t9\tflip_decision',
                              'edge\t9\t7\tabort0']
# A rejecting participant leaves the transaction in a state with no way to finish.
DEAD_END = SAFE_GRAPH + ['node\t9\t30\t0\t0\t0\t1\t0\t1',
                         'edge\t0\t9\treject0']
# One step writes a participant record and the coordinator decision together.
TWO_RECORDS = SAFE_GRAPH + ['node\t9\t30\t0\t3\t0\t1\t0\t1',
                            'edge\t0\t9\treject0_and_persist_abort',
                            'edge\t9\t8\tabort1']


def without_branch(first_node):
    """Drop SAFE_GRAPH's commit branch (nodes 3-5) or abort branch (nodes 6-8)."""
    dropped = {str(i) for i in range(first_node, first_node + 3)}
    return [line for line in SAFE_GRAPH
            if not (line.startswith('node') and line.split('\t')[1] in dropped)
            and not (line.startswith('edge') and line.split('\t')[2] in dropped)]
# Durable ABORT is followed by both participants committing through
# participant-legal steps, with a uniform abort branch keeping the Safe-mode
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
# The timeout fault as a one-step-per-edge trace: participant 1 aborts while
# prepared, the coordinator persists COMMIT from its retained votes, and
# participant 0 commits.
SPLIT_GRAPH = ['meta\t2\tTimeout'] + SAFE_GRAPH[1:] + ['node\t9\t13\t0\t0\t0\t1\t0\t1',
                                                     'node\t10\t13\t0\t2\t0\t1\t0\t1',
                                                     'node\t11\t23\t0\t2\t0\t1\t1\t1',
                                                     'edge\t2\t9\ttimeout1',
                                                     'edge\t9\t10\tpersist_commit',
                                                     'edge\t10\t11\tcommit0']
# The committed participant then flips to aborted.
TERMINAL_FLIP = ['node\t12\t33\t0\t2\t0\t1\t1\t2', 'edge\t11\t12\tuncommit']


def run_oracle(lines, *interpreter_flags):
    with tempfile.TemporaryDirectory() as tmp:
        graph = pathlib.Path(tmp, 'graph.tsv')
        graph.write_text('\n'.join(lines) + '\n')
        return subprocess.run([sys.executable, *interpreter_flags, str(ORACLE), str(graph)],
                              capture_output=True, text=True, timeout=60)


class OracleGateTest(unittest.TestCase):
    def assert_rejected(self, lines, stderr_message, stdout_fragment=None):
        result = run_oracle(lines)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(stderr_message, result.stderr)
        if stdout_fragment is not None:
            self.assertIn(stdout_fragment, result.stdout)

    def test_safe_graph_passes(self):
        result = run_oracle(SAFE_GRAPH)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"violations": {}', result.stdout)

    def test_safe_mode_rejects_prepared_abort_before_decision(self):
        self.assert_rejected(PREPARED_ABORT, 'abstract specification', '"abstract_step": 1')

    def test_safe_mode_rejects_commit_in_same_step_as_decision(self):
        self.assert_rejected(COMMIT_WITH_DECISION, 'one step changed two durable records',
                             '"abstract_step": 1')

    def test_safe_mode_rejects_commit_decision_before_all_prepared(self):
        self.assert_rejected(COMMIT_BEFORE_PREPARE, 'abstract specification',
                             '"decision_mismatch": 1')

    def test_safe_mode_rejects_commit_under_durable_abort(self):
        self.assert_rejected(ABORT_THEN_COMMIT, 'abstract specification', '"decision_mismatch": 2')

    def test_every_mode_rejects_decision_change(self):
        self.assert_rejected(DECISION_FLIP, 'durable decision changed')

    def test_every_mode_rejects_two_durable_records_in_one_step(self):
        self.assert_rejected(TWO_RECORDS, 'one step changed two durable records')

    def test_safe_mode_rejects_state_without_completion_path(self):
        self.assert_rejected(DEAD_END, 'state without a completion path')

    def test_safe_mode_requires_both_uniform_outcomes(self):
        self.assert_rejected(without_branch(3), 'no uniform commit state')
        self.assert_rejected(without_branch(6), 'no uniform abort state')

    def test_fault_mode_requires_detected_fault(self):
        self.assert_rejected(['meta\t2\tTimeout'] + SAFE_GRAPH[1:], 'fault was not detected')

    def test_fault_mode_accepts_split_with_stable_records(self):
        self.assertEqual(run_oracle(SPLIT_GRAPH).returncode, 0)

    def test_fault_mode_rejects_terminal_record_change(self):
        self.assert_rejected(SPLIT_GRAPH + TERMINAL_FLIP, 'terminal record changed')

    def test_gate_survives_optimized_interpreter(self):
        safe = ['meta\t2\tSafe'] + SPLIT_GRAPH[1:]
        self.assertNotEqual(run_oracle(safe).returncode, 0)
        self.assertNotEqual(run_oracle(safe, '-O').returncode, 0)


if __name__ == '__main__':
    unittest.main()
