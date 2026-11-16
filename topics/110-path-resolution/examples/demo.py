import os
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as tmp:
    base = Path(tmp)
    root, outside = base / "root", base / "outside"
    (root / "job").mkdir(parents=True)
    outside.mkdir()
    (root / "job" / "report").write_text("INSIDE\n")
    (outside / "report").write_text("OUTSIDE\n")
    candidate = root / "job" / "report"
    checked = candidate.resolve()
    assert root.resolve() in checked.parents
    rootfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    held = os.open("job/report", os.O_RDONLY, dir_fd=rootfd)
    try:
        (root / "job").rename(root / "saved")
        (root / "job").symlink_to("../outside")
        reopened = os.open(
            "job/report", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=rootfd
        )
        try:
            bad = os.read(reopened, 100).decode().strip()
            good = os.read(held, 100).decode().strip()
            assert (bad, good) == ("OUTSIDE", "INSIDE")
            print("reopened:", bad)
            print("held:", good)
        finally:
            os.close(reopened)
    finally:
        os.close(held)
        os.close(rootfd)
