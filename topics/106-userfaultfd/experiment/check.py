"""Compare every output byte with an eager, algebraic epoch oracle."""
import itertools
import json
import pathlib
import subprocess
import sys
import tempfile

if not __debug__:
    raise SystemExit("validation uses assert: run without python3 -O or PYTHONOPTIMIZE")

binary = str(pathlib.Path(sys.argv[1]).resolve())
results = []
for pages, writers, passes, mode in itertools.product((1, 17, 256), (1, 4), (1, 8), ("pre", "fault", "race")):
    with tempfile.TemporaryDirectory() as temp:
        run = subprocess.run([binary, str(pages), str(writers), str(passes), mode],
                             cwd=temp, capture_output=True, text=True, timeout=20)
        if run.returncode == 77:
            print(json.dumps({"status": "unavailable", "stderr": run.stderr}))
            sys.exit(77)
        assert run.returncode == 0, (run.returncode, run.stderr)
        row = json.loads(run.stdout)
        size = row["page_size"]
        initial = bytes((p * 17 + j * 3) % 256 for p in range(pages) for j in range(size))
        final = bytes((b + passes) % 256 for b in initial)
        assert pathlib.Path(temp, "snapshot.bin").read_bytes() == initial
        assert pathlib.Path(temp, "live.bin").read_bytes() == final
        assert row["fault_copies"] + row["scan_copies"] == pages
        if mode == "pre":
            assert row["events"] == 0 and row["scan_copies"] == pages
        if mode == "fault":
            assert row["fault_copies"] == pages and row["events"] == pages
        row["mode"] = mode
        results.append(row)
print(json.dumps({"status": "pass", "processes": len(results), "results": results}, indent=2))
