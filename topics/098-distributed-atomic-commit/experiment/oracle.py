#!/usr/bin/env python3
"""Check an abstract transaction specification, independently of Rust transitions.

The oracle ignores implementation action labels when checking safety. It projects
onto participant states and applies a separate declarative legal-step relation.
Graph coverage is the explorer's responsibility; this checker validates its output.
"""
import collections
import json
import sys


def check(path):
    nodes, edges = {}, []
    with open(path) as stream:
        for line in stream:
            f = line.rstrip().split('\t')
            if f[0] == 'meta':
                n, mode = int(f[1]), f[2]
            elif f[0] == 'node':
                nodes[int(f[1])] = (tuple(map(int, f[2])), *map(int, f[3:]))
            elif f[0] == 'edge':
                edges.append((int(f[1]), int(f[2]), f[3]))
    assert nodes[0] == ((0,) * n, 0, 0, 0, 1, 0, 0)
    violations = collections.Counter()
    parents, forward, reverse = {0: None}, collections.defaultdict(list), collections.defaultdict(list)
    for a, b, label in edges:
        forward[a].append((b, label))
        reverse[b].append(a)
        before, after = nodes[a][0], nodes[b][0]
        changed = [i for i in range(n) if before[i] != after[i]]
        legal = not changed
        if len(changed) == 1:
            i = changed[0]
            old, new = before[i], after[i]
            legal = ((old, new) == (0, 1)
                     or (old in (0, 1) and new == 3 and 2 not in before)
                     or (old == 1 and new == 2 and all(p in (1, 2) for p in before)))
        if not legal:
            violations['abstract_step'] += 1
        if nodes[a][2] in (2, 3) and nodes[b][2] != nodes[a][2]:
            violations['decision_changed'] += 1
        for i in range(n):
            if before[i] in (2, 3) and after[i] != before[i]:
                violations['terminal_changed'] += 1
    queue = collections.deque([0])
    while queue:
        a = queue.popleft()
        for b, label in forward[a]:
            if b not in parents:
                parents[b] = (a, label)
                queue.append(b)
    assert len(parents) == len(nodes), 'unreachable exported node'
    bad = None
    terminal = set()
    # A sends 10 to B; third participant audits the transaction with delta zero.
    delta = (-10, 10, 0)[:n]
    for i, (p, votes, decision, volatile, alive, commits, aborts) in nodes.items():
        if 2 in p and 3 in p:
            violations['agreement'] += 1
            if bad is None:
                bad = i
        if 2 in p and any(x not in (1, 2) for x in p):
            violations['commit_validity'] += 1
        if all(x in (2, 3) for x in p):
            terminal.add(i)
            if sum(d for d, x in zip(delta, p) if x == 2) != 0:
                violations['terminal_transfer_total'] += 1
    # Existential recovery: every reachable state has a path to uniform completion.
    # This does not prove termination under unfair scheduling or endless failures.
    can_finish = {i for i in terminal if len(set(nodes[i][0])) == 1}
    queue = collections.deque(can_finish)
    while queue:
        for a in reverse[queue.popleft()]:
            if a not in can_finish:
                can_finish.add(a)
                queue.append(a)
    witness = []
    while bad is not None and parents[bad] is not None:
        a, label = parents[bad]
        witness.append({'action': label, 'participants': nodes[bad][0], 'decision': nodes[bad][2]})
        bad = a
    result = dict(mode=mode, participants=n, states=len(nodes), edges=len(edges),
                  violations=dict(violations), states_with_completion_path=len(can_finish),
                  witness=list(reversed(witness)))
    print(json.dumps(result, indent=2))
    if mode == 'Safe':
        assert not violations, 'safe model violates abstract specification'
        assert len(can_finish) == len(nodes), 'state without a completion path'
        assert any(p == (2,) * n for p, *_ in nodes.values())
        assert any(p == (3,) * n for p, *_ in nodes.values())
    else:
        assert violations['agreement'] > 0, 'fault was not detected'
        assert witness, 'fault needs a reachable witness'


if __name__ == '__main__':
    check(sys.argv[1])
