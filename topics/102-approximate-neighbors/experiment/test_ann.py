"""Regression tests for the Topic 102 Python model contract."""
import pathlib
import subprocess
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ann import Index  # noqa: E402


class ImmutableIndex(unittest.TestCase):
    def test_lists_reject_mutation_and_search_is_unchanged(self):
        index = Index([(0,), (51,)], [(0,), (100,)])
        with self.assertRaises((AttributeError, TypeError)):
            index.lists[0].append(1)
        self.assertIsInstance(index.lists, tuple)
        self.assertEqual(index.search((49,), 1, 1)[0], [(2401, 0)])

    def test_lists_cover_every_id_once(self):
        index = Index([(3,), (97,), (50,)], [(0,), (100,)])
        self.assertEqual(index.lists, ((0, 2), (1,)))


class OptimizedPython(unittest.TestCase):
    def test_optimized_python_is_rejected_before_any_check(self):
        for script, args in (('experiment.py', ['check']), ('ann.py', ['demo'])):
            result = subprocess.run([sys.executable, '-O', str(HERE / script), *args],
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0, script)
            self.assertIn('PYTHONOPTIMIZE', result.stderr, script)
            self.assertEqual(result.stdout, '', script)


if __name__ == '__main__':
    unittest.main()
