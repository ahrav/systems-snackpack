#!/usr/bin/env python3
"""Independent parser oracle and balanced fresh-process measurement campaign."""
import argparse
import hashlib
import itertools
import json
import os
import platform
import random
import statistics
import struct
import subprocess
from pathlib import Path


def oracle(b):
    if len(b) < 8 or b[:4] != b'W093':
        return 'ERR'
    n = int.from_bytes(b[4:8], 'little')
    if n > (len(b) - 8) // 12:
        return 'ERR'
    fields = list(struct.iter_unpack('<III', b[8:8 + n * 12]))
    # Partition the payload suffix by declared lengths, then compare positions.
    cursor = 8 + n * 12
    result = []
    for ident, off, size in fields:
        payload = b[cursor:cursor + size]
        if off != cursor or len(payload) != size:
            return 'ERR'
        result.append(f'{ident}:{payload.hex()}')
        cursor += size
    return 'OK ' + ','.join(result) if cursor == len(b) else 'ERR'


def packet(rows):
    off = 8 + len(rows) * 12
    entries = []
    for ident, payload in rows:
        entries.append(struct.pack('<III', ident, off, len(payload)))
        off += len(payload)
    return b'W093' + struct.pack('<I', len(rows)) + b''.join(entries) + b''.join(b for _, b in rows)


def cases():
    rng = random.Random(930)
    result = {b'', b'W093', packet([])}
    for n in range(9):
        for size in [0, 1, 2, 7, 32]:
            b = packet([(rng.randrange(2**32), bytes(rng.randrange(256) for _ in range(size))) for _ in range(n)])
            result.add(b)
            result.update(b[:i] for i in range(len(b)))
            result.add(b + b'\x00')
            for at in range(min(len(b), 8 + 12 * n)):
                for value in [0, 1, 127, 255]:
                    result.add(b[:at] + bytes([value]) + b[at + 1:])
            for _ in range(100):
                a = bytearray(b)
                for _ in range(rng.randrange(1, 5)):
                    a[rng.randrange(len(a))] = rng.randrange(256)
                result.add(bytes(a))
    result.update(bytes(rng.randrange(256) for _ in range(rng.randrange(128))) for _ in range(2000))
    return sorted(result)


WORKLOADS = {
    'small_sparse': (128, 16, 16, 1, 5000),
    'small_full': (128, 16, 1, 1, 5000),
    'large_sparse': (128, 4096, 16, 1, 300),
    'large_full': (128, 4096, 1, 1, 100),
    'repeated_metadata': (4096, 0, 1, 32, 50),
    'repeated_payload': (128, 64, 1, 16, 300),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('binary')
    ap.add_argument('output')
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    binary = str(Path(args.binary).resolve())
    inputs = cases()
    encoded = '\n'.join(x.hex() for x in inputs) + '\n'
    p = subprocess.run([binary, 'check'], input=encoded, text=True, capture_output=True, check=True)
    actual = p.stdout.splitlines()
    expected = [oracle(x) for x in inputs]
    # The oracle check remains active under python -O and PYTHONOPTIMIZE.
    if actual != expected:
        i = next((i for i in range(min(len(actual), len(expected))) if actual[i] != expected[i]), None)
        detail = (i, actual[i], expected[i]) if i is not None else f'line count {len(actual)} != {len(expected)}'
        raise SystemExit(f'decoder disagrees with oracle: {detail}')
    report = {'inputs': len(inputs), 'accepted': sum(x.startswith('OK') for x in expected),
              'decoder_comparisons': len(inputs) * 2,
              'corpus_sha256': hashlib.sha256(encoded.encode()).hexdigest()}
    (out / 'correctness.json').write_text(json.dumps(report, indent=2) + '\n')
    cpu = None
    if hasattr(os, 'sched_getaffinity'):
        cpu = min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {cpu})
    cpuinfo = Path('/proc/cpuinfo')
    metadata = {'uname': list(platform.uname()), 'cpu': cpu,
                'cpuinfo': cpuinfo.read_text() if cpuinfo.exists() else 'unavailable on macOS',
                'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip(),
                'binary_sha256': hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
                'workloads': WORKLOADS, 'blocks': 8,
                'limits': 'Warm input; allocation/copy/drop included for owned. Input construction and process startup excluded. Frequency, thermals, competing load and SMT uncontrolled.'}
    (out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    samples = []
    # Every campaign starts from an empty samples file, matching summary.json.
    with (out / 'samples.jsonl').open('w') as f:
        for name, params in WORKLOADS.items():
            for mode in ['borrowed', 'owned']:
                subprocess.run([binary, mode, *map(str, params)], check=True, capture_output=True)
            for block in range(8):
                modes = ['borrowed', 'owned'] if block % 2 == 0 else ['owned', 'borrowed']
                for mode in modes:
                    raw = subprocess.check_output([binary, mode, *map(str, params)], text=True).strip()
                    observed, ns, iterations, checksum = raw.split(',')
                    if observed != mode:
                        raise SystemExit(f'probe reported mode {observed!r} for {mode!r}')
                    row = dict(workload=name, block=block, mode=mode, ns=int(ns),
                               iterations=int(iterations), checksum=int(checksum), ns_per_batch=int(ns)/int(iterations))
                    samples.append(row)
                    f.write(json.dumps(row) + '\n')
                    f.flush()
    summaries = []
    for name in WORKLOADS:
        stats = {}
        values = {}
        for mode in ['borrowed', 'owned']:
            values[mode] = [x['ns_per_batch'] for x in samples if x['workload'] == name and x['mode'] == mode]
            v = values[mode]
            stats[mode] = dict(median=statistics.median(v), min=min(v), max=max(v))
        ratios = [o / b for b, o in zip(values['borrowed'], values['owned'])]
        verdict = ('borrowed' if min(ratios) > 1.05 else 'owned' if max(ratios) < 1/1.05
                   else 'tie' if all(1/1.05 <= r <= 1.05 for r in ratios) else 'unresolved')
        summaries.append(dict(workload=name, stats=stats, paired_owned_over_borrowed=ratios, verdict=verdict))
    (out / 'summary.json').write_text(json.dumps(summaries, indent=2) + '\n')
    print(json.dumps(report))
    print(json.dumps(summaries))


if __name__ == '__main__':
    main()
