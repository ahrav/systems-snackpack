#!/usr/bin/env python3
"""campaign.py rejects a replay whose resident order differs from the oracle, with or without -O."""
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


def campaign_exit(binary, out, *flags):
    return subprocess.run([sys.executable, *flags, str(campaign), '--binary', str(binary), '--out', str(out)],
                          text=True, capture_output=True, timeout=600).returncode


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    fake = tmp / 'fake_replay.py'
    fake.write_text(FAKE_REPLAY)
    fake.chmod(0o755)
    assert campaign_exit(fake, tmp / 'plain') != 0, 'campaign accepted a resident order that differs from the oracle'
    assert campaign_exit(fake, tmp / 'optimized', '-O') != 0, 'campaign accepted a wrong resident order under python -O'
    assert not (tmp / 'optimized' / 'summary.json').exists(), 'campaign wrote a summary for an invalid run'
print('ok')
