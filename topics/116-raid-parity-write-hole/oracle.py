"""Compare recovered bytes with the original writer's old and intended bytes."""
from itertools import product
from pathlib import Path
import subprocess
import sys


def parity(a, b):
    # Different construction from the Rust delta calculation.
    return sum((1 << i) for i in range(8) if ((a >> i) % 2 + (b >> i) % 2) % 2)


def as_hex(values):
    return bytes(values).hex()


def check(binary):
    total = bad_untouched = bad_full = 0
    # Representative distinct bytes, duplicates and no-op updates.
    alphabet = (0, 0x3c, 0x55, 0xa6)
    for a, b in product(alphabet, repeat=2):
        requests, wanted = [], []
        old = (a, b, parity(a, b))
        for u, v, kind in product(alphabet, alphabet, range(3)):
            intended = (u if kind != 1 else a, v if kind != 0 else b)
            after = (*intended, parity(*intended))
            touched = (0, 2) if kind == 0 else (1, 2) if kind == 1 else (0, 1, 2)
            masks = [sum(1 << member for member, flag in zip(touched, flags) if flag)
                     for flags in product((0, 1), repeat=len(touched))]
            for cut, lost, replay_cut in product(masks, range(3), masks):
                home = [after[i] if cut & (1 << i) else old[i] for i in range(3)]
                home[lost] = parity(*(home[i] for i in range(3) if i != lost))
                requests.append(f"{a} {b} {u} {v} {kind} {cut} {lost} {replay_cut}")
                wanted.append([as_hex(old), as_hex(home), as_hex(after), as_hex(after)])
                bad_untouched += kind < 2 and lost == 1 - kind and home[lost] != old[lost]
                bad_full += kind == 2 and tuple(home) not in (old, after)
        got = subprocess.run([binary], input="\n".join(requests) + "\n", text=True,
                             stdout=subprocess.PIPE, check=True).stdout.splitlines()
        if len(got) != len(wanted):
            raise AssertionError((len(got), len(wanted)))
        for history, row, expected in zip(requests, got, wanted):
            if row.split() != expected:
                raise AssertionError((history, row, expected))
        total += len(got)
    assert bad_untouched > 0 and bad_full > 0
    print(f"{total} histories; {4*total} stripe comparisons")
    print(f"unprotected: {bad_untouched} wrong untouched rebuilds; "
          f"{bad_full} full-stripe outcomes outside old/new")


if __name__ == "__main__":
    check(Path(sys.argv[1]).resolve())
