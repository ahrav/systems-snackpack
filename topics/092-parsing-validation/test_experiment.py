#!/usr/bin/env python3
"""experiment.py rejects parser output that differs from the oracle, with or without -O."""
import os
import pathlib
import subprocess
import sys
import tempfile

experiment = pathlib.Path(__file__).with_name('experiment.py')
ORACLE = '''
import re, sys
def oracle(data):
    if re.fullmatch(rb'(?:(?:0|[1-9][0-9]{0,9})\\n)*', data) is None:
        return None
    values = [int(f) for f in data.splitlines()]
    return values if all(v <= 0xffffffff for v in values) else None
'''
# WRONG_VERIFY exercises oracle-mismatch rejection: it answers every verify request with the vector [1].
WRONG_VERIFY = '#!/usr/bin/env python3\nimport sys\nfor line in sys.stdin:\n    print("OK 1\\nOK 1\\nOK 1")\n'
# WRONG_BENCH passes verification and exercises benchmark rejection by reporting one extra value for inputs the oracle accepts.
WRONG_BENCH = '#!/usr/bin/env python3' + ORACLE + '''
if sys.argv[1] == 'verify':
    for line in sys.stdin:
        values = oracle(bytes.fromhex(line.strip()))
        answer = 'ERR' if values is None else 'OK' + ''.join(f' {v}' for v in values)
        print(answer); print(answer); print(answer)
else:
    _, _, algorithm, path, iters = sys.argv
    data = open(path, 'rb').read()
    values = oracle(data)
    count = 0 if values is None else len(values) + 1
    checksum = 0 if values is None else sum(values)
    print(f'{algorithm},{len(data)},{iters},1000,{"true" if values is not None else "false"},{count},{checksum}')
'''


def experiment_run(binary, out, *flags):
    # The plain child runs at optimization level 0 even when the caller's environment sets PYTHONOPTIMIZE.
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONOPTIMIZE'}
    return subprocess.run([sys.executable, *flags, str(experiment), str(binary), str(out)],
                          text=True, capture_output=True, timeout=600, env=env)


def require(condition, message):
    # Explicit checks run under -O, which strips assert statements and their operands.
    if not condition:
        raise SystemExit(message)


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    for name, source, message in [('wrong_verify.py', WRONG_VERIFY, 'parser output differs from oracle'),
                                  ('wrong_bench.py', WRONG_BENCH, 'benchmark output differs from oracle')]:
        fake = tmp / name
        fake.write_text(source)
        fake.chmod(0o755)
        for flags in ((), ('-O',)):
            out = tmp / f'{name}-{"".join(flags) or "plain"}'
            run = experiment_run(fake, out, *flags)
            require(run.returncode != 0 and message in run.stderr,
                    f'experiment accepted {name} with flags {flags!r}: exit {run.returncode}, stderr tail: {run.stderr[-300:]!r}')
            require(not (out / 'summary.json').exists(),
                    f'experiment wrote a summary for an invalid run of {name} with flags {flags!r}')
print('ok')
