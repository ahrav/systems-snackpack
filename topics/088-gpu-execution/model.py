"""Address counts for 32 lanes, four-byte words, and 32-byte sectors."""


def sectors(byte_addresses):
    return len({a // 32 for a in byte_addresses})


def bank_depth(word_addresses):
    banks = [set() for _ in range(32)]
    for word in word_addresses:
        banks[word % 32].add(word)
    return max(map(len, banks))


def transpose_tiled(a, rows, cols, pitch):
    out = [None] * len(a)
    for by in range(0, rows, 32):
        for bx in range(0, cols, 32):
            tile = [None] * (32 * pitch)
            for y in range(min(32, rows - by)):
                for x in range(min(32, cols - bx)):
                    tile[y * pitch + x] = a[(by + y) * cols + bx + x]
            # All producers finish before any consumer reads this tile.
            for y in range(min(32, cols - bx)):
                for x in range(min(32, rows - by)):
                    out[(bx + y) * rows + by + x] = tile[x * pitch + y]
    return out


if __name__ == "__main__":
    lanes = range(32)
    print("aligned contiguous sectors:", sectors([4 * t for t in lanes]))
    print("one-word shifted sectors:", sectors([4 * (t + 1) for t in lanes]))
    print("1024-word stride sectors:", sectors([4 * 1024 * t for t in lanes]))
    print("pitch 32 column bank depth:", bank_depth([32 * t for t in lanes]))
    print("pitch 33 column bank depth:", bank_depth([33 * t for t in lanes]))
    print("broadcast bank depth:", bank_depth([0] * 32))
    cases = 0
    for rows in range(66):
        for cols in range(66):
            a = list(range(rows * cols))
            # Output-major oracle has no tiles, padding, or thread mapping.
            expected = [a[r * cols + c] for c in range(cols) for r in range(rows)]
            for pitch in (32, 33):
                assert transpose_tiled(a, rows, cols, pitch) == expected
                cases += 1
    print("oracle comparisons:", cases)
