#!/usr/bin/env python3
"""campaign.py rejects a replay whose resident order differs from the oracle, with or without -O."""
import os
import pathlib
import subprocess
import sys
import tempfile

campaign = pathlib.Path(__file__).with_name('campaign.py')
FAKE_REPLAY = '''#!/usr/bin/env python3
import json, sys
policy, _path, _cap, _uni, _age, repeats, expected = sys.argv[1:]
print(json.dumps(dict(policy=policy, requests=262144, hits=int(expected), repeats=int(repeats), elapsed_ns=1000, residents=[])))
'''


def campaign_run(binary, out, *flags):
    # The plain child runs at optimization level 0 even when the caller's environment sets PYTHONOPTIMIZE.
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONOPTIMIZE'}
    return subprocess.run([sys.executable, *flags, str(campaign), '--binary', str(binary), '--out', str(out)],
                          text=True, capture_output=True, timeout=600, env=env)


def require(condition, message):
    # Explicit checks run under -O, which strips assert statements and their operands.
    if not condition:
        raise SystemExit(message)


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    fake = tmp / 'fake_replay.py'
    fake.write_text(FAKE_REPLAY)
    fake.chmod(0o755)
    plain = campaign_run(fake, tmp / 'plain')
    require(plain.returncode != 0 and 'resident order differs from oracle' in plain.stderr,
            'campaign accepted a resident order that differs from the oracle')
    optimized = campaign_run(fake, tmp / 'optimized', '-O')
    require(optimized.returncode != 0 and 'resident order differs from oracle' in optimized.stderr,
            'campaign accepted a wrong resident order under python -O')
    require(not (tmp / 'optimized' / 'summary.json').exists(), 'campaign wrote a summary for an invalid run')
print('ok')
