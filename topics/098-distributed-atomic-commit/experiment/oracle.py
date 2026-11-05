#!/usr/bin/env python3
"""Check an abstract transaction specification, independently of Rust transitions.

The oracle ignores implementation action labels when checking safety. It projects
onto participant states plus the durable coordinator decision and applies a
separate declarative legal-step relation.
Graph coverage is the explorer's responsibility; this checker validates its output.
"""
import collections
import json
import sys


def require(condition, message):
    """Fail the check with a nonzero exit; an explicit check survives ``python -O``."""
    if not condition:
        sys.exit('oracle: ' + message)


def check(path):
    nodes, edges, n, mode = {}, [], 0, ''
    with open(path) as stream:
        for line in stream:
            f = line.rstrip().split('\t')
            if f[0] == 'meta':
                n, mode = int(f[1]), f[2]
            elif f[0] == 'node':
                nodes[int(f[1])] = (tuple(map(int, f[2])), *map(int, f[3:]))
            elif f[0] == 'edge':
                edges.append((int(f[1]), int(f[2]), f[3]))
    require(nodes[0] == ((0,) * n, 0, 0, 0, 1, 0, 0), 'initial state mismatch')
    violations = collections.Counter()
    parents: dict = {0: None}
    forward, reverse = collections.defaultdict(list), collections.defaultdict(list)
    mutant_step = {'Timeout': 'prepared_abort_before_decision', 'Early': 'commit_before_decision'}
    mutant_edges = set()
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
                     or (old == 0 and new == 3 and 2 not in before)
                     or (old == 1 and new == 3 and 2 not in before and nodes[a][2] == 3)
                     or (old == 1 and new == 2 and all(p in (1, 2) for p in before)
                         and nodes[a][2] == 2))
            if (old, new) == (1, 3) and nodes[a][2] != 3:
                violations['prepared_abort_before_decision'] += 1
                mutant_edges.add((a, b, 'prepared_abort_before_decision'))
            if (old, new) == (1, 2) and nodes[a][2] != 2:
                violations['commit_before_decision'] += 1
                mutant_edges.add((a, b, 'commit_before_decision'))
        if not legal:
            violations['abstract_step'] += 1
        if nodes[a][2] != nodes[b][2] and not (nodes[a][2] == 0 and nodes[b][2] in (2, 3)):
            violations['decision_changed'] += 1
        if len(changed) + (nodes[b][2] != nodes[a][2]) > 1:
            violations['two_durable_records'] += 1
        for i in range(n):
            if before[i] in (2, 3) and after[i] != before[i]:
                violations['terminal_changed'] += 1
    # A fault witness must pass through the requested mode's mutant step.
    wanted = mutant_step.get(mode)
    through_mutant = {0: wanted is None}
    queue = collections.deque([0])
    while queue:
        a = queue.popleft()
        for b, label in forward[a]:
            if b not in parents:
                parents[b] = (a, label)
                through_mutant[b] = through_mutant[a] or (a, b, wanted) in mutant_edges
                queue.append(b)
    require(len(parents) == len(nodes), 'unreachable exported node')
    bad = None
    terminal = set()
    # A sends 10 to B; third participant audits the transaction with delta zero.
    delta = (-10, 10, 0)[:n]
    for i in parents:
        p, votes, decision, volatile, alive, commits, aborts = nodes[i]
        if 2 in p and 3 in p:
            violations['agreement'] += 1
            if bad is None and through_mutant[i]:
                bad = i
        if 2 in p and any(x not in (1, 2) for x in p):
            violations['commit_validity'] += 1
        if (2 in p and decision != 2) or (decision == 2 and any(x not in (1, 2) for x in p)):
            violations['decision_mismatch'] += 1
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
    require(not violations['terminal_changed'], 'terminal record changed')
    require(not violations['decision_changed'], 'durable decision changed')
    require(not violations['two_durable_records'], 'one step changed two durable records')
    if mode == 'Safe':
        require(not violations, 'safe model violates abstract specification')
        require(len(can_finish) == len(nodes), 'state without a completion path')
        require(any(p == (2,) * n for p, *_ in nodes.values()), 'no uniform commit state')
        require(any(p == (3,) * n for p, *_ in nodes.values()), 'no uniform abort state')
    else:
        require(violations[mutant_step[mode]] > 0, f'{mode} graph lacks its mutant step')
        require(violations['agreement'] > 0, 'fault was not detected')
        require(witness, 'fault needs a witness through its mutant step')


if __name__ == '__main__':
    check(sys.argv[1])
