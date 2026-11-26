"""Whole-segment recovery targets on a single timeline."""
bases = {"A": (10, 11), "B": (14, 15)}
wal = set(range(10, 18)) - {12}


def paths(target, archive):
    return [name for name, (start, consistent) in bases.items()
            if consistent <= target
            and all(s in archive for s in range(start, target + 1))]


if __name__ == "__main__":
    for target in (11, 13, 15, 17):
        print(target, paths(target, wal))
    print("after dropping 14:", paths(17, wal - {14}))
