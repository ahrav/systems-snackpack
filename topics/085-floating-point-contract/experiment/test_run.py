#!/usr/bin/env python3
"""run.py locates rustup through PATH; the home-directory path is a fallback only."""
import os
import pathlib
import stat
import subprocess
import sys
import tempfile

run_py = pathlib.Path(__file__).with_name('run.py')
SHIM = '''#!/bin/sh
# The shim answers the toolchain probe and fails every other invocation to stop the experiment early.
case "$*" in
  "run 1.93.1 rustc -vV") echo "rustc shim 1.93.1"; exit 0 ;;
  *) echo "shim refuses: $*" >&2; exit 1 ;;
esac
'''


def test_rustup_resolves_from_path_when_home_has_no_cargo():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        bindir, home, out = tmp / 'bin', tmp / 'home', tmp / 'out'
        bindir.mkdir()
        home.mkdir()
        shim = bindir / 'rustup'
        shim.write_text(SHIM)
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
        env = dict(os.environ, HOME=str(home), PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}")
        p = subprocess.run([sys.executable, str(run_py), str(out)], env=env,
                           text=True, capture_output=True, timeout=120, check=False)
        assert 'FileNotFoundError' not in p.stderr, p.stderr
        assert (out / 'rustc.json').exists(), 'toolchain probe never ran'
        assert p.returncode != 0 and 'compile failed' in p.stderr, p.stderr


if __name__ == '__main__':
    test_rustup_resolves_from_path_when_home_has_no_cargo()
    print('ok')
