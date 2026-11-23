"""Check field-byte encoding and every erased target with a binary linear oracle."""
import subprocess
import sys

# A generator table for GF(256). Newton interpolation uses divided differences.
exp = [1]
for _ in range(254):
    v = exp[-1] << 1
    exp.append(v ^ 0x11D if v & 256 else v)
assert len(set(exp)) == 255
log = {v: i for i, v in enumerate(exp)}


def times(a, b):
    return exp[(log[a] + log[b]) % 255] if a and b else 0


def value(data, x):
    diff = list(data)
    for span in range(1, 6):
        for i in range(5, span - 1, -1):
            denominator = i ^ (i - span)
            diff[i] = times(diff[i] ^ diff[i - 1], exp[-log[denominator] % 255])
    v = diff[-1]
    for i in reversed(range(5)):
        v = times(x ^ i, v) ^ diff[i]
    return v


def encode(code, data):
    if code == "rs":
        return list(data) + [value(data, x) for x in (7, 8, 6)]
    a, b, c, d, e, f = data
    return list(data) + [a ^ b ^ c, d ^ e ^ f, value(data, 6)]


def rank(rows):
    basis = {}
    for row in rows:
        while row:
            pivot = row.bit_length()
            if pivot not in basis:
                basis[pivot] = row
                break
            row ^= basis[pivot]
    return len(basis)


def binary_rows(code):
    rows = [[0] * 8 for _ in range(9)]
    for bit in range(48):
        data = list((1 << bit).to_bytes(6, "little"))
        for i, byte in enumerate(encode(code, data)):
            for j in range(8):
                rows[i][j] |= ((byte >> j) & 1) << bit
    return rows


def main(executable):
    entries = subprocess.check_output([executable, "check"], text=True).splitlines()
    seen = set()
    totals = {"rs": [0]*4, "lrc": [0]*4}
    matrices = {c: binary_rows(c) for c in totals}
    for line in entries:
        kind, code, number, result = line.split()
        i = int(number)
        key = (kind, code, i)
        assert key not in seen
        seen.add(key)
        if kind == "encoded":
            expected = bytes(encode(code, [((d+1)*(j*j+17)+71*j) % 256 for d in range(6)])[i]
                             for j in range(17))
            assert bytes.fromhex(result) == expected, key
            continue
        assert kind == "mask" and 0 <= i < 512
        rows = matrices[code]
        surviving = [r for pos, rs in enumerate(rows) if not (i >> pos) & 1 for r in rs]
        dimension = rank(surviving)
        wanted = sum(1 << pos for pos in range(9) if i >> pos & 1
                     and rank(surviving + rows[pos]) == dimension)
        assert int(result) == wanted, (key, wanted, result)
        losses = bin(i).count("1")
        if losses <= 3 and dimension == 48:
            totals[code][losses] += 1
    assert len(seen) == 2 * (512 + 9)
    print("18 encoded fragments, 1024 erasure masks, 4608 erased target decisions passed")
    print("Recoverable whole stripes for 0,1,2,3 erasures:", totals)


if __name__ == "__main__":
    main(sys.argv[1])
