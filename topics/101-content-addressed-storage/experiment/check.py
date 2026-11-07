"""Direct polynomial oracle plus byte-list identity and reachability checks."""
import json
import random
import sys
from cas import Store, chunks


def oracle(data):
    ends, start = [], 0
    for end in range(1, len(data) + 1):
        size = end - start
        if size < 2048:
            continue
        # Recompute each window from bytes, independently of the rolling update.
        value = sum(b * 257**i for i, b in enumerate(reversed(data[max(start, end-64):end])))
        if size >= 16384 or value % 4096 == 0:
            ends.append(end)
            start = end
    if start < len(data):
        ends.append(len(data))
    return [data[a:b] for a, b in zip([0] + ends, ends)]


def main(binary):
    rng = random.Random(101)
    cases = [b"", b"a", bytes(40000), bytes([1])*40000, bytes(range(256))*160]
    cases += [bytes(rng.randrange(256) for _ in range(n)) for n in
              [63, 64, 65, 2047, 2048, 2049, 4095, 4096, 4097, 16383, 16384, 16385]]
    cases += [bytes(rng.randrange(256) for _ in range(rng.randrange(18000))) for _ in range(40)]
    comparisons = 0
    for data in cases:
        for mode in ["whole", "fixed", "cdc"]:
            got = chunks(binary, mode, data)
            expected = (oracle(data) if mode == "cdc" else
                        [data[i:i+4096] for i in range(0, len(data), 4096)] if mode == "fixed" else
                        [data] if data else [])
            assert got == expected
            store = Store()
            root = store.publish("a", got)
            assert store.restore(root) == data
            assert sum(len(v) - 9 for v in store.objects.values() if v.startswith(b"chunk-v1\0")) == sum(map(len, set(expected)))
            comparisons += 1
    s = Store()
    a = s.publish("a", [b"a", b"b", b"a"])
    b = s.publish("b", [b"b", b"c"])
    orphan = s.put(b"chunk-v1", b"orphan")
    del s.roots["a"]
    s.collect()
    assert s.restore(b) == b"bc" and a not in s.objects and orphan not in s.objects
    assert len(s.objects) == 3
    key = s.refs(b)[0]
    s.objects[key] = b"chunk-v1\0damaged"
    try:
        s.restore(b)
        raise AssertionError("corruption accepted")
    except ValueError:
        pass
    collision = Store(lambda _: bytes(32))
    collision.put(b"chunk-v1", b"a")
    try:
        collision.put(b"chunk-v1", b"b")
        raise AssertionError("collision accepted")
    except ValueError:
        assert list(collision.objects.values()) == [b"chunk-v1\0a"]
    t = Store()
    assert t.put(b"chunk-v1", b"x") != t.put(b"manifest-v1", b"x")
    print(json.dumps({"boundary_restore_payload_comparisons": comparisons, "inputs": len(cases),
                      "collision_corruption_gc_domain_checks": "pass"}, sort_keys=True))

if __name__ == "__main__":
    main(sys.argv[1])
