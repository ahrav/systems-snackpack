"""inventory.py checks the parent's decode under optimized Python, and its forked
child leaves only through os._exit."""
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
EXPECTED = """\
8 (11, 3)
16 (42, 7)
12 invalid record offset
24 invalid record offset
4294967295 invalid record offset
child read (42, 7) from a distinct mapping
"""
# A valid child decode would mask the parent mismatch if two_readers checked only the child.
WRONG_PARENT = """
import os, inventory
parent, real = os.getpid(), inventory.selected
inventory.selected = lambda data: (0, 0) if os.getpid() == parent else real(data)
inventory.two_readers()
"""
# A caller that catches the child's exception would keep running its own code in the child.
FAILED_CHILD = """
import os, inventory
parent, real = os.getpid(), inventory.mmap.mmap
def mapping(*args, **kwargs):
    if os.getpid() != parent:
        raise OSError("no second mapping")
    return real(*args, **kwargs)
inventory.mmap.mmap = mapping
try:
    inventory.two_readers()
    outcome = "returned"
except BaseException as error:
    outcome = type(error).__name__
print(outcome, "in", "parent" if os.getpid() == parent else "child", flush=True)
"""


def run(*args, optimize=""):
    """Run Python in the topic directory; a non-empty `optimize` strips assert statements."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONOPTIMIZE"}
    return subprocess.run(
        [sys.executable, *args], cwd=ROOT, env={**env, "PYTHONOPTIMIZE": optimize},
        text=True, capture_output=True, timeout=60, check=False,
    )


class TwoReaders(unittest.TestCase):
    def test_documented_run_prints_the_readme_output(self):
        for optimize in ("", "1"):
            with self.subTest(PYTHONOPTIMIZE=optimize):
                proc = run("inventory.py", optimize=optimize)
                self.assertEqual((proc.returncode, proc.stdout), (0, EXPECTED), proc.stderr)

    def test_wrong_parent_decode_fails_before_the_fork(self):
        for optimize in ("", "1"):
            with self.subTest(PYTHONOPTIMIZE=optimize):
                proc = run("-c", WRONG_PARENT, optimize=optimize)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertEqual(proc.stdout, "")

    def test_failed_child_never_returns_to_the_caller(self):
        proc = run("-c", FAILED_CHILD)
        self.assertEqual(proc.stdout, "RuntimeError in parent\n", proc.stderr)
        self.assertIn("child failed: OSError", proc.stderr)


if __name__ == "__main__":
    unittest.main()
