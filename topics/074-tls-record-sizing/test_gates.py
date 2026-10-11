"""check.py, run.py, and analyze.py reject invalid evidence with and without Python optimization.

Fake toolchain shims replace cc, pkg-config, openssl, and the compiled probe, so
every test runs in seconds without OpenSSL headers and exercises only the gates.
"""
import itertools
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
SCRIPTS = ("check.py", "run.py", "analyze.py")
CLI_VERSION = "OpenSSL 9.9.9 1 Jan 2030"
MODES = ("", "1")


def executable(path, body):
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def fake_probe(path, *, correct=True, runtime=CLI_VERSION, before=""):
    """Shell probe printing one row shaped like probe.c output; `before` runs first."""
    row = {
        "cap": 16384, "length": 16384, "write_size": 16384, "repeats": 8, "records": 1,
        "wire_bytes": 16406, "ns_per_response": 1.0, "setup_us": 1.0, "teardown_us": 1.0,
        "openssl": runtime, "correct": correct,
    }
    return executable(path, "#!/bin/sh\n" + before + "\nprintf '%s\\n' '" + json.dumps(row) + "'\n")


def oracle_probe(path):
    """Python probe that reproduces check.py's framing arithmetic and accepts every input."""
    return executable(path, f"""#!{sys.executable}
import json, sys
cap, length, write_size = (int(x) for x in sys.argv[1:4])
pending, records, wire = max(length, 0), 0, 0
while pending and min(cap, write_size) > 0:
    group = min(pending, write_size); pending -= group
    while group:
        take = min(group, cap); group -= take; records += 1; wire += take + 22
print(json.dumps({{"correct": True, "records": records, "wire_bytes": wire, "openssl": {CLI_VERSION!r}}}))
""")


def fake_toolchain(tmp, probe):
    """PATH directory whose cc copies `probe` to its -o target; pkg-config and openssl are stubs."""
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    executable(bin_dir / "cc", f"#!/bin/sh\nif [ \"$1\" = --version ]; then echo fake-cc; exit 0; fi\n"
               f"while [ $# -gt 1 ]; do [ \"$1\" = -o ] && out=$2; shift; done\ncp {probe} \"$out\"\n")
    executable(bin_dir / "pkg-config", "#!/bin/sh\necho -lfake\n")
    executable(bin_dir / "openssl", f"#!/bin/sh\necho '{CLI_VERSION} (Library: {CLI_VERSION})'\necho 'platform: fake'\n")
    return bin_dir


def run_script(script, args, *, cwd, mode, path_prefix=None, extra_env=None):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONOPTIMIZE"}
    env["PYTHONOPTIMIZE"] = mode
    if path_prefix:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env['PATH']}"
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(cwd / script), *map(str, args)],
                          cwd=cwd, env=env, text=True, capture_output=True, timeout=300)


def campaign_rows(*, drop_caps=(), drop_block=None, workload="bulk"):
    """108-row campaign with ns_per_response favouring 16384, minus the requested rows."""
    rows = []
    for block, order in enumerate(itertools.permutations([1024, 4096, 16384])):
        for name in ("tiny", "one_k", "sixteen_k", "bulk", "tiny_writes", "four_k_writes"):
            for cap in order:
                if name == workload and (cap in drop_caps or block == drop_block):
                    continue
                rows.append({"workload": name, "block": block, "cap": cap, "records": 1, "wire_bytes": 1,
                             "ns_per_response": 1000.0 * (16384 // cap) + 1000.0})
    return rows


class CheckGates(unittest.TestCase):
    def test_incorrect_row_fails(self):
        for mode in MODES:
            with self.subTest(PYTHONOPTIMIZE=mode), tempfile.TemporaryDirectory() as tmp:
                probe = fake_probe(pathlib.Path(tmp) / "probe", correct=False)
                proc = run_script("check.py", [probe], cwd=ROOT, mode=mode)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertNotIn("passed", proc.stdout)

    def test_accepted_invalid_input_fails(self):
        for mode in MODES:
            with self.subTest(PYTHONOPTIMIZE=mode), tempfile.TemporaryDirectory() as tmp:
                probe = oracle_probe(pathlib.Path(tmp) / "probe")
                proc = run_script("check.py", [probe], cwd=ROOT, mode=mode)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertNotIn("passed", proc.stdout)


class AnalyzeGates(unittest.TestCase):
    def analyze(self, rows, mode):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            proc = run_script("analyze.py", [root], cwd=ROOT, mode=mode)
            return proc, (root / "summary.json").exists()

    def test_complete_campaign_selects_winner(self):
        for mode in MODES:
            with self.subTest(PYTHONOPTIMIZE=mode):
                proc, written = self.analyze(campaign_rows(), mode)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertTrue(written)
                self.assertTrue(all(r["winner"] == 16384 for r in json.loads(proc.stdout)))

    def test_lone_candidate_is_rejected(self):
        for mode in MODES:
            with self.subTest(PYTHONOPTIMIZE=mode):
                proc, written = self.analyze(campaign_rows(drop_caps=(1024, 4096)), mode)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertFalse(written, "no summary may be written for an incomplete candidate set")

    def test_missing_block_is_rejected(self):
        for mode in MODES:
            with self.subTest(PYTHONOPTIMIZE=mode):
                proc, written = self.analyze(campaign_rows(drop_block=3), mode)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertFalse(written)


class RunGates(unittest.TestCase):
    def campaign(self, tmp, probe, mode, extra_env=None):
        """Copy the topic scripts into tmp so a tampering probe can touch only the copy."""
        work = pathlib.Path(tmp) / "topic"
        work.mkdir()
        for name in (*SCRIPTS, "probe.c"):
            shutil.copy(ROOT / name, work / name)
        bin_dir = fake_toolchain(pathlib.Path(tmp), probe)
        out = pathlib.Path(tmp) / "campaign"
        proc = run_script("run.py", [out], cwd=work, mode=mode, path_prefix=bin_dir, extra_env=extra_env)
        return proc, out, work

    def test_crypto_override_is_rejected_before_output(self):
        for mode in MODES:
            with self.subTest(PYTHONOPTIMIZE=mode), tempfile.TemporaryDirectory() as tmp:
                probe = fake_probe(pathlib.Path(tmp) / "probe")
                proc, out, _ = self.campaign(tmp, probe, mode, {"LD_PRELOAD": "/nonexistent/interposer.so"})
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertFalse(out.exists(), "rejected run must not create the output directory")

    def test_correct_campaign_completes(self):
        for mode in MODES:
            with self.subTest(PYTHONOPTIMIZE=mode), tempfile.TemporaryDirectory() as tmp:
                probe = fake_probe(pathlib.Path(tmp) / "probe")
                proc, out, _ = self.campaign(tmp, probe, mode)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(len((out / "runs.jsonl").read_text().splitlines()), 108)

    def test_incorrect_row_fails(self):
        for mode in MODES:
            with self.subTest(PYTHONOPTIMIZE=mode), tempfile.TemporaryDirectory() as tmp:
                probe = fake_probe(pathlib.Path(tmp) / "probe", correct=False)
                proc, _, _ = self.campaign(tmp, probe, mode)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertNotIn("108 correct", proc.stdout)

    def test_runtime_library_mismatch_fails(self):
        for mode in MODES:
            with self.subTest(PYTHONOPTIMIZE=mode), tempfile.TemporaryDirectory() as tmp:
                probe = fake_probe(pathlib.Path(tmp) / "probe", runtime="OpenSSL 1.1.1w 11 Sep 2023")
                proc, _, _ = self.campaign(tmp, probe, mode)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertNotIn("108 correct", proc.stdout)

    def test_source_change_during_campaign_fails(self):
        for mode in MODES:
            with self.subTest(PYTHONOPTIMIZE=mode), tempfile.TemporaryDirectory() as tmp:
                source = pathlib.Path(tmp) / "topic" / "probe.c"
                probe = fake_probe(pathlib.Path(tmp) / "probe", before=f"echo '// tampered' >> {source}")
                proc, _, work = self.campaign(tmp, probe, mode)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertNotIn("108 correct", proc.stdout)
                self.assertNotEqual((work / "probe.c").read_bytes(), (ROOT / "probe.c").read_bytes())


if __name__ == "__main__":
    unittest.main()
