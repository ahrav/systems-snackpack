"""oracle.py passes the retained native CSVs, rejects optimized Python,
and rejects rows outside the declared scenario matrix."""
import csv
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
HEADER = ["initial", "amount", "point", "repair_cut", "mode", "a", "b"]


def run_oracle(path, optimize=""):
    """Run oracle.py on `path`; a non-empty `optimize` strips assert statements."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONOPTIMIZE"}
    return subprocess.run(
        [sys.executable, str(ROOT / "oracle.py"), str(path)],
        env={**env, "PYTHONOPTIMIZE": optimize}, text=True, capture_output=True, timeout=60, check=False,
    )


def run_rows(rows, optimize=""):
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "native.csv"
        with open(path, "w", newline="", encoding="utf-8") as out:
            csv.writer(out).writerows([HEADER, *rows])
        return run_oracle(path, optimize)


class Oracle(unittest.TestCase):
    def test_retained_native_results_pass(self):
        for host in ("arm", "x86"):
            with self.subTest(host=host):
                proc = run_oracle(ROOT / "evidence" / f"{host}.csv")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("total=384", proc.stdout)

    def test_optimized_python_never_reports_pass(self):
        for name, proc in (("header only", run_rows([], optimize="1")),
                           ("retained rows", run_oracle(ROOT / "evidence" / "x86.csv", optimize="1"))):
            with self.subTest(csv=name):
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertNotIn("PASS", proc.stdout)

    def test_rows_outside_the_declared_matrix_are_rejected(self):
        with open(ROOT / "evidence" / "x86.csv", encoding="utf-8") as retained:
            rows = [list(r.values()) for r in csv.DictReader(retained)]
        controls = [r for r in rows if r[4] != "repair"]
        self.assertEqual((len(rows), len(controls)), (384, 24))
        off_matrix = [[a, amount, 0, -1, "repair", a, 100 - a] for a in range(10, 100) for amount in range(1, 5)]
        moved_cut = [["10", "1", "0", "4", "repair", "10", "90"] if r[:4] == ["10", "1", "0", "-1"] else r for r in rows]
        repeated_poison = [["10", "1", "3", "-1", "poison", "11", "89"] if r[:5] == ["100", "100", "3", "-1", "poison"] else r
                           for r in rows]
        for name, candidate in (("360 repairs at point 0", off_matrix + controls),
                                ("one repair cut outside -1..3", moved_cut),
                                ("one poison key twice, one absent", repeated_poison)):
            with self.subTest(rows=name):
                self.assertEqual(len(candidate), 384)
                self.assertNotEqual(candidate, rows)
                proc = run_rows(candidate)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertNotIn("PASS", proc.stdout)

if __name__ == "__main__":
    unittest.main()
