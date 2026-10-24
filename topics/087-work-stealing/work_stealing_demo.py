#!/usr/bin/env python3
"""Deterministic work-stealing model with a serial oracle.

The model is deliberately single-process.  It checks task accounting and shows
the scheduling trade-off without claiming measurements of a production runtime.
"""
import argparse
import json


def leaf_cost(index: int) -> int:
    """A deterministic irregular workload: most leaves cost 1, some cost 100."""
    mixed = (index * 1103515245 + 12345) & 0x7fffffff
    return 100 if mixed % 19 == 0 else 1


def subtree_cost(depth: int, path: int) -> int:
    if depth == 0:
        return leaf_cost(path)
    return subtree_cost(depth - 1, path * 2) + subtree_cost(depth - 1, path * 2 + 1)


def static_blocks(depth: int, workers: int) -> list[int]:
    leaves = 1 << depth
    loads = [0] * workers
    for leaf in range(leaves):
        loads[(leaf * workers) // leaves] += leaf_cost(leaf)
    return loads


def work_steal(depth: int, cutoff: int, workers: int) -> tuple[list[int], int, int, int]:
    queues = [[] for _ in range(workers)]
    queues[0].append((depth, 0))
    loads = [0] * workers
    steals = tasks = failures = 0

    while any(queues):
        worker = min(range(workers), key=lambda i: loads[i])
        if queues[worker]:
            node = queues[worker].pop()  # owner takes newest work
        else:
            victim = max(range(workers), key=lambda i: len(queues[i]))
            if not queues[victim]:
                failures += 1
                continue
            node = queues[victim].pop(0)  # thief takes oldest work
            steals += 1
        remaining, path = node
        tasks += 1
        if remaining <= cutoff:
            loads[worker] += subtree_cost(remaining, path)
        else:
            # The owner can continue with the newest child.  The older child
            # remains available to a thief.
            queues[worker].append((remaining - 1, path * 2))
            queues[worker].append((remaining - 1, path * 2 + 1))
    return loads, tasks, steals, failures


def report(depth: int, cutoff: int, workers: int) -> dict:
    oracle = subtree_cost(depth, 0)
    static = static_blocks(depth, workers)
    stolen, tasks, steals, failures = work_steal(depth, cutoff, workers)
    if sum(static) != oracle or sum(stolen) != oracle:
        raise AssertionError("scheduler lost or duplicated work")
    return {
        "depth": depth,
        "cutoff": cutoff,
        "workers": workers,
        "serial_oracle": oracle,
        "static_loads": static,
        "work_steal_loads": stolen,
        "static_makespan_model": max(static),
        "work_steal_makespan_model": max(stolen),
        "tasks": tasks,
        "steals": steals,
        "failed_steal_attempts": failures,
    }


def self_test() -> None:
    cases = 0
    for depth in range(1, 11):
        for cutoff in range(depth + 1):
            for workers in (1, 2, 3, 4, 8):
                item = report(depth, cutoff, workers)
                assert sum(item["static_loads"]) == item["serial_oracle"]
                assert sum(item["work_steal_loads"]) == item["serial_oracle"]
                cases += 1
    print(f"self-test: {cases} accounting cases passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depth", type=int, default=14)
    parser.add_argument("--cutoff", type=int, default=6)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        print(json.dumps(report(args.depth, args.cutoff, args.workers), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
