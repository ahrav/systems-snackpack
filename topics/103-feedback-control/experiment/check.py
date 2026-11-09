"""Independent Fraction/history oracle and paired workload comparison. Python 3.9+."""
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
import sys
from fractions import Fraction

if not __debug__:
    raise SystemExit('Run Python without -O so oracle checks remain active')

POLICIES = ('fast', 'slow', 'feedforward')


def oracle(load, valid, policy, measurement, actuation):
    # Reconstruct readiness by absolute command timestamps; no FIFO queues or
    # fixed-point controller arithmetic from the Rust implementation.
    rows, commands, ready_history = [], {}, {}
    desired, backlog = Fraction(10), 0
    for tick, arrivals in enumerate(load):
        ready = commands.get(tick - actuation, 10)
        ready_history[tick] = ready
        timestamp = tick - measurement
        demand = load[timestamp] if timestamp >= 0 else 6000
        ready_sample = ready_history.get(timestamp, 10)
        if timestamp < 0 or valid[timestamp]:
            target = Fraction(demand, 600)
            if policy == 'feedforward':
                desired = target
            else:
                gain = Fraction(1, 8) if policy == 'slow' else Fraction(1)
                desired += gain * (target - ready_sample)
            desired = min(Fraction(40), max(Fraction(1), desired))
        commands[tick] = math.ceil(desired)
        backlog += arrivals
        served = min(backlog, 1000 * ready)
        backlog -= served
        rows.append([ready, int(desired * 4800), commands[tick], backlog])
    return rows


def execute(binary, load, valid, policy, measurement, actuation):
    result = subprocess.run([binary, policy, str(measurement), str(actuation)],
                            input=''.join(f'{x} {int(v)}\n' for x, v in zip(load, valid)),
                            text=True, capture_output=True, check=True)
    return [list(map(int, line.split())) for line in result.stdout.splitlines()]


def metrics(rows):
    ready, _, command, queue = zip(*rows)
    return dict(final_queue=queue[-1], peak_queue=max(queue), queue_request_ticks=sum(queue),
                replica_ticks=sum(ready), command_changes=sum(a != b for a, b in zip((10,) + command[:-1], command)),
                final_ready_span=max(ready[-40:]) - min(ready[-40:]))


def workload(name, seed):
    rng = random.Random(seed)
    load, valid = [], []
    for tick in range(240):
        if name == 'step':
            value = 6000 if tick < 20 else 12000
        elif name == 'burst':
            value = 12000 if 20 <= tick < 28 else 6000
        elif name == 'noisy':
            value = 6000 + rng.randrange(-1800, 1801)
        elif name == 'saturation':
            value = 60000 if 20 <= tick < 60 else 6000
        else:
            raise ValueError(name)
        # Identical seed gives identical disturbances across all policy arms.
        if name != 'noisy' and 20 <= tick < 80:
            value += rng.randrange(-300, 301)
        load.append(value)
        valid.append(not (100 <= tick < 105))
    return load, valid


def main(binary):
    digest = hashlib.sha256()
    comparisons = 0
    for seed in range(60):
        rng = random.Random(seed)
        load = [rng.randrange(100001) for _ in range(80)]
        valid = [rng.random() > 0.15 for _ in load]
        m, a = seed % 8, 1 + seed % 7
        for policy in POLICIES:
            actual = execute(binary, load, valid, policy, m, a)
            assert actual == oracle(load, valid, policy, m, a), (seed, policy)
            comparisons += len(actual)
            digest.update(json.dumps(actual).encode())
    samples = []
    traces = {}
    for name in ('step', 'burst', 'noisy', 'saturation'):
        for seed in range(20):
            load, valid = workload(name, seed)
            for policy in POLICIES:
                rows = execute(binary, load, valid, policy, 2, 3)
                assert rows == oracle(load, valid, policy, 2, 3), (name, seed, policy)
                comparisons += len(rows)
                digest.update(json.dumps(rows).encode())
                samples.append(dict(workload=name, seed=seed, policy=policy, **metrics(rows)))
                if seed == 0:
                    traces[name + '/' + policy] = dict(load=load, valid=valid, rows=rows)
    summary = {}
    for name in ('step', 'burst', 'noisy', 'saturation'):
        summary[name] = {}
        for policy in POLICIES:
            group = [x for x in samples if x['workload'] == name and x['policy'] == policy]
            summary[name][policy] = {key: dict(median=statistics.median([x[key] for x in group]),
                                               min=min(x[key] for x in group), max=max(x[key] for x in group))
                                     for key in metrics(traces[name + '/' + policy]['rows'])}
    print(json.dumps(dict(host=platform.platform(), machine=platform.machine(), python=sys.version,
                         comparisons=comparisons, digest=digest.hexdigest(), summary=summary,
                         samples=samples, traces=traces), indent=2))


if __name__ == '__main__':
    main(sys.argv[1])
