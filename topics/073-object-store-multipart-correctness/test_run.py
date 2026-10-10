"""run.py rejects inherited compiler, profile, and loader-interposition settings before touching the output path."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
REJECTED = {
    "CARGO_BUILD_RUSTFLAGS": "-C target-cpu=native",
    "CARGO_BUILD_RUSTC_WRAPPER": "/usr/bin/env",
    "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER": "/usr/bin/env",
    "RUSTFLAGS": "-C target-cpu=native",
    "CARGO_PROFILE_RELEASE_LTO": "fat",
    "LD_PRELOAD": "/nonexistent/interposer.so",
    "LD_AUDIT": "/nonexistent/auditor.so",
    "DYLD_INSERT_LIBRARIES": "/nonexistent/interposer.dylib",
}


class EnvironmentGuard(unittest.TestCase):
    def test_rejected_variables_stop_the_campaign_before_output(self):
        base = {k: v for k, v in os.environ.items() if k not in REJECTED}
        for name, value in REJECTED.items():
            with self.subTest(variable=name), tempfile.TemporaryDirectory() as tmp:
                out = pathlib.Path(tmp) / "campaign"
                proc = subprocess.run(
                    [sys.executable, str(ROOT / "run.py"), str(out)],
                    cwd=ROOT, env={**base, name: value}, text=True, capture_output=True, timeout=120,
                )
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertIn(name, proc.stderr)
                self.assertIn("clear Cargo compiler/profile and loader-interposition", proc.stderr)
                self.assertFalse(out.exists(), "rejected run must not create the output directory")


if __name__ == "__main__":
    unittest.main()
