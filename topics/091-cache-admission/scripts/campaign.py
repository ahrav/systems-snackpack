#!/usr/bin/env python3
"""Cold logical caches, resident traces, balanced fresh-process policy timing."""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import statistics
import struct
import subprocess
import time

POLICIES = ['fifo', 'lru', 'frequency', 'aged']
WORKLOADS = ['hot', 'scan', 'shift', 'cycle', 'uniform']
N, CAP, UNIVERSE, AGE, REPEATS = 262144, 128, 8192, 8192, 8


def trace_for(name):
    state = 0x12345678
    trace = []
    for i in range(N):
        if name == 'hot':
            key = i % 64
        elif name == 'scan':
            # Alternate 512 hot references with a 512-key scan.
            offset = i % 1024
            key = offset % 64 if offset < 512 else 64 + ((i // 1024) * 512 + offset - 512) % (UNIVERSE - 64)
        elif name == 'shift':
            key = i % CAP + (CAP if i >= N // 2 else 0)
        elif name == 'cycle':
            key = i % (CAP + 1)
        else:
            state ^= (state << 13) & 0xffffffff
            state ^= state >> 17
            state ^= (state << 5) & 0xffffffff
            key = state % UNIVERSE
        trace.append(key)
    return trace


def oracle(trace, policy):
    # Timestamp selection is independent of the native indexed linked list.
    resident, counts, phases = {}, {}, [0, 0]
    for t, key in enumerate(trace):
        if policy == 'aged' and t and t % AGE == 0:
            counts = {k: n // 2 for k, n in counts.items()}
        counts[key] = min(65535, counts.get(key, 0) + 1)
        if key in resident:
            phases[int(t >= len(trace) // 2)] += 1
            if policy != 'fifo':
                resident[key] = t
        else:
            if len(resident) == CAP:
                victim = min(resident, key=resident.get)
                if policy in ('frequency', 'aged') and counts[key] <= counts[victim]:
                    continue
                del resident[victim]
            resident[key] = t
    return dict(hits=sum(phases), phase_hits=phases, residents=sorted(resident, key=resident.get))


def command_output(cmd):
    p = subprocess.run(cmd, text=True, capture_output=True)
    return dict(command=cmd, status=p.returncode, stdout=p.stdout.strip(), stderr=p.stderr.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    affinity = None
    if hasattr(os, 'sched_getaffinity'):
        allowed = sorted(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {allowed[0]})
        affinity = dict(inherited=allowed, selected=allowed[0])
    meta = dict(platform=platform.platform(), machine=platform.machine(), host=platform.node(),
                affinity=affinity, rust=command_output(['rustc', '+1.93.1', '--version']),
                cpu=command_output(['lscpu']) if platform.system() == 'Linux' else dict(machine=platform.machine()),
                n=N, capacity=CAP, universe=UNIVERSE, age=AGE, repeats=REPEATS,
                start_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                binary_sha256=hashlib.sha256(Path(args.binary).read_bytes()).hexdigest())
    (out / 'metadata.json').write_text(json.dumps(meta, indent=2) + '\n')
    schedules = [POLICIES[i:] + POLICIES[:i] for i in range(4)]
    schedules += [list(reversed(s)) for s in schedules]
    records, expectations = [], {}
    with (out / 'samples.jsonl').open('w') as log:
        for name in WORKLOADS:
            trace = trace_for(name)
            path = out / (name + '.bin')
            path.write_bytes(struct.pack('<' + 'I' * len(trace), *trace))
            expectations[name] = dict(trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                      policies={p: oracle(trace, p) for p in POLICIES})
            for block, order in [(-1, POLICIES)] + list(enumerate(schedules)):
                for position, policy in enumerate(order):
                    expect = expectations[name]['policies'][policy]
                    cmd = [args.binary, policy, str(path), str(CAP), str(UNIVERSE), str(AGE), str(REPEATS), str(expect['hits'])]
                    record = json.loads(subprocess.check_output(cmd, text=True))
                    assert record['residents'] == expect['residents']
                    record.update(workload=name, block=block, position=position,
                                  ns_per_request=record['elapsed_ns'] / (N * REPEATS))
                    log.write(json.dumps(record) + '\n')
                    log.flush()
                    records.append(record)
            print(name, {p: expectations[name]['policies'][p]['hits'] for p in POLICIES}, flush=True)
    (out / 'oracle.json').write_text(json.dumps(expectations, indent=2) + '\n')
    summary = {}
    for name in WORKLOADS:
        samples = {p: [r['ns_per_request'] for r in records if r['workload'] == name and r['policy'] == p and r['block'] >= 0] for p in POLICIES}
        summary[name] = dict(timings={p: dict(median=statistics.median(v), minimum=min(v), maximum=max(v)) for p, v in samples.items()})
        comparisons = {}
        for a, b in itertools.combinations(POLICIES, 2):
            ratios = [x/y for x,y in zip(samples[a], samples[b])]
            verdict = b if min(ratios) > 1.05 else a if max(ratios) < 1/1.05 else 'tie' if min(ratios) >= 1/1.05 and max(ratios) <= 1.05 else 'unresolved'
            comparisons[a + '/' + b] = dict(verdict=verdict, ratio_min=min(ratios), ratio_max=max(ratios))
        summary[name]['comparisons'] = comparisons
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('complete: 160 measured fresh processes and 20 warmups; all hits and resident orders match oracle')


if __name__ == '__main__':
    main()
