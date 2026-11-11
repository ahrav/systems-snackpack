"""Fresh-process paired trials; validate native output with a page-set oracle."""
import json
import os
import platform
import subprocess
import sys

binary = os.path.abspath(sys.argv[1])
rows = []
# Keep all parent/child work on one permitted CPU to control placement.
affinity = None
if hasattr(os, "sched_getaffinity"):
    affinity = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {affinity})
for count in (1024, 4096):
    for passes in (1, 8):
        for block in range(-1, 8):
            order = ("packed", "scattered") if block % 2 == 0 else ("scattered", "packed")
            for layout in order:
                r = json.loads(subprocess.check_output(
                    [binary, layout, str(count), str(passes)], timeout=30))
                p = r["page_size"]
                offsets = range(count) if layout == "packed" else range(0, count * p, p)
                pages = len({offset // p for offset in offsets})
                expected = pages * p // 1024
                for phase in ("before", "after"):
                    for actor in ("parent", "child"):
                        s = r[actor + "_" + phase]
                        assert s["rss_kib"] == count * p // 1024, r
                        assert s["huge_kib"] == 0 and s["swap_kib"] == 0, r
                gain = sum(r[a + "_after"]["pss_kib"] - r[a + "_before"]["pss_kib"]
                           for a in ("parent", "child"))
                assert gain == expected, (gain, expected, r)
                for actor in ("parent", "child"):
                    assert r[actor + "_before"]["private_dirty_kib"] == 0, r
                    assert r[actor + "_after"]["private_dirty_kib"] == expected, r
                assert r["parent_bytes_ok"] and r["child_bytes_ok"]
                r.update(block=block, warmup=block < 0, extra_pss_kib=gain,
                         oracle_pages=pages)
                rows.append(r)
print(json.dumps({"host": platform.uname()._asdict(), "cpu": affinity,
                  "trials": rows}, indent=2))
