"""Sequential reservation model. Unbounded integers; no weak-memory simulation."""
from collections import deque
import random


class Ring:
    def __init__(self, capacity):
        assert capacity >= 2
        self.n = capacity
        self.head = self.tail = 0
        self.seq = list(range(capacity))
        self.values = [None] * capacity
        self.reserved = set()

    def reserve(self):
        if self.tail - self.head == self.n:
            return None
        p = self.tail
        assert self.seq[p % self.n] == p
        self.tail += 1
        self.reserved.add(p)
        return p

    def publish(self, p, value):
        assert p in self.reserved
        self.reserved.remove(p)
        self.values[p % self.n] = value
        self.seq[p % self.n] = p + 1

    def pop(self):
        if self.head == self.tail:
            return ("empty", None)
        p = self.head
        if self.seq[p % self.n] != p + 1:
            return ("pending", None)
        value = self.values[p % self.n]
        self.values[p % self.n] = None
        self.seq[p % self.n] = p + self.n
        self.head += 1
        return ("value", value)


def test_hole():
    q = Ring(4)
    a, b = q.reserve(), q.reserve()
    q.publish(b, "B")
    assert q.pop() == ("pending", None)
    q.publish(a, "A")
    assert q.pop() == ("value", "A")
    assert q.pop() == ("value", "B")
    assert q.pop() == ("empty", None)


def test_oracle():
    for capacity in [2, 3, 4, 17]:
        q, oracle, rng = Ring(capacity), deque(), random.Random(78)
        for value in range(20000):
            if rng.randrange(2):
                ticket = q.reserve()
                if len(oracle) == capacity:
                    assert ticket is None
                else:
                    assert ticket is not None
                    q.publish(ticket, value)
                    oracle.append(value)
            else:
                expected = ("value", oracle.popleft()) if oracle else ("empty", None)
                assert q.pop() == expected
        while oracle:
            assert q.pop() == ("value", oracle.popleft())
        assert q.pop() == ("empty", None)


def test_all_publication_orders():
    from itertools import permutations
    for order in permutations(range(4)):
        q = Ring(4)
        tickets = [q.reserve() for _ in range(4)]
        assert q.reserve() is None
        ready, next_value = set(), 0
        for ticket in order:
            q.publish(tickets[ticket], ticket)
            ready.add(ticket)
            while next_value in ready:
                assert q.pop() == ("value", next_value)
                next_value += 1
            assert q.pop() == (("empty", None) if next_value == 4 else ("pending", None))


if __name__ == "__main__":
    test_hole()
    test_oracle()
    test_all_publication_orders()
    print("publication hole observed; FIFO restored after A publishes")
    print("80000 deque-oracle steps and all 24 publication orders passed")
