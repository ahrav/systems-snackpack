"""Focused tests for the Topic 83 runner helpers."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run

# FRAGMENTED and HYPERTHREADED model `lscpu -p=CPU,CORE,SOCKET,NODE` output.
FRAGMENTED = '\n'.join(['# comment'] + [f'{c},{c},0,0' for c in range(4)] + [f'{c},{c},0,1' for c in range(4, 12)])
HYPERTHREADED = '\n'.join(f'{cpu},{cpu % 8},0,0' for cpu in range(16))


class SelectCpus(unittest.TestCase):
    def test_hyperthread_siblings_count_once(self):
        self.assertEqual(run.select_cpus(HYPERTHREADED, set(range(16))), list(range(8)))

    def test_node_with_eight_cores_is_chosen_over_a_short_first_node(self):
        self.assertEqual(run.select_cpus(FRAGMENTED, set(range(12))), list(range(4, 12)))

    def test_no_node_with_eight_allowed_cores_is_rejected(self):
        with self.assertRaises(AssertionError):
            run.select_cpus(FRAGMENTED, set(range(10)))


class Run(unittest.TestCase):
    def test_timed_out_attempt_is_retained(self):
        with tempfile.TemporaryDirectory() as out:
            out = pathlib.Path(out)
            command = [sys.executable, '-c', 'import sys, time; print("partial"); sys.stdout.flush(); time.sleep(5)']
            with self.assertRaises(subprocess.TimeoutExpired):
                run.run(out, command, 'slow', timeout=1)
            record = json.loads((out / 'slow.json').read_text())
            self.assertEqual(record['command'], command)
            self.assertIsNone(record['returncode'])
            self.assertEqual(record['stdout'], 'partial\n')

    def test_failed_attempt_is_retained(self):
        with tempfile.TemporaryDirectory() as out:
            out = pathlib.Path(out)
            command = [sys.executable, '-c', 'import sys; sys.exit(3)']
            with self.assertRaises(subprocess.CalledProcessError):
                run.run(out, command, 'failed')
            self.assertEqual(json.loads((out / 'failed.json').read_text())['returncode'], 3)


class Usage(unittest.TestCase):
    def test_missing_output_directory_prints_usage(self):
        result = subprocess.run([sys.executable, run.__file__], text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('usage: run.py OUTPUT_DIRECTORY', result.stderr)


if __name__ == '__main__':
    unittest.main()
