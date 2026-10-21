"""Check emitted values using exact rational arithmetic, independent of Rust."""
import subprocess
import sys
from fractions import Fraction


def check(binary):
    cases = 0
    for mode in ("split", "blocked", "fused"):
        for n in (1, 7, 1023, 1024, 1025, 2051):
            p = subprocess.run([str(binary), mode, str(n), "1", "dump"],
                               text=True, capture_output=True, check=True, timeout=30)
            actual = [Fraction(line.split(",")[1]) for line in p.stdout.splitlines()
                      if line.startswith("value,")]
            expected = [6 * Fraction(i % 1024 - 512, 16) + 2 for i in range(n)]
            if actual != expected:
                raise RuntimeError(f"oracle mismatch: {mode}, {n}")
            cases += len(expected)
    return cases


if __name__ == "__main__":
    print(f"independent rational oracle: {check(sys.argv[1])} values passed")
