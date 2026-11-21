"""Compare Rust transitions with an ordering predicate over complete histories."""
from itertools import permutations, product
from pathlib import Path
import subprocess
import sys


def expected(grant, access, history):
    # Find the first eligible release in the history. A cooperative writer
    # needs an earlier flush. A recall timeout requires an actual conflict.
    never = len(history) + 1
    pos = lambda e: history.index(e) if e in history else never
    conflict = "w" in (grant, access)
    returned = pos("R") if grant == "r" or pos("F") < pos("R") else never
    revoked = pos("V") if conflict else never
    release = min(returned, revoked)
    status = "held" if release == never else ("returned" if returned < revoked else "revoked")
    open_at = next((i for i, e in enumerate(history) if e == "P" and i > release), never) if conflict else -1
    b_wrote = access == "w" and any(e == "B" and i > open_at for i, e in enumerate(history))
    a_wrote = grant == "w" and pos("F") < release
    value = "RED" if b_wrote else ("GOLD" if a_wrote else "BLUE")
    return f"{status} {'open' if open_at < never else 'wait'} {value}"


def main(binary):
    prefixes = {""}
    for order in permutations("KFRVPB"):
        history = "".join(order)
        prefixes.update(history[:i] for i in range(1, 7))
        # Retried writeback and OPEN can straddle the release boundary.
        prefixes.add(history + "FPB")
    rows = list(product("rw", "rw", sorted(prefixes)))
    payload = "".join(f"{g} {a} {h}\n" for g, a, h in rows)
    proc = subprocess.run([str(Path(binary).resolve())], input=payload, text=True,
                          capture_output=True, check=True)
    observed = proc.stdout.splitlines()
    assert len(observed) == len(rows)
    for args, actual in zip(rows, observed):
        wanted = expected(*args)
        if wanted != actual:
            raise AssertionError((args, wanted, actual))
    print(f"oracle passed {len(rows)} histories")


if __name__ == "__main__":
    main(sys.argv[1])
