"""Compare the Rust continuation with exact Python sums and effect sequences."""
import itertools
import pathlib
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[3]
probe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else root / "target/release/examples/probe"
alphabet = [("A", 0), ("A", 1), ("A", -1), ("A", 2147483647), ("A", -2147483648), ("B", 7)]
cases = [r for n in range(7) for r in itertools.product(alphabet, repeat=n)]
encoded = "".join(" ".join(f"{k}:{v}" for k, v in rows) + "\n" for rows in cases)
result = subprocess.run([str(probe)], input=encoded, capture_output=True, text=True, check=True)
lines = result.stdout.splitlines()
assert len(lines) == len(cases)
for rows, line in zip(cases, lines):
    total, deopt, effects = line.split(";")
    assert int(total) == sum(v for _, v in rows)
    assert effects == ",".join(map(str, range(len(rows))))
    # Exact prefix sums define the earliest violated specialization precondition.
    prefixes = list(itertools.accumulate(v for _, v in rows))
    failed = [i for i, ((shape, _), s) in enumerate(zip(rows, prefixes))
              if shape != "A" or not -2**31 <= s < 2**31]
    assert deopt == (str(failed[0]) if failed else "none")
print(f"PASS {len(cases)} independent sum, effect-order and bailout comparisons")
