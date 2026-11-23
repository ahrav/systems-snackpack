from functools import reduce
from operator import xor


def mul(a, b):
    result = 0
    while b:
        if b & 1:
            result ^= a
        a = (a << 1) ^ (0x11D if a & 128 else 0)
        b >>= 1
    return result


# One byte position from six fragments. Repeat independently for every byte.
data = [19, 42, 61, 85, 127, 201]
weights = [7, 6, 5, 4, 3, 2]
global_parity = reduce(xor, (mul(w, d) for w, d in zip(weights, data)))
local_parity = data[0] ^ data[1] ^ data[2]

# Only the encoder and the final check can see the missing byte.
survivors = data[1:]
residual = reduce(xor, (mul(w, d) for w, d in zip(weights[1:], survivors)),
                  global_parity)
inverse_seven = next(v for v in range(1, 256) if mul(7, v) == 1)
rs = mul(inverse_seven, residual)
local = local_parity ^ survivors[0] ^ survivors[1]
assert rs == local == data[0]
print(f"RS: {rs} from 6 helpers. LRC: {local} from 3 helpers.")
